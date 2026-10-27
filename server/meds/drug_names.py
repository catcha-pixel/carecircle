"""Spot medicine names (and strengths and directions) in text read from a pill bottle label."""

import csv
import re
from difflib import get_close_matches
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

# "10 MG", "10MG", and combination strengths like "10-325 MG" or "10/325 MG"
STRENGTH_RE = re.compile(r"(\d+(?:\.\d+)?(?:\s*[-/]\s*\d+(?:\.\d+)?)?)\s*(MG|MCG|MEQ|G|ML|UNITS?|IU|%)\b", re.IGNORECASE)
OCR_DIGIT_FIXES = str.maketrans({"0": "o", "1": "l", "5": "s", "8": "b"})
# Directions start with a word like TAKE and often wrap onto a short second line ("DAILY").
DIRECTIONS_RE = re.compile(
    r"\b(TAKE|USE|APPLY|INHALE|INJECT|DISSOLVE|CHEW|PLACE)\b[^\n]{4,120}"
    r"(?:\n(?![^\n]*(?:QTY|REFILL|RX|DR\b|DATE|:|\d))[A-Za-z ,.]{2,40}(?=\n|$))?",
    re.IGNORECASE,
)


def _clean(name):
    return re.sub(r"\s+", " ", name.strip().lower())


class DrugNames:
    def __init__(self, extra_names=()):
        """extra_names: names from the pill database, as a list or as {name: base name}."""
        self.generics = set()
        self.base = {}  # salt form -> base medicine, like "amlodipine besylate" -> "amlodipine"
        for line in (DATA / "common_drugs.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self.generics.add(_clean(line))

        self.brands = {}
        with open(DATA / "brand_names.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.brands[_clean(row["brand"])] = _clean(row["generic"])

        # Simple one- or two-word names from the pill database (skip long product titles).
        pairs = extra_names.items() if isinstance(extra_names, dict) else ((n, n) for n in extra_names)
        for name, base in pairs:
            n, b = _clean(name), _clean(base)
            if 4 <= len(n) <= 30 and len(n.split()) <= 2 and n.replace(" ", "").isalpha():
                self.generics.add(n)
                if b != n and b.replace(" ", "").isalpha():
                    self.base[n] = b

        self.all_names = self.generics | set(self.brands)
        self.one_word = {n for n in self.all_names if " " not in n}
        self.two_word = {n for n in self.all_names if len(n.split()) == 2}

    def generic_for(self, name):
        n = _clean(name)
        n = self.brands.get(n, n)
        return self.base.get(n, n)

    def suggest(self, query, limit=8):
        """Names that start with what the person has typed so far."""
        q = _clean(query)
        if len(q) < 2:
            return []
        starts = sorted(n for n in self.all_names if n.startswith(q))
        if len(starts) < limit:
            starts += [n for n in get_close_matches(q, self.all_names, n=limit, cutoff=0.75) if n not in starts]
        return [{"name": n, "generic": self.generic_for(n)} for n in starts[:limit]]

    def find_in_text(self, text):
        """Return medicines found in label text, with strength if it's printed nearby."""
        # Words may contain digits the photo reader confused with letters (METF0RMIN),
        # so swap those back. Pure numbers (like "500") are skipped.
        words = []
        for m in re.finditer(r"[A-Za-z0-9]+", text):
            token = m.group(0)
            if sum(c.isalpha() for c in token) < 3:
                continue
            fixed = token.lower().translate(OCR_DIGIT_FIXES)
            words.append((fixed, m.start(), m.end(), fixed == token.lower()))
        found = {}

        def add(name, start, end, exact):
            generic = self.generic_for(name)
            if generic in found and found[generic]["exact"]:
                return
            after = text[end:end + 40]
            m = STRENGTH_RE.search(after)
            found[generic] = {
                "name": generic,
                "label_name": name,
                "strength": f"{m.group(1)} {m.group(2).lower()}" if m else "",
                "exact": exact,
            }

        skip_next = False
        for i, (w, start, end, clean) in enumerate(words):
            if skip_next:  # second word of a two-word name, like "calcium" in "atorvastatin calcium"
                skip_next = False
                continue
            if i + 1 < len(words):
                pair = f"{w} {words[i + 1][0]}"
                if pair in self.two_word:
                    add(pair, start, words[i + 1][2], clean and words[i + 1][3])
                    skip_next = True
                    continue
            if len(w) < 4:
                continue
            if w in self.one_word:
                add(w, start, end, clean)
            elif len(w) >= 6:
                # Text read from a photo has small mistakes ("LISINOPRlL"), so allow close matches.
                close = get_close_matches(w, self.one_word, n=1, cutoff=0.86)
                if close:
                    add(close[0], start, end, False)

        directions = DIRECTIONS_RE.search(text)
        return {
            "medicines": list(found.values()),
            "directions": re.sub(r"\s+", " ", directions.group(0)).strip().capitalize() if directions else "",
        }
