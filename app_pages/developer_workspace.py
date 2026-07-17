from __future__ import annotations

import html as _html
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core.i18n import t
from helpers.exposure_telemetry import load_telemetry_health_snapshot
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
    get_business_action_display,
    get_evidence_display,
    get_experiment_display_name,
    get_integrity_status_display,
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


def _yes_no(value: bool) -> str:
    return "yes" if bool(value) else "no"


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


def _render_readiness_card(label: str, payload: dict) -> None:
    value = "ready" if bool(payload.get("ready")) else "not ready"
    if label == "Artifact Filesystem":
        value = "writable" if bool(payload.get("ready")) else "not writable"
    checks = payload.get("checks") or []
    details: list[str] = []
    for check in checks:
        icon = "✓" if bool(check.get("ready")) else "✗"
        detail = str(check.get("name") or "")
        error = str(check.get("error") or "").strip()
        message = str(check.get("message") or "").strip()
        suffix = f" ({message})" if message and message.lower() != f"{detail} import ready.".lower() else ""
        details.append(f"{icon} {detail}{suffix}")
        if error:
            details.append(f"Why failing: {error}")
        action = str(check.get("recommended_action") or "").strip()
        if action and not bool(check.get("ready")):
            details.append(f"Recommended action: {action}")
    _render_clickable_readiness_card(
        label,
        value,
        str(payload.get("message") or ""),
        details=details,
        expander_key=f"dev_readiness_{label.lower().replace(' ', '_')}",
    )


