"""
Generate an LLM-narrated horoscope from the command line.

Usage:
    export ANTHROPIC_API_KEY=...
    python -m kerala_astro.narrative.run kerala_astro/sample_birth.json
    python -m kerala_astro.narrative.run kerala_astro/sample_birth.json --language manglish
    python -m kerala_astro.narrative.run kerala_astro/sample_birth.json --section yogas

Without an API key, an EchoProvider is used (no LLM call, useful for plumbing tests).
"""

import argparse
import json
import sys
from pathlib import Path

from ..core.chart import BirthData, compute_chart
from ..core.dasha import compute_vimshottari
from ..core.yogas import detect_all_yogas
from .engine import NarrativeEngine, NarrativeOptions
from .prompts import BRIEFS, section_ids


def main():
    ap = argparse.ArgumentParser(description="LLM-narrated horoscope generator")
    ap.add_argument("birth_json", help="Path to birth-data JSON file")
    ap.add_argument("--language", default="english",
                    choices=["english", "manglish", "malayalam"])
    ap.add_argument("--section", action="append",
                    help="Generate only this section (can be repeated). "
                         f"Choices: {section_ids()}")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--temperature", type=float, default=0.55)
    ap.add_argument("--output", "-o", default=None,
                    help="Write Markdown to this file instead of stdout.")
    ap.add_argument("--include-digest", action="store_true",
                    help="Append the raw chart digest as an appendix.")
    ap.add_argument("--no-cache", action="store_true",
                    help="Skip the response cache (always call the LLM).")
    args = ap.parse_args()

    birth = BirthData(**json.loads(Path(args.birth_json).read_text()))

    chart = compute_chart(birth)
    dashas = compute_vimshottari(chart)
    yogas = detect_all_yogas(chart)

    engine = NarrativeEngine()
    secs = args.section or section_ids()
    print(f"# Provider: {engine.provider.name}", file=sys.stderr)
    print(f"# Generating {len(secs)} sections in {args.language}...",
          file=sys.stderr)

    options = NarrativeOptions(
        language=args.language,
        sections=secs,
        model=args.model,
        temperature=args.temperature,
        use_response_cache=not args.no_cache,
    )

    result = engine.generate(chart, yogas, dashas, options)
    md = result.to_markdown(include_digest=args.include_digest)

    print(f"\n# --- Token usage ---", file=sys.stderr)
    print(result.usage.summary(), file=sys.stderr)

    if args.output:
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"# Wrote {args.output}", file=sys.stderr)
    else:
        print(md)


if __name__ == "__main__":
    main()
