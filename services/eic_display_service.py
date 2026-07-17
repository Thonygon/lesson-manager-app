from __future__ import annotations

import re
from typing import Any

from core.i18n import t


COMPONENT_NAME_KEYS = {
    "teacher_recommendation_objective_selector": "admin_eic_component_name_teacher_recommendation_objective_selector",
    "teacher_recommendation_resource_ranker": "admin_eic_component_name_teacher_recommendation_resource_ranker",
    "teacher_material_feed_ranker": "admin_eic_component_name_teacher_material_feed_ranker",
    "student_recommendation_ranker": "admin_eic_component_name_student_recommendation_ranker",
    "student_recommendation_acceptance_blend_model": "admin_eic_component_name_student_recommendation_acceptance_blend_model",
    "explicit_topic_resource_matching": "admin_eic_component_name_explicit_topic_resource_matching",
    "practice_mastery_aggregator": "admin_eic_component_name_practice_mastery_aggregator",
    "review_synchronization_loop": "admin_eic_component_name_review_synchronization_loop",
    "material_reuse_similarity_retriever": "admin_eic_component_name_material_reuse_similarity_retriever",
    "recommendation_event_feedback_loop": "admin_eic_component_name_recommendation_event_feedback_loop",
    "assigned_resource_open_within_7d": "admin_eic_component_name_assigned_resource_open_within_7d",
}

EXPERIMENT_NAME_KEYS = {
    "assigned_resource_open_within_7d": "admin_eic_experiment_name_assigned_resource_open_within_7d",
}

RUN_STATUS_KEYS = {
    "VALIDATED_EXPLORATORY_RUN": "admin_eic_run_status_validated_exploratory_run",
    "VALIDATED_NO_ROBUST_WINNER": "admin_eic_run_status_validated_no_robust_winner",
    "REQUIRES_RERUN": "admin_eic_run_status_requires_rerun",
    "FAILED": "admin_eic_run_status_failed",
    "SUPERSEDED": "admin_eic_run_status_superseded",
    "COMPLETED_PENDING_VALIDATION": "admin_eic_run_status_completed_pending_validation",
    "INELIGIBLE": "admin_eic_run_status_ineligible",
    "INVALID_LABEL_CONSTRUCTION": "admin_eic_run_status_invalid_label_construction",
    "QUEUED": "admin_eic_run_status_queued",
    "RUNNING": "admin_eic_run_status_running",
    "ELIGIBLE": "admin_eic_run_status_eligible",
    "DRAFT": "admin_eic_run_status_draft",
}

INTEGRITY_STATUS_KEYS = {
    "NOT_RUN": "admin_eic_integrity_not_run",
    "RUNNING": "admin_eic_integrity_running",
    "FAILED": "admin_eic_integrity_failed",
    "PASSED": "admin_eic_integrity_passed",
    "REQUIRES_RERUN": "admin_eic_integrity_requires_rerun",
}

MATURITY_KEYS = {
    "EXPLORATORY_ONLY": "admin_eic_maturity_exploratory_only",
    "CANDIDATE_FOR_SHADOW_TESTING": "admin_eic_maturity_candidate_for_shadow_testing",
    "SHADOW_CANDIDATE": "admin_eic_maturity_candidate_for_shadow_testing",
}

EVIDENCE_KEYS = {
    "exploratory": "admin_eic_evidence_exploratory",
    "validated": "admin_eic_evidence_validated",
    "not_available": "admin_eic_evidence_not_available",
    "limited": "admin_eic_evidence_limited",
    "proxy_only": "admin_eic_evidence_proxy_only",
    "feature_source": "admin_eic_evidence_feature_source",
    "direct_observed_data": "admin_eic_evidence_direct_observed_data",
    "validated_evidence_ready": "admin_eic_evidence_validated_evidence_ready",
    "Exploratory evidence": "admin_eic_evidence_exploratory",
}