def _render_launcher_card(payload: dict) -> None:
    value = "ready" if bool(payload.get("ready")) else "not ready"
    details: list[str] = []
    blocking = payload.get("blocking_reasons") or []
    if blocking:
        details.append("Blocking reasons:")
        for reason in blocking:
            details.append(f"• {reason}")
    actions = payload.get("recommended_actions") or []
    if actions:
        details.append("Recommended action:")
        for action in actions:
            details.append(f"• {action}")
    _render_clickable_readiness_card(
        "Experiment Launcher",
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
    artifact_type = str(artifact.get("artifact_type") or "").strip().replace("_", " ")
    artifact_type = " ".join(part.capitalize() for part in artifact_type.split())
    artifact_path = Path(str(artifact.get("storage_path") or ""))
    if artifact_path.name:
        return f"{artifact_type} ({artifact_path.name})"
    return artifact_type or "Artifact"


def _developer_table_column_label(column_name: str) -> str:
    labels = {
        "id": t("developer_workspace_table_id"),
        "run_id": t("developer_workspace_table_run_id"),
        "model_name": t("developer_workspace_table_model_name"),
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
    if column_name == "model_name":
        return get_model_name_display(str(value))
    if column_name in {"execution_status", "status"}:
        return get_model_result_status_display(str(value))
    if column_name in {"surface", "exposure_type"}:
        return _humanize_identifier(value)
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
        "Experiment",
        option_ids,
        index=option_ids.index(current),
        format_func=lambda value: next((str(row.get("display_label") or row.get("name") or value) for row in catalog if str(row.get("experiment_id") or "") == value), value),
        key=state_key,
    )
    return next((row for row in catalog if str(row.get("experiment_id") or "") == selected_id), {})


def _render_protected_artifacts(artifact_rows: list[dict], *, key_prefix: str) -> None:
    if not artifact_rows:
        return
    st.markdown("<div class='dev-expander-gap'></div>", unsafe_allow_html=True)
    with st.expander("Protected Artifacts", expanded=False):
        st.caption("Validated stored artifacts for the selected run.")
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
    cards = [
        ("Environment", str(overview.get("environment") or "unknown"), "Current runtime for controlled technical jobs."),
        ("Code Version", str(overview.get("code_version") or "unknown"), "Git HEAD when available."),
        ("Latest Successful Experiment", str(latest_successful.get("run_id") or "none"), get_run_status_display(str(latest_successful.get("run_status") or "No completed run yet."))),
        ("Latest Attempted Experiment", str(latest_attempted.get("run_id") or "none"), get_run_status_display(str(latest_attempted.get("run_status") or "No run yet."))),
        ("Latest Validated Run", str(latest_validated.get("run_id") or "No validated run yet"), get_run_status_display(str(latest_validated.get("run_status") or ""))),
        ("Active Jobs", str(len(overview.get("active_jobs") or [])), "Queued and running controlled jobs."),
        ("Failed Jobs", str(len(overview.get("failed_jobs") or [])), "Recent failed jobs requiring attention."),
        ("Telemetry Outcome Coverage", f"{float(telemetry.get('outcome_coverage') or 0.0):.1%}", "Recent canonical exposure coverage."),
    ]
    cols = st.columns(4, gap="small")
    for idx, (label, value, help_text) in enumerate(cards):
        with cols[idx % 4]:
            st.markdown(_card(label, value, help_text), unsafe_allow_html=True)

    if catalog:
        st.markdown("#### Experiment Catalog")
        catalog_df = pd.DataFrame(
            [
                {
                    "Experiment": str(row.get("display_label") or row.get("name") or ""),
                    "Status": str(row.get("status") or ""),
                    "Runs": int(row.get("run_count") or 0),
                    "Validated Runs": int(row.get("validated_run_count") or 0),
                    "Latest Run": str((row.get("latest_run") or {}).get("run_id") or "none"),
                    "Latest Status": get_run_status_display(str((row.get("latest_run") or {}).get("run_status") or "not_available")),
                }
                for row in catalog
            ]
        )
        st.dataframe(catalog_df, use_container_width=True, hide_index=True)

    warnings = [warning for warning in (overview.get("warnings") or []) if str(warning).strip()]
    if warnings:
        st.markdown("#### Developer Warnings")
        for warning in warnings:
            st.warning(str(warning))

    env = overview.get("environment_readiness") or get_environment_readiness()
    st.markdown("#### Environment Readiness")
    env_cols = st.columns(5, gap="small")
    with env_cols[0]:
        _render_readiness_card("Database Migration", env.get("database_migration") or {})
    with env_cols[1]:
        _render_readiness_card("Artifact Filesystem", env.get("artifact_filesystem") or {})
    with env_cols[2]:
        _render_readiness_card("ML Dependencies", env.get("ml_dependencies") or {})
    with env_cols[3]:
        execution_mode = env.get("execution_mode") or {}
        mode_value = str(execution_mode.get("mode") or "unknown")
        _render_clickable_readiness_card(
            "Execution Mode",
            mode_value,
            str(execution_mode.get("message") or ""),
            details=[
                f"Worker available: {'yes' if bool(execution_mode.get('worker_available')) else 'no'}",
                f"Synchronous enabled: {'yes' if bool(execution_mode.get('synchronous_enabled')) else 'no'}",
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
        ("Experiment", str(selected_experiment.get("display_label") or get_experiment_display_name(selected_experiment_id))),
        ("Eligible", _yes_no(bool(eligibility.get("eligible")))),
        ("Mature Labels", str(int((eligibility.get("data_summary") or {}).get("mature_labels") or 0))),
        ("Expected Ceiling", get_maturity_display(str(eligibility.get("expected_maturity_ceiling") or "unknown"))),
    ]
    for col, (label, value) in zip(top, cards):
        with col:
            st.markdown(_card(label, value), unsafe_allow_html=True)
    if not bool(eligibility.get("supported")):
        st.info(str(eligibility.get("message") or "This experiment is visible, but not fully wired in the lab yet."))
    if eligibility.get("blocking_reasons"):
        st.error("Blocking reasons: " + " | ".join(eligibility.get("blocking_reasons") or []))
    if eligibility.get("warnings"):
        for warning in eligibility.get("warnings") or []:
            st.warning(str(warning))

    st.caption(
        "Approved models: DummyClassifier, LogisticRegression, LogisticRegressionReduced, DecisionTreeClassifier, RandomForestClassifier, HistGradientBoostingClassifier, SVC, KNeighborsClassifier."
    )
    env = get_environment_readiness()
    launcher_ready = bool(((env.get("experiment_launcher") or {}).get("ready")))
    action_cols = st.columns([1.1, 1, 1.2], gap="medium")
    with action_cols[0]:
        if has_capability(CAPABILITY_RUN_APPROVED_EXPERIMENTS):
            if st.button("Launch Evaluation", key="launch_approved_eval", use_container_width=True, disabled=not launcher_ready or not bool(selected_experiment.get("launch_supported"))):
                ok, payload, message = launch_experiment(selected_experiment_id)
                if ok:
                    st.success(message)
                    st.session_state["developer_workspace_selected_run_id"] = str(payload.get("run_id") or "")
                    st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
                    st.rerun()
                else:
                    st.error(message)
            if not launcher_ready:
                st.caption("Launch is disabled until all experiment launcher blocking conditions are resolved.")
            elif not bool(selected_experiment.get("launch_supported")):
                st.caption("This experiment is cataloged but its launch flow is not wired in the workspace yet.")
    with action_cols[1]:
        if st.button("Refresh Runs", key="refresh_runs", use_container_width=True):
            st.session_state["developer_workspace_refresh_nonce"] = int(st.session_state.get("developer_workspace_refresh_nonce") or 0) + 1
            st.rerun()
    with action_cols[2]:
        if st.button("Mark Stale Jobs", key="mark_stale_jobs", use_container_width=True):
            count = mark_stale_experiment_jobs()
            st.info(f"Marked {count} stale job(s).")

    runs = list_experiment_runs(experiment_id=selected_experiment_id, limit=25, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if runs:
        st.markdown("#### Run Registry")
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
                "run_id": "Run ID",
                "run_status": "Run Status",
                "integrity_status": "Integrity",
                "maturity_verdict": "Maturity",
                "included_row_count": "Included Rows",
                "positive_label_count": "Positive Labels",
                "negative_label_count": "Negative Labels",
                "teachers_represented": "Teachers Represented",
                "created_at": "Created At",
                "is_current_validated_run": "Current Validated",
            }
        )
        st.dataframe(registry_df, use_container_width=True, hide_index=True)
        selected_run_id = st.selectbox(
            "Run Detail",
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
                ("Run Status", get_run_status_display(str(state_summary.get("run_status") or ""))),
                ("Integrity", get_integrity_status_display(str(selected_run.get("integrity_status") or ""))),
                ("Artifacts Ready", _yes_no(readiness.ready)),
                ("Current Validated", _yes_no(bool(selected_run.get("is_current_validated_run")))),
            ]
            for col, (label, value) in zip(detail_cols, detail_cards):
                with col:
                    st.markdown(_card(label, value), unsafe_allow_html=True)
            st.caption(str(state_summary.get("current_message") or ""))
            st.caption(f"Next action: {state_summary.get('next_action') or 'Refresh'}")
            st.caption(f"Artifact retention: {retention.reason}")
            if state_summary.get("failure_message"):
                st.error(str(state_summary.get("failure_message")))
            if readiness.missing_artifact_types:
                st.warning("Missing artifacts: " + ", ".join(readiness.missing_artifact_types))
            model_rows = list_run_models(selected_run_id)
            if model_rows:
                st.markdown("##### Model Results")
                st.dataframe(_present_developer_table(model_rows), use_container_width=True, hide_index=True)
            compare_rows = runs[:2]
            if has_capability(CAPABILITY_COMPARE_EXPERIMENT_RUNS) and len(compare_rows) >= 2:
                st.markdown("##### Run Comparison")
                comparison_df = pd.DataFrame(compare_rows)[
                    [col for col in ["run_id", "run_status", "integrity_status", "included_row_count", "positive_label_count", "negative_label_count", "primary_metric_leader"] if col in pd.DataFrame(compare_rows).columns]
                ].copy()
                if "run_status" in comparison_df.columns:
                    comparison_df["run_status"] = comparison_df["run_status"].astype(str).map(get_run_status_display)
                if "integrity_status" in comparison_df.columns:
                    comparison_df["integrity_status"] = comparison_df["integrity_status"].astype(str).map(get_integrity_status_display)
                comparison_df = comparison_df.rename(
                    columns={
                        "run_id": "Run ID",
                        "run_status": "Run Status",
                        "integrity_status": "Integrity",
                        "included_row_count": "Included Rows",
                        "positive_label_count": "Positive Labels",
                        "negative_label_count": "Negative Labels",
                        "primary_metric_leader": "Primary Metric Leader",
                    }
                )
                st.dataframe(comparison_df, use_container_width=True, hide_index=True)
            if has_capability(CAPABILITY_RERUN_INTEGRITY_REVIEW):
                allowed, explanation = can_manually_rerun_integrity(selected_run_id)
                if allowed:
                    if st.button("Rerun Integrity Validation", key=f"rerun_integrity_{selected_run_id}", use_container_width=False):
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
        st.info("No registered experiment runs yet.")


def _render_experiment_evidence() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE)
    refresh_nonce = int(st.session_state.get("developer_workspace_refresh_nonce") or 0)
    cache_bust = str(refresh_nonce)
    catalog = list_experiment_catalog(cache_bust=cache_bust)
    selected_experiment = _selected_experiment(catalog, state_key="developer_workspace_evidence_experiment_id")
    selected_experiment_id = str(selected_experiment.get("experiment_id") or APPROVED_EXPERIMENT_ID)
    latest_validated = get_latest_validated_run_summary(experiment_id=selected_experiment_id, cache_bust=cache_bust) or {}
    validated_runs = eic_service.list_validated_experiment_summaries(limit=10, cache_bust=cache_bust, experiment_id=selected_experiment_id)

    st.markdown("### Experiment Evidence")
    st.caption(
        "Validated experiment governance for developers and data scientists. Use this page to review the selected experiment, compare evidence, inspect artifacts, and generate formal reports."
    )

    if latest_validated:
        top_cards = [
            ("Current Validated Run", str(latest_validated.get("run_id") or "none")),
            ("Run Status", get_run_status_display(str(latest_validated.get("run_status") or ""))),
            ("Integrity", get_integrity_status_display(str(latest_validated.get("integrity_status") or "not_run"))),
            ("Evidence", get_evidence_display(str(latest_validated.get("evidence_level") or latest_validated.get("evidence_verdict") or "not_available"))),
        ]
        cols = st.columns(4, gap="small")
        for col, (label, value) in zip(cols, top_cards):
            with col:
                st.markdown(_card(label, value), unsafe_allow_html=True)
    else:
        st.info("No validated experiment evidence is available yet.")

    evidence_tab, registry_tab, reports_tab = st.tabs(
        ["Validated Summary", "Registry and Artifacts", "Reports"]
    )

    with evidence_tab:
        if not latest_validated:
            st.info("A validated run is required before evidence details can be shown here.")
        else:
            run_id = str(latest_validated.get("run_id") or "")
            summary_rows = [
                ("Experiment", str(selected_experiment.get("display_label") or get_experiment_display_name(str(latest_validated.get("experiment_id") or selected_experiment_id)))),
                ("Dataset Size", str(int(latest_validated.get("included_row_count") or 0))),
                ("Positive Labels", str(int(latest_validated.get("positive_label_count") or 0))),
                ("Negative Labels", str(int(latest_validated.get("negative_label_count") or 0))),
                ("Teachers Represented", str(int(latest_validated.get("teachers_represented") or 0))),
                ("Recommended Business Action", get_business_action_display(str(latest_validated.get("recommended_business_action") or ""))),
            ]
            st.dataframe(pd.DataFrame(summary_rows, columns=["Field", "Value"]), use_container_width=True, hide_index=True)
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
                st.markdown("#### Model Comparison")
                st.dataframe(model_df, use_container_width=True, hide_index=True)

    with registry_tab:
        if validated_runs:
            registry_df = pd.DataFrame(
                [
                    {
                        "Run ID": str(row.get("run_id") or ""),
                        "Experiment": next((str(item.get("display_label") or item.get("name") or "") for item in catalog if str(item.get("experiment_id") or "") == str(row.get("experiment_id") or "")), get_experiment_display_name(str(row.get("experiment_id") or selected_experiment_id))),
                        "Run Status": get_run_status_display(str(row.get("run_status") or "")),
                        "Integrity": get_integrity_status_display(str(row.get("integrity_status") or "not_run")),
                        "Evidence": get_evidence_display(str(row.get("evidence_level") or row.get("evidence_verdict") or "not_available")),
                        "Included Rows": int(row.get("included_row_count") or 0),
                        "Positive Labels": int(row.get("positive_label_count") or 0),
                        "Negative Labels": int(row.get("negative_label_count") or 0),
                        "Primary Metric Leader": str(row.get("primary_metric_leader") or "—"),
                    }
                    for row in validated_runs
                ]
            )
            st.dataframe(registry_df, use_container_width=True, hide_index=True)
        else:
            st.info("No validated runs are available yet.")

        runs = list_experiment_runs(experiment_id=selected_experiment_id, limit=25, cache_bust=cache_bust)
        if runs:
            selected_run_id = st.selectbox(
                "Artifact Run Detail",
                [str(row.get("run_id") or "") for row in runs],
                key="developer_workspace_evidence_run_id",
            )
            selected_run = get_run(selected_run_id)
            if selected_run:
                retention = get_run_artifact_retention_status(selected_run_id)
                detail_cols = st.columns(4, gap="small")
                detail_cards = [
                    ("Run Status", get_run_status_display(str(selected_run.get("run_status") or ""))),
                    ("Integrity", get_integrity_status_display(str(selected_run.get("integrity_status") or "not_run"))),
                    ("Maturity", get_maturity_display(str(selected_run.get("maturity_verdict") or ""))),
                    ("Current Validated", _yes_no(bool(selected_run.get("is_current_validated_run")))),
                ]
                for col, (label, value) in zip(detail_cols, detail_cards):
                    with col:
                        st.markdown(_card(label, value), unsafe_allow_html=True)
                st.caption(f"Artifact retention: {retention.reason}")
                artifact_rows = list_run_artifacts(selected_run_id)
                _render_protected_artifacts(artifact_rows, key_prefix=f"evidence_{selected_run_id}")

    with reports_tab:
        if not latest_validated:
            st.info("Word reports become available after a final validated run exists.")
        else:
            run_id = str(latest_validated.get("run_id") or "")
            capabilities = {CAPABILITY_VIEW_TECHNICAL_ARTIFACTS} if has_capability(CAPABILITY_VIEW_TECHNICAL_ARTIFACTS) else set()
            report_rows = list_available_eic_reports(run_id, capabilities, language="en")
            for start in range(0, len(report_rows), 3):
                cols = st.columns(3, gap="medium")
                for col, report in zip(cols, report_rows[start : start + 3]):
                    report_type = str(report.get("report_type") or "")
                    report_status = str(report.get("status") or "not_available")
                    with col:
                        st.markdown(_card(str(report.get("title") or ""), report_status, str(report.get("description") or "")), unsafe_allow_html=True)
                        if report_status == "available" and not bool(report.get("download_ready")):
                            if st.button("Generate Word report", key=f"developer_workspace_generate_{run_id}_{report_type}", use_container_width=True):
                                result = get_or_create_validated_report(run_id, report_type, "en")
                                if result.get("ok"):
                                    st.rerun()
                                st.error(str(result.get("message") or "The Word report could not be generated from the current validated evidence."))
                        elif report_status == "available" and bool(report.get("download_ready")):
                            report_path = Path(str(report.get("path") or ""))
                            st.download_button(
                                label="Download Word report",
                                data=report_path.read_bytes(),
                                file_name=report_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key=f"developer_workspace_download_docx_{run_id}_{report_type}",
                            )
                        else:
                            st.caption(f"Availability: {report_status}")


