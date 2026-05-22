"""
Room 48 — Offline launcher.

Single-command entry point for running Room 48 with NO internet dependency
once the initial setup is done.

Modes:
  --mode rules    Pure rule-based engine (chart + yogas + dashas + text
                  report). No LLM. Always available. Fastest.
  --mode ollama   Adds LLM-narrated prose using a local Ollama model.
                  Requires Ollama installed and `ollama serve` running.
  --mode auto     Picks ollama if available, otherwise rules. (default)

Usage:
    # One-time interactive (asks for birth details, prints reading to terminal)
    python -m kerala_astro.offline

    # Take a saved birth.json and write a Markdown file
    python -m kerala_astro.offline --input sample_birth.json --output reading.md

    # Force rules-only mode (no LLM call at all)
    python -m kerala_astro.offline --input sample_birth.json --mode rules

    # Use a different Ollama model
    python -m kerala_astro.offline --input sample_birth.json --mode ollama \\
        --model qwen2.5:14b
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .core.chart import BirthData, compute_chart
from .core.dasha import compute_vimshottari
from .core.yogas import detect_all_yogas
from .agent.horoscope_agent import HoroscopeAgent
from .narrative.engine import NarrativeEngine, NarrativeOptions
from .narrative.llm_provider import OllamaProvider, EchoProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def interactive_birth_data() -> BirthData:
    print("Room 48 — birth details\n")
    name = input("Name                       : ").strip() or "Anonymous"
    date = input("Date of birth (YYYY-MM-DD) : ").strip()
    time = input("Time of birth (HH:MM, 24h) : ").strip()
    place = input("Place of birth (any text)  : ").strip()
    lat  = float(input("Latitude  (e.g. 8.5241)   : ").strip())
    lon  = float(input("Longitude (e.g. 76.9366)  : ").strip())
    tz   = input("Timezone (blank = auto)    : ").strip() or None

    y, m, d = map(int, date.split("-"))
    hh, mm  = map(int, time.split(":"))
    return BirthData(
        name=name, year=y, month=m, day=d,
        hour=hh, minute=mm, latitude=lat, longitude=lon,
        timezone_name=tz, place_name=place,
    )


def pick_provider(mode: str, ollama_model: Optional[str]):
    """Return (provider, mode_actually_used) tuple."""
    if mode == "rules":
        return None, "rules"
    if mode == "ollama":
        op = OllamaProvider(model=ollama_model) if ollama_model else OllamaProvider()
        if not op.health_check():
            print(
                f"\n✗ Could not reach Ollama at {op.base_url}.\n"
                "  Make sure you've installed Ollama and that `ollama serve` is running.\n"
                "  See OFFLINE_SETUP.md for one-time setup steps.\n"
                "  Falling back to rules-only mode.\n",
                file=sys.stderr,
            )
            return None, "rules"
        return op, f"ollama ({op.model})"
    # auto
    op = OllamaProvider(model=ollama_model) if ollama_model else OllamaProvider()
    if op.health_check():
        return op, f"ollama ({op.model})"
    return None, "rules"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Room 48 — fully offline Kerala astrology reading.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--input", "-i", default=None,
                    help="Path to birth-data JSON file. If omitted, runs interactively.")
    ap.add_argument("--output", "-o", default=None,
                    help="Write the reading to this file. If omitted, prints to stdout.")
    ap.add_argument("--mode", choices=["auto", "rules", "ollama"], default="auto",
                    help="Engine mode (default: auto).")
    ap.add_argument("--model", default=None,
                    help="Ollama model name (default: llama3.1:8b).")
    ap.add_argument("--language", default="english",
                    choices=["english", "manglish", "malayalam"],
                    help="Language for the narrative (Ollama mode only).")
    ap.add_argument("--sections", default=None,
                    help="Comma-separated sections to render (Ollama mode only).")
    args = ap.parse_args()

    # 1. Get birth data
    if args.input:
        birth = BirthData(**json.loads(Path(args.input).read_text()))
    else:
        birth = interactive_birth_data()

    # 2. Compute chart + dashas + yogas (always runs)
    print(f"\nComputing chart for {birth.name}...", file=sys.stderr)
    chart = compute_chart(birth)
    dashas = compute_vimshottari(chart)
    yogas = detect_all_yogas(chart)

    # 3. Pick provider
    provider, mode_used = pick_provider(args.mode, args.model)
    print(f"Mode: {mode_used}", file=sys.stderr)

    # 4. Render output
    if provider is None:
        # Rules-only — use the deterministic text report
        agent = HoroscopeAgent()
        report = agent.generate(birth)["report_text"]
    else:
        # LLM-narrated reading
        sections = None
        if args.sections:
            sections = [s.strip() for s in args.sections.split(",")]
        engine = NarrativeEngine(provider=provider)
        opts = NarrativeOptions(
            language=args.language,
            sections=sections if sections else NarrativeOptions().sections,
        )
        print(f"Generating {len(opts.sections)} sections offline "
              f"(this can take 1-3 minutes on first run)...", file=sys.stderr)
        result = engine.generate(chart, yogas, dashas, opts)
        report = result.to_markdown()
        print(f"\n{result.usage.summary()}", file=sys.stderr)

    # 5. Output
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\n✓ Wrote {args.output}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
