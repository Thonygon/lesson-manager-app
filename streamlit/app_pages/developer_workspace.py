from __future__ import annotations

import html as _html
import json
import logging
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
    EXPERIMENT_PARADIGM_SUPERVISED,
    EXPERIMENT_PARADIGM_UNSUPERVISED,
    RESOURCE_AFFINITY_EXPERIMENT_ID,
    can_manually_rerun_integrity,
    get_run_artifact_retention_status,
    get_current_validated_run,
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
    publish_approved_resource_affinity_runtime_bundle,
    rerun_integrity_review_for_run,
    save_resource_affinity_human_review_recommendation,
)


logger = logging.getLogger(__name__)


def _safe_key(value: object) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())[:96] or "item"


def _format_run_option(run_id: str, runs: list[dict]) -> str:
    row = next((item for item in runs if str(item.get("run_id") or "") == str(run_id or "")), {})
    status = get_run_status_display(str(row.get("run_status") or ""))
    created = str(row.get("created_at") or "")[:19]
    return f"{run_id} · {status}" + (f" · {created}" if created else "")


def _confirm_action(key: str, label_key: str = "developer_workspace_confirm_action") -> bool:
    return bool(st.checkbox(t(label_key), key=f"{key}_confirm"))


def _render_empty_state(title_key: str, body_key: str, action_key: str = "") -> None:
    action = t(action_key) if action_key else ""
    action_html = f"<div class='dev-empty-action'>{_html.escape(action)}</div>" if action else ""
    st.markdown(
        f"""
        <div class="dev-empty-state">
            <div class="dev-empty-title">{_html.escape(t(title_key))}</div>
            <div class="dev-empty-body">{_html.escape(t(body_key))}</div>
            {action_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _role_guidance_text(context) -> str:
    staff_roles = {str(role or "").strip().lower() for role in getattr(context, "staff_roles", [])}
    if "developer" in staff_roles:
        return t("developer_workspace_role_guidance_developer")
    if "data_scientist" in staff_roles:
        return t("developer_workspace_role_guidance_data_scientist")
    return t("developer_workspace_role_guidance_default")


def _render_workspace_section_error(section_name: str, exc: Exception) -> None:
    from services.operational_diagnostics_service import capture_exception, sanitize_text, short_event_reference

    event_id = capture_exception(
        exc,
        component="app_pages.developer_workspace",
        operation="render_workspace_section",
        page_key="developer_workspace",
        user_face="developer",
        context={"resource_type": "workspace_section"},
    )
    logger.error(
        "Developer Workspace section failed event_id=%s exception_type=%s",
        event_id,
        type(exc).__name__,
        extra={"section_name": section_name},
    )
    st.error(t("developer_workspace_section_error") if t("developer_workspace_section_error") != "developer_workspace_section_error" else "No pudimos abrir esta sección del panel.")
    st.caption(f"{section_name}: {type(exc).__name__}: {sanitize_text(exc, limit=500)}")
    st.caption(t("operational_diagnostics_user_reference", reference=short_event_reference(event_id)))


def _prepare_model_comparison_frame(model_rows: list[dict]) -> pd.DataFrame:
    model_df = pd.DataFrame(model_rows)
    if model_df.empty:
        return model_df
    model_df = model_df[[column for column in model_df.columns if not str(column).startswith("_")]].copy()
    display_columns: dict[str, str] = {}
    seen_labels: set[str] = set()
    for column_name in list(model_df.columns):
        model_df[column_name] = model_df[column_name].apply(
            lambda value, name=column_name: get_model_comparison_value_display(name, value)
        )
        display_label = get_model_comparison_column_display(column_name)
        if display_label in seen_labels:
            display_label = f"{display_label} ({column_name})"
        seen_labels.add(display_label)
        display_columns[column_name] = display_label
    return model_df.rename(columns=display_columns)


def _experiment_paradigm_label(value: str) -> str:
    lang = str(st.session_state.get("ui_lang") or "en")
    safe = str(value or "").strip().lower()
    labels = {
        "all": {"en": "All experiment types", "es": "Todos los tipos", "tr": "Tüm deney türleri"},
        EXPERIMENT_PARADIGM_SUPERVISED: {"en": "Supervised", "es": "Supervisados", "tr": "Denetimli"},
        EXPERIMENT_PARADIGM_UNSUPERVISED: {"en": "Unsupervised", "es": "No supervisados", "tr": "Denetimsiz"},
    }
    return labels.get(safe, {}).get(lang, labels.get(safe, {}).get("en", safe.title() or "Unknown"))


def _filtered_experiment_catalog(catalog: list[dict], *, state_key: str) -> list[dict]:
    if not catalog:
        return []
    options = ["all", EXPERIMENT_PARADIGM_SUPERVISED, EXPERIMENT_PARADIGM_UNSUPERVISED]
    selected = st.selectbox(
        t("developer_workspace_experiment_type_label"),
        options,
        index=options.index(str(st.session_state.get(state_key) or "all")) if str(st.session_state.get(state_key) or "all") in options else 0,
        format_func=_experiment_paradigm_label,
        key=state_key,
    )
    if selected == "all":
        return catalog
    return [row for row in catalog if str(row.get("modeling_paradigm") or "").strip().lower() == selected]
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


def _artifact_type_display(artifact_type: str, *, filename: str = "") -> str:
    safe_type = " ".join(str(artifact_type or "").split()).strip()
    if str(filename or "").startswith("resource_affinity_"):
        affinity_labels = {
            "label_audit_csv": "Profile Audit",
            "holdout_predictions_csv": "Pairwise Semantic Neighbors",
            "anchor_resource_candidates_csv": "Program Topic Resource Candidates",
            "label_reconciliation_csv": "Unsupervised Validation Reconciliation",
            "resource_affinity_program_topic_resource_candidates.csv": "Program Topic Resource Candidates",
            "resource_affinity_exclusion_audit.csv": "Exclusion Audit",
            "resource_affinity_category_normalization_audit.csv": "Category Normalization Audit",
            "resource_affinity_human_review_sample.csv": "Human Review Sample",
            "resource_affinity_experiment_config.json": "Experiment Configuration",
            "resource_affinity_representation_manifest.json": "Fitted Representation Manifest",
        }
        specific = affinity_labels.get(safe_type) or affinity_labels.get(str(filename or ""))
        if specific:
            return specific
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


def _render_ml_workflow_guide(*, launcher_ready: bool, eligible: bool, has_runs: bool, has_validated: bool) -> None:
    states = [
        (t("developer_workspace_workflow_step_readiness"), t("developer_workspace_workflow_readiness_ready" if launcher_ready else "developer_workspace_workflow_readiness_blocked")),
        (t("developer_workspace_workflow_step_eligibility"), t("developer_workspace_workflow_eligibility_ready" if eligible else "developer_workspace_workflow_eligibility_blocked")),
        (t("developer_workspace_workflow_step_launch"), t("developer_workspace_workflow_launch_ready" if has_runs else "developer_workspace_workflow_launch_empty")),
        (t("developer_workspace_workflow_step_validate"), t("developer_workspace_workflow_validate_ready" if has_validated else "developer_workspace_workflow_validate_empty")),
        (t("developer_workspace_workflow_step_report"), t("developer_workspace_workflow_report_ready" if has_validated else "developer_workspace_workflow_report_empty")),
    ]
    items = []
    for index, (title, body) in enumerate(states, start=1):
        items.append(
            "<div class='dev-step'>"
            f"<div class='dev-step-number'>{_html.escape(t('developer_workspace_workflow_step', number=index))}</div>"
            f"<div class='dev-step-title'>{_html.escape(title)}</div>"
            f"<div class='dev-step-body'>{_html.escape(body)}</div>"
            "</div>"
        )
    st.markdown(f"<div class='dev-workflow'>{''.join(items)}</div>", unsafe_allow_html=True)


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
        .dev-workflow{
            display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:4px 0 16px;
        }
        .dev-step{
            border:1px solid var(--border);border-radius:16px;padding:12px 14px;
            background:linear-gradient(180deg, color-mix(in srgb, var(--panel) 96%, white 4%), color-mix(in srgb, var(--panel-soft) 92%, var(--primary) 8%));
            min-height:86px;
        }
        .dev-step-number{font-size:.72rem;font-weight:950;color:var(--primary);text-transform:uppercase;letter-spacing:.05em;}
        .dev-step-title{margin-top:5px;font-weight:950;color:var(--text);}
        .dev-step-body{margin-top:4px;color:var(--muted);font-size:.8rem;line-height:1.35;}
        .dev-empty-state{
            border:1px dashed color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
            border-radius:20px;padding:18px 20px;margin:12px 0;
            background:color-mix(in srgb, var(--panel-soft) 86%, transparent 14%);
        }
        .dev-empty-title{font-size:1rem;font-weight:950;color:var(--text);}
        .dev-empty-body{margin-top:5px;color:var(--muted);line-height:1.45;}
        .dev-empty-action{margin-top:10px;font-size:.86rem;font-weight:850;color:var(--primary);}
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
    artifact_path = Path(str(artifact.get("storage_path") or ""))
    artifact_type = _artifact_type_display(str(artifact.get("artifact_type") or ""), filename=artifact_path.name)
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


def _row_matches_search(row: dict, search: str, columns: tuple[str, ...]) -> bool:
    safe_search = " ".join(str(search or "").split()).strip().lower()
    if not safe_search:
        return True
    haystack = " ".join(str(row.get(column) or "") for column in columns).lower()
    return safe_search in haystack


def _render_paginated_table(rows: list[dict], *, key_prefix: str, page_size: int = 25) -> None:
    total_pages = max(1, (len(rows) + page_size - 1) // page_size)
    page_key = f"{key_prefix}_page"
    selected_page = max(1, min(int(st.session_state.get(page_key) or 1), total_pages))
    st.session_state[page_key] = selected_page
    start = (selected_page - 1) * page_size
    visible_rows = rows[start : start + page_size]
    if len(rows) > page_size:
        prev_col, info_col, next_col = st.columns([1, 3, 1])
        with prev_col:
            if st.button("←", key=f"{key_prefix}_prev", use_container_width=True, disabled=selected_page <= 1):
                st.session_state[page_key] = max(1, selected_page - 1)
                st.rerun()
        with info_col:
            st.caption(f"{start + 1}-{min(start + page_size, len(rows))} / {len(rows)} · {selected_page}/{total_pages}")
        with next_col:
            if st.button("→", key=f"{key_prefix}_next", use_container_width=True, disabled=selected_page >= total_pages):
                st.session_state[page_key] = min(total_pages, selected_page + 1)
                st.rerun()
    elif rows:
        st.caption(f"{start + 1}-{min(start + page_size, len(rows))} / {len(rows)} · {selected_page}/{total_pages}")
    st.dataframe(_present_developer_table(visible_rows), use_container_width=True, hide_index=True)


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
            artifact_key = f"{key_prefix}_{artifact.get('artifact_type')}_{artifact_path.name}_{artifact.get('checksum') or ''}"
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
                    "Type" if str(st.session_state.get("ui_lang") or "en") == "en" else ("Tipo" if str(st.session_state.get("ui_lang") or "en") == "es" else "Tür"): _experiment_paradigm_label(str(row.get("modeling_paradigm") or "")),
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
    catalog = _filtered_experiment_catalog(catalog, state_key="developer_workspace_lab_experiment_paradigm")
    selected_experiment = _selected_experiment(catalog, state_key="developer_workspace_lab_experiment_id")
    selected_experiment_id = str(selected_experiment.get("experiment_id") or APPROVED_EXPERIMENT_ID)
    selected_paradigm = str(selected_experiment.get("modeling_paradigm") or EXPERIMENT_PARADIGM_SUPERVISED)
    eligibility = compute_experiment_eligibility_summary(selected_experiment_id)
    top = st.columns(4, gap="small")
    count_label = t("developer_workspace_lab_mature_labels") if selected_paradigm == EXPERIMENT_PARADIGM_SUPERVISED else ("Resources" if str(st.session_state.get("ui_lang") or "en") == "en" else ("Recursos" if str(st.session_state.get("ui_lang") or "en") == "es" else "Kaynaklar"))
    count_value = int((eligibility.get("data_summary") or {}).get("mature_labels") or (eligibility.get("data_summary") or {}).get("resource_profiles") or (eligibility.get("data_summary") or {}).get("resource_count") or 0)
    cards = [
        (t("developer_workspace_lab_experiment"), get_experiment_display_name(selected_experiment_id)),
        (t("developer_workspace_lab_eligible"), _yes_no(bool(eligibility.get("eligible")))),
        (count_label, str(count_value)),
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

    env = get_environment_readiness()
    launcher_ready = bool(((env.get("experiment_launcher") or {}).get("ready")))
    runs = list_experiment_runs(experiment_id=selected_experiment_id, limit=25, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    has_validated = any(str(row.get("run_status") or "").upper().startswith("VALIDATED") for row in runs)
    _render_ml_workflow_guide(
        launcher_ready=launcher_ready,
        eligible=bool(eligibility.get("eligible")),
        has_runs=bool(runs),
        has_validated=has_validated,
    )

    st.caption(
        t("developer_workspace_lab_approved_models")
    )
    action_cols = st.columns([1.1, 1, 1.2], gap="medium")
    with action_cols[0]:
        if has_capability(CAPABILITY_RUN_APPROVED_EXPERIMENTS):
            launch_confirmed = _confirm_action(f"launch_approved_eval_{_safe_key(selected_experiment_id)}")
            launch_disabled = not launcher_ready or not bool(selected_experiment.get("launch_supported")) or not launch_confirmed
            if st.button(t("developer_workspace_lab_launch_evaluation"), key="launch_approved_eval", use_container_width=True, disabled=launch_disabled):
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
            elif not launch_confirmed:
                st.caption(t("developer_workspace_confirm_before_launch"))
    with action_cols[1]:
        if st.button(t("developer_workspace_lab_refresh_runs"), key="refresh_runs", use_container_width=True):
            st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
            st.rerun()
    with action_cols[2]:
        stale_confirmed = _confirm_action("mark_stale_jobs")
        if st.button(t("developer_workspace_lab_mark_stale_jobs"), key="mark_stale_jobs", use_container_width=True, disabled=not stale_confirmed):
            count = mark_stale_experiment_jobs()
            st.info(t("developer_workspace_lab_marked_stale_jobs", count=count))
        if not stale_confirmed:
            st.caption(t("developer_workspace_confirm_before_stale_jobs"))

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
            if has_capability(CAPABILITY_COMPARE_EXPERIMENT_RUNS) and len(runs) >= 2:
                st.markdown(f"##### {t('developer_workspace_run_comparison_title')}")
                compare_columns = st.columns(2, gap="small")
                run_ids = [str(row.get("run_id") or "") for row in runs if str(row.get("run_id") or "").strip()]
                with compare_columns[0]:
                    left_run_id = st.selectbox(
                        t("developer_workspace_compare_left_run"),
                        run_ids,
                        index=0,
                        format_func=lambda value: _format_run_option(value, runs),
                        key=f"developer_workspace_compare_left_{_safe_key(selected_experiment_id)}",
                    )
                default_right_index = 1 if len(run_ids) > 1 else 0
                with compare_columns[1]:
                    right_run_id = st.selectbox(
                        t("developer_workspace_compare_right_run"),
                        run_ids,
                        index=default_right_index,
                        format_func=lambda value: _format_run_option(value, runs),
                        key=f"developer_workspace_compare_right_{_safe_key(selected_experiment_id)}",
                    )
                compare_rows = [row for row in runs if str(row.get("run_id") or "") in {left_run_id, right_run_id}]
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
                    rerun_confirmed = _confirm_action(f"rerun_integrity_{_safe_key(selected_run_id)}")
                    if st.button(t("developer_workspace_lab_rerun_integrity"), key=f"rerun_integrity_{selected_run_id}", use_container_width=False, disabled=not rerun_confirmed):
                        ok, _payload, message = rerun_integrity_review_for_run(selected_run_id)
                        if ok:
                            st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    if not rerun_confirmed:
                        st.caption(t("developer_workspace_confirm_before_integrity"))
                    st.caption(explanation)
                else:
                    st.caption(explanation)
    else:
        _render_empty_state(
            "developer_workspace_lab_empty_title",
            "developer_workspace_lab_empty_body",
            "developer_workspace_lab_empty_action",
        )


def _render_experiment_evidence() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE)
    refresh_nonce = int(st.session_state.get("developer_workspace_refresh_nonce") or 0)
    cache_bust = str(refresh_nonce)
    catalog = list_experiment_catalog(cache_bust=cache_bust)
    catalog = _filtered_experiment_catalog(catalog, state_key="developer_workspace_evidence_experiment_paradigm")
    selected_experiment = _selected_experiment(catalog, state_key="developer_workspace_evidence_experiment_id")
    selected_experiment_id = str(selected_experiment.get("experiment_id") or APPROVED_EXPERIMENT_ID)
    selected_paradigm = str(selected_experiment.get("modeling_paradigm") or EXPERIMENT_PARADIGM_SUPERVISED)
    latest_validated = get_latest_validated_run_summary(experiment_id=selected_experiment_id, cache_bust=cache_bust) or {}
    current_validated = get_current_validated_run(experiment_id=selected_experiment_id, cache_bust=cache_bust) or {}
    active_run = current_validated or latest_validated
    validated_runs = eic_service.list_validated_experiment_summaries(limit=10, cache_bust=cache_bust, experiment_id=selected_experiment_id)

    st.markdown(f"### {t('developer_workspace_evidence_title')}")
    st.caption(t("developer_workspace_evidence_caption"))

    if active_run:
        top_cards = [
            (t("developer_workspace_evidence_current_validated_run"), str(active_run.get("run_id") or t("admin_eic_value_none"))),
            (t("developer_workspace_detail_run_status"), get_run_status_display(str(active_run.get("run_status") or ""))),
            (t("developer_workspace_detail_integrity"), get_integrity_status_display(str(active_run.get("integrity_status") or "not_run"))),
            (t("developer_workspace_evidence_evidence"), get_evidence_display(str(active_run.get("evidence_level") or active_run.get("evidence_verdict") or "not_available"), lang=str(st.session_state.get("ui_lang") or "en"))),
        ]
        cols = st.columns(4, gap="small")
        for col, (label, value) in zip(cols, top_cards):
            with col:
                st.markdown(_card(label, value), unsafe_allow_html=True)
    else:
        _render_empty_state(
            "developer_workspace_evidence_empty_title",
            "developer_workspace_evidence_empty_body",
            "developer_workspace_evidence_empty_action",
        )

    evidence_tab, registry_tab, reports_tab = st.tabs(
        [t("developer_workspace_evidence_tab_summary"), t("developer_workspace_evidence_tab_registry"), t("developer_workspace_evidence_tab_reports")]
    )

    with evidence_tab:
        try:
            if not latest_validated:
                _render_empty_state(
                    "developer_workspace_evidence_requires_title",
                    "developer_workspace_evidence_requires_body",
                    "developer_workspace_evidence_requires_action",
                )
            else:
                run_id = str(latest_validated.get("run_id") or "")
                summary_rows = [
                    (t("developer_workspace_summary_experiment"), get_experiment_display_name(str(latest_validated.get("experiment_id") or selected_experiment_id))),
                    (t("developer_workspace_summary_dataset_size"), str(int(latest_validated.get("included_row_count") or 0))),
                    (t("developer_workspace_summary_teachers_represented"), str(int(latest_validated.get("teachers_represented") or 0))),
                    (t("developer_workspace_summary_recommended_business_action"), get_business_action_display(str(latest_validated.get("recommended_business_action") or ""))),
                ]
                if selected_paradigm == EXPERIMENT_PARADIGM_SUPERVISED:
                    summary_rows.insert(2, (t("developer_workspace_summary_positive_labels"), str(int(latest_validated.get("positive_label_count") or 0))))
                    summary_rows.insert(3, (t("developer_workspace_summary_negative_labels"), str(int(latest_validated.get("negative_label_count") or 0))))
                st.dataframe(pd.DataFrame(summary_rows, columns=[t("admin_field_label"), t("admin_value_label")]), use_container_width=True, hide_index=True)
                try:
                    business_detail = eic_service.get_experiment_business_detail(run_id, cache_bust=cache_bust)
                except Exception:
                    business_detail = {}
                model_rows = ((business_detail or {}).get("model_results") or {}).get("models_compared") or []
                if model_rows:
                    model_df = _prepare_model_comparison_frame(model_rows)
                    st.markdown(f"#### {t('developer_workspace_model_comparison_title')}")
                    st.dataframe(model_df, use_container_width=True, hide_index=True)
                if selected_experiment_id == RESOURCE_AFFINITY_EXPERIMENT_ID:
                    runtime_model = str(current_validated.get("human_review_recommended_model_name") or current_validated.get("overall_model_selection") or "—")
                    runtime_run = str(current_validated.get("run_id") or "—")
                    review_model = str((business_detail.get("model_results") or {}).get("human_review_recommended_model_name") or "—")
                    comparison_rows = [
                        (t("developer_workspace_review_automatic_winner"), str((business_detail.get("model_results") or {}).get("automatic_winner") or "—")),
                        (t("developer_workspace_review_human_recommendation"), review_model),
                        (t("developer_workspace_review_active_runtime_model"), f"{runtime_model} ({runtime_run})" if runtime_run != "—" else runtime_model),
                    ]
                    st.dataframe(
                        pd.DataFrame(comparison_rows, columns=[t("admin_field_label"), t("admin_value_label")]),
                        use_container_width=True,
                        hide_index=True,
                    )
        except Exception as exc:
            _render_workspace_section_error("Resumen validado", exc)

    with registry_tab:
        try:
            if validated_runs:
                registry_df = pd.DataFrame(
                    [
                        ({
                            t("developer_workspace_registry_run_id"): str(row.get("run_id") or ""),
                            t("developer_workspace_catalog_experiment"): get_experiment_display_name(str(row.get("experiment_id") or selected_experiment_id)),
                            t("developer_workspace_registry_run_status"): get_run_status_display(str(row.get("run_status") or "")),
                            t("developer_workspace_registry_integrity"): get_integrity_status_display(str(row.get("integrity_status") or "not_run")),
                            t("developer_workspace_evidence_evidence"): get_evidence_display(str(row.get("evidence_level") or row.get("evidence_verdict") or "not_available"), lang=str(st.session_state.get("ui_lang") or "en")),
                            t("developer_workspace_registry_included_rows"): int(row.get("included_row_count") or 0),
                            t("developer_workspace_registry_primary_metric_leader"): str(row.get("primary_metric_leader") or "—"),
                        } | ({
                            t("developer_workspace_registry_positive_labels"): int(row.get("positive_label_count") or 0),
                            t("developer_workspace_registry_negative_labels"): int(row.get("negative_label_count") or 0),
                        } if selected_paradigm == EXPERIMENT_PARADIGM_SUPERVISED else {}))
                        for row in validated_runs
                    ]
                )
                st.dataframe(registry_df, use_container_width=True, hide_index=True)
            else:
                _render_empty_state(
                    "developer_workspace_evidence_no_validated_title",
                    "developer_workspace_evidence_no_validated_body",
                    "developer_workspace_evidence_no_validated_action",
                )

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
                    current_runtime_run_id = str(current_validated.get("run_id") or "")
                    current_runtime_model = str(current_validated.get("human_review_recommended_model_name") or current_validated.get("overall_model_selection") or "")
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
                    if selected_experiment_id == RESOURCE_AFFINITY_EXPERIMENT_ID:
                        model_rows = list_run_models(selected_run_id)
                        model_names = [str(row.get("model_name") or "") for row in model_rows if str(row.get("model_name") or "").strip()]
                        automatic_winner = str(selected_run.get("overall_model_selection") or selected_run.get("primary_metric_leader") or "—")
                        reviewed_model = str(selected_run.get("human_review_recommended_model_name") or "")
                        summary_rows = [
                            (t("developer_workspace_review_automatic_winner"), automatic_winner),
                            (t("developer_workspace_review_human_recommendation"), reviewed_model or "—"),
                            (
                                t("developer_workspace_review_active_runtime_model"),
                                f"{current_runtime_model or '—'} ({current_runtime_run_id})" if current_runtime_run_id else (current_runtime_model or "—"),
                            ),
                        ]
                        st.dataframe(
                            pd.DataFrame(summary_rows, columns=[t("admin_field_label"), t("admin_value_label")]),
                            use_container_width=True,
                            hide_index=True,
                        )
                        if model_names:
                            default_index = model_names.index(reviewed_model) if reviewed_model in model_names else (model_names.index(automatic_winner) if automatic_winner in model_names else 0)
                            st.markdown(f"##### {t('developer_workspace_review_controls')}")
                            selected_model_name = st.selectbox(
                                t("developer_workspace_review_recommended_model"),
                                model_names,
                                index=default_index,
                                key=f"developer_workspace_resource_affinity_review_model_{selected_run_id}",
                            )
                            notes_key = f"developer_workspace_resource_affinity_review_notes_{selected_run_id}"
                            st.text_area(
                                t("developer_workspace_review_notes"),
                                value=str(selected_run.get("human_review_notes") or ""),
                                key=notes_key,
                                height=100,
                            )
                            action_cols = st.columns(2, gap="small")
                            with action_cols[0]:
                                save_confirmed = _confirm_action(f"save_review_model_{_safe_key(selected_run_id)}")
                                if st.button(
                                    t("developer_workspace_review_save_recommendation"),
                                    key=f"developer_workspace_save_review_model_{selected_run_id}",
                                    use_container_width=True,
                                    disabled=not save_confirmed,
                                ):
                                    ok, message = save_resource_affinity_human_review_recommendation(
                                        selected_run_id,
                                        selected_model_name,
                                        st.session_state.get(notes_key) or "",
                                        activate_for_runtime=False,
                                    )
                                    if ok:
                                        st.success(message)
                                        st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
                                        st.rerun()
                                    st.error(message)
                                if not save_confirmed:
                                    st.caption(t("developer_workspace_confirm_before_review_save"))
                            with action_cols[1]:
                                activate_confirmed = _confirm_action(f"activate_review_model_{_safe_key(selected_run_id)}", "developer_workspace_confirm_runtime_action")
                                if st.button(
                                    t("developer_workspace_review_set_runtime_model"),
                                    key=f"developer_workspace_activate_review_model_{selected_run_id}",
                                    use_container_width=True,
                                    disabled=not activate_confirmed,
                                ):
                                    ok, message = save_resource_affinity_human_review_recommendation(
                                        selected_run_id,
                                        selected_model_name,
                                        st.session_state.get(notes_key) or "",
                                        activate_for_runtime=True,
                                    )
                                    if ok:
                                        st.success(message)
                                        st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
                                        st.rerun()
                                    st.error(message)
                                if not activate_confirmed:
                                    st.caption(t("developer_workspace_confirm_before_runtime"))
                        if (
                            has_capability(CAPABILITY_RUN_APPROVED_EXPERIMENTS)
                            and str(selected_run.get("operational_use") or "") == "PRODUCTION_RUNTIME"
                            and bool(selected_run.get("is_current_validated_run"))
                        ):
                            if st.button(
                                t("developer_workspace_publish_runtime_bundle"),
                                key=f"developer_workspace_publish_runtime_bundle_{selected_run_id}",
                                use_container_width=True,
                            ):
                                ok, message = publish_approved_resource_affinity_runtime_bundle(selected_run_id)
                                (st.success if ok else st.error)(t("developer_workspace_runtime_bundle_published") if ok else message)
                    artifact_rows = list_run_artifacts(selected_run_id)
                    _render_protected_artifacts(artifact_rows, key_prefix=f"evidence_{selected_run_id}")
        except Exception as exc:
            _render_workspace_section_error("Registro y artefactos", exc)

    with reports_tab:
        try:
            if not latest_validated:
                _render_empty_state(
                    "developer_workspace_reports_empty_title",
                    "developer_workspace_reports_empty_body",
                    "developer_workspace_reports_empty_action",
                )
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
                                generate_confirmed = _confirm_action(f"generate_report_{_safe_key(run_id)}_{_safe_key(report_type)}")
                                if st.button(t("developer_workspace_reports_generate"), key=f"developer_workspace_generate_{run_id}_{report_type}", use_container_width=True, disabled=not generate_confirmed):
                                    with st.spinner(t("generating")):
                                        result = get_or_create_validated_report(run_id, report_type, lang)
                                    if result.get("ok"):
                                        st.session_state[feedback_key] = {
                                            "generation_mode": str(result.get("generation_mode") or "template"),
                                            "provider": str(result.get("provider") or ""),
                                        }
                                        st.rerun()
                                    st.error(str(result.get("message") or t("admin_eic_report_generation_failed")))
                                if not generate_confirmed:
                                    st.caption(t("developer_workspace_confirm_before_report"))
                            elif report_status == "available" and bool(report.get("download_ready")):
                                report_path = Path(str(report.get("path") or ""))
                                modified_epoch = int(report.get("modified_epoch") or 0)
                                action_cols = st.columns(2, gap="small")
                                with action_cols[0]:
                                    if report_path.exists():
                                        st.download_button(
                                            label=t("developer_workspace_reports_download"),
                                            data=report_path.read_bytes(),
                                            file_name=report_path.name,
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            use_container_width=True,
                                            key=f"developer_workspace_download_docx_{run_id}_{report_type}_{modified_epoch}",
                                        )
                                    else:
                                        st.button(t("developer_workspace_reports_download"), disabled=True, use_container_width=True, key=f"developer_workspace_missing_docx_{run_id}_{report_type}")
                                with action_cols[1]:
                                    if st.button(
                                        t("developer_workspace_reports_regenerate"),
                                        key=f"developer_workspace_regenerate_{run_id}_{report_type}",
                                        use_container_width=True,
                                        disabled=not _confirm_action(f"regenerate_report_{_safe_key(run_id)}_{_safe_key(report_type)}", "developer_workspace_confirm_regenerate_action"),
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
                                    if not st.session_state.get(f"regenerate_report_{_safe_key(run_id)}_{_safe_key(report_type)}_confirm"):
                                        st.caption(t("developer_workspace_confirm_before_regenerate"))
                                if str(report.get("modified_at") or "").strip():
                                    st.caption(t("developer_workspace_reports_latest_generated_at", value=str(report.get("modified_at") or "")))
                            else:
                                st.caption(t("developer_workspace_reports_availability", value=report_status))
        except Exception as exc:
            _render_workspace_section_error("Informes", exc)


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
        _render_empty_state(
            "developer_workspace_telemetry_empty_title",
            "developer_workspace_telemetry_empty_body",
            "developer_workspace_telemetry_empty_action",
        )


def _render_jobs() -> None:
    require_capability(CAPABILITY_VIEW_JOB_DIAGNOSTICS)
    jobs = list_jobs(limit=200, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if not jobs:
        _render_empty_state(
            "developer_workspace_jobs_empty_title",
            "developer_workspace_jobs_empty_body",
            "developer_workspace_jobs_empty_action",
        )
        return
    filter_cols = st.columns(3, gap="small")
    statuses = ["all", *sorted({str(row.get("status") or "").upper() for row in jobs if str(row.get("status") or "").strip()})]
    job_types = ["all", *sorted({str(row.get("job_type") or "") for row in jobs if str(row.get("job_type") or "").strip()})]
    with filter_cols[0]:
        selected_status = st.selectbox(
            t("developer_workspace_jobs_filter_status"),
            statuses,
            format_func=lambda value: t("developer_workspace_filter_all") if value == "all" else get_model_result_status_display(str(value)),
            key="developer_workspace_jobs_status_filter",
        )
    with filter_cols[1]:
        selected_type = st.selectbox(
            t("developer_workspace_jobs_filter_type"),
            job_types,
            format_func=lambda value: t("developer_workspace_filter_all") if value == "all" else get_job_type_display(str(value)),
            key="developer_workspace_jobs_type_filter",
        )
    with filter_cols[2]:
        search = st.text_input(
            t("developer_workspace_filter_search"),
            placeholder=t("developer_workspace_jobs_search_placeholder"),
            key="developer_workspace_jobs_search",
        )
    filtered = [
        row
        for row in jobs
        if (selected_status == "all" or str(row.get("status") or "").upper() == selected_status)
        and (selected_type == "all" or str(row.get("job_type") or "") == selected_type)
        and _row_matches_search(row, search, ("job_id", "job_type", "status", "current_stage", "related_entity_id", "error_message"))
    ]
    if not filtered:
        _render_empty_state(
            "developer_workspace_jobs_no_matches_title",
            "developer_workspace_jobs_no_matches_body",
            "developer_workspace_jobs_no_matches_action",
        )
        return
    _render_paginated_table(filtered, key_prefix="developer_workspace_jobs", page_size=25)


def _render_audit_log() -> None:
    require_capability(CAPABILITY_VIEW_AUDIT_LOG)
    actions = list_privileged_actions(limit=200, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if not actions:
        _render_empty_state(
            "developer_workspace_audit_empty_title",
            "developer_workspace_audit_empty_body",
            "developer_workspace_audit_empty_action",
        )
        return
    filter_cols = st.columns(3, gap="small")
    action_types = ["all", *sorted({str(row.get("action_type") or "") for row in actions if str(row.get("action_type") or "").strip()})]
    entity_types = ["all", *sorted({str(row.get("entity_type") or "") for row in actions if str(row.get("entity_type") or "").strip()})]
    with filter_cols[0]:
        selected_action = st.selectbox(
            t("developer_workspace_audit_filter_action"),
            action_types,
            format_func=lambda value: t("developer_workspace_filter_all") if value == "all" else get_action_type_display(str(value)),
            key="developer_workspace_audit_action_filter",
        )
    with filter_cols[1]:
        selected_entity = st.selectbox(
            t("developer_workspace_audit_filter_entity"),
            entity_types,
            format_func=lambda value: t("developer_workspace_filter_all") if value == "all" else get_entity_type_display(str(value)),
            key="developer_workspace_audit_entity_filter",
        )
    with filter_cols[2]:
        search = st.text_input(
            t("developer_workspace_filter_search"),
            placeholder=t("developer_workspace_audit_search_placeholder"),
            key="developer_workspace_audit_search",
        )
    filtered = [
        row
        for row in actions
        if (selected_action == "all" or str(row.get("action_type") or "") == selected_action)
        and (selected_entity == "all" or str(row.get("entity_type") or "") == selected_entity)
        and _row_matches_search(row, search, ("action_type", "entity_type", "entity_id", "actor_user_id", "reason"))
    ]
    if not filtered:
        _render_empty_state(
            "developer_workspace_audit_no_matches_title",
            "developer_workspace_audit_no_matches_body",
            "developer_workspace_audit_no_matches_action",
        )
        return
    _render_paginated_table(filtered, key_prefix="developer_workspace_audit", page_size=25)


def render_developer_workspace() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE, message=t("developer_workspace_access_required"))
    _inject_styles()
    context = get_authorization_context()
    chip_values = [_product_role_display(role) for role in context.product_roles] + [get_staff_role_display(role) for role in context.staff_roles]
    chips = "".join(f"<span class='dev-chip'>{_html.escape(role)}</span>" for role in chip_values)
    role_guidance = _role_guidance_text(context)
    st.markdown(
        f"""
        <div class="dev-hero">
            <div class="dev-title">{_html.escape(t("developer_workspace_title"))}</div>
            <div class="dev-subtitle">{_html.escape(t("developer_workspace_subtitle"))}</div>
            <div class="dev-subtitle">{_html.escape(role_guidance)}</div>
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
