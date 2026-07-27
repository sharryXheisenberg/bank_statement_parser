"""
bank_identifier.py

Looks at the first 1-2 pages of a bank statement PDF and figures out which
bank issued it, so main.py can route the file to the correct parser.

Detection strategy: every Indian bank statement carries very distinctive
boilerplate on page 1 (bank name, IFSC prefix, statement title, etc). We
just search the raw text for a handful of fingerprints per bank. This is
far more reliable than trying to guess from layout/table shape.
"""

from __future__ import annotations
import re
import pdfplumber

# Each bank has a list of fingerprint patterns (case-insensitive).
# If ANY pattern matches the extracted text of the first two pages,
# we consider it a match. Add new banks here as you add new parsers.
BANK_FINGERPRINTS = {
    "HDFC": [
        r"HDFC BANK",
        r"HDFC0\d{6}",          # HDFC IFSC codes always start with HDFC0
    ],
    "SBI": [
        r"STATE BANK OF INDIA",
        r"\bSBIN0\d{6}\b",      # SBI IFSC codes always start with SBIN0
    ],
    "ICICI": [
        r"ICICI BANK",
        r"\bICIC0\d{6}\b",
    ],
    "AXIS": [
        r"AXIS BANK",
        r"\bUTIB0\d{6}\b",
    ],
}


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
    Returns one of: "HDFC", "SBI", "ICICI", "AXIS", or "UNKNOWN".

    Raises no exceptions on unrecognised banks -- callers should handle
    "UNKNOWN" by returning a clear 400 error to the API user rather than
    guessing at a parser.
    """
    text = _extract_probe_text(pdf_path)

    for bank_name, patterns in BANK_FINGERPRINTS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return bank_name

    return "UNKNOWN"
