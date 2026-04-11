# CV_STORAGE.PY
#===============================

import streamlit as st
import re, math
import pandas as pd
from io import BytesIO
from datetime import datetime as _dt, timezone
from typing import Optional

from core.i18n import t
from core.state import get_current_user_id, with_owner, PROFILE_SUBJECT_OPTIONS, PROFILE_STAGE_OPTIONS, PROFILE_TEACH_LANG_OPTIONS
from helpers.lesson_planner import subject_label as _subject_label
from core.timezone import today_local, get_app_tz
from core.database import get_sb, load_table, clear_app_caches

AI_CV_DAILY_LIMIT = 3
AI_CV_COOLDOWN_SECONDS = 30

SEX_OPTIONS_RAW = [
    "male",
    "female",
    "other",
    "prefer_not_to_say",
    "",
]


def _parse_dob(raw) -> "date | None":
    """Parse a date_of_birth value from profile or session into datetime.date."""
    import datetime as _dt_mod
    if isinstance(raw, _dt_mod.date):
        return raw
    s = str(raw or "").strip()[:10]
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return _dt_mod.datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _sanitize_phone(val: str) -> str:
    """Keep only digits, +, ( and ) for CV phone input."""
    import re as _re
    return _re.sub(r"[^\d+()]", "", str(val or "")).strip()


def _is_valid_cv_phone(val: str) -> bool:
    s = str(val or "").strip()
    if not s:
        return True
    if not re.fullmatch(r"[\d+()]+", s):
        return False
    digits = re.sub(r"\D", "", s)
    return len(digits) >= 6


def _cv():
    """Lazy import – avoids circular dependency with lesson_planner chain."""
    import helpers.cv_builder as cb
    return cb

def _sex_label(value: str) -> str:
    key_map = {
        "male": "sex_male",
        "female": "sex_female",
        "other": "sex_other",
        "prefer_not_to_say": "sex_prefer_not_to_say",
        "": "select_option",
    }

    key = key_map.get(str(value or "").strip(), "")
    return t(key) if key else str(value or "")


def _role_label(value: str) -> str:
    v = str(value or "").strip().lower()
    mapping = {
        "teacher": t("teacher_role"),
        "tutor": t("tutor_role"),
    }
    return mapping.get(v, str(value or ""))




def _translate_cv_list(key: str, values) -> list[str]:
    items = values if isinstance(values, list) else [values]
    out = []
    for item in items:
        s = str(item or "").strip()
        if not s:
            continue
        if key == "subjects":
            out.append(_subject_label(s))
        elif key == "teaching_stages":
            out.append(_stage_label(s))
        elif key == "teaching_languages":
            out.append(_lang_label(s))
        else:
            out.append(s)
    return out


def _stage_label(stage: str) -> str:
    labels = {
        "early_primary": t("stage_early_primary"),
        "upper_primary": t("stage_upper_primary"),
        "lower_secondary": t("stage_lower_secondary"),
        "upper_secondary": t("stage_upper_secondary"),
        "adult_stage": t("stage_adult"),
    }
    return labels.get(str(stage), str(stage))


def _lang_label(code: str) -> str:
    labels = {
        "en": t("english"),
        "es": t("spanish"),
        "tr": t("turkish"),
    }
    return labels.get(str(code), str(code))

def _country_options() -> list[str]:
    try:
        import pycountry
        names = sorted({c.name for c in pycountry.countries if getattr(c, "name", None)})
        return [""] + names
    except Exception:
        return [""]


