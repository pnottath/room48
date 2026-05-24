"""
Build a tight, factual "chart digest" from the computed Chart, yogas, and
dasha tree. The digest is the ONLY source of facts the LLM is allowed to use.

We pack it densely (Markdown tables / bullet lists) so the LLM treats it
as ground truth rather than narrative to be rewritten.
"""

from datetime import datetime
from typing import List, Optional

from ..core.chart import Chart
from ..core.dasha import DashaPeriod, find_current_dasha, find_current_antardasha
from ..core.yogas import Yoga
from ..core.constants import (
    NAKSHATRA_GANAM, NAKSHATRA_NADI, RASI_LORDS, BHAVA_MEANINGS, GRAHAS,
    NATURAL_KARAKAS, NAKSHATRA_MALAYALAM, NAKSHATRA_MALAYALAM_SCRIPT,
    RASI_MALAYALAM_SCRIPT,
)


def _nak_name(nak: str, script: bool = False) -> str:
    """
    Render a nakshatra with its Kerala name in brackets:
        _nak_name("Jyeshtha")        → "Jyeshtha (Thriketta)"
        _nak_name("Jyeshtha", True)  → "Jyeshtha (Thriketta / തൃക്കേട്ട)"
    """
    mal = NAKSHATRA_MALAYALAM.get(nak)
    if not mal:
        return nak
    if script:
        ml = NAKSHATRA_MALAYALAM_SCRIPT.get(nak, "")
        return f"{nak} ({mal} / {ml})" if ml else f"{nak} ({mal})"
    return f"{nak} ({mal})"


def _rasi_name(rasi: str, script: bool = False) -> str:
    """Render a rasi, optionally with Malayalam script appended."""
    if script:
        ml = RASI_MALAYALAM_SCRIPT.get(rasi, "")
        return f"{rasi} ({ml})" if ml else rasi
    return rasi


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _planet_lines(chart: Chart, script: bool = False) -> str:
    rows = ["| Planet | Rasi | Deg | House | Nakshatra | Pada | Dignity | Retro |",
            "|---|---|---|---|---|---|---|---|"]
    for name in GRAHAS:
        p = chart.planets[name]
        rows.append(
            f"| {p.name} | {_rasi_name(p.rasi_name, script)} "
            f"| {p.degrees_in_rasi:.2f}° "
            f"| {p.house} | {_nak_name(p.nakshatra, script)} | {p.pada} "
            f"| {p.dignity or '—'} | {'Yes' if p.retrograde else 'No'} |"
        )
    return "\n".join(rows)


def _house_lines(chart: Chart) -> str:
    rows = ["| House | Significations | Lord | Lord in House | Occupants |",
            "|---|---|---|---|---|"]
    for h in range(1, 13):
        lord = RASI_LORDS[(chart.lagna_rasi_index + h - 1) % 12]
        lord_house = chart.planets[lord].house
        occupants = chart.planet_in_house(h)
        occ = ", ".join(occupants) if occupants else "—"
        # Truncate the parenthetical for compactness
        sig = BHAVA_MEANINGS[h].split("(")[0].strip()
        rows.append(f"| {h} | {sig} | {lord} | {lord_house} | {occ} |")
    return "\n".join(rows)


def _yoga_lines(yogas: List[Yoga]) -> str:
    if not yogas:
        return "_No major yogas detected by the rule set._"
    rows = []
    for y in yogas:
        rows.append(
            f"- **{y.name}** ({y.sanskrit}) [{y.category}, {y.strength}]  \n"
            f"  Basis: {y.basis}  \n"
            f"  Classical result: {y.result}"
        )
    return "\n".join(rows)


def _dasha_summary(dashas: List[DashaPeriod], n: int = 9) -> str:
    rows = ["| Mahadasha | Start | End | Years |", "|---|---|---|---|"]
    for md in dashas[:n]:
        rows.append(
            f"| {md.lord} | {md.start.date()} | {md.end.date()} "
            f"| {md.duration_years:.2f} |"
        )
    return "\n".join(rows)


