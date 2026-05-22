"""
Vimshottari Dasha calculator.
Standard 120-year cycle keyed off the Moon's nakshatra at birth.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

import swisseph as swe

from .constants import (
    DASHA_YEARS, DASHA_SEQUENCE, DEGREES_PER_NAKSHATRA, NAKSHATRAS,
)
from .chart import Chart


# A solar year in days — Vimshottari traditionally uses 365.25
YEAR_DAYS = 365.25


@dataclass
class DashaPeriod:
    lord: str
    start: datetime
    end: datetime
    level: str  # "Mahadasha" / "Antardasha" / "Pratyantardasha"
    sub_periods: List["DashaPeriod"] = field(default_factory=list)

    @property
    def duration_years(self) -> float:
        return (self.end - self.start).days / YEAR_DAYS

    def __repr__(self):
        return (f"<{self.level} {self.lord} "
                f"{self.start.date()} → {self.end.date()} "
                f"({self.duration_years:.2f}y)>")


def _jd_to_datetime(jd: float) -> datetime:
    y, m, d, h = swe.revjul(jd, swe.GREG_CAL)
    full_secs = h * 3600
    return (datetime(int(y), int(m), int(d))
            + timedelta(seconds=full_secs))


def _balance_at_birth(chart: Chart):
    """
    Returns (starting_lord, balance_years_remaining_in_that_lord,
             birth_datetime_utc).
    Computed from Moon's position within its nakshatra.
    """
    moon = chart.planets["Moon"]
    nak_index = int(moon.longitude // DEGREES_PER_NAKSHATRA)
    nak_name, nak_lord = NAKSHATRAS[nak_index]
    # Fraction of nakshatra already traversed
    pos_in_nak = moon.longitude - nak_index * DEGREES_PER_NAKSHATRA
    fraction_traversed = pos_in_nak / DEGREES_PER_NAKSHATRA
    total_years = DASHA_YEARS[nak_lord]
    remaining = total_years * (1 - fraction_traversed)
    birth_dt = _jd_to_datetime(chart.jd_ut)
    return nak_lord, remaining, birth_dt


def compute_vimshottari(chart: Chart,
                       num_mahadashas: int = 9,
                       include_pratyantar: bool = False
                       ) -> List[DashaPeriod]:
    """
    Build the Mahadasha → Antardasha (→ Pratyantardasha) tree.
    Default: 9 mahadashas = full 120-year cycle.
    """
    start_lord, balance_years, birth_dt = _balance_at_birth(chart)
    start_index = DASHA_SEQUENCE.index(start_lord)

    periods: List[DashaPeriod] = []
    cursor = birth_dt

    for i in range(num_mahadashas):
        lord = DASHA_SEQUENCE[(start_index + i) % 9]
        if i == 0:
            years = balance_years
        else:
            years = DASHA_YEARS[lord]
        end = cursor + timedelta(days=years * YEAR_DAYS)

        md = DashaPeriod(lord=lord, start=cursor, end=end, level="Mahadasha")
        md.sub_periods = _antardashas(md, include_pratyantar)
        periods.append(md)
        cursor = end

    return periods


def _antardashas(maha: DashaPeriod,
                 include_pratyantar: bool) -> List[DashaPeriod]:
    """
    Within a Mahadasha, the 9 antardashas (bhuktis) follow Vimshottari order
    starting from the Mahadasha lord.
    Antar duration = (Maha years × Antar lord years) / 120.
    """
    maha_years_full = DASHA_YEARS[maha.lord]
    actual_years = maha.duration_years   # may be partial for first MD
    scale = actual_years / maha_years_full

    start_idx = DASHA_SEQUENCE.index(maha.lord)
    periods: List[DashaPeriod] = []
    cursor = maha.start
    for i in range(9):
        ad_lord = DASHA_SEQUENCE[(start_idx + i) % 9]
        ad_years_full = (DASHA_YEARS[maha.lord] * DASHA_YEARS[ad_lord]) / 120
        ad_years = ad_years_full * scale
        ad_end = cursor + timedelta(days=ad_years * YEAR_DAYS)
        if ad_end > maha.end:
            ad_end = maha.end
        ad = DashaPeriod(lord=ad_lord, start=cursor, end=ad_end,
                         level="Antardasha")
        if include_pratyantar:
            ad.sub_periods = _pratyantars(ad)
        periods.append(ad)
        cursor = ad_end
        if cursor >= maha.end:
            break
    return periods


def _pratyantars(antar: DashaPeriod) -> List[DashaPeriod]:
    """Third-level dasha — Pratyantardasha within an Antardasha."""
    start_idx = DASHA_SEQUENCE.index(antar.lord)
    total_days = (antar.end - antar.start).days
    periods: List[DashaPeriod] = []
    cursor = antar.start
    for i in range(9):
        pa_lord = DASHA_SEQUENCE[(start_idx + i) % 9]
        share = DASHA_YEARS[pa_lord] / 120
        pa_days = total_days * share
        pa_end = cursor + timedelta(days=pa_days)
        if pa_end > antar.end:
            pa_end = antar.end
        periods.append(DashaPeriod(lord=pa_lord, start=cursor, end=pa_end,
                                   level="Pratyantardasha"))
        cursor = pa_end
        if cursor >= antar.end:
            break
    return periods


def find_current_dasha(periods: List[DashaPeriod],
                       at: Optional[datetime] = None
                       ) -> Optional[DashaPeriod]:
    """Find the Mahadasha active at the given datetime (default: now)."""
    if at is None:
        at = datetime.utcnow()
    for md in periods:
        if md.start <= at < md.end:
            return md
    return None


def find_current_antardasha(maha: DashaPeriod,
                            at: Optional[datetime] = None
                            ) -> Optional[DashaPeriod]:
    if at is None:
        at = datetime.utcnow()
    for ad in maha.sub_periods:
        if ad.start <= at < ad.end:
            return ad
    return None


def format_dasha_table(periods: List[DashaPeriod],
                       show_antar: bool = True) -> str:
    lines = ["=== Vimshottari Dasha ==="]
    for md in periods:
        lines.append(f"\n{md.lord:<9} Mahadasha   "
                     f"{md.start.date()} → {md.end.date()}   "
                     f"({md.duration_years:.2f} yrs)")
        if show_antar:
            for ad in md.sub_periods:
                lines.append(f"   ├─ {ad.lord:<8} Antar  "
                             f"{ad.start.date()} → {ad.end.date()}   "
                             f"({ad.duration_years*12:.1f} months)")
    return "\n".join(lines)