def _normalize_country_value(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    opts = set(_country_options())
    return s if s in opts else ""


# -----------------------------------------------------------------------
# SUPABASE CRUD
# -----------------------------------------------------------------------

def save_cv_record(cv_dict: dict, source_type: str, title: str, ai_prompt: str = "") -> bool:
    try:
        payload = with_owner({
            "doc_type": "cv",
            "title": str(title or "").strip() or t("my_cv"),
            "source_type": source_type,
            "cv_json": cv_dict,
            "ai_prompt": str(ai_prompt or "").strip(),
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("professional_profiles").insert(payload).execute()
        clear_app_caches()
        return True
    except Exception as e:
        st.warning(f"{t('cv_save_failed')}: {e}")
        return False


def save_cover_letter_record(
    content: str,
    title: str,
    ai_prompt: str = "",
    target_employer: str = "",
) -> bool:
    try:
        payload = with_owner({
            "doc_type": "cover_letter",
            "title": str(title or "").strip() or t("my_cover_letter"),
            "source_type": "ai",
            "content": str(content or "").strip(),
            "ai_prompt": str(ai_prompt or "").strip(),
            "target_employer": str(target_employer or "").strip(),
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("professional_profiles").insert(payload).execute()
        clear_app_caches()
        return True
    except Exception as e:
        st.warning(f"{t('cover_letter_save_failed')}: {e}")
        return False


def load_my_cvs() -> pd.DataFrame:
    try:
        df = load_table("professional_profiles")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df[df["doc_type"].astype(str).str.strip() == "cv"].copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        return df.sort_values("created_at", ascending=False, na_position="last").reset_index(drop=True)
    except Exception as e:
        st.error(f"{t('cv_load_failed')}: {e}")
        return pd.DataFrame()


def load_my_cover_letters() -> pd.DataFrame:
    try:
        df = load_table("professional_profiles")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df[df["doc_type"].astype(str).str.strip() == "cover_letter"].copy()
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        return df.sort_values("created_at", ascending=False, na_position="last").reset_index(drop=True)
    except Exception as e:
        st.error(f"{t('cover_letter_load_failed')}: {e}")
        return pd.DataFrame()


# -----------------------------------------------------------------------
# AI USAGE TRACKING  (shares ai_usage_logs table, feature_name="quick_cv_ai")
# -----------------------------------------------------------------------

def _safe_ai_logs_df() -> pd.DataFrame:
    try:
        df = load_table("ai_usage_logs")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    for col in ("created_at", "status", "feature_name"):
        if col not in df.columns:
            df[col] = None
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df["status"]       = df["status"].fillna("").astype(str).str.strip().str.lower()
    df["feature_name"] = df["feature_name"].fillna("").astype(str).str.strip().str.lower()
    return df


def get_ai_cv_usage_status() -> dict:
    df = _safe_ai_logs_df()
    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(
        today_local(), _dt.min.time()
    ).replace(tzinfo=get_app_tz()).astimezone(timezone.utc)

    _empty = {"used_today": 0, "remaining_today": AI_CV_DAILY_LIMIT, "cooldown_ok": True, "seconds_left": 0}
    if df.empty:
        return _empty

    cv_df    = df[(df["feature_name"] == "quick_cv_ai") & (df["status"] == "success")]
    used_today = int(len(cv_df[(cv_df["created_at"].notna()) & (cv_df["created_at"] >= today_start_utc)]))

    cooldown_df = df[df["feature_name"] == "quick_cv_ai"].dropna(subset=["created_at"]).sort_values("created_at")
    cooldown_ok = True
    seconds_left = 0
    if not cooldown_df.empty:
        last = cooldown_df.iloc[-1]["created_at"].to_pydatetime()
        delta = (now_utc - last).total_seconds()
        if delta < AI_CV_COOLDOWN_SECONDS:
            cooldown_ok = False
            seconds_left = int(math.ceil(AI_CV_COOLDOWN_SECONDS - delta))

    return {
        "used_today": used_today,
        "remaining_today": max(0, AI_CV_DAILY_LIMIT - used_today),
        "cooldown_ok": cooldown_ok,
        "seconds_left": max(0, seconds_left),
    }


def _log_ai_cv(status: str, meta: dict = None) -> None:
    try:
        payload = with_owner({
            "feature_name": "quick_cv_ai",
            "status": status,
            "meta_json": meta or {},
            "created_at": _dt.now(timezone.utc).isoformat(),
        })
        get_sb().table("ai_usage_logs").insert(payload).execute()
        clear_app_caches()
    except Exception as e:
        st.warning(f"{t('ai_usage_log_insert_failed')}: {e}")


# -----------------------------------------------------------------------
# PDF BUILDERS
# -----------------------------------------------------------------------

def build_cv_pdf_bytes(cv: dict) -> bytes:
    import os, tempfile, urllib.request
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem, Table, TableStyle
    from reportlab.platypus import Image as RLImage
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()

    sty_name    = ParagraphStyle("CVName", parent=styles["Title"],    fontSize=20, leading=24, textColor=colors.HexColor("#1D4ED8"), spaceAfter=2)
    sty_role    = ParagraphStyle("CVRole", parent=styles["Normal"],   fontSize=12, textColor=colors.HexColor("#475569"), spaceAfter=4)
    sty_contact = ParagraphStyle("CVContact", parent=styles["Normal"],fontSize=9,  textColor=colors.HexColor("#475569"), spaceAfter=8)
    sty_sec     = ParagraphStyle("CVSection", parent=styles["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#1E40AF"), spaceBefore=10, spaceAfter=3)
    sty_body    = ParagraphStyle("CVBody",    parent=styles["BodyText"], fontSize=10, leading=13, textColor=colors.HexColor("#1E293B"), spaceAfter=3)
    sty_bullet  = ParagraphStyle("CVBullet",  parent=sty_body, leftIndent=12, firstLineIndent=-8)

    sty_name_c    = ParagraphStyle("CVNameC",    parent=sty_name,    alignment=1)
    sty_role_c    = ParagraphStyle("CVRoleC",    parent=sty_role,    alignment=1)
    sty_contact_c = ParagraphStyle("CVContactC", parent=sty_contact, alignment=1)

    story = []

    full_name = str(cv.get("full_name") or cv.get("title") or t("cv")).strip()
    role = _role_label(cv.get("role"))

    contact_parts = []
    for field in ("email", "phone", "location", "date_of_birth", "sex"):
        raw = str(cv.get(field) or "").strip()
        if not raw:
            continue
        if field == "sex":
            raw = _sex_label(raw)
        contact_parts.append(raw)

    # ── Centered name / role / contact, optional photo beside name ───
    avatar_url = str(cv.get("avatar_url") or "").strip()
    _tmp_photo_path = None
    _photo_flowable = None
    if avatar_url:
        try:
            req = urllib.request.Request(avatar_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                img_data = resp.read()
            suffix = ".png" if "png" in avatar_url.lower() else ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(img_data)
            tmp.close()
            _tmp_photo_path = tmp.name
            _photo_flowable = RLImage(_tmp_photo_path, width=2.8 * cm, height=2.8 * cm)
        except Exception:
            _tmp_photo_path = None

    name_block = [Paragraph(full_name, sty_name_c)]
    if role:
        name_block.append(Paragraph(role, sty_role_c))
    if contact_parts:
        name_block.append(Paragraph("  |  ".join(contact_parts), sty_contact_c))

    if _photo_flowable:
        hdr_table = Table(
            [[name_block, _photo_flowable]],
            colWidths=[None, 3.0 * cm],
        )
        hdr_table.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (0, 0),   0),
            ("RIGHTPADDING", (1, 0), (1, 0),   0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(hdr_table)
    else:
        story.extend(name_block)

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=8))

    def _sec(label):
        story.append(Paragraph(str(label).upper(), sty_sec))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#BFDBFE"), spaceAfter=4))

    def _body(text):
        if text:
            story.append(Paragraph(str(text), sty_body))

    def _bullets(items):
        if not items:
            return
        li = [ListItem(Paragraph(str(x), sty_bullet)) for x in items if str(x).strip()]
        if li:
            story.append(ListFlowable(li, bulletType="bullet"))

    sections = [
        ("professional_summary", t("cv_professional_summary"), False),
        ("subjects",             t("cv_subjects"),             True),
        ("teaching_stages",      t("cv_teaching_stages"),      True),
        ("teaching_languages",   t("cv_teaching_languages"),   True),
        ("education",            t("cv_education"),            True),
        ("certifications",       t("cv_certifications"),       True),
        ("experience",           t("cv_experience"),           True),
        ("skills",               t("cv_skills"),               True),
    ]

    for key, label, is_list in sections:
        val = cv.get(key)
        if not val:
            continue
        _sec(label)
        if is_list:
            translated_vals = _translate_cv_list(key, val)
            _bullets(translated_vals)
        else:
            _body(str(val))
        story.append(Spacer(1, 4))

    avail = str(cv.get("availability") or "").strip()
    rate  = str(cv.get("rate") or "").strip()
    if avail or rate:
        _sec(t("cv_availability_rate"))
        if avail:
            _body(f"{t('cv_availability')}: {avail}")
        if rate:
            _body(f"{t('cv_rate')}: {rate}")

    doc.build(story)
    buffer.seek(0)
    # Clean up temp photo file
    if _tmp_photo_path:
        try:
            import os
            os.unlink(_tmp_photo_path)
        except Exception:
            pass
    return buffer.getvalue()


def build_cover_letter_pdf_bytes(content: str, title: str = "") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    sty_title = ParagraphStyle("CLTitle", parent=styles["Heading1"], fontSize=14, textColor=colors.HexColor("#1D4ED8"), spaceAfter=12)
    sty_body  = ParagraphStyle("CLBody",  parent=styles["BodyText"], fontSize=10.5, leading=16, textColor=colors.HexColor("#1E293B"), spaceAfter=10)

    sty_title_c = ParagraphStyle("CLTitleC", parent=sty_title, alignment=1)

    story = []

    if title:
        story.append(Paragraph(str(title), sty_title_c))
    for para in str(content or "").split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip().replace("\n", "<br/>"), sty_body))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# -----------------------------------------------------------------------
# UI: CV RESULT DISPLAY
# -----------------------------------------------------------------------

def render_cv_result(
    cv: dict,
    read_only: bool = False,
    source_type: str = "template",
    ai_prompt: str = "",
    title: str = "",
) -> None:
    if not read_only:
        st.success(t("cv_ready"))
    st.caption(f"{t('source_type')}: {t('mode_ai') if source_type == 'ai' else t('mode_template')}")

    avatar_url = str(cv.get("avatar_url") or "").strip()
    full_name_display = cv.get("full_name") or cv.get("title") or t("cv")
    role_val = _role_label(cv.get("role"))

    contact_parts = []
    for field in ("email", "phone", "location", "date_of_birth", "sex"):
        raw = str(cv.get(field) or "").strip()
        if not raw:
            continue
        if field == "sex":
            raw = _sex_label(raw)
        contact_parts.append(raw)

    contact = " · ".join(contact_parts)

    if avatar_url:
        hdr_col, photo_col = st.columns([5, 1])
        with hdr_col:
            st.markdown(f"## {full_name_display}")
            if role_val:
                st.caption(role_val)
            if contact:
                st.caption(contact)
        with photo_col:
            st.image(avatar_url, width=90)
    else:
        st.markdown(f"## {full_name_display}")
        if role_val:
            st.caption(role_val)
        if contact:
            st.caption(contact)

    st.markdown("---")

    def _sec(label):
        st.markdown(f"**{label}**")

    def _list_items(items):
        if isinstance(items, list):
            for item in items:
                if str(item).strip():
                    st.write(f"- {item}")
        elif items:
            st.write(str(items))

    if cv.get("professional_summary"):
        _sec(t("cv_professional_summary"))
        st.write(cv["professional_summary"])

    for key, label in [
        ("subjects",           t("cv_subjects")),
        ("teaching_stages",    t("cv_teaching_stages")),
        ("teaching_languages", t("cv_teaching_languages")),
    ]:
        val = cv.get(key)
        if val:
            _sec(label)
            st.write(", ".join(_translate_cv_list(key, val)))

    for key, label in [
        ("education",     t("cv_education")),
        ("certifications",t("cv_certifications")),
        ("experience",    t("cv_experience")),
        ("skills",        t("cv_skills")),
    ]:
        val = cv.get(key)
        if val:
            _sec(label)
            _list_items(val)

    avail = str(cv.get("availability") or "").strip()
    rate  = str(cv.get("rate") or "").strip()
    if avail or rate:
        _sec(t("cv_availability_rate"))
        if avail:
            st.write(f"{t('cv_availability')}: {avail}")
        if rate:
            st.write(f"{t('cv_rate')}: {rate}")

    st.markdown("---")

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(cv.get("full_name") or "cv").strip()) or "cv"
    pdf_bytes = build_cv_pdf_bytes(cv)
    st.download_button(
        label=t("download_cv_pdf"),
        data=pdf_bytes,
        file_name=f"cv_{safe_name}.pdf",
        mime="application/pdf",
        key=f"dl_cv_pdf_{safe_name}_{id(cv)}",
        use_container_width=True,
    )

    if not read_only:
        c1, c2 = st.columns(2)
        with c1:
            if st.button(t("save_cv"), key="btn_save_cv", use_container_width=True):
                ok = save_cv_record(
                    cv_dict=cv,
                    source_type=source_type,
                    title=title or str(cv.get("title") or cv.get("full_name") or t("my_cv")),
                    ai_prompt=ai_prompt,
                )
                if ok:
                    st.success(t("cv_saved"))
                    for k in ("quick_cv_result", "quick_cv_title", "quick_cv_source_type", "quick_cv_ai_prompt"):
                        st.session_state.pop(k, None)
                    st.rerun()
        with c2:
            if st.button(t("discard_cv"), key="btn_discard_cv", use_container_width=True):
                for k in ("quick_cv_result", "quick_cv_title", "quick_cv_source_type", "quick_cv_ai_prompt"):
                    st.session_state.pop(k, None)
                st.rerun()


# -----------------------------------------------------------------------
# UI: LIBRARY CARDS
# -----------------------------------------------------------------------

def delete_cv_record(record_id: str) -> bool:
    try:
        get_sb().table("professional_profiles").delete().eq("id", record_id).execute()
        clear_app_caches()
        return True
    except Exception as e:
        st.warning(f"{t('record_delete_failed')}: {e}")
        return False


def render_cv_library_cards(df: pd.DataFrame, prefix: str) -> None:
    if df is None or df.empty:
        return

    for i, row in df.reset_index(drop=True).iterrows():
        row_id     = row.get("id", i)
        title      = str(row.get("title") or t("untitled_plan")).strip()
        source_type= str(row.get("source_type") or "").strip()
        created_at = str(row.get("created_at") or "")[:16]
        employer   = str(row.get("target_employer") or "").strip()

        with st.container(border=True):
            top_l, top_r = st.columns([5, 1])
            with top_l:
                st.markdown(f"**{title}**")
                meta = []
                if source_type:
                    meta.append(f"{t('source_type')}: {t('mode_ai') if source_type == 'ai' else t('mode_template')}")
                if employer:
                    meta.append(f"{t('cv_target_employer')}: {employer}")
                if created_at:
                    meta.append(f"{t('date')}: {created_at}")
                if meta:
                    st.caption(" · ".join(meta))
            with top_r:
                _btn_col1, _btn_col2 = st.columns(2)
                with _btn_col1:
                    if st.button(t("view"), key=f"{prefix}_view_{row_id}_{i}", use_container_width=True):
                        st.session_state[f"{prefix}_selected"] = row.to_dict()
                        st.toast(t("scroll_down_to_view"))
                        st.rerun()
                with _btn_col2:
                    if st.button("🗑️", key=f"{prefix}_del_{row_id}_{i}", use_container_width=True, help=t("delete")):
                        if delete_cv_record(str(row_id)):
                            st.session_state.pop(f"{prefix}_selected", None)
                            st.rerun()
                        else:
                            st.error(t("delete_failed"))


# -----------------------------------------------------------------------
# UI: MAIN CV BUILDER EXPANDER
# -----------------------------------------------------------------------
def _sex_label(value: str) -> str:
    mapping = {
        "male": t("sex_male"),
        "female": t("sex_female"),
        "other": t("sex_other"),
        "prefer_not_to_say": t("sex_prefer_not_to_say"),
        "": t("select_option"),
    }
    return mapping.get(str(value or "").strip(), str(value or ""))

def render_quick_cv_builder_expander() -> None:
    from core.database import load_profile_row, upsert_profile_row

    user_id = get_current_user_id()
    profile = load_profile_row(user_id) if user_id else {}

    _current_cv_owner = str(st.session_state.get("_quick_cv_owner") or "")
    _current_user_id = str(user_id or "")

    if _current_cv_owner != _current_user_id:
        for k in (
            "quick_cv_result",
            "quick_cv_title",
            "quick_cv_source_type",
            "quick_cv_ai_prompt",
            "quick_cl_result",
            "quick_cl_title",
            "quick_cl_ai_prompt",
            "cv_import_applied",
        ):
            st.session_state.pop(k, None)

        st.session_state["_quick_cv_owner"] = _current_user_id

    with st.expander(t("quick_cv_builder"), expanded=False):
        st.caption(t("quick_cv_caption"))
        usage = get_ai_cv_usage_status()

        # ── Import from existing PDF ──────────────────────────────────────
        with st.container(border=True):
            st.caption(t("cv_import_hint"))
            _upload_col, _btn_col = st.columns([4, 1])
            with _upload_col:
                imported_pdf = st.file_uploader(
                    t("cv_import_pdf_label"),
                    type=["pdf"],
                    key="cv_import_pdf_upload",
                    label_visibility="collapsed",
                )
            with _btn_col:
                _import_btn = st.button(
                    t("cv_import_btn"),
                    key="btn_cv_import_pdf",
                    disabled=imported_pdf is None,
                    use_container_width=True,
                )

            if _import_btn and imported_pdf is not None:
                with st.spinner(t("cv_importing")):
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(imported_pdf)
                        pdf_text = "\n".join(
                            page.extract_text() or "" for page in reader.pages
                        ).strip()
                        if not pdf_text:
                            st.error(t("cv_import_no_text"))
                        else:
                            parsed = _cv().extract_cv_from_pdf_text(pdf_text)
                            # Safely stringify list items (AI may return dicts)
                            def _to_str_list(items):
                                out = []
                                for x in (items or []):
                                    if isinstance(x, dict):
                                        out.append(" – ".join(str(v) for v in x.values() if v))
                                    else:
                                        out.append(str(x))
                                return out
                            # Map parsed fields into widget session_state keys
                            _field_map = {
                                "cv_full_name":  str(parsed.get("full_name") or "").strip(),
                                "cv_email":      str(parsed.get("email") or "").strip(),
                                "cv_phone":      _sanitize_phone(parsed.get("phone") or ""),
                                "cv_location":   str(parsed.get("location") or "").strip(),
                                "cv_summary":    str(parsed.get("professional_summary") or "").strip(),
                                "cv_education":  "\n".join(_to_str_list(parsed.get("education"))),
                                "cv_experience": "\n".join(_to_str_list(parsed.get("experience"))),
                                "cv_certs":      ", ".join(_to_str_list(parsed.get("certifications"))),
                                "cv_skills_input": ", ".join(_to_str_list(parsed.get("skills"))),
                                "cv_availability": str(parsed.get("availability") or "").strip(),
                                "cv_rate":       str(parsed.get("rate") or "").strip(),
                            }
                            for k, v in _field_map.items():
                                if v:
                                    st.session_state[k] = v
                            # Date of birth (needs datetime.date for st.date_input)
                            _imp_dob = _parse_dob(parsed.get("date_of_birth"))
                            if _imp_dob:
                                st.session_state["cv_dob"] = _imp_dob
                            # Subjects / stages / langs from import
                            _imp_subjects = [s for s in (parsed.get("subjects") or []) if s in PROFILE_SUBJECT_OPTIONS]
                            if _imp_subjects:
                                st.session_state["cv_subjects"] = _imp_subjects
                            _imp_stages = [s for s in (parsed.get("teaching_stages") or []) if s in PROFILE_STAGE_OPTIONS]
                            if _imp_stages:
                                st.session_state["cv_stages"] = _imp_stages
                            _imp_langs = [l for l in (parsed.get("teaching_languages") or []) if l in PROFILE_TEACH_LANG_OPTIONS]
                            if _imp_langs:
                                st.session_state["cv_langs"] = _imp_langs
                            # Sex selectbox
                            _imp_sex = str(parsed.get("sex") or "").strip()
                            if _imp_sex in SEX_OPTIONS_RAW:
                                st.session_state["cv_sex"] = _imp_sex
                            # Role
                            _imp_role = str(parsed.get("role") or "").strip().lower()
                            if _imp_role in ("teacher", "tutor"):
                                st.session_state["cv_role"] = _imp_role
                            st.session_state["cv_import_applied"] = True
                            st.rerun()
                    except Exception as exc:
                        st.error(f"{t('cv_import_failed')}: {exc}")

            if st.session_state.get("cv_import_applied"):
                st.success(t("cv_import_success"))
                if st.button(t("cv_import_clear"), key="btn_cv_import_clear"):
                    st.session_state.pop("cv_import_applied", None)
                    st.rerun()

        cv_mode = st.radio(
            t("generation_mode"),
            options=["template", "ai"],
            horizontal=True,
            format_func=lambda x: t("mode_ai") if x == "ai" else t("mode_template"),
            key="quick_cv_mode",
        )

        if cv_mode == "ai":
            st.caption(t("ai_plans_left_today", remaining=usage["remaining_today"], limit=AI_CV_DAILY_LIMIT))

        # ── Profile picture toggle ───────────────────────────────────────
        _avatar = str(st.session_state.get("avatar_url") or "").strip()
        _has_avatar = bool(_avatar)
        cv_include_photo = st.checkbox(
            t("cv_include_photo"),
            value=_has_avatar,
            key="cv_include_photo",
            disabled=not _has_avatar,
            help=t("cv_include_photo_hint") if not _has_avatar else None,
        )
        _avatar_for_cv = _avatar if cv_include_photo else ""

        # ── Personal info ────────────────────────────────────────────────
        st.markdown(f"**{t('cv_personal_info')}**")

        # Initialise defaults only when session_state key is absent
        # (import or previous run may have set them already)
        if "cv_full_name" not in st.session_state:
            st.session_state["cv_full_name"] = str(profile.get("display_name") or st.session_state.get("user_name") or "")
        if "cv_email" not in st.session_state:
            st.session_state["cv_email"] = str(profile.get("email") or st.session_state.get("user_email") or "")
        if "cv_phone" not in st.session_state:
            st.session_state["cv_phone"] = _sanitize_phone(profile.get("phone_number") or "")
        if "cv_location" not in st.session_state:
            st.session_state["cv_location"] = _normalize_country_value(profile.get("country") or "")

        pi1, pi2, pi3 = st.columns(3)
        
        with pi1:
            cv_full_name = st.text_input(
                t("cv_full_name_label"),
                key="cv_full_name",
            )

        with pi2:
            cv_email = st.text_input(
                t("email"),
                key="cv_email",
            )

        with pi3:
            cv_phone_raw = st.text_input(
                t("phone"),
                placeholder="+1234567890",
                key="cv_phone",
                help=t("phone_format_hint"),
            )
            cv_phone = _sanitize_phone(cv_phone_raw)
  
        pi4, pi5, pi6 = st.columns(3)
        with pi4:
            _country_opts = _country_options()

            if "cv_location" not in st.session_state:
                st.session_state["cv_location"] = _normalize_country_value(profile.get("country") or "")

            _current_country = _normalize_country_value(st.session_state.get("cv_location"))
            if _current_country not in _country_opts:
                st.session_state["cv_location"] = ""

            cv_location = st.selectbox(
                t("country_label"),
                options=_country_opts,
                format_func=lambda x: x if x else t("select_option"),
                key="cv_location",
            )
        with pi5:
            import datetime as _dt_mod
            _dob_val = _parse_dob(profile.get("date_of_birth"))
            cv_dob = st.date_input(
                t("date_of_birth"),
                value=_dob_val,
                min_value=_dt_mod.date(1940, 1, 1),
                max_value=_dt_mod.date.today(),
                format="YYYY-MM-DD",
                key="cv_dob",
            )

        with pi6:
            def _normalize_sex_value(raw) -> str:
                v = str(raw or "").strip().lower()
                aliases = {
                    "male": "male",
                    "female": "female",
                    "other": "other",
                    "prefer_not_to_say": "prefer_not_to_say",
                    "prefer not to say": "prefer_not_to_say",
                    "prefer-not-to-say": "prefer_not_to_say",
                    "not specified": "",
                    "unknown": "",
                    "none": "",
                    "null": "",
                    "nan": "",
                    "": "",
                }
                return aliases.get(v, "")

            _saved_profile_sex = _normalize_sex_value(profile.get("sex"))
            _session_sex = _normalize_sex_value(st.session_state.get("cv_sex"))

            if not _session_sex and _saved_profile_sex:
                st.session_state["cv_sex"] = _saved_profile_sex
            elif "cv_sex" not in st.session_state:
                st.session_state["cv_sex"] = ""

            cv_sex = st.selectbox(
                t("sex"),
                options=SEX_OPTIONS_RAW,
                format_func=_sex_label,
                key="cv_sex",
            )

        # ── Teaching profile ─────────────────────────────────────────────
        cv_subjects = st.multiselect(
            t("primary_subjects_label"),
            options=PROFILE_SUBJECT_OPTIONS,
            default=st.session_state.get("cv_subjects", []),
            format_func=_subject_label,
            key="cv_subjects",
            placeholder=t("select_option"),
        )

        cv_other_subject = ""
        if "other" in cv_subjects:
            cv_other_subject = st.text_input(
                t("other_subject_label"),
                key="cv_other_subject",
            ).strip()

        cv_col1, cv_col2 = st.columns(2)
        with cv_col1:
            cv_stages = st.multiselect(
                t("teaching_stages_label"),
                options=PROFILE_STAGE_OPTIONS,
                default=st.session_state.get("cv_stages", []),
                format_func=_stage_label,
                key="cv_stages",
                placeholder=t("select_option"),
            )
        with cv_col2:
            cv_langs = st.multiselect(
                t("teaching_languages_label"),
                options=PROFILE_TEACH_LANG_OPTIONS,
                default=st.session_state.get("cv_langs", []),
                format_func=_lang_label,
                key="cv_langs",
                placeholder=t("select_option"),
            )

        role_val = str(profile.get("role") or "teacher")
        cv_role = st.selectbox(
            t("role_label"),
            ["teacher", "tutor"],
            index=0 if role_val == "teacher" else 1,
            format_func=lambda x: t("teacher_role") if x == "teacher" else t("tutor_role"),
            key="cv_role",
        )

        # ── Optional details ─────────────────────────────────────────────
        with st.expander(t("cv_optional_sections"), expanded=False):
            cv_summary = st.text_area(
                t("cv_professional_summary"),
                value="",
                placeholder=t("cv_summary_placeholder"),
                height=80,
                key="cv_summary",
            )
            cv_education = st.text_area(
                t("cv_education"),
                value="",
                placeholder=t("cv_education_placeholder"),
                height=70,
                key="cv_education",
            )
            cv_certs = st.text_input(
                t("cv_certifications"),
                key="cv_certs",
                placeholder=t("cv_certs_placeholder"),
            )
            cv_experience = st.text_area(
                t("cv_experience"),
                value="",
                placeholder=t("cv_experience_placeholder"),
                height=70,
                key="cv_experience",
            )
            cv_skills = st.text_input(
                t("cv_skills"),
                key="cv_skills_input",
                placeholder=t("cv_skills_placeholder"),
            )
            va1, va2 = st.columns(2)
            with va1:
                cv_availability = st.text_input(
                    t("cv_availability"),
                    key="cv_availability",
                    placeholder=t("cv_availability_placeholder"),
                )
            with va2:
                cv_rate = st.text_input(
                    t("cv_rate"),
                    key="cv_rate",
                    placeholder=t("cv_rate_placeholder"),
                )

        # ── AI-only options ───────────────────────────────────────────────
        if cv_mode == "ai":
            cv_ai_prompt = st.text_area(
                t("cv_ai_prompt"),
                placeholder=t("cv_ai_prompt_placeholder"),
                height=80,
                key="cv_ai_prompt",
            )
            cv_also_cl = st.checkbox(t("cv_also_generate_cover_letter"), key="cv_also_cl")
            if cv_also_cl:
                cv_cl_prompt = st.text_area(
                    t("cv_cover_letter_prompt"),
                    placeholder=t("cv_cl_prompt_placeholder"),
                    height=70,
                    key="cv_cl_prompt",
                )
            else:
                cv_cl_prompt = ""
        else:
            cv_ai_prompt = ""
            cv_also_cl = False
            cv_cl_prompt = ""

        cv_doc_title = st.text_input(
            t("cv_document_title"),
            value=f"{t('cv')} – {cv_full_name.strip()}" if cv_full_name.strip() else t("my_cv"),
            key="cv_doc_title",
        )

        if st.button(t("generate_cv"), key="btn_generate_cv", use_container_width=True):
            validation_errors = []

            if not cv_full_name.strip():
                validation_errors.append(t("cv_name_required"))

            if cv_phone_raw.strip() and not _is_valid_cv_phone(cv_phone_raw):
                validation_errors.append(t("cv_phone_invalid"))

            if not cv_location.strip():
                validation_errors.append(t("cv_country_required"))
            elif not _normalize_country_value(cv_location):
                validation_errors.append(t("cv_country_invalid"))

            if not cv_subjects:
                validation_errors.append(t("cv_subject_required"))

            if "other" in cv_subjects and not cv_other_subject:
                validation_errors.append(t("enter_subject_name"))    

            if not cv_stages:
                validation_errors.append(t("cv_stage_required"))

            if not cv_langs:
                validation_errors.append(t("cv_language_required"))

            if cv_mode == "ai" and usage["used_today"] >= AI_CV_DAILY_LIMIT:
                validation_errors.append(t("ai_limit_reached"))

            if cv_mode == "ai" and not usage["cooldown_ok"]:
                validation_errors.append(
                    t("ai_cooldown_active", seconds=usage["seconds_left"])
                )

            if validation_errors:
                for msg in validation_errors:
                    st.error(msg)
            else:
                if user_id:
                    _profile_patch = {
                        "country": cv_location.strip(),
                        "date_of_birth": str(cv_dob) if cv_dob else None,
                        "sex": _normalize_sex_value(cv_sex) if cv_sex else None,
                        "primary_subjects": effective_cv_subjects,
                        "teaching_stages": cv_stages,
                        "teaching_languages": cv_langs,
                        "role": cv_role,
                    }

                    _profile_ok = upsert_profile_row(user_id, _profile_patch)
                    if not _profile_ok:
                        st.error(t("cv_profile_save_failed"))
                        st.stop()

                    clear_app_caches()

                _kwargs = dict(
                    full_name=cv_full_name.strip(),
                    email=cv_email.strip(),
                    phone=cv_phone.strip(),
                    location=cv_location.strip(),
                    date_of_birth=str(cv_dob) if cv_dob else "",
                    sex=_normalize_sex_value(cv_sex) if cv_sex else "",
                    subjects=effective_cv_subjects,
                    teaching_stages=cv_stages,
                    teaching_languages=cv_langs,
                    professional_summary=cv_summary.strip(),
                    education_text=cv_education.strip(),
                    certifications_text=cv_certs.strip(),
                    experience_text=cv_experience.strip(),
                    skills_text=cv_skills.strip(),
                    availability=cv_availability.strip(),
                    rate=cv_rate.strip(),
                    role=cv_role,
                    avatar_url=_avatar_for_cv,
                )

                with st.spinner(t("generating_cv")):
                    try:
                        effective_cv_subjects = [s for s in cv_subjects if s != "other"]
                        if "other" in cv_subjects and cv_other_subject:
                            effective_cv_subjects.append(cv_other_subject) 

                        if cv_mode == "ai":
                            _log_ai_cv("requested", {"doc": "cv"})
                            generated_cv = _cv().build_ai_cv(
                                **_kwargs,
                                user_prompt=cv_ai_prompt,
                            )
                            _log_ai_cv("success", {"doc": "cv"})
                        else:
                            generated_cv = _cv().build_template_cv(**_kwargs)

                        st.session_state["quick_cv_result"] = generated_cv
                        st.session_state["quick_cv_title"] = cv_doc_title.strip()
                        st.session_state["quick_cv_source_type"] = cv_mode
                        st.session_state["quick_cv_ai_prompt"] = cv_ai_prompt
                        st.session_state["_quick_cv_owner"] = str(user_id or "")

                    except Exception as e:
                        st.error(f"{t('cv_generation_failed')}: {e}")

                if cv_mode == "ai" and cv_also_cl and st.session_state.get("quick_cv_result"):
                    with st.spinner(t("generating_cover_letter")):
                        try:
                            _log_ai_cv("requested", {"doc": "cover_letter"})
                            cl_text = _cv().build_ai_cover_letter(
                                cv=st.session_state["quick_cv_result"],
                                user_prompt=cv_cl_prompt,
                            )
                            _log_ai_cv("success", {"doc": "cover_letter"})
                            st.session_state["quick_cl_result"] = cl_text
                            st.session_state["quick_cl_title"] = (
                                f"{t('cover_letter')} – {cv_full_name.strip()}"
                                if cv_full_name.strip()
                                else t("my_cover_letter")
                            )
                            st.session_state["quick_cl_ai_prompt"] = cv_cl_prompt
                        except Exception as e:
                            st.error(f"{t('cv_generation_failed')}: {e}")
        # ── Display CV result ────────────────────────────────────────────
        cv_result = st.session_state.get("quick_cv_result")
        if cv_result:
            st.markdown("---")
            render_cv_result(
                cv=cv_result,
                read_only=False,
                source_type=st.session_state.get("quick_cv_source_type", "template"),
                ai_prompt=st.session_state.get("quick_cv_ai_prompt", ""),
                title=st.session_state.get("quick_cv_title", ""),
            )

        # ── Display cover letter result ──────────────────────────────────
        cl_result = st.session_state.get("quick_cl_result")
        if cl_result:
            st.markdown("---")
            st.markdown(f"### {t('cover_letter')}")
            st.success(t("cover_letter_ready"))
            st.text_area(
                t("cover_letter_content"),
                value=cl_result,
                height=300,
                key="cv_cl_display",
            )
            cl_title = st.session_state.get("quick_cl_title", t("my_cover_letter"))
            cl_pdf   = build_cover_letter_pdf_bytes(cl_result, cl_title)
            safe_cl  = re.sub(r"[^A-Za-z0-9._-]+", "_", cl_title) or "cover_letter"
            st.download_button(
                label=t("download_cl_pdf"),
                data=cl_pdf,
                file_name=f"{safe_cl}.pdf",
                mime="application/pdf",
                key=f"dl_cl_pdf_{safe_cl}",
                use_container_width=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("save_cover_letter"), key="btn_save_cl", use_container_width=True):
                    ok = save_cover_letter_record(
                        content=cl_result,
                        title=cl_title,
                        ai_prompt=st.session_state.get("quick_cl_ai_prompt", ""),
                    )
                    if ok:
                        st.success(t("cover_letter_saved"))
                        for k in ("quick_cl_result", "quick_cl_title", "quick_cl_ai_prompt"):
                            st.session_state.pop(k, None)
                        st.rerun()
            with c2:
                if st.button(t("discard_cover_letter"), key="btn_discard_cl", use_container_width=True):
                    for k in ("quick_cl_result", "quick_cl_title", "quick_cl_ai_prompt"):
                        st.session_state.pop(k, None)
                    st.rerun()
