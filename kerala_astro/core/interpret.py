"""
Dasha interpretation: translate the chart's planetary positions into
phala (outcome) descriptions for each Mahadasha and Antardasha.

Method follows Kerala/Parashari tradition:
  1. Lord's natural significations (Karaka)
  2. Lord's house placement
  3. Lord's house ownership (rasis it rules from Lagna)
  4. Lord's strength (dignity, retrograde, combustion)
  5. Lord's relationship to Lagna lord
  6. Antardasha lord's relationship to Mahadasha lord
"""

from typing import List, Dict
from .chart import Chart
from .dasha import DashaPeriod
from .constants import (
    NATURAL_KARAKAS, BHAVA_MEANINGS, RASI_LORDS,
    NATURAL_RELATIONS, OWN_SIGNS,
)


def _house_ownership(chart: Chart, planet: str) -> List[int]:
    """Which houses (1-12) the planet rules from the Lagna."""
    houses = []
    lagna = chart.lagna_rasi_index
    for h in range(1, 13):
        rasi_idx = (lagna + h - 1) % 12
        if RASI_LORDS[rasi_idx] == planet:
            houses.append(h)
    return houses


def _classify_house(house: int) -> str:
    if house in (1, 4, 7, 10): return "kendra"
    if house in (1, 5, 9): return "trikona"
    if house in (6, 8, 12): return "dusthana"
    if house in (3, 6, 10, 11): return "upachaya"
    return "other"


def _strength_summary(chart: Chart, planet: str) -> str:
    p = chart.planets[planet]
    bits = []
    if p.dignity:
        bits.append(p.dignity)
    if p.retrograde and planet not in ("Sun", "Moon"):
        bits.append("retrograde")
    if planet == "Mercury":
        sun = chart.planets["Sun"]
        if abs(sun.longitude - p.longitude) < 14 and p.rasi_index == sun.rasi_index:
            bits.append("combust")
    return ", ".join(bits) if bits else "neutral strength"


def interpret_mahadasha(chart: Chart, md: DashaPeriod) -> str:
    """Return a paragraph describing the Mahadasha's likely themes."""
    lord = md.lord
    p = chart.planets[lord]
    karakas = NATURAL_KARAKAS[lord]
    owned = _house_ownership(chart, lord)
    placement = p.house
    placement_type = _classify_house(placement)
    strength = _strength_summary(chart, lord)
    bhava_meaning = BHAVA_MEANINGS[placement]

    # Lagna-lord relationship for benefic/malefic shading
    lagna_lord = RASI_LORDS[chart.lagna_rasi_index]
    relation = "self" if lord == lagna_lord else NATURAL_RELATIONS.get(
        lagna_lord, {}).get(lord, "N")
    rel_text = {
        "F": "friendly to the Lagna lord",
        "N": "neutral to the Lagna lord",
        "E": "in adverse relation to the Lagna lord",
        "self": "the Lagna lord itself",
    }[relation]

    owned_houses_text = ""
    if owned:
        owned_houses_text = ("rules " +
            ", ".join(f"house {h} ({BHAVA_MEANINGS[h].split('(')[0].strip()})"
                      for h in owned))

    para = (
        f"During the Mahadasha of {lord} ({md.start.date()} → "
        f"{md.end.date()}, {md.duration_years:.1f} years), the themes of "
        f"{', '.join(karakas[:3])} come to the fore.\n\n"
        f"{lord} is placed in house {placement} — {bhava_meaning} — "
        f"in {p.rasi_name}, with {strength}. This is a {placement_type} placement"
    )
    if owned_houses_text:
        para += f", and {lord} also {owned_houses_text}"
    para += f". {lord} is {rel_text}.\n\n"

    # Phala based on dignity and house
    if p.dignity.startswith("Exalt") or p.dignity.startswith("Deep Exalt"):
        para += (f"Because {lord} is exalted, the period tends to deliver its "
                 f"results in full measure. Expect notable progress in "
                 f"{karakas[0].lower()} and matters of house {placement}.\n")
    elif p.dignity.startswith("Own"):
        para += (f"In its own sign, {lord} gives stable, steady results across "
                 f"its significations.\n")
    elif p.dignity.startswith("Deep Debilit") or p.dignity.startswith("Debilit"):
        para += (f"Debilitated, {lord} may produce setbacks or delays in "
                 f"{karakas[0].lower()} and house {placement} matters unless "
                 f"Neechabhanga is present in the chart.\n")
    else:
        para += (f"With ordinary dignity, results will be mixed and shaped "
                 f"strongly by the antardasha lord and current transits.\n")

    # House-driven outlook
    if placement_type == "trikona":
        para += ("A trikona placement supports dharma, fortune and inner "
                 "growth during this period. Generally favourable.\n")
    elif placement_type == "kendra":
        para += ("A kendra placement gives the period prominence in worldly "
                 "matters — career, home, partnerships, status.\n")
    elif placement_type == "dusthana":
        para += ("A dusthana placement asks for caution — health, debts, or "
                 "hidden adversaries may demand attention. Such placements "
                 "can also yield Vipareeta-style unexpected gains when other "
                 "lords cooperate.\n")
    elif placement_type == "upachaya":
        para += ("An upachaya placement means results improve with effort "
                 "over time — the latter half of the dasha tends to be "
                 "stronger than the start.\n")

    # Recommendation
    para += (f"\nWatch the antardashas of planets friendly to {lord} for "
             f"opportunities; periods of {lord}'s enemies will test patience.")

    return para


def interpret_antardasha(chart: Chart, maha: DashaPeriod,
                        antar: DashaPeriod) -> str:
    """Short paragraph for an antardasha within a mahadasha."""
    ml, al = maha.lord, antar.lord
    if ml == al:
        relation_text = (f"the antardasha of {al} within its own Mahadasha — "
                         f"a concentrated period where the {al} themes peak")
    else:
        rel = NATURAL_RELATIONS.get(ml, {}).get(al, "N")
        rel_text = {"F": "friend", "N": "neutral", "E": "enemy"}[rel]
        relation_text = f"{al} is a {rel_text} of {ml}"

    al_planet = chart.planets[al]
    al_houses = _house_ownership(chart, al)
    al_place = al_planet.house

    text = (
        f"{ml}-{al} period ({antar.start.date()} → {antar.end.date()}, "
        f"{antar.duration_years*12:.1f} months): {relation_text}. "
        f"{al} sits in house {al_place} ({al_planet.rasi_name}"
    )
    if al_planet.dignity:
        text += f", {al_planet.dignity.lower()}"
    text += ")"
    if al_houses:
        text += f" and rules house(s) {', '.join(str(h) for h in al_houses)}"
    text += ". "

    if al in ("Jupiter", "Venus") and not al_planet.dignity.startswith("Debilit"):
        text += "Generally a supportive sub-period."
    elif al in ("Saturn", "Mars", "Rahu", "Ketu"):
        text += ("A demanding sub-period — discipline and patience help; "
                 "check transits before major decisions.")
    else:
        text += "Mixed results, weighted by transits and the natal placement above."
    return text