COMPONENT_TYPE_KEYS = {
    "deterministic_workflow": "admin_eic_type_deterministic_workflow",
    "heuristic_ranker": "admin_eic_type_heuristic_ranker",
    "statistical_estimator": "admin_eic_type_statistical_estimator",
    "supervised_experiment": "admin_eic_type_supervised_experiment",
    "retrieval_system": "admin_eic_type_retrieval_system",
    "hybrid_intelligence": "admin_eic_type_hybrid_intelligence",
}

BUSINESS_ACTION_KEYS = {
    "continue_collecting_data": "admin_eic_action_continue_collecting_data",
    "reevaluate_later": "admin_eic_action_reevaluate_later",
    "maintain_current_logic": "admin_eic_action_maintain_current_logic",
    "improve_exposure_matching": "admin_eic_action_improve_exposure_matching",
    "expand_teacher_coverage": "admin_eic_action_expand_teacher_coverage",
}

STAFF_ROLE_DISPLAY_KEYS = {
    "developer": "admin_staff_role_developer",
    "data_scientist": "admin_staff_role_data_scientist",
}

LEGACY_STATUS_KEYS = {
    "live": "admin_model_reports_status_live",
    "planned": "admin_model_reports_status_planned",
}

REPORT_TYPE_KEYS = {
    "experiment_docx": "admin_eic_report_type_experiment_docx",
    "executive_docx": "admin_eic_report_type_executive_docx",
    "academic_docx": "admin_eic_report_type_academic_docx",
    "technical_docx": "admin_eic_report_type_technical_docx",
}

MODEL_COMPARISON_COLUMN_KEYS = {
    "model_name": "admin_eic_model_table_model_name",
    "model_kind": "admin_eic_model_table_model_kind",
    "status": "admin_eic_model_table_status",
    "failure_reason": "admin_eic_model_table_failure_reason",
    "used_reduced_features": "admin_eic_model_table_used_reduced_features",
    "cv_fold_count": "admin_eic_model_table_cv_fold_count",
    "cv_status": "admin_eic_model_table_cv_status",
    "cv_primary_metric_mean": "admin_eic_model_table_cv_primary_metric_mean",
    "cv_primary_metric_variance": "admin_eic_model_table_cv_primary_metric_variance",
    "train_duration_seconds": "admin_eic_model_table_train_duration_seconds",
    "inference_duration_seconds": "admin_eic_model_table_inference_duration_seconds",
    "holdout_positive_rate": "admin_eic_model_table_holdout_positive_rate",
    "accuracy": "admin_eic_model_table_accuracy",
    "balanced_accuracy": "admin_eic_model_table_balanced_accuracy",
    "precision": "admin_eic_model_table_precision",
    "recall": "admin_eic_model_table_recall",
    "specificity": "admin_eic_model_table_specificity",
    "f1": "admin_eic_model_table_f1",
    "roc_auc": "admin_eic_model_table_roc_auc",
    "average_precision": "admin_eic_model_table_average_precision",
    "log_loss": "admin_eic_model_table_log_loss",
    "brier_score": "admin_eic_model_table_brier_score",
    "predicted_positive_rate": "admin_eic_model_table_predicted_positive_rate",
    "confusion_matrix": "admin_eic_model_table_confusion_matrix",
    "single_class_prediction": "admin_eic_model_table_single_class_prediction",
    "confidence_intervals": "admin_eic_model_table_confidence_intervals",
    "parameters_json": "admin_eic_model_table_parameters_json",
    "dropped_feature_reasons_json": "admin_eic_model_table_dropped_feature_reasons_json",
    "delta_vs_dummy_roc_auc": "admin_eic_model_table_delta_vs_dummy_roc_auc",
    "roc_auc_ci_low": "admin_eic_model_table_roc_auc_ci_low",
    "roc_auc_ci_high": "admin_eic_model_table_roc_auc_ci_high",
    "delta_vs_dummy_average_precision": "admin_eic_model_table_delta_vs_dummy_average_precision",
    "average_precision_ci_low": "admin_eic_model_table_average_precision_ci_low",
    "average_precision_ci_high": "admin_eic_model_table_average_precision_ci_high",
    "delta_vs_dummy_balanced_accuracy": "admin_eic_model_table_delta_vs_dummy_balanced_accuracy",
    "balanced_accuracy_ci_low": "admin_eic_model_table_balanced_accuracy_ci_low",
    "balanced_accuracy_ci_high": "admin_eic_model_table_balanced_accuracy_ci_high",
    "delta_vs_dummy_f1": "admin_eic_model_table_delta_vs_dummy_f1",
    "f1_ci_low": "admin_eic_model_table_f1_ci_low",
    "f1_ci_high": "admin_eic_model_table_f1_ci_high",
    "delta_vs_dummy_brier_score": "admin_eic_model_table_delta_vs_dummy_brier_score",
    "brier_score_ci_low": "admin_eic_model_table_brier_score_ci_low",
    "brier_score_ci_high": "admin_eic_model_table_brier_score_ci_high",
    "delta_vs_dummy_log_loss": "admin_eic_model_table_delta_vs_dummy_log_loss",
    "log_loss_ci_low": "admin_eic_model_table_log_loss_ci_low",
    "log_loss_ci_high": "admin_eic_model_table_log_loss_ci_high",
    "default_threshold": "admin_eic_model_table_default_threshold",
    "best_f1_threshold": "admin_eic_model_table_best_f1_threshold",
    "best_f1": "admin_eic_model_table_best_f1",
    "best_f1_recall": "admin_eic_model_table_best_f1_recall",
    "best_f1_specificity": "admin_eic_model_table_best_f1_specificity",
    "best_balanced_accuracy_threshold": "admin_eic_model_table_best_balanced_accuracy_threshold",
    "best_balanced_accuracy": "admin_eic_model_table_best_balanced_accuracy",
    "best_balanced_recall": "admin_eic_model_table_best_balanced_recall",
    "best_balanced_specificity": "admin_eic_model_table_best_balanced_specificity",
    "overall_interpretation": "admin_eic_model_table_overall_interpretation",
}

