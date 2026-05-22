"""
Demo script — shows what the narrative output looks like with and without
a real LLM. Also showcases the cost telemetry (cache hits etc).

Run:
    python -m kerala_astro.narrative.demo
"""

import os
import json
from pathlib import Path

from ..core.chart import BirthData, compute_chart
from ..core.dasha import compute_vimshottari
from ..core.yogas import detect_all_yogas
from .engine import NarrativeEngine, NarrativeOptions
from .llm_provider import LLMProvider, LLMConfig, LLMResult


# ---------------------------------------------------------------------------
# Hand-crafted realistic sample output (used when no API key is available)
# ---------------------------------------------------------------------------

MOCK_OUTPUTS = {
    "overview": """\
Namaskaram, Sample Native. Your chart opens with **Mithunam lagnam** rising at 22.27°, falling in Punarvasu nakshatra, pada 1 — a lagna that confers a quick, communicative, adaptable temperament from its very first impression. The Janma rasi is **Kumbham**, and the Moon resides in **Shatabhisha nakshatram**, pada 3, under the lordship of Rahu. The ganam is Rakshasa, the nadi Aadi — a combination that gives independence of mind, an unconventional streak, and a willingness to walk one's own path rather than the worn one.

The lagna lord Budhan (Mercury) sits in the 12th bhava in Vrishabham — a placement that already tells us this is a chart oriented toward inner work, foreign lands, and the quieter expansions of life as much as the loud ones. We shall examine the bhavas and yogams below, then the running dasa, with care.""",

    "personality": """\
The lagnam being Mithunam, ruled by Budhan, gives a mind that is naturally curious, articulate, and inclined to gather information from many sources. With Surya and Guru both placed in the lagnam itself, the first house carries both vitality (from Surya) and dharmic seriousness (from Guru). This is no superficial mind — it tends to weigh, to consider, to seek wisdom beneath the chatter. Yet the lagna lord Budhan sits in the 12th — a quiet, reflective placement that gives a private interior life, a comfort with solitude, and often an attraction to subjects that lie behind the visible world: research, spirituality, foreign cultures, contemplative pursuits.

The Moon in Kumbham, under Shatabhisha nakshatram, deepens this signature. Shatabhisha is sometimes called "the veiling star" — Phaladeepika notes that those born under it possess an unusually penetrating but private mind, a capacity for healing or insight, and a tendency to keep their deepest convictions to themselves until trust is earned. The Rakshasa ganam adds force of will and a willingness to defend one's positions; the Aadi nadi indicates an active, somewhat restless vata constitution.

Surya in Mithunam in the lagnam itself gives a flexible identity — the native shapes themselves to circumstance without losing core integrity, much as Parasara describes for Surya placed in the first. Overall, this is a person of independent judgement, intellectually substantial, and more comfortable in the company of ideas than in crowds.""",

    "bhava": """\
**Tanu Bhavam (1st)** holds Surya and Brihaspati — a most auspicious combination for the personality. This gives dignity, broad vision, and a tendency toward leadership in modest, principled ways. **Dhana Bhavam (2nd)** is occupied by Ketu and ruled by the Moon placed in the 9th. Wealth comes with a spiritual or detached quality; speech tends toward the philosophical. There may be early questions about family resources, but the 9th-house lord support strengthens dhana over time.

**Sahaja (3rd)** is empty but ruled by Surya in lagnam — a placement that gives initiative and the courage to undertake one's own ventures. **Sukha Bhavam (4th)**, ruled by Budhan in the 12th, suggests that comforts and home are found in unconventional places — possibly abroad, or in quiet, private settings rather than ostentatious ones. The mother's themes may carry their own depths.

**Putra Bhavam (5th)** is unoccupied, ruled by Sukran in the 11th — a generally favourable signature for intelligence, creative children, and the bearing fruit of past punya. **Ari (6th)** is ruled by Kuja in the 10th — service, work, and overcoming opposition all align well with career; rivalries, if any, tend to be in the professional domain rather than personal.

**Kalatra Bhavam (7th)** ruled by Brihaspati in lagnam is a powerful placement for marriage. **Ayur Bhavam (8th)** holds Sani in its own sign Makaram, retrograde, alongside Rahu — a striking placement. Saturn in its own house in the 8th is steady and confers longevity, depth, and the capacity to engage transformative subjects (occult, research, inheritance) without being destabilised by them, though periods of intensity must be expected.

**Dharma Bhavam (9th)** holds the Moon — fortune through the mother's lineage, an instinctive moral compass, and a connection to teachers and gurus. **Karma Bhavam (10th)** holds Kuja in Meenam — a charged placement for career. **Labha Bhavam (11th)** holds Sukran — a fine signature for gains, networks, and the fulfilment of desires. **Vyaya Bhavam (12th)** holds Budhan, the lagna lord — expenditure on learning, travel, and inner pursuits is a recurring theme.""",

    "yogas": """\
Two yogams are clearly present in this jathakam.

**Durudhara Yogam** (दुरुधरा). With Kuja in the 2nd from Chandra and Sani in the 12th from Chandra, the Moon is "shouldered" on both sides by planets. Parasara assigns to this yogam comforts, generosity of spirit, fulfilment in family life, and a steady accumulation of resources.

**Kuja Dosham (Mangal Dosham)** (कुजदोष). Kuja is placed in the 2nd from Chandra Lagna and in the 12th from Sukra — a double affliction. This indicates potential for friction or delays in the marriage sphere; it must be approached with care, not alarm. Classical mitigations apply: matching with a partner who carries similar dosha; the dosha attenuates after age 28; and the strength of the 7th bhava (Brihaspati as 7th lord in lagnam) provides cushioning.

Kerala parihara measures include Kuja Shanti homam, Hanuman seva on Tuesdays, and daana in Kuja's significations. The native should approach a senior priest at a Subramanya temple for proper guidance.""",

    "current_dasha": """\
The native is presently in **Sani Mahadasa** (2011-07-17 to 2030-07-17, a 19-year period). The lord of this dasa, Sani, sits in his own sign Makaram in the 8th bhava, retrograde. This is a placement of considerable importance.

Sani in own sign confers durability and the capacity for deep, sustained work. The 8th bhava placement, while traditionally testing, becomes here a study in patient transformation: matters of longevity, inheritance, occult or research interests, depth psychology have been recurring themes through this dasa. The retrograde quality means the work tends to be inward-turning.

The current **antardasa is of Rahu** (Feb 2025 to Jan 2028). Rahu also sits in the 8th, conjoined with Sani. This period tends to bring unfamiliar circumstances, foreign or unconventional opportunities, and a sharpening of ambition. The advice: work steadily, avoid hasty commitments, and let Sani's discipline temper Rahu's appetite.""",

    "upcoming": """\
**Budha Mahadasa** (2030-07-17 to 2047-07-17, 17 years) follows. Budhan being the lagna lord, this is a dasa of the native's own significator — a period of personal expression and intellectual flowering. Budhan sits in the 12th, colouring the dasa with private, reflective, cross-border qualities.

**Ketu Mahadasa** (2047-07-17 to 2054-07-17, 7 years) brings a shorter, more inward turn. Ketu in the 2nd bhava in Karkatakam indicates detachment from purely material accumulation and a deepening of spiritual orientation.

**Sukra Mahadasa** (2054-07-17 to 2074-07-17, 20 years) opens the longer late chapter. Sukran in the 11th in Mesham is a fine placement for gains, relationships, and refined enjoyments.""",

    "closing": """\
The central karmic theme of this jathakam is the conversation between an intellectually rich lagnam (Surya and Guru in Mithunam) and a Moon placed deep in the 9th bhava in Shatabhisha. The Durudhara yogam supports steady accumulation; the Sani in own sign in the 8th asks for patience and depth. The chart leans toward inner work that bears outer fruit.

Jyothisham reveals tendencies and rhythms, never fates. Purushartha — conscious effort — and parihara have real effect. For matters of significance, the native should consult both a qualified astrologer and the appropriate domain professionals.""",
}


