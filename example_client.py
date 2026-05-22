"""
Example client showing how to call the Kerala Astrology API.

Usage:
    # Start the server first:
    #   uvicorn kerala_astro.api.main:app --port 8000
    # Then:
    python example_client.py
"""

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read())


def main():
    # 1. Sanity
    print("Health:", get_json("/health"))

    # 2. Resolve timezone (optional helper)
    tz = get_json("/api/v1/timezone?latitude=8.5241&longitude=76.9366")
    print(f"\nTimezone for Thiruvananthapuram: {tz['timezone']}")

    # 3. Build the birth payload
    birth = {
        "name": "Sample Native",
        "year": 1990, "month": 6, "day": 15,
        "hour": 7, "minute": 45,
        "latitude": 8.5241, "longitude": 76.9366,
        "timezone_name": tz["timezone"],
        "place_name": "Thiruvananthapuram, Kerala",
        "num_upcoming_dashas": 2,
    }

    # 4. Get the full horoscope
    horoscope = post_json("/api/v1/horoscope", birth)

    chart = horoscope["chart"]
    print(f"\n=== {chart['name']} ===")
    print(f"Lagna          : {chart['lagna_rasi']}  (Nakshatra {chart['lagna_nakshatra']} pada {chart['lagna_pada']})")
    print(f"Janma rasi     : {chart['janma_rasi']}")
    print(f"Janma nakshatra: {chart['janma_nakshatra']} (ganam {chart['ganam']}, nadi {chart['nadi']})")
    print(f"Ayanamsa       : {chart['ayanamsa_lahiri']}°")

    print("\nPlanets:")
    for p in chart["planets"]:
        retro = " R" if p["retrograde"] else ""
        dignity = f"  [{p['dignity']}]" if p["dignity"] else ""
        print(f"  {p['name']:<8} {p['rasi']:<13} {p['degrees_in_rasi']:>6.2f}°{retro}  "
              f"H{p['house']:<2}  {p['nakshatra']} (pada {p['pada']}){dignity}")

    print(f"\n{len(horoscope['yogas'])} yoga(s) detected:")
    for y in horoscope["yogas"]:
        print(f"  ● {y['name']} ({y['category']}) — {y['strength']}")
        print(f"    {y['result']}")

    if horoscope["current_mahadasha"]:
        md = horoscope["current_mahadasha"]
        print(f"\nCurrent Mahadasha: {md['lord']}  ({md['start']} → {md['end']})")
        print(f"  {md['narrative'][:300]}...")


if __name__ == "__main__":
    main()
