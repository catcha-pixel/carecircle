"""Pill lookup tests. The sample CSVs are made-up TEST data, not real medicines."""

import gzip
import json

import pytest

from conftest import FIXTURES
from meds.build_pill_index import build, imprint_key
from meds.pill_search import PillIndex


@pytest.fixture
def index(tmp_path):
    pills = build(FIXTURES / "pillbox_sample.csv")
    path = tmp_path / "pill_index.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump({"source": "test", "pills": pills}, f)
    return PillIndex(path)


def test_imprint_key_ignores_spaces_and_separators():
    assert imprint_key("AB;12") == imprint_key("ab 12") == "AB12"


def test_build_skips_blank_imprints_and_duplicates():
    pills = build(FIXTURES / "pillbox_sample.csv")
    names = [p["name"] for p in pills]
    assert "TEST-ONLY SAMPLE ROWS" not in names and "Test-Only Sample Rows" not in names
    assert names.count("Betatestine") == 1


def test_build_understands_color_and_shape_codes():
    pills = build(FIXTURES / "pillbox_codes_sample.csv")
    qq = next(p for p in pills if p["key"] == "QQ7")
    assert qq["colors"] == ["WHITE"] and qq["shape"] == "ROUND"
    assert qq["name"] == "Codetestol 7 MG Oral Tablet"  # falls back to RXSTRING for the name


def test_exact_imprint_match(index):
    results = index.search("AB 12")
    assert {r["name"] for r in results[:2]} == {"Alphatestol", "Deltatest"}


def test_color_picks_the_right_pill(index):
    assert index.search("AB 12", color="white")[0]["name"] == "Alphatestol"
    assert index.search("AB 12", color="pink")[0]["name"] == "Deltatest"
    assert index.search("AB 12", color="white", shape="round")[0]["match"] == "strong"


def test_sides_in_other_order(index):
    assert index.search("500 ZX")[0]["name"] == "Betatestine"


def test_misread_imprint_still_finds_close_match(index):
    results = index.search("ZX5OO")  # letter O instead of zero
    assert results and results[0]["name"] == "Betatestine"
    assert results[0]["match"] != "strong"


def test_two_colored_capsule(index):
    assert index.search("G5", color="blue", shape="capsule")[0]["name"] == "Gammatest"


def test_no_match_and_empty_input(index):
    assert index.search("QWERTY99") == []
    assert index.search("   ") == []


def test_missing_database_is_reported(tmp_path):
    assert PillIndex(tmp_path / "missing.json.gz").available is False