MODEL_KIND_KEYS = {
    "baseline_manual": "admin_eic_model_kind_baseline_manual",
    "baseline": "admin_eic_model_kind_baseline",
    "supervised": "admin_eic_model_kind_supervised",
}

MODEL_RESULT_STATUS_KEYS = {
    "success": "admin_eic_model_status_success",
    "failed": "admin_eic_model_status_failed",
    "not_applicable": "admin_eic_model_status_not_applicable",
}

MODEL_NAME_KEYS = {
    "MajorityClassRule": "admin_eic_model_name_majority_class_rule",
    "DummyClassifier": "admin_eic_model_name_dummy_classifier",
    "LogisticRegression": "admin_eic_model_name_logistic_regression",
    "LogisticRegressionReduced": "admin_eic_model_name_logistic_regression_reduced",
    "DecisionTreeClassifier": "admin_eic_model_name_decision_tree_classifier",
    "RandomForestClassifier": "admin_eic_model_name_random_forest_classifier",
    "HistGradientBoostingClassifier": "admin_eic_model_name_hist_gradient_boosting_classifier",
    "SVC": "admin_eic_model_name_svc",
    "KNeighborsClassifier": "admin_eic_model_name_k_neighbors_classifier",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fallback_display(value: str) -> str:
    safe_value = _clean_text(value)
    if not safe_value:
        return ""
    text = re.sub(r"[_\-]+", " ", safe_value).strip()
    text = re.sub(r"\s+", " ", text)
    parts = []
    for part in text.split(" "):
        if part.isupper() and len(part) <= 5:
            parts.append(part)
        else:
            parts.append(part.capitalize())
    return " ".join(parts)


def _translate_key(key: str, lang: str | None = None) -> str:
    translated = t(key, lang=lang)
    return translated if translated != key else ""


def get_component_display_name(component_id: str, lang: str | None = None) -> str:
    safe_id = _clean_text(component_id)
    key = COMPONENT_NAME_KEYS.get(safe_id)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_id)


