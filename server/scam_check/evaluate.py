"""Evaluate on held-out modern messages the model never trained on.

Compares the ML model alone vs. the full CareCircle checker (model + red flags).
Usage:  python3 -I evaluate.py <holdout_csv>
"""

import csv
import sys

from checker import ScamChecker


def main():
    rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
    checker = ScamChecker()

    model_correct = full_correct = 0
    missed_scams, false_alarms = [], []
    print(f"{'truth':6} {'model':>6} {'verdict':8} message")
    print("-" * 100)
    for row in rows:
        truth = row["label"]
        res = checker.check(row["text"])
        model_says = "spam" if res["model_probability"] >= 0.5 else "ham"
        full_says = "ham" if res["verdict"] == "safe" else "spam"
        model_correct += model_says == truth
        full_correct += full_says == truth
        if truth == "spam" and full_says == "ham":
            missed_scams.append(row["text"])
        if truth == "ham" and res["verdict"] != "safe":
            false_alarms.append((res["verdict"], row["text"]))
        mark = "" if full_says == truth else "  <-- WRONG"
        print(f"{truth:6} {res['model_probability']:6.2f} {res['verdict']:8} {row['text'][:70]}{mark}")

    n = len(rows)
    print(f"\nModel alone:            {model_correct}/{n} correct ({model_correct / n:.0%})")
    print(f"Model + red flags:      {full_correct}/{n} correct ({full_correct / n:.0%})")
    print(f"Scams missed:           {len(missed_scams)}")
    print(f"Safe messages flagged:  {len(false_alarms)}")
    for v, t in false_alarms:
        print(f"   [{v}] {t}")


if __name__ == "__main__":
    main()
