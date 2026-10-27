"""Bottle-label reading and interaction checks.

FAKE_LABELS below are short TEST stand-ins written for these tests. The real app reads
official labels from openFDA.
"""

import pytest

from meds.drug_names import DrugNames
from meds.interactions import InteractionChecker, LabelUnavailable

FAKE_LABELS = {
    "lisinopril": (
        "Diuretics: Patients on diuretics may experience an excessive reduction of blood pressure. "
        "Potassium Supplements: Use of potassium-sparing diuretics, potassium supplements, or "
        "potassium-containing salt substitutes may lead to increases in serum potassium. "
        "Non-Steroidal Anti-Inflammatory Agents: NSAIDs may reduce the effect of ACE inhibitors."
    ),
    "ibuprofen": (
        "Ask a doctor or pharmacist before use if you are taking a diuretic, or a prescription "
        "drug for high blood pressure such as ACE inhibitors."
    ),
    "levothyroxine": "Calcium carbonate may reduce absorption.",
}


@pytest.fixture
def names():
    return DrugNames()


def test_reads_drug_and_strength_from_label(names):
    label = "CVS PHARMACY\nRx 1234567\nJANE DOE\nLISINOPRIL 10 MG TABLET\nTAKE ONE TABLET BY MOUTH DAILY\nQTY 30"
    result = names.find_in_text(label)
    assert result["medicines"][0]["name"] == "lisinopril"
    assert result["medicines"][0]["strength"] == "10 mg"
    assert result["directions"].startswith("Take one tablet by mouth daily")


def test_directions_that_wrap_onto_two_lines(names):
    result = names.find_in_text("LISINOPRIL 10 MG\nTAKE ONE TABLET BY MOUTH ONCE\nDAILY\nQTY: 30 REFILLS: 2")
    assert result["directions"] == "Take one tablet by mouth once daily"


def test_tolerates_photo_reading_mistakes(names):
    result = names.find_in_text("METF0RMIN HCL 500 MG")  # zero instead of O
    assert [m["name"] for m in result["medicines"]] == ["metformin"]
    assert result["medicines"][0]["exact"] is False


def test_two_word_names_and_brands(names):
    result = names.find_in_text("POTASSIUM CHLORIDE ER 20 MEQ\nEliquis 5 mg")
    found = {m["name"]: m["strength"] for m in result["medicines"]}
    assert found == {"potassium chloride": "20 meq", "apixaban": "5 mg"}


def test_ignores_ordinary_words(names):
    assert names.find_in_text("TAKE WITH FOOD. REFILLS: 2. DOCTOR SMITH")["medicines"] == []


def test_suggestions(names):
    suggestions = [s["name"] for s in names.suggest("lisin")]
    assert "lisinopril" in suggestions
    assert names.suggest("x") == []


def checker():
    return InteractionChecker(fetch_label=lambda name: FAKE_LABELS.get(name))


def test_finds_warning_by_drug_group():
    result = checker().check(["lisinopril", "ibuprofen"])
    assert len(result["warnings"]) == 1
    mentions = result["warnings"][0]["mentions"]
    assert {m["label_of"] for m in mentions} == {"lisinopril", "ibuprofen"}
    lis = next(m for m in mentions if m["label_of"] == "lisinopril")
    assert "NSAID" in lis["excerpt"]


def test_finds_potassium_supplement_warning():
    result = checker().check(["lisinopril", "potassium chloride"])
    excerpt = result["warnings"][0]["mentions"][0]["excerpt"]
    assert "potassium supplements" in excerpt.lower()


def test_no_warning_when_labels_dont_mention_each_other():
    result = checker().check(["lisinopril", "levothyroxine"])
    assert result["warnings"] == []


def test_reports_medicines_without_a_label():
    result = checker().check(["lisinopril", "madeupdrug"])
    assert result["no_label_found"] == ["madeupdrug"]


def test_service_down_is_raised():
    def down(name):
        raise LabelUnavailable("offline")
    with pytest.raises(LabelUnavailable):
        InteractionChecker(fetch_label=down).check(["a", "b"])


def test_labels_are_cached():
    calls = []
    def fetch(name):
        calls.append(name)
        return FAKE_LABELS.get(name)
    c = InteractionChecker(fetch_label=fetch)
    c.check(["lisinopril", "ibuprofen"])
    c.check(["lisinopril", "ibuprofen"])
    assert calls == ["lisinopril", "ibuprofen"]
