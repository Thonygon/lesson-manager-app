import streamlit as st
import json, datetime, os, re, time, math
from typing import Optional
from datetime import datetime as _dt, timezone
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id, with_owner
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, load_students, register_cache, clear_app_caches
import html
import textwrap
from core.navigation import home_go

# ── Cleanup code-like key names in AI-generated plan text ────────────
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
    "core_material",
    "reading_passage",
    "listening_script",
    "gist_questions",
    "detail_questions",
    "pre_task_questions",
    "target_vocabulary",
    "post_task",
]


def _clean_plan_text(text: str) -> str:
    """Replace code-like key references with translated labels in plan content."""
    if not text:
        return text
    for pat in _PLAN_KEY_PATTERNS:
        # strip "core_material." prefix to get the translation key
        tkey = pat.split(".")[-1]
        translated = t(tkey)
        # replace various quote/bracket styles: 'key', "key", `key`, key:
        text = text.replace(f"'{pat}'", translated)
        text = text.replace(f'"{pat}"', translated)
        text = text.replace(f"`{pat}`", translated)
        text = text.replace(f"{pat}:", f"{translated}:")
        text = text.replace(f"{pat},", f"{translated},")
        text = text.replace(f"{pat}.", f"{translated}.")
        text = text.replace(f"{pat} ", f"{translated} ")
    return text


def _clean_plan_data(plan: dict) -> dict:
    """Deep-clean all string values in a plan dict."""
    out = {}
    for k, v in plan.items():
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

    # Collapse repeated spaces
    s = re.sub(r"\s+", " ", s)

    # Remove spaces before punctuation
    s = re.sub(r"\s+([.,!?;:])", r"\1", s)

    # Normalize spaces around hyphens and slashes
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s*/\s*", " / ", s)

    # Final trim
    s = re.sub(r"\s+", " ", s).strip()

    # Capitalize first letter
    if s:
        s = s[0].upper() + s[1:]

    return s

def _lp():
    """Lazy import to avoid circular dependency with lesson_planner."""
    import helpers.lesson_planner as lp
    return lp


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
        mask_subject = df["subject"].str.strip().str.casefold() == subject_norm
        topic_norm = str(topic or "").strip().casefold()
        mask_topic = df["topic"].str.strip().str.casefold() == topic_norm

        matches = df[mask_subject & mask_topic].copy()
        if matches.empty:
            return None

        def _score(row):
            s = 0
            if str(row.get("learner_stage", "")).strip() == str(learner_stage).strip():
                s += 1
            if str(row.get("level_or_band", "")).strip() == str(level_or_band).strip():
                s += 1
            if str(row.get("lesson_purpose", "")).strip() == str(lesson_purpose).strip():
                s += 1
            return s

        matches["_score"] = matches.apply(_score, axis=1)
        best = matches.sort_values(["_score", "created_at"], ascending=[False, False]).iloc[0]
        return best.to_dict()
    except Exception:
        return None

# 07.1A.1) QUICK LESSON PLANNER STORAGE + AI LOGGING
# =========================

def planner_payload_from_inputs(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
    mode: str,
    plan: dict,
) -> dict:
    return with_owner({
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
        "author_name": str(st.session_state.get("user_name") or "Unknown").strip(),
        "subject_display": subject,
        "is_public": True,
        "created_at": _dt.now(timezone.utc).isoformat(),
    })


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
        get_sb().table("lesson_plans").insert(payload).execute()
        return True
    except Exception as e:
        st.warning(f"Could not save lesson plan: {e}")
        return False

def load_my_lesson_plans() -> pd.DataFrame:
    try:
        df = load_table("lesson_plans")
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        sort_col = "created_at" if "created_at" in df.columns else None
        if sort_col:
            df = df.sort_values(sort_col, ascending=False, na_position="last")

        return df.reset_index(drop=True)

    except Exception as e:
        st.error(f"Could not load your lesson plans: {e}")
        return pd.DataFrame()


def load_public_lesson_plans() -> pd.DataFrame:
    try:
        res = (
            get_sb().table("lesson_plans")
            .select("*")
            .eq("is_public", True)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )

        df = pd.DataFrame(res.data or [])
        if df.empty:
            return pd.DataFrame()

        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        return df.reset_index(drop=True)

    except Exception as e:
        st.error(f"Could not load community lesson plans: {e}")
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
    if not s:
        return ""
    return f"{prefix}{s}"


