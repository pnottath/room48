"""
Convert internal dataclasses (Chart, DashaPeriod, Yoga) into Pydantic
response models. Keeping this in one place means the agent never needs
to know about HTTP/JSON shapes.
"""

from typing import List
from datetime import datetime

from ..core.chart import Chart
from ..core.dasha import DashaPeriod
from ..core.yogas import Yoga
from ..core.interpret import interpret_mahadasha, interpret_antardasha
from ..core.constants import (
    NAKSHATRA_GANAM, NAKSHATRA_NADI, RASI_LORDS, BHAVA_MEANINGS, GRAHAS,
)
from .schemas import (
    PlanetResponse, ChartResponse, YogaResponse,
    DashaResponse, DashaInterpretationResponse,
)


def chart_to_response(chart: Chart, tz_name: str) -> ChartResponse:
    moon = chart.planets["Moon"]
    planets = [
        PlanetResponse(
            name=p.name,
            rasi=p.rasi_name,
            rasi_index=p.rasi_index,
            longitude=round(p.longitude, 4),
            degrees_in_rasi=round(p.degrees_in_rasi, 4),
            house=p.house,
            nakshatra=p.nakshatra,
            nakshatra_lord=p.nakshatra_lord,
            pada=p.pada,
            retrograde=p.retrograde,
            dignity=p.dignity,
        )
        for p in (chart.planets[n] for n in GRAHAS)
    ]

    houses = {}
    for h in range(1, 13):
        lord = RASI_LORDS[(chart.lagna_rasi_index + h - 1) % 12]
        houses[h] = {
            "lord": lord,
            "lord_house": chart.planets[lord].house,
            "occupants": chart.planet_in_house(h),
            "significations": BHAVA_MEANINGS[h],
        }

    b = chart.birth
    birth_dt = f"{b.year:04d}-{b.month:02d}-{b.day:02d}T{b.hour:02d}:{b.minute:02d}:{b.second:02d}"

    return ChartResponse(
        name=b.name,
        birth_datetime_local=birth_dt,
        place=b.place_name,
        latitude=b.latitude,
        longitude=b.longitude,
        timezone=tz_name,
        julian_day_ut=round(chart.jd_ut, 6),
        ayanamsa_lahiri=round(chart.ayanamsa, 4),
        lagna_rasi=chart.lagna_rasi_name,
        lagna_longitude=round(chart.lagna_longitude, 4),
        lagna_nakshatra=chart.lagna_nakshatra,
        lagna_pada=chart.lagna_pada,
        janma_rasi=moon.rasi_name,
        janma_nakshatra=moon.nakshatra,
        janma_pada=moon.pada,
        ganam=NAKSHATRA_GANAM[moon.nakshatra],
        nadi=NAKSHATRA_NADI[moon.nakshatra],
        nakshatra_lord=moon.nakshatra_lord,
        planets=planets,
        houses=houses,
    )


def yoga_to_response(y: Yoga) -> YogaResponse:
    return YogaResponse(
        name=y.name,
        sanskrit=y.sanskrit,
        category=y.category,
        strength=y.strength,
        basis=y.basis,
        result=y.result,
    )


def dasha_to_response(d: DashaPeriod) -> DashaResponse:
    return DashaResponse(
        lord=d.lord,
        level=d.level,
        start=d.start.date().isoformat(),
        end=d.end.date().isoformat(),
        duration_years=round(d.duration_years, 4),
        sub_periods=[dasha_to_response(sp) for sp in d.sub_periods],
    )


def md_to_interpretation(chart: Chart,
                         md: DashaPeriod) -> DashaInterpretationResponse:
    return DashaInterpretationResponse(
        lord=md.lord,
        start=md.start.date().isoformat(),
        end=md.end.date().isoformat(),
        duration_years=round(md.duration_years, 4),
        narrative=interpret_mahadasha(chart, md),
    )
