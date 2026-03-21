import streamlit as st
import json, re, math, os
from typing import Optional
from datetime import datetime as _dt, timezone
import pandas as pd
from io import BytesIO
from core.i18n import t
from core.state import get_current_user_id, with_owner
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, clear_app_caches


def _wb():
    import helpers.worksheet_builder as wb
    return wb


def _lp():
    import helpers.lesson_planner as lp
    return lp


# ── CRUD ──────────────────────────────────────────────────────────────

def save_worksheet_record(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    worksheet_type: str,
    topic: str,
    worksheet: dict,
) -> bool:
    try:
        payload = with_owner({
            "subject": str(subject).strip(),
            "topic": str(topic).strip(),
            "learner_stage": str(learner_stage).strip(),
            "level_or_band": str(level_or_band).strip(),
            "worksheet_type": str(worksheet_type).strip(),
            "plan_language": str(worksheet.get("plan_language") or _wb().get_plan_language()).strip(),
            "student_material_language": str(worksheet.get("student_material_language") or "").strip(),
            "source_type": "ai",
            "worksheet_json": worksheet,
            "title": str(worksheet.get("title") or "").strip(),
            "author_name": str(st.session_state.get("user_name") or "Unknown").strip(),
            "subject_display": subject,
            "is_public": True,
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("worksheets").insert(payload).execute()
        return True
    except Exception as e:
        st.warning(f"Could not save worksheet: {e}")
        return False


def load_my_worksheets() -> pd.DataFrame:
    try:
        df = load_table("worksheets")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        sort_col = "created_at" if "created_at" in df.columns else None
        if sort_col:
            df = df.sort_values(sort_col, ascending=False, na_position="last")
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def load_public_worksheets() -> pd.DataFrame:
    try:
        res = (
            get_sb().table("worksheets")
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
    except Exception:
        return pd.DataFrame()


# ── AI usage tracking (per-feature) ──────────────────────────────────

def log_ai_usage(request_kind: str, status: str, meta: Optional[dict] = None) -> None:
    try:
        payload = with_owner({
            "feature_name": str(request_kind).strip(),
            "status": str(status).strip(),
            "meta_json": meta or {},
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("ai_usage_logs").insert(payload).execute()
        clear_app_caches()
    except Exception:
        pass


def _safe_ai_logs_df() -> pd.DataFrame:
    try:
        df = load_table("ai_usage_logs")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    for col, default in {"created_at": None, "status": "", "feature_name": ""}.items():
        if col not in df.columns:
            df[col] = default
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["feature_name"] = df["feature_name"].fillna("").astype(str).str.strip().str.lower()
    return df


def get_ai_worksheet_usage_status() -> dict:
    df = _safe_ai_logs_df()
    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(
        today_local(), _dt.min.time()
    ).replace(tzinfo=get_app_tz()).astimezone(timezone.utc)

    limit = _wb().AI_WORKSHEET_DAILY_LIMIT
    cooldown = _wb().AI_WORKSHEET_COOLDOWN_SECONDS

    if df.empty:
        return {"used_today": 0, "remaining_today": limit, "cooldown_ok": True, "seconds_left": 0, "last_request_at": None}

    feat_df = df[(df["feature_name"] == "quick_worksheet_ai") & (df["status"] == "success")].copy()
    today_df = feat_df[(feat_df["created_at"].notna()) & (feat_df["created_at"] >= today_start_utc)]
    used_today = int(len(today_df))

    cd_df = df[df["feature_name"] == "quick_worksheet_ai"].dropna(subset=["created_at"]).sort_values("created_at")
    cooldown_ok = True
    seconds_left = 0
    last_request_at = None
    if not cd_df.empty:
        last_request_at = cd_df.iloc[-1]["created_at"]
        delta = (now_utc - last_request_at.to_pydatetime()).total_seconds()
        if delta < cooldown:
            cooldown_ok = False
            seconds_left = int(math.ceil(cooldown - delta))

    return {
        "used_today": used_today,
        "remaining_today": max(0, limit - used_today),
        "cooldown_ok": cooldown_ok,
        "seconds_left": max(0, seconds_left),
        "last_request_at": last_request_at,
    }


# ── Library cards ────────────────────────────────────────────────────

def _format_dt(value) -> str:
    try:
        dt = pd.to_datetime(value, errors="coerce")
        return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def render_worksheet_library_cards(df: pd.DataFrame, prefix: str, show_author: bool = False) -> None:
    if df is None or df.empty:
        return
    for i, row in df.reset_index(drop=True).iterrows():
        row_id = row.get("id", i)
        title = str(row.get("title") or t("untitled_worksheet")).strip()
        subject = str(row.get("subject") or "").strip()
        topic = str(row.get("topic") or "").strip()
        ws_type = str(row.get("worksheet_type") or "").strip()
        author = str(row.get("author_name") or "").strip()
        created = _format_dt(row.get("created_at"))

        with st.container(border=True):
            top_l, top_r = st.columns([5, 1])
            with top_l:
                st.markdown(f"**{title}**")
                parts = []
                if subject:
                    parts.append(f"{t('subject_label')}: {t('subject_' + subject.strip().lower().replace(' ', '_'))}")
                if topic:
                    parts.append(f"{t('topic_label')}: {topic}")
                if ws_type:
                    parts.append(f"{t('worksheet_type_label')}: {t(ws_type)}")
                if show_author and author:
                    parts.append(f"{t('author_name')}: {author}")
                if created:
                    parts.append(f"{t('date')}: {created}")
                if parts:
                    st.caption(" · ".join(parts))
            with top_r:
                if st.button(t("view_worksheet"), key=f"{prefix}_view_{row_id}_{i}", use_container_width=True):
                    st.session_state["files_selected_worksheet"] = row.get("worksheet_json") or {}
                    st.session_state["files_ws_subject"] = subject
                    st.session_state["files_ws_stage"] = str(row.get("learner_stage") or "")
                    st.session_state["files_ws_level"] = str(row.get("level_or_band") or "")
                    st.session_state["files_ws_type"] = ws_type
                    st.session_state["files_ws_topic"] = topic
                    st.session_state["files_ws_title"] = title
                    st.toast(t("scroll_down_to_view"))
                    st.rerun()


# ── Render worksheet result ──────────────────────────────────────────

def render_worksheet_result(ws: dict, read_only: bool = False, **meta) -> None:
    if not ws:
        return

    if not read_only:
        st.success(t("worksheet_ready"))
        warning = st.session_state.get("worksheet_warning")
        if warning:
            st.warning(warning)

    st.markdown(f"### {ws.get('title', '')}")
    st.caption(
        f"{t('plan_language')}: {ws.get('plan_language', '').upper()} · "
        f"{t('student_material_language')}: {ws.get('student_material_language', '').upper()}"
    )

    if ws.get("instructions"):
        st.markdown(f"**{t('ws_instructions')}**")
        st.write(ws["instructions"])

    if ws.get("vocabulary_bank"):
        st.markdown(f"**{t('ws_vocabulary_bank')}**")
        st.write(", ".join(ws["vocabulary_bank"]))

    if ws.get("questions"):
        st.markdown(f"**{t('ws_questions')}**")
        for idx, q in enumerate(ws["questions"], 1):
            st.write(f"{idx}. {q}")

    if ws.get("answer_key"):
        with st.expander(t("ws_answer_key"), expanded=False):
            st.write(ws["answer_key"])

    if ws.get("teacher_notes"):
        with st.expander(t("ws_teacher_notes"), expanded=False):
            for note in ws["teacher_notes"]:
                st.write(f"- {note}")

    # ── Actions ──
    subject = meta.get("subject", ws.get("subject", ""))
    topic = meta.get("topic", ws.get("topic", ""))
    ws_type = meta.get("worksheet_type", ws.get("worksheet_type", ""))
    learner_stage = meta.get("learner_stage", ws.get("learner_stage", ""))
    level_or_band = meta.get("level_or_band", ws.get("level_or_band", ""))

    _pdf_kwargs = dict(subject=subject, topic=topic, ws_type=ws_type, learner_stage=learner_stage, level_or_band=level_or_band)
    student_pdf = build_worksheet_pdf_bytes(ws, student_only=True, **_pdf_kwargs)
    teacher_pdf = build_worksheet_pdf_bytes(ws, student_only=False, **_pdf_kwargs)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str(ws.get("title") or "worksheet").strip()) or "worksheet"

    if read_only:
        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button(
                label=t("download_student_pdf"),
                data=student_pdf,
                file_name=f"{safe_title}_student.pdf",
                mime="application/pdf",
                key=f"dl_ws_stu_{safe_title}",
                use_container_width=True,
            )
        with dc2:
            st.download_button(
                label=t("download_teacher_pdf"),
                data=teacher_pdf,
                file_name=f"{safe_title}_teacher.pdf",
                mime="application/pdf",
                key=f"dl_ws_tch_{safe_title}",
                use_container_width=True,
            )
    else:
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("keep_worksheet"), key="btn_keep_ws", use_container_width=True):
                st.session_state["worksheet_kept"] = True
                st.success(t("worksheet_kept_msg"))
        with c2:
            if st.button(t("delete_worksheet"), key="btn_del_ws", use_container_width=True):
                _wb().reset_worksheet_maker_state()
                st.rerun()

        dc1, dc2 = st.columns(2)
        with dc1:
            st.download_button(
                label=t("download_student_pdf"),
                data=student_pdf,
                file_name=f"{safe_title}_student.pdf",
                mime="application/pdf",
                key=f"dl_ws_stu_inline_{safe_title}",
                use_container_width=True,
            )
        with dc2:
            st.download_button(
                label=t("download_teacher_pdf"),
                data=teacher_pdf,
                file_name=f"{safe_title}_teacher.pdf",
                mime="application/pdf",
                key=f"dl_ws_tch_inline_{safe_title}",
                use_container_width=True,
            )


# ── PDF generation ───────────────────────────────────────────────────

def build_worksheet_pdf_bytes(
    ws: dict,
    subject: str = "",
    topic: str = "",
    ws_type: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
    student_only: bool = False,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("WsTitle", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#1D4ED8"), spaceAfter=10)
    heading_style = ParagraphStyle("WsH", parent=styles["Heading2"], fontSize=12, leading=15, textColor=colors.HexColor("#0F172A"), spaceBefore=8, spaceAfter=4)
    body_style = ParagraphStyle("WsBody", parent=styles["BodyText"], fontSize=10.5, leading=14, textColor=colors.HexColor("#0F172A"), spaceAfter=4)

    story = []

    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png"))
    if os.path.isfile(logo_path):
        story.append(RLImage(logo_path, width=2.8*cm, height=2.8*cm, kind="proportional"))
        story.append(Spacer(1, 6))

    story.append(Paragraph(str(ws.get("title") or t("untitled_worksheet")), title_style))

    meta_parts = []
    if subject:
        meta_parts.append(f"<b>{t('subject_label')}:</b> {subject}")
    if topic:
        meta_parts.append(f"<b>{t('topic_label')}:</b> {topic}")
    if ws_type:
        meta_parts.append(f"<b>{t('worksheet_type_label')}:</b> {t(ws_type)}")
    if learner_stage:
        meta_parts.append(f"<b>{t('learner_stage')}:</b> {t(learner_stage)}")
    if level_or_band:
        lbl = level_or_band if level_or_band in ["A1","A2","B1","B2","C1","C2"] else t(level_or_band)
        meta_parts.append(f"<b>{t('level_or_band')}:</b> {lbl}")
    if meta_parts:
        story.append(Paragraph(" | ".join(meta_parts), body_style))
        story.append(Spacer(1, 8))

    def _sec(title_key, value):
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

    _sec("ws_instructions", ws.get("instructions", ""))

    if ws.get("vocabulary_bank"):
        _sec("ws_vocabulary_bank", ", ".join(ws["vocabulary_bank"]))

    # Questions as numbered list
    questions = ws.get("questions", [])
    if questions:
        story.append(Paragraph(t("ws_questions"), heading_style))
        for idx, q in enumerate(questions, 1):
            story.append(Paragraph(f"{idx}. {q}", body_style))
        story.append(Spacer(1, 6))

    if not student_only:
        _sec("ws_answer_key", ws.get("answer_key", ""))
        _sec("ws_teacher_notes", ws.get("teacher_notes", []))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ── Expander UI ──────────────────────────────────────────────────────

def render_quick_worksheet_maker_expander() -> None:
    with st.expander(t("worksheet_maker"), expanded=False):
        st.caption(t("worksheet_maker_caption"))

        usage = get_ai_worksheet_usage_status()
        st.caption(t("ai_plans_left_today", remaining=usage["remaining_today"], limit=_wb().AI_WORKSHEET_DAILY_LIMIT))

        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            key="ws_subject",
        )

        other_subject_name = ""
        if subject == "Other":
            other_subject_name = st.text_input(t("other_subject_label"), key="ws_other_subject").strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=_lp()._stage_label,
            key="ws_stage",
        )

        default_level = _lp().recommend_default_level(subject, learner_stage)
        level_options = _lp().get_level_options(subject)
        if st.session_state.get("ws_level") not in level_options:
            st.session_state["ws_level"] = default_level

        c1, c2 = st.columns(2)
        with c1:
            level_or_band = st.selectbox(
                t("level_or_band"),
                level_options,
                format_func=_lp()._level_label,
                key="ws_level",
            )
        with c2:
            worksheet_type = st.selectbox(
                t("worksheet_type_label"),
                _wb().WORKSHEET_TYPES,
                format_func=lambda x: t(x),
                key="ws_type",
            )

        topic = st.text_input(t("topic_label"), key="ws_topic")

        if st.button(t("generate_worksheet"), key="btn_gen_ws", use_container_width=True):
            if not topic.strip():
                st.error(t("enter_topic"))
            elif subject == "Other" and not other_subject_name:
                st.error(t("enter_subject_name"))
            else:
                effective_subject = other_subject_name if subject == "Other" else subject
                with st.spinner(t("generating")):
                    ws, warning = _wb().generate_worksheet_with_limit(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        worksheet_type=worksheet_type,
                        topic=topic,
                    )

                if warning and not ws:
                    st.warning(warning)
                else:
                    st.session_state["worksheet_result"] = ws
                    st.session_state["worksheet_kept"] = False
                    st.session_state["worksheet_warning"] = warning

                    # Auto-save to DB + community
                    save_worksheet_record(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        worksheet_type=worksheet_type,
                        topic=topic,
                        worksheet=ws,
                    )

        result = st.session_state.get("worksheet_result")
        if result:
            if st.session_state.get("worksheet_kept"):
                st.info(f"📌 {t('worksheet_kept_msg')}")
            render_worksheet_result(
                result,
                subject=subject,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
                worksheet_type=worksheet_type,
                topic=topic,
            )

# =========================
