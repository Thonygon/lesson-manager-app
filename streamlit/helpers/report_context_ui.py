from __future__ import annotations

import streamlit as st

from core.i18n import t
from services.experiment_report_context_service import (
    get_report_context,
    report_context_completion,
    report_context_options,
    save_report_context,
)


def _humanize(value: str) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).strip().title()


def _option_label(group: str, value: str) -> str:
    key = f"report_context_option_{group}_{value}"
    translated = t(key)
    return translated if translated != key else _humanize(value)


def render_report_context_editor(*, run_id: str, experiment_id: str, language: str, key_prefix: str) -> dict:
    if not run_id:
        st.info(t("report_context_requires_validated_run"))
        return {}
    context = get_report_context(run_id, experiment_id, language)
    options = report_context_options()
    with st.expander(t("report_context_title"), expanded=False):
        st.caption(t("report_context_caption"))
        with st.form(key=f"{key_prefix}_report_context_form", clear_on_submit=False):
            st.markdown(f"**{t('report_context_section_business_reason')}**")
            purpose = st.selectbox(
                t("report_context_purpose"),
                [""] + list(options["purpose_key"]),
                index=([""] + list(options["purpose_key"])).index(str(context.get("purpose_key") or "")) if str(context.get("purpose_key") or "") in ([""] + list(options["purpose_key"])) else 0,
                format_func=lambda value: t("report_context_not_selected") if not value else _option_label("purpose", value),
            )
            decision_key = st.selectbox(
                t("report_context_decision_under_consideration"),
                [""] + list(options["decision_under_consideration_key"]),
                index=([""] + list(options["decision_under_consideration_key"])).index(str(context.get("decision_under_consideration_key") or "")) if str(context.get("decision_under_consideration_key") or "") in ([""] + list(options["decision_under_consideration_key"])) else 0,
                format_func=lambda value: t("report_context_not_selected") if not value else _option_label("decision", value),
            )
            audience_key = st.selectbox(
                t("report_context_audience"),
                [""] + list(options["audience_key"]),
                index=([""] + list(options["audience_key"])).index(str(context.get("audience_key") or "")) if str(context.get("audience_key") or "") in ([""] + list(options["audience_key"])) else 0,
                format_func=lambda value: t("report_context_not_selected") if not value else _option_label("audience", value),
            )
            business_problem = st.text_area(t("report_context_business_problem"), value=str(context.get("business_problem") or ""), height=90)
            decision_supported = st.text_area(t("report_context_decision_supported"), value=str(context.get("decision_supported") or ""), height=90)
            st.markdown(f"**{t('report_context_section_value')}**")
            expected_value = st.text_area(t("report_context_expected_value"), value=str(context.get("expected_value") or ""), height=80)
            product_impact = st.text_area(t("report_context_product_impact"), value=str(context.get("product_impact") or ""), height=80)
            success_definition = st.text_area(t("report_context_success_definition"), value=str(context.get("success_definition") or ""), height=80)
            minimum_evidence_required = st.text_area(t("report_context_minimum_evidence_required"), value=str(context.get("minimum_evidence_required") or ""), height=80)
            st.markdown(f"**{t('report_context_section_risk')}**")
            risks = st.text_area(t("report_context_risks"), value=str(context.get("risks") or ""), height=80)
            main_limitation = st.text_area(t("report_context_main_limitation"), value=str(context.get("main_limitation") or ""), height=80)
            evidence_non_proof = st.text_area(t("report_context_evidence_non_proof"), value=str(context.get("evidence_non_proof") or ""), height=80)
            st.markdown(f"**{t('report_context_section_actions')}**")
            recommended_next_action = st.text_area(t("report_context_recommended_next_action"), value=str(context.get("recommended_next_action") or ""), height=80)
            next_review_trigger = st.text_area(t("report_context_next_review_trigger"), value=str(context.get("next_review_trigger") or ""), height=70)
            next_review_date = st.text_input(t("report_context_next_review_date"), value=str(context.get("next_review_date") or ""))
            responsible_person_or_team = st.text_input(t("report_context_responsible_person_or_team"), value=str(context.get("responsible_person_or_team") or ""))
            st.markdown(f"**{t('report_context_section_notes')}**")
            meeting_notes = st.text_area(t("report_context_meeting_notes"), value=str(context.get("meeting_notes") or ""), height=90)
            submitted = st.form_submit_button(t("report_context_save"), use_container_width=True)
        if submitted:
            saved_context = save_report_context(
                {
                    "run_id": run_id,
                    "experiment_id": experiment_id,
                    "language": language,
                    "purpose_key": purpose,
                    "decision_under_consideration_key": decision_key,
                    "audience_key": audience_key,
                    "business_problem": business_problem,
                    "decision_supported": decision_supported,
                    "expected_value": expected_value,
                    "product_impact": product_impact,
                    "success_definition": success_definition,
                    "minimum_evidence_required": minimum_evidence_required,
                    "risks": risks,
                    "main_limitation": main_limitation,
                    "evidence_non_proof": evidence_non_proof,
                    "recommended_next_action": recommended_next_action,
                    "next_review_trigger": next_review_trigger,
                    "next_review_date": next_review_date,
                    "responsible_person_or_team": responsible_person_or_team,
                    "meeting_notes": meeting_notes,
                }
            )
            storage_status = str(saved_context.get("_storage_status") or "supabase")
            if storage_status == "local_cache":
                st.warning(t("report_context_saved_local_cache"))
            else:
                st.success(t("report_context_saved"))
            st.rerun()
    return context


