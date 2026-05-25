"""
FastAPI service for the Kerala Astrology Agent.

Endpoints:
    GET  /                       Service info
    GET  /health                 Health probe
    POST /api/v1/horoscope       Full horoscope (chart + yogas + dashas + interpretation)
    POST /api/v1/chart           Just the Rasi chart
    POST /api/v1/dashas          Just the Vimshottari dasha tree
    POST /api/v1/yogas           Just the detected yogas
    POST /api/v1/report-text     Plain-text human-readable report
    GET  /api/v1/timezone        Resolve timezone from lat/lon

Run with:
    uvicorn kerala_astro.api.main:app --reload --port 8000
Then open:
    http://localhost:8000/docs
"""

from datetime import datetime
from typing import Optional
import hashlib
import json
import threading
import time
import logging

from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse, Response
import swisseph as swe
from timezonefinder import TimezoneFinder

from ..core.chart import BirthData, compute_chart
from ..core.dasha import (compute_vimshottari, find_current_dasha,
                          find_current_antardasha)
from ..core.yogas import detect_all_yogas
from ..core.interpret import interpret_antardasha
from ..agent.horoscope_agent import HoroscopeAgent

# ─────────────────────────────────────────────────────────────────────────
# In-flight request deduplication
# ─────────────────────────────────────────────────────────────────────────
# When two requests arrive for the same chart+language+sections combination
# while the first is still running its LLM calls, the second waits for the
# first to finish rather than firing its own parallel burst of section
# generations. This plugs the most common cost-leak: a user hitting
# "Generate reading" again before the first request returned.
#
# The registry maps a content hash to an Event that fires when the request
# completes, plus a shared result dict.

_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT: dict[str, "_InflightEntry"] = {}
_INFLIGHT_WAIT_SECONDS = 180   # max we'll keep a follower waiting

class _InflightEntry:
    __slots__ = ("event", "result", "exc", "started_at")
    def __init__(self):
        self.event = threading.Event()
        self.result = None
        self.exc: Optional[Exception] = None
        self.started_at = time.time()

