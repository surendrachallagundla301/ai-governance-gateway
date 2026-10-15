"""Release gate: fail the build if the trained model is below the agreed quality bar on the held-out set.

Usage: python -m governance_gateway.ml.evaluate --card models/model_card.json --min-recall 0.8 --min-precision 0.8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def gate(card: dict, min_recall: float, min_precision: float) -> list[str]:
    holdout = card["metrics"]["holdout"]
    failures = []
    if holdout["recall"] < min_recall:
        failures.append(f"holdout recall {holdout['recall']} < {min_recall}")
    if holdout["precision"] < min_precision:
        failures.append(f"holdout precision {holdout['precision']} < {min_precision}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", default="models/model_card.json", type=Path)
    parser.add_argument("--min-recall", default=0.8, type=float)
    parser.add_argument("--min-precision", default=0.8, type=float)
    args = parser.parse_args()

    card = json.loads(args.card.read_text(encoding="utf-8"))
    failures = gate(card, args.min_recall, args.min_precision)
    print(f"Model {card['version']} holdout metrics: {card['metrics']['holdout']}")
    if failures:
        print("GATE FAILED: " + "; ".join(failures))
        sys.exit(1)
    print("GATE PASSED")


if __name__ == "__main__":
    main()