def get_experiment_display_name(experiment_id: str, lang: str | None = None) -> str:
    safe_id = _clean_text(experiment_id)
    key = EXPERIMENT_NAME_KEYS.get(safe_id)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_id)


def get_run_status_display(status: str, lang: str | None = None) -> str:
    safe_status = _clean_text(status).upper()
    key = RUN_STATUS_KEYS.get(safe_status)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_status)


def get_integrity_status_display(status: str, lang: str | None = None) -> str:
    safe_status = _clean_text(status).upper()
    key = INTEGRITY_STATUS_KEYS.get(safe_status)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_status)


def get_maturity_display(verdict: str, lang: str | None = None) -> str:
    safe_verdict = _clean_text(verdict)
    key = MATURITY_KEYS.get(safe_verdict)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_verdict)


def get_evidence_display(verdict: str, lang: str | None = None) -> str:
    safe_verdict = _clean_text(verdict)
    key = EVIDENCE_KEYS.get(safe_verdict)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_verdict)


def get_component_type_display(component_type: str, lang: str | None = None) -> str:
    safe_type = _clean_text(component_type)
    key = COMPONENT_TYPE_KEYS.get(safe_type)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_type)


def get_business_action_display(action_key: str, lang: str | None = None) -> str:
    safe_action = _clean_text(action_key)
    key = BUSINESS_ACTION_KEYS.get(safe_action)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_action)


def get_staff_role_display(role_key: str, lang: str | None = None) -> str:
    safe_role = _clean_text(role_key)
    key = STAFF_ROLE_DISPLAY_KEYS.get(safe_role)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_role)


def get_legacy_report_status_display(status: str, lang: str | None = None) -> str:
    safe_status = _clean_text(status).lower()
    key = LEGACY_STATUS_KEYS.get(safe_status)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_status)


def get_report_type_display(report_type: str, lang: str | None = None) -> str:
    safe_type = _clean_text(report_type)
    key = REPORT_TYPE_KEYS.get(safe_type)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_type)


def get_model_comparison_column_display(column_name: str, lang: str | None = None) -> str:
    safe_column = _clean_text(column_name)
    key = MODEL_COMPARISON_COLUMN_KEYS.get(safe_column)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_column)


def get_model_name_display(model_name: str, lang: str | None = None) -> str:
    safe_name = _clean_text(model_name)
    key = MODEL_NAME_KEYS.get(safe_name)
    return _translate_key(key, lang=lang) if key else safe_name


def get_model_kind_display(model_kind: str, lang: str | None = None) -> str:
    safe_kind = _clean_text(model_kind).lower()
    key = MODEL_KIND_KEYS.get(safe_kind)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_kind)


def get_model_result_status_display(status: str, lang: str | None = None) -> str:
    safe_status = _clean_text(status).lower()
    key = MODEL_RESULT_STATUS_KEYS.get(safe_status)
    return _translate_key(key, lang=lang) if key else _fallback_display(safe_status)


def get_model_comparison_value_display(column_name: str, value: Any, lang: str | None = None) -> Any:
    safe_column = _clean_text(column_name)
    safe_value = _clean_text(value)
    if not safe_value:
        return "—"
    if safe_column == "model_name":
        return get_model_name_display(safe_value, lang=lang)
    if safe_column == "model_kind":
        return get_model_kind_display(safe_value, lang=lang)
    if safe_column in {"status", "cv_status"}:
        return get_model_result_status_display(safe_value, lang=lang)
    if safe_column in {"used_reduced_features", "single_class_prediction"}:
        normalized = safe_value.lower()
        if normalized in {"true", "1", "yes"}:
            return t("admin_eic_boolean_yes", lang=lang)
        if normalized in {"false", "0", "no"}:
            return t("admin_eic_boolean_no", lang=lang)
    if safe_column == "overall_interpretation":
        return _fallback_display(safe_value)
    return value
