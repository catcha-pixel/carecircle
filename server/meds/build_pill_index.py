"""Turn the NLM Pillbox CSV into a small, fast pill lookup file for the app.

Usage (from the server folder):
    python3 -m meds.build_pill_index path/to/pillbox.csv

Writes data/pill_index.json.gz. Commit that file; the server loads it at startup.

Pillbox was retired by the National Library of Medicine in January 2021, so it does
not include pills released after that. The app tells people to confirm with a pharmacist.
"""

import csv
import gzip
import json
import re
import sys
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "pill_index.json.gz"

# FDA SPL codes, used if the CSV has codes but no color or shape words.
SPL_COLORS = {
    "C48323": "BLACK", "C48324": "GRAY", "C48325": "WHITE", "C48326": "RED", "C48327": "PURPLE",
    "C48328": "PINK", "C48329": "GREEN", "C48330": "YELLOW", "C48331": "ORANGE", "C48332": "BROWN",
    "C48333": "BLUE", "C48334": "TURQUOISE",
}
SPL_SHAPES = {
    "C48335": "BULLET", "C48336": "CAPSULE", "C48337": "CLOVER", "C48338": "DIAMOND",
    "C48339": "DOUBLE CIRCLE", "C48340": "FREEFORM", "C48341": "GEAR", "C48342": "HEPTAGON",
    "C48343": "HEXAGON", "C48344": "OCTAGON", "C48345": "OVAL", "C48346": "PENTAGON",
    "C48347": "RECTANGLE", "C48348": "ROUND", "C48349": "SEMI-CIRCLE", "C48350": "SQUARE",
    "C48351": "TEAR", "C48352": "TRAPEZOID", "C48353": "TRIANGLE",
}

# Column names have changed between Pillbox exports, so accept several spellings.
COLUMNS = {
    "imprint": ["splimprint", "spl_imprint", "imprint", "pillbox_imprint"],
    "color": ["splcolor_text", "spl_color_text", "color_text", "pillbox_color_text", "splcolor", "spl_color", "color"],
    "shape": ["splshape_text", "spl_shape_text", "shape_text", "pillbox_shape_text", "splshape", "spl_shape", "shape"],
    "name": ["medicine_name", "part_medicine_name", "rxstring", "title"],
    "strength": ["spl_strength", "strength"],
    "ingredients": ["spl_ingredients", "ingredients", "active_ingredients"],
    "maker": ["author", "labeler", "manufacturer"],
    "rxstring": ["rxstring"],
    "size": ["splsize", "spl_size", "size"],
}


def imprint_key(text):
    """'M;30' and 'M 30' both become 'M30'."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def imprint_tokens(text):
    return sorted(t for t in re.split(r"[^A-Z0-9]+", (text or "").upper()) if t)


def to_words(value, codes):
    """Turn 'C48325' or 'WHITE' or 'WHITE;BLUE' into ['WHITE', 'BLUE']."""
    out = []
    for part in re.split(r"[;,]", value or ""):
        part = part.strip().upper()
        if not part:
            continue
        out.append(codes.get(part, part))
    return out


def clean_strength(raw, name):
    """'TEMAZEPAM 15 mg;' -> '15 mg'.  Combination pills keep each part:
    'ACETAMINOPHEN 325 mg;HYDROCODONE BITARTRATE 5 mg;' -> 'Acetaminophen 325 mg, Hydrocodone Bitartrate 5 mg'."""
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    if len(parts) == 1:
        m = re.search(r"(\d[\d.,/]*\s*\S+)$", parts[0])  # the amount and unit at the end
        return m.group(1) if m else parts[0]
    return ", ".join(p.title().replace(" Mg", " mg").replace(" Mcg", " mcg").replace(" Ml", " mL") for p in parts)


def resolve_columns(header):
    lower = {h.lower().strip(): h for h in header}
    found = {}
    for key, options in COLUMNS.items():
        for option in options:
            if option in lower:
                found[key] = lower[option]
                break
    missing = [k for k in ("imprint", "name") if k not in found]
    if missing:
        raise SystemExit(
            f"Couldn't find the {', '.join(missing)} column(s) in this CSV.\n"
            f"Columns in the file: {', '.join(header)}"
        )
    return found


def build(csv_path):
    csv.field_size_limit(10_000_000)
    pills, seen = [], set()
    with open(csv_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        cols = resolve_columns(reader.fieldnames or [])
        get = lambda row, key: (row.get(cols[key]) or "").strip() if key in cols else ""
        # NLM added corrected values in "pillbox_*" columns; use them when they're filled in.
        lower = {h.lower(): h for h in reader.fieldnames}
        fix = lambda row, key, column: (row.get(lower.get(column, ""), "") or "").strip() or get(row, key)
        enabled_col = lower.get("enabled?")
        for row in reader:
            if enabled_col and row.get(enabled_col, "").strip().lower() == "false":
                continue  # NLM switched this record off
            imprint = fix(row, "imprint", "pillbox_imprint")
            key = imprint_key(imprint)
            if not key:
                continue  # can't identify a pill with no marking
            name = get(row, "name").strip()
            strength = clean_strength(get(row, "strength"), name)
            colors = to_words(fix(row, "color", "pillbox_color_text"), SPL_COLORS)
            shape = (to_words(fix(row, "shape", "pillbox_shape_text"), SPL_SHAPES) or [""])[0]
            dedupe = (key, name.upper(), strength.upper(), tuple(colors), shape)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            pills.append({
                "name": name.title() if name.isupper() or name.islower() else name,
                "strength": strength,
                "imprint": imprint.replace(";", " / "),
                "key": key,
                "tokens": imprint_tokens(imprint),
                "colors": colors,
                "shape": shape,
                "ingredients": get(row, "ingredients"),
                "maker": get(row, "maker"),
                "rx": get(row, "rxstring"),
                "size_mm": get(row, "size"),
            })
    return pills


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 -m meds.build_pill_index path/to/pillbox.csv")
    pills = build(sys.argv[1])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_PATH, "wt", encoding="utf-8") as f:
        json.dump({"source": "NLM Pillbox (retired Jan 2021)", "pills": pills}, f, separators=(",", ":"))
    print(f"Saved {len(pills):,} pills to {OUT_PATH} ({OUT_PATH.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