def render_plan_library_cards(
    df: pd.DataFrame,
    prefix: str,
    show_author: bool = False,
    open_in_files: bool = False,
    require_signup: bool = False,
) -> None:
    if df is None or df.empty:
        return

    rows = df.reset_index(drop=True).to_dict("records")

    for idx in range(0, len(rows), 2):
        pair = rows[idx:idx + 2]
        cols = st.columns(2, gap="medium")

        for col_idx, row in enumerate(pair):
            row_id = row.get("id", idx + col_idx)
            title = _clean_display_text(row.get("title") or t("untitled_plan"))
            subject = str(row.get("subject") or "").strip()
            topic = _clean_display_text(row.get("topic") or "")
            learner_stage = str(row.get("learner_stage") or "").strip()
            level_or_band = str(row.get("level_or_band") or "").strip()
            lesson_purpose = str(row.get("lesson_purpose") or "").strip()
            source_type = str(row.get("source_type") or "").strip()
            author_name = str(row.get("author_name") or "").strip()
            created_at = format_plan_datetime(row.get("created_at"))

            subject_label = ""
            if subject:
                subj_key = "subject_" + subject.strip().lower().replace(" ", "_")
                subject_label = t(subj_key)

            level_label = ""
            if level_or_band:
                if level_or_band in ["A1", "A2", "B1", "B2", "C1", "C2"]:
                    level_label = level_or_band
                else:
                    level_label = t(level_or_band)

            purpose_label = t(lesson_purpose) if lesson_purpose else ""
            stage_label = t(learner_stage) if learner_stage else ""
            source_label = t("mode_ai") if source_type == "ai" else t("mode_template")

            safe_title = html.escape(title)
            safe_author = html.escape(author_name)
            preview_text = html.escape((topic or t("no_description_available"))[:180])

            chips = "".join([
                f'<span class="cm-resource-chip">📚 {html.escape(subject_label)}</span>' if subject_label else "",
                f'<span class="cm-resource-chip">🎯 {html.escape(purpose_label)}</span>' if purpose_label else "",
                f'<span class="cm-resource-chip">👥 {html.escape(stage_label)}</span>' if stage_label else "",
                f'<span class="cm-resource-chip">🏷️ {html.escape(level_label)}</span>' if level_label else "",
                f'<span class="cm-resource-chip">⚙️ {html.escape(source_label)}</span>' if source_label else "",
            ])

            meta = "".join([
                f'<div class="cm-resource-meta">👤 {safe_author}</div>' if show_author and author_name else "",
                f'<div class="cm-resource-meta">🕒 {html.escape(created_at)}</div>' if created_at else "",
            ])

            card_html = (
                f'<div class="cm-resource-card cm-resource-plan">'
                f'<div class="cm-resource-card__title">{safe_title}</div>'
                f'<div class="cm-resource-chip-row">{chips}</div>'
                f'<div class="cm-resource-preview">{preview_text}</div>'
                f'{meta}'
                f'</div>'
            )

            with cols[col_idx]:
                st.markdown(card_html, unsafe_allow_html=True)

                if st.button(
                    t("view_plan"),
                    key=f"{prefix}_view_{row_id}_{idx}_{col_idx}",
                    use_container_width=True,
                ):
                    st.session_state["files_selected_plan"] = row.get("plan_json") or {}
                    st.session_state["files_selected_subject"] = subject
                    st.session_state["files_selected_stage"] = learner_stage
                    st.session_state["files_selected_level"] = level_or_band
                    st.session_state["files_selected_purpose"] = lesson_purpose
                    st.session_state["files_selected_topic"] = topic
                    st.session_state["files_selected_source_type"] = source_type
                    st.session_state["files_selected_title"] = title

                    if require_signup:
                        st.session_state["_post_signup_open_panel"] = "files"
                        st.session_state["_post_signup_open_tab"] = "community_library"
                        st.session_state["_explore_go_signup"] = True
                    elif open_in_files:
                        home_go("home", panel="files")
                    else:
                        st.toast(t("scroll_down_to_view"))

                    st.rerun()

