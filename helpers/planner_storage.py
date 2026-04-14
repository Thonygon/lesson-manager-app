# CLASSIO — Planner Storage (Full Replacement)
# ============================================================
import html
import math
import os
import re
from datetime import datetime as _dt, timezone
from io import BytesIO
from typing import Optional

import pandas as pd
import streamlit as st
from core.database import clear_app_caches, get_sb, load_table
from core.i18n import t
from core.navigation import go_to
from core.state import get_current_user_id, with_owner
from core.timezone import get_app_tz, today_local
from helpers.archive_utils import ACTIVE_STATUS, ARCHIVED_STATUS, filter_archived_rows, is_archived_status
from reportlab.lib.enums import TA_CENTER

# ============================================================
# Cleanup helpers
# ============================================================
_PLAN_KEY_PATTERNS = [
    "core_material.pre_task_questions",
    "core_material.gist_questions",
    "core_material.detail_questions",
    "core_material.target_vocabulary",
    "core_material.post_task",
    "core_material.worked_example",
    "core_material.independent_practice",
    "core_material.common_error_alert",
    "core_material.concept_explanation",
    "core_material.real_life_application",
    "core_material.strategy_steps",
    "core_material.performance_goal",
    "core_material.materials_needed",
    "core_material.expected_output",
    "core_material.timing_guide",
    "core_material.differentiation",
    "core_material.assessment_check",
    "core_material.student_checklist",
    "core_material.key_concept",
    "core_material.guided_problem_set",
    "core_material.independent_problem_set",
    "core_material.challenge_problem",
    "core_material.answer_key",
    "core_material.phenomenon_prompt",
    "core_material.prediction_task",
    "core_material.observation_task",
    "core_material.evidence_questions",
    "core_material.misconception_alert",
    "core_material.technical_focus",
    "core_material.practice_pattern",
    "core_material.teacher_model",
    "core_material.strategy_name",
    "core_material.model_scenario",
    "core_material.student_action_plan",
    "core_material.language_frames",
    "core_material",
    "reading_passage",
    "listening_script",
    "gist_questions",
    "detail_questions",
    "pre_task_questions",
    "target_vocabulary",
    "post_task",
    "materials_needed",
    "expected_output",
    "timing_guide",
    "differentiation",
    "assessment_check",
    "student_checklist",
    "key_concept",
    "guided_problem_set",
    "independent_problem_set",
    "challenge_problem",
    "answer_key",
    "phenomenon_prompt",
    "prediction_task",
    "observation_task",
    "evidence_questions",
    "misconception_alert",
    "technical_focus",
    "practice_pattern",
    "teacher_model",
    "strategy_name",
    "model_scenario",
    "student_action_plan",
]


def _lp():
    """Lazy import to avoid circular dependency with lesson_planner."""
    import helpers.lesson_planner as lp

    return lp


def _fallback_label(key: str) -> str:
    return str(key or "").replace("_", " ").strip().capitalize()


def _clean_plan_text(text: str) -> str:
    """Replace code-like key references with translated labels in plan content."""
    if not text:
        return text

    for pat in _PLAN_KEY_PATTERNS:
        tkey = pat.split(".")[-1]
        translated = t(tkey)
        if not translated or translated == tkey:
            translated = _fallback_label(tkey)

        text = text.replace(f"'{pat}'", translated)
        text = text.replace(f'"{pat}"', translated)
        text = text.replace(f"`{pat}`", translated)

        for variant in [pat, tkey]:
            text = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(variant)}(?![A-Za-z0-9_])",
                translated,
                text,
            )

    return text


def _clean_plan_data(plan: dict) -> dict:
    """Deep-clean all string values in a plan dict."""
    out = {}
    for k, v in (plan or {}).items():
        if isinstance(v, str):
            out[k] = _clean_plan_text(v)
        elif isinstance(v, list):
            out[k] = [_clean_plan_text(i) if isinstance(i, str) else i for i in v]
        elif isinstance(v, dict):
            out[k] = _clean_plan_data(v)
        else:
            out[k] = v
    return out


def _clean_display_text(text: str) -> str:
    s = str(text or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,!?;:])", r"\1", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s:
        s = s[0].upper() + s[1:]
    return s


# ============================================================
# Display helpers
# ============================================================


