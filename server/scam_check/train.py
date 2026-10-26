"""Train the CareCircle scam classifier.

Usage:  python3 -I train.py <data_dir> <model_out>
"""

import csv
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline

MODERN_WEIGHT = 3.0  # modern U.S. examples count more than the 2012 UK dataset


def load(data_dir):
    texts, labels, weights = [], [], []
    with open(data_dir / "raw" / "sms.tsv", encoding="utf-8") as f:
        for line in f:
            label, _, text = line.rstrip("\n").partition("\t")
            texts.append(text)
            labels.append(1 if label == "spam" else 0)
            weights.append(1.0)
    with open(data_dir / "modern_examples.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            labels.append(1 if row["label"] == "spam" else 0)
            weights.append(MODERN_WEIGHT)
    return texts, np.array(labels), np.array(weights)


def build_model():
    features = FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, lowercase=True)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)),
    ])
    clf = LogisticRegression(C=8.0, class_weight="balanced", max_iter=3000)
    return Pipeline([("features", features), ("clf", clf)])


def main():
    data_dir, model_out = Path(sys.argv[1]), Path(sys.argv[2])
    texts, y, w = load(data_dir)
    print(f"Training examples: {len(texts)}  (scam: {y.sum()}, safe: {(1 - y).sum()})")

    model = build_model()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    preds = cross_val_predict(model, texts, y, cv=cv, params={"clf__sample_weight": w})
    print("\n5-fold cross-validation:")
    print(classification_report(y, preds, target_names=["safe", "scam"], digits=3))

    model.fit(texts, y, clf__sample_weight=w)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_out)
    print(f"Saved model to {model_out}")


if __name__ == "__main__":
    main()
