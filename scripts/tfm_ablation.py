"""Offline TFM ranking comparison. No product imports, network, or student data."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

VARIANTS = ("A", "B", "C")


def evaluate(payload: dict) -> dict:
    if not payload.get("code_version") or not payload.get("candidate_set_version"):
        raise ValueError("Code and candidate set versions are required")
    contexts = payload.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise ValueError("At least one context is required")
    results = []
    for context in contexts:
        candidates = context.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Every context needs frozen candidates")
        ids = [item.get("id") for item in candidates]
        if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("Candidate IDs must be unique nonempty strings")
        eligible = [item for item in candidates if item.get("eligible") is True]
        if any(item.get("eligible") not in (True, False) for item in candidates):
            raise ValueError("Every candidate needs a frozen eligibility decision")
        eligible_ids = {item["id"] for item in eligible}
        scores = context.get("scores") or {}
        if set(scores) != set(VARIANTS):
            raise ValueError("A, B and C scores are required")
        top = {}
        for variant in VARIANTS:
            rows = scores[variant]
            if not isinstance(rows, dict) or set(rows) != eligible_ids:
                raise ValueError("Every variant must score the same eligible candidates")
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in rows.values()):
                raise ValueError("Scores must be finite numbers")
            top[variant] = sorted(eligible_ids, key=lambda item: (-rows[item], item))[:5]
        result = {"context_id": context.get("id"), "eligible_count": len(eligible), "top5": top}
        judgments = context.get("judgments")
        if judgments is not None:
            if context.get("judgment_source") != "independent_human":
                raise ValueError("NDCG requires independent human judgments")
            if not isinstance(judgments, dict) or set(judgments) != eligible_ids:
                raise ValueError("All eligible candidates need judgments")
            if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 3 for value in judgments.values()):
                raise ValueError("Judgments must use integer relevance 0–3")
            ideal = sorted(judgments.values(), reverse=True)[:5]
            def dcg(grades):
                return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))
            denominator = dcg(ideal)
            result["ndcg_at_5"] = {variant: (dcg([judgments[item] for item in top[variant]]) / denominator if denominator else 0.0) for variant in VARIANTS}
        results.append(result)
    return {"code_version": payload["code_version"], "candidate_set_version": payload["candidate_set_version"], "model_versions": payload.get("model_versions", {}), "contexts": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Private frozen JSON; never commit real student data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
