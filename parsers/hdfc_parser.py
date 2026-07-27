"""
hdfc_parser.py

HDFC's statement layout (as of their standard net-banking PDF export) has
these columns, left to right:

    Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance

Quirks this parser handles:
  * Only ONE of Withdrawal/Deposit is filled per row -- the other is blank,
    not zero. We can't just split on whitespace and hope amount #1 is
    withdrawal, because a credit-only row has its single amount land in a
    different visual column. That's exactly why we use x-position bucketing
    from common.py instead of naive whitespace splitting.
  * Long narrations (e.g. UPI reference strings) wrap onto a second line
    with no date -- merged back in via merge_continuation_rows().
  * The header row only appears on page 1 in some exports and on every page
    in others -- we re-detect it per page and fall back to the last known
    good column set if a page doesn't repeat the header.
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
    "Date",
    "Narration",
    "Chq./Ref.No.",
    "Value Dt",
    "Withdrawal Amt.",
    "Deposit Amt.",
    "Closing Balance",
]

# Fallback regex for when a page has no visible header / column bucketing
# fails (e.g. an image-based export). Anchors on: date ... date ... amount
# [amount] amount, since one of the two middle amounts is usually absent.
FALLBACK_LINE_RE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"(?P<narration>.+?)\s+"
    r"(?P<ref>\S+)\s+"
    r"(?P<value_date>\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"(?P<amt1>[\d,]+\.\d{2})\s+"
    r"(?:(?P<amt2>[\d,]+\.\d{2})\s+)?"
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
            # drop the header row itself if it got captured as data
            raw_rows = [r for r in raw_rows if not DATE_RE.match(r.get("Date", "").strip())
                        or r.get("Date", "").strip().upper() != "DATE"]
            merged = merge_continuation_rows(raw_rows, date_column="Date", narration_column="Narration")
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
                # HDFC never has both withdrawal and deposit non-empty; when
                # amt2 is present, amt1=withdrawal, amt2=deposit. When amt2
                # is absent we can't be 100% sure which column amt1 belongs
                # to from regex alone, so we leave both and let the caller's
                # running-balance check in build_dataframe() disambiguate.
                rows.append({
                    "Date": d["date"],
                    "Narration": d["narration"],
                    "Chq./Ref.No.": d["ref"],
                    "Value Dt": d["value_date"],
                    "Withdrawal Amt.": d["amt1"] if d["amt2"] else "",
                    "Deposit Amt.": d["amt2"] if d["amt2"] else d["amt1"],
                    "Closing Balance": d["balance"],
                })
    return rows


def build_dataframe(pdf_path: str) -> pd.DataFrame:
    rows = _parse_via_columns(pdf_path)

    if len(rows) < 2:
        # column-bucketing didn't find anything usable -- fall back
        rows = _parse_via_regex_fallback(pdf_path)

    cleaned = []
    prev_balance = None
    for r in rows:
        date = clean_date(r.get("Date", ""))
        if date is None:
            continue

        withdrawal = clean_amount(r.get("Withdrawal Amt.", ""))
        deposit = clean_amount(r.get("Deposit Amt.", ""))
        balance = clean_amount(r.get("Closing Balance", ""))

        # Disambiguate withdrawal vs deposit using the running balance when
        # both ended up in the same cell (regex-fallback edge case above).
        if withdrawal is not None and deposit is not None and withdrawal == deposit:
            if prev_balance is not None and balance is not None:
                if round(prev_balance - withdrawal, 2) == round(balance, 2):
                    deposit = None
                elif round(prev_balance + deposit, 2) == round(balance, 2):
                    withdrawal = None

        cleaned.append({
            "Date": date,
            "Narration": re.sub(r"\s+", " ", r.get("Narration", "")).strip(),
            "Reference No": r.get("Chq./Ref.No.", "").strip(),
            "Value Date": clean_date(r.get("Value Dt", "")),
            "Withdrawal (INR)": withdrawal,
            "Deposit (INR)": deposit,
            "Closing Balance (INR)": balance,
        })
        if balance is not None:
            prev_balance = balance

    df = pd.DataFrame(cleaned, columns=[
        "Date", "Narration", "Reference No", "Value Date",
        "Withdrawal (INR)", "Deposit (INR)", "Closing Balance (INR)",
    ])
    return df
