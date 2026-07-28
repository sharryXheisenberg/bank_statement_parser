"""
base.py

The contract every bank parser must implement.

Why this exists (SOLID, concretely):

  Open/Closed Principle (OCP) -- the system should be OPEN to adding new
  banks, but CLOSED to modification of existing code. Before this refactor,
  adding a bank meant editing utils/bank_identifier.py (add a fingerprint)
  AND parsers/__init__.py (register the function) AND hoping the new
  parser's function signature matched what main.py expected by convention.
  Now: dropping a new file into parsers/ that defines a BankParser subclass
  is enough. Nothing else changes. See parsers/__init__.py's auto-discovery.

  Liskov Substitution Principle (LSP) -- main.py must be able to use ANY
  bank parser interchangeably without knowing which one it got. That only
  works if every subclass honours the same contract:
    - matches(text) -> bool, never raises
    - parse(pdf_path) -> pd.DataFrame with the CANONICAL_COLUMNS below,
      always in that order, always with those exact names/dtypes, even
      though each bank's raw PDF layout is completely different.
  If HDFCParser returned "Withdrawal (INR)" while SBIParser returned
  "Debit (INR)" for the same concept (the actual bug in the original
  version), callers would need bank-specific branches downstream -- which
  is exactly the kind of substitution violation LSP flags. Both parsers now
  normalize to the same canonical schema.

Every subclass must set:
  bank_name: str                       -- e.g. "HDFC"
And implement:
  matches(cls, first_page_text) -> bool
  parse(self, pdf_path) -> pd.DataFrame
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd

# Every parser MUST return a DataFrame with exactly these columns, in this
# order. This is the substitutability guarantee: main.py, the API response
# schema, and any future frontend can rely on this shape regardless of which
# bank was actually parsed.
CANONICAL_COLUMNS = [
    "Date",
    "Narration",
    "Reference No",
    "Value Date",
    "Debit (INR)",
    "Credit (INR)",
    "Balance (INR)",
]


class BankParser(ABC):
    """Abstract base every bank-specific parser subclasses."""

    bank_name: str = "UNSET"

    @classmethod
    @abstractmethod
    def matches(cls, first_page_text: str) -> bool:
        """
        Return True if `first_page_text` (raw text of the PDF's first 1-2
        pages) looks like a statement issued by this bank. Must be cheap
        (regex/substring checks only) and must never raise -- a parser that
        can't confidently say yes should just return False.
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, pdf_path: str) -> pd.DataFrame:
        """
        Parse the statement at `pdf_path` and return a DataFrame with
        exactly CANONICAL_COLUMNS, in that order. Return an empty DataFrame
        (same columns, zero rows) if nothing could be extracted -- never
        return None, and never raise for "just couldn't find transactions"
        (do raise for genuinely unreadable/corrupt files; main.py already
        catches and reports those as a clean 422).
        """
        raise NotImplementedError

    @classmethod
    def empty_result(cls) -> pd.DataFrame:
        """Convenience for parsers to return a schema-correct empty frame."""
        return pd.DataFrame(columns=CANONICAL_COLUMNS)
