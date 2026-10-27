"""Check a medicine list for warnings, using official FDA drug labels (openFDA).

For each medicine, we fetch its FDA label and look in the "drug interactions" section
for the other medicines on the list (or the group they belong to, like "NSAIDs").
We show the label's own sentences, never our own medical judgment.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OPENFDA_URL = "https://api.fda.gov/drug/label.json"

# Label sections that describe interactions, in order of preference.
# The last three are used on over-the-counter labels (like ibuprofen).
SECTIONS = ["drug_interactions", "precautions", "warnings_and_cautions",
            "ask_doctor_or_pharmacist", "do_not_use", "ask_doctor"]


class LabelUnavailable(Exception):
    """The FDA service couldn't be reached."""


def fetch_label_from_openfda(name, timeout=8):
    """Return the interaction text from the FDA label for this medicine, or None if no label."""
    api_key = os.environ.get("OPENFDA_API_KEY")
    for field in ("openfda.generic_name", "openfda.brand_name", "openfda.substance_name"):
        params = {"search": f'{field}:"{name}"', "limit": "10"}
        if api_key:
            params["api_key"] = api_key
        url = f"{OPENFDA_URL}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:  # openFDA's way of saying "no matches"
                continue
            raise LabelUnavailable(str(e)) from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise LabelUnavailable(str(e)) from e

        results = data.get("results", [])
        if not results:
            continue
        # Prefer a label for this medicine alone, not a combination pill.
        want = name.upper()
        best = next((r for r in results if want in [g.upper() for g in r.get("openfda", {}).get("generic_name", [])]), results[0])
        text = " ".join(" ".join(best.get(s, [])) for s in SECTIONS if best.get(s))
        if text.strip():
            return text
    return None


class InteractionChecker:
    def __init__(self, fetch_label=fetch_label_from_openfda, cache_seconds=24 * 3600):
        self.fetch_label = fetch_label
        self.cache = {}
        self.cache_seconds = cache_seconds
        groups = json.loads((DATA / "drug_classes.json").read_text(encoding="utf-8"))["groups"]
        self.groups = list(groups.values())

    def _label(self, name):
        hit = self.cache.get(name)
        if hit and time.time() - hit[0] < self.cache_seconds:
            return hit[1]
        text = self.fetch_label(name)
        self.cache[name] = (time.time(), text)
        return text

    def terms_for(self, name):
        """Words that would mean a label is talking about this medicine."""
        terms = {name}
        for g in self.groups:
            if name in g["members"]:
                terms.update(g["terms"])
        return sorted(terms, key=len, reverse=True)

    def check(self, meds):
        meds = list(dict.fromkeys(m.strip().lower() for m in meds if m.strip()))
        labels, no_label = {}, []
        for m in meds:
            text = self._label(m)  # may raise LabelUnavailable
            if text:
                labels[m] = text
            else:
                no_label.append(m)

        pairs = {}
        for a, text in labels.items():
            sentences = re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", text))
            for b in meds:
                if b == a:
                    continue
                for term in self.terms_for(b):
                    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
                    hits = [s for s in sentences if pattern.search(s)]
                    if hits:
                        key = tuple(sorted((a, b)))
                        entry = pairs.setdefault(key, {"medicines": list(key), "mentions": []})
                        entry["mentions"].append({
                            "label_of": a,
                            "mentions": b,
                            "matched_words": term,
                            "excerpt": _short(hits[0], term),
                        })
                        break

        return {
            "checked": meds,
            "warnings": list(pairs.values()),
            "no_label_found": no_label,
        }


def _short(sentence, term, width=320):
    """Trim a long label sentence to the part around the matched words."""
    sentence = sentence.strip()
    if len(sentence) <= width:
        return sentence
    i = sentence.lower().find(term.lower())
    start = max(0, i - width // 2)
    piece = sentence[start:start + width]
    return ("…" if start > 0 else "") + piece.strip() + ("…" if start + width < len(sentence) else "")
