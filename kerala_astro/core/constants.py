"""
Core constants for Kerala astrology calculations.
All Sanskrit/Malayalam terms preserved with English equivalents.
"""

import swisseph as swe

# === Rasis (Zodiac signs) — Kerala order starts from Mesham ===
RASIS = [
    "Mesham",      # Aries
    "Vrishabham",  # Taurus
    "Mithunam",    # Gemini
    "Karkatakam",  # Cancer
    "Simham",      # Leo
    "Kanni",       # Virgo
    "Thulam",      # Libra
    "Vrischikam",  # Scorpio
    "Dhanu",       # Sagittarius
    "Makaram",     # Capricorn
    "Kumbham",     # Aquarius
    "Meenam",      # Pisces
]

RASI_LORDS = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]

# === 27 Nakshatras with lords (Vimshottari sequence) ===
NAKSHATRAS = [
    ("Ashwini",       "Ketu"),
    ("Bharani",       "Venus"),
    ("Krittika",      "Sun"),
    ("Rohini",        "Moon"),
    ("Mrigashira",    "Mars"),
    ("Ardra",         "Rahu"),
    ("Punarvasu",     "Jupiter"),
    ("Pushya",        "Saturn"),
    ("Ashlesha",      "Mercury"),
    ("Magha",         "Ketu"),
    ("Purva Phalguni","Venus"),
    ("Uttara Phalguni","Sun"),
    ("Hasta",         "Moon"),
    ("Chitra",        "Mars"),
    ("Swati",         "Rahu"),
    ("Vishakha",      "Jupiter"),
    ("Anuradha",      "Saturn"),
    ("Jyeshtha",      "Mercury"),
    ("Moola",         "Ketu"),
    ("Purva Ashadha", "Venus"),
    ("Uttara Ashadha","Sun"),
    ("Shravana",      "Moon"),
    ("Dhanishta",     "Mars"),
    ("Shatabhisha",   "Rahu"),
    ("Purva Bhadrapada","Jupiter"),
    ("Uttara Bhadrapada","Saturn"),
    ("Revati",        "Mercury"),
]

# Ganam classification per nakshatra: Deva / Manushya / Rakshasa
NAKSHATRA_GANAM = {
    "Ashwini": "Deva", "Bharani": "Manushya", "Krittika": "Rakshasa",
    "Rohini": "Manushya", "Mrigashira": "Deva", "Ardra": "Manushya",
    "Punarvasu": "Deva", "Pushya": "Deva", "Ashlesha": "Rakshasa",
    "Magha": "Rakshasa", "Purva Phalguni": "Manushya", "Uttara Phalguni": "Manushya",
    "Hasta": "Deva", "Chitra": "Rakshasa", "Swati": "Deva",
    "Vishakha": "Rakshasa", "Anuradha": "Deva", "Jyeshtha": "Rakshasa",
    "Moola": "Rakshasa", "Purva Ashadha": "Manushya", "Uttara Ashadha": "Manushya",
    "Shravana": "Deva", "Dhanishta": "Rakshasa", "Shatabhisha": "Rakshasa",
    "Purva Bhadrapada": "Manushya", "Uttara Bhadrapada": "Manushya", "Revati": "Deva",
}

# Nadi classification: Aadi / Madhya / Antya — critical for porutham
NAKSHATRA_NADI = {
    "Ashwini": "Aadi", "Bharani": "Madhya", "Krittika": "Antya",
    "Rohini": "Antya", "Mrigashira": "Madhya", "Ardra": "Aadi",
    "Punarvasu": "Aadi", "Pushya": "Madhya", "Ashlesha": "Antya",
    "Magha": "Antya", "Purva Phalguni": "Madhya", "Uttara Phalguni": "Aadi",
    "Hasta": "Aadi", "Chitra": "Madhya", "Swati": "Antya",
    "Vishakha": "Antya", "Anuradha": "Madhya", "Jyeshtha": "Aadi",
    "Moola": "Aadi", "Purva Ashadha": "Madhya", "Uttara Ashadha": "Antya",
    "Shravana": "Antya", "Dhanishta": "Madhya", "Shatabhisha": "Aadi",
    "Purva Bhadrapada": "Aadi", "Uttara Bhadrapada": "Madhya", "Revati": "Antya",
}

# === Vimshottari Mahadasha years (total 120) ===
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}

DASHA_SEQUENCE = ["Ketu", "Venus", "Sun", "Moon", "Mars",
                  "Rahu", "Jupiter", "Saturn", "Mercury"]

# === Graha (planet) reference ===
GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
          "Venus", "Saturn", "Rahu", "Ketu"]

SWE_PLANET_IDS = {
    "Sun":     swe.SUN,
    "Moon":    swe.MOON,
    "Mars":    swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus":   swe.VENUS,
    "Saturn":  swe.SATURN,
    "Rahu":    swe.MEAN_NODE,   # Mean Rahu is Kerala convention
    # Ketu computed as Rahu + 180°
}

