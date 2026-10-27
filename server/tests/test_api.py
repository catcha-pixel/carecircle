"""End-to-end tests of the server's web API."""

import pytest
from fastapi.testclient import TestClient

import api
from meds.interactions import LabelUnavailable
from test_meds import FAKE_LABELS


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api.interaction_checker, "fetch_label", lambda name: FAKE_LABELS.get(name))
    api.interaction_checker.cache.clear()
    return TestClient(api.app)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


@pytest.mark.parametrize("text,verdict", [
    ("Grandpa it's me, I'm in jail and need $1500 for bail. Send gift cards and don't tell mom", "scam"),
    ("FasTrak: Unpaid toll of $5.40. Pay within 12 hours to avoid a $75 fine: fastrak-ca-pay.info", "scam"),
    ("Hi Grandma, I'll come by Sunday after church to fix your TV", "safe"),
])
def test_scam_check(client, text, verdict):
    body = client.post("/check-message", json={"text": text}).json()
    assert body["verdict"] == verdict
    assert body["confidence"] and isinstance(body["warning_signs"], int)


def test_scam_check_rejects_empty(client):
    assert client.post("/check-message", json={"text": ""}).status_code == 422


def test_read_label(client):
    body = client.post("/meds/read-label", json={"text": "LISINOPRIL 10 MG TAB\nTAKE 1 TABLET DAILY"}).json()
    assert body["medicines"][0]["name"] == "lisinopril"


def test_suggest(client):
    names = [s["name"] for s in client.get("/meds/suggest", params={"q": "metf"}).json()["suggestions"]]
    assert "metformin" in names


def test_interactions_use_generic_names(client):
    body = client.post("/meds/interactions", json={"medicines": ["Zestril", "Advil"]}).json()
    assert body["checked"] == ["lisinopril", "ibuprofen"]
    assert len(body["warnings"]) == 1


def test_interactions_need_two_medicines(client):
    assert client.post("/meds/interactions", json={"medicines": ["lisinopril"]}).status_code == 422


def test_interactions_service_down(client, monkeypatch):
    def down(name):
        raise LabelUnavailable("offline")
    monkeypatch.setattr(api.interaction_checker, "fetch_label", down)
    assert client.post("/meds/interactions", json={"medicines": ["x", "y"]}).status_code == 503


def test_pill_identify_validates_color(client):
    assert client.post("/pills/identify", json={"imprint": "M 30", "color": "plaid"}).status_code == 422


def test_pill_identify_responds(client):
    body = client.post("/pills/identify", json={"imprint": "M 30"}).json()
    assert "available" in body and isinstance(body["candidates"], list)
