"""
Render a Room 48 reading (Markdown) as a print-quality PDF.

The PDF reuses an already-generated reading — there is no LLM call
inside this module. Input: the same markdown the frontend displays.
Output: bytes of a finished A4 PDF.

The renderer is deliberately small. Heavy lifting (layout, page breaks,
fonts, hyphenation, page numbers) is done by WeasyPrint via the CSS in
style.css.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Paths to the bundled template / fonts ────────────────────────────────
_HERE = Path(__file__).resolve().parent
_TEMPLATE_PATH = _HERE / "template.html"
_STYLE_PATH    = _HERE / "style.css"


@dataclass
class ReadingPdfInput:
    """All the data needed to render a reading as PDF."""
    native_name: str
    markdown: str
    disclaimer: str

    # Birth details for the cover page (already formatted strings —
    # the caller decides whether to show "Sun 15 Jun 1990" vs ISO
    # vs Malayalam, etc.)
    birth_date: str
    birth_time: str
    birth_tz: str
    birth_place: str

    # Optional: when this reading was generated. If None, we use 'now'.
    generated_on: Optional[str] = None


def render_reading_pdf(data: ReadingPdfInput) -> bytes:
    """
    Render a reading as a PDF and return the bytes.

    The heavy import (weasyprint) is deferred to first call so the rest
    of the API doesn't pay startup cost if PDFs are never requested.
    """
    # Local import — weasyprint pulls in cairo/pango at import time, and
    # we want a clean ImportError surface if a deployment is missing the
    # system libs rather than failing at FastAPI boot.
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    # 1. Markdown → HTML
    body_html = _markdown_to_html(data.markdown)

    # 2. Stitch the template (no Jinja dep needed — we keep this simple)
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    filled = (template
        .replace("{{ native_name }}",  _html.escape(data.native_name))
        .replace("{{ birth_date }}",   _html.escape(data.birth_date))
        .replace("{{ birth_time }}",   _html.escape(data.birth_time))
        .replace("{{ birth_tz }}",     _html.escape(data.birth_tz))
        .replace("{{ birth_place }}",  _html.escape(data.birth_place))
        .replace("{{ generated_on }}", _html.escape(
            data.generated_on or _today_human()))
        .replace("{{ disclaimer }}",   _html.escape(data.disclaimer))
        .replace("{{ body_html | safe }}", body_html)
    )

    # 3. Render via WeasyPrint
    # `base_url` is set to our package dir so relative paths in the
    # template (the stylesheet and the bundled fonts) resolve correctly.
    fc = FontConfiguration()
    pdf_bytes: bytes = HTML(
        string=filled,
        base_url=str(_HERE),
    ).write_pdf(
        stylesheets=[CSS(filename=str(_STYLE_PATH), font_config=fc)],
        font_config=fc,
    )
    return pdf_bytes


# ─── Markdown → HTML (small, focused subset) ──────────────────────────────
#
# The reading markdown produced by the engine uses just a few constructs:
#   #  Top-level title  →  <h1>
#   ## Section heading  →  <h2>
#   **bold**            →  <strong>
#   *italic*            →  <em>
#   paragraphs separated by blank lines
#
# We deliberately implement a tiny converter rather than pull in a full
# Markdown library. This keeps the dep footprint minimal AND lets us
# guarantee what HTML the PDF template will see. The text is escaped
# before we apply any conversion so injection isn't possible.

_BOLD_RE   = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")  # single * not part of **
_H1_RE     = re.compile(r"^# (.+)$", re.MULTILINE)
_H2_RE     = re.compile(r"^## (.+)$", re.MULTILINE)

def _section_class(heading: str) -> str:
    """Derive a CSS-safe class name from an H2 heading.
       'At a glance' → 'sec-at-a-glance'
       'Vyakti Swabhavam — Personality' → 'sec-vyakti-swabhavam'
       This lets CSS style specific sections differently (e.g. the
       summary section gets a softer "preamble" treatment).
    """
    base = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
    # Cap length to first 2-3 words for clarity
    parts = base.split("-")
    return "sec-" + "-".join(parts[:4]) if parts else "sec"

def _markdown_to_html(md: str) -> str:
    """Convert the reading's markdown to safe HTML for the PDF body.

       Each ## section becomes <section class="sec-{slug}"><h2>...</h2>...</section>
       so CSS can target individual sections without parsing HTML."""
    # 1. Escape everything first
    s = _html.escape(md)

    # 2. Bold / italic — order matters: bold first, then italic, so
    #    "**word**" doesn't get caught by the italic regex.
    s = _BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = _ITALIC_RE.sub(r"<em>\1</em>", s)

    # 3. Split on blank lines, then group blocks into sections based on H2 headings
    blocks = re.split(r"\n{2,}", s)
    out_html = []
    current_section: list[str] = []
    current_section_class: str = ""

    def flush_section():
        if current_section:
            opener = f'<section class="{current_section_class}">' if current_section_class else "<section>"
            out_html.append(opener + "\n" + "\n".join(current_section) + "\n</section>")

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m_h1 = _H1_RE.match(block)
        m_h2 = _H2_RE.match(block)
        if m_h1:
            # Close any open section, then emit standalone H1
            flush_section()
            current_section = []
            current_section_class = ""
            out_html.append(f"<h1>{m_h1.group(1)}</h1>")
        elif m_h2:
            # New section: flush the previous one, open a new container
            flush_section()
            heading_text = m_h2.group(1)
            current_section = [f"<h2>{heading_text}</h2>"]
            current_section_class = _section_class(heading_text)
        else:
            # Body paragraph (possibly multi-line within the same block)
            inner = block.replace("\n", "<br/>")
            current_section.append(f"<p>{inner}</p>")

    flush_section()
    return "\n".join(out_html)


def _today_human() -> str:
    """A human-friendly date string in the form '24 May 2026'."""
    return datetime.now().strftime("%-d %B %Y") if _supports_dash_d() else \
           datetime.now().strftime("%d %B %Y").lstrip("0")


def _supports_dash_d() -> bool:
    # `%-d` works on Linux/macOS, fails on Windows. Detect once.
    try:
        datetime.now().strftime("%-d")
        return True
    except ValueError:
        return False