# === Exaltation / Debilitation degrees ===
# Format: (rasi_index, degree)
EXALTATION = {
    "Sun":     (0, 10),   # Mesham 10°
    "Moon":    (1, 3),    # Vrishabham 3°
    "Mars":    (9, 28),   # Makaram 28°
    "Mercury": (5, 15),   # Kanni 15°
    "Jupiter": (3, 5),    # Karkatakam 5°
    "Venus":   (11, 27),  # Meenam 27°
    "Saturn":  (6, 20),   # Thulam 20°
    "Rahu":    (1, 20),   # Vrishabham (debated; Kerala uses Vrishabham)
    "Ketu":    (7, 20),   # Vrischikam
}

DEBILITATION = {
    "Sun":     (6, 10),
    "Moon":    (7, 3),
    "Mars":    (3, 28),
    "Mercury": (11, 15),
    "Jupiter": (9, 5),
    "Venus":   (5, 27),
    "Saturn":  (0, 20),
    "Rahu":    (7, 20),
    "Ketu":    (1, 20),
}

# === Own signs (Swakshetra) ===
OWN_SIGNS = {
    "Sun":     [4],         # Simham
    "Moon":    [3],         # Karkatakam
    "Mars":    [0, 7],      # Mesham, Vrischikam
    "Mercury": [2, 5],      # Mithunam, Kanni
    "Jupiter": [8, 11],     # Dhanu, Meenam
    "Venus":   [1, 6],      # Vrishabham, Thulam
    "Saturn":  [9, 10],     # Makaram, Kumbham
}

# === Naisargika (natural) friendships ===
# F=Friend, N=Neutral, E=Enemy
NATURAL_RELATIONS = {
    "Sun":     {"Moon":"F","Mars":"F","Mercury":"N","Jupiter":"F","Venus":"E","Saturn":"E","Rahu":"E","Ketu":"E"},
    "Moon":    {"Sun":"F","Mars":"N","Mercury":"F","Jupiter":"N","Venus":"N","Saturn":"N","Rahu":"E","Ketu":"E"},
    "Mars":    {"Sun":"F","Moon":"F","Mercury":"E","Jupiter":"F","Venus":"N","Saturn":"N","Rahu":"N","Ketu":"F"},
    "Mercury": {"Sun":"F","Moon":"E","Mars":"N","Jupiter":"N","Venus":"F","Saturn":"N","Rahu":"F","Ketu":"N"},
    "Jupiter": {"Sun":"F","Moon":"F","Mars":"F","Mercury":"E","Venus":"E","Saturn":"N","Rahu":"N","Ketu":"N"},
    "Venus":   {"Sun":"E","Moon":"E","Mars":"N","Mercury":"F","Jupiter":"N","Saturn":"F","Rahu":"F","Ketu":"N"},
    "Saturn":  {"Sun":"E","Moon":"E","Mars":"E","Mercury":"F","Jupiter":"N","Venus":"F","Rahu":"F","Ketu":"N"},
}

# === Karaka assignments (significators) ===
NATURAL_KARAKAS = {
    "Sun":     ["Atma (soul)", "Father", "Authority", "Health"],
    "Moon":    ["Mind", "Mother", "Emotions", "Public"],
    "Mars":    ["Energy", "Siblings", "Courage", "Property"],
    "Mercury": ["Intellect", "Communication", "Trade", "Education"],
    "Jupiter": ["Wisdom", "Children", "Wealth", "Guru"],
    "Venus":   ["Spouse", "Comforts", "Arts", "Vehicles"],
    "Saturn":  ["Longevity", "Discipline", "Servants", "Sorrow"],
    "Rahu":    ["Foreign", "Innovation", "Obsession", "Maya"],
    "Ketu":    ["Moksha", "Detachment", "Past karma", "Spirituality"],
}

# === Bhava (house) significations — Kerala/Parashari ===
BHAVA_MEANINGS = {
    1:  "Tanu (body, self, personality, vitality, lagna)",
    2:  "Dhana (wealth, family, speech, food, early education)",
    3:  "Sahaja (siblings, courage, short travel, communication)",
    4:  "Sukha (mother, home, vehicles, comforts, land, education)",
    5:  "Putra (children, intelligence, mantras, purva-punya)",
    6:  "Ari/Shatru (enemies, debts, disease, service, litigation)",
    7:  "Kalatra (spouse, marriage, partnerships, business)",
    8:  "Ayur (longevity, occult, sudden events, inheritance, transformation)",
    9:  "Dharma (father, fortune, guru, higher learning, pilgrimage)",
    10: "Karma (career, status, authority, public life)",
    11: "Labha (gains, elder siblings, fulfilment of desires, networks)",
    12: "Vyaya (losses, foreign lands, moksha, expenditure, hidden enemies)",
}

DEGREES_PER_RASI = 30.0
DEGREES_PER_NAKSHATRA = 360.0 / 27   # 13°20'
DEGREES_PER_PADA = DEGREES_PER_NAKSHATRA / 4  # 3°20'