def _narrative_dedup_key(req) -> str:
    """A stable content hash for an inflight request."""
    payload = json.dumps({
        "year": req.year, "month": req.month, "day": req.day,
        "hour": req.hour, "minute": req.minute,
        "lat": round(req.latitude, 4), "lon": round(req.longitude, 4),
        "tz":  req.timezone_name,
        "lang": req.language,
        "model": req.model,
        "temp": round(req.temperature, 2),
        "sections": sorted(req.sections) if req.sections else "all",
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

_log = logging.getLogger("kerala_astro.narrative")

from .schemas import (
    BirthDataRequest, HoroscopeResponse, ChartResponse, YogaResponse,
    DashaResponse, HealthResponse, ErrorResponse,
    NarrativeRequest, NarrativeResponse, NarrativeSectionResponse,
    NarrativePdfRequest,
)
from .converters import (
    chart_to_response, yoga_to_response, dasha_to_response,
    md_to_interpretation,
)


# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------

API_VERSION = "1.0.0"

app = FastAPI(
    title="Room 48 — Kerala Astrology API",
    description=(
        "Room 48 generates a Kerala-tradition (Parashari) janma kundali from "
        "date, time and place of birth. Uses sidereal Lahiri ayanamsa "
        "and whole-sign houses. Computes Vimshottari dasha, detects classical "
        "yogas (Pancha Mahapurusha, Raja, Dhana, Gajakesari, Kuja dosha, "
        "Kalasarpa, and others), and produces a flowing LLM-narrated reading "
        "grounded strictly in the computed chart facts."
    ),
    version=API_VERSION,
    contact={"name": "Room 48"},
    license_info={"name": "For educational/spiritual use"},
)

# CORS — open by default so it's usable from any frontend. Lock down in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # By default the browser does NOT let cross-origin JS read response
    # headers other than a tiny safelist. We need Content-Disposition
    # so the PDF download flow can pick up the friendly filename
    # ("Prasanth Nottath Room48 Jaathakam.pdf") that the backend builds.
    expose_headers=["Content-Disposition"],
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_birthdata(req: BirthDataRequest) -> BirthData:
    return BirthData(
        name=req.name,
        year=req.year, month=req.month, day=req.day,
        hour=req.hour, minute=req.minute, second=req.second,
        latitude=req.latitude, longitude=req.longitude,
        timezone_name=req.timezone_name,
        place_name=req.place_name,
    )


def _resolve_tz(birth: BirthData) -> str:
    if birth.timezone_name:
        return birth.timezone_name
    tf = TimezoneFinder()
    tz = tf.timezone_at(lat=birth.latitude, lng=birth.longitude)
    if not tz:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("Could not determine timezone from coordinates. "
                    "Please supply timezone_name explicitly."))
    return tz


def _safe_compute(birth: BirthData):
    """Wrap chart computation with HTTP-friendly error mapping."""
    try:
        return compute_chart(birth)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Computation error: {e}")


DISCLAIMER = (
    "This reading is generated by Room 48 using classical Kerala/Parashari "
    "rules. It indicates tendencies and karmic themes, not fixed outcomes. "
    "Conscious effort (purushartha) and parihara (remedial measures) can "
    "modify results. For major life decisions, consult a qualified human "
    "astrologer."
)


# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root():
    return {
        "service": "Room 48 — Kerala Astrology API",
        "version": API_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "endpoints": [
            "POST /api/v1/horoscope",
            "POST /api/v1/chart",
            "POST /api/v1/dashas",
            "POST /api/v1/yogas",
            "POST /api/v1/report-text",
            "POST /api/v1/narrative",
            "GET  /api/v1/timezone",
        ],
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    # Smoke-test Swiss Ephemeris by calling get_ayanamsa
    swe_ok = False
    try:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        _ = swe.get_ayanamsa_ut(2451545.0)   # J2000
        swe_ok = True
    except Exception:
        pass
    return HealthResponse(
        status="ok" if swe_ok else "degraded",
        service="room48-kerala-astrology",
        version=API_VERSION,
        swiss_ephemeris=swe_ok,
    )


# ---------------------------------------------------------------------------
# Main horoscope endpoint
# ---------------------------------------------------------------------------

@app.post("/api/v1/horoscope",
          response_model=HoroscopeResponse,
          tags=["horoscope"],
          summary="Full janma kundali",
          responses={422: {"model": ErrorResponse}})
def generate_horoscope(req: BirthDataRequest):
    """
    Computes the complete horoscope:
    chart, yogas, full Vimshottari dasha tree, current dasha interpretation,
    upcoming Mahadasha analyses, and a plain-text report.
    """
    birth = _to_birthdata(req)
    tz_name = _resolve_tz(birth)

    chart = _safe_compute(birth)
    dashas = compute_vimshottari(chart,
                                 include_pratyantar=req.include_pratyantar)
    yogas = detect_all_yogas(chart)

    current_md = find_current_dasha(dashas)
    current_md_interp = None
    current_ad_note = None
    if current_md:
        current_md_interp = md_to_interpretation(chart, current_md)
        ad = find_current_antardasha(current_md)
        if ad:
            current_ad_note = interpret_antardasha(chart, current_md, ad)

    now = datetime.utcnow()
    upcoming = [md for md in dashas if md.start > now][: req.num_upcoming_dashas]
    upcoming_interps = [md_to_interpretation(chart, md) for md in upcoming]

    # Reuse the agent for the prose report
    agent = HoroscopeAgent(include_pratyantar=req.include_pratyantar)
    full_text = agent.generate(birth)["report_text"]

    return HoroscopeResponse(
        chart=chart_to_response(chart, tz_name),
        yogas=[yoga_to_response(y) for y in yogas],
        dashas=[dasha_to_response(d) for d in dashas],
        current_mahadasha=current_md_interp,
        current_antardasha_note=current_ad_note,
        upcoming_mahadashas=upcoming_interps,
        full_text_report=full_text,
        disclaimer=DISCLAIMER,
    )


# ---------------------------------------------------------------------------
# Slice endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/chart",
          response_model=ChartResponse,
          tags=["chart"],
          summary="Rasi chart only")
def get_chart(req: BirthDataRequest):
    birth = _to_birthdata(req)
    tz_name = _resolve_tz(birth)
    chart = _safe_compute(birth)
    return chart_to_response(chart, tz_name)


@app.post("/api/v1/dashas",
          response_model=list[DashaResponse],
          tags=["dasha"],
          summary="Vimshottari dasha tree only")
def get_dashas(req: BirthDataRequest):
    birth = _to_birthdata(req)
    chart = _safe_compute(birth)
    dashas = compute_vimshottari(chart,
                                 include_pratyantar=req.include_pratyantar)
    return [dasha_to_response(d) for d in dashas]


@app.post("/api/v1/yogas",
          response_model=list[YogaResponse],
          tags=["yogas"],
          summary="Detected yogas only")
def get_yogas(req: BirthDataRequest):
    birth = _to_birthdata(req)
    chart = _safe_compute(birth)
    yogas = detect_all_yogas(chart)
    return [yoga_to_response(y) for y in yogas]


@app.post("/api/v1/report-text",
          response_class=PlainTextResponse,
          tags=["horoscope"],
          summary="Plain-text horoscope report")
def get_report_text(req: BirthDataRequest):
    """Returns the human-readable text report (the same content the CLI prints)."""
    birth = _to_birthdata(req)
    agent = HoroscopeAgent(include_pratyantar=req.include_pratyantar)
    return agent.generate(birth)["report_text"]


# ---------------------------------------------------------------------------
# Utility endpoint
# ---------------------------------------------------------------------------

@app.get("/api/v1/timezone",
         tags=["utility"],
         summary="Resolve IANA timezone from coordinates")
def resolve_timezone(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
):
    tf = TimezoneFinder()
    tz = tf.timezone_at(lat=latitude, lng=longitude)
    if not tz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No timezone found for these coordinates.")
    return {"latitude": latitude, "longitude": longitude, "timezone": tz}


# ---------------------------------------------------------------------------
# Narrative (LLM) endpoint
# ---------------------------------------------------------------------------

from ..narrative.engine import NarrativeEngine, NarrativeOptions
from ..narrative.prompts import BRIEFS, SECTION_HEADERS, section_ids as _all_section_ids


@app.post("/api/v1/narrative",
          response_model=NarrativeResponse,
          tags=["narrative"],
          summary="LLM-generated astrological narrative",
          responses={422: {"model": ErrorResponse},
                     503: {"model": ErrorResponse}})
def generate_narrative(req: NarrativeRequest):
    """
    Computes the chart, runs the yoga and dasha engines, then asks an LLM
    to render a flowing astrological reading grounded ONLY in the computed
    facts. The LLM is constrained by a strict system prompt — it never
    invents positions, dates, or yogas.

    Provider is chosen by environment:
      - ANTHROPIC_API_KEY set → AnthropicProvider (real LLM)
      - otherwise            → EchoProvider (no network calls, for tests)

    Includes in-flight request deduplication: if a request for the
    identical chart+language+sections combination is already running,
    a second arrival waits for the first to complete rather than
    firing its own LLM calls. This prevents the most common cost-leak
    (impatient users re-tapping "Generate reading").
    """
    birth = _to_birthdata(req)
    chart = _safe_compute(birth)
    dashas = compute_vimshottari(chart, include_pratyantar=False)
    yogas = detect_all_yogas(chart)

    section_ids = req.sections if req.sections else _all_section_ids()

    try:
        engine = NarrativeEngine()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM provider unavailable: {e}",
        )

    options = NarrativeOptions(
        language=req.language,
        sections=section_ids,
        model=req.model,
        temperature=req.temperature,
        use_response_cache=req.use_response_cache,
        parallel=req.parallel,
    )

    # ── In-flight dedup ─────────────────────────────────────────────
    dedup_key = _narrative_dedup_key(req)
    is_follower = False
    entry = None
    with _INFLIGHT_LOCK:
        existing = _INFLIGHT.get(dedup_key)
        if existing is not None and not existing.event.is_set():
            entry = existing
            is_follower = True
            _log.info("dedup: follower joining in-flight request %s", dedup_key)
        else:
            entry = _InflightEntry()
            _INFLIGHT[dedup_key] = entry

    if is_follower:
        # Wait for the leading request to complete, with a ceiling so we
        # don't hang forever if something went wrong with the leader.
        if not entry.event.wait(timeout=_INFLIGHT_WAIT_SECONDS):
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Reading is still being generated. Please try again in a moment.",
            )
        if entry.exc is not None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Reading generation failed: {entry.exc}",
            )
        return entry.result

    # We are the leader — actually generate.
    try:
        try:
            result = engine.generate(chart, yogas, dashas, options)
        except Exception as e:
            entry.exc = e
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM generation failed: {e}",
            )

        section_models = [
            NarrativeSectionResponse(
                section=sid,
                title=SECTION_HEADERS[sid],
                text=result.sections.get(sid, ""),
            )
            for sid in section_ids
            if sid in result.sections
        ]

        response = NarrativeResponse(
            language=req.language,
            model=req.model,
            provider=result.provider_name,
            sections=section_models,
            markdown=result.to_markdown(include_digest=req.include_digest_in_response),
            digest=result.digest if req.include_digest_in_response else None,
            disclaimer=DISCLAIMER,
            usage={
                "response_cache_hit":   result.usage.response_cache_hit,
                "total_input_tokens":   result.usage.total_input,
                "total_output_tokens":  result.usage.total_output,
                "cache_read_tokens":    result.usage.total_cache_read,
                "cache_write_tokens":   result.usage.total_cache_write,
                "prompt_cache_hits":    sum(1 for s in result.usage.sections if s.cache_hit),
                "sections_generated":   len(result.usage.sections),
            },
        )
        entry.result = response
        return response
    finally:
        # Signal followers and clean up.
        entry.event.set()
        with _INFLIGHT_LOCK:
            # Only remove if it's still us (could've been overwritten)
            if _INFLIGHT.get(dedup_key) is entry:
                del _INFLIGHT[dedup_key]


