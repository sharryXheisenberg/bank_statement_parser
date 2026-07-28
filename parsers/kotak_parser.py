"""
kotak_parser.py

Added purely to PROVE the OCP claim: this file did not exist when
parsers/__init__.py, main.py, and utils/bank_identifier.py were written.
Dropping it in here is the ONLY change needed to support Kotak Mahindra
Bank statements -- nothing else in the codebase was touched.

Kotak's layout (as used in the test fixture): Date | Particulars | Chq No |
Debit | Credit | Balance -- no separate "Value Date" or reference number
column, so those canonical fields are left as None for this bank.
"""

from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from parsers.base import BankParser, CANONICAL_COLUMNS
from parsers.common import find_header_columns, extract_rows_by_columns, clean_amount, clean_date

FINGERPRINT_PATTERNS = [
    r"KOTAK MAHINDRA BANK",
    r"\bKKBK0\d{6}\b",
]

HEADER_LABELS = ["Date", "Particulars", "Chq No", "Debit", "Credit", "Balance"]


class KotakParser(BankParser):
    bank_name = "KOTAK"

    @classmethod
    def matches(cls, first_page_text: str) -> bool:
        return any(re.search(p, first_page_text, re.IGNORECASE) for p in FINGERPRINT_PATTERNS)

    def parse(self, pdf_path: str) -> pd.DataFrame:
        cleaned = []
        with pdfplumber.open(pdf_path) as pdf:
            last_good_columns = None
            for page in pdf.pages:
                columns = find_header_columns(page, HEADER_LABELS) or last_good_columns
                if columns is None:
                    continue
                last_good_columns = columns
                for row in extract_rows_by_columns(page, columns):
                    date = clean_date(row.get("Date", ""))
                    if date is None:
                        continue
                    cleaned.append({
                        "Date": date,
                        "Narration": re.sub(r"\s+", " ", row.get("Particulars", "")).strip(),
                        "Reference No": row.get("Chq No", "").strip() or None,
                        "Value Date": None,  # Kotak's statement format has no separate value date
                        "Debit (INR)": clean_amount(row.get("Debit", "")),
                        "Credit (INR)": clean_amount(row.get("Credit", "")),
                        "Balance (INR)": clean_amount(row.get("Balance", "")),
                    })

        if not cleaned:
            return self.empty_result()
        return pd.DataFrame(cleaned, columns=CANONICAL_COLUMNS)