def log_user_activity(
    activity_type: str,
    feature_name: str,
    meta: Optional[dict] = None,
) -> None:
    try:
        payload = with_owner({
            "activity_type": str(activity_type or "").strip() or "unknown",
            "feature_name": str(feature_name or "").strip() or "unknown",
            "meta_json": meta or {},
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("user_activity_log").insert(payload).execute()
    except Exception as e:
        st.warning(f"user_activity_log insert failed: {e}")

def log_ai_usage(
    request_kind: str,
    status: str,
    meta: Optional[dict] = None,
) -> None:
    try:
        payload = with_owner({
            "feature_name": str(request_kind).strip(),
            "status": str(status).strip(),
            "meta_json": meta or {},
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
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

    if "created_at" not in df.columns:
        df["created_at"] = None
    if "status" not in df.columns:
        df["status"] = ""
    if "feature_name" not in df.columns:
        df["feature_name"] = ""

    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["feature_name"] = df["feature_name"].fillna("").astype(str).str.strip().str.lower()
    return df


def get_ai_planner_usage_status() -> dict:
    df = _safe_ai_logs_df()
    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(
        today_local(), _dt.min.time()
    ).replace(tzinfo=get_app_tz()).astimezone(timezone.utc)

    if df.empty:
        return {
            "used_today": 0,
            "remaining_today": _lp().AI_DAILY_LIMIT,
            "cooldown_ok": True,
            "seconds_left": 0,
            "last_request_at": None,
        }

    planner_df = df[
        (df["feature_name"] == "quick_lesson_ai") &
        (df["status"] == "success")
    ].copy()

    today_df = planner_df[
        (planner_df["created_at"].notna()) &
        (planner_df["created_at"] >= today_start_utc)
    ].copy()

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

def render_quick_lesson_plan_result(
    plan: dict,
    subject: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    lesson_purpose: str = "",
    topic: str = "",
    read_only: bool = False,
) -> None:
    plan = _clean_plan_data(plan)
    if not read_only:
        st.success(t("lesson_plan_ready"))
    resolved_mode = st.session_state.get("quick_lesson_plan_mode_used", "template")
    warning_msg = st.session_state.get("quick_lesson_plan_warning")

    st.caption(t("mode_used", mode=resolved_mode.upper()))

    if warning_msg:
        st.warning(warning_msg)
    st.markdown(f"### {t('plan_title')}: {plan.get('title', '')}")

    rec_level = plan.get("recommended_level", "")
    if rec_level:
        show_level = rec_level if rec_level in _lp().LANGUAGE_LEVELS else t(rec_level)
        st.caption(f"{t('recommended_level')}: {show_level}")

    st.caption(
        f"{t('plan_language')}: {_lp().get_plan_language().upper()} · "
        f"{t('student_material_language')}: {plan.get('student_material_language', '').upper()}"
    )

    st.markdown(f"**{t('lesson_objective')}**")
    st.write(plan.get("objective", ""))

    st.markdown(f"**{t('success_criteria')}**")
    for item in plan.get("success_criteria", []):
        st.write(f"- {item}")

    st.markdown(f"**1. {t('warm_up')}**")
    for item in plan.get("warm_up", []):
        st.write(f"- {item}")

    st.markdown(f"**2. {t('main_activity')}**")
    for item in plan.get("main_activity", []):
        st.write(f"- {item}")

    cm = plan.get("core_material", {}) or {}

    if cm.get("target_vocabulary"):
        st.markdown(f"**{t('target_vocabulary')}**")
        st.write(", ".join(cm["target_vocabulary"]))

    if cm.get("pre_task_questions"):
        st.markdown(f"**{t('pre_task_questions')}**")
        for q in cm["pre_task_questions"]:
            st.write(f"- {q}")

    if plan.get("reading_passage"):
        st.markdown(f"**{t('reading_passage')}**")
        st.text_area(
            t("reading_passage"),
            value=plan["reading_passage"],
            height=190,
            key="quick_plan_reading_passage_view",
        )

    if plan.get("listening_script"):
        st.markdown(f"**{t('listening_script')}**")
        st.text_area(
            t("listening_script"),
            value=plan["listening_script"],
            height=190,
            key="quick_plan_listening_script_view",
        )

    if cm.get("gist_questions"):
        st.markdown(f"**{t('gist_questions')}**")
        for q in cm["gist_questions"]:
            st.write(f"- {q}")

    if cm.get("detail_questions"):
        st.markdown(f"**{t('detail_questions')}**")
        for q in cm["detail_questions"]:
            st.write(f"- {q}")

    st.markdown(f"**{t('core_examples')}**")
    for item in plan.get("core_examples", []):
        if isinstance(item, list):
            for sub in item:
                st.write(f"- {sub}")
        else:
            st.write(f"- {item}")

    # subject-specific core material
    if cm.get("worked_example"):
        st.markdown(f"**{t('worked_example')}**")
        for item in cm["worked_example"]:
            st.write(f"- {item}")

    if cm.get("independent_practice"):
        st.markdown(f"**{t('independent_practice')}**")
        for item in cm["independent_practice"]:
            st.write(f"- {item}")

    if cm.get("common_error_alert"):
        st.markdown(f"**{t('common_error_alert')}**")
        st.write(cm["common_error_alert"])

    if cm.get("concept_explanation"):
        st.markdown(f"**{t('concept_explanation')}**")
        st.write(cm["concept_explanation"])

    if cm.get("real_life_application"):
        st.markdown(f"**{t('real_life_application')}**")
        st.write(cm["real_life_application"])

    if cm.get("strategy_steps"):
        st.markdown(f"**{t('strategy_steps')}**")
        for item in cm["strategy_steps"]:
            st.write(f"- {item}")

    if cm.get("performance_goal"):
        st.markdown(f"**{t('performance_goal')}**")
        st.write(cm["performance_goal"])

    st.markdown(f"**3. {t('guided_practice')}**")
    for item in plan.get("guided_practice", []):
        st.write(f"- {item}")

    st.markdown(f"**{t('practice_questions')}**")
    for q in plan.get("practice_questions", []):
        st.write(f"- {q}")

    if cm.get("post_task"):
        st.markdown(f"**{t('post_task')}**")
        st.write(cm["post_task"])

    st.markdown(f"**4. {t('freer_task')}**")
    for item in plan.get("freer_task", []):
        st.write(f"- {item}")

    st.markdown(f"**5. {t('wrap_up')}**")
    for item in plan.get("wrap_up", []):
        st.write(f"- {item}")

    st.markdown(f"**{t('teacher_moves')}**")
    for item in plan.get("teacher_moves", []):
        st.write(f"- {item}")

    st.markdown(f"**{t('extension_task')}**")
    st.write(plan.get("extension_task", ""))

    st.markdown(f"**{t('optional_homework')}**")
    st.write(plan.get("homework", ""))

    if read_only:
        pdf_bytes = build_lesson_plan_pdf_bytes(
            plan=plan,
            subject=subject,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
            lesson_purpose=lesson_purpose,
            topic=topic,
        )

        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str(plan.get("title") or "lesson_plan").strip())
        if not safe_title:
            safe_title = "lesson_plan"

        st.download_button(
            label=t("download_pdf"),
            data=pdf_bytes,
            file_name=f"{safe_title}.pdf",
            mime="application/pdf",
            key=f"download_plan_pdf_{safe_title}",
            use_container_width=True,
        )
    else:
        c1, c2, c3 = st.columns(3)

        with c1:
            if resolved_mode == "template":
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

        with c2:
            if st.button(t("keep_plan"), key="btn_keep_quick_plan", use_container_width=True):
                st.session_state["quick_lesson_plan_kept"] = True
                st.success(t("plan_kept"))

        with c3:
            if st.button(t("delete_plan"), key="btn_delete_quick_plan", use_container_width=True):
                _lp().reset_quick_lesson_planner_state()
                st.success(t("plan_deleted"))
                st.rerun()     

def build_lesson_plan_pdf_bytes(
    plan: dict,
    subject: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    lesson_purpose: str = "",
    topic: str = "",
) -> bytes:
    plan = _clean_plan_data(plan)
    import os
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PlanTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1D4ED8"),
        spaceAfter=10,
    )
    heading_style = ParagraphStyle(
        "PlanHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "PlanBody",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )

    story = []

    # ── Top-left logo, then left-aligned title ─────────────────────────
    title = str(plan.get("title") or t("untitled_plan")).strip()
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png"))
    if os.path.isfile(logo_path):
        logo = RLImage(logo_path, width=2.8 * cm, height=2.8 * cm, kind="proportional")
        story.append(logo)
        story.append(Spacer(1, 6))

    story.append(Paragraph(title, title_style))

    meta_parts = []
    if subject:
        meta_parts.append(f"<b>{t('subject_label')}:</b> {subject}")
    if topic:
        meta_parts.append(f"<b>{t('topic_label')}:</b> {topic}")
    if learner_stage:
        meta_parts.append(f"<b>{t('learner_stage')}:</b> {t(learner_stage)}")
    if level_or_band:
        level_label = level_or_band if level_or_band in ["A1", "A2", "B1", "B2", "C1", "C2"] else t(level_or_band)
        meta_parts.append(f"<b>{t('level_or_band')}:</b> {level_label}")
    if lesson_purpose:
        meta_parts.append(f"<b>{t('lesson_purpose')}:</b> {t(lesson_purpose)}")

    if meta_parts:
        story.append(Paragraph(" | ".join(meta_parts), body_style))
        story.append(Spacer(1, 8))

    def add_section(title_key: str, value):
        if not value:
            return
        story.append(Paragraph(t(title_key), heading_style))
        if isinstance(value, list):
            items = [ListItem(Paragraph(str(x), body_style)) for x in value if str(x).strip()]
            if items:
                story.append(ListFlowable(items, bulletType="bullet"))
        else:
            story.append(Paragraph(str(value), body_style))
        story.append(Spacer(1, 6))

    add_section("lesson_objective", plan.get("objective", ""))
    add_section("success_criteria", plan.get("success_criteria", []))
    add_section("warm_up", plan.get("warm_up", []))
    add_section("main_activity", plan.get("main_activity", []))
    add_section("guided_practice", plan.get("guided_practice", []))
    add_section("freer_task", plan.get("freer_task", []))
    add_section("wrap_up", plan.get("wrap_up", []))

    core_material = plan.get("core_material", {}) or {}
    if core_material.get("target_vocabulary"):
        add_section("target_vocabulary", [", ".join(core_material.get("target_vocabulary", []))])
    if core_material.get("language_frames"):
        add_section("language_frames", core_material.get("language_frames", []))
    if plan.get("reading_passage"):
        add_section("reading_passage", plan.get("reading_passage", ""))
    if plan.get("listening_script"):
        add_section("listening_script", plan.get("listening_script", ""))
    if core_material.get("pre_task_questions"):
        add_section("pre_task_questions", core_material.get("pre_task_questions", []))
    if core_material.get("gist_questions"):
        add_section("gist_questions", core_material.get("gist_questions", []))
    if core_material.get("detail_questions"):
        add_section("detail_questions", core_material.get("detail_questions", []))
    if core_material.get("post_task"):
        add_section("post_task", core_material.get("post_task", ""))

    add_section("teacher_moves", plan.get("teacher_moves", []))
    add_section("extension_task", plan.get("extension_task", ""))
    add_section("optional_homework", plan.get("homework", ""))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def render_quick_lesson_planner_expander() -> None:
    with st.expander(t("quick_lesson_planner"), expanded=False):
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
            st.caption(
                t("ai_plans_left_today", remaining=usage["remaining_today"], limit=_lp().AI_DAILY_LIMIT)
            )        

        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            key="quick_plan_subject",
        )

        other_subject_name = ""
        if subject == "Other":
            other_subject_name = st.text_input(
                t("other_subject_label"),
                key="quick_plan_other_subject",
            ).strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=_lp()._stage_label,
            key="quick_plan_stage",
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

        topic = st.text_input(
            t("topic_label"),
            key="quick_plan_topic",
            
        )

        rec_level = _lp().recommend_default_level(subject, learner_stage)
        rec_label = rec_level if rec_level in _lp().LANGUAGE_LEVELS else t(rec_level)
        st.caption(f"{t('recommended_level')}: {rec_label}")

        if st.button(t("generate_plan"), key="btn_generate_quick_plan", use_container_width=True):
            if not topic.strip():
                st.error(t("enter_topic"))
            elif subject == "Other" and not other_subject_name:
                st.error(t("enter_subject_name"))
            elif subject == "Other" and quick_plan_mode == "template":
                # For "Other" in template mode: look up the community library first
                community_row = _find_community_plan_for_other(other_subject_name, topic, learner_stage, level_or_band, lesson_purpose)
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
                    # No template and no community plan available
                    st.session_state["quick_lesson_plan_result"] = None
                    st.session_state["quick_lesson_no_template"] = True
            else:
                st.session_state["quick_lesson_no_template"] = False
                effective_subject = other_subject_name if subject == "Other" else subject
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

        if subject == "Other" and st.session_state.get("quick_lesson_no_template"):
            st.info(t("no_template_for_subject"))
        elif st.session_state.get("quick_lesson_plan_result"):
            if st.session_state.get("quick_lesson_plan_kept"):
                st.info(f"📌 {t('quick_plan_saved_label')}")

            render_quick_lesson_plan_result(
                st.session_state["quick_lesson_plan_result"],
                subject=subject,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
                lesson_purpose=lesson_purpose,
                topic=topic,
            )

# =========================
