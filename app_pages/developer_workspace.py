from __future__ import annotations

import html as _html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core.i18n import t
from helpers.exposure_telemetry import load_telemetry_health_snapshot
from helpers.report_context_ui import render_report_context_editor
from services import eic_service
from services.authorization_service import (
    CAPABILITY_COMPARE_EXPERIMENT_RUNS,
    CAPABILITY_RERUN_INTEGRITY_REVIEW,
    CAPABILITY_RUN_APPROVED_EXPERIMENTS,
    CAPABILITY_VIEW_AUDIT_LOG,
    CAPABILITY_VIEW_DEVELOPER_WORKSPACE,
    CAPABILITY_VIEW_JOB_DIAGNOSTICS,
    CAPABILITY_VIEW_ML_LAB,
    CAPABILITY_VIEW_TECHNICAL_ARTIFACTS,
    CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS,
    get_authorization_context,
    has_capability,
    require_capability,
)
from services.controlled_jobs_service import list_jobs, mark_stale_jobs
from services.eic_display_service import (
    get_action_type_display,
    get_business_action_display,
    get_evidence_display,
    get_experiment_display_name,
    get_experiment_status_display,
    get_entity_type_display,
    get_integrity_status_display,
    get_job_stage_display,
    get_job_type_display,
    get_model_name_display,
    get_model_comparison_column_display,
    get_model_comparison_value_display,
    get_model_result_status_display,
    get_maturity_display,
    get_run_status_display,
    get_staff_role_display,
)
from services.eic_report_service import get_or_create_validated_report, list_available_eic_reports
from services.ml_experiment_service import (
    APPROVED_EXPERIMENT_ID,
    can_manually_rerun_integrity,
    get_run_artifact_retention_status,
    compute_experiment_eligibility_summary,
    get_environment_readiness,
    get_latest_validated_run_summary,
    get_run_artifact_readiness,
    get_run_state_summary,
    get_run,
    get_workspace_overview,
    launch_experiment,
    list_experiment_catalog,
    list_experiment_runs,
    list_run_artifacts,
    list_run_models,
    mark_stale_experiment_jobs,
    rerun_integrity_review_for_run,
)
from services.privileged_action_service import list_privileged_actions, record_privileged_action


PRODUCT_ROLE_DISPLAY_KEYS = {
    "teacher": "admin_role_value_teacher",
    "student": "admin_role_value_student",
    "school_admin": "admin_role_value_school_admin",
    "admin": "admin_role_value_admin",
}

READINESS_CHECK_NAME_KEYS = {
    "ml_experiments": "developer_workspace_readiness_check_ml_experiments",
    "ml_experiment_runs": "developer_workspace_readiness_check_ml_experiment_runs",
    "ml_run_models": "developer_workspace_readiness_check_ml_run_models",
    "ml_run_artifacts": "developer_workspace_readiness_check_ml_run_artifacts",
    "system_jobs": "developer_workspace_readiness_check_system_jobs",
    "user_staff_roles": "developer_workspace_readiness_check_user_staff_roles",
    "artifact_filesystem": "developer_workspace_readiness_check_artifact_filesystem",
    "numpy": "developer_workspace_readiness_check_numpy",
    "pandas": "developer_workspace_readiness_check_pandas",
    "scipy": "developer_workspace_readiness_check_scipy",
    "scikit-learn": "developer_workspace_readiness_check_scikit_learn",
    "job runner": "developer_workspace_readiness_check_job_runner",
    "evaluator import": "developer_workspace_readiness_check_evaluator_import",
    "integrity review import": "developer_workspace_readiness_check_integrity_import",
}

ARTIFACT_TYPE_DISPLAY_KEYS = {
    "findings_interpretation_report": "developer_workspace_artifact_findings_interpretation_report",
}


def _yes_no(value: bool) -> str:
    return t("admin_eic_boolean_yes") if bool(value) else t("admin_eic_boolean_no")


def _product_role_display(role: str) -> str:
    safe_role = " ".join(str(role or "").split()).strip().lower()
    key = PRODUCT_ROLE_DISPLAY_KEYS.get(safe_role)
    return t(key) if key else safe_role


def _artifact_type_display(artifact_type: str) -> str:
    safe_type = " ".join(str(artifact_type or "").split()).strip()
    key = ARTIFACT_TYPE_DISPLAY_KEYS.get(safe_type)
    if key:
        translated = t(key)
        if translated != key:
            return translated
    normalized = safe_type.replace("_md", "").replace("_json", "").replace("_csv", "")
    normalized = normalized.replace("_report", " report").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in normalized.split()) if normalized else t("developer_workspace_artifact_fallback")


def _translate_workspace_warning(message: str) -> str:
    safe = " ".join(str(message or "").split()).strip()
    known = {
        "Historical run ca935f4e5587 remains superseded and not final.": t("developer_workspace_warning_historical_run_superseded"),
        "Only one teacher is represented in the current mature label set.": t("developer_workspace_warning_single_teacher"),
        "Only one recommendation surface is represented in the current mature label set.": t("developer_workspace_warning_single_recommendation_surface"),
        "Very few students are represented in the current mature recommendation labels.": t("developer_workspace_warning_few_recommendation_students"),
        "Telemetry has unmatched opens in the recent window.": t("developer_workspace_warning_unmatched_opens"),
        "Telemetry diagnostics were unavailable during the eligibility check.": t("developer_workspace_warning_telemetry_unavailable"),
    }
    return known.get(safe, safe)


def _translate_lab_issue(message: str) -> str:
    safe = " ".join(str(message or "").split()).strip()
    known = {
        "Fewer than 10 positive mature labels are available.": t("developer_workspace_lab_blocking_positive_labels"),
        "Fewer than 10 negative mature labels are available.": t("developer_workspace_lab_blocking_negative_labels"),
        "Fewer than 50 mature labels are available.": t("developer_workspace_lab_blocking_total_labels"),
    }
    if safe.startswith("Fully missing historical features:"):
        features = safe.split(":", 1)[1].strip() if ":" in safe else ""
        return t("developer_workspace_warning_fully_missing_features", value=features)
    return known.get(safe, safe)


def _translate_retention_reason(reason: str) -> str:
    safe = " ".join(str(reason or "").split()).strip()
    known = {
        "Current validated run artifacts are always protected.": t("developer_workspace_retention_current_validated"),
        "Artifacts are kept while the run is active, pending validation, or currently validated.": t("developer_workspace_retention_active_or_pending"),
        "Artifacts are retained until the configured cleanup window expires.": t("developer_workspace_retention_temporary"),
        "Artifacts are eligible for cleanup under the retention policy.": t("developer_workspace_retention_cleanup_eligible"),
        "No automatic cleanup rule applies to this run.": t("developer_workspace_retention_no_cleanup_rule"),
    }
    return known.get(safe, safe)


