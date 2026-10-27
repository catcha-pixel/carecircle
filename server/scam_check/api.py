"""CareCircle server: Scam Check, Pill Check, and the web app.

Run (from the server/scam_check folder):
    uvicorn api:app --reload --host 0.0.0.0

Then open http://127.0.0.1:8000 for the app, or http://127.0.0.1:8000/docs for the API.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # lets us import the meds package

from checker import ScamChecker  # noqa: E402
from meds.drug_names import DrugNames  # noqa: E402
from meds.interactions import InteractionChecker, LabelUnavailable  # noqa: E402
from meds.pill_search import PillIndex  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[2] / "app"

app = FastAPI(title="CareCircle", version="0.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

scam_checker = ScamChecker()
pill_index = PillIndex()
drug_names = DrugNames(extra_names=pill_index.names())
interaction_checker = InteractionChecker()

# For testing without internet: point this at a JSON file of {"medicine": "label text"}.
if os.environ.get("CARECIRCLE_FAKE_LABELS"):
    _fake = json.loads(Path(os.environ["CARECIRCLE_FAKE_LABELS"]).read_text(encoding="utf-8"))
    interaction_checker.fetch_label = lambda name: _fake.get(name)


# ---------- Scam Check ----------
class CheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="The message to check")
    lang: Literal["en", "es"] = "en"


@app.get("/health")
def health():
    return {"status": "ok", "pill_database": pill_index.available, "pills": len(pill_index.pills)}


@app.post("/check-message")
def check_message(req: CheckRequest):
    # The message is analyzed in memory only and never stored.
    return scam_checker.check(req.text, req.lang)


# ---------- Pill Check ----------
class PillSearchRequest(BaseModel):
    imprint: str = Field(..., min_length=1, max_length=60, description="Letters/numbers stamped on the pill")
    color: Optional[Literal["white", "yellow", "orange", "pink", "red", "blue", "green", "brown", "gray"]] = None
    shape: Optional[Literal["round", "oval", "capsule", "other"]] = None


@app.post("/pills/identify")
def identify_pill(req: PillSearchRequest):
    if not pill_index.available:
        return {"available": False, "candidates": []}
    return {
        "available": True,
        "source": pill_index.source,
        "candidates": pill_index.search(req.imprint, req.color, req.shape),
    }


class LabelTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)


@app.post("/meds/read-label")
def read_label(req: LabelTextRequest):
    return drug_names.find_in_text(req.text)


@app.get("/meds/suggest")
def suggest(q: str = Query(..., min_length=1, max_length=40)):
    return {"suggestions": drug_names.suggest(q)}


class InteractionRequest(BaseModel):
    medicines: List[str] = Field(..., min_length=2, max_length=20)


@app.post("/meds/interactions")
def check_interactions(req: InteractionRequest):
    meds = [drug_names.generic_for(m) for m in req.medicines]
    try:
        return interaction_checker.check(meds)
    except LabelUnavailable:
        raise HTTPException(status_code=503, detail="The FDA label service couldn't be reached. Please try again later.")


# Serve the web app last, so the API routes above take priority.
if APP_DIR.exists():
    app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="app")
