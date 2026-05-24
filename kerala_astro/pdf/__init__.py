"""
PDF rendering for Room 48 readings.

This sub-package converts an already-generated narrative reading (as
Markdown) into a print-quality PDF without making any further LLM call.

The on-screen reading and the PDF are produced from the same content;
the PDF is just a more presentable, shareable, archivable form.
"""

from .render import render_reading_pdf, ReadingPdfInput  # noqa: F401
