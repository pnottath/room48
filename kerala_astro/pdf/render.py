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

def _markdown_to_html(md: str) -> str:
    """Convert the reading's markdown to safe HTML for the PDF body."""
    # 1. Escape everything first
    s = _html.escape(md)

    # 2. Headings (process h2 before h1 isn't needed since both anchor on ^)
    s = _H1_RE.sub(r"<h1>\1</h1>", s)
    s = _H2_RE.sub(r"<h2>\1</h2>", s)

    # 3. Bold / italic — order matters: bold first, then italic, so
    #    "**word**" doesn't get caught by the italic regex.
    s = _BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = _ITALIC_RE.sub(r"<em>\1</em>", s)

    # 4. Split on blank lines; wrap non-heading blocks in <p>
    out_blocks = []
    for block in re.split(r"\n{2,}", s):
        block = block.strip()
        if not block:
            continue
        if block.startswith("<h1>") or block.startswith("<h2>"):
            out_blocks.append(block)
        else:
            # Preserve single newlines as line breaks within a paragraph
            inner = block.replace("\n", "<br/>")
            out_blocks.append(f"<p>{inner}</p>")
    return "\n".join(out_blocks)


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
