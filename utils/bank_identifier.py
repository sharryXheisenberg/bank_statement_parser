"""
bank_identifier.py

Looks at the first 1-2 pages of a bank statement PDF and figures out which
bank issued it, so main.py can route the file to the correct parser.

This used to own its own hardcoded fingerprint dict (HDFC -> ["HDFC BANK",
"HDFC0..."], SBI -> [...], etc), separate from the parsers themselves. That
was a real OCP violation: adding a bank meant editing a fingerprint list
here AND writing the parser AND registering it in parsers/__init__.py --
three edits for one new bank, two of which touched shared files.

Now each parser owns its own detection logic via a `matches()` classmethod
(see parsers/base.py), and this module just asks every registered parser
"is this yours?" via parsers.identify_and_get_parser(). Adding a bank is a
single new file; this module never changes again.
"""

from __future__ import annotations
import pdfplumber

from parsers import identify_and_get_parser


def _extract_probe_text(pdf_path: str, max_pages: int = 2) -> str:
    """Pulls raw text from the first `max_pages` pages for fingerprinting."""
    text_chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def identify_bank(pdf_path: str) -> str:
    """
    Returns the matching bank_name (e.g. "HDFC", "SBI") or "UNKNOWN" if no
    registered parser recognizes this statement. Raises no exceptions on
    unrecognized banks -- callers should handle "UNKNOWN" by returning a
    clear 4xx error rather than guessing at a parser.
    """
    text = _extract_probe_text(pdf_path)
    bank_name, _ = identify_and_get_parser(text)
    return bank_name or "UNKNOWN"