# ─────────────────────────────────────────────────────────────────────────
# PDF export — takes an already-generated reading and returns a PDF.
# NO LLM call. NO additional Anthropic cost.
# ─────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/narrative-pdf",
          tags=["narrative"],
          summary="Render an already-generated reading as a print-quality PDF",
          responses={
              200: {"content": {"application/pdf": {}},
                    "description": "The reading as a downloadable PDF."},
              422: {"model": ErrorResponse},
              500: {"model": ErrorResponse},
          })
def generate_narrative_pdf(req: NarrativePdfRequest):
    """
    Render a previously-generated reading as a typeset PDF.

    The frontend already has the reading's Markdown (from /api/v1/narrative).
    It POSTs that markdown plus the cover-page metadata here, and gets back
    application/pdf bytes — no further LLM call is made.

    The PDF reuses the temple-paper palette and Kerala-tradition styling.
    """
    # Defer the import so the API boots even if WeasyPrint's native deps
    # are temporarily missing from the container (the error then surfaces
    # only on the PDF endpoint, not at FastAPI startup).
    try:
        from ..pdf import render_reading_pdf, ReadingPdfInput
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF renderer unavailable: {e}",
        )

    try:
        pdf_bytes = render_reading_pdf(ReadingPdfInput(
            native_name = req.native_name,
            markdown    = req.markdown,
            disclaimer  = req.disclaimer,
            birth_date  = req.birth_date,
            birth_time  = req.birth_time,
            birth_tz    = req.birth_tz,
            birth_place = req.birth_place,
            generated_on= req.generated_on,
        ))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF rendering failed: {e}",
        )

    # Build a friendly download filename:
    #   "Prasanth Nottath Room48 Jaathakam.pdf"
    # Spaces preserved, punctuation stripped, multiple spaces collapsed.
    # Falls back to "Reading" if the name field is empty.
    import re as _re
    from urllib.parse import quote as _urlquote
    cleaned = _re.sub(r"[^\w\s]", "", req.native_name, flags=_re.UNICODE)
    cleaned = _re.sub(r"\s+", " ", cleaned).strip()
    safe_name = cleaned or "Reading"
    filename = f"{safe_name} Room48 Jaathakam.pdf"

    # HTTP header values are ASCII. To support non-ASCII names (e.g.
    # Malayalam script in the future) we emit both forms per RFC 5987:
    #   - `filename="..."` with non-ASCII chars stripped, for older clients
    #   - `filename*=UTF-8''...` with the full name, for compliant clients
    ascii_stripped = filename.encode("ascii", "ignore").decode("ascii")
    # Re-collapse whitespace in case the name was entirely non-ASCII
    # (e.g. "പ്രശാന്ത്" would strip to "" and leave stray spaces).
    ascii_stripped = _re.sub(r"\s+", " ", ascii_stripped).strip()
    ascii_filename = ascii_stripped or "Reading Room48 Jaathakam.pdf"
    utf8_encoded = _urlquote(filename, safe="")
    content_disposition = (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{utf8_encoded}"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition,
            "Cache-Control": "no-store",
        },
    )