def _translate_run_state_message(message: str) -> str:
    safe = " ".join(str(message or "").split()).strip()
    known = {
        "Waiting to start. No evaluation artifacts exist yet.": t("developer_workspace_state_waiting_to_start"),
        "Models are being evaluated. Integrity review will start after completion.": t("developer_workspace_state_models_running"),
        "Evaluation completed. Integrity validation is ready.": t("developer_workspace_state_validation_ready"),
        "This run passed integrity checks and may feed business and academic reports.": t("developer_workspace_state_validated_ready_for_reports"),
        "The evaluation failed before producing a validated result.": t("developer_workspace_state_evaluation_failed"),
        "Artifacts exist, but the review requires a new evaluation before this run can be trusted.": t("developer_workspace_state_requires_new_evaluation"),
        "Integrity review found invalid label construction.": t("developer_workspace_state_invalid_label_construction"),
        "This historical run has been superseded and is read-only.": t("developer_workspace_state_superseded_read_only"),
        "Run status is not yet fully classified.": t("developer_workspace_state_unclassified"),
        "Artifacts are readable.": t("developer_workspace_next_action_artifacts_readable"),
        "Launch a new evaluation.": t("developer_workspace_next_action_launch_new_evaluation"),
        "Fix implementation and launch a new evaluation.": t("developer_workspace_next_action_fix_and_launch"),
        "Review artifacts only.": t("developer_workspace_next_action_review_only"),
        "Refresh this view.": t("developer_workspace_next_action_refresh_view"),
    }
    return known.get(safe, safe)


def _translate_readiness_message(message: str) -> str:
    safe = " ".join(str(message or "").split()).strip()
    known = {
        "Evaluation artifacts are ready.": t("developer_workspace_readiness_message_ready"),
        "Evaluation is still queued.": t("developer_workspace_readiness_message_queued"),
        "Evaluation is currently running.": t("developer_workspace_readiness_message_running"),
        "Evaluation failed; launch a new run.": t("developer_workspace_readiness_message_failed"),
        "This historical run is superseded.": t("developer_workspace_readiness_message_superseded"),
        "Protected artifacts for this run are missing. Regenerate or restore the evidence package.": t("developer_workspace_readiness_message_protected_missing"),
        "Local artifacts for this run have expired under the retention policy.": t("developer_workspace_readiness_message_expired"),
        "Required evaluation artifacts are missing.": t("developer_workspace_readiness_message_missing"),
        "All required registry and job tables are available.": t("developer_workspace_readiness_message_tables_ready"),
        "One or more required tables are missing.": t("developer_workspace_readiness_message_tables_missing"),
        "Run artifact directory is writable.": t("developer_workspace_readiness_message_artifact_writable"),
        "Run artifact directory is not writable.": t("developer_workspace_readiness_message_artifact_not_writable"),
        "All required ML dependencies are available.": t("developer_workspace_readiness_message_dependencies_ready"),
        "One or more ML dependencies are unavailable.": t("developer_workspace_readiness_message_dependencies_missing"),
        "Synchronous execution is enabled in the current runtime.": t("developer_workspace_readiness_message_synchronous_runtime"),
        "All blocking conditions are resolved.": t("developer_workspace_readiness_message_blockers_resolved"),
        "Launch is blocked until the listed conditions are resolved.": t("developer_workspace_readiness_message_launch_blocked"),
    }
    return known.get(safe, safe)


def _translate_readiness_check_name(name: str) -> str:
    safe_name = " ".join(str(name or "").split()).strip()
    key = READINESS_CHECK_NAME_KEYS.get(safe_name)
    translated = t(key) if key else ""
    return translated if translated and translated != key else safe_name


def _translate_readiness_check_detail(check: dict) -> list[str]:
    ready = bool(check.get("ready"))
    name = _translate_readiness_check_name(str(check.get("name") or ""))
    message = " ".join(str(check.get("message") or "").split()).strip()
    error = " ".join(str(check.get("error") or "").split()).strip()
    action = " ".join(str(check.get("recommended_action") or "").split()).strip()
    icon = "✓" if ready else "✗"
    details = [f"{icon} {name}"]
    if not ready and error:
        details.append(t("developer_workspace_readiness_check_error", value=error))
    if action and not ready:
        details.append(t("developer_workspace_readiness_check_action", value=action))
    elif message and not ready:
        details.append(t("developer_workspace_readiness_check_note", value=message))
    elif message and ready and "ready" not in message.lower() and "available" not in message.lower():
        details.append(t("developer_workspace_readiness_check_note", value=message))
    return details


def _report_status_display(status: str) -> str:
    safe = " ".join(str(status or "").split()).strip().lower() or "not_available"
    return t(f"admin_eic_report_state_{safe}")


def _card(label: str, value: str, help_text: str = "") -> str:
    safe_label = _html.escape(label)
    safe_value = _html.escape(value)
    safe_help = _html.escape(help_text)
    subtitle = f"<div class='dev-card-help'>{safe_help}</div>" if safe_help else ""
    return (
        "<div class='dev-card'>"
        f"<div class='dev-card-label'>{safe_label}</div>"
        f"<div class='dev-card-value'>{safe_value}</div>"
        f"{subtitle}"
        "</div>"
    )


def _render_clickable_readiness_card(
    label: str,
    value: str,
    help_text: str,
    *,
    details: list[str] | None = None,
    expander_key: str,
) -> None:
    with st.expander(f"{label} • {value}", expanded=False):
        st.markdown(_card(label, value, help_text), unsafe_allow_html=True)
        for detail in details or []:
            st.caption(detail)


def _render_readiness_card(label: str, payload: dict, *, writable_label: bool = False) -> None:
    value = t("developer_workspace_state_ready") if bool(payload.get("ready")) else t("developer_workspace_state_not_ready")
    if writable_label:
        value = t("developer_workspace_state_writable") if bool(payload.get("ready")) else t("developer_workspace_state_not_writable")
    checks = payload.get("checks") or []
    details: list[str] = []
    for check in checks:
        details.extend(_translate_readiness_check_detail(check))
    _render_clickable_readiness_card(
        label,
        value,
        _translate_readiness_message(str(payload.get("message") or "")),
        details=details,
        expander_key=f"dev_readiness_{label.lower().replace(' ', '_')}",
    )


