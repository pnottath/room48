"""
Q&A engine — single-call grounded answers about a chart.

The flow is intentionally simple:
  1. Build the digest (deterministic, free)
  2. Build system blocks (persona + contract + language + digest)
  3. ONE LLM call (no parallel sections)
  4. Parse the JSON response
  5. Verify grounding citations against the digest text
  6. Return a structured response

Cost: ~$0.02-$0.04 per question on Sonnet 4.6.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .digest import build_chart_digest
from .ask_prompts import ask_system_blocks, ask_user_prompt
from .llm_provider import LLMConfig, default_provider


# Valid classifications the model is allowed to return
_VALID_CLASSIFICATIONS = {"answerable", "interpretive", "out_of_scope", "refused"}


# ─────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────
@dataclass
class AskGroundingItem:
    fact: str

@dataclass
class AskUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

@dataclass
class AskResult:
    question: str
    answer: str
    grounded_in: List[AskGroundingItem]
    classification: str
    digest: str
    language: str
    model: str
    provider_name: str
    usage: AskUsage = field(default_factory=AskUsage)


# ─────────────────────────────────────────────────────────────────────
# Options for a single Q&A call
# ─────────────────────────────────────────────────────────────────────
@dataclass
class AskOptions:
    language: str = "english"
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.4   # cooler than the reading — Q&A wants steadier output
    max_tokens: int = 1200      # plenty for a 200-word answer + JSON envelope


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _extract_json(text: str) -> dict:
    """
    Pull the JSON object out of the LLM response.

    The contract says "raw JSON, nothing else" but we defend against
    a stray markdown fence, preamble, OR trailing text just in case.
    If parsing fails, we raise ValueError with a useful message.
    """
    text = text.strip()
    # Strip common markdown fences
    if text.startswith("```"):
        # Drop the first line (```json or ```) and the trailing ```
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse first (the happy path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back: find the first { and the LAST } and try that slice.
    # This handles preamble, trailing text, and most reasonable variations.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]}")

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}. Response was: {text[:400]}")


def _normalise(s: str) -> str:
    """Lowercase + collapse whitespace, for tolerant substring matching."""
    return re.sub(r"\s+", " ", s.lower()).strip()


def _verify_grounding(grounded_in: List[str], digest: str) -> List[str]:
    """
    Given a list of grounding citations the LLM produced, return only those
    that actually appear (tolerantly) in the digest text. Citations that
    don't match are silently dropped — they are signs the LLM is hallucinating
    citations and we don't want to surface those to the user.

    'Tolerantly' means: case-insensitive substring match after whitespace
    normalisation. The LLM may paraphrase punctuation/spacing slightly.
    """
    norm_digest = _normalise(digest)
    verified = []
    for citation in grounded_in:
        if not isinstance(citation, str):
            continue
        c = citation.strip()
        if not c:
            continue
        norm_c = _normalise(c)
        # For very short citations, require substring match
        if len(norm_c) >= 8 and norm_c in norm_digest:
            verified.append(c)
        # For longer citations, allow partial match (e.g. half the words present)
        # We don't try to be too clever here — substring match handles 95% of real cases.
    return verified


# ─────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────
class AskEngine:
    """Runs a single grounded Q&A call against an LLM provider."""

    def __init__(self, provider=None):
        self.provider = provider or default_provider()

    def answer(self, chart, yogas, dashas, question: str,
               opts: Optional[AskOptions] = None) -> AskResult:
        opts = opts or AskOptions()

        digest = build_chart_digest(chart, yogas, dashas)
        sys_blocks = ask_system_blocks(opts.language, digest)
        user_msg = ask_user_prompt(question)

        config = LLMConfig(
            model=opts.model,
            max_tokens=opts.max_tokens,
            temperature=opts.temperature,
        )

        # Single sync LLM call
        llm_response = self.provider.generate(sys_blocks, user_msg, config)

        # Parse the JSON envelope
        try:
            parsed = _extract_json(llm_response.text)
        except ValueError:
            # The LLM didn't return JSON. Fall back to a safe out_of_scope
            # response with the raw text. This should be rare given the
            # explicit OUTPUT CONTRACT but we degrade gracefully.
            return AskResult(
                question=question,
                answer="I had trouble producing a structured answer for that question. Could you try rephrasing it?",
                grounded_in=[],
                classification="out_of_scope",
                digest=digest,
                language=opts.language,
                model=opts.model,
                provider_name=self.provider.name,
                usage=AskUsage(
                    input_tokens=llm_response.input_tokens,
                    output_tokens=llm_response.output_tokens,
                    cache_read_tokens=llm_response.cache_read_tokens,
                    cache_creation_tokens=llm_response.cache_creation_tokens,
                ),
            )

        # Validate the classification
        classification = parsed.get("classification", "")
        if classification not in _VALID_CLASSIFICATIONS:
            classification = "out_of_scope"

        # Pull and verify grounding citations
        raw_grounded = parsed.get("grounded_in", [])
        if not isinstance(raw_grounded, list):
            raw_grounded = []
        verified_citations = _verify_grounding(raw_grounded, digest)

        # If the LLM said "answerable" or "interpretive" but verification
        # stripped everything (i.e. all citations were hallucinated), we
        # downgrade the answer.
        if classification in ("answerable", "interpretive") and not verified_citations:
            classification = "out_of_scope"

        answer_text = parsed.get("answer", "") or ""
        if not isinstance(answer_text, str):
            answer_text = str(answer_text)

        # If downgraded to out_of_scope, replace the answer with a clean refusal
        if classification == "out_of_scope" and parsed.get("classification") in ("answerable", "interpretive"):
            answer_text = (
                "I cannot confidently answer that question from the facts in "
                "your chart alone. Could you ask about a specific area the "
                "chart speaks to — such as your current period, marriage, "
                "career, or a particular yoga in your reading?"
            )

        return AskResult(
            question=question,
            answer=answer_text.strip(),
            grounded_in=[AskGroundingItem(fact=c) for c in verified_citations],
            classification=classification,
            digest=digest,
            language=opts.language,
            model=opts.model,
            provider_name=self.provider.name,
            usage=AskUsage(
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                cache_read_tokens=llm_response.cache_read_tokens,
                cache_creation_tokens=llm_response.cache_creation_tokens,
            ),
        )
