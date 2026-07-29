# Bank Statement Parser

Turns messy, human-formatted bank statement PDFs (HDFC, SBI, ...) into clean,
structured data — JSON or Excel — in seconds instead of hours of manual
copy-paste.

## Why this is hard

Banks don't export statements as clean tables. The PDFs are built for human
eyes: logos, account summaries, varying column widths, and (critically) most
of them have **no real gridlines** — the "table" is just text positioned at
fixed x/y coordinates by a report engine. Naive `pdftotext`-style extraction
collapses all of that into a single wall of text and destroys the column
structure.

## How it works

1. **Router** (`utils/bank_identifier.py`) — reads the first couple of pages
   and asks every registered parser "is this yours?" via each parser's own
   `matches()` classmethod (bank name, IFSC prefix like `HDFC0` / `SBIN0`).
2. **Per-bank parser** (`parsers/hdfc_parser.py`, `parsers/sbi_parser.py`, ...)
   — each subclasses `parsers.base.BankParser`. Each bank's layout is
   different (HDFC puts Value Date after Narration; SBI puts it right after
   Txn Date), so each gets its own parser rather than forcing one universal
   regex to handle every bank. Every parser returns the same **canonical
   column schema** regardless of the bank's original column names — see
   "Architecture" below.
3. **Coordinate-based column extraction** (`parsers/common.py`) — this is the
   core trick. `pdfplumber` exposes the exact (x0, top, x1, bottom) bounding
   box of every word on the page. We:
   - find the header row and use each header label's x-position to define
     column boundaries
   - bucket every other word on the page into the column its x0 falls into
   - group buckets by vertical position to reconstruct rows
   - fold narration-continuation lines (long UPI strings that wrap onto a
     second line with no date) back into the previous transaction
   This works even with zero visible table lines, which is the normal case.
4. **Regex fallback** — if column-bucketing comes up short (e.g. an unusual
   layout), each parser falls back to an anchored regex over the raw text.
5. **Cleanup** — dates normalized to ISO, Indian lakh-style comma amounts
   (`1,23,456.78`) converted to floats, running-balance cross-checks used to
   disambiguate debit vs. credit when a line is ambiguous.

## Architecture: OCP + LSP by construction

- **`parsers/base.py`** defines `BankParser`, an abstract base every parser
  subclasses, and `CANONICAL_COLUMNS` — the exact schema every parser's
  `.parse()` must return (`Date`, `Narration`, `Reference No`, `Value Date`,
  `Debit (INR)`, `Credit (INR)`, `Balance (INR)`), in that order, regardless
  of what the source bank calls its columns.
  - **Liskov Substitution Principle**: `main.py` never knows or cares which
    bank's parser it's holding — every subclass is a drop-in substitute for
    another because they all honor the same input/output contract. (Before
    this refactor, HDFC returned `"Withdrawal (INR)"`/`"Deposit (INR)"`
    while SBI returned `"Debit (INR)"`/`"Credit (INR)"` for the same
    concept — a real substitution violation that would have forced
    bank-specific branches in any downstream consumer.)
- **`parsers/__init__.py`** auto-discovers every `BankParser` subclass in
  the package at import time (via `pkgutil`/`inspect`) and builds
  `PARSER_REGISTRY` automatically.
  - **Open/Closed Principle**: adding a new bank means writing **one new
    file** — nothing existing gets modified. Drop `parsers/kotak_parser.py`
    into the folder, and it's registered, matchable, and callable with zero
    edits to `main.py`, `utils/bank_identifier.py`, or `parsers/__init__.py`.
    (This was proven by literally doing it — `parsers/kotak_parser.py` in
    this repo was added after everything else was written and required no
    other file to change.)

## Project layout

```text
bank_statement_parser/
├── requirements.txt
├── main.py # FastAPI app: upload -> JSON or .xlsx
├── .env.example # copy to .env; see Setup below
├── utils/
│   └── bank_identifier.py # asks each registered parser "is this yours?"
├── parsers/
│   ├── __init__.py # auto-discovers BankParser subclasses
│   ├── base.py # BankParser ABC + CANONICAL_COLUMNS contract
│   ├── common.py # shared coordinate-extraction engine
│   ├── hdfc_parser.py
│   ├── sbi_parser.py
│   └── kotak_parser.py # added after everything else -- proves OCP
└── sample_pdfs/ # synthetic test fixtures + generator scripts
    ├── make_test_hdfc.py
    ├── make_test_sbi.py
    ├── hdfc_sample.pdf
    ├── hdfc_multipage.pdf # tests wrapped narration + repeated headers
    └── sbi_sample.pdf
    └── kotak_sample.pdf

``` 

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # leave RAPIDAPI_PROXY_SECRET blank for local dev
```

## Run

```bash
python main.py
# or: uvicorn main:app --reload --port 8000
```

## Use

```bash
# JSON preview
curl -F "file=@/path/to/statement.pdf" http://localhost:8000/parse-statement