def _render_launcher_card(payload: dict) -> None:
    value = t("developer_workspace_state_ready") if bool(payload.get("ready")) else t("developer_workspace_state_not_ready")
    details: list[str] = []
    blocking = payload.get("blocking_reasons") or []
    if blocking:
        details.append(t("developer_workspace_lab_blocking_reasons_prefix"))
        for reason in blocking:
            details.append(f"• {reason}")
    actions = payload.get("recommended_actions") or []
    if actions:
        details.append(t("developer_workspace_recommended_action_label"))
        for action in actions:
            details.append(f"• {action}")
    _render_clickable_readiness_card(
        t("developer_workspace_readiness_experiment_launcher"),
        value,
        str(payload.get("message") or ""),
        details=details,
        expander_key="dev_readiness_experiment_launcher",
    )


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .dev-hero{
            border-radius:24px;padding:24px 26px;margin-bottom:1rem;
            background:
              radial-gradient(circle at top right, rgba(14,165,233,.18), transparent 34%),
              radial-gradient(circle at bottom left, rgba(16,185,129,.14), transparent 34%),
              linear-gradient(135deg, color-mix(in srgb, var(--panel) 95%, white 5%), color-mix(in srgb, var(--panel-soft) 88%, var(--primary) 12%));
            border:1px solid color-mix(in srgb, var(--border) 78%, var(--primary) 22%);
            box-shadow:0 18px 42px rgba(15,23,42,.08);
        }
        .dev-title{font-size:1.55rem;font-weight:950;color:var(--text);letter-spacing:-.02em;}
        .dev-subtitle{margin-top:.45rem;color:var(--muted);max-width:940px;line-height:1.5;}
        .dev-chip-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;}
        .dev-chip{display:inline-flex;align-items:center;border-radius:999px;padding:6px 11px;font-size:.74rem;font-weight:800;background:var(--panel);border:1px solid var(--border);}
        .dev-card{
            padding:14px 16px;border-radius:18px;min-height:92px;margin-bottom:14px;
            background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), color-mix(in srgb, var(--panel-soft) 94%, var(--primary) 6%));
            border:1px solid var(--border);box-shadow:0 10px 24px rgba(15,23,42,.05);
        }
        .dev-card-label{font-size:.78rem;font-weight:900;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}
        .dev-card-value{margin-top:8px;font-size:1.15rem;font-weight:900;color:var(--text);}
        .dev-card-help{margin-top:6px;font-size:.82rem;color:var(--muted);line-height:1.45;}
        .dev-expander-gap{margin-top:14px;}
        .stDownloadButton button, .stButton button {
            text-align:left !important;
            justify-content:flex-start !important;
        }
        [data-testid="stExpander"]{
            border:1px solid var(--border);
            border-radius:18px;
            background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), color-mix(in srgb, var(--panel-soft) 94%, var(--primary) 6%));
            overflow:hidden;
            margin-bottom:14px;
        }
        [data-testid="stExpander"] details summary{
            padding:12px 16px;
            font-weight:900;
            color:var(--text);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _artifact_button_label(artifact: dict) -> str:
    artifact_type = _artifact_type_display(str(artifact.get("artifact_type") or ""))
    artifact_path = Path(str(artifact.get("storage_path") or ""))
    if artifact_path.name:
        return f"{artifact_type} ({artifact_path.name})"
    return artifact_type or t("developer_workspace_artifact_fallback")


def _developer_table_column_label(column_name: str) -> str:
    labels = {
        "id": t("developer_workspace_table_id"),
        "run_id": t("developer_workspace_table_run_id"),
        "job_id": t("developer_workspace_table_job_id"),
        "action_id": t("developer_workspace_table_action_id"),
        "model_name": t("developer_workspace_table_model_name"),
        "experiment_id": t("developer_workspace_table_experiment_id"),
        "job_type": t("developer_workspace_table_job_type"),
        "job_version": t("developer_workspace_table_job_version"),
        "job_status": t("developer_workspace_table_job_status"),
        "priority": t("developer_workspace_table_priority"),
        "requested_by": t("developer_workspace_table_requested_by"),
        "requested_by_role": t("developer_workspace_table_requested_by_role"),
        "requested_at": t("developer_workspace_table_requested_at"),
        "started_at": t("developer_workspace_table_started_at"),
        "finished_at": t("developer_workspace_table_finished_at"),
        "completed_at": t("developer_workspace_table_completed_at"),
        "heartbeat_at": t("developer_workspace_table_heartbeat_at"),
        "progress_pct": t("developer_workspace_table_progress_pct"),
        "current_stage": t("developer_workspace_table_current_stage"),
        "created_at": t("developer_workspace_table_created_at"),
        "updated_at": t("developer_workspace_table_updated_at"),
        "triggered_by": t("developer_workspace_table_triggered_by"),
        "actor_roles": t("developer_workspace_table_actor_roles"),
        "action_type": t("developer_workspace_table_action_type"),
        "actor_user_id": t("developer_workspace_table_actor_user_id"),
        "target_run_id": t("developer_workspace_table_target_run_id"),
        "entity_type": t("developer_workspace_table_entity_type"),
        "entity_id": t("developer_workspace_table_entity_id"),
        "before_json": t("developer_workspace_table_before_json"),
        "after_json": t("developer_workspace_table_after_json"),
        "reason": t("developer_workspace_table_reason"),
        "details_json": t("developer_workspace_table_details"),
        "execution_status": t("developer_workspace_table_execution_status"),
        "parameters_json": t("developer_workspace_table_parameters"),
        "cv_metrics_json": t("developer_workspace_table_cv_metrics"),
        "holdout_metrics_json": t("developer_workspace_table_holdout_metrics"),
        "confidence_intervals_json": t("developer_workspace_table_confidence_intervals"),
        "confusion_matrix_json": t("developer_workspace_table_confusion_matrix"),
        "predicted_positive_rate": t("developer_workspace_table_predicted_positive_rate"),
        "train_duration_ms": t("developer_workspace_table_train_duration_ms"),
        "inference_duration_ms": t("developer_workspace_table_inference_duration_ms"),
        "failure_message": t("developer_workspace_table_failure_message"),
        "exposure_type": t("developer_workspace_table_exposure_type"),
        "surface": t("developer_workspace_table_surface"),
        "exposures": t("developer_workspace_table_exposures"),
        "matched_opens": t("developer_workspace_table_matched_opens"),
        "unmatched_opens": t("developer_workspace_table_unmatched_opens"),
        "open_rate": t("developer_workspace_table_open_rate"),
        "downstream_outcome_rate": t("developer_workspace_table_downstream_outcome_rate"),
        "duplicate_warnings": t("developer_workspace_table_duplicate_warnings"),
        "date_start": t("developer_workspace_table_date_start"),
        "date_end": t("developer_workspace_table_date_end"),
        "status": t("developer_workspace_table_status"),
        "mature_exposures": t("developer_workspace_table_mature_exposures"),
    }
    return labels.get(column_name, " ".join(part.capitalize() for part in str(column_name).split("_")))


def _humanize_identifier(value: object) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return "—"
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(part.upper() if part.isupper() and len(part) <= 4 else part.capitalize() for part in text.split())


def _developer_table_value(column_name: str, value: object) -> object:
    if value in (None, ""):
        return "—"
    if column_name == "actor_roles" and isinstance(value, list):
        return ", ".join(_product_role_display(str(item)) for item in value if str(item).strip()) or "—"
    if isinstance(value, (dict, list)):
        try:
            if column_name in {"before_json", "after_json"}:
                return json.dumps(value, ensure_ascii=True, sort_keys=True)
        except Exception:
            return str(value)
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    if column_name == "model_name":
        return get_model_name_display(str(value))
    if column_name == "experiment_id":
        return get_experiment_display_name(str(value))
    if column_name in {"run_status"}:
        return get_run_status_display(str(value))
    if column_name in {"integrity_status"}:
        return get_integrity_status_display(str(value))
    if column_name in {"maturity_verdict"}:
        return get_maturity_display(str(value))
    if column_name in {"execution_status", "status", "job_status"}:
        return get_model_result_status_display(str(value))
    if column_name == "job_type":
        return get_job_type_display(str(value))
    if column_name == "current_stage":
        return get_job_stage_display(str(value))
    if column_name == "action_type":
        return get_action_type_display(str(value))
    if column_name == "entity_type":
        return get_entity_type_display(str(value))
    if column_name == "requested_by_role":
        return _product_role_display(str(value))
    if column_name in {"surface", "exposure_type"}:
        return _humanize_identifier(value)
    if column_name in {"failure_message", "reason"} and str(value).lower() == "nan":
        return "—"
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=True, sort_keys=True)
        except Exception:
            return str(value)
    return value