def _current_period_block(chart: Chart, dashas: List[DashaPeriod]) -> str:
    now = datetime.utcnow()
    md = find_current_dasha(dashas, now)
    if not md:
        return "_Birth is outside the calculated 120-year window._"

    ad = find_current_antardasha(md, now)
    md_p = chart.planets[md.lord]
    ad_p = chart.planets[ad.lord] if ad else None

    lines = [
        f"- **Current Mahadasha**: {md.lord} "
        f"({md.start.date()} → {md.end.date()}, "
        f"{md.duration_years:.1f} years)",
        f"  - Natal placement: house {md_p.house} ({md_p.rasi_name}), "
        f"{md_p.dignity or 'no special dignity'}"
        f"{', retrograde' if md_p.retrograde else ''}",
        f"  - Karakas: {', '.join(NATURAL_KARAKAS[md.lord][:3])}",
    ]
    if ad:
        lines.extend([
            f"- **Current Antardasha**: {ad.lord} "
            f"({ad.start.date()} → {ad.end.date()}, "
            f"{ad.duration_years*12:.1f} months)",
            f"  - Natal placement: house {ad_p.house} ({ad_p.rasi_name}), "
            f"{ad_p.dignity or 'no special dignity'}",
        ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public: build the full digest
# ---------------------------------------------------------------------------

def build_chart_digest(chart: Chart,
                       yogas: List[Yoga],
                       dashas: List[DashaPeriod],
                       language: str = "english") -> str:
    """
    Produce the canonical factual digest that the LLM must rely on.

    Nakshatra names are always rendered with their Kerala name in brackets:
        "Jyeshtha (Thriketta)" for English/Manglish output
        "Jyeshtha (Thriketta / തൃക്കേട്ട)" for true Malayalam-script output
    so the narrator can preserve them naturally in prose.
    """
    script = (language == "malayalam_script")
    b = chart.birth
    moon = chart.planets["Moon"]
    lagna_lord = RASI_LORDS[chart.lagna_rasi_index]
    ll_planet = chart.planets[lagna_lord]

    parts: List[str] = []

    # 1. Identity
    parts.append("## NATIVE")
    parts.append(
        f"- Name: {b.name}\n"
        f"- Birth: {b.year:04d}-{b.month:02d}-{b.day:02d} "
        f"{b.hour:02d}:{b.minute:02d}:{b.second:02d} "
        f"(local at {b.place_name or 'place'})\n"
        f"- Coordinates: {b.latitude:.4f}°N, {b.longitude:.4f}°E"
    )

    # 2. Lagna / Janma core — with Kerala/Malayalam names
    parts.append("\n## LAGNA & JANMA CORE")
    parts.append(
        f"- Lagna (Ascendant): **{_rasi_name(chart.lagna_rasi_name, script)}** "
        f"{chart.lagna_longitude % 30:.2f}° "
        f"(nakshatra {_nak_name(chart.lagna_nakshatra, script)}, "
        f"pada {chart.lagna_pada})\n"
        f"- Lagna lord: **{lagna_lord}** in house {ll_planet.house} "
        f"({_rasi_name(ll_planet.rasi_name, script)}"
        f"{', ' + ll_planet.dignity.lower() if ll_planet.dignity else ''})\n"
        f"- Janma Rasi (Moon-sign): **{_rasi_name(moon.rasi_name, script)}**\n"
        f"- Janma Nakshatra: **{_nak_name(moon.nakshatra, script)}** "
        f"pada {moon.pada} (lord {moon.nakshatra_lord})\n"
        f"- Ganam: {NAKSHATRA_GANAM[moon.nakshatra]}, "
        f"Nadi: {NAKSHATRA_NADI[moon.nakshatra]}\n"
        f"- Ayanamsa (Lahiri): {chart.ayanamsa:.4f}°"
    )

    # 3. Planets — with bracketed Kerala names in the Nakshatra column
    parts.append("\n## PLANETARY POSITIONS")
    parts.append(_planet_lines(chart, script))

    # 4. Houses
    parts.append("\n## BHAVAS (HOUSES)")
    parts.append(_house_lines(chart))

    # 5. Yogas (already-computed; LLM must NOT invent new ones)
    parts.append("\n## YOGAS DETECTED")
    parts.append("_The following yogas were detected by the rule engine. "
                 "Do not claim any other yoga is present._")
    parts.append(_yoga_lines(yogas))

    # 6. Dashas
    parts.append("\n## VIMSHOTTARI DASHA — FULL CYCLE")
    parts.append(_dasha_summary(dashas))

    # 7. Current period
    parts.append("\n## CURRENT PERIOD")
    parts.append(_current_period_block(chart, dashas))

    return "\n".join(parts)
