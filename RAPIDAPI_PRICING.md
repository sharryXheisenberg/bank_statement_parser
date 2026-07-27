# RapidAPI Studio — Pricing Plan Config for "Bank Statement Parser"

Paste/adapt these directly when setting up the Monetize tab in RapidAPI Studio.
All plans include a mandatory "Requests" quota object (RapidAPI requirement).

---

## Plan 1: Basic (Free)
- **Price:** $0/month
- **Requests:** 25 requests/month (hard limit — no overage, requests just fail
  once the quota is hit, so nobody gets a surprise bill)
- **Rate limit:** 2 requests/second
- **Endpoints included:** `/parse-statement` (JSON) only — download endpoint excluded
- **Purpose:** Let a developer/accountant test the API end-to-end on one real
  statement before paying anything.

## Plan 2: Pro
- **Price:** $9.99/month
- **Requests:** 500 requests/month
- **Overage:** $0.03 per additional request
- **Rate limit:** 5 requests/second
- **Endpoints included:** both `/parse-statement` and `/parse-statement/download`
- **Purpose:** Individual accountants / freelancers processing a handful of
  client statements per month.

## Plan 3: Ultra
- **Price:** $29.99/month
- **Requests:** 3,000 requests/month
- **Overage:** $0.015 per additional request
- **Rate limit:** 10 requests/second
- **Endpoints included:** both endpoints
- **Purpose:** Small accounting firms / bookkeeping SaaS tools with steady
  monthly volume.

## Plan 4: Mega
- **Price:** $99.99/month
- **Requests:** 15,000 requests/month
- **Overage:** $0.008 per additional request
- **Rate limit:** 20 requests/second
- **Endpoints included:** both endpoints, priority support (email/SLA)
- **Purpose:** Fintech products or larger firms embedding this into their
  own pipeline.

---

## Listing copy (for the Hub description field)

**Short description:**
> Convert HDFC and SBI bank statement PDFs into clean, structured JSON or
> Excel in seconds. No OCR, no manual copy-paste — built for accountants,
> bookkeeping tools, and fintech apps that need reliable transaction data
> out of messy statement PDFs.

**Category:** Finance / Data Extraction / Business

**Tags:** bank statement, pdf parser, hdfc, sbi, fintech, accounting,
transaction extraction, excel export, ocr alternative

**Key selling points to put in the "Overview" tab:**
- No AI/LLM cost per request → fast and cheap, not billed per page like
  vision-model-based competitors
- Handles borderless statement layouts (most real bank PDFs have no table
  gridlines) via coordinate-based column detection
- Merges wrapped/multi-line narrations correctly instead of splitting them
  into broken rows
- Clean, documented error codes (422 unsupported bank, 400 wrong file type,
  413 file too large) instead of silent failures

---

## Notes on setup
- Set `RAPIDAPI_PROXY_SECRET` as an environment variable on your deployed
  server (Render/Railway) to the secret RapidAPI Studio generates for this
  API — this is what `main.py`'s middleware checks on every request.
- Add example request/response pairs in Studio using the sample PDFs in
  `sample_pdfs/` — reviewers and prospective subscribers test against these
  before subscribing.
- Start with just Free + Pro live; add Ultra/Mega once you see real usage,
  so you're not overwhelmed by support requests for a product with zero
  subscribers yet.