def _inject_planner_result_css() -> None:
    st.markdown(
        """
        <style>
        .cl-plan-group-title {
            margin: 1.15rem 0 0.35rem 0;
            font-size: 1.08rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            color: var(--text, var(--text-color));
        }
        .cl-plan-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 0.35rem 0 0.85rem 0;
        }
        .cl-plan-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border-radius: 999px;
            padding: 6px 10px;
            border: 1px solid var(--border, rgba(120, 140, 170, 0.18));
            background: color-mix(in srgb, var(--panel, rgba(255,255,255,0.08)) 72%, #3B82F6 28%);
            color: var(--text, var(--text-color));
            font-size: 0.83rem;
            line-height: 1;
            box-shadow: var(--shadow-sm, none);
        }
        .cl-plan-small-note {
            color: var(--muted, var(--text-color));
            opacity: 0.88;
            font-size: 0.88rem;
        }
        .cl-plan-callout {
            border-left: 4px solid var(--primary, #3B82F6);
            background: color-mix(in srgb, var(--panel-soft, rgba(59,130,246,0.06)) 88%, var(--primary, #3B82F6) 12%);
            color: var(--text, var(--text-color));
            padding: 10px 12px;
            border-radius: 10px;
            margin: 0.35rem 0 0.55rem 0;
        }
        .cl-plan-inline-box {
            background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.08)), var(--panel-2, rgba(255,255,255,0.04)));
            border: 1px solid var(--border, rgba(120, 140, 170, 0.18));
            border-radius: 14px;
            padding: 0.85rem 0.95rem;
            margin: 0.15rem 0 0.8rem 0;
            box-shadow: var(--shadow-sm, none);
            color: var(--text, var(--text-color));
        }
        .cl-plan-inline-box strong {
            color: var(--text, var(--text-color));
        }
        div[data-testid="stExpander"] .cl-plan-expander-note {
            margin-top: -0.1rem;
        }
        /* Theme-aware expanders for planner sections */
        div[data-testid="stExpander"].cl-plan-expander,
        .cl-plan-expander + div[data-testid="stExpander"] {
            border-radius: 16px !important;
            border: 1px solid var(--border, rgba(120, 140, 170, 0.18)) !important;
            background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.08)), var(--panel-2, rgba(255,255,255,0.04))) !important;
            box-shadow: var(--shadow-sm, none) !important;
            overflow: hidden !important;
            margin-bottom: 0.8rem !important;
        }
        div[data-testid="stExpander"] summary {
            font-weight: 800 !important;
            color: var(--text, var(--text-color)) !important;
        }
        div[data-testid="stExpander"] details[open] summary {
            border-bottom: 1px solid var(--border, rgba(120, 140, 170, 0.18)) !important;
            margin-bottom: 0.6rem !important;
        }
        div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
            color: var(--text, var(--text-color)) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _canonical_subject_display(subject: str) -> str:
    """Return a consistent Title Case English label for storage.

    Always language-independent so the DB column stays clean.
    Translated labels are computed at display time instead.
    """
    s = str(subject or "").strip()
    if not s:
        return ""
    return _clean_display_text(s.replace("_", " "))


def _translated_subject_display(subject: str) -> str:
    """Return a UI-language-translated label (for display only, NOT for DB storage)."""
    s = str(subject or "").strip()
    if not s:
        return ""

    canonical = s.lower()
    if canonical in getattr(_lp(), "QUICK_SUBJECTS", []):
        return _lp().subject_label(canonical)
    return _clean_display_text(s)


def _translated_level_display(level_or_band: str) -> str:
    s = str(level_or_band or "").strip()
    if not s:
        return ""
    return s if s in getattr(_lp(), "LANGUAGE_LEVELS", []) else t(s)


def _translated_stage_display(stage: str) -> str:
    s = str(stage or "").strip()
    return t(s) if s else ""


def _translated_purpose_display(purpose: str) -> str:
    s = str(purpose or "").strip()
    return t(s) if s else ""


def _safe_title_from_plan(plan: dict) -> str:
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str(plan.get("title") or "lesson_plan").strip())
    return safe_title or "lesson_plan"


def _has_any_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _normalize_list_for_display(items) -> list[str]:
    if items is None:
        return []
    if isinstance(items, list):
        return [str(x).strip() for x in items if str(x).strip()]
    if isinstance(items, str):
        text = items.strip()
        if not text:
            return []
        parts = [line.strip() for line in text.splitlines() if line.strip()]
        return parts if len(parts) > 1 else [text]
    return [str(items).strip()]


def _write_list(items) -> None:
    for item in _normalize_list_for_display(items):
        st.write(f"- {item}")


def _render_meta_chip_row(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    mode_label: str,
    material_language: str = "",
) -> None:
    chips = []
    if subject:
        chips.append(f"📚 {_translated_subject_display(subject)}")
    if learner_stage:
        chips.append(f"👥 {_translated_stage_display(learner_stage)}")
    if level_or_band:
        chips.append(f"🏷️ {_translated_level_display(level_or_band)}")
    if lesson_purpose:
        chips.append(f"🎯 {_translated_purpose_display(lesson_purpose)}")
    if mode_label:
        chips.append(f"⚙️ {mode_label}")
    if material_language:
        chips.append(f"🌐 {str(material_language).upper()}")

    if not chips:
        return

    chip_html = "".join([f'<span class="cl-plan-chip">{html.escape(chip)}</span>' for chip in chips])
    st.markdown(f'<div class="cl-plan-chip-row">{chip_html}</div>', unsafe_allow_html=True)


def _render_text_block(value: str) -> None:
    if _has_any_value(value):
        st.write(str(value))


def _render_textarea_block(label: str, value: str, key: str, height: int = 190) -> None:
    if _has_any_value(value):
        st.text_area(label, value=value, height=height, key=key)


def _render_inline_box(title: str, value) -> None:
    if not _has_any_value(value):
        return
    st.markdown(
        f'<div class="cl-plan-inline-box"><strong>{html.escape(title)}</strong></div>',
        unsafe_allow_html=True,
    )
    if isinstance(value, list):
        _write_list(value)
    else:
        _render_text_block(str(value))


def _render_material_body(label: str, value, style: str, section_key: str, action_key_prefix: str) -> None:
    if style == "list_inline":
        st.write(", ".join([str(x) for x in value]))
    elif style == "list":
        _write_list(value)
    elif style == "textarea":
        _render_textarea_block(label, str(value), key=f"{action_key_prefix}_{section_key}_view")
    elif style == "callout":
        st.markdown(
            f'<div class="cl-plan-callout">{html.escape(str(value))}</div>',
            unsafe_allow_html=True,
        )
    elif style == "list_or_text":
        if isinstance(value, list):
            _write_list(value)
        else:
            _render_text_block(str(value))
    else:
        _render_text_block(str(value))


def _material_groups(plan: dict) -> list[tuple[str, object, str]]:
    cm = plan.get("core_material", {}) or {}
    return [
        ("target_vocabulary", cm.get("target_vocabulary"), "list_inline"),
        ("language_frames", cm.get("language_frames"), "list"),
        ("pre_task_questions", cm.get("pre_task_questions"), "list"),
        ("reading_passage", plan.get("reading_passage"), "textarea"),
        ("listening_script", plan.get("listening_script"), "textarea"),
        ("gist_questions", cm.get("gist_questions"), "list"),
        ("detail_questions", cm.get("detail_questions"), "list"),
        ("worked_example", cm.get("worked_example"), "list"),
        ("independent_practice", cm.get("independent_practice"), "list"),
        ("common_error_alert", cm.get("common_error_alert"), "callout"),
        ("concept_explanation", cm.get("concept_explanation"), "text"),
        ("real_life_application", cm.get("real_life_application"), "text"),
        ("strategy_steps", cm.get("strategy_steps"), "list"),
        ("performance_goal", cm.get("performance_goal"), "text"),
        ("materials_needed", cm.get("materials_needed"), "list_or_text"),
        ("timing_guide", cm.get("timing_guide"), "list_or_text"),
        ("expected_output", cm.get("expected_output"), "text"),
        ("differentiation", cm.get("differentiation"), "list_or_text"),
        ("assessment_check", cm.get("assessment_check"), "list_or_text"),
        ("student_checklist", cm.get("student_checklist"), "list"),
        ("key_concept", cm.get("key_concept"), "text"),
        ("guided_problem_set", cm.get("guided_problem_set"), "list"),
        ("independent_problem_set", cm.get("independent_problem_set"), "list"),
        ("challenge_problem", cm.get("challenge_problem"), "list_or_text"),
        ("answer_key", cm.get("answer_key"), "list_or_text"),
        ("phenomenon_prompt", cm.get("phenomenon_prompt"), "text"),
        ("prediction_task", cm.get("prediction_task"), "list_or_text"),
        ("observation_task", cm.get("observation_task"), "list_or_text"),
        ("evidence_questions", cm.get("evidence_questions"), "list"),
        ("misconception_alert", cm.get("misconception_alert"), "callout"),
        ("technical_focus", cm.get("technical_focus"), "text"),
        ("practice_pattern", cm.get("practice_pattern"), "list_or_text"),
        ("teacher_model", cm.get("teacher_model"), "list_or_text"),
        ("strategy_name", cm.get("strategy_name"), "text"),
        ("model_scenario", cm.get("model_scenario"), "text"),
        ("student_action_plan", cm.get("student_action_plan"), "list_or_text"),
        ("post_task", cm.get("post_task"), "text"),
    ]


# ============================================================
# Community search
# ============================================================


def _find_community_plan_for_other(
    subject_name: str,
    topic: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
) -> Optional[dict]:
    """
    Searches the public library for a plan matching the given real subject name and topic.
    Prefers plans that also match stage/level/purpose.
    Returns the best-matching row dict, or None if not found.
    """
    try:
        df = load_public_lesson_plans()
        if df is None or df.empty:
            return None

        subject_norm = str(subject_name or "").strip().casefold()
        topic_norm = str(topic or "").strip().casefold()
        mask_subject = df["subject"].astype(str).str.strip().str.casefold() == subject_norm
        mask_topic = df["topic"].astype(str).str.strip().str.casefold() == topic_norm

        matches = df[mask_subject & mask_topic].copy()
        if matches.empty:
            return None

        def _score(row):
            score = 0
            if str(row.get("learner_stage", "")).strip() == str(learner_stage).strip():
                score += 1
            if str(row.get("level_or_band", "")).strip() == str(level_or_band).strip():
                score += 1
            if str(row.get("lesson_purpose", "")).strip() == str(lesson_purpose).strip():
                score += 1
            return score

        matches["_score"] = matches.apply(_score, axis=1)
        best = matches.sort_values(["_score", "created_at"], ascending=[False, False]).iloc[0]
        return best.to_dict()
    except Exception:
        return None


# ============================================================
# Persistence / loading
# ============================================================


def planner_payload_from_inputs(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
    mode: str,
    plan: dict,
) -> dict:
    from helpers.branding import get_user_branding, resolve_is_public

    branding = get_user_branding()

    return with_owner(
        {
            "subject": str(subject).strip(),
            "topic": _clean_display_text(topic),
            "learner_stage": str(learner_stage).strip(),
            "level_or_band": str(level_or_band).strip(),
            "lesson_purpose": str(lesson_purpose).strip(),
            "plan_language": str(plan.get("plan_language") or _lp().get_plan_language()).strip(),
            "student_material_language": str(plan.get("student_material_language") or "").strip(),
            "source_type": "ai" if str(mode).strip().lower() == "ai" else "template",
            "planner_mode": mode,
            "plan_json": plan,
            "title": _clean_display_text(plan.get("title") or ""),
            "author_name": str(st.session_state.get("user_name") or t("unknown")).strip(),
            "subject_display": _canonical_subject_display(subject),
            "is_public": resolve_is_public(branding),
            "status": ACTIVE_STATUS,
            "created_at": _dt.now(timezone.utc).isoformat(),
        }
    )


def save_lesson_plan_record(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
    mode: str,
    plan: dict,
) -> bool:
    try:
        payload = planner_payload_from_inputs(
            subject=subject,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
            lesson_purpose=lesson_purpose,
            topic=topic,
            mode=mode,
            plan=plan,
        )
        try:
            get_sb().table("lesson_plans").insert(payload).execute()
        except Exception as inner_exc:
            if "status" not in str(inner_exc).lower():
                raise
            legacy_payload = dict(payload)
            legacy_payload.pop("status", None)
            get_sb().table("lesson_plans").insert(legacy_payload).execute()
        return True
    except Exception as e:
        st.warning(f"{t('could_not_save_lesson_plan')}: {e}")
        return False


def load_my_lesson_plans(*, include_archived: bool = False, archived_only: bool = False) -> pd.DataFrame:
    try:
        df = load_table("lesson_plans")
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        if "created_at" in df.columns:
            df = df.sort_values("created_at", ascending=False, na_position="last")

        return filter_archived_rows(
            df,
            include_archived=include_archived,
            archived_only=archived_only,
        )
    except Exception as e:
        st.error(f"{t('could_not_load_your_lesson_plans')}: {e}")
        return pd.DataFrame()


def load_public_lesson_plans() -> pd.DataFrame:
    try:
        res = (
            get_sb().table("lesson_plans").select("*").eq("is_public", True).order("created_at", desc=True).limit(500).execute()
        )
        df = pd.DataFrame(res.data or [])
        if df.empty:
            return pd.DataFrame()

        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        return filter_archived_rows(df)
    except Exception as e:
        st.error(f"{t('could_not_load_community_lesson_plans')}: {e}")
        return pd.DataFrame()


def format_plan_datetime(value) -> str:
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return ""
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def safe_plan_label(value: str, prefix: str = "") -> str:
    s = str(value or "").strip()
    return f"{prefix}{s}" if s else ""


def _is_public_value(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "public"}


def update_lesson_plan_visibility(plan_id, is_public: bool) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid:
        return False, "auth_required"
    safe_plan_id = plan_id
    if isinstance(plan_id, str):
        stripped = plan_id.strip()
        if not stripped:
            return False, "invalid_id"
        safe_plan_id = int(stripped) if stripped.isdigit() else stripped
    elif plan_id is None:
        return False, "invalid_id"
    try:
        res = (
            get_sb()
            .table("lesson_plans")
            .select("id, user_id")
            .eq("id", safe_plan_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return False, "not_found"
        if str(rows[0].get("user_id") or "").strip() != uid:
            return False, "not_owner"
        (
            get_sb()
            .table("lesson_plans")
            .update({"is_public": bool(is_public)})
            .eq("id", safe_plan_id)
            .eq("user_id", uid)
            .execute()
        )
        clear_app_caches()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def update_lesson_plan_archive(plan_id, archived: bool) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid:
        return False, "auth_required"
    safe_plan_id = plan_id
    if isinstance(plan_id, str):
        stripped = plan_id.strip()
        if not stripped:
            return False, "invalid_id"
        safe_plan_id = int(stripped) if stripped.isdigit() else stripped
    elif plan_id is None:
        return False, "invalid_id"
    payload = {
        "status": ARCHIVED_STATUS if archived else ACTIVE_STATUS,
        "is_public": False,
    }
    try:
        (
            get_sb()
            .table("lesson_plans")
            .update(payload)
            .eq("id", safe_plan_id)
            .eq("user_id", uid)
            .execute()
        )
        from helpers.teacher_student_integration import update_assignment_source_archive_state

        update_assignment_source_archive_state(
            assignment_type="lesson_plan_topic",
            source_type="lesson_plan_builder",
            source_record_id=safe_plan_id,
            archived=archived,
        )
        clear_app_caches()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _open_plan_library_record(
    row: dict,
    *,
    open_in_files: bool = False,
    require_signup: bool = False,
    expand_assign: bool = False,
) -> None:
    if require_signup:
        st.session_state["_post_signup_open_panel"] = "files"
        st.session_state["_post_signup_open_tab"] = "community_library"
        st.session_state["_explore_go_signup"] = True
        st.rerun()

    st.session_state["files_selected_plan"] = row.get("plan_json") or {}
    st.session_state["files_selected_subject"] = str(row.get("subject") or "").strip()
    st.session_state["files_selected_stage"] = str(row.get("learner_stage") or "").strip()
    st.session_state["files_selected_level"] = str(row.get("level_or_band") or "").strip()
    st.session_state["files_selected_purpose"] = str(row.get("lesson_purpose") or "").strip()
    st.session_state["files_selected_topic"] = _clean_display_text(row.get("topic") or "")
    st.session_state["files_selected_source_type"] = str(row.get("source_type") or "").strip()
    st.session_state["files_selected_title"] = _clean_display_text(row.get("title") or t("untitled_plan"))
    st.session_state["files_selected_plan_id"] = row.get("id")
    st.session_state["files_selected_plan_status"] = str(row.get("status") or "").strip()
    st.session_state["files_selected_plan_assign_expanded"] = bool(expand_assign)

    if open_in_files:
        go_to("resources")
    else:
        st.toast(t("scroll_down_to_view"))
    st.rerun()


# ============================================================
# Library cards
# ============================================================


def render_plan_library_cards(
    df: pd.DataFrame,
    prefix: str,
    show_author: bool = False,
    open_in_files: bool = False,
    require_signup: bool = False,
    allow_visibility_toggle: bool = False,
    allow_archive_toggle: bool = False,
) -> None:
    if df is None or df.empty:
        return

    rows = df.reset_index(drop=True).to_dict("records")

    for idx in range(0, len(rows), 2):
        pair = rows[idx : idx + 2]
        cols = st.columns(2, gap="medium")

        for col_idx, row in enumerate(pair):
            row_id = row.get("id", idx + col_idx)
            plan_id = row.get("id")
            title = _clean_display_text(row.get("title") or t("untitled_plan"))
            subject = str(row.get("subject") or "").strip()
            topic = _clean_display_text(row.get("topic") or "")
            learner_stage = str(row.get("learner_stage") or "").strip()
            level_or_band = str(row.get("level_or_band") or "").strip()
            lesson_purpose = str(row.get("lesson_purpose") or "").strip()
            source_type = str(row.get("source_type") or "").strip()
            author_name = str(row.get("author_name") or "").strip()
            created_at = format_plan_datetime(row.get("created_at"))
            is_archived = is_archived_status(row.get("status"))

            subject_label = _translated_subject_display(subject)
            level_label = _translated_level_display(level_or_band)
            purpose_label = _translated_purpose_display(lesson_purpose)
            stage_label = _translated_stage_display(learner_stage)
            source_label = t("mode_ai") if source_type == "ai" else t("mode_template")
            visibility_label = t("public_label") if _is_public_value(row.get("is_public")) else t("private_label")

            safe_title = html.escape(title)
            safe_author = html.escape(author_name)
            preview_text = html.escape((topic or t("no_description_available"))[:180])

            chips = "".join(
                [
                    f'<span class="cm-resource-chip">📚 {html.escape(subject_label)}</span>' if subject_label else "",
                    f'<span class="cm-resource-chip">🎯 {html.escape(purpose_label)}</span>' if purpose_label else "",
                    f'<span class="cm-resource-chip">👥 {html.escape(stage_label)}</span>' if stage_label else "",
                    f'<span class="cm-resource-chip">🏷️ {html.escape(level_label)}</span>' if level_label else "",
                    f'<span class="cm-resource-chip">⚙️ {html.escape(source_label)}</span>' if source_label else "",
                ]
            )

            meta = "".join(
                [
                    f'<div class="cm-resource-meta">⚙️ {html.escape(visibility_label)}</div>',
                    f'<div class="cm-resource-meta">🗂️ {html.escape(t("archived_label"))}</div>' if is_archived else "",
                    f'<div class="cm-resource-meta">👤 {safe_author}</div>' if show_author and author_name else "",
                    f'<div class="cm-resource-meta">🕒 {html.escape(created_at)}</div>' if created_at else "",
                ]
            )

            card_html = (
                f'<div class="cm-resource-card cm-resource-plan">'
                f'<div class="cm-resource-card__title">{safe_title}</div>'
                f'<div class="cm-resource-chip-row">{chips}</div>'
                f'<div class="cm-resource-preview">{preview_text}</div>'
                f"{meta}"
                f"</div>"
            )

            with cols[col_idx]:
                st.markdown(card_html, unsafe_allow_html=True)
                is_owner = str(row.get("user_id") or "").strip() == str(get_current_user_id() or "").strip()
                show_owner_controls = allow_visibility_toggle or allow_archive_toggle
                action_cols = st.columns([1, 1, 1, 1] if show_owner_controls else [1, 1])
                with action_cols[0]:
                    if st.button(
                        t("view_plan"),
                        key=f"{prefix}_view_{row_id}_{idx}_{col_idx}",
                        use_container_width=True,
                    ):
                        _open_plan_library_record(
                            row,
                            open_in_files=open_in_files,
                            require_signup=False,
                            expand_assign=False,
                        )
                with action_cols[1]:
                    if not show_owner_controls or not is_archived:
                        if st.button(
                            t("assign_to_student"),
                            key=f"{prefix}_assign_{row_id}_{idx}_{col_idx}",
                            use_container_width=True,
                        ):
                            _open_plan_library_record(
                                row,
                                open_in_files=open_in_files,
                                require_signup=require_signup,
                                expand_assign=True,
                            )
                if show_owner_controls:
                    with action_cols[2]:
                        if allow_visibility_toggle and is_owner and str(plan_id or "").strip() and not is_archived:
                            current_public = _is_public_value(row.get("is_public"))
                            toggle_key = re.sub(r"[^A-Za-z0-9._-]+", "_", str(plan_id or "").strip()) or f"{idx}_{col_idx}"
                            new_public = st.toggle(
                                t("public_toggle_label"),
                                value=current_public,
                                key=f"{prefix}_toggle_visibility_{toggle_key}_{idx}_{col_idx}",
                            )
                            if new_public != current_public:
                                ok, msg = update_lesson_plan_visibility(plan_id, new_public)
                                if ok:
                                    st.success(
                                        t(
                                            "resource_visibility_updated",
                                            visibility=t("public_label") if new_public else t("private_label"),
                                        )
                                    )
                                    st.rerun()
                                st.error(t("resource_visibility_update_failed", error=msg))
                    with action_cols[3]:
                        if allow_archive_toggle and is_owner and str(plan_id or "").strip():
                            toggle_key = re.sub(r"[^A-Za-z0-9._-]+", "_", str(plan_id or "").strip()) or f"{idx}_{col_idx}"
                            new_archived = st.toggle(
                                t("archive_toggle_label"),
                                value=is_archived,
                                key=f"{prefix}_toggle_archive_{toggle_key}_{idx}_{col_idx}",
                            )
                            if new_archived != is_archived:
                                ok, msg = update_lesson_plan_archive(plan_id, new_archived)
                                if ok:
                                    st.success(
                                        t(
                                            "resource_archive_updated",
                                            state=t("archived_label") if new_archived else t("restored_label"),
                                        )
                                    )
                                    st.rerun()
                                st.error(t("resource_archive_update_failed", error=msg))


# ============================================================
# Logs / usage
# ============================================================


def log_user_activity(
    activity_type: str,
    feature_name: str,
    meta: Optional[dict] = None,
) -> None:
    try:
        payload = with_owner(
            {
                "activity_type": str(activity_type or "").strip() or "unknown",
                "feature_name": str(feature_name or "").strip() or "unknown",
                "meta_json": meta or {},
                "created_at": _dt.now(timezone.utc).isoformat(),
            }
        )
        get_sb().table("user_activity_log").insert(payload).execute()
    except Exception as e:
        st.warning(f"user_activity_log insert failed: {e}")


def log_ai_usage(
    request_kind: str,
    status: str,
    meta: Optional[dict] = None,
) -> None:
    try:
        payload = with_owner(
            {
                "feature_name": str(request_kind).strip(),
                "status": str(status).strip(),
                "meta_json": meta or {},
                "created_at": _dt.now(timezone.utc).isoformat(),
            }
        )
        get_sb().table("ai_usage_logs").insert(payload).execute()
        clear_app_caches()
    except Exception as e:
        st.warning(f"ai_usage_logs insert failed: {e}")


def _safe_ai_logs_df() -> pd.DataFrame:
    try:
        df = load_table("ai_usage_logs")
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    if "created_at" not in df.columns:
        df["created_at"] = None
    if "status" not in df.columns:
        df["status"] = ""
    if "feature_name" not in df.columns:
        df["feature_name"] = ""

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["feature_name"] = df["feature_name"].fillna("").astype(str).str.strip().str.lower()
    return df


def get_ai_planner_usage_status() -> dict:
    df = _safe_ai_logs_df()
    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(today_local(), _dt.min.time()).replace(tzinfo=get_app_tz()).astimezone(timezone.utc)

    if df.empty:
        return {
            "used_today": 0,
            "remaining_today": _lp().AI_DAILY_LIMIT,
            "cooldown_ok": True,
            "seconds_left": 0,
            "last_request_at": None,
        }

    planner_df = df[(df["feature_name"] == "quick_lesson_ai") & (df["status"] == "success")].copy()
    today_df = planner_df[(planner_df["created_at"].notna()) & (planner_df["created_at"] >= today_start_utc)].copy()
    used_today = int(len(today_df))

    cooldown_df = df[df["feature_name"] == "quick_lesson_ai"].dropna(subset=["created_at"]).sort_values("created_at")
    cooldown_ok = True
    seconds_left = 0
    last_request_at = None

    if not cooldown_df.empty:
        last_request_at = cooldown_df.iloc[-1]["created_at"]
        delta = (now_utc - last_request_at.to_pydatetime()).total_seconds()
        if delta < _lp().AI_COOLDOWN_SECONDS:
            cooldown_ok = False
            seconds_left = int(math.ceil(_lp().AI_COOLDOWN_SECONDS - delta))

    return {
        "used_today": used_today,
        "remaining_today": max(0, _lp().AI_DAILY_LIMIT - used_today),
        "cooldown_ok": cooldown_ok,
        "seconds_left": max(0, seconds_left),
        "last_request_at": last_request_at,
    }


# ============================================================
# Streamlit plan renderer
# ============================================================


def render_quick_lesson_plan_result(
    plan: dict,
    subject: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    lesson_purpose: str = "",
    topic: str = "",
    read_only: bool = False,
    allow_assign: bool = False,
    assign_expanded: bool = False,
    resource_record_id: int | str | None = None,
    action_key_prefix: str = "quick_plan",
    signup_required_actions: bool = False,
) -> None:
    _inject_planner_result_css()
    plan = _clean_plan_data(plan)

    if not read_only:
        st.success(t("lesson_plan_ready"))

    resolved_mode = st.session_state.get("quick_lesson_plan_mode_used", "template")
    warning_msg = st.session_state.get("quick_lesson_plan_warning")
    mode_label = t("mode_ai") if str(resolved_mode).strip().lower() == "ai" else t("mode_template")

    if warning_msg:
        st.warning(warning_msg)

    st.markdown(f"### {t('plan_title')}: {plan.get('title', '')}")
    _render_meta_chip_row(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        lesson_purpose=lesson_purpose,
        mode_label=mode_label,
        material_language=str(plan.get("student_material_language") or "").upper(),
    )

    # Lesson Overview
    with st.expander(f"📌 {t('lesson_overview')}", expanded=True):
        _render_inline_box(t("lesson_objective"), plan.get("objective", ""))
        if _has_any_value(plan.get("success_criteria")):
            st.markdown(f"**{t('success_criteria')}**")
            _write_list(plan.get("success_criteria", []))

    # Lesson Flow
    with st.expander(f"🧭 {t('lesson_flow')}", expanded=True):
        flow_sections = [
            (f"1. {t('warm_up')}", plan.get("warm_up", [])),
            (f"2. {t('main_activity')}", plan.get("main_activity", [])),
            (f"3. {t('guided_practice')}", plan.get("guided_practice", [])),
            (f"4. {t('freer_task')}", plan.get("freer_task", [])),
            (f"5. {t('wrap_up')}", plan.get("wrap_up", [])),
        ]
        for section_title, section_items in flow_sections:
            if _has_any_value(section_items):
                st.markdown(f"**{section_title}**")
                _write_list(section_items)

    # Teacher Notes — together with Overview + Flow
    teacher_note_blocks = [
        (t("core_examples"), plan.get("core_examples", []), "list"),
        (t("practice_questions"), plan.get("practice_questions", []), "list"),
        (t("teacher_moves"), plan.get("teacher_moves", []), "list"),
        (t("extension_task"), plan.get("extension_task", ""), "text"),
        (t("optional_homework"), plan.get("homework", ""), "text"),
    ]
    teacher_blocks_present = [b for b in teacher_note_blocks if _has_any_value(b[1])]
    if teacher_blocks_present:
        with st.expander(f"👩‍🏫 {t('teacher_notes')}", expanded=True):
            for label, value, style in teacher_blocks_present:
                st.markdown(f"**{label}**")
                if style == "list":
                    _write_list(value)
                else:
                    _render_text_block(str(value))

    # Teaching Materials — separate expander
    materials = [(key, value, style) for key, value, style in _material_groups(plan) if _has_any_value(value)]
    if materials:
        with st.expander(f"📚 {t('lesson_materials')}", expanded=True):
            for key, value, style in materials:
                label = t(key)
                if not label or label == key:
                    label = _fallback_label(key)
                st.markdown(f"**{label}**")
                _render_material_body(label, value, style, key, action_key_prefix)

    pdf_bytes = build_lesson_plan_pdf_bytes(
        plan=plan,
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        lesson_purpose=lesson_purpose,
        topic=topic,
    )
    safe_title = _safe_title_from_plan(plan)

    # Word export
    from helpers.docx_generator import generate_docx_lesson_plan
    docx_bytes = generate_docx_lesson_plan(
        plan,
        subject=subject,
        topic=topic,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        lesson_purpose=lesson_purpose,
    )

    if read_only:
        dc1, dc2 = st.columns(2)
        with dc1:
            if signup_required_actions:
                if st.button(
                    t("download_pdf"),
                    key=f"{action_key_prefix}_download_pdf_signup",
                    use_container_width=True,
                ):
                    st.session_state["_explore_go_signup"] = True
                    st.rerun()
            else:
                st.download_button(
                    label=t("download_pdf"),
                    data=pdf_bytes,
                    file_name=f"{safe_title}.pdf",
                    mime="application/pdf",
                    key=f"{action_key_prefix}_download_pdf",
                    use_container_width=True,
                )
        with dc2:
            if signup_required_actions:
                if st.button(
                    t("download_word"),
                    key=f"{action_key_prefix}_download_docx_signup",
                    use_container_width=True,
                ):
                    st.session_state["_explore_go_signup"] = True
                    st.rerun()
            else:
                st.download_button(
                    label=t("download_word"),
                    data=docx_bytes,
                    file_name=f"{safe_title}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"{action_key_prefix}_download_docx",
                    use_container_width=True,
                )
        if signup_required_actions:
            st.caption(t("explore_resource_action_signup_note"))
            if st.button(
                t("assign_to_student"),
                key=f"{action_key_prefix}_assign_signup",
                use_container_width=True,
            ):
                st.session_state["_explore_go_signup"] = True
                st.rerun()
        elif allow_assign:
            with st.expander(t("assign_to_student"), expanded=assign_expanded):
                from helpers.teacher_student_integration import render_assignment_panel_for_lesson_plan

                render_assignment_panel_for_lesson_plan(
                    prefix=f"{action_key_prefix}_assign",
                    plan=plan,
                    subject=subject,
                    topic=topic,
                    lesson_purpose=lesson_purpose,
                    source_record_id=resource_record_id,
                )
        return

    if resolved_mode == "template":
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button(t("save_template_plan"), key="btn_save_template_plan", use_container_width=True):
                ok = save_lesson_plan_record(
                    subject=subject,
                    learner_stage=learner_stage,
                    level_or_band=level_or_band,
                    lesson_purpose=lesson_purpose,
                    topic=topic,
                    mode="template",
                    plan=plan,
                )
                if ok:
                    st.session_state["quick_lesson_plan_kept"] = True
                    log_user_activity(
                        activity_type="planner_save",
                        feature_name="quick_lesson_planner",
                        meta={"source_type": "template", "subject": subject, "topic": topic},
                    )
                    st.success(t("template_plan_saved"))
        with a2:
            st.download_button(
                label=t("download_pdf"),
                data=pdf_bytes,
                file_name=f"{safe_title}.pdf",
                mime="application/pdf",
                key=f"{action_key_prefix}_download_pdf_inline",
                use_container_width=True,
            )
        with a3:
            if st.button(t("close"), key="btn_close_quick_plan", use_container_width=True):
                _lp().reset_quick_lesson_planner_state()
                st.rerun()
        st.download_button(
            label=t("download_word"),
            data=docx_bytes,
            file_name=f"{safe_title}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"{action_key_prefix}_download_docx_inline",
            use_container_width=True,
        )
        with st.expander(t("assign_to_student"), expanded=assign_expanded):
            from helpers.teacher_student_integration import render_assignment_panel_for_lesson_plan

            render_assignment_panel_for_lesson_plan(
                prefix=f"{action_key_prefix}_assign",
                plan=plan,
                subject=subject,
                topic=topic,
                lesson_purpose=lesson_purpose,
                source_record_id=resource_record_id,
            )
    else:
        a1, a2 = st.columns(2)
        with a1:
            st.download_button(
                label=t("download_pdf"),
                data=pdf_bytes,
                file_name=f"{safe_title}.pdf",
                mime="application/pdf",
                key=f"{action_key_prefix}_download_pdf_inline",
                use_container_width=True,
            )
        with a2:
            st.download_button(
                label=t("download_word"),
                data=docx_bytes,
                file_name=f"{safe_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"{action_key_prefix}_download_docx_inline2",
                use_container_width=True,
            )
        with st.expander(t("assign_to_student"), expanded=assign_expanded):
            from helpers.teacher_student_integration import render_assignment_panel_for_lesson_plan

            render_assignment_panel_for_lesson_plan(
                prefix=f"{action_key_prefix}_assign",
                plan=plan,
                subject=subject,
                topic=topic,
                lesson_purpose=lesson_purpose,
                source_record_id=resource_record_id,
            )
        if st.button(t("close"), key="btn_close_quick_plan", use_container_width=True):
            _lp().reset_quick_lesson_planner_state()
            st.rerun()


# ============================================================
# PDF generation
# ============================================================


def build_lesson_plan_pdf_bytes(
    plan: dict,
    subject: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    lesson_purpose: str = "",
    topic: str = "",
) -> bytes:
    plan = _clean_plan_data(plan)

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image as RLImage,
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from styles.pdf_styles import (
        ensure_pdf_fonts_registered,
        get_plan_pdf_styles,
        get_pdf_layout_constants,
        C as _C,
    )

    body_font, bold_font = ensure_pdf_fonts_registered()

    # Use user's font/size preference
    from helpers.branding import get_user_branding as _get_branding
    _branding_cfg = _get_branding()
    _font_key = _branding_cfg.get("branding_font", "dejavu")
    _size_key = _branding_cfg.get("branding_font_size", "standard")

    from helpers.font_manager import register_font_for_pdf
    body_font, bold_font = register_font_for_pdf(_font_key)
    _PS = get_plan_pdf_styles(body_font, bold_font, size_preset=_size_key)
    _L = get_pdf_layout_constants()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        **_L["plan_margins"],
    )

    styles = getSampleStyleSheet()
    title_style        = _PS["title"]
    meta_style         = _PS["meta"]
    section_title_style = _PS["section"]
    card_title_style   = _PS["card_title"]
    body_style         = _PS["body"]

    story = []

    def _safe_para(text: str) -> str:
        return html.escape(str(text or "")).replace("\n", "<br/>")

    def _section_title(label: str):
        story.append(Spacer(1, 4))
        story.append(Paragraph(label.upper(), section_title_style))

    def _normalize_pdf_list(items):
        if items is None:
            return []
        if isinstance(items, list):
            return [str(x).strip() for x in items if str(x).strip()]
        if isinstance(items, str):
            text = items.strip()
            if not text:
                return []
            parts = [line.strip() for line in text.splitlines() if line.strip()]
            return parts if len(parts) > 1 else [text]
        return [str(items).strip()]

    def _list_flow(items):
        normalized = _normalize_pdf_list(items)
        return ListFlowable(
            [ListItem(Paragraph(_safe_para(x), body_style)) for x in normalized],
            bulletType="bullet",
            leftIndent=12,
        )

    def _boxed_block(title: str, content):
        parts = [Paragraph(_safe_para(title), card_title_style)]
        if isinstance(content, list):
            items = [ListItem(Paragraph(_safe_para(x), body_style)) for x in content if str(x).strip()]
            if items:
                parts.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
        else:
            if str(content or "").strip():
                parts.append(Paragraph(_safe_para(content), body_style))
        table = Table([[parts]], colWidths=[doc.width])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _C.BG_SUBTLE),
                    ("BOX", (0, 0), (-1, -1), 0.8, _C.BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 7))

    def _simple_section(title_key: str, value, *, boxed: bool = False, inline_csv: bool = False):
        if not _has_any_value(value):
            return
        label = t(title_key)
        if not label or label == title_key:
            label = _fallback_label(title_key)

        rendered_value = ", ".join([str(x) for x in value]) if inline_csv and isinstance(value, list) else value
        if boxed:
            _boxed_block(label, rendered_value)
            return

        story.append(Paragraph(_safe_para(label), card_title_style))
        if isinstance(rendered_value, list):
            items = [ListItem(Paragraph(_safe_para(x), body_style)) for x in rendered_value if str(x).strip()]
            if items:
                story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
        else:
            story.append(Paragraph(_safe_para(rendered_value), body_style))
        story.append(Spacer(1, 6))

    # Header/logo — branding-aware (no school layout for lesson plans)
    from helpers.branding import get_user_branding, build_pdf_footer_handler, has_custom_branding, LOGO_MAX_HEIGHT_CM

    _branding = get_user_branding()
    _header_enabled = _branding.get("header_enabled", False)
    _logo_url = str(_branding.get("header_logo_url") or "").strip()
    _brand_name = str(_branding.get("brand_name") or "").strip()

    title = str(plan.get("title") or t("untitled_plan")).strip()

    if _header_enabled and _logo_url:
        try:
            import urllib.request
            from io import BytesIO as _BytesIO
            _req = urllib.request.Request(_logo_url, headers={"User-Agent": "Classio/1.0"})
            with urllib.request.urlopen(_req, timeout=8) as _resp:
                _img_data = _resp.read()
            _img_buf = _BytesIO(_img_data)
            story.append(RLImage(_img_buf, width=LOGO_MAX_HEIGHT_CM * cm, height=LOGO_MAX_HEIGHT_CM * cm, kind="proportional"))
            story.append(Spacer(1, 5))
        except Exception:
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png"))
            if os.path.isfile(logo_path):
                story.append(RLImage(logo_path, width=2.7 * cm, height=2.7 * cm, kind="proportional"))
                story.append(Spacer(1, 5))
    else:
        logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png"))
        if os.path.isfile(logo_path):
            story.append(RLImage(logo_path, width=2.7 * cm, height=2.7 * cm, kind="proportional"))
            story.append(Spacer(1, 5))

    if _header_enabled and _brand_name:
        story.append(Paragraph(_safe_para(_brand_name), _PS["brand"]))

    story.append(Paragraph(_safe_para(title), title_style))

    meta_parts = []
    subject_text = _translated_subject_display(subject)
    if subject_text:
        meta_parts.append(f"<b>{html.escape(t('subject_label'))}:</b> {html.escape(subject_text)}")
    if topic:
        meta_parts.append(f"<b>{html.escape(t('topic_label'))}:</b> {html.escape(_clean_display_text(topic))}")
    if learner_stage:
        meta_parts.append(f"<b>{html.escape(t('learner_stage'))}:</b> {html.escape(_translated_stage_display(learner_stage))}")
    if level_or_band:
        meta_parts.append(f"<b>{html.escape(t('level_or_band'))}:</b> {html.escape(_translated_level_display(level_or_band))}")
    if lesson_purpose:
        meta_parts.append(f"<b>{html.escape(t('lesson_purpose'))}:</b> {html.escape(_translated_purpose_display(lesson_purpose))}")

    material_language = str(plan.get("student_material_language") or "").upper()
    if material_language:
        meta_parts.append(f"<b>{html.escape(t('student_material_language'))}:</b> {html.escape(material_language)}")

    if meta_parts:
        story.append(Paragraph(" | ".join(meta_parts), meta_style))

    story.append(Spacer(1, 6))

    # Page 1 — Overview + Flow + Teacher Notes

    # LESSON OVERVIEW: two vertical columns inside one blue box
    overview_left = [
        Paragraph(_safe_para(t("lesson_objective")), card_title_style),
        Spacer(1, 4),
        Paragraph(_safe_para(plan.get("objective", "")), body_style),
    ]

    success_items = plan.get("success_criteria", [])
    overview_right = [
        Paragraph(_safe_para(t("success_criteria")), card_title_style),
        Spacer(1, 4),
    ]
    if success_items:
        overview_right.append(_list_flow(success_items))

    overview_table = Table(
        [[overview_left, overview_right]],
        colWidths=[doc.width * 0.48, doc.width * 0.48],
    )
    overview_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 1.3, _C.OVERVIEW_BLUE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, _C.BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), _C.BG_WHITE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    story.append(Paragraph(_safe_para(t("lesson_overview").upper()), section_title_style))
    story.append(overview_table)
    story.append(Spacer(1, 12))

    # LESSON FLOW: separate small green blocks
    story.append(Paragraph(_safe_para(t("lesson_flow").upper()), section_title_style))
    story.append(Spacer(1, 4))

    flow_sections = [
        ("warm_up", plan.get("warm_up", [])),
        ("main_activity", plan.get("main_activity", [])),
        ("guided_practice", plan.get("guided_practice", [])),
        ("freer_task", plan.get("freer_task", [])),
        ("wrap_up", plan.get("wrap_up", [])),
    ]

    for key, value in flow_sections:
        if not _has_any_value(value):
            continue

        label = t(key) if t(key) != key else _fallback_label(key)
        block_parts = [Paragraph(_safe_para(label), card_title_style), Spacer(1, 3)]

        if isinstance(value, list):
            block_parts.append(_list_flow(value))
        else:
            block_parts.append(Paragraph(_safe_para(str(value)), body_style))

        block_table = Table([[block_parts]], colWidths=[doc.width])
        block_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _C.BG_WHITE),
                    ("BOX", (0, 0), (-1, -1), 1.0, _C.FLOW_GREEN),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(block_table)
        story.append(Spacer(1, 8))

    # TEACHER NOTES: separate small orange blocks
    teacher_note_blocks = [
        ("core_examples", plan.get("core_examples", [])),
        ("practice_questions", plan.get("practice_questions", [])),
        ("teacher_moves", plan.get("teacher_moves", [])),
        ("extension_task", plan.get("extension_task", "")),
        ("optional_homework", plan.get("homework", "")),
    ]
    teacher_note_blocks = [row for row in teacher_note_blocks if _has_any_value(row[1])]

    if teacher_note_blocks:
        story.append(Paragraph(_safe_para(t("teacher_notes").upper()), section_title_style))
        story.append(Spacer(1, 4))

        for key, value in teacher_note_blocks:
            label = t(key) if t(key) != key else _fallback_label(key)
            block_parts = [Paragraph(_safe_para(label), card_title_style), Spacer(1, 3)]

            if isinstance(value, list):
                block_parts.append(_list_flow(value))
            else:
                block_parts.append(Paragraph(_safe_para(str(value)), body_style))

            block_table = Table([[block_parts]], colWidths=[doc.width])
            block_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _C.BG_WHITE),
                        ("BOX", (0, 0), (-1, -1), 1.0, _C.NOTE_AMBER),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(block_table)
            story.append(Spacer(1, 8))

    # Page 2 — Materials
    materials = [(key, value, style) for key, value, style in _material_groups(plan) if _has_any_value(value)]
    if materials:
        story.append(PageBreak())

        # Section heading only — do NOT wrap the whole page in one giant table
        story.append(Paragraph(_safe_para(t("lesson_materials").upper()), section_title_style))
        story.append(Spacer(1, 6))

        for key, value, style in materials:
            label = t(key)
            if not label or label == key:
                label = _fallback_label(key)

            # Small per-block table is fine; huge whole-page table is not
            block_parts = [Paragraph(_safe_para(label), card_title_style), Spacer(1, 3)]

            if style == "list_inline":
                block_parts.append(Paragraph(_safe_para(", ".join([str(x) for x in value])), body_style))
            elif style == "list":
                block_parts.append(_list_flow(value))
            elif style == "textarea":
                block_parts.append(Paragraph(_safe_para(str(value)), body_style))
            elif style == "callout":
                block_parts.append(Paragraph(_safe_para(str(value)), body_style))
            elif style == "list_or_text":
                if isinstance(value, list):
                    block_parts.append(_list_flow(value))
                else:
                    block_parts.append(Paragraph(_safe_para(str(value)), body_style))
            else:
                block_parts.append(Paragraph(_safe_para(str(value)), body_style))

            block_table = Table([[block_parts]], colWidths=[doc.width])
            block_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _C.BG_WHITE),
                        ("BOX", (0, 0), (-1, -1), 1.0, _C.MATERIAL_PURPLE),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(block_table)
            story.append(Spacer(1, 8))

    _branding_footer = build_pdf_footer_handler(_branding, bold_font=body_font)
    doc.build(story, onFirstPage=_branding_footer, onLaterPages=_branding_footer)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================
# Planner expander
# ============================================================


def render_quick_lesson_planner_expander() -> None:
    with st.expander(f"📝 {t('quick_lesson_planner')}", expanded=False):
        st.caption(t("quick_lesson_caption"))
        st.caption(t("plan_language_note"))

        usage = get_ai_planner_usage_status()
        mode_labels = {
            "template": t("mode_template"),
            "ai": t("mode_ai"),
        }

        quick_plan_mode = st.radio(
            t("generation_mode"),
            options=["template", "ai"],
            horizontal=True,
            format_func=lambda x: mode_labels.get(x, x.title()),
            key="quick_plan_mode",
        )

        if quick_plan_mode == "ai":
            st.caption(t("ai_plans_left_today", remaining=usage["remaining_today"], limit=_lp().AI_DAILY_LIMIT))

        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            format_func=_lp().subject_label,
            key="quick_plan_subject",
        )

        other_subject_name = ""
        if subject == "other":
            other_subject_name = st.text_input(t("other_subject_label"), key="quick_plan_other_subject").strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=lambda x: t(x),
            key="quick_plan_learner_stage",
        )

        default_level = _lp().recommend_default_level(subject, learner_stage)
        level_options = _lp().get_level_options(subject)
        if st.session_state.get("quick_plan_level") not in level_options:
            st.session_state["quick_plan_level"] = default_level

        c1, c2 = st.columns(2)
        with c1:
            level_or_band = st.selectbox(
                t("level_or_band"),
                level_options,
                format_func=_lp()._level_label,
                key="quick_plan_level",
            )
        with c2:
            lesson_purpose = st.selectbox(
                t("lesson_purpose"),
                _lp().LESSON_PURPOSES,
                format_func=_lp()._purpose_label,
                key="quick_plan_purpose",
            )

        topic = st.text_input(t("topic_label"), key="quick_plan_topic")

        rec_level = _lp().recommend_default_level(subject, learner_stage)
        rec_label = rec_level if rec_level in _lp().LANGUAGE_LEVELS else t(rec_level)
        st.caption(f"{t('recommended_level')}: {rec_label}")

        if st.button(t("generate_plan"), key="btn_generate_quick_plan", use_container_width=True):
            if not topic.strip():
                st.error(t("enter_topic"))
            elif subject == "other" and not other_subject_name:
                st.error(t("enter_subject_name"))
            elif subject == "other" and quick_plan_mode == "template":
                community_row = _find_community_plan_for_other(
                    other_subject_name,
                    topic,
                    learner_stage,
                    level_or_band,
                    lesson_purpose,
                )
                if community_row is not None:
                    community_plan = _lp().normalize_planner_output(community_row.get("plan_json") or {})
                    st.session_state["quick_lesson_plan_result"] = community_plan
                    st.session_state["quick_lesson_plan_kept"] = False
                    st.session_state["quick_lesson_plan_mode_used"] = str(community_row.get("source_type") or "template")
                    st.session_state["quick_lesson_plan_warning"] = t("community_plan_found_note")
                    st.session_state["quick_lesson_no_template"] = False
                    log_user_activity(
                        activity_type="planner_generate",
                        feature_name="quick_lesson_planner",
                        meta={
                            "requested_mode": "template",
                            "resolved_mode": "community",
                            "subject": subject,
                            "topic": topic,
                            "lesson_purpose": lesson_purpose,
                        },
                    )
                else:
                    st.session_state["quick_lesson_plan_result"] = None
                    st.session_state["quick_lesson_no_template"] = True
            else:
                st.session_state["quick_lesson_no_template"] = False
                effective_subject = other_subject_name if subject == "other" else subject

                with st.spinner(t("generating")):
                    plan, resolved_mode, warning_msg = _lp().generate_quick_lesson_plan_with_fallback(
                        mode=quick_plan_mode,
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        lesson_purpose=lesson_purpose,
                        topic=topic,
                    )

                st.session_state["quick_lesson_plan_result"] = plan
                st.session_state["quick_lesson_plan_kept"] = False
                st.session_state["quick_lesson_plan_mode_used"] = resolved_mode
                st.session_state["quick_lesson_plan_warning"] = warning_msg

                if resolved_mode == "ai":
                    save_lesson_plan_record(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        lesson_purpose=lesson_purpose,
                        topic=topic,
                        mode="ai",
                        plan=plan,
                    )

                log_user_activity(
                    activity_type="planner_generate",
                    feature_name="quick_lesson_planner",
                    meta={
                        "requested_mode": quick_plan_mode,
                        "resolved_mode": resolved_mode,
                        "subject": effective_subject,
                        "topic": topic,
                        "lesson_purpose": lesson_purpose,
                    },
                )

        if subject == "other" and st.session_state.get("quick_lesson_no_template"):
            st.info(t("no_template_for_subject"))
        elif st.session_state.get("quick_lesson_plan_result"):
            if st.session_state.get("quick_lesson_plan_kept"):
                st.info(f"📌 {t('quick_plan_saved_label')}")

            render_quick_lesson_plan_result(
                st.session_state["quick_lesson_plan_result"],
                subject=other_subject_name if subject == "other" else subject,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
                lesson_purpose=lesson_purpose,
                topic=topic,
            )
