#!/usr/bin/env python3
"""
Narrative eval harness — precision/recall vs gold_narrative fixtures.

Dry / mockable structure for expanding toward ~200 labeled pairs.

  PYTHONPATH=api python3 api/scripts/run_narrative_eval_harness.py
  PYTHONPATH=api python3 api/scripts/run_narrative_eval_harness.py \\
      --gold tests/fixtures/gold_narrative/starter_gold.json --mock-perfect
  PYTHONPATH=api python3 api/scripts/run_narrative_eval_harness.py --predictions /tmp/preds.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

_API_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_DEFAULT_GOLD = (
    _PROJECT_ROOT / "tests" / "fixtures" / "gold_narrative" / "starter_gold.json"
)


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = float(tp) / float(tp + fp) if (tp + fp) else 0.0
    recall = float(tp) / float(tp + fn) if (tp + fn) else 0.0
    f1 = (
        (2.0 * precision * recall / (precision + recall))
        if (precision + recall)
        else 0.0
    )
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def score_binary_pairs(
    gold_positive: set[tuple[Any, Any]],
    predicted_positive: set[tuple[Any, Any]],
) -> dict[str, float]:
    """Standard set precision/recall for unordered labeled pairs."""
    tp = len(gold_positive & predicted_positive)
    fp = len(predicted_positive - gold_positive)
    fn = len(gold_positive - predicted_positive)
    return _prf(tp, fp, fn)


def _norm_pair(a: Any, b: Any) -> tuple[Any, Any]:
    return (a, b) if a <= b else (b, a)


def evaluate_article_storyline(
    gold: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_pos = {
        (int(r["article_id"]), int(r["storyline_id"]))
        for r in gold.get("article_storyline_assignments") or []
        if str(r.get("label") or "").lower() in ("positive", "pos", "1", "true")
    }
    pred_pos = {
        (int(r["article_id"]), int(r["storyline_id"]))
        for r in predictions
        if str(r.get("label") or r.get("decision") or "").lower()
        in ("positive", "pos", "accept", "link", "1", "true")
    }
    return {
        "task": "article_storyline",
        **score_binary_pairs(gold_pos, pred_pos),
        "gold_positive": len(gold_pos),
        "predicted_positive": len(pred_pos),
    }


def evaluate_event_coreference(
    gold: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    gold_pos = {
        _norm_pair(int(r["event_a"]), int(r["event_b"]))
        for r in gold.get("event_coreference_pairs") or []
        if str(r.get("label") or "").lower() in ("same_event", "same", "positive", "pos")
    }
    pred_pos = {
        _norm_pair(int(r["event_a"]), int(r["event_b"]))
        for r in predictions
        if str(r.get("label") or r.get("decision") or "").lower()
        in ("same_event", "same", "positive", "pos", "accept", "1", "true")
    }
    return {
        "task": "event_coreference",
        **score_binary_pairs(gold_pos, pred_pos),
        "gold_positive": len(gold_pos),
        "predicted_positive": len(pred_pos),
    }


def mock_perfect_predictions(gold: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Oracle predictions matching gold positives (harness smoke)."""
    return {
        "article_storyline": [
            {
                "article_id": r["article_id"],
                "storyline_id": r["storyline_id"],
                "label": "positive",
            }
            for r in gold.get("article_storyline_assignments") or []
            if str(r.get("label") or "").lower() in ("positive", "pos", "1", "true")
        ],
        "event_coreference": [
            {
                "event_a": r["event_a"],
                "event_b": r["event_b"],
                "label": "same_event",
            }
            for r in gold.get("event_coreference_pairs") or []
            if str(r.get("label") or "").lower()
            in ("same_event", "same", "positive", "pos")
        ],
    }


def mock_empty_predictions(_gold: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {"article_storyline": [], "event_coreference": []}


def run_eval(
    gold: dict[str, Any],
    *,
    article_preds: list[dict[str, Any]] | None = None,
    event_preds: list[dict[str, Any]] | None = None,
    predictor: Callable[[dict[str, Any]], dict[str, list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    if predictor is not None:
        bundled = predictor(gold)
        article_preds = bundled.get("article_storyline") or []
        event_preds = bundled.get("event_coreference") or []
    article_preds = article_preds or []
    event_preds = event_preds or []
    return {
        "gold_version": gold.get("version"),
        "domain_key": gold.get("domain_key"),
        "article_storyline": evaluate_article_storyline(gold, article_preds),
        "event_coreference": evaluate_event_coreference(gold, event_preds),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=_DEFAULT_GOLD)
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="JSON with article_storyline + event_coreference prediction lists",
    )
    parser.add_argument(
        "--mock-perfect",
        action="store_true",
        help="Score oracle predictions against gold (expect P=R=1)",
    )
    parser.add_argument(
        "--mock-empty",
        action="store_true",
        help="Score empty predictions (expect P=0, R=0)",
    )
    args = parser.parse_args()

    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    predictor = None
    article_preds = None
    event_preds = None
    if args.mock_perfect:
        predictor = mock_perfect_predictions
    elif args.mock_empty:
        predictor = mock_empty_predictions
    elif args.predictions:
        pred_doc = json.loads(args.predictions.read_text(encoding="utf-8"))
        article_preds = pred_doc.get("article_storyline") or []
        event_preds = pred_doc.get("event_coreference") or []
    else:
        predictor = mock_empty_predictions

    result = run_eval(
        gold,
        article_preds=article_preds,
        event_preds=event_preds,
        predictor=predictor,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
