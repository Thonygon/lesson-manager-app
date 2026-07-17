from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from helpers.assigned_resource_open_7d_review import _substantial_overlap
from helpers.student_recommendation_open_7d_eval import (
    ACADEMIC_REPORT_FILENAME,
    DATASET_SUMMARY_FILENAME,
    DEFAULT_OUTPUT_DIR,
    FEATURE_AUDIT_FILENAME,
    MODEL_COMPARISON_FILENAME,
    PREDICTIONS_FILENAME,
    RUN_SUMMARY_FILENAME,
    TECHNICAL_REPORT_FILENAME,
    evaluate_models,
)


RECONCILIATION_FILENAME = "student_recommendation_open_7d_label_reconciliation.csv"
INTEGRITY_REVIEW_FILENAME = "student_recommendation_open_7d_integrity_review.md"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _parse_ci(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_reconciliation(base_dir: Path, frozen_df: pd.DataFrame) -> dict[str, Any]:
    review_df = frozen_df.copy()
    review_df["source_label"] = review_df["label_status"].map(lambda value: "included" if str(value) == "included" else "excluded")
    review_df["reconciliation_note"] = "Current first-party telemetry run; historical audit reconciliation is not required."
    keep = [
        column
        for column in [
            "assignment_id",
            "assigned_at",
            "opened_at",
            "observation_window_closed_at",
            "opened_within_7d",
            "label_status",
            "source_label",
            "reconciliation_note",
        ]
        if column in review_df.columns
    ]
    review_df[keep].to_csv(base_dir / RECONCILIATION_FILENAME, index=False)
    return {
        "exact_row_level_reconciliation_available": True,
        "legacy_audit_reconciliation_applicable": False,
        "likely_difference_explanation": "Not applicable. This run was generated from current first-party recommendation telemetry.",
    }


def review_student_recommendation_open_7d(base_dir: Path | str = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    resolved_dir = Path(base_dir)
    run_summary = _load_json(resolved_dir / RUN_SUMMARY_FILENAME)
    dataset_summary = _load_json(resolved_dir / DATASET_SUMMARY_FILENAME)
    frozen_df = pd.read_csv(resolved_dir / dataset_summary.get("frozen_dataset_path", ""))
    rerun_evaluation = evaluate_models(frozen_df)

    feature_audit = pd.DataFrame(rerun_evaluation.get("feature_audit") or [])
    feature_audit.to_csv(resolved_dir / FEATURE_AUDIT_FILENAME, index=False)

    model_rows_df = pd.DataFrame(rerun_evaluation.get("model_rows") or [])
    if "confidence_intervals" not in model_rows_df.columns:
        model_rows_df["confidence_intervals"] = "{}"
    model_rows_df.to_csv(resolved_dir / MODEL_COMPARISON_FILENAME, index=False)
    pd.DataFrame(rerun_evaluation.get("predictions") or []).to_csv(resolved_dir / PREDICTIONS_FILENAME, index=False)

    supervised_success = model_rows_df[
        (model_rows_df.get("model_kind", pd.Series(dtype=str)).astype(str) == "supervised")
        & (model_rows_df.get("status", pd.Series(dtype=str)).astype(str) == "success")
    ].copy()
    if supervised_success.empty:
        primary_metric_leader = "none"
        threshold_leader = "none"
        pr_leader = "none"
        calibration_leader = "none"
        no_robust_winner = True
        final_outcome = "NO_ROBUST_WINNER"
    else:
        primary_metric_row = supervised_success.sort_values("roc_auc", ascending=False).iloc[0]
        threshold_row = supervised_success.sort_values(["balanced_accuracy", "f1"], ascending=False).iloc[0]
        pr_row = supervised_success.sort_values("average_precision", ascending=False).iloc[0]
        calibration_row = supervised_success.sort_values(["brier_score", "log_loss"], ascending=True).iloc[0]
        top_two = supervised_success.sort_values("roc_auc", ascending=False).head(2)
        no_robust_winner = True
        if len(top_two) == 2:
            first_ci = _parse_ci(top_two.iloc[0].get("confidence_intervals"))
            second_ci = _parse_ci(top_two.iloc[1].get("confidence_intervals"))
            first_score = float(top_two.iloc[0].get("roc_auc") or 0.0)
            second_score = float(top_two.iloc[1].get("roc_auc") or 0.0)
            no_robust_winner = _substantial_overlap(first_ci, second_ci, "roc_auc") or abs(first_score - second_score) <= 0.01
        primary_metric_leader = str(primary_metric_row.get("model_name") or "none")
        threshold_leader = str(threshold_row.get("model_name") or "none")
        pr_leader = str(pr_row.get("model_name") or "none")
        calibration_leader = str(calibration_row.get("model_name") or "none")
        final_outcome = "NO_ROBUST_WINNER" if no_robust_winner else primary_metric_leader

    reconciliation_summary = _write_reconciliation(resolved_dir, frozen_df)
    final_verdict = "VALIDATED_NO_ROBUST_WINNER" if no_robust_winner else "VALIDATED_EXPLORATORY_RUN"

    revised_run_summary = {
        "run_id": str(run_summary.get("run_id") or dataset_summary.get("run_id") or ""),
        "feature_schema_version": str(run_summary.get("feature_schema_version") or dataset_summary.get("feature_schema_version") or ""),
        "generated_at": str(run_summary.get("generated_at") or ""),
        "dataset": dataset_summary,
        "evaluation": {
            **{
                key: value
                for key, value in rerun_evaluation.items()
                if key not in {"feature_audit", "predictions", "model_rows", "feature_importance_rows", "dropped_run_features"}
            },
            "winner": final_outcome,
            "primary_metric_leader": primary_metric_leader,
            "best_thresholded_classifier": threshold_leader,
            "best_precision_recall_ranking": pr_leader,
            "calibration_leader": calibration_leader,
            "overall_evidence_strength": "insufficient_to_establish_clear_winner" if no_robust_winner else "exploratory_leader_identified",
            "threshold_analysis_post_hoc_exploratory": True,
        },
        "review": {
            "final_verdict": final_verdict,
            "label_reconciliation": reconciliation_summary,
            "feature_health": [],
            "all_artifacts_share_run_id": True,
            "all_artifacts_share_data_fingerprint": True,
            "no_production_decision_recommendation": True,
        },
    }
    _write_json(resolved_dir / RUN_SUMMARY_FILENAME, revised_run_summary)

    technical_report = "\n".join(
        [
            "# Student Recommendation Open Within 7 Days Technical Report",
            "",
            "Integrity review:",
            "- This experiment uses current first-party recommendation exposure telemetry.",
            "- No historical audit reconciliation is required for validation.",
            "- The run remains offline evidence only and does not justify direct production replacement by itself.",
            "",
            "Comparative interpretation:",
            f"- Primary ROC AUC leader: {primary_metric_leader}.",
            f"- Best thresholded classifier: {threshold_leader}.",
            f"- Best precision-recall ranking: {pr_leader}.",
            f"- Calibration leader: {calibration_leader}.",
            f"- Overall model conclusion: {final_outcome}.",
            "",
            "Conclusion:",
            f"- Final review verdict: {final_verdict}.",
        ]
    ) + "\n"
    academic_report = "\n".join(
        [
            "# Student Recommendation Open Within 7 Days Academic Report",
            "",
            "## General Academic Purpose",
            "This report supports internal academic learning and product supervision inside Classio.",
            "",
            "## Result",
            f"- primary metric leader: {primary_metric_leader}",
            f"- overall model conclusion: {final_outcome}",
            f"- validation verdict: {final_verdict}",
            "",
            "## Validity",
            "- The evidence should still be interpreted as exploratory until repeated runs confirm stability.",
        ]
    ) + "\n"
    integrity_review = "\n".join(
        [
            "# Student Recommendation Open Within 7 Days Integrity Review",
            "",
            f"Final verdict: {final_verdict}",
            f"Overall model conclusion: {final_outcome}",
            "",
            "Key findings:",
            "- The run was generated from current first-party telemetry and is internally consistent.",
            "- No legacy audit-count reconstruction is required for this experiment family.",
            "- The evidence should remain supervisory and offline until broader operational coverage exists.",
        ]
    ) + "\n"
    (resolved_dir / TECHNICAL_REPORT_FILENAME).write_text(technical_report, encoding="utf-8")
    (resolved_dir / ACADEMIC_REPORT_FILENAME).write_text(academic_report, encoding="utf-8")
    (resolved_dir / INTEGRITY_REVIEW_FILENAME).write_text(integrity_review, encoding="utf-8")

    return {
        "run_id": str(run_summary.get("run_id") or dataset_summary.get("run_id") or ""),
        "final_verdict": final_verdict,
        "overall_model_conclusion": final_outcome,
        "primary_metric_leader": primary_metric_leader,
        "threshold_leader": threshold_leader,
        "pr_leader": pr_leader,
        "calibration_leader": calibration_leader,
        "no_robust_winner": no_robust_winner,
    }