class DemoMockProvider(LLMProvider):
    """Returns hand-crafted prose. Matches the new LLMProvider interface."""

    @property
    def name(self) -> str:
        return "demo-mock"

    @staticmethod
    def _section_from_brief(brief: str) -> str | None:
        markers = {
            "overview":      "brief opening to the janma kundali",
            "personality":   "Vyakti Swabhavam",
            "bhava":         "Bhava Phalam",
            "yogas":         "Yoga Phalam",
            "current_dasha": "Current Dasa Phalam",
            "upcoming":      "Upcoming Dasa Phalam",
            "closing":       "closing paragraph",
        }
        for sec_id, marker in markers.items():
            if marker in brief:
                return sec_id
        return None

    def generate(self, system_blocks, user_prompt, config):
        sec = self._section_from_brief(user_prompt)
        text = MOCK_OUTPUTS.get(sec, "[mock — no matching section]")
        return LLMResult(text=text)

    async def generate_async(self, system_blocks, user_prompt, config):
        return self.generate(system_blocks, user_prompt, config)


def main():
    birth = BirthData(**json.loads(
        Path(__file__).parents[1].joinpath("sample_birth.json").read_text()
    ))
    chart = compute_chart(birth)
    dashas = compute_vimshottari(chart)
    yogas = detect_all_yogas(chart)

    if os.getenv("ANTHROPIC_API_KEY"):
        from .llm_provider import AnthropicProvider
        provider = AnthropicProvider()
        print("# Using real Anthropic API\n")
    else:
        provider = DemoMockProvider()
        print("# No ANTHROPIC_API_KEY in environment — using DemoMockProvider\n"
              "# Set ANTHROPIC_API_KEY to get genuine LLM output.\n")

    engine = NarrativeEngine(provider=provider)
    # Disable response cache for the demo so we always exercise the engine
    result = engine.generate(chart, yogas, dashas,
                             NarrativeOptions(language="english",
                                              use_response_cache=False))
    print(result.to_markdown())
    print("\n---\n# Token usage\n")
    print(result.usage.summary())


if __name__ == "__main__":
    main()