def _present_developer_table(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column_name in list(frame.columns):
        frame[column_name] = frame[column_name].apply(lambda value, name=column_name: _developer_table_value(name, value))
    return frame.rename(columns={column_name: _developer_table_column_label(column_name) for column_name in frame.columns})


def _selected_experiment(catalog: list[dict], *, state_key: str) -> dict:
    if not catalog:
        return {}
    option_ids = [str(row.get("experiment_id") or "") for row in catalog]
    current = str(st.session_state.get(state_key) or option_ids[0])
    if current not in option_ids:
        current = option_ids[0]
    selected_id = st.selectbox(
        t("developer_workspace_experiment_label"),
        option_ids,
        index=option_ids.index(current),
        format_func=lambda value: next((get_experiment_display_name(str(row.get("experiment_id") or value)) for row in catalog if str(row.get("experiment_id") or "") == value), get_experiment_display_name(value)),
        key=state_key,
    )
    return next((row for row in catalog if str(row.get("experiment_id") or "") == selected_id), {})


def _render_protected_artifacts(artifact_rows: list[dict], *, key_prefix: str) -> None:
    if not artifact_rows:
        return
    st.markdown("<div class='dev-expander-gap'></div>", unsafe_allow_html=True)
    with st.expander(t("developer_workspace_protected_artifacts_title"), expanded=False):
        st.caption(t("developer_workspace_protected_artifacts_caption"))
        for artifact in artifact_rows:
            artifact_path = Path(str(artifact.get("storage_path") or ""))
            label = _artifact_button_label(artifact)
            artifact_key = f"{key_prefix}_{artifact.get('artifact_type')}"
            if artifact_path.exists() and has_capability(CAPABILITY_VIEW_TECHNICAL_ARTIFACTS):
                st.download_button(
                    label,
                    data=artifact_path.read_bytes(),
                    file_name=artifact_path.name,
                    mime=str(artifact.get("content_type") or "application/octet-stream"),
                    use_container_width=True,
                    key=f"download_{artifact_key}",
                )
            else:
                st.button(label, disabled=True, use_container_width=True, key=f"disabled_{artifact_key}")


def _render_overview() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE)
    overview = get_workspace_overview(cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    catalog = overview.get("experiment_catalog") or []
    latest_validated = overview.get("latest_validated_run") or {}
    latest_attempted = overview.get("latest_attempted_experiment") or {}
    latest_successful = overview.get("latest_successful_experiment") or {}
    telemetry = overview.get("telemetry_status") or {}
    latest_successful_status = get_run_status_display(str(latest_successful.get("run_status") or "")) if latest_successful.get("run_status") else t("developer_workspace_no_completed_run")
    latest_attempted_status = get_run_status_display(str(latest_attempted.get("run_status") or "")) if latest_attempted.get("run_status") else t("developer_workspace_no_run_yet")
    cards = [
        (t("developer_workspace_overview_environment"), str(overview.get("environment") or t("admin_eic_status_not_available")), t("developer_workspace_overview_environment_help")),
        (t("developer_workspace_overview_code_version"), str(overview.get("code_version") or t("admin_eic_status_not_available")), t("developer_workspace_overview_code_version_help")),
        (t("developer_workspace_overview_latest_successful"), str(latest_successful.get("run_id") or t("admin_eic_value_none")), latest_successful_status),
        (t("developer_workspace_overview_latest_attempted"), str(latest_attempted.get("run_id") or t("admin_eic_value_none")), latest_attempted_status),
        (t("developer_workspace_overview_latest_validated"), str(latest_validated.get("run_id") or t("developer_workspace_no_validated_run")), get_run_status_display(str(latest_validated.get("run_status") or ""))),
        (t("developer_workspace_overview_active_jobs"), str(len(overview.get("active_jobs") or [])), t("developer_workspace_overview_active_jobs_help")),
        (t("developer_workspace_overview_failed_jobs"), str(len(overview.get("failed_jobs") or [])), t("developer_workspace_overview_failed_jobs_help")),
        (t("developer_workspace_overview_telemetry_coverage"), f"{float(telemetry.get('outcome_coverage') or 0.0):.1%}", t("developer_workspace_overview_telemetry_coverage_help")),
    ]
    cols = st.columns(4, gap="small")
    for idx, (label, value, help_text) in enumerate(cards):
        with cols[idx % 4]:
            st.markdown(_card(label, value, help_text), unsafe_allow_html=True)

    if catalog:
        st.markdown(f"#### {t('developer_workspace_overview_catalog_title')}")
        catalog_df = pd.DataFrame(
            [
                {
                    t("developer_workspace_catalog_experiment"): get_experiment_display_name(str(row.get("experiment_id") or "")),
                    t("developer_workspace_catalog_status"): get_experiment_status_display(str(row.get("status") or "")),
                    t("developer_workspace_catalog_runs"): int(row.get("run_count") or 0),
                    t("developer_workspace_catalog_validated_runs"): int(row.get("validated_run_count") or 0),
                    t("developer_workspace_catalog_latest_run"): str((row.get("latest_run") or {}).get("run_id") or t("admin_eic_value_none")),
                    t("developer_workspace_catalog_latest_status"): get_run_status_display(str((row.get("latest_run") or {}).get("run_status") or "not_available")),
                }
                for row in catalog
            ]
        )
        st.dataframe(catalog_df, use_container_width=True, hide_index=True)

    warnings = [warning for warning in (overview.get("warnings") or []) if str(warning).strip()]
    if warnings:
        st.markdown(f"#### {t('developer_workspace_warnings_title')}")
        for warning in warnings:
            st.warning(_translate_workspace_warning(str(warning)))

    env = overview.get("environment_readiness") or get_environment_readiness()
    st.markdown(f"#### {t('developer_workspace_readiness_title')}")
    env_cols = st.columns(5, gap="small")
    with env_cols[0]:
        _render_readiness_card(t("developer_workspace_readiness_database_migration"), env.get("database_migration") or {})
    with env_cols[1]:
        _render_readiness_card(t("developer_workspace_readiness_artifact_filesystem"), env.get("artifact_filesystem") or {}, writable_label=True)
    with env_cols[2]:
        _render_readiness_card(t("developer_workspace_readiness_ml_dependencies"), env.get("ml_dependencies") or {})
    with env_cols[3]:
        execution_mode = env.get("execution_mode") or {}
        mode_value = str(execution_mode.get("mode") or "unknown")
        _render_clickable_readiness_card(
            t("developer_workspace_readiness_execution_mode"),
            t("developer_workspace_execution_mode_synchronous") if mode_value == "synchronous" else _humanize_identifier(mode_value),
            _translate_readiness_message(str(execution_mode.get("message") or "")),
            details=[
                t("developer_workspace_readiness_worker_available", value=_yes_no(bool(execution_mode.get("worker_available")))),
                t("developer_workspace_readiness_synchronous_enabled", value=_yes_no(bool(execution_mode.get("synchronous_enabled")))),
            ],
            expander_key="dev_readiness_execution_mode",
        )
    with env_cols[4]:
        _render_launcher_card(env.get("experiment_launcher") or {})


def _render_ml_lab() -> None:
    require_capability(CAPABILITY_VIEW_ML_LAB)
    catalog = list_experiment_catalog(cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    selected_experiment = _selected_experiment(catalog, state_key="developer_workspace_lab_experiment_id")
    selected_experiment_id = str(selected_experiment.get("experiment_id") or APPROVED_EXPERIMENT_ID)
    eligibility = compute_experiment_eligibility_summary(selected_experiment_id)
    top = st.columns(4, gap="small")
    cards = [
        (t("developer_workspace_lab_experiment"), get_experiment_display_name(selected_experiment_id)),
        (t("developer_workspace_lab_eligible"), _yes_no(bool(eligibility.get("eligible")))),
        (t("developer_workspace_lab_mature_labels"), str(int((eligibility.get("data_summary") or {}).get("mature_labels") or 0))),
        (t("developer_workspace_lab_expected_ceiling"), get_maturity_display(str(eligibility.get("expected_maturity_ceiling") or "unknown"))),
    ]
    for col, (label, value) in zip(top, cards):
        with col:
            st.markdown(_card(label, value), unsafe_allow_html=True)
    if not bool(eligibility.get("supported")):
        st.info(str(eligibility.get("message") or t("developer_workspace_lab_not_fully_wired")))
    if eligibility.get("blocking_reasons"):
        st.error(
            t("developer_workspace_lab_blocking_reasons_prefix")
            + " "
            + " | ".join(_translate_lab_issue(str(reason)) for reason in (eligibility.get("blocking_reasons") or []))
        )
    if eligibility.get("warnings"):
        for warning in eligibility.get("warnings") or []:
            st.warning(_translate_lab_issue(_translate_workspace_warning(str(warning))))

    st.caption(
        t("developer_workspace_lab_approved_models")
    )
    env = get_environment_readiness()
    launcher_ready = bool(((env.get("experiment_launcher") or {}).get("ready")))
    action_cols = st.columns([1.1, 1, 1.2], gap="medium")
    with action_cols[0]:
        if has_capability(CAPABILITY_RUN_APPROVED_EXPERIMENTS):
            if st.button(t("developer_workspace_lab_launch_evaluation"), key="launch_approved_eval", use_container_width=True, disabled=not launcher_ready or not bool(selected_experiment.get("launch_supported"))):
                ok, payload, message = launch_experiment(selected_experiment_id)
                if ok:
                    st.success(message)
                    st.session_state["developer_workspace_selected_run_id"] = str(payload.get("run_id") or "")
                    st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
                    st.rerun()
                else:
                    st.error(message)
            if not launcher_ready:
                st.caption(t("developer_workspace_lab_launch_disabled"))
            elif not bool(selected_experiment.get("launch_supported")):
                st.caption(t("developer_workspace_lab_launch_unwired"))
    with action_cols[1]:
        if st.button(t("developer_workspace_lab_refresh_runs"), key="refresh_runs", use_container_width=True):
            st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
            st.rerun()
    with action_cols[2]:
        if st.button(t("developer_workspace_lab_mark_stale_jobs"), key="mark_stale_jobs", use_container_width=True):
            count = mark_stale_experiment_jobs()
            st.info(t("developer_workspace_lab_marked_stale_jobs", count=count))

    runs = list_experiment_runs(experiment_id=selected_experiment_id, limit=25, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if runs:
        st.markdown(f"#### {t('developer_workspace_lab_run_registry')}")
        run_df = pd.DataFrame(runs)
        visible_columns = [col for col in [
            "run_id",
            "run_status",
            "integrity_status",
            "maturity_verdict",
            "included_row_count",
            "positive_label_count",
            "negative_label_count",
            "teachers_represented",
            "created_at",
            "is_current_validated_run",
        ] if col in run_df.columns]
        registry_df = run_df[visible_columns].copy()
        if "run_status" in registry_df.columns:
            registry_df["run_status"] = registry_df["run_status"].astype(str).map(get_run_status_display)
        if "integrity_status" in registry_df.columns:
            registry_df["integrity_status"] = registry_df["integrity_status"].astype(str).map(get_integrity_status_display)
        if "maturity_verdict" in registry_df.columns:
            registry_df["maturity_verdict"] = registry_df["maturity_verdict"].astype(str).map(get_maturity_display)
        if "is_current_validated_run" in registry_df.columns:
            registry_df["is_current_validated_run"] = registry_df["is_current_validated_run"].map(_yes_no)
        registry_df = registry_df.rename(
            columns={
                "run_id": t("developer_workspace_registry_run_id"),
                "run_status": t("developer_workspace_registry_run_status"),
                "integrity_status": t("developer_workspace_registry_integrity"),
                "maturity_verdict": t("developer_workspace_registry_maturity"),
                "included_row_count": t("developer_workspace_registry_included_rows"),
                "positive_label_count": t("developer_workspace_registry_positive_labels"),
                "negative_label_count": t("developer_workspace_registry_negative_labels"),
                "teachers_represented": t("developer_workspace_registry_teachers_represented"),
                "created_at": t("developer_workspace_registry_created_at"),
                "is_current_validated_run": t("developer_workspace_registry_current_validated"),
            }
        )
        st.dataframe(registry_df, use_container_width=True, hide_index=True)
        selected_run_id = st.selectbox(
            t("developer_workspace_lab_run_detail"),
            [str(row.get("run_id") or "") for row in runs],
            index=0,
            key="developer_workspace_selected_run_id",
        )
        selected_run = get_run(selected_run_id)
        if selected_run:
            state_summary = get_run_state_summary(selected_run_id)
            readiness = get_run_artifact_readiness(selected_run_id)
            retention = get_run_artifact_retention_status(selected_run_id)
            detail_cols = st.columns(4, gap="small")
            detail_cards = [
                (t("developer_workspace_detail_run_status"), get_run_status_display(str(state_summary.get("run_status") or ""))),
                (t("developer_workspace_detail_integrity"), get_integrity_status_display(str(selected_run.get("integrity_status") or ""))),
                (t("developer_workspace_detail_artifacts_ready"), _yes_no(readiness.ready)),
                (t("developer_workspace_detail_current_validated"), _yes_no(bool(selected_run.get("is_current_validated_run")))),
            ]
            for col, (label, value) in zip(detail_cols, detail_cards):
                with col:
                    st.markdown(_card(label, value), unsafe_allow_html=True)
            st.caption(_translate_run_state_message(str(state_summary.get("current_message") or "")))
            st.caption(t("developer_workspace_detail_next_action", value=_translate_run_state_message(str(state_summary.get("next_action") or t("developer_workspace_refresh_action")))))
            st.caption(t("developer_workspace_detail_artifact_retention", value=_translate_retention_reason(retention.reason)))
            if state_summary.get("failure_message"):
                st.error(str(state_summary.get("failure_message")))
            if readiness.missing_artifact_types:
                st.warning(t("developer_workspace_detail_missing_artifacts_prefix") + " " + ", ".join(_artifact_type_display(item) for item in readiness.missing_artifact_types))
            model_rows = list_run_models(selected_run_id)
            if model_rows:
                st.markdown(f"##### {t('developer_workspace_model_results_title')}")
                st.dataframe(_present_developer_table(model_rows), use_container_width=True, hide_index=True)
            compare_rows = runs[:2]
            if has_capability(CAPABILITY_COMPARE_EXPERIMENT_RUNS) and len(compare_rows) >= 2:
                st.markdown(f"##### {t('developer_workspace_run_comparison_title')}")
                comparison_df = pd.DataFrame(compare_rows)[
                    [col for col in ["run_id", "run_status", "integrity_status", "included_row_count", "positive_label_count", "negative_label_count", "primary_metric_leader"] if col in pd.DataFrame(compare_rows).columns]
                ].copy()
                if "run_status" in comparison_df.columns:
                    comparison_df["run_status"] = comparison_df["run_status"].astype(str).map(get_run_status_display)
                if "integrity_status" in comparison_df.columns:
                    comparison_df["integrity_status"] = comparison_df["integrity_status"].astype(str).map(get_integrity_status_display)
                comparison_df = comparison_df.rename(
                    columns={
                        "run_id": t("developer_workspace_registry_run_id"),
                        "run_status": t("developer_workspace_registry_run_status"),
                        "integrity_status": t("developer_workspace_registry_integrity"),
                        "included_row_count": t("developer_workspace_registry_included_rows"),
                        "positive_label_count": t("developer_workspace_registry_positive_labels"),
                        "negative_label_count": t("developer_workspace_registry_negative_labels"),
                        "primary_metric_leader": t("developer_workspace_registry_primary_metric_leader"),
                    }
                )
                st.dataframe(comparison_df, use_container_width=True, hide_index=True)
            if has_capability(CAPABILITY_RERUN_INTEGRITY_REVIEW):
                allowed, explanation = can_manually_rerun_integrity(selected_run_id)
                if allowed:
                    if st.button(t("developer_workspace_lab_rerun_integrity"), key=f"rerun_integrity_{selected_run_id}", use_container_width=False):
                        ok, _payload, message = rerun_integrity_review_for_run(selected_run_id)
                        if ok:
                            st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    st.caption(explanation)
                else:
                    st.caption(explanation)
    else:
        st.info(t("developer_workspace_lab_no_runs"))


def _render_experiment_evidence() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE)
    refresh_nonce = int(st.session_state.get("developer_workspace_refresh_nonce") or 0)
    cache_bust = str(refresh_nonce)
    catalog = list_experiment_catalog(cache_bust=cache_bust)
    selected_experiment = _selected_experiment(catalog, state_key="developer_workspace_evidence_experiment_id")
    selected_experiment_id = str(selected_experiment.get("experiment_id") or APPROVED_EXPERIMENT_ID)
    latest_validated = get_latest_validated_run_summary(experiment_id=selected_experiment_id, cache_bust=cache_bust) or {}
    validated_runs = eic_service.list_validated_experiment_summaries(limit=10, cache_bust=cache_bust, experiment_id=selected_experiment_id)

    st.markdown(f"### {t('developer_workspace_evidence_title')}")
    st.caption(t("developer_workspace_evidence_caption"))

    if latest_validated:
        top_cards = [
            (t("developer_workspace_evidence_current_validated_run"), str(latest_validated.get("run_id") or t("admin_eic_value_none"))),
            (t("developer_workspace_detail_run_status"), get_run_status_display(str(latest_validated.get("run_status") or ""))),
            (t("developer_workspace_detail_integrity"), get_integrity_status_display(str(latest_validated.get("integrity_status") or "not_run"))),
            (t("developer_workspace_evidence_evidence"), get_evidence_display(str(latest_validated.get("evidence_level") or latest_validated.get("evidence_verdict") or "not_available"), lang=str(st.session_state.get("ui_lang") or "en"))),
        ]
        cols = st.columns(4, gap="small")
        for col, (label, value) in zip(cols, top_cards):
            with col:
                st.markdown(_card(label, value), unsafe_allow_html=True)
    else:
        st.info(t("developer_workspace_evidence_none"))

    evidence_tab, registry_tab, reports_tab = st.tabs(
        [t("developer_workspace_evidence_tab_summary"), t("developer_workspace_evidence_tab_registry"), t("developer_workspace_evidence_tab_reports")]
    )

    with evidence_tab:
        if not latest_validated:
            st.info(t("developer_workspace_evidence_requires_validated_run"))
        else:
            run_id = str(latest_validated.get("run_id") or "")
            summary_rows = [
                (t("developer_workspace_summary_experiment"), get_experiment_display_name(str(latest_validated.get("experiment_id") or selected_experiment_id))),
                (t("developer_workspace_summary_dataset_size"), str(int(latest_validated.get("included_row_count") or 0))),
                (t("developer_workspace_summary_positive_labels"), str(int(latest_validated.get("positive_label_count") or 0))),
                (t("developer_workspace_summary_negative_labels"), str(int(latest_validated.get("negative_label_count") or 0))),
                (t("developer_workspace_summary_teachers_represented"), str(int(latest_validated.get("teachers_represented") or 0))),
                (t("developer_workspace_summary_recommended_business_action"), get_business_action_display(str(latest_validated.get("recommended_business_action") or ""))),
            ]
            st.dataframe(pd.DataFrame(summary_rows, columns=[t("admin_field_label"), t("admin_value_label")]), use_container_width=True, hide_index=True)
            business_detail = eic_service.get_experiment_business_detail(run_id, cache_bust=cache_bust)
            model_rows = ((business_detail or {}).get("model_results") or {}).get("models_compared") or []
            if model_rows:
                model_df = pd.DataFrame(model_rows)
                for column_name in list(model_df.columns):
                    model_df[column_name] = model_df[column_name].apply(
                        lambda value, name=column_name: get_model_comparison_value_display(name, value)
                    )
                model_df = model_df.rename(
                    columns={column_name: get_model_comparison_column_display(column_name) for column_name in model_df.columns}
                )
                st.markdown(f"#### {t('developer_workspace_model_comparison_title')}")
                st.dataframe(model_df, use_container_width=True, hide_index=True)

    with registry_tab:
        if validated_runs:
            registry_df = pd.DataFrame(
                [
                    {
                        t("developer_workspace_registry_run_id"): str(row.get("run_id") or ""),
                        t("developer_workspace_catalog_experiment"): get_experiment_display_name(str(row.get("experiment_id") or selected_experiment_id)),
                        t("developer_workspace_registry_run_status"): get_run_status_display(str(row.get("run_status") or "")),
                        t("developer_workspace_registry_integrity"): get_integrity_status_display(str(row.get("integrity_status") or "not_run")),
                        t("developer_workspace_evidence_evidence"): get_evidence_display(str(row.get("evidence_level") or row.get("evidence_verdict") or "not_available"), lang=str(st.session_state.get("ui_lang") or "en")),
                        t("developer_workspace_registry_included_rows"): int(row.get("included_row_count") or 0),
                        t("developer_workspace_registry_positive_labels"): int(row.get("positive_label_count") or 0),
                        t("developer_workspace_registry_negative_labels"): int(row.get("negative_label_count") or 0),
                        t("developer_workspace_registry_primary_metric_leader"): str(row.get("primary_metric_leader") or "—"),
                    }
                    for row in validated_runs
                ]
            )
            st.dataframe(registry_df, use_container_width=True, hide_index=True)
        else:
            st.info(t("developer_workspace_evidence_no_validated_runs"))

        runs = list_experiment_runs(experiment_id=selected_experiment_id, limit=25, cache_bust=cache_bust)
        if runs:
            selected_run_id = st.selectbox(
                t("developer_workspace_registry_artifact_run_detail"),
                [str(row.get("run_id") or "") for row in runs],
                key="developer_workspace_evidence_run_id",
            )
            selected_run = get_run(selected_run_id)
            if selected_run:
                retention = get_run_artifact_retention_status(selected_run_id)
                detail_cols = st.columns(4, gap="small")
                detail_cards = [
                    (t("developer_workspace_detail_run_status"), get_run_status_display(str(selected_run.get("run_status") or ""))),
                    (t("developer_workspace_detail_integrity"), get_integrity_status_display(str(selected_run.get("integrity_status") or "not_run"))),
                    (t("developer_workspace_registry_maturity"), get_maturity_display(str(selected_run.get("maturity_verdict") or ""))),
                    (t("developer_workspace_detail_current_validated"), _yes_no(bool(selected_run.get("is_current_validated_run")))),
                ]
                for col, (label, value) in zip(detail_cols, detail_cards):
                    with col:
                        st.markdown(_card(label, value), unsafe_allow_html=True)
                st.caption(t("developer_workspace_detail_artifact_retention", value=_translate_retention_reason(retention.reason)))
                artifact_rows = list_run_artifacts(selected_run_id)
                _render_protected_artifacts(artifact_rows, key_prefix=f"evidence_{selected_run_id}")

    with reports_tab:
        if not latest_validated:
            st.info(t("developer_workspace_reports_no_validated_run"))
        else:
            run_id = str(latest_validated.get("run_id") or "")
            lang = str(st.session_state.get("ui_lang") or "en")
            feedback_key = f"developer_workspace_report_feedback_{run_id}_{lang}"
            feedback = st.session_state.pop(feedback_key, None)
            if isinstance(feedback, dict):
                generation_mode = str(feedback.get("generation_mode") or "template")
                provider = str(feedback.get("provider") or "").strip()
                if generation_mode == "ai":
                    provider_suffix = f" ({provider})" if provider else ""
                    st.success(t("developer_workspace_reports_feedback_ai", provider=provider_suffix))
                else:
                    st.warning(t("developer_workspace_reports_feedback_template"))
            render_report_context_editor(
                run_id=run_id,
                experiment_id=selected_experiment_id,
                language=lang,
                key_prefix=f"developer_workspace_{selected_experiment_id}_{run_id}",
            )
            capabilities = {CAPABILITY_VIEW_TECHNICAL_ARTIFACTS} if has_capability(CAPABILITY_VIEW_TECHNICAL_ARTIFACTS) else set()
            report_rows = list_available_eic_reports(run_id, capabilities, language=lang)
            for start in range(0, len(report_rows), 3):
                cols = st.columns(3, gap="medium")
                for col, report in zip(cols, report_rows[start : start + 3]):
                    report_type = str(report.get("report_type") or "")
                    report_status = str(report.get("status") or "not_available")
                    with col:
                        st.markdown(_card(str(report.get("title") or ""), _report_status_display(report_status), str(report.get("description") or "")), unsafe_allow_html=True)
                        if report_status == "available" and not bool(report.get("download_ready")):
                            if st.button(t("developer_workspace_reports_generate"), key=f"developer_workspace_generate_{run_id}_{report_type}", use_container_width=True):
                                with st.spinner(t("generating")):
                                    result = get_or_create_validated_report(run_id, report_type, lang)
                                if result.get("ok"):
                                    st.session_state[feedback_key] = {
                                        "generation_mode": str(result.get("generation_mode") or "template"),
                                        "provider": str(result.get("provider") or ""),
                                    }
                                    st.rerun()
                                st.error(str(result.get("message") or t("admin_eic_report_generation_failed")))
                        elif report_status == "available" and bool(report.get("download_ready")):
                            report_path = Path(str(report.get("path") or ""))
                            modified_epoch = int(report.get("modified_epoch") or 0)
                            action_cols = st.columns(2, gap="small")
                            with action_cols[0]:
                                st.download_button(
                                    label=t("developer_workspace_reports_download"),
                                    data=report_path.read_bytes(),
                                    file_name=report_path.name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    use_container_width=True,
                                    key=f"developer_workspace_download_docx_{run_id}_{report_type}_{modified_epoch}",
                                )
                            with action_cols[1]:
                                if st.button(
                                    t("developer_workspace_reports_regenerate"),
                                    key=f"developer_workspace_regenerate_{run_id}_{report_type}",
                                    use_container_width=True,
                                ):
                                    with st.spinner(t("generating")):
                                        result = get_or_create_validated_report(
                                            run_id,
                                            report_type,
                                            lang,
                                            force_regenerate=True,
                                        )
                                    if result.get("ok"):
                                        st.session_state[feedback_key] = {
                                            "generation_mode": str(result.get("generation_mode") or "template"),
                                            "provider": str(result.get("provider") or ""),
                                        }
                                        st.rerun()
                                    st.error(str(result.get("message") or t("admin_eic_report_generation_failed")))
                            if str(report.get("modified_at") or "").strip():
                                st.caption(t("developer_workspace_reports_latest_generated_at", value=str(report.get("modified_at") or "")))
                        else:
                            st.caption(t("developer_workspace_reports_availability", value=report_status))


def _render_telemetry_diagnostics() -> None:
    require_capability(CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS)
    health = load_telemetry_health_snapshot(
        teacher_id=str(get_authorization_context().user_id or "").strip(),
        days=int(st.selectbox(t("developer_workspace_telemetry_window"), [7, 14, 30], index=2, key="developer_workspace_telemetry_days")),
    )
    summary = health.get("summary") or {}
    cols = st.columns(4, gap="small")
    cards = [
        (t("developer_workspace_telemetry_exposures"), str(int(summary.get("total_exposures") or 0))),
        (t("developer_workspace_telemetry_matched_opens"), str(int(summary.get("exposures_with_matched_opens") or 0))),
        (t("developer_workspace_telemetry_unmatched_opens"), str(int(summary.get("unmatched_opens") or 0))),
        (t("developer_workspace_telemetry_outcome_coverage"), f"{float(summary.get('outcome_coverage') or 0.0):.1%}"),
    ]
    for col, (label, value) in zip(cols, cards):
        with col:
            st.markdown(_card(label, value), unsafe_allow_html=True)
    by_surface = health.get("by_surface") or []
    if by_surface:
        st.dataframe(_present_developer_table(by_surface), use_container_width=True, hide_index=True)
    else:
        st.info(t("developer_workspace_telemetry_empty"))


def _render_jobs() -> None:
    require_capability(CAPABILITY_VIEW_JOB_DIAGNOSTICS)
    jobs = list_jobs(limit=50, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if not jobs:
        st.info(t("developer_workspace_jobs_empty"))
        return
    st.dataframe(_present_developer_table(jobs), use_container_width=True, hide_index=True)


def _render_audit_log() -> None:
    require_capability(CAPABILITY_VIEW_AUDIT_LOG)
    actions = list_privileged_actions(limit=100, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if not actions:
        st.info(t("developer_workspace_audit_empty"))
        return
    st.dataframe(_present_developer_table(actions), use_container_width=True, hide_index=True)


def render_developer_workspace() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE, message=t("developer_workspace_access_required"))
    _inject_styles()
    context = get_authorization_context()
    chip_values = [_product_role_display(role) for role in context.product_roles] + [get_staff_role_display(role) for role in context.staff_roles]
    chips = "".join(f"<span class='dev-chip'>{_html.escape(role)}</span>" for role in chip_values)
    st.markdown(
        f"""
        <div class="dev-hero">
            <div class="dev-title">{_html.escape(t("developer_workspace_title"))}</div>
            <div class="dev-subtitle">{_html.escape(t("developer_workspace_subtitle"))}</div>
            <div class="dev-chip-row">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    overview_tab, lab_tab, evidence_tab, telemetry_tab, jobs_tab, audit_tab = st.tabs(
        [t("developer_workspace_tab_overview"), t("developer_workspace_tab_ml_lab"), t("developer_workspace_tab_evidence"), t("developer_workspace_tab_telemetry"), t("developer_workspace_tab_jobs"), t("developer_workspace_tab_audit")]
    )
    with overview_tab:
        _render_overview()
    with lab_tab:
        _render_ml_lab()
    with evidence_tab:
        _render_experiment_evidence()
    with telemetry_tab:
        _render_telemetry_diagnostics()
    with jobs_tab:
        _render_jobs()
    with audit_tab:
        _render_audit_log()
