"""Find a pill by the letters/numbers stamped on it, plus its color and shape."""

import gzip
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .build_pill_index import imprint_key, imprint_tokens

INDEX_PATH = Path(__file__).resolve().parents[1] / "data" / "pill_index.json.gz"

# Simple choices shown in the app, mapped to the database's color words.
COLOR_GROUPS = {
    "white": {"WHITE"},
    "yellow": {"YELLOW"},
    "orange": {"ORANGE"},
    "pink": {"PINK", "RED", "PURPLE"},
    "red": {"RED", "PINK"},
    "blue": {"BLUE", "TURQUOISE", "PURPLE"},
    "green": {"GREEN", "TURQUOISE"},
    "brown": {"BROWN", "ORANGE"},
    "gray": {"GRAY", "BLACK", "WHITE"},
}
SHAPE_GROUPS = {
    "round": {"ROUND", "DOUBLE CIRCLE"},
    "oval": {"OVAL", "CAPSULE", "TEAR"},
    "capsule": {"CAPSULE", "OVAL", "BULLET"},
    "other": None,  # any shape
}


def ingredient_names(ingredients):
    """'HYDROCODONE BITARTRATE[HYDROCODONE];ACETAMINOPHEN[ACETAMINOPHEN];'
    -> [('hydrocodone bitartrate', 'hydrocodone'), ('acetaminophen', 'acetaminophen')]"""
    text = ingredients or ""
    pairs = re.findall(r"([^;\[\]/,]+?)\s*\[([^\]]+)\]", text)
    if not pairs:  # no [brackets]: just names separated by semicolons
        pairs = [(p, p) for p in text.split(";") if p.strip()]
    return [(full.strip().lower(), moiety.strip().lower()) for full, moiety in pairs]


LOOK_ALIKES =str.maketrans({"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"})


def look_alike_key(key):
    """Treat characters that photos often mix up (O/0, I/1, S/5...) as the same."""
    return key.translate(LOOK_ALIKES)


class PillIndex:
    def __init__(self, path=INDEX_PATH):
        self.path = Path(path)
        self.pills = []
        self.source = None
        self.by_key = {}
        if self.path.exists():
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            self.pills = data["pills"]
            self.source = data.get("source")
            for p in self.pills:
                self.by_key.setdefault(p["key"], []).append(p)
                p["look_alike"] = look_alike_key(p["key"])

    @property
    def available(self):
        return bool(self.pills)

    def names(self):
        """Active-ingredient names in the database, mapped to their base medicine
        ('amlodipine besylate' -> 'amlodipine'). Used to spot medicines on bottle labels.
        Product names aren't used, because some are ordinary words like "Sleep" or "Cold"."""
        names = {}
        for p in self.pills:
            for full, moiety in ingredient_names(p.get("ingredients", "")):
                if re.search(r"\b(ion|cation|anion)$", moiety):
                    continue
                names.setdefault(moiety, moiety)
                if not re.search(r"\b(ion|cation|anion)$", full):
                    names.setdefault(full, moiety)
        return names

    def search(self, imprint, color=None, shape=None, limit=6):
        q_key = imprint_key(imprint)
        q_tokens = imprint_tokens(imprint)
        if not q_key:
            return []

        candidates = []
        for p in self.pills:
            score, why = self._imprint_score(q_key, q_tokens, p)
            if score <= 0:
                continue
            score += self._look_score(p, color, shape)
            candidates.append((score, why, p))

        candidates.sort(key=lambda c: -c[0])
        results, seen = [], set()
        for score, why, p in candidates:
            ident = (p["name"].lower(), p["strength"].lower(), p["key"])
            if ident in seen:
                continue
            seen.add(ident)
            results.append(self._present(p, score, why, color, shape))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _imprint_score(q_key, q_tokens, p):
        if p["key"] == q_key:
            return 100, "exact"
        if q_tokens and q_tokens == p["tokens"]:
            return 95, "exact"  # same marks, sides read in a different order
        if len(q_key) >= 2 and look_alike_key(q_key) == p["look_alike"]:
            return 85, "close"  # only differs by look-alike characters, like O and 0
        # One contains the other (a side wasn't read, or an extra mark was), but not tiny overlaps like "5".
        short, longer = sorted((q_key, p["key"]), key=len)
        if len(short) >= 3 and short in longer and len(short) / len(longer) >= 0.6:
            return 70, "partial"
        # Close spelling, for marks that were misread (O vs 0, I vs 1).
        if len(q_key) >= 3 and abs(len(p["key"]) - len(q_key)) <= 2:
            matcher = SequenceMatcher(None, q_key, p["key"])
            if matcher.quick_ratio() >= 0.8 and matcher.ratio() >= 0.8:
                return int(60 * matcher.ratio()), "close"
        return 0, None

    @staticmethod
    def _look_score(p, color, shape):
        score = 0
        if color and color in COLOR_GROUPS:
            score += 15 if set(p["colors"]) & COLOR_GROUPS[color] else -25
        if shape and SHAPE_GROUPS.get(shape):
            score += 10 if p["shape"] in SHAPE_GROUPS[shape] else -15
        return score

    @staticmethod
    def _present(p, score, why, color, shape):
        color_ok = not color or bool(set(p["colors"]) & COLOR_GROUPS.get(color, set(p["colors"])))
        shape_ok = not shape or not SHAPE_GROUPS.get(shape) or p["shape"] in SHAPE_GROUPS[shape]
        if why == "exact" and color_ok and shape_ok:
            match = "strong"
        elif why in ("exact", "partial", "close") and (color_ok or shape_ok):
            match = "possible"
        else:
            match = "weak"
        ingredients = ingredient_names(p.get("ingredients", ""))
        return {
            "name": p["name"],
            # The single active ingredient, used for the medicine list and FDA label lookups.
            "generic": ingredients[0][1] if len(ingredients) == 1 else "",
            "strength": p["strength"],
            "imprint": p["imprint"],
            "colors": [c.title() for c in p["colors"]],
            "shape": p["shape"].title(),
            "maker": p.get("maker", ""),
            "description": p.get("rx", ""),
            "match": match,
            "score": score,
        }
