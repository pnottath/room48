"""
Yoga detection engine.
Each detector returns a Yoga dataclass with name, basis, strength, and result.
Coverage follows Brihat Parashara Hora Shastra and Phaladeepika.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .chart import Chart
from .constants import (
    RASIS, RASI_LORDS, OWN_SIGNS, EXALTATION, DEBILITATION,
    GRAHAS,
)


@dataclass
class Yoga:
    name: str
    sanskrit: str
    category: str        # "Raja" / "Dhana" / "Mahapurusha" / "Dosha" / etc.
    present: bool
    strength: str = ""   # "Full" / "Partial" / "Cancelled"
    basis: str = ""      # Astrological reasoning
    result: str = ""     # Phala (effect description)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KENDRAS = [1, 4, 7, 10]
TRIKONAS = [1, 5, 9]
DUSTHANAS = [6, 8, 12]
UPACHAYAS = [3, 6, 10, 11]

def _lagna_lord(chart: Chart) -> str:
    return RASI_LORDS[chart.lagna_rasi_index]

def _house_lord(chart: Chart, house: int) -> str:
    rasi_idx = (chart.lagna_rasi_index + house - 1) % 12
    return RASI_LORDS[rasi_idx]

def _planets_in_house(chart: Chart, house: int) -> List[str]:
    return [p.name for p in chart.planets.values() if p.house == house]

def _planet_house(chart: Chart, planet: str) -> int:
    return chart.planets[planet].house

def _planet_rasi(chart: Chart, planet: str) -> int:
    return chart.planets[planet].rasi_index

def _is_kendra(h: int) -> bool: return h in KENDRAS
def _is_trikona(h: int) -> bool: return h in TRIKONAS
def _is_dusthana(h: int) -> bool: return h in DUSTHANAS

def _angular_distance(h1: int, h2: int) -> int:
    """Minimum 'house distance' on the 12-house wheel."""
    d = abs(h1 - h2) % 12
    return min(d, 12 - d)


# ---------------------------------------------------------------------------
# Pancha Mahapurusha Yogas
# ---------------------------------------------------------------------------
# Mars=Ruchaka, Mercury=Bhadra, Jupiter=Hamsa, Venus=Malavya, Saturn=Sasa
# Formed when planet is in own/exalted sign AND in a kendra from Lagna.

_MAHAPURUSHA = {
    "Mars":    ("Ruchaka", "रुचक",
                "Courageous, leader, commanding presence, military or athletic excellence, "
                "property gains, but can be aggressive."),
    "Mercury": ("Bhadra",  "भद्र",
                "Sharp intellect, scholarly, eloquent speech, business acumen, longevity, "
                "respected by the learned."),
    "Jupiter": ("Hamsa",   "हंस",
                "Virtuous, dharmic, respected, prosperous, wise; admired in society, "
                "good progeny, religious inclination."),
    "Venus":   ("Malavya", "मालव्य",
                "Beautiful, luxurious life, refined tastes, success in arts, vehicles and "
                "comforts, harmonious marriage."),
    "Saturn":  ("Sasa",    "शश",
                "Authority over land/people, leadership, persistent, can rise from humble "
                "origins; capable of harsh rule if afflicted."),
}

def detect_mahapurusha(chart: Chart) -> List[Yoga]:
    yogas = []
    for planet, (name, sansk, result) in _MAHAPURUSHA.items():
        p = chart.planets[planet]
        in_kendra = _is_kendra(p.house)
        in_own = p.rasi_index in OWN_SIGNS.get(planet, [])
        in_exalt = (planet in EXALTATION and
                    p.rasi_index == EXALTATION[planet][0])
        if in_kendra and (in_own or in_exalt):
            dignity = "exalted" if in_exalt else "own sign"
            yogas.append(Yoga(
                name=name + " Yoga",
                sanskrit=sansk,
                category="Pancha Mahapurusha",
                present=True,
                strength="Full" if in_exalt else "Strong",
                basis=f"{planet} in {dignity} ({p.rasi_name}) in kendra "
                      f"(house {p.house})",
                result=result,
            ))
    return yogas


# ---------------------------------------------------------------------------
# Gajakesari Yoga — Jupiter in a kendra from the Moon
# ---------------------------------------------------------------------------

def detect_gajakesari(chart: Chart) -> Optional[Yoga]:
    jup_h = _planet_house(chart, "Jupiter")
    moon_h = _planet_house(chart, "Moon")
    # Kendra from Moon: 1, 4, 7, 10 houses away
    diff = (jup_h - moon_h) % 12
    if diff in (0, 3, 6, 9):
        return Yoga(
            name="Gajakesari Yoga",
            sanskrit="गजकेसरी",
            category="Subha",
            present=True,
            strength="Full",
            basis=f"Jupiter in house {jup_h}, Moon in house {moon_h} "
                  f"(kendra relationship).",
            result="Confers intelligence, virtue, eloquence, lasting fame, "
                   "respect from authorities, and steady prosperity. "
                   "Native is regarded as wise and trustworthy."
        )
    return None


# ---------------------------------------------------------------------------
# Budhaditya Yoga — Sun + Mercury conjunction
# ---------------------------------------------------------------------------

def detect_budhaditya(chart: Chart) -> Optional[Yoga]:
    sun = chart.planets["Sun"]
    merc = chart.planets["Mercury"]
    if sun.rasi_index == merc.rasi_index:
        # Combustion check — Mercury within ~14° of Sun is combust
        combust = abs(sun.longitude - merc.longitude) < 14
        strength = "Partial (Mercury combust)" if combust else "Full"
        return Yoga(
            name="Budhaditya Yoga",
            sanskrit="बुधादित्य",
            category="Subha",
            present=True,
            strength=strength,
            basis=f"Sun and Mercury conjunct in {sun.rasi_name} (house {sun.house})",
            result="Sharp intellect, communication skills, success in education, "
                   "writing, and government or administrative roles. "
                   "Effect reduced if Mercury is combust."
        )
    return None


# ---------------------------------------------------------------------------
# Chandra-Mangala Yoga — Moon + Mars conjunction/exchange
# ---------------------------------------------------------------------------

def detect_chandra_mangala(chart: Chart) -> Optional[Yoga]:
    moon = chart.planets["Moon"]
    mars = chart.planets["Mars"]
    if moon.rasi_index == mars.rasi_index:
        return Yoga(
            name="Chandra-Mangala Yoga",
            sanskrit="चन्द्र-मङ्गल",
            category="Dhana",
            present=True, strength="Full",
            basis=f"Moon and Mars conjunct in {moon.rasi_name}",
            result="Wealth through enterprise, real estate, or trade. "
                   "Energetic mind, strong drive; possible tension with mother "
                   "or in domestic matters."
        )
    return None


# ---------------------------------------------------------------------------
# Sunapha / Anapha / Durudhara / Kemadruma — Moon-axis yogas
# ---------------------------------------------------------------------------

def detect_moon_yogas(chart: Chart) -> List[Yoga]:
    """Planets (excluding Sun, Rahu, Ketu) in 2nd or 12th from Moon."""
    moon_h = _planet_house(chart, "Moon")
    second_from_moon = ((moon_h - 1 + 1) % 12) + 1
    twelfth_from_moon = ((moon_h - 1 - 1) % 12) + 1

    relevant = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    in_2nd = [p for p in relevant if _planet_house(chart, p) == second_from_moon]
    in_12th = [p for p in relevant if _planet_house(chart, p) == twelfth_from_moon]
    in_with = [p for p in relevant if _planet_house(chart, p) == moon_h]

    yogas = []
    if in_2nd and not in_12th:
        yogas.append(Yoga(
            name="Sunapha Yoga", sanskrit="सुनफा", category="Chandra",
            present=True, strength="Full",
            basis=f"{', '.join(in_2nd)} in 2nd from Moon",
            result="Self-acquired wealth, intelligence, good reputation, "
                   "independent achievements."
        ))
    if in_12th and not in_2nd:
        yogas.append(Yoga(
            name="Anapha Yoga", sanskrit="अनफा", category="Chandra",
            present=True, strength="Full",
            basis=f"{', '.join(in_12th)} in 12th from Moon",
            result="Refined personality, good health, comforts, eloquence, "
                   "respected social standing."
        ))
    if in_2nd and in_12th:
        yogas.append(Yoga(
            name="Durudhara Yoga", sanskrit="दुरुधरा", category="Chandra",
            present=True, strength="Full",
            basis=f"Planets in both 2nd ({', '.join(in_2nd)}) and 12th "
                  f"({', '.join(in_12th)}) from Moon",
            result="Wealth, comforts, generosity, servants and vehicles, "
                   "happiness in family life."
        ))
    if not in_2nd and not in_12th and not in_with:
        yogas.append(Yoga(
            name="Kemadruma Yoga", sanskrit="केमद्रुम", category="Dosha",
            present=True, strength="Full",
            basis="Moon has no planets in 2nd, 12th, or conjunct (except Sun/nodes)",
            result="Struggle in early life, financial fluctuation, "
                   "loneliness or emotional difficulty. CANCELLED if Moon is in "
                   "kendra from Lagna, exalted, or aspected by Jupiter — verify "
                   "before considering this dosha active."
        ))
    return yogas


# ---------------------------------------------------------------------------
# Raja Yogas — Kendra lord + Trikona lord association
# ---------------------------------------------------------------------------

def detect_raja_yogas(chart: Chart) -> List[Yoga]:
    yogas = []
    kendra_lords = {_house_lord(chart, h): h for h in KENDRAS}
    trikona_lords = {_house_lord(chart, h): h for h in TRIKONAS}

    seen = set()
    for kl, kh in kendra_lords.items():
        for tl, th in trikona_lords.items():
            if kl == tl:
                continue   # same lord owning both — counted differently
            pair = tuple(sorted([kl, tl]))
            if pair in seen:
                continue
            seen.add(pair)
            kp = chart.planets[kl]
            tp = chart.planets[tl]
            # Conjunction
            if kp.rasi_index == tp.rasi_index:
                yogas.append(Yoga(
                    name=f"Raja Yoga ({kl}–{tl} conjunction)",
                    sanskrit="राजयोग",
                    category="Raja",
                    present=True, strength="Full",
                    basis=f"{kl} (lord of {kh}) and {tl} (lord of {th}) "
                          f"conjunct in {kp.rasi_name} (house {kp.house})",
                    result="Significant rise in status, authority, success and "
                           "recognition. Activates strongly in the dasha/bhukti "
                           "of either lord."
                ))
            # Mutual exchange (Parivartana) — kl in tl's sign and vice versa
            elif (kp.rasi_index in OWN_SIGNS.get(tl, []) and
                  tp.rasi_index in OWN_SIGNS.get(kl, [])):
                yogas.append(Yoga(
                    name=f"Parivartana Raja Yoga ({kl}↔{tl})",
                    sanskrit="परिवर्तन-राजयोग",
                    category="Raja",
                    present=True, strength="Strong",
                    basis=f"Exchange between {kl} and {tl}",
                    result="Powerful elevation in life, often through unexpected "
                           "or transformational events. Both house meanings get fused."
                ))
    return yogas


# ---------------------------------------------------------------------------
# Dhana Yogas — combinations of 2/5/9/11 lords
# ---------------------------------------------------------------------------

def detect_dhana_yogas(chart: Chart) -> List[Yoga]:
    yogas = []
    wealth_houses = [2, 5, 9, 11]
    lords = {h: _house_lord(chart, h) for h in wealth_houses}
    pairs_seen = set()
    for h1 in wealth_houses:
        for h2 in wealth_houses:
            if h1 >= h2:
                continue
            l1, l2 = lords[h1], lords[h2]
            if l1 == l2:
                continue
            key = tuple(sorted([l1, l2]))
            if key in pairs_seen:
                continue
            pairs_seen.add(key)
            p1, p2 = chart.planets[l1], chart.planets[l2]
            if p1.rasi_index == p2.rasi_index:
                yogas.append(Yoga(
                    name=f"Dhana Yoga ({h1}L–{h2}L)",
                    sanskrit="धनयोग",
                    category="Dhana",
                    present=True, strength="Strong",
                    basis=f"{l1} (lord of {h1}) and {l2} (lord of {h2}) "
                          f"conjunct in house {p1.house}",
                    result=f"Wealth accumulation through {_dhana_source(h1, h2)}. "
                           f"Activates in dasha of either planet."
                ))
    return yogas

def _dhana_source(h1: int, h2: int) -> str:
    src = {2: "family/savings/speech", 5: "intellect/children/investments",
           9: "fortune/father/dharma", 11: "gains/networks/elder siblings"}
    return f"{src[h1]} combined with {src[h2]}"


# ---------------------------------------------------------------------------
# Neechabhanga Raja Yoga — cancellation of debilitation
# ---------------------------------------------------------------------------

def detect_neechabhanga(chart: Chart) -> List[Yoga]:
    yogas = []
    for name, p in chart.planets.items():
        if name not in DEBILITATION:
            continue
        db_rasi, _ = DEBILITATION[name]
        if p.rasi_index != db_rasi:
            continue
        # Lord of the debilitation sign
        db_sign_lord = RASI_LORDS[db_rasi]
        # Planet exalted in same sign as the debilitated one
        exalter = None
        for pname, (er, _) in EXALTATION.items():
            if er == db_rasi:
                exalter = pname
                break

        cancellation_reasons = []
        # (a) Lord of debilitation sign in a kendra from Lagna or Moon
        ds_lord_planet = chart.planets[db_sign_lord]
        if _is_kendra(ds_lord_planet.house):
            cancellation_reasons.append(
                f"{db_sign_lord} (lord of debilitation sign) in kendra")
        # (b) The planet that exalts in this sign is in kendra
        if exalter and _is_kendra(chart.planets[exalter].house):
            cancellation_reasons.append(
                f"{exalter} (exalts in {p.rasi_name}) in kendra")

        if cancellation_reasons:
            yogas.append(Yoga(
                name=f"Neechabhanga Raja Yoga ({name})",
                sanskrit="नीचभङ्ग-राजयोग",
                category="Raja",
                present=True, strength="Full",
                basis=f"{name} debilitated in {p.rasi_name}, "
                      f"but cancelled because: {'; '.join(cancellation_reasons)}",
                result=f"Initial setbacks related to {name}'s significations are "
                       "overcome; results in unexpected rise, transformation of "
                       "weakness into strength, and recognition later in life."
            ))
    return yogas


# ---------------------------------------------------------------------------
# Vipareeta Raja Yoga — dusthana lord in dusthana
# ---------------------------------------------------------------------------

def detect_vipareeta(chart: Chart) -> List[Yoga]:
    yogas = []
    for h in DUSTHANAS:
        lord = _house_lord(chart, h)
        lord_p = chart.planets[lord]
        if lord_p.house in DUSTHANAS and lord_p.house != h:
            yogas.append(Yoga(
                name=f"Vipareeta Raja Yoga (Harsha/Sarala/Vimala – {h}L in {lord_p.house})",
                sanskrit="विपरीत-राजयोग",
                category="Raja",
                present=True, strength="Strong",
                basis=f"{lord} (lord of {h}) placed in house {lord_p.house}",
                result="Unexpected gains, success born of adversity, victory over "
                       "enemies, hidden strength. Best when there's no association "
                       "with benefic-house lords."
            ))
    return yogas


# ---------------------------------------------------------------------------
# Kuja Dosha (Mangal Dosha)
# ---------------------------------------------------------------------------

KUJA_HOUSES_FROM_LAGNA = {1, 2, 4, 7, 8, 12}

def detect_kuja_dosha(chart: Chart) -> Optional[Yoga]:
    mars = chart.planets["Mars"]
    moon_h = _planet_house(chart, "Moon")
    venus_h = _planet_house(chart, "Venus")

    afflicts = []
    if mars.house in KUJA_HOUSES_FROM_LAGNA:
        afflicts.append(f"from Lagna (house {mars.house})")
    # From Moon
    mars_from_moon = ((mars.house - moon_h) % 12) + 1
    if mars_from_moon in KUJA_HOUSES_FROM_LAGNA:
        afflicts.append(f"from Chandra Lagna (house {mars_from_moon} from Moon)")
    # From Venus (for marriage specifically)
    mars_from_venus = ((mars.house - venus_h) % 12) + 1
    if mars_from_venus in KUJA_HOUSES_FROM_LAGNA:
        afflicts.append(f"from Sukra (house {mars_from_venus} from Venus)")

    if afflicts:
        return Yoga(
            name="Kuja Dosha (Mangal Dosha)",
            sanskrit="कुजदोष",
            category="Dosha",
            present=True,
            strength="Full" if len(afflicts) >= 2 else "Partial",
            basis="Mars in 1/2/4/7/8/12 " + " and ".join(afflicts),
            result="May cause friction in marriage, delays, or temperamental "
                   "issues with partner. Mitigated by matching with another "
                   "Manglik, by Mars in own/exalted sign, by aspect of benefic, "
                   "or after age 28. Specific parihara recommended."
        )
    return None


# ---------------------------------------------------------------------------
# Kalasarpa Yoga — all 7 planets between Rahu and Ketu
# ---------------------------------------------------------------------------

def detect_kalasarpa(chart: Chart) -> Optional[Yoga]:
    rahu_long = chart.planets["Rahu"].longitude
    ketu_long = chart.planets["Ketu"].longitude
    # Define the arc from Rahu to Ketu going forward
    def in_arc(start, end, point):
        if start < end:
            return start < point < end
        return point > start or point < end

    planets_7 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    longs = [chart.planets[p].longitude for p in planets_7]
    forward = all(in_arc(rahu_long, ketu_long, l) for l in longs)
    backward = all(in_arc(ketu_long, rahu_long, l) for l in longs)
    if forward or backward:
        direction = "Rahu→Ketu (forward)" if forward else "Ketu→Rahu (backward)"
        return Yoga(
            name="Kalasarpa Yoga",
            sanskrit="कालसर्प",
            category="Dosha",
            present=True, strength="Full",
            basis=f"All 7 planets hemmed in {direction}",
            result="Significant karmic theme around the Rahu–Ketu axis. "
                   "Life may feel constrained until mid-life; sudden rises and falls. "
                   "Often produces unusual achievement when combined with Raja yogas. "
                   "Traditional Kerala parihara: Sarpa Bali at temples like "
                   "Mannarasala, Pambumekkattu, or Vettikode."
        )
    return None


# ---------------------------------------------------------------------------
# Sarpa Dosha — Rahu/Ketu in 5th house (especially)
# ---------------------------------------------------------------------------

def detect_sarpa_dosha(chart: Chart) -> Optional[Yoga]:
    rahu_h = _planet_house(chart, "Rahu")
    ketu_h = _planet_house(chart, "Ketu")
    if rahu_h == 5 or ketu_h == 5:
        node = "Rahu" if rahu_h == 5 else "Ketu"
        return Yoga(
            name="Sarpa Dosha (5th house)",
            sanskrit="सर्पदोष",
            category="Dosha",
            present=True, strength="Partial",
            basis=f"{node} placed in 5th house",
            result="May indicate delays or difficulty regarding children, or "
                   "obstacles in higher learning/mantras. Kerala parihara includes "
                   "Naga prathishta puja and ancestral propitiation."
        )
    return None


# ---------------------------------------------------------------------------
# Saraswati Yoga — Jupiter, Venus, Mercury together strong
# ---------------------------------------------------------------------------

def detect_saraswati(chart: Chart) -> Optional[Yoga]:
    jup = chart.planets["Jupiter"]
    ven = chart.planets["Venus"]
    mer = chart.planets["Mercury"]
    benefics = [jup, ven, mer]
    # All three in kendras, trikonas, or 2nd house, and Jupiter strong
    good_houses = set(KENDRAS) | set(TRIKONAS) | {2}
    if all(p.house in good_houses for p in benefics):
        jup_strong = (jup.dignity.startswith("Exalt") or
                      jup.dignity.startswith("Own") or
                      jup.dignity.startswith("Deep Exalt"))
        if jup_strong:
            return Yoga(
                name="Saraswati Yoga",
                sanskrit="सरस्वती",
                category="Subha",
                present=True, strength="Full",
                basis=f"Jupiter ({jup.dignity or 'placed'} in {jup.rasi_name}), "
                      f"Venus and Mercury all in kendra/trikona/2nd house",
                result="Exceptional intellect, learning, eloquence, scholarship "
                       "in arts/sciences/scriptures. Famous as a knowledgeable person."
            )
    return None


# ---------------------------------------------------------------------------
# Master detector
# ---------------------------------------------------------------------------

def detect_all_yogas(chart: Chart) -> List[Yoga]:
    yogas: List[Yoga] = []
    yogas.extend(detect_mahapurusha(chart))
    g = detect_gajakesari(chart)
    if g: yogas.append(g)
    g = detect_budhaditya(chart)
    if g: yogas.append(g)
    g = detect_chandra_mangala(chart)
    if g: yogas.append(g)
    yogas.extend(detect_moon_yogas(chart))
    yogas.extend(detect_raja_yogas(chart))
    yogas.extend(detect_dhana_yogas(chart))
    yogas.extend(detect_neechabhanga(chart))
    yogas.extend(detect_vipareeta(chart))
    g = detect_kuja_dosha(chart)
    if g: yogas.append(g)
    g = detect_kalasarpa(chart)
    if g: yogas.append(g)
    g = detect_sarpa_dosha(chart)
    if g: yogas.append(g)
    g = detect_saraswati(chart)
    if g: yogas.append(g)
    return yogas


def format_yogas(yogas: List[Yoga]) -> str:
    lines = ["=== Yoga Phalam ==="]
    if not yogas:
        return "\n".join(lines + ["(No major yogas detected by the rule set.)"])
    for y in yogas:
        lines.append(f"\n● {y.name}  ({y.sanskrit})   [{y.category}]")
        lines.append(f"  Strength : {y.strength}")
        lines.append(f"  Basis    : {y.basis}")
        lines.append(f"  Result   : {y.result}")
    return "\n".join(lines)
