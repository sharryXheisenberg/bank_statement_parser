"""
sbi_parser.py

SBI's statement layout, left to right:

    Txn Date | Value Date | Description | Ref No./Cheque No. | Debit | Credit | Balance

Same overall strategy as hdfc_parser.py (coordinate-based column bucketing,
with a regex fallback), just with SBI's own header labels and column order
-- SBI puts Value Date second instead of after the narration like HDFC does,
which is exactly the kind of per-bank layout difference that makes a single
universal parser fragile and a "router + per-bank parser" architecture the
right call.
"""

from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from parsers.common import (
    find_header_columns,
    extract_rows_by_columns,
    merge_continuation_rows,
    clean_amount,
    clean_date,
    DATE_RE,
)

HEADER_LABELS = [
    "Txn Date",
    "Value Date",
    "Description",
    "Ref No./Cheque No.",
    "Debit",
    "Credit",
    "Balance",
]

FALLBACK_LINE_RE = re.compile(
    r"^(?P<txn_date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+"
    r"(?P<value_date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<ref>\S+)\s+"
    r"(?:(?P<debit>[\d,]+\.\d{2}))?\s*"
    r"(?:(?P<credit>[\d,]+\.\d{2}))?\s+"
    r"(?P<balance>[\d,]+\.\d{2})$"
)


def _parse_via_columns(pdf_path: str) -> list[dict]:
    all_rows = []
    last_good_columns = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            columns = find_header_columns(page, HEADER_LABELS) or last_good_columns
            if columns is None:
                continue
            last_good_columns = columns

            raw_rows = extract_rows_by_columns(page, columns)
            raw_rows = [r for r in raw_rows if r.get("Txn Date", "").strip().upper() != "TXN DATE"]
            merged = merge_continuation_rows(raw_rows, date_column="Txn Date", narration_column="Description")
            all_rows.extend(merged)

    return all_rows


def _parse_via_regex_fallback(pdf_path: str) -> list[dict]:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                m = FALLBACK_LINE_RE.match(line.strip())
                if not m:
                    continue
                d = m.groupdict()
                rows.append({
                    "Txn Date": d["txn_date"],
                    "Value Date": d["value_date"],
                    "Description": d["description"],
                    "Ref No./Cheque No.": d["ref"],
                    "Debit": d["debit"] or "",
                    "Credit": d["credit"] or "",
                    "Balance": d["balance"],
                })
    return rows


def build_dataframe(pdf_path: str) -> pd.DataFrame:
    rows = _parse_via_columns(pdf_path)

    if len(rows) < 2:
        rows = _parse_via_regex_fallback(pdf_path)

    cleaned = []
    for r in rows:
        txn_date = clean_date(r.get("Txn Date", ""))
        if txn_date is None:
            continue

        cleaned.append({
            "Txn Date": txn_date,
            "Value Date": clean_date(r.get("Value Date", "")),
            "Description": re.sub(r"\s+", " ", r.get("Description", "")).strip(),
            "Reference No": r.get("Ref No./Cheque No.", "").strip(),
            "Debit (INR)": clean_amount(r.get("Debit", "")),
            "Credit (INR)": clean_amount(r.get("Credit", "")),
            "Balance (INR)": clean_amount(r.get("Balance", "")),
        })

    df = pd.DataFrame(cleaned, columns=[
        "Txn Date", "Value Date", "Description", "Reference No",
        "Debit (INR)", "Credit (INR)", "Balance (INR)",
    ])
    return df
