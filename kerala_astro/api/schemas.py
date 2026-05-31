"""
Pydantic schemas for the Kerala Astrology API.

Request models describe what the client sends; response models describe
the JSON shape returned. Keeping these separate from the internal
dataclasses (in core/) lets the API evolve without touching the calc engine.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class BirthDataRequest(BaseModel):
    """Input from the client. Time must be exact local time at the place."""
    name: str = Field(..., min_length=1, max_length=100,
                      description="Native's name (for the report header).")
    year: int = Field(..., ge=1800, le=2200)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23,
                      description="Hour in 24-hour format, local time.")
    minute: int = Field(..., ge=0, le=59)
    second: int = Field(0, ge=0, le=59)

    latitude: float = Field(..., ge=-90, le=90,
                            description="Decimal degrees, North positive.")
    longitude: float = Field(..., ge=-180, le=180,
                             description="Decimal degrees, East positive.")
    timezone_name: Optional[str] = Field(
        None,
        description=("IANA timezone name (e.g. 'Asia/Kolkata'). "
                     "If omitted, auto-detected from coordinates."))
    place_name: str = Field("", max_length=200,
                            description="Display name for the place.")

    # Options
    include_pratyantar: bool = Field(
        False,
        description="If true, include third-level Pratyantardasha "
                    "(makes response much larger).")
    num_upcoming_dashas: int = Field(
        3, ge=0, le=8,
        description="How many upcoming Mahadashas to interpret in detail.")

    @field_validator("day")
    @classmethod
    def validate_day_in_month(cls, v, info):
        # Basic sanity — full leap-year handling left to datetime in the agent
        if v > 31:
            raise ValueError("day must be 1-31")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Sample Native",
                "year": 1990, "month": 6, "day": 15,
                "hour": 7, "minute": 45, "second": 0,
                "latitude": 8.5241, "longitude": 76.9366,
                "timezone_name": "Asia/Kolkata",
                "place_name": "Thiruvananthapuram, Kerala, India",
                "include_pratyantar": False,
                "num_upcoming_dashas": 3
            }
        }
    }


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class PlanetResponse(BaseModel):
    name: str
    rasi: str
    rasi_index: int
    longitude: float = Field(..., description="Sidereal longitude (0–360°).")
    degrees_in_rasi: float
    house: int = Field(..., ge=1, le=12)
    nakshatra: str
    nakshatra_lord: str
    pada: int
    retrograde: bool
    dignity: str


class ChartResponse(BaseModel):
    name: str
    birth_datetime_local: str
    place: str
    latitude: float
    longitude: float
    timezone: str
    julian_day_ut: float
    ayanamsa_lahiri: float

    lagna_rasi: str
    lagna_longitude: float
    lagna_nakshatra: str
    lagna_pada: int

    janma_rasi: str = Field(..., description="Moon-sign (rasi)")
    janma_nakshatra: str
    janma_pada: int
    ganam: str
    nadi: str
    nakshatra_lord: str

    planets: List[PlanetResponse]
    houses: Dict[int, Dict[str, Any]] = Field(
        ..., description="House → {lord, lord_house, occupants[], significations}")


class YogaResponse(BaseModel):
    name: str
    sanskrit: str
    category: str
    strength: str
    basis: str
    result: str


class DashaResponse(BaseModel):
    lord: str
    level: str
    start: str        # ISO date
    end: str
    duration_years: float
    sub_periods: List["DashaResponse"] = Field(default_factory=list)


# Allow forward reference for nested DashaResponse
DashaResponse.model_rebuild()


class DashaInterpretationResponse(BaseModel):
    lord: str
    start: str
    end: str
    duration_years: float
    narrative: str


class HoroscopeResponse(BaseModel):
    """The full horoscope payload."""
    chart: ChartResponse
    yogas: List[YogaResponse]
    dashas: List[DashaResponse]
    current_mahadasha: Optional[DashaInterpretationResponse] = None
    current_antardasha_note: Optional[str] = None
    upcoming_mahadashas: List[DashaInterpretationResponse]
    full_text_report: str
    disclaimer: str


# ---------------------------------------------------------------------------
# Auxiliary
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    swiss_ephemeris: bool


class ErrorResponse(BaseModel):
    error: str
    detail: str


# ---------------------------------------------------------------------------
# Narrative layer
# ---------------------------------------------------------------------------

VALID_LANGUAGES = ("english", "manglish", "malayalam", "malayalam_script")
VALID_SECTIONS = ("overview", "personality", "bhava", "yogas",
                  "current_dasha", "upcoming", "closing")


class NarrativeRequest(BirthDataRequest):
    """Same as BirthDataRequest plus narrative options."""
    language: str = Field(
        "english",
        description=("Output language. "
                     "'english' = clear English, "
                     "'manglish' = Malayalam-English mix in Latin script, "
                     "'malayalam' = Malayalam in Latin transliteration, "
                     "'malayalam_script' = actual Malayalam script (മലയാളം)."))
    sections: Optional[List[str]] = Field(
        None,
        description=("Which sections to generate. If omitted, all sections "
                     "are produced. Valid: " + ", ".join(VALID_SECTIONS)))
    model: str = Field(
        "claude-sonnet-4-6",
        description="LLM model name passed to the provider.")
    temperature: float = Field(0.55, ge=0.0, le=1.0)
    include_digest_in_response: bool = Field(
        False,
        description="If true, the canonical chart digest is included in the response.")
    use_response_cache: bool = Field(
        True,
        description="If true, serve identical requests from disk cache "
                    "(skips LLM entirely on repeat).")
    parallel: bool = Field(
        True,
        description="If true, generate all sections concurrently. "
                    "Same cost but much faster (~7x).")

    @field_validator("language")
    @classmethod
    def _valid_language(cls, v):
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {VALID_LANGUAGES}")
        return v

    @field_validator("sections")
    @classmethod
    def _valid_sections(cls, v):
        if v is None:
            return v
        bad = [s for s in v if s not in VALID_SECTIONS]
        if bad:
            raise ValueError(f"Unknown section(s): {bad}. Valid: {VALID_SECTIONS}")
        return v


class NarrativeSectionResponse(BaseModel):
    section: str
    title: str
    text: str


class NarrativeResponse(BaseModel):
    language: str
    model: str
    provider: str
    sections: List[NarrativeSectionResponse]
    markdown: str = Field(..., description="Full reading rendered as Markdown.")
    digest: Optional[str] = None
    disclaimer: str
    usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Token usage and cache telemetry for this request.")


# ────────────────────────────────────────────────────────────────────
# PDF export
# ────────────────────────────────────────────────────────────────────

class NarrativePdfRequest(BaseModel):
    """
    Request for /api/v1/narrative-pdf — takes an ALREADY-GENERATED
    reading (the markdown the frontend just displayed) and returns a
    typeset PDF. No LLM call is made; no Anthropic cost is incurred.
    """
    native_name: str = Field(..., description="The person's name as printed on the cover.")
    markdown: str = Field(..., description="The full reading in Markdown — the same content the frontend displayed.")
    disclaimer: str = Field(..., description="Disclaimer text for the closing page.")

    # Birth details for the cover page. The caller (frontend) supplies
    # these already formatted so we don't have to know about locales.
    birth_date: str = Field(..., description="Pre-formatted birth date, e.g. '15 June 1990'.")
    birth_time: str = Field(..., description="Pre-formatted birth time, e.g. '07:45'.")
    birth_tz:   str = Field(..., description="Timezone, e.g. 'Asia/Kolkata'.")
    birth_place: str = Field(..., description="Birthplace, e.g. 'Thiruvananthapuram, Kerala'.")

    # Optional — the cover shows when the reading was generated. If
    # omitted, the server uses 'now'.
    generated_on: Optional[str] = Field(None, description="Optional pre-formatted date, e.g. '24 May 2026'.")


# ────────────────────────────────────────────────────────────────────
# Ask a question (Q&A flow)
# ────────────────────────────────────────────────────────────────────

class AskRequest(BirthDataRequest):
    """
    Request for /api/v1/ask — chart-grounded Q&A.

    The user submits birth details and a single question. The backend
    computes the chart (deterministic, no LLM) and builds the digest,
    then sends ONE constrained LLM call. The answer is grounded only
    in the digest's facts; out-of-scope or unverifiable questions get
    a clean refusal.
    """
    question: str = Field(
        ...,
        min_length=4,
        max_length=500,
        description="The user's question about their chart.",
    )
    language: str = Field(
        "english",
        description="english | manglish | malayalam | malayalam_script",
    )
    model: str = Field(
        "claude-sonnet-4-6",
        description="Anthropic model to use.",
    )

    @field_validator("language")
    @classmethod
    def _valid_lang(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {VALID_LANGUAGES}")
        return v

    @field_validator("question")
    @classmethod
    def _clean_question(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 4:
            raise ValueError("question is too short")
        return v


class AskGrounding(BaseModel):
    """One piece of chart-fact grounding used by the answer."""
    fact: str = Field(..., description="A specific fact from the digest the answer relies on.")


class AskResponse(BaseModel):
    """Response from /api/v1/ask."""
    question: str = Field(..., description="The original question, echoed back.")
    answer: str = Field(..., description="The grounded answer in flowing prose.")
    grounded_in: List[AskGrounding] = Field(
        default_factory=list,
        description="Chart facts the answer drew on, for transparency.",
    )
    classification: str = Field(
        ...,
        description="answerable | interpretive | out_of_scope | refused",
    )
    language: str
    model: str
    provider: str
    disclaimer: str
    usage: Optional[Dict[str, Any]] = Field(
        None,
        description="Token usage telemetry for this call.",
    )
