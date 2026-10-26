"""CareCircle server: the Scam Check API, plus it serves the web app.

Run (from the server/scam_check folder):
    uvicorn api:app --reload --host 0.0.0.0

Then open http://127.0.0.1:8000 for the app, or http://127.0.0.1:8000/docs for the API.
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from checker import ScamChecker

APP_DIR = Path(__file__).resolve().parents[2] / "app"

app = FastAPI(title="CareCircle Scam Check", version="0.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
checker = ScamChecker()


class CheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="The message to check")
    lang: Literal["en", "es"] = "en"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check-message")
def check_message(req: CheckRequest):
    # The message is analyzed in memory only and never stored.
    return checker.check(req.text, req.lang)


# Serve the web app last, so the API routes above take priority.
if APP_DIR.exists():
    app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="app")