def _render_telemetry_diagnostics() -> None:
    require_capability(CAPABILITY_VIEW_TELEMETRY_DIAGNOSTICS)
    health = load_telemetry_health_snapshot(
        teacher_id=str(get_authorization_context().user_id or "").strip(),
        days=int(st.selectbox("Telemetry window", [7, 14, 30], index=2, key="developer_workspace_telemetry_days")),
    )
    summary = health.get("summary") or {}
    cols = st.columns(4, gap="small")
    cards = [
        ("Exposures", str(int(summary.get("total_exposures") or 0))),
        ("Matched Opens", str(int(summary.get("exposures_with_matched_opens") or 0))),
        ("Unmatched Opens", str(int(summary.get("unmatched_opens") or 0))),
        ("Outcome Coverage", f"{float(summary.get('outcome_coverage') or 0.0):.1%}"),
    ]
    for col, (label, value) in zip(cols, cards):
        with col:
            st.markdown(_card(label, value), unsafe_allow_html=True)
    by_surface = health.get("by_surface") or []
    if by_surface:
        st.dataframe(_present_developer_table(by_surface), use_container_width=True, hide_index=True)
    else:
        st.info("No canonical telemetry rows were returned for the selected window.")


def _render_jobs() -> None:
    require_capability(CAPABILITY_VIEW_JOB_DIAGNOSTICS)
    jobs = list_jobs(limit=50, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if not jobs:
        st.info("No controlled jobs have been recorded yet.")
        return
    st.dataframe(pd.DataFrame(jobs), use_container_width=True, hide_index=True)


def _render_audit_log() -> None:
    require_capability(CAPABILITY_VIEW_AUDIT_LOG)
    actions = list_privileged_actions(limit=100, cache_bust=str(st.session_state.get("developer_workspace_refresh_nonce") or 0))
    if not actions:
        st.info("No privileged developer-workspace actions have been recorded yet.")
        return
    st.dataframe(pd.DataFrame(actions), use_container_width=True, hide_index=True)


def render_developer_workspace() -> None:
    require_capability(CAPABILITY_VIEW_DEVELOPER_WORKSPACE, message="Developer Workspace access requires a developer or data scientist staff role.")
    _inject_styles()
    context = get_authorization_context()
    chip_values = list(context.product_roles) + [get_staff_role_display(role) for role in context.staff_roles]
    chips = "".join(f"<span class='dev-chip'>{_html.escape(role)}</span>" for role in chip_values)
    st.markdown(
        f"""
        <div class="dev-hero">
            <div class="dev-title">Developer and Data Science Workspace</div>
            <div class="dev-subtitle">Controlled ML jobs, experiment registry, telemetry diagnostics, and audit evidence. This workspace does not change live recommendation ordering or deploy models.</div>
            <div class="dev-chip-row">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    overview_tab, lab_tab, evidence_tab, telemetry_tab, jobs_tab, audit_tab = st.tabs(
        ["Overview", "ML Evaluation Lab", "Experiment Evidence", "Telemetry Diagnostics", "Jobs", "Audit Log"]
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
