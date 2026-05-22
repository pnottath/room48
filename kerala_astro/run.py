"""
Command-line runner for the Kerala Astrology Agent.

Usage:
    python -m kerala_astro.run                   # interactive mode
    python -m kerala_astro.run input.json        # batch mode
"""

import json
import sys
from pathlib import Path

from .core.chart import BirthData
from .agent.horoscope_agent import HoroscopeAgent


def from_json(path: str) -> BirthData:
    data = json.loads(Path(path).read_text())
    return BirthData(**data)


def interactive() -> BirthData:
    print("=== Kerala Astrology Agent — Birth data entry ===\n")
    name = input("Name                    : ").strip()
    date = input("Date of birth (YYYY-MM-DD): ").strip()
    time = input("Time of birth (HH:MM, 24h): ").strip()
    place = input("Place of birth (city)    : ").strip()
    lat = float(input("Latitude (decimal, N+)   : ").strip())
    lon = float(input("Longitude (decimal, E+)  : ").strip())
    tz  = input("Timezone (blank = auto)  : ").strip() or None

    y, m, d = map(int, date.split("-"))
    hh, mm = map(int, time.split(":"))
    return BirthData(
        name=name, year=y, month=m, day=d,
        hour=hh, minute=mm,
        latitude=lat, longitude=lon,
        timezone_name=tz, place_name=place,
    )


def main():
    if len(sys.argv) > 1:
        birth = from_json(sys.argv[1])
    else:
        birth = interactive()

    agent = HoroscopeAgent(include_pratyantar=False)
    result = agent.generate(birth)
    print(result["report_text"])


if __name__ == "__main__":
    main()
