# CLASSIO — Quick Exam Storage, PDF, UI
# ============================================================
import streamlit as st
import json, re, math, os, html
from typing import Optional
from datetime import datetime as _dt, timezone
import pandas as pd
from io import BytesIO
from core.i18n import t
from core.state import get_current_user_id, with_owner
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, clear_app_caches
from xml.sax.saxutils import escape as xml_escape
import unicodedata
from styles.pdf_styles import (
    ensure_pdf_fonts_registered,
    get_student_pdf_styles,
    get_answer_key_pdf_styles,
    get_pdf_layout_constants,
    C as _C,
)


def _eb():
    import helpers.quick_exam_builder as eb
    return eb


def _lp():
    import helpers.lesson_planner as lp
    return lp


def _normalize_text(value) -> str:
    return unicodedata.normalize("NFC", str(value or ""))


def _pdf_safe_text(value) -> str:
    return xml_escape(_normalize_text(value))


# ── CRUD ──────────────────────────────────────────────────────────────

def save_exam_record(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    topic: str,
    exam_length: str,
    exercise_types: list[str],
    exam_data: dict,
    answer_key: dict,
) -> bool:
    try:
        from helpers.branding import resolve_is_public
        payload = with_owner({
            "title": str(exam_data.get("title", "")).strip(),
            "subject": str(subject).strip(),
            "topic": str(topic).strip(),
            "learner_stage": str(learner_stage).strip(),
            "level": str(level_or_band).strip(),
            "exam_length": str(exam_length).strip(),
            "exercise_types": exercise_types,
            "exam_data": exam_data,
            "answer_key": answer_key,
            "is_public": resolve_is_public(),
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("quick_exams").insert(payload).execute()
        return True
    except Exception as e:
        st.warning(f"Could not save exam: {e}")
        return False


def load_my_exams() -> pd.DataFrame:
    try:
        df = load_table("quick_exams")
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


def load_public_exams() -> pd.DataFrame:
    try:
        res = (
            get_sb()
            .table("quick_exams")
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


def _format_exam_dt(value) -> str:
    try:
        dt = pd.to_datetime(value, errors="coerce")
        return "" if pd.isna(dt) else dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def render_exam_library_cards(
    df: pd.DataFrame,
    prefix: str = "exam",
    show_author: bool = False,
    open_in_files: bool = False,
) -> None:
    if df is None or df.empty:
        st.info(t("no_data"))
        return

    from core.navigation import home_go

    rows = df.reset_index(drop=True).to_dict("records")

    for idx in range(0, len(rows), 2):
        pair = rows[idx : idx + 2]
        cols = st.columns(2, gap="medium")

        for col_idx, row in enumerate(pair):
            row_id = row.get("id", idx + col_idx)
            title = str(row.get("title") or t("untitled_plan")).strip()
            subject = str(row.get("subject") or "").strip()
            topic = str(row.get("topic") or "").strip()
            learner_stage = str(row.get("learner_stage") or "").strip()
            level = str(row.get("level") or "").strip()
            exam_length = str(row.get("exam_length") or "").strip()
            author_name = str(row.get("author_name") or "").strip()
            created_at = _format_exam_dt(row.get("created_at"))

            subject_label = ""
            if subject:
                subj_key = "subject_" + subject.lower().replace(" ", "_")
                subject_label = t(subj_key)

            level_label = ""
            if level:
                level_label = level if level in ("A1", "A2", "B1", "B2", "C1", "C2") else t(level)

            stage_label = t(learner_stage) if learner_stage else ""
            length_label = t(f"{exam_length}_exam") if exam_length else ""

            safe_title = html.escape(title)
            safe_author = html.escape(author_name)
            preview_text = html.escape((topic or t("no_description_available"))[:180])

            chips = "".join([
                f'<span class="cm-resource-chip">📚 {html.escape(subject_label)}</span>' if subject_label else "",
                f'<span class="cm-resource-chip">📏 {html.escape(length_label)}</span>' if length_label else "",
                f'<span class="cm-resource-chip">👥 {html.escape(stage_label)}</span>' if stage_label else "",
                f'<span class="cm-resource-chip">🏷️ {html.escape(level_label)}</span>' if level_label else "",
            ])

            meta = "".join([
                f'<div class="cm-resource-meta">👤 {safe_author}</div>' if show_author and author_name else "",
                f'<div class="cm-resource-meta">🕒 {html.escape(created_at)}</div>' if created_at else "",
            ])

            card_html = (
                f'<div class="cm-resource-card cm-resource-exam">'
                f'<div class="cm-resource-card__title">{safe_title}</div>'
                f'<div class="cm-resource-chip-row">{chips}</div>'
                f'<div class="cm-resource-preview">{preview_text}</div>'
                f'{meta}'
                f'</div>'
            )

            with cols[col_idx]:
                st.markdown(card_html, unsafe_allow_html=True)

                if st.button(
                    t("preview"),
                    key=f"{prefix}_preview_{row_id}_{idx}_{col_idx}",
                    use_container_width=True,
                ):
                    st.session_state["files_selected_exam"] = row.get("exam_data") or {}
                    st.session_state["files_selected_exam_answer_key"] = row.get("answer_key") or {}
                    st.session_state["files_exam_subject"] = subject
                    st.session_state["files_exam_stage"] = learner_stage
                    st.session_state["files_exam_level"] = level
                    st.session_state["files_exam_topic"] = topic
                    st.session_state["files_exam_title"] = title

                    if open_in_files:
                        home_go("home", panel="files")
                    else:
                        st.toast(t("scroll_down_to_view"))

                    st.rerun()


# ── AI usage tracking ────────────────────────────────────────────────

def log_exam_ai_usage(status: str, meta: Optional[dict] = None) -> None:
    try:
        payload = with_owner({
            "feature_name": "quick_exam_ai",
            "status": str(status).strip(),
            "meta_json": meta or {},
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("ai_usage_logs").insert(payload).execute()
        clear_app_caches()
    except Exception:
        pass


def get_ai_exam_usage_status() -> dict:
    try:
        df = load_table("ai_usage_logs")
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        df = pd.DataFrame()

    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(today_local(), _dt.min.time()).replace(
        tzinfo=get_app_tz()
    ).astimezone(timezone.utc)

    limit = _eb().AI_EXAM_DAILY_LIMIT
    cooldown = _eb().AI_EXAM_COOLDOWN_SECONDS

    if df.empty:
        return {
            "used_today": 0,
            "remaining_today": limit,
            "cooldown_ok": True,
            "seconds_left": 0,
            "last_request_at": None,
        }

    for col, default in {"created_at": None, "status": "", "feature_name": ""}.items():
        if col not in df.columns:
            df[col] = default

    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["feature_name"] = df["feature_name"].fillna("").astype(str).str.strip().str.lower()

    feat_df = df[(df["feature_name"] == "quick_exam_ai") & (df["status"] == "success")].copy()
    today_df = feat_df[(feat_df["created_at"].notna()) & (feat_df["created_at"] >= today_start_utc)]
    used_today = int(len(today_df))

    cd_df = df[df["feature_name"] == "quick_exam_ai"].dropna(subset=["created_at"]).sort_values("created_at")
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


# ── PDF generation ───────────────────────────────────────────────────

def build_exam_pdf_bytes(
    exam_data: dict,
    subject: str = "",
    topic: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
) -> bytes:
    """Build the student exam PDF (no answers)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, KeepTogether, CondPageBreak,
    )
    from reportlab.lib import colors

    body_font, bold_font = ensure_pdf_fonts_registered()

    # Use user's font/size preference
    from helpers.branding import get_user_branding as _get_branding_cfg
    _branding_cfg = _get_branding_cfg()
    _font_key = _branding_cfg.get("branding_font", "dejavu")
    _size_key = _branding_cfg.get("branding_font_size", "standard")

    from helpers.font_manager import register_font_for_pdf
    body_font, bold_font = register_font_for_pdf(_font_key)
    _L = get_pdf_layout_constants()
    _S = get_student_pdf_styles(body_font, bold_font, size_preset=_size_key)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, **_L["margins"])
    styles = getSampleStyleSheet()
    story = []

    plan_lang = "en"
    def _t_pdf(key, **kw):
        try:
            return t(key, lang=plan_lang, **kw)
        except TypeError:
            return t(key, **kw)

    # ── Branding header ──────────────────────────────────
    from helpers.branding import get_user_branding, build_worksheet_header
    _branding = get_user_branding()

    ws_stub = {"title": exam_data.get("title", "Exam")}
    build_worksheet_header(
        story, ws_stub, _branding,
        styles=styles, doc=doc,
        bold_font=bold_font, body_font=body_font,
        _t_pdf=_t_pdf, _pdf_safe_text=_pdf_safe_text,
        subject=subject, topic=topic,
        ws_type="", learner_stage=learner_stage,
        level_or_band=level_or_band,
    )

    # General instructions
    if exam_data.get("instructions"):
        story.append(Paragraph(_pdf_safe_text(exam_data["instructions"]), _S["instruction"]))
        story.append(Spacer(1, 8))

    # ── Sections ─────────────────────────────────────────
    for sec in exam_data.get("sections", []):
        sec_type = sec.get("type", "")
        sec_title = sec.get("title", "")

        story.append(CondPageBreak(3 * cm))
        story.append(Paragraph(_pdf_safe_text(sec_title), _S["section"]))

        if sec.get("instructions"):
            story.append(Paragraph(_pdf_safe_text(sec["instructions"]), _S["instruction"]))
            story.append(Spacer(1, 4))

        if sec.get("source_text"):
            story.append(Paragraph(_pdf_safe_text(sec["source_text"]), _S["body"]))
            story.append(Spacer(1, 6))

        questions = sec.get("questions", [])

        if sec_type == "multiple_choice":
            for idx, q in enumerate(questions, 1):
                if isinstance(q, dict):
                    stem = q.get("stem", q.get("text", ""))
                    options = q.get("options", [])
                    block = [
                        Paragraph(_pdf_safe_text(f"{idx}. {stem}"), _S["mc_stem"]),
                        Spacer(1, 2),
                    ]
                    for oi, opt in enumerate(options):
                        letter = chr(65 + oi)
                        block.append(Paragraph(_pdf_safe_text(f"{letter}) {opt}"), _S["mc_option"]))
                    block.append(Spacer(1, 4))
                    story.append(KeepTogether(block))
                else:
                    story.append(Paragraph(_pdf_safe_text(f"{idx}. {q}"), _S["body"]))
                    story.append(Spacer(1, 4))

        elif sec_type == "matching":
            left_items = []
            right_items = []
            for q in questions:
                if isinstance(q, dict):
                    left_items.append(q.get("left", ""))
                    right_items.append(q.get("right", ""))

            if left_items:
                import random
                rng = random.Random("|".join(left_items))
                shuffled = right_items[:]
                rng.shuffle(shuffled)

                box_style = _S["box_label"]
                rows = []
                for i in range(max(len(left_items), len(shuffled))):
                    lt = f"{i+1}. {left_items[i]}" if i < len(left_items) else ""
                    rt = f"{chr(97+i)}) {shuffled[i]}" if i < len(shuffled) else ""
                    rows.append([
                        Paragraph(_pdf_safe_text(lt), _S["body"]),
                        Paragraph(_pdf_safe_text("[   ]"), box_style),
                        Paragraph(_pdf_safe_text(rt), _S["body"]),
                    ])

                tbl = Table(rows, colWidths=[9.0*cm, 1.0*cm, 6.4*cm], hAlign="LEFT")
                tbl.setStyle(TableStyle([
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("ALIGN", (1,0), (1,-1), "CENTER"),
                    ("TOPPADDING", (0,0), (-1,-1), 5),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 7),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 6))

        elif sec_type == "true_false":
            tf_label_style = _S["tf_label"]
            tf_rows = []
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                tf_rows.append([
                    Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]),
                    Paragraph(_pdf_safe_text("True ☐   False ☐"), tf_label_style),
                ])
            if tf_rows:
                tbl = Table(tf_rows, colWidths=[11.8*cm, 4.6*cm], hAlign="LEFT")
                tbl.setStyle(TableStyle([
                    ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ("TOPPADDING", (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                    ("LEFTPADDING", (1,0), (1,-1), 2),
                    ("RIGHTPADDING", (1,0), (1,-1), 2),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 6))

        elif sec_type == "fill_in_blank":
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                text = re.sub(r"_+", "______________", text)
                story.append(Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]))
                story.append(Spacer(1, 6))

        elif sec_type in ("short_answer", "reading_comprehension"):
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                block = [
                    Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]),
                    Spacer(1, 4),
                ]
                # Answer lines
                for _ in range(2):
                    line_tbl = Table(
                        [[""]],
                        colWidths=[16.2*cm],
                        rowHeights=[0.6*cm],
                        hAlign="LEFT",
                    )
                    line_tbl.setStyle(TableStyle([
                        ("LINEBELOW", (0,0), (-1,-1), 0.6, _C.LINE),
                        ("LEFTPADDING", (0,0), (-1,-1), 0),
                        ("RIGHTPADDING", (0,0), (-1,-1), 0),
                        ("TOPPADDING", (0,0), (-1,-1), 0),
                        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                    ]))
                    block.append(line_tbl)
                    block.append(Spacer(1, 4))
                story.append(KeepTogether(block))

        elif sec_type == "vocabulary":
            for idx, q in enumerate(questions, 1):
                if isinstance(q, dict):
                    word = q.get("word", "")
                    task = q.get("task", "")
                    text = f"{word}: {task}" if task else word
                else:
                    text = str(q)
                story.append(Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]))
                line_tbl = Table([[""]],
                                colWidths=[16.2*cm], rowHeights=[0.6*cm], hAlign="LEFT")
                line_tbl.setStyle(TableStyle([
                    ("LINEBELOW", (0,0), (-1,-1), 0.6, _C.LINE),
                    ("LEFTPADDING", (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                    ("TOPPADDING", (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                ]))
                story.append(line_tbl)
                story.append(Spacer(1, 6))

        elif sec_type == "sentence_transformation":
            for idx, q in enumerate(questions, 1):
                if isinstance(q, dict):
                    original = q.get("original", "")
                    prompt = q.get("prompt", "")
                    text = f"{original}\n({prompt})" if prompt else original
                else:
                    text = str(q)
                block = [
                    Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]),
                    Spacer(1, 4),
                ]
                line_tbl = Table([[""]],
                                colWidths=[16.2*cm], rowHeights=[0.6*cm], hAlign="LEFT")
                line_tbl.setStyle(TableStyle([
                    ("LINEBELOW", (0,0), (-1,-1), 0.6, _C.LINE),
                    ("LEFTPADDING", (0,0), (-1,-1), 0),
                    ("RIGHTPADDING", (0,0), (-1,-1), 0),
                    ("TOPPADDING", (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 0),
                ]))
                block.append(line_tbl)
                block.append(Spacer(1, 6))
                story.append(KeepTogether(block))

        elif sec_type == "writing_prompt":
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                story.append(Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]))
                story.append(Spacer(1, 8))

        else:
            # Fallback: numbered list
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                story.append(Paragraph(_pdf_safe_text(f"{idx}. {text}"), _S["body"]))
                story.append(Spacer(1, 4))

        story.append(Spacer(1, 10))

    from helpers.branding import build_pdf_footer_handler
    _footer_handler = build_pdf_footer_handler(_branding, bold_font=body_font)
    doc.build(story, onFirstPage=_footer_handler, onLaterPages=_footer_handler)
    buf.seek(0)
    return buf.getvalue()


def build_exam_answer_pdf_bytes(
    exam_data: dict,
    answer_key: dict,
    subject: str = "",
    topic: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
) -> bytes:
    """Build the teacher answer key PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, CondPageBreak,
    )

    body_font, bold_font = ensure_pdf_fonts_registered()

    # Use user's font/size preference
    from helpers.branding import get_user_branding as _get_branding_cfg2
    _branding_cfg2 = _get_branding_cfg2()
    _font_key2 = _branding_cfg2.get("branding_font", "dejavu")
    _size_key2 = _branding_cfg2.get("branding_font_size", "standard")

    from helpers.font_manager import register_font_for_pdf as _rfp2
    body_font, bold_font = _rfp2(_font_key2)
    _L = get_pdf_layout_constants()
    _AK = get_answer_key_pdf_styles(body_font, bold_font, size_preset=_size_key2)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, **_L["margins"])
    styles = getSampleStyleSheet()
    story = []

    def _t_pdf(key, **kw):
        try:
            return t(key, lang="en", **kw)
        except TypeError:
            return t(key, **kw)

    # Header
    from helpers.branding import get_user_branding, build_worksheet_header
    _branding = get_user_branding()

    title_text = exam_data.get("title", "Exam") + " — " + _t_pdf("ws_answer_key")
    ws_stub = {"title": title_text}
    build_worksheet_header(
        story, ws_stub, _branding,
        styles=styles, doc=doc,
        bold_font=bold_font, body_font=body_font,
        _t_pdf=_t_pdf, _pdf_safe_text=_pdf_safe_text,
        subject=subject, topic=topic,
        ws_type="", learner_stage=learner_stage,
        level_or_band=level_or_band,
    )

    # Sections
    ak_sections = answer_key.get("sections", [])
    exam_sections = exam_data.get("sections", [])

    for i, ak_sec in enumerate(ak_sections):
        sec_title = ak_sec.get("title", f"Part {i+1}")
        answers = ak_sec.get("answers", [])

        story.append(CondPageBreak(2 * cm))
        story.append(Paragraph(_pdf_safe_text(sec_title), _AK["section"]))
        story.append(Spacer(1, 4))

        for idx, ans in enumerate(answers, 1):
            if isinstance(ans, dict):
                ans_text = ans.get("answer", ans.get("text", str(ans)))
            else:
                ans_text = str(ans)
            story.append(Paragraph(_pdf_safe_text(f"{idx}. {ans_text}"), _AK["body"]))

        story.append(Spacer(1, 8))

    from helpers.branding import build_pdf_footer_handler
    _footer_handler = build_pdf_footer_handler(_branding, bold_font=body_font)
    doc.build(story, onFirstPage=_footer_handler, onLaterPages=_footer_handler)
    buf.seek(0)
    return buf.getvalue()


# ── Render UI ────────────────────────────────────────────────────────

def render_exam_result(exam_data: dict, answer_key: dict, **meta) -> None:
    if not exam_data or not exam_data.get("sections"):
        return

    st.success(t("exam_ready") if t("exam_ready") != "exam_ready" else "Exam ready!")
    warning = st.session_state.get("exam_warning")
    if warning:
        st.warning(warning)

    st.markdown(f"### {exam_data.get('title', '')}")

    if exam_data.get("instructions"):
        st.markdown(f"**{t('ws_instructions')}**")
        st.write(exam_data["instructions"])

    for sec in exam_data.get("sections", []):
        sec_type = sec.get("type", "")
        st.markdown(f"#### {sec.get('title', '')}")

        if sec.get("instructions"):
            st.caption(sec["instructions"])

        if sec.get("source_text"):
            st.write(sec["source_text"])

        questions = sec.get("questions", [])

        if sec_type == "multiple_choice":
            for idx, q in enumerate(questions, 1):
                if isinstance(q, dict):
                    stem = q.get("stem", q.get("text", ""))
                    st.write(f"**{idx}. {stem}**")
                    for oi, opt in enumerate(q.get("options", [])):
                        st.write(f"   {chr(65+oi)}) {opt}")
                else:
                    st.write(f"{idx}. {q}")

        elif sec_type == "matching":
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Column A**")
                for idx, q in enumerate(questions, 1):
                    left = q.get("left", str(q)) if isinstance(q, dict) else str(q)
                    st.write(f"{idx}. {left}")
            with c2:
                st.markdown("**Column B**")
                for idx, q in enumerate(questions):
                    right = q.get("right", "") if isinstance(q, dict) else ""
                    st.write(f"{chr(97+idx)}) {right}")

        elif sec_type == "true_false":
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                st.write(f"{idx}. {text}")

        elif sec_type == "sentence_transformation":
            for idx, q in enumerate(questions, 1):
                if isinstance(q, dict):
                    st.write(f"{idx}. {q.get('original', '')}  →  ({q.get('prompt', '')})")
                else:
                    st.write(f"{idx}. {q}")

        elif sec_type == "vocabulary":
            for idx, q in enumerate(questions, 1):
                if isinstance(q, dict):
                    st.write(f"{idx}. **{q.get('word', '')}**: {q.get('task', '')}")
                else:
                    st.write(f"{idx}. {q}")

        else:
            for idx, q in enumerate(questions, 1):
                text = q if isinstance(q, str) else q.get("text", str(q))
                st.write(f"{idx}. {text}")

    # Answer key preview
    with st.expander(t("ws_answer_key"), expanded=False):
        for sec in answer_key.get("sections", []):
            st.markdown(f"**{sec.get('title', '')}**")
            for idx, ans in enumerate(sec.get("answers", []), 1):
                if isinstance(ans, dict):
                    st.write(f"{idx}. {ans.get('answer', ans.get('text', str(ans)))}")
                else:
                    st.write(f"{idx}. {ans}")

    # PDF downloads
    _pdf_kwargs = dict(
        subject=meta.get("subject", ""),
        topic=meta.get("topic", ""),
        learner_stage=meta.get("learner_stage", ""),
        level_or_band=meta.get("level_or_band", ""),
    )

    student_pdf = build_exam_pdf_bytes(exam_data, **_pdf_kwargs)
    answer_pdf = build_exam_answer_pdf_bytes(exam_data, answer_key, **_pdf_kwargs)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", str(exam_data.get("title") or "exam").strip()) or "exam"

    dc1, dc2 = st.columns(2)
    with dc1:
        st.download_button(
            label=t("download_exam") if t("download_exam") != "download_exam" else "Download Student Exam",
            data=student_pdf,
            file_name=f"{safe_title}_student.pdf",
            mime="application/pdf",
            key=f"dl_exam_stu_{safe_title}",
            use_container_width=True,
        )
    with dc2:
        st.download_button(
            label=t("download_answer_key") if t("download_answer_key") != "download_answer_key" else "Download Answer Key",
            data=answer_pdf,
            file_name=f"{safe_title}_answers.pdf",
            mime="application/pdf",
            key=f"dl_exam_ak_{safe_title}",
            use_container_width=True,
        )


# ── Expander UI ──────────────────────────────────────────────────────

def render_quick_exam_builder_expander() -> None:
    with st.expander(
        t("quick_exam_builder") if t("quick_exam_builder") != "quick_exam_builder" else "Quick Exam Builder",
        expanded=False,
    ):
        st.caption(
            t("quick_exam_builder_caption")
            if t("quick_exam_builder_caption") != "quick_exam_builder_caption"
            else "Generate a full multi-section exam in seconds"
        )

        usage = get_ai_exam_usage_status()
        st.caption(
            t(
                "ai_plans_left_today",
                remaining=usage["remaining_today"],
                limit=_eb().AI_EXAM_DAILY_LIMIT,
            )
        )

        # ── Core fields ──
        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            format_func=_lp().subject_label,
            key="quick_exam_subject",
        )

        other_subject_name = ""
        if subject == "other":
            other_subject_name = st.text_input(
                t("other_subject_label"), key="exam_other_subject"
            ).strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=_lp()._stage_label,
            key="exam_stage",
        )

        default_level = _lp().recommend_default_level(subject, learner_stage)
        level_options = _lp().get_level_options(subject)
        if st.session_state.get("exam_level") not in level_options:
            st.session_state["exam_level"] = default_level

        level_or_band = st.selectbox(
            t("level_or_band"),
            level_options,
            format_func=_lp()._level_label,
            key="exam_level",
        )

        topic = st.text_input(t("topic_label"), key="quick_exam_topic")
        exam_title = st.text_input(
            t("exam_title") if t("exam_title") != "exam_title" else "Exam title",
            key="quick_exam_title",
        )

        # ── Exam settings ──
        st.markdown(f"**{t('exam_settings') if t('exam_settings') != 'exam_settings' else 'Exam Settings'}**")

        c1, c2 = st.columns(2)
        with c1:
            exam_length = st.selectbox(
                t("exam_length") if t("exam_length") != "exam_length" else "Exam length",
                _eb().EXAM_LENGTHS,
                format_func=lambda x: t(f"{x}_exam") if t(f"{x}_exam") != f"{x}_exam" else x.capitalize(),
                key="exam_length_select",
            )
        with c2:
            exercise_types = st.multiselect(
                t("exercise_types") if t("exercise_types") != "exercise_types" else "Exercise types",
                _eb().EXAM_EXERCISE_TYPES,
                default=["multiple_choice", "true_false", "short_answer"],
                format_func=lambda x: t(x) if t(x) != x else x.replace("_", " ").title(),
                key="exam_exercise_types",
            )

        # ── Generate ──
        if st.button(
            t("generate_exam") if t("generate_exam") != "generate_exam" else "Generate Exam",
            key="btn_gen_exam",
            use_container_width=True,
        ):
            if not topic.strip():
                st.error(t("enter_topic"))
            elif subject == "other" and not other_subject_name:
                st.error(t("enter_subject_name"))
            elif not exercise_types:
                st.error(
                    t("select_exercise_types")
                    if t("select_exercise_types") != "select_exercise_types"
                    else "Please select at least one exercise type."
                )
            else:
                effective_subject = other_subject_name if subject == "other" else subject
                with st.spinner(t("generating")):
                    exam_data, answer_key, warning = _eb().generate_exam_with_limit(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        topic=topic,
                        exam_title=exam_title or f"{effective_subject} Exam",
                        exam_length=exam_length,
                        exercise_types=exercise_types,
                    )

                if warning and not exam_data:
                    st.warning(warning)
                elif not exam_data or not exam_data.get("sections"):
                    st.error(
                        t("exam_generation_failed")
                        if t("exam_generation_failed") != "exam_generation_failed"
                        else "Exam generation failed. Please try again."
                    )
                else:
                    st.session_state["exam_result"] = exam_data
                    st.session_state["exam_answer_key"] = answer_key
                    st.session_state["exam_kept"] = False
                    st.session_state["exam_warning"] = warning

                    save_exam_record(
                        subject=effective_subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        topic=topic,
                        exam_length=exam_length,
                        exercise_types=exercise_types,
                        exam_data=exam_data,
                        answer_key=answer_key,
                    )

        # ── Show result ──
        result = st.session_state.get("exam_result")
        ak = st.session_state.get("exam_answer_key")
        if result and ak:
            render_exam_result(
                result,
                ak,
                subject=subject,
                topic=topic,
                learner_stage=learner_stage,
                level_or_band=level_or_band,
            )
