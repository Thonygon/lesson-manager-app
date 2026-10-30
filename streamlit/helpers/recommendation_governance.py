"""Conservative, aggregate evidence gate for recommendation model promotion.

Usage events are proxy outcomes, not independent relevance labels. This module
accepts only explicit human judgments of shown and held-out candidates. It
never exports raw judgments or learner identifiers in its result.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path


POLICY_PATH = Path(__file__).resolve().parents[2] / "docs/RECOMMENDATION_GOVERNANCE_POLICY.json"


def heuristic_fallback_enabled(family: str) -> bool:
    """An operator can retire learned ranking without changing stored evidence."""
    names = {
        "teacher_resources": "CLASSIO_TEACHER_RECOMMENDATION_MODE",
        "student_resources": "CLASSIO_STUDENT_RECOMMENDATION_MODE",
    }
    if family not in names:
        raise ValueError("Unknown recommendation family")
    return os.getenv(names[family], "").strip().lower() == "heuristic"


def _policy() -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if not policy.get("version") or not policy.get("families"):
        raise ValueError("Recommendation governance policy is incomplete")
    if any(not 0 <= float(policy[key]) <= 1 for key in ("decision_threshold", "maximum_error_regression_vs_baseline")):
        raise ValueError("Recommendation governance global thresholds must be between zero and one")
    for rule in policy["families"].values():
        if not rule.get("required_axes") or any(int(rule[key]) < 1 for key in ("minimum_evaluations", "minimum_positive", "minimum_negative", "minimum_held_out", "minimum_labelers", "minimum_segment")):
            raise ValueError("Recommendation governance minimums must be positive")
        if any(not 0 <= float(rule[key]) <= 1 for key in ("maximum_false_positive_rate", "maximum_false_negative_rate", "maximum_segment_error_gap")):
            raise ValueError("Recommendation governance rate thresholds must be between zero and one")
    return policy


def _wilson(successes: int, total: int) -> list[float] | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def _time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def _confusion(rows: list[dict], threshold: float) -> dict:
    tp = tn = fp = fn = 0
    for row in rows:
        predicted = row["score"] >= threshold
        label = row["label"] == 1
        if predicted and label:
            tp += 1
        elif predicted:
            fp += 1
        elif label:
            fn += 1
        else:
            tn += 1
    negatives, positives = fp + tn, tp + fn
    return {
        "count": len(rows), "positive": positives, "negative": negatives,
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "false_positive_rate": round(fp / negatives, 4) if negatives else None,
        "false_negative_rate": round(fn / positives, 4) if positives else None,
        "false_positive_rate_ci95": _wilson(fp, negatives),
        "false_negative_rate_ci95": _wilson(fn, positives),
    }


def evaluate_recommendation_evidence(judgments: list[dict], family: str, review: dict | None = None) -> dict:
    """Return only aggregate diagnostics and an explicit human-reviewed action."""
    policy = _policy()
    if family not in policy["families"]:
        raise ValueError("Unknown recommendation family")
    rule = policy["families"][family]
    threshold = float(policy["decision_threshold"])
    accepted: list[dict] = []
    seen_units: set[str] = set()
    seen_candidates: set[str] = set()
    model_versions: set[str] = set()
    for item in judgments:
        if not isinstance(item, dict) or item.get("label_source") != policy["label_source"]:
            continue
        unit = str(item.get("judgment_id") or "").strip()
        candidate = str(item.get("candidate_id") or "").strip()
        labeler = str(item.get("labeler_id") or "").strip()
        if not unit or not candidate or not labeler or unit in seen_units or candidate in seen_candidates or item.get("candidate_source") not in policy["candidate_sources"] or type(item.get("label")) is not int or item["label"] not in (0, 1):
            continue
        try:
            score = float(item["score"])
            baseline_score = float(item["baseline_score"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in (score, baseline_score)):
            continue
        trained_until = _time(item.get("trained_until"))
        judged_at = _time(item.get("judged_at"))
        if not trained_until or not judged_at or judged_at <= trained_until or judged_at > datetime.now(timezone.utc):
            continue
        model_version = str(item.get("model_version") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", model_version):
            continue
        axes = {axis: str(item.get(axis) or "").strip().casefold() for axis in rule["required_axes"]}
        if not all(axes.values()):
            continue
        axes = {axis: value if re.fullmatch(r"[a-z0-9_-]{1,40}", value) else "other" for axis, value in axes.items()}
        seen_units.add(unit)
        seen_candidates.add(candidate)
        model_versions.add(model_version)
        accepted.append({"judgment_hash": hashlib.sha256(unit.encode()).hexdigest(), "labeler_hash": hashlib.sha256(labeler.encode()).hexdigest(), "model_version": model_version, "label": item["label"], "score": score, "baseline_score": baseline_score, "candidate_source": item["candidate_source"], **axes})
    accepted.sort(key=lambda row: json.dumps(row, sort_keys=True))
    digest = hashlib.sha256(json.dumps(accepted, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    global_metrics = _confusion(accepted, threshold)
    baseline_metrics = _confusion([{**row, "score": row["baseline_score"]} for row in accepted], threshold)
    reasons: list[str] = []
    if len(model_versions) != 1:
        reasons.append("missing_or_mixed_model_version")
    model_version = next(iter(model_versions)) if len(model_versions) == 1 else None
    if len(accepted) < rule["minimum_evaluations"]:
        reasons.append("insufficient_independent_judgments")
    if global_metrics["positive"] < rule["minimum_positive"] or global_metrics["negative"] < rule["minimum_negative"]:
        reasons.append("insufficient_positive_or_negative_labels")
    if sum(row["candidate_source"] == "held_out" for row in accepted) < rule["minimum_held_out"]:
        reasons.append("insufficient_held_out_candidates")
    if len({row["labeler_hash"] for row in accepted}) < rule["minimum_labelers"]:
        reasons.append("insufficient_independent_labelers")
    if accepted and len({row["candidate_source"] for row in accepted}) < len(policy["candidate_sources"]):
        reasons.append("missing_candidate_source")
    segments: list[dict] = []
    for axis in rule["required_axes"]:
        values = sorted({row[axis] for row in accepted})
        if not values:
            reasons.append(f"missing_axis:{axis}")
        if "other" in values:
            reasons.append(f"unclassified_segment:{axis}")
        axis_rates: dict[str, list[float]] = {"false_positive_rate": [], "false_negative_rate": []}
        for value in values:
            rows = [row for row in accepted if row[axis] == value]
            if len(rows) < rule["minimum_segment"]:
                reasons.append(f"small_segment:{axis}")
                segments.append({"axis": axis, "value": value, "count": len(rows), "suppressed": True})
                continue
            metrics = _confusion(rows, threshold)
            if metrics["positive"] < 1 or metrics["negative"] < 1:
                reasons.append(f"single_class_segment:{axis}")
            for rate in axis_rates:
                if metrics[rate] is not None:
                    axis_rates[rate].append(metrics[rate])
            segments.append({"axis": axis, "value": value, **metrics, "suppressed": False})
        for rate, rates in axis_rates.items():
            if len(rates) > 1 and max(rates) - min(rates) > rule["maximum_segment_error_gap"]:
                reasons.append(f"segment_error_gap:{axis}:{rate}")
    for rate in ("false_positive_rate", "false_negative_rate"):
        if global_metrics[rate] is not None and global_metrics[rate] > rule[f"maximum_{rate}"]:
            reasons.append(f"high_{rate}")
        if global_metrics[rate] is not None and baseline_metrics[rate] is not None and global_metrics[rate] > baseline_metrics[rate] + policy["maximum_error_regression_vs_baseline"]:
            reasons.append(f"regressed_vs_baseline:{rate}")
    reasons = sorted(set(reasons))
    eligible = not reasons
    action = "hold"
    review = review or {}
    try:
        reviewed_at = datetime.fromisoformat(str(review.get("reviewed_at") or "").replace("Z", "+00:00"))
        valid_date = reviewed_at.tzinfo is not None and reviewed_at <= datetime.now(timezone.utc)
    except ValueError:
        valid_date = False
    reviewed = (review.get("family") == family and review.get("policy_version") == policy["version"]
                and model_version is not None and review.get("model_version") == model_version
                and review.get("evidence_sha256") == digest and valid_date
                and bool(str(review.get("reviewer") or "").strip()) and bool(str(review.get("rationale") or "").strip())
                and hashlib.sha256(str(review.get("reviewer") or "").strip().encode()).hexdigest()
                not in {row["labeler_hash"] for row in accepted})
    if reviewed and review.get("decision") == "retire":
        action = "heuristic_fallback"
    elif eligible and reviewed and review.get("decision") == "promote":
        action = "promote"
    return {
        "family": family, "policy_version": policy["version"], "model_version": model_version, "evidence_sha256": digest,
        "eligible_for_human_approval": eligible, "action": action,
        "review_record_valid": reviewed, "reasons": reasons,
        "excluded_rows": len(judgments) - len(accepted), "held_out_count": sum(row["candidate_source"] == "held_out" for row in accepted),
        "labeler_count": len({row["labeler_hash"] for row in accepted}),
        "global": global_metrics if len(accepted) >= rule["minimum_segment"] else {"count": len(accepted), "suppressed": True},
        "baseline": baseline_metrics if len(accepted) >= rule["minimum_segment"] else {"count": len(accepted), "suppressed": True},
        "segments": segments,
    }


def write_governance_artifact(
    output_dir: str | Path,
    family: str,
    *,
    evaluation_json: str | Path | None = None,
    review_json: str | Path | None = None,
) -> tuple[Path, dict]:
    """Write only aggregated evidence; never copy raw judgments to reports."""
    judgments = json.loads(Path(evaluation_json).read_text(encoding="utf-8")) if evaluation_json else []
    review = json.loads(Path(review_json).read_text(encoding="utf-8")) if review_json else None
    if not isinstance(judgments, list) or (review is not None and not isinstance(review, dict)):
        raise ValueError("Recommendation evaluation/review input has an invalid shape")
    result = evaluate_recommendation_evidence(judgments, family, review)
    destination = Path(output_dir) / f"classio_{family}_governance.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination, result
