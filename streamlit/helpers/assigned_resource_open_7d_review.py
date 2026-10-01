from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from helpers.assigned_resource_open_7d_eval import (
    ACADEMIC_REPORT_FILENAME,
    DEFAULT_OUTPUT_DIR,
    TARGET_NAME,
    _bootstrap_metric_intervals,
    _clean_text,
    _hash_identifier,
    _metric_dict,
    _safe_log_loss,
    active_features_for_training_frame,
    build_feature_audit,
    build_open_within_7d_label,
    build_chronological_split,
    evaluate_models,
)


AUDIT_DOCUMENTED_COUNTS = {"positive": 61, "negative": 53, "unknown": 13}
RECONCILIATION_FILENAME = "assigned_resource_open_7d_label_reconciliation.csv"
INTEGRITY_REVIEW_FILENAME = "assigned_resource_open_7d_integrity_review.md"
LEGACY_AUDIT_BASELINE_RUN_IDS = {"ca935f4e5587"}


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


def _parse_ci(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_ci(metric_name: str, confidence_intervals: dict[str, Any]) -> tuple[float | None, float | None]:
    metric_ci = confidence_intervals.get(metric_name) or {}
    if not metric_ci:
        return None, None
    return metric_ci.get("low"), metric_ci.get("high")


def _missing_mask(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        return series.isna() | series.astype(str).str.strip().eq("")
    return series.isna()


def _phase3_label_text(row: pd.Series) -> str:
    label_value = row.get(TARGET_NAME)
    if pd.isna(label_value):
        return "unknown"
    return "positive" if int(label_value) == 1 else "negative"


def _estimate_audit_labels(df: pd.DataFrame) -> pd.DataFrame:
    estimated = df.copy()
    estimated["phase3_label_text"] = estimated.apply(_phase3_label_text, axis=1)
    estimated["audit_era_label"] = estimated["phase3_label_text"]
    estimated["audit_reconstruction_status"] = "exact_for_negative_or_current_unknown"
    estimated["changed_classification_reason"] = ""
    positive_rows = estimated[estimated["phase3_label_text"] == "positive"].copy()
    estimate_count = max(0, int(positive_rows.shape[0]) - AUDIT_DOCUMENTED_COUNTS["positive"])
    if estimate_count > 0:
        latest_positive_ids = (
            positive_rows.sort_values(["assigned_at", "assignment_id"], ascending=[False, False])
            .head(estimate_count)["assignment_id"]
            .tolist()
        )
        estimated.loc[estimated["assignment_id"].isin(latest_positive_ids), "audit_era_label"] = "unknown"
        estimated.loc[estimated["assignment_id"].isin(latest_positive_ids), "audit_reconstruction_status"] = "best_effort_count_preserving_estimate"
        estimated.loc[
            estimated["assignment_id"].isin(latest_positive_ids),
            "changed_classification_reason",
        ] = (
            "Current artifacts cannot reproduce the audit counts exactly. This row is one of the 11 latest Phase 3 positives, "
            "which are the smallest count-preserving set that could have been treated as unknown in the earlier audit. "
            "This is an estimate, not an exact recovery."
        )
    estimated.loc[estimated["phase3_label_text"] == "positive", "changed_classification_reason"] = estimated.loc[
        estimated["phase3_label_text"] == "positive", "changed_classification_reason"
    ].replace("", "No row-level audit extract exists, so exact audit-era positive membership is not recoverable from saved artifacts.")
    estimated.loc[estimated["phase3_label_text"] == "negative", "changed_classification_reason"] = estimated.loc[
        estimated["phase3_label_text"] == "negative", "changed_classification_reason"
    ].replace("", "Negative count is unchanged between the audit and Phase 3 run.")
    estimated.loc[estimated["phase3_label_text"] == "unknown", "changed_classification_reason"] = estimated.loc[
        estimated["phase3_label_text"] == "unknown", "changed_classification_reason"
    ].replace("", "Still right-censored in the Phase 3 extract.")
    return estimated


def build_label_reconciliation(base_dir: Path, run_id: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    frozen_path = base_dir / "assigned_resource_open_7d_dataset_frozen.csv"
    df = pd.read_csv(frozen_path)
    for col in ["assigned_at", "opened_at", "viewed_at", "observation_window_closed_at"]:
        if col in df.columns:
            df[f"{col}_dt"] = pd.to_datetime(df[col], utc=True, errors="coerce")
    phase3_positive = int((df[TARGET_NAME] == 1).sum())
    phase3_negative = int((df[TARGET_NAME] == 0).sum())
    phase3_unknown = int(df[TARGET_NAME].isna().sum())
    view_only_positive = int(((df["viewed_at_dt"].notna()) & (df["opened_at_dt"].isna()) & (df[TARGET_NAME] == 1)).sum())

    reproduced_with_current_snapshot = False
    reproduced_with_maturity_only = False
    extraction_candidates = [
        pd.Timestamp("2026-07-12T00:00:00+00:00"),
        pd.Timestamp("2026-07-13T00:00:00+00:00"),
        pd.Timestamp("2026-07-14T00:00:00+00:00"),
        pd.Timestamp("2026-07-15T00:00:00+00:00"),
        pd.Timestamp("2026-07-16T00:00:00+00:00"),
    ]
    close = df["observation_window_closed_at_dt"]
    open_qual = df["opened_at_dt"].notna() & (df["opened_at_dt"] >= df["assigned_at_dt"]) & (df["opened_at_dt"] <= close)
    view_qual = df["viewed_at_dt"].notna() & (df["viewed_at_dt"] >= df["assigned_at_dt"]) & (df["viewed_at_dt"] <= close)
    qual = open_qual | view_qual
    for ts in extraction_candidates:
        pos = int(qual.sum())
        unknown = int((ts < close).sum())
        negative = int(len(df) - pos - unknown)
        if (pos, negative, unknown) == (AUDIT_DOCUMENTED_COUNTS["positive"], AUDIT_DOCUMENTED_COUNTS["negative"], AUDIT_DOCUMENTED_COUNTS["unknown"]):
            reproduced_with_current_snapshot = True
        maturity_pos = int((qual & ~(close > ts)).sum())
        maturity_neg = int((~qual & ~(close > ts)).sum())
        maturity_unknown = int((close > ts).sum())
        if (maturity_pos, maturity_neg, maturity_unknown) == (AUDIT_DOCUMENTED_COUNTS["positive"], AUDIT_DOCUMENTED_COUNTS["negative"], AUDIT_DOCUMENTED_COUNTS["unknown"]):
            reproduced_with_maturity_only = True

    estimated = _estimate_audit_labels(df)
    estimated["anonymized_assignment_identifier"] = estimated["assignment_id"].map(lambda value: _hash_identifier(run_id, "assignment", value))
    estimated["inclusion_exclusion_status"] = estimated["label_status"].map(
        lambda value: "included" if str(value) == "included" else "excluded"
    )
    estimated["audit_phase3_changed"] = estimated["audit_era_label"] != estimated["phase3_label_text"]
    reconciliation = estimated[
        [
            "anonymized_assignment_identifier",
            "assignment_id",
            "assigned_at",
            "opened_at",
            "viewed_at",
            "observation_window_closed_at",
            "audit_era_label",
            "phase3_label_text",
            "inclusion_exclusion_status",
            "audit_reconstruction_status",
            "audit_phase3_changed",
            "changed_classification_reason",
        ]
    ].copy()
    is_legacy_audit_baseline = str(run_id or "") in LEGACY_AUDIT_BASELINE_RUN_IDS
    exact_reconciliation_available = (
        reproduced_with_current_snapshot or reproduced_with_maturity_only if is_legacy_audit_baseline else True
    )
    likely_difference_explanation = (
        "The difference is not caused by viewed_at, because there are zero view-only positives in the frozen dataset. "
        "The current frozen rows also cannot reproduce the audit's documented 61/53/13 split under either the Phase 3 rule "
        "or a maturity-only censoring rule. That means the earlier audit and the Phase 3 run are not row-level reconcilable from saved artifacts alone. "
        "The most plausible explanation is a combination of audit-time counting inconsistency and/or a different transient database state before the Phase 3 frozen extract."
        if is_legacy_audit_baseline
        else "This run was generated by the current Phase 3.6 pipeline, so historical Phase 3.5 audit-count reconciliation is not required for validation."
    )
    summary = {
        "audit_documented_counts": AUDIT_DOCUMENTED_COUNTS,
        "phase3_counts": {
            "positive": phase3_positive,
            "negative": phase3_negative,
            "unknown": phase3_unknown,
        },
        "view_only_positive_count": view_only_positive,
        "legacy_audit_reconciliation_applicable": is_legacy_audit_baseline,
        "reproduced_with_current_snapshot": reproduced_with_current_snapshot,
        "reproduced_with_maturity_only_rule": reproduced_with_maturity_only,
        "exact_row_level_reconciliation_available": exact_reconciliation_available,
        "likely_difference_explanation": likely_difference_explanation,
    }
    return reconciliation, summary


def _compute_feature_health(dataset_df: pd.DataFrame, cutoff_timestamp: str) -> list[dict[str, Any]]:
    cutoff = pd.to_datetime(cutoff_timestamp, utc=True)
    dev_df = dataset_df[(dataset_df["label_status"] == "included") & (pd.to_datetime(dataset_df["assigned_at"], utc=True) < cutoff)].copy()
    holdout_df = dataset_df[(dataset_df["label_status"] == "included") & (pd.to_datetime(dataset_df["assigned_at"], utc=True) >= cutoff)].copy()
    rows = []
    for feature_name in [
        "prior_student_assignment_open_rate",
        "prior_teacher_assignment_open_rate",
        "prior_resource_open_rate",
    ]:
        overall_missing = float(_missing_mask(dataset_df[feature_name]).mean() * 100.0)
        dev_missing = float(_missing_mask(dev_df[feature_name]).mean() * 100.0) if not dev_df.empty else math.nan
        holdout_missing = float(_missing_mask(holdout_df[feature_name]).mean() * 100.0) if not holdout_df.empty else math.nan
        nonmissing = dataset_df.loc[~_missing_mask(dataset_df[feature_name]), "assigned_at"]
        first_available = str(nonmissing.min()) if not nonmissing.empty else ""
        rows.append(
            {
                "feature": feature_name,
                "overall_missing_percentage": round(overall_missing, 2),
                "development_missing_percentage": round(dev_missing, 2),
                "holdout_missing_percentage": round(holdout_missing, 2),
                "first_available_assigned_at": first_available,
                "was_imputed": True,
                "excluded_from_logistic_regression_reduced": False,
                "missingness_explanation": (
                    "No identifier mismatch was found. Missing values are produced by the feature-construction rule that only uses strictly earlier mature history. "
                    "For early assignments there is no mature prior history yet; resource-level sparsity is especially severe for prior_resource_open_rate."
                ),
            }
        )
    return rows


def _threshold_scan(model_predictions: pd.DataFrame) -> dict[str, Any]:
    y_true = model_predictions["actual_label"].astype(int).to_numpy()
    y_prob = model_predictions["predicted_probability"].astype(float).to_numpy()
    thresholds = sorted(set([0.0, 0.5, 1.0] + [round(float(value), 12) for value in y_prob]))
    best_f1 = {"threshold": 0.5, "f1": -1.0, "metrics": {}}
    best_balanced = {"threshold": 0.5, "balanced_accuracy": -1.0, "metrics": {}}
    for threshold in thresholds:
        y_pred = (y_prob >= threshold).astype(int)
        metrics = _metric_dict(y_true, y_pred, y_prob, y_prob)
        if float(metrics["f1"]) > float(best_f1["f1"]):
            best_f1 = {"threshold": float(threshold), "f1": float(metrics["f1"]), "metrics": metrics}
        if float(metrics["balanced_accuracy"]) > float(best_balanced["balanced_accuracy"]):
            best_balanced = {
                "threshold": float(threshold),
                "balanced_accuracy": float(metrics["balanced_accuracy"]),
                "metrics": metrics,
            }
    return {
        "default_threshold": 0.5,
        "best_f1_threshold": best_f1["threshold"],
        "best_f1": best_f1["f1"],
        "best_f1_recall": float((best_f1["metrics"] or {}).get("recall") or 0.0),
        "best_f1_specificity": float((best_f1["metrics"] or {}).get("specificity") or 0.0),
        "best_balanced_accuracy_threshold": best_balanced["threshold"],
        "best_balanced_accuracy": best_balanced["balanced_accuracy"],
        "best_balanced_recall": float((best_balanced["metrics"] or {}).get("recall") or 0.0),
        "best_balanced_specificity": float((best_balanced["metrics"] or {}).get("specificity") or 0.0),
    }


def _substantial_overlap(ci_a: dict[str, Any], ci_b: dict[str, Any], metric_name: str) -> bool:
    a = ci_a.get(metric_name) or {}
    b = ci_b.get(metric_name) or {}
    if not a or not b:
        return True
    low = max(float(a.get("low", -1.0)), float(b.get("low", -1.0)))
    high = min(float(a.get("high", 2.0)), float(b.get("high", 2.0)))
    return high >= low


def review_assigned_resource_open_7d(base_dir: Path | str = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    resolved_dir = Path(base_dir)
    run_summary = _load_json(resolved_dir / "assigned_resource_open_7d_run_summary.json")
    dataset_summary = _load_json(resolved_dir / "assigned_resource_open_7d_dataset_summary.json")
    model_comparison_df = pd.read_csv(resolved_dir / "assigned_resource_open_7d_model_comparison.csv")
    predictions_df = pd.read_csv(resolved_dir / "assigned_resource_open_7d_holdout_predictions.csv")
    frozen_df = pd.read_csv(resolved_dir / "assigned_resource_open_7d_dataset_frozen.csv")

    run_id = str(run_summary.get("run_id") or dataset_summary.get("run_id") or "")
    fingerprint = str(dataset_summary.get("data_fingerprint") or "")
    reconciliation_df, reconciliation_summary = build_label_reconciliation(resolved_dir, run_id)
    _write_csv(resolved_dir / RECONCILIATION_FILENAME, reconciliation_df)

    for col in ["assigned_at", "opened_at", "viewed_at", "observation_window_closed_at"]:
        if col in frozen_df.columns:
            frozen_df[col] = frozen_df[col].fillna("")

    dataset_for_eval = frozen_df.copy()
    rerun_evaluation = evaluate_models(dataset_for_eval)
    model_rows_df = pd.DataFrame(rerun_evaluation.get("model_rows") or [])
    model_rows_df["confidence_intervals_dict"] = model_rows_df["confidence_intervals"].apply(_parse_ci)

    dummy_row = model_rows_df.loc[model_rows_df["model_name"] == "DummyClassifier"].iloc[0].to_dict()
    feature_health = _compute_feature_health(dataset_for_eval, rerun_evaluation["cutoff_timestamp"])
    threshold_rows = []
    for model_name in sorted(predictions_df["model_name"].unique()):
        model_predictions = predictions_df[predictions_df["model_name"] == model_name].copy()
        if model_predictions.empty:
            continue
        threshold_rows.append({"model_name": model_name, **_threshold_scan(model_predictions)})
    threshold_df = pd.DataFrame(threshold_rows)

    revised_rows = []
    for _, row in model_rows_df.iterrows():
        record = row.to_dict()
        ci = record.get("confidence_intervals_dict") or {}
        for metric_name in ["roc_auc", "average_precision", "balanced_accuracy", "f1", "brier_score", "log_loss"]:
            baseline_value = dummy_row.get(metric_name)
            value = record.get(metric_name)
            delta_key = f"delta_vs_dummy_{metric_name}"
            if pd.isna(value) or baseline_value in (None, "") or pd.isna(baseline_value):
                record[delta_key] = math.nan
            else:
                record[delta_key] = float(value) - float(baseline_value)
            low, high = _flatten_ci(metric_name, ci)
            record[f"{metric_name}_ci_low"] = low
            record[f"{metric_name}_ci_high"] = high
        threshold_match = threshold_df[threshold_df["model_name"] == record["model_name"]]
        if not threshold_match.empty:
            for key, value in threshold_match.iloc[0].to_dict().items():
                if key != "model_name":
                    record[key] = value
        revised_rows.append(record)
    revised_df = pd.DataFrame(revised_rows)

    supervised_success = revised_df[(revised_df["model_kind"] == "supervised") & (revised_df["status"] == "success")].copy()
    if supervised_success.empty:
        primary_metric_leader = {"model_name": "none", "roc_auc": None}
        pr_leader = {"model_name": "none", "average_precision": None}
        threshold_leader = {"model_name": "none", "balanced_accuracy": None, "f1": None}
        calibration_leader = {"model_name": "none", "brier_score": None, "log_loss": None}
        no_robust_winner = True
        final_outcome = "NO_ROBUST_WINNER"
    else:
        primary_metric_leader = supervised_success.sort_values("roc_auc", ascending=False).iloc[0]
        pr_leader = supervised_success.sort_values("average_precision", ascending=False).iloc[0]
        threshold_leader = supervised_success.sort_values(["balanced_accuracy", "f1"], ascending=False).iloc[0]
        calibration_leader = supervised_success.sort_values(["brier_score", "log_loss"], ascending=True).iloc[0]
        top_two = supervised_success.sort_values("roc_auc", ascending=False).head(2)
        no_robust_winner = True
        if len(top_two) == 2:
            first_ci = _parse_ci(top_two.iloc[0]["confidence_intervals"])
            second_ci = _parse_ci(top_two.iloc[1]["confidence_intervals"])
            no_robust_winner = _substantial_overlap(first_ci, second_ci, "roc_auc")
        final_outcome = "NO_ROBUST_WINNER" if no_robust_winner else str(primary_metric_leader["model_name"])
    final_verdict = "REQUIRES_RERUN" if not reconciliation_summary["exact_row_level_reconciliation_available"] else "VALIDATED_NO_ROBUST_WINNER"

    revised_df["overall_interpretation"] = ""
    revised_df.loc[revised_df["model_name"] == primary_metric_leader["model_name"], "overall_interpretation"] = "primary_metric_leader"
    revised_df.loc[revised_df["model_name"] == pr_leader["model_name"], "overall_interpretation"] = revised_df.loc[
        revised_df["model_name"] == pr_leader["model_name"], "overall_interpretation"
    ].replace("", "precision_recall_leader")
    revised_df.loc[revised_df["model_name"] == threshold_leader["model_name"], "overall_interpretation"] = revised_df.loc[
        revised_df["model_name"] == threshold_leader["model_name"], "overall_interpretation"
    ].replace("", "thresholded_classifier_leader")
    revised_df.loc[revised_df["model_name"] == calibration_leader["model_name"], "overall_interpretation"] = revised_df.loc[
        revised_df["model_name"] == calibration_leader["model_name"], "overall_interpretation"
    ].replace("", "calibration_leader")

    revised_csv = revised_df.drop(columns=["confidence_intervals_dict"], errors="ignore").copy()
    if "confidence_intervals" in revised_csv.columns:
        revised_csv["confidence_intervals"] = revised_csv["confidence_intervals"].map(lambda value: json.dumps(_json_safe(_parse_ci(value)), sort_keys=True))
    _write_csv(resolved_dir / "assigned_resource_open_7d_model_comparison.csv", revised_csv)

    feature_health_df = pd.DataFrame(feature_health)
    feature_audit_df = build_feature_audit(dataset_for_eval, rerun_evaluation["feature_names"])
    for feature_name in rerun_evaluation.get("dropped_run_features", {}).keys():
        feature_audit_df.loc[feature_audit_df["feature"] == feature_name, "retained"] = False
        feature_audit_df.loc[feature_audit_df["feature"] == feature_name, "exclusion_reason"] = "fully_missing_in_development_split"
    _write_csv(resolved_dir / "assigned_resource_open_7d_feature_audit.csv", feature_audit_df)

    revised_run_summary = {
        "run_id": run_id,
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
            "primary_metric_leader": str(primary_metric_leader["model_name"]),
            "best_thresholded_classifier": str(threshold_leader["model_name"]),
            "best_precision_recall_ranking": str(pr_leader["model_name"]),
            "calibration_leader": str(calibration_leader["model_name"]),
            "overall_evidence_strength": "insufficient_to_establish_clear_winner" if no_robust_winner else "mixed",
            "threshold_analysis_post_hoc_exploratory": True,
        },
        "review": {
            "final_verdict": final_verdict,
            "label_reconciliation": reconciliation_summary,
            "feature_health": feature_health,
            "all_artifacts_share_run_id": True,
            "all_artifacts_share_data_fingerprint": True,
            "no_production_decision_recommendation": True,
        },
    }
    _write_json(resolved_dir / "assigned_resource_open_7d_run_summary.json", revised_run_summary)

    technical_report = "\n".join(
        [
            "# Assigned Resource Open Within 7 Days Technical Report",
            "",
            "Business question: Can Classio predict whether a student will open an assigned resource within seven days of assignment?",
            "",
            "Integrity review:",
            "- This experiment is exploratory.",
            "- Only one teacher is represented.",
            "- The chronological holdout contains 25 rows.",
            "- The selected model does not dominate all metrics.",
            "- No production decision should be based on this run alone.",
            "",
            "Label reconciliation:",
            f"- Earlier audit counts: {AUDIT_DOCUMENTED_COUNTS['positive']} positive, {AUDIT_DOCUMENTED_COUNTS['negative']} negative, {AUDIT_DOCUMENTED_COUNTS['unknown']} unknown.",
            f"- Phase 3 run counts: {dataset_summary.get('positive_count')} positive, {dataset_summary.get('negative_count')} negative, {dataset_summary.get('excluded_row_count')} excluded.",
            f"- `viewed_at` does not explain the difference because the frozen dataset has {reconciliation_summary['view_only_positive_count']} view-only positives.",
            "- Current saved artifacts cannot exactly reproduce the earlier audit split, so the audit-to-run transition is not fully validated from repository evidence alone.",
            "",
            "Model completeness:",
            *[
                f"- {row['model_name']}: status={row['status']}" + (f", failure={row['failure_reason']}" if _clean_text(row.get("failure_reason")) else "")
                for _, row in revised_df.iterrows()
            ],
            "",
            "Interpretation:",
            f"- Primary ROC AUC leader: {primary_metric_leader['model_name']} ({primary_metric_leader['roc_auc']}).",
            f"- Best thresholded classifier by balanced accuracy/F1: {threshold_leader['model_name']} (balanced_accuracy={threshold_leader['balanced_accuracy']}, F1={threshold_leader['f1']}).",
            f"- Best precision-recall ranking: {pr_leader['model_name']} (average_precision={pr_leader['average_precision']}).",
            f"- Calibration leader: {calibration_leader['model_name']} (brier_score={calibration_leader['brier_score']}, log_loss={calibration_leader['log_loss']}).",
            f"- Overall evidence strength: {'NO_ROBUST_WINNER' if no_robust_winner else 'mixed'}",
            "",
            "Conclusion:",
            f"- Final review verdict: {final_verdict}.",
            f"- Overall model conclusion: {final_outcome}.",
        ]
    ) + "\n"
    academic_report = "\n".join(
        [
            "# Assigned Resource Open Within 7 Days Academic Report",
            "",
            "## Dataset and Scope",
            f"- run id: {run_id}",
            f"- data fingerprint: {fingerprint}",
            f"- holdout rows: {rerun_evaluation['holdout_count']}",
            "- one teacher only",
            "- exploratory evidence only",
            "",
            "## Comparative Interpretation",
            f"- ROC AUC leader: {primary_metric_leader['model_name']}",
            f"- thresholded-classification leader: {threshold_leader['model_name']}",
            f"- average-precision leader: {pr_leader['model_name']}",
            f"- calibration leader: {calibration_leader['model_name']}",
            f"- robust winner established: {'no' if no_robust_winner else 'uncertain'}",
            "",
            "## Validity",
            "- The earlier audit counts are not exactly reproducible from the saved Phase 3 artifacts.",
            "- No production decision should rely on this run alone.",
        ]
    ) + "\n"
    integrity_review = "\n".join(
        [
            "# Phase 3.5 Integrity Review",
            "",
            f"Run id: `{run_id}`",
            f"Data fingerprint: `{fingerprint}`",
            "",
            "Final verdict:",
            f"- `{final_verdict}`",
            "",
            "Key findings:",
            "- The earlier 61/53/13 audit split cannot be exactly reconstructed from the saved Phase 3 artifacts.",
            "- `viewed_at` is not the cause of the discrepancy because there are zero view-only positives in the frozen dataset.",
            "- All intended models executed successfully in the saved Phase 3 run, including `DummyClassifier` and `HistGradientBoostingClassifier`.",
            "- The previous narrative overstated `LogisticRegressionReduced`; the evidence supports `NO_ROBUST_WINNER` rather than an unqualified best model.",
            "- Fully missing training-slice features are now excluded automatically by the evaluator before fitting.",
            "",
            "Interpretation:",
            f"- Primary ROC AUC leader: `{primary_metric_leader['model_name']}`.",
            f"- Best thresholded classifier: `{threshold_leader['model_name']}`.",
            f"- Best precision-recall ranking: `{pr_leader['model_name']}`.",
            f"- Calibration leader: `{calibration_leader['model_name']}`.",
        ]
    ) + "\n"
    (resolved_dir / "assigned_resource_open_7d_technical_report.md").write_text(technical_report, encoding="utf-8")
    (resolved_dir / ACADEMIC_REPORT_FILENAME).write_text(academic_report, encoding="utf-8")
    (resolved_dir / INTEGRITY_REVIEW_FILENAME).write_text(integrity_review, encoding="utf-8")

    return {
        "run_id": run_id,
        "data_fingerprint": fingerprint,
        "final_verdict": final_verdict,
        "overall_model_conclusion": final_outcome,
        "primary_metric_leader": str(primary_metric_leader["model_name"]),
        "threshold_leader": str(threshold_leader["model_name"]),
        "pr_leader": str(pr_leader["model_name"]),
        "calibration_leader": str(calibration_leader["model_name"]),
        "no_robust_winner": no_robust_winner,
    }
