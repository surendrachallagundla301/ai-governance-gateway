"""Train the prompt-injection classifier, evaluate it, and write a versioned model + model card.

Usage: python -m governance_gateway.ml.train --out models
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from governance_gateway.ml.data import generate, load_jsonl

MODEL_FILE = "injection_clf.joblib"
CARD_FILE = "model_card.json"


def build_pipeline() -> Pipeline:
    features = FeatureUnion(
        [
            ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
            ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced", C=4.0)),
        ]
    )


def metrics(y_true, scores, threshold: float) -> dict:
    preds = [int(s >= threshold) for s in scores]
    return {
        "precision": round(precision_score(y_true, preds, zero_division=0), 4),
        "recall": round(recall_score(y_true, preds, zero_division=0), 4),
        "f1": round(f1_score(y_true, preds, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_true, scores), 4),
        "n": len(y_true),
    }


def train(out_dir: Path, holdout_path: Path, threshold: float = 0.5, seed: int = 7) -> dict:
    rows = generate(seed)
    texts, labels = [r["text"] for r in rows], [r["label"] for r in rows]
    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=seed
    )

    pipeline = build_pipeline()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    cv_f1 = cross_val_score(pipeline, x_train, y_train, cv=cv, scoring="f1")
    pipeline.fit(x_train, y_train)

    holdout = load_jsonl(holdout_path)
    h_texts, h_labels = [r["text"] for r in holdout], [r["label"] for r in holdout]

    card = {
        "model": "prompt-injection-classifier",
        "version": datetime.now(UTC).strftime("%Y%m%d%H%M%S"),
        "algorithm": "TF-IDF (word 1-2 grams + char 3-5 grams) + logistic regression",
        "threshold": threshold,
        "training_data": {
            "source": "synthetic templates (governance_gateway/ml/data.py)",
            "rows": len(rows),
            "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        },
        "metrics": {
            "cv_f1_mean": round(float(cv_f1.mean()), 4),
            "test": metrics(y_test, pipeline.predict_proba(x_test)[:, 1], threshold),
            "holdout": metrics(h_labels, pipeline.predict_proba(h_texts)[:, 1], threshold),
        },
        "intended_use": "One signal among several (with heuristic rules) for screening agent inputs "
        "and tool outputs. Not a sole security control.",
        "limitations": "Trained on synthetic English text; expect lower recall on novel or non-English "
        "attacks. Retrain on real labeled traffic before production use.",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, out_dir / MODEL_FILE)
    (out_dir / CARD_FILE).write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="models", type=Path)
    parser.add_argument("--holdout", default="data/holdout.jsonl", type=Path)
    parser.add_argument("--threshold", default=0.5, type=float)
    args = parser.parse_args()
    card = train(args.out, args.holdout, args.threshold)
    print(json.dumps(card["metrics"], indent=2))


if __name__ == "__main__":
    main()
