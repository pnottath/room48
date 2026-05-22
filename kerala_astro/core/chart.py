"""
Astronomical computation layer.
Uses Swiss Ephemeris with Lahiri (Chitrapaksha) ayanamsa — Kerala standard.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import math

import swisseph as swe
import pytz
from timezonefinder import TimezoneFinder

from .constants import (
    RASIS, RASI_LORDS, NAKSHATRAS, NAKSHATRA_GANAM, NAKSHATRA_NADI,
    SWE_PLANET_IDS, GRAHAS, EXALTATION, DEBILITATION, OWN_SIGNS,
    NATURAL_RELATIONS, DEGREES_PER_RASI, DEGREES_PER_NAKSHATRA,
    DEGREES_PER_PADA,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BirthData:
    """User input — all the agent needs to compute a chart."""
    name: str
    year: int
    month: int
    day: int
    hour: int           # 24-hour local time
    minute: int
    second: int = 0
    latitude: float = 0.0     # decimal degrees, N positive
    longitude: float = 0.0    # decimal degrees, E positive
    timezone_name: Optional[str] = None   # IANA name; auto-detected if None
    place_name: str = ""


@dataclass
class PlanetPosition:
    name: str
    longitude: float        # 0–360 sidereal
    rasi_index: int         # 0–11
    rasi_name: str
    degrees_in_rasi: float
    nakshatra: str
    nakshatra_lord: str
    pada: int               # 1–4
    house: int              # 1–12, whole-sign from Lagna
    retrograde: bool = False
    speed: float = 0.0
    dignity: str = ""       # "Exalted" / "Debilitated" / "Own sign" / "" etc.


@dataclass
class Chart:
    birth: BirthData
    jd_ut: float                       # Julian Day, Universal Time
    ayanamsa: float                    # Lahiri value at birth, degrees
    lagna_longitude: float             # sidereal Asc
    lagna_rasi_index: int
    lagna_rasi_name: str
    lagna_nakshatra: str
    lagna_pada: int
    planets: Dict[str, PlanetPosition] = field(default_factory=dict)

    # Convenience
    def planet_in_house(self, house: int) -> List[str]:
        return [p.name for p in self.planets.values() if p.house == house]

    def planets_in_rasi(self, rasi_index: int) -> List[str]:
        return [p.name for p in self.planets.values() if p.rasi_index == rasi_index]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_timezone(birth: BirthData) -> str:
    """Infer IANA timezone from lat/lon if not supplied."""
    if birth.timezone_name:
        return birth.timezone_name
    tf = TimezoneFinder()
    tz = tf.timezone_at(lat=birth.latitude, lng=birth.longitude)
    if tz is None:
        raise ValueError(
            f"Could not determine timezone for ({birth.latitude}, {birth.longitude}). "
            "Please supply timezone_name explicitly."
        )
    return tz


def _local_to_utc_jd(birth: BirthData) -> float:
    """Convert local birth time to Julian Day in UT — handles historical TZ rules."""
    tzname = _resolve_timezone(birth)
    tz = pytz.timezone(tzname)
    naive = datetime(birth.year, birth.month, birth.day,
                     birth.hour, birth.minute, birth.second)
    local = tz.localize(naive, is_dst=None)
    utc = local.astimezone(pytz.utc)
    # Swiss Ephemeris expects UT fractional hour
    ut_hour = utc.hour + utc.minute / 60.0 + utc.second / 3600.0
    jd = swe.julday(utc.year, utc.month, utc.day, ut_hour, swe.GREG_CAL)
    return jd


def _nakshatra_info(longitude: float):
    """Return (nakshatra_name, lord, pada 1-4)."""
    n_index = int(longitude // DEGREES_PER_NAKSHATRA)
    n_index = n_index % 27
    name, lord = NAKSHATRAS[n_index]
    pos_in_nak = longitude - n_index * DEGREES_PER_NAKSHATRA
    pada = int(pos_in_nak // DEGREES_PER_PADA) + 1
    pada = min(max(pada, 1), 4)
    return name, lord, pada, n_index


def _dignity(planet: str, rasi_index: int, deg_in_rasi: float) -> str:
    if planet in EXALTATION:
        ex_rasi, ex_deg = EXALTATION[planet]
        if rasi_index == ex_rasi:
            # Deep exaltation if within 1° of exact degree
            if abs(deg_in_rasi - ex_deg) < 1.0:
                return "Deep Exaltation (Param-Uccha)"
            return "Exalted (Uccha)"
    if planet in DEBILITATION:
        db_rasi, db_deg = DEBILITATION[planet]
        if rasi_index == db_rasi:
            if abs(deg_in_rasi - db_deg) < 1.0:
                return "Deep Debilitation (Param-Neecha)"
            return "Debilitated (Neecha)"
    if planet in OWN_SIGNS and rasi_index in OWN_SIGNS[planet]:
        return "Own sign (Swakshetra)"
    return ""


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_chart(birth: BirthData) -> Chart:
    """
    Build a sidereal Rasi chart with whole-sign houses (Kerala convention).
    """
    # Use Lahiri (Chitrapaksha) ayanamsa
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    jd_ut = _local_to_utc_jd(birth)
    ayanamsa = swe.get_ayanamsa_ut(jd_ut)

    # Ascendant — use Placidus houses just to get the ASC, then apply whole-sign
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    cusps, ascmc = swe.houses_ex(jd_ut, birth.latitude, birth.longitude,
                                 b'P', flags)
    lagna_long = ascmc[0] % 360.0
    lagna_rasi = int(lagna_long // DEGREES_PER_RASI)
    lagna_deg = lagna_long - lagna_rasi * DEGREES_PER_RASI
    lagna_nak, lagna_nak_lord, lagna_pada, _ = _nakshatra_info(lagna_long)

    planets: Dict[str, PlanetPosition] = {}

    # First 7 planets via Swiss Ephemeris
    for name, pid in SWE_PLANET_IDS.items():
        result, _ = swe.calc_ut(jd_ut, pid, flags)
        lon = result[0] % 360.0
        speed = result[3]
        retro = speed < 0 and name not in ("Sun", "Moon")
        rasi_idx = int(lon // DEGREES_PER_RASI)
        deg_in = lon - rasi_idx * DEGREES_PER_RASI
        nak, nak_lord, pada, _ = _nakshatra_info(lon)
        house = ((rasi_idx - lagna_rasi) % 12) + 1
        planets[name] = PlanetPosition(
            name=name,
            longitude=lon,
            rasi_index=rasi_idx,
            rasi_name=RASIS[rasi_idx],
            degrees_in_rasi=deg_in,
            nakshatra=nak,
            nakshatra_lord=nak_lord,
            pada=pada,
            house=house,
            retrograde=retro,
            speed=speed,
            dignity=_dignity(name, rasi_idx, deg_in),
        )

    # Ketu = Rahu + 180°
    rahu = planets["Rahu"]
    ketu_lon = (rahu.longitude + 180.0) % 360.0
    rasi_idx = int(ketu_lon // DEGREES_PER_RASI)
    deg_in = ketu_lon - rasi_idx * DEGREES_PER_RASI
    nak, nak_lord, pada, _ = _nakshatra_info(ketu_lon)
    house = ((rasi_idx - lagna_rasi) % 12) + 1
    planets["Ketu"] = PlanetPosition(
        name="Ketu",
        longitude=ketu_lon,
        rasi_index=rasi_idx,
        rasi_name=RASIS[rasi_idx],
        degrees_in_rasi=deg_in,
        nakshatra=nak,
        nakshatra_lord=nak_lord,
        pada=pada,
        house=house,
        retrograde=True,   # always retrograde
        speed=-abs(rahu.speed),
        dignity=_dignity("Ketu", rasi_idx, deg_in),
    )

    return Chart(
        birth=birth,
        jd_ut=jd_ut,
        ayanamsa=ayanamsa,
        lagna_longitude=lagna_long,
        lagna_rasi_index=lagna_rasi,
        lagna_rasi_name=RASIS[lagna_rasi],
        lagna_nakshatra=lagna_nak,
        lagna_pada=lagna_pada,
        planets=planets,
    )


def format_chart_summary(chart: Chart) -> str:
    """Human-readable chart printout — useful for verification."""
    lines = []
    b = chart.birth
    lines.append(f"=== Janma Vivaram for {b.name} ===")
    lines.append(f"Date  : {b.year:04d}-{b.month:02d}-{b.day:02d}  "
                 f"{b.hour:02d}:{b.minute:02d}:{b.second:02d}")
    lines.append(f"Place : {b.place_name}  ({b.latitude:.4f}°N, {b.longitude:.4f}°E)")
    lines.append(f"Timezone: {_resolve_timezone(b)}")
    lines.append(f"Julian Day (UT): {chart.jd_ut:.6f}")
    lines.append(f"Ayanamsa (Lahiri): {chart.ayanamsa:.4f}°")
    lines.append("")
    lines.append(f"Lagna (Ascendant): {chart.lagna_rasi_name} "
                 f"{chart.lagna_longitude % 30:.2f}°  "
                 f"[{chart.lagna_nakshatra} pada {chart.lagna_pada}]")
    lines.append("")
    lines.append(f"{'Planet':<9}{'Rasi':<13}{'Deg':>7}  "
                 f"{'House':>5}  {'Nakshatra':<18}{'Pada':>4}  Dignity")
    lines.append("-" * 86)
    for name in GRAHAS:
        p = chart.planets[name]
        retro = " R" if p.retrograde else "  "
        lines.append(f"{name:<9}{p.rasi_name:<13}{p.degrees_in_rasi:>6.2f}{retro}"
                     f"{p.house:>5}  {p.nakshatra:<18}{p.pada:>4}  {p.dignity}")
    return "\n".join(lines)
