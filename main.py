"""
main.py

...

Run locally with EITHER:
    python main.py
    uvicorn main:app --reload --port 8000

Then test with:
    curl -F "file=@/path/to/statement.pdf" http://localhost:8000/parse-statement

Environment variables (see .env.example):
    RAPIDAPI_PROXY_SECRET  -- optional. Leave unset for local dev (the proxy
                              secret check is skipped). Set it to test the
                              production RapidAPI-gateway behavior locally.
    PORT                   -- optional. Defaults to 8000.
"""

from __future__ import annotations
import os
import tempfile
import uuid
import secrets

import math
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory into os.environ, if present

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from utils.bank_identifier import identify_bank
from parsers import PARSER_REGISTRY

app = FastAPI(
    title="Bank Statement Parser",
    description="Upload a bank statement PDF (HDFC, SBI, ...) and get back "
                "clean, structured transactions as JSON or Excel.",
    version="1.0.0",
)

MAX_FILE_SIZE_MB = 25

# --------------------------------------------------------------------------
# RapidAPI gateway verification
# --------------------------------------------------------------------------
# When this API is listed on RapidAPI, every request that goes through
# RapidAPI's marketplace gateway (i.e. one a paying subscriber made using
# their RapidAPI key) arrives at our server with an extra header:
#
#     X-RapidAPI-Proxy-Secret: <a secret only RapidAPI and we know>
#
# You generate this secret once in RapidAPI Studio and set it here as an
# environment variable. If someone calls our server directly (bypassing
# RapidAPI entirely -- e.g. scraping our URL from network traffic), that
# header will be missing or wrong, and we reject the request. This is what
# makes the "everyone must pay/subscribe through RapidAPI" model actually
# enforceable -- without it, anyone could skip the marketplace and hit our
# backend for free.
#
# Set RAPIDAPI_PROXY_SECRET in your deployment environment (Render/Railway
# env vars). If it's unset, we assume local/dev mode and skip the check --
# this keeps `uvicorn main:app --reload` working without any extra setup.
RAPIDAPI_PROXY_SECRET = os.environ.get("RAPIDAPI_PROXY_SECRET")


@app.middleware("http")
async def verify_rapidapi_proxy_secret(request: Request, call_next):
    # Always allow the health check through, even in production, so
    # uptime monitors / RapidAPI's own health probes don't need the secret.
    if RAPIDAPI_PROXY_SECRET and request.url.path != "/":
        incoming = request.headers.get("x-rapidapi-proxy-secret", "")
        if not secrets.compare_digest(incoming, RAPIDAPI_PROXY_SECRET):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid RapidAPI proxy secret. "
                                    "This API must be accessed through the "
                                    "RapidAPI marketplace."},
            )
    return await call_next(request)


def _save_upload_to_temp(file: UploadFile) -> str:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are supported.")

    suffix = ".pdf"
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="statement_")
    size = 0
    with os.fdopen(fd, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE_MB * 1024 * 1024:
                out.close()
                os.remove(path)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {MAX_FILE_SIZE_MB}MB limit.",
                )
            out.write(chunk)
    return path


def _parse(file: UploadFile):
    pdf_path = _save_upload_to_temp(file)
    try:
        try:
            bank = identify_bank(pdf_path)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Could not read this file as a PDF ({exc.__class__.__name__}). "
                       "It may be corrupted, password-protected, or not a real PDF.",
            )

        if bank == "UNKNOWN" or bank not in PARSER_REGISTRY:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not identify the issuing bank, or no parser exists "
                    f"for it yet. Detected: {bank}. Supported banks: "
                    f"{', '.join(PARSER_REGISTRY.keys())}."
                ),
            )
        build_dataframe = PARSER_REGISTRY[bank]
        try:
            df = build_dataframe(pdf_path)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Identified this as an {bank} statement but parsing failed "
                       f"({exc.__class__.__name__}: {exc}).",
            )
        if df.empty:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Identified this as an {bank} statement but could not "
                    "extract any transaction rows. The layout may differ "
                    "from what the parser expects (e.g. a scanned/image PDF)."
                ),
            )
        return bank, df
    finally:
        # temp PDF is no longer needed once we've extracted the data
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


@app.get("/")
def health_check():
    return {"status": "ok", "supported_banks": list(PARSER_REGISTRY.keys())}


def _json_safe(value):
    """NaN/NaT don't survive standard json.dumps -- convert to None."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


@app.post("/parse-statement")
async def parse_statement(file: UploadFile = File(...)):
    """Returns the parsed statement as JSON -- good for quick previews / UIs."""
    bank, df = _parse(file)
    records = [
        {col: _json_safe(val) for col, val in row.items()}
        for row in df.to_dict(orient="records")
    ]
    return JSONResponse(content={
        "bank": bank,
        "transaction_count": len(df),
        "transactions": records,
    })


@app.post("/parse-statement/download")
async def parse_statement_download(file: UploadFile = File(...)):
    """Returns the parsed statement as a downloadable .xlsx file."""
    bank, df = _parse(file)

    out_dir = tempfile.mkdtemp(prefix="parsed_")
    out_path = os.path.join(out_dir, f"{bank.lower()}_statement_{uuid.uuid4().hex[:8]}.xlsx")
    df.to_excel(out_path, index=False)

    return FileResponse(
        path=out_path,
        filename=os.path.basename(out_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    
if __name__ == "__main__":
    # Lets you run `python main.py` directly instead of typing out the full
    # uvicorn command. Reads PORT from .env / environment, defaults to 8000.
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