def render_report_context_summary(*, run_id: str, experiment_id: str, language: str, key_prefix: str) -> dict:
    if not run_id:
        st.info(t("report_context_requires_validated_run"))
        return {}
    context = get_report_context(run_id, experiment_id, language)
    completion = report_context_completion(context)
    with st.expander(t("report_context_summary_title"), expanded=False):
        st.caption(t("report_context_summary_caption"))
        rows = [
            (t("report_context_purpose"), _option_label("purpose", str(context.get("purpose_key") or "")) if str(context.get("purpose_key") or "") else t("report_context_not_selected")),
            (
                t("report_context_decision_under_consideration"),
                _option_label("decision", str(context.get("decision_under_consideration_key") or ""))
                if str(context.get("decision_under_consideration_key") or "")
                else t("report_context_not_selected"),
            ),
            (t("report_context_audience"), _option_label("audience", str(context.get("audience_key") or "")) if str(context.get("audience_key") or "") else t("report_context_not_selected")),
            (t("report_context_business_problem"), str(context.get("business_problem") or "") or "—"),
            (t("report_context_decision_supported"), str(context.get("decision_supported") or "") or "—"),
            (t("report_context_expected_value"), str(context.get("expected_value") or "") or "—"),
            (t("report_context_product_impact"), str(context.get("product_impact") or "") or "—"),
            (t("report_context_success_definition"), str(context.get("success_definition") or "") or "—"),
            (t("report_context_minimum_evidence_required"), str(context.get("minimum_evidence_required") or "") or "—"),
            (t("report_context_risks"), str(context.get("risks") or "") or "—"),
            (t("report_context_main_limitation"), str(context.get("main_limitation") or "") or "—"),
            (t("report_context_evidence_non_proof"), str(context.get("evidence_non_proof") or "") or "—"),
            (t("report_context_recommended_next_action"), str(context.get("recommended_next_action") or "") or "—"),
            (t("report_context_next_review_trigger"), str(context.get("next_review_trigger") or "") or "—"),
            (t("report_context_next_review_date"), str(context.get("next_review_date") or "") or "—"),
            (t("report_context_responsible_person_or_team"), str(context.get("responsible_person_or_team") or "") or "—"),
            (t("report_context_meeting_notes"), str(context.get("meeting_notes") or "") or "—"),
            (t("report_context_saved_by"), str(context.get("created_by") or "") or "—"),
            (t("report_context_saved_at"), str(context.get("updated_at") or context.get("created_at") or "") or "—"),
            (
                t("report_context_completion_status"),
                t("report_context_completion_value", completed=int(completion.get("completed_fields") or 0), total=int(completion.get("total_fields") or 0)),
            ),
        ]
        st.dataframe(
            [{"field": label, "value": value} for label, value in rows],
            use_container_width=True,
            hide_index=True,
            column_config={"field": t("admin_field_label"), "value": t("admin_value_label")},
            key=f"{key_prefix}_report_context_summary",
        )
        st.caption(t("report_context_summary_admin_note"))
    return context