# Downloadable Excel file
curl -F "file=@/path/to/statement.pdf" http://localhost:8000/parse-statement/download -o result.xlsx
```

Interactive API docs (Swagger UI) are auto-generated by FastAPI at
`http://localhost:8000/docs`.

## Adding a new bank

1. Write `parsers/<bank>_parser.py` with a class that subclasses
   `parsers.base.BankParser`:
   - set `bank_name = "YOURBANK"`
   - implement `matches(cls, first_page_text) -> bool` (fingerprint check —
     bank name, IFSC prefix, etc.)
   - implement `parse(self, pdf_path) -> pd.DataFrame` returning exactly
     `CANONICAL_COLUMNS` (reuse `common.py`'s column-extraction helpers,
     add a regex fallback, following `hdfc_parser.py`/`sbi_parser.py` as a
     template)
2. That's it. Nothing else changes — `parsers/__init__.py` finds it
   automatically at import time, `utils/bank_identifier.py` will start
   recognizing it, and `main.py` will route to it. See `kotak_parser.py`
   for a real example of exactly this — it was added after the rest of the
   codebase was finished and required zero edits anywhere else.

## Testing notes

`sample_pdfs/` contains synthetic statements (generated with `reportlab`, no
real customer data) used to validate the parser end-to-end, including:
- normal single-page statements for all three banks
- a multi-page HDFC statement with a repeated header row and a wrapped
  narration line, to exercise page-boundary and continuation-row handling

Regenerate them anytime with:
```bash
python3 sample_pdfs/make_test_hdfc.py
python3 sample_pdfs/make_test_sbi.py
python3 sample_pdfs/make_test_kotak.py
```

## Known limitations / next steps

- HDFC, SBI, and Kotak are implemented; other banks simply need one new
  parser file (see "Adding a new bank" above) — until then, unrecognized
  banks get a clean 422.
- Scanned/image-based PDFs (no extractable text layer) aren't handled —
  would need an OCR pre-pass (e.g. `pytesseract`) before this pipeline.
- Password-protected PDFs return a clean 422 rather than prompting for a
  password; add password support to `pdfplumber.open(..., password=...)`
  if needed.

## Production-readiness checklist (not yet implemented)

The refactor above addresses architecture (OCP/LSP). These are the other
gaps between "works" and "production-ready" — prioritized roughly by
impact vs. effort:

1. **Structured logging** — replace nothing-currently-logged with proper
   request-scoped logging (bank identified, parse duration, row count,
   failures) so you can debug a subscriber's "it didn't work" report
   without asking them to resend the PDF.
2. **Rate limiting at the app level** — `slowapi` (or similar) as a second
   layer behind RapidAPI's own gateway limits, so a bug in RapidAPI's
   enforcement (or a leaked key) can't let one caller hammer your server.
3. **Containerization** — a `Dockerfile` so deployment to Render/Railway/Fly
   is reproducible instead of depending on whatever Python version happens
   to be on the host.
4. **Automated tests** — the `sample_pdfs/` fixtures exist and were used for
   manual verification throughout this build, but there's no `pytest` suite
   wired up yet. Worth adding `tests/test_parsers.py` asserting exact
   expected DataFrames against each fixture, so future changes to
   `common.py` can't silently break a bank that was already working.
5. **Config via `pydantic-settings`** instead of raw `os.environ.get()`
   calls scattered through `main.py` — validates required env vars at
   startup instead of failing confusingly on first request.
6. **Monitoring/alerting** — Sentry (or similar) for exceptions in
   production; right now a parsing failure is only visible if you happen
   to be tailing logs when it happens.
7. **CORS configuration** — currently unset; if you ever want a browser-
   based frontend to call this directly (rather than only server-to-server
   or RapidAPI traffic), you'll need `CORSMiddleware` configured explicitly.
8. **Large-file handling** — very large multi-page statements (100+ pages)
   parse synchronously today; a background job queue (e.g. Celery/RQ) would
   avoid tying up a worker on a single big request for tens of seconds.