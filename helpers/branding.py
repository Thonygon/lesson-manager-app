# CLASSIO — Branding Helper
# ============================================================
import os
import re
import uuid
from io import BytesIO
from datetime import datetime as _dt, timezone

import streamlit as st
import base64

from core.database import get_sb
from core.state import get_current_user_id
from core.i18n import t


# ── Constants ────────────────────────────────────────────────────────
ALLOWED_IMAGE_TYPES = ("png", "jpg", "jpeg")
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB
LOGO_MAX_HEIGHT_CM = 4.0
FOOTER_MAX_HEIGHT_CM = 1.8
_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9_\-.]")
BRANDING_BUCKET = "branding"

_DEFAULT_LOGO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png")
)


# ── Defaults ─────────────────────────────────────────────────────────

def _default_branding() -> dict:
    """
    Default Classio branding.
    DejaVu Sans + standard size come from font_manager.py defaults.
    """
    return {
        "header_logo_url": "",
        "footer_image_url": "",
        "brand_name": "",
        "department": "",
        "header_style": "standard",
        "header_enabled": False,
        "footer_enabled": False,
        "branding_font": "dejavu",
        "branding_font_size": "standard",
    }

def _image_file_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# ── Data access ──────────────────────────────────────────────────────

def get_user_branding(user_id: str | None = None) -> dict:
    """
    Return branding settings for the given user.
    Uses safe Classio defaults when no record exists.
    """
    uid = str(user_id or get_current_user_id() or "").strip()
    if not uid:
        return _default_branding()

    cache_key = f"_branding_{uid}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict):
        return cached

    try:
        sb = get_sb()
        res = (
            sb.table("branding_settings")
            .select("*")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if rows:
            row = rows[0] or {}
            branding = {
                "header_logo_url": str(row.get("header_logo_url") or "").strip(),
                "footer_image_url": str(row.get("footer_image_url") or "").strip(),
                "brand_name": str(row.get("brand_name") or "").strip(),
                "department": str(row.get("department") or "").strip(),
                "header_style": str(row.get("header_style") or "standard").strip(),
                "header_enabled": bool(row.get("header_enabled")),
                "footer_enabled": bool(row.get("footer_enabled")),
                "branding_font": str(row.get("branding_font") or "dejavu").strip(),
                "branding_font_size": str(row.get("branding_font_size") or "standard").strip(),
            }
            st.session_state[cache_key] = branding
            return branding
    except Exception:
        pass

    branding = _default_branding()
    st.session_state[cache_key] = branding
    return branding


def save_user_branding(
    brand_name: str = "",
    department: str = "",
    header_style: str = "standard",
    header_enabled: bool = False,
    footer_enabled: bool = False,
    header_logo_url: str = "",
    footer_image_url: str = "",
    branding_font: str = "dejavu",
    branding_font_size: str = "standard",
) -> bool:
    """
    Save branding settings for the current user.
    """
    uid = get_current_user_id()
    if not uid:
        return False

    if header_style not in ("standard", "school"):
        header_style = "standard"

    from helpers.font_manager import FONT_REGISTRY, SIZE_PRESETS

    if branding_font not in FONT_REGISTRY:
        branding_font = "dejavu"
    if branding_font_size not in SIZE_PRESETS:
        branding_font_size = "standard"

    payload = {
        "user_id": uid,
        "brand_name": str(brand_name or "").strip()[:200],
        "department": str(department or "").strip()[:200],
        "header_style": header_style,
        "header_enabled": bool(header_enabled),
        "footer_enabled": bool(footer_enabled),
        "header_logo_url": str(header_logo_url or "").strip(),
        "footer_image_url": str(footer_image_url or "").strip(),
        "branding_font": branding_font,
        "branding_font_size": branding_font_size,
        "updated_at": _dt.now(timezone.utc).isoformat(),
    }

    try:
        sb = get_sb()
        existing = (
            sb.table("branding_settings")
            .select("id")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        rows = getattr(existing, "data", None) or []

        if rows:
            sb.table("branding_settings").update(payload).eq("user_id", uid).execute()
        else:
            payload["created_at"] = _dt.now(timezone.utc).isoformat()
            sb.table("branding_settings").insert(payload).execute()

        clear_branding_cache(uid)
        return True
    except Exception as e:
        st.warning(f"{t('branding_save_failed')}: {e}")
        return False


def clear_branding_cache(user_id: str | None = None) -> None:
    uid = str(user_id or get_current_user_id() or "").strip()
    if uid:
        st.session_state.pop(f"_branding_{uid}", None)


# ── Image upload / validation ────────────────────────────────────────

def _safe_filename(name: str) -> str:
    name = str(name or "unknown.png").strip()
    name = _SAFE_FILENAME_RE.sub("_", name)
    return name[:100]


def _validate_image_upload(uploaded_file) -> str | None:
    """
    Validate uploaded file.
    Returns translated error message or None if OK.
    """
    if uploaded_file is None:
        return t("branding_no_file_selected")

    name = str(getattr(uploaded_file, "name", "") or "").strip().lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_IMAGE_TYPES:
        return t("branding_invalid_file_type")

    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size > MAX_UPLOAD_BYTES:
        return t("branding_file_too_large")

    return None


def upload_branding_image(uploaded_file, image_type: str = "header") -> str:
    """
    Upload a branding image to Supabase storage.
    image_type: 'header' or 'footer'
    Returns the public URL.
    Raises RuntimeError on failure.
    """
    uid = get_current_user_id()
    if not uid:
        raise RuntimeError(t("branding_not_logged_in"))

    if image_type not in ("header", "footer"):
        image_type = "header"

    error = _validate_image_upload(uploaded_file)
    if error:
        raise RuntimeError(error)

    raw_name = str(getattr(uploaded_file, "name", "image.png")).strip()
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else "png"
    safe_name = f"{image_type}_{uuid.uuid4().hex}.{ext}"
    object_path = f"{uid}/{safe_name}"

    content_type_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }
    content_type = content_type_map.get(ext, "image/png")

    file_bytes = uploaded_file.read()

    try:
        sb = get_sb()

        # Remove old images of the same type for this user
        try:
            existing = sb.storage.from_(BRANDING_BUCKET).list(uid)
            for item in existing or []:
                item_name = str(item.get("name") or "")
                if item_name.startswith(f"{image_type}_"):
                    sb.storage.from_(BRANDING_BUCKET).remove([f"{uid}/{item_name}"])
        except Exception:
            pass

        sb.storage.from_(BRANDING_BUCKET).upload(
            path=object_path,
            file=file_bytes,
            file_options={
                "content-type": content_type,
                "upsert": "true",
            },
        )
    except Exception as e:
        raise RuntimeError(f"{t('branding_upload_failed')}: {e}")

    try:
        public_url = sb.storage.from_(BRANDING_BUCKET).get_public_url(object_path)
    except Exception as e:
        raise RuntimeError(f"{t('branding_url_failed')}: {e}")

    if isinstance(public_url, dict):
        public_url = public_url.get("publicUrl") or public_url.get("public_url") or ""

    public_url = str(public_url or "").strip()
    if not public_url:
        raise RuntimeError(t("branding_no_public_url"))

    return public_url


def delete_branding_image(image_type: str = "header") -> bool:
    """
    Delete all branding images of the given type for the current user.
    """
    uid = get_current_user_id()
    if not uid:
        return False

    if image_type not in ("header", "footer"):
        return False

    try:
        sb = get_sb()
        existing = sb.storage.from_(BRANDING_BUCKET).list(uid)
        for item in existing or []:
            item_name = str(item.get("name") or "")
            if item_name.startswith(f"{image_type}_"):
                sb.storage.from_(BRANDING_BUCKET).remove([f"{uid}/{item_name}"])
        return True
    except Exception:
        return False


def delete_all_branding_images() -> None:
    """
    Remove both header and footer branding images for current user.
    """
    delete_branding_image("header")
    delete_branding_image("footer")


# ── Branding state helpers ───────────────────────────────────────────

def has_custom_branding(branding: dict | None = None) -> bool:
    """
    True when custom branding is actually active.
    """
    if branding is None:
        branding = get_user_branding()

    header_enabled = bool(branding.get("header_enabled"))
    footer_enabled = bool(branding.get("footer_enabled"))
    brand_name = str(branding.get("brand_name") or "").strip()
    department = str(branding.get("department") or "").strip()
    header_logo_url = str(branding.get("header_logo_url") or "").strip()
    footer_image_url = str(branding.get("footer_image_url") or "").strip()
    header_style = str(branding.get("header_style") or "standard").strip()
    branding_font = str(branding.get("branding_font") or "dejavu").strip()
    branding_font_size = str(branding.get("branding_font_size") or "standard").strip()

    has_non_default_values = any([
        brand_name,
        department,
        header_logo_url,
        footer_image_url,
        header_style != "standard",
        branding_font != "dejavu",
        branding_font_size != "standard",
    ])

    return (header_enabled or footer_enabled) and (
        has_non_default_values or header_enabled or footer_enabled
    )


def resolve_is_public(branding: dict | None = None) -> bool:
    """
    If custom branding is active, documents must be private.
    If Classio default branding is active, documents can be public.
    """
    return not has_custom_branding(branding)


# ── PDF header builders ──────────────────────────────────────────────

def build_worksheet_header(
    story: list,
    ws: dict,
    branding: dict,
    *,
    styles: dict,
    doc,
    bold_font: str = "Helvetica-Bold",
    body_font: str = "Helvetica",
    _t_pdf=None,
    _pdf_safe_text=None,
    subject: str = "",
    topic: str = "",
    ws_type: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
) -> None:
    """
    Build the worksheet header. Dispatches to school or standard layout
    based on branding['header_style'].
    """
    if _t_pdf is None:
        _t_pdf = lambda k, **kw: t(k, **kw)

    if _pdf_safe_text is None:
        from xml.sax.saxutils import escape as xml_escape
        import unicodedata
        _pdf_safe_text = lambda v: xml_escape(unicodedata.normalize("NFC", str(v or "")))

    header_style = str(branding.get("header_style") or "standard").strip()
    header_enabled = bool(branding.get("header_enabled"))

    if header_style == "school" and header_enabled:
        _build_school_header(
            story,
            ws,
            branding,
            styles=styles,
            doc=doc,
            bold_font=bold_font,
            body_font=body_font,
            _t_pdf=_t_pdf,
            _pdf_safe_text=_pdf_safe_text,
        )
    else:
        _build_standard_header(
            story,
            ws,
            branding,
            styles=styles,
            doc=doc,
            bold_font=bold_font,
            body_font=body_font,
            _t_pdf=_t_pdf,
            _pdf_safe_text=_pdf_safe_text,
            subject=subject,
            topic=topic,
            ws_type=ws_type,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
        )


def _build_school_header(
    story,
    ws,
    branding,
    *,
    styles,
    doc,
    bold_font,
    body_font,
    _t_pdf,
    _pdf_safe_text,
):
    """
    School-style worksheet header layout.
    """
    from io import BytesIO as _BytesIO
    import urllib.request

    from reportlab.lib.units import cm
    from reportlab.platypus import Spacer, Paragraph, Table, TableStyle, Image as RLImage, HRFlowable
    from styles.pdf_styles import get_school_header_styles, C as _C

    _hs = get_school_header_styles(body_font, bold_font)

    logo_url = str(branding.get("header_logo_url") or "").strip()
    brand_name = str(branding.get("brand_name") or "").strip()
    department = str(branding.get("department") or "").strip()
    title = str(ws.get("title") or _t_pdf("untitled_worksheet")).strip()

    page_width = doc.width

    if logo_url:
        try:
            req = urllib.request.Request(logo_url, headers={"User-Agent": "Classio/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                img_data = resp.read()

            img_buf = _BytesIO(img_data)
            logo_img = RLImage(
                img_buf,
                width=LOGO_MAX_HEIGHT_CM * cm,
                height=LOGO_MAX_HEIGHT_CM * cm,
                kind="proportional",
            )
            logo_table = Table([[logo_img]], colWidths=[page_width])
            logo_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(logo_table)
            story.append(Spacer(1, 4))
        except Exception:
            pass

    if brand_name:
        story.append(Paragraph(_pdf_safe_text(brand_name), _hs["brand"]))

    if department:
        story.append(Paragraph(_pdf_safe_text(department), _hs["department"]))

    story.append(Spacer(1, 4))
    story.append(Paragraph(_pdf_safe_text(title), _hs["title"]))
    story.append(Spacer(1, 4))

    name_label = (
        f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('student_name_label'))}:</font> "
        f"_______________________________"
    )
    class_label = (
        f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('class_label'))}:</font> "
        f"__________"
    )
    date_label = (
        f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('date_label'))}:</font> "
        f"__________"
    )

    fields_table = Table(
        [[
            Paragraph(name_label, _hs["field"]),
            Paragraph(class_label, _hs["field"]),
            Paragraph(date_label, _hs["field"]),
        ]],
        colWidths=[page_width * 0.50, page_width * 0.25, page_width * 0.25],
    )
    fields_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(fields_table)
    story.append(Spacer(1, 6))

    story.append(HRFlowable(width="100%", thickness=0.8, color=_C.BORDER))
    story.append(Spacer(1, 6))

    instructions = str(ws.get("instructions") or "").strip()
    if instructions:
        story.append(Paragraph(_pdf_safe_text(_t_pdf("ws_instructions")), _hs["instr_heading"]))
        story.append(Paragraph(_pdf_safe_text(instructions), _hs["instr_body"]))
        story.append(Spacer(1, 4))


def _build_standard_header(
    story,
    ws,
    branding,
    *,
    styles,
    doc,
    bold_font,
    body_font,
    _t_pdf,
    _pdf_safe_text,
    subject="",
    topic="",
    ws_type="",
    learner_stage="",
    level_or_band="",
):
    """
    Standard header layout with optional custom branding logo.
    Otherwise it falls back to the default Classio logo.
    """
    from io import BytesIO as _BytesIO
    import urllib.request

    from reportlab.lib.units import cm
    from reportlab.platypus import Spacer, Paragraph, Image as RLImage
    from styles.pdf_styles import get_standard_header_styles

    _hs = get_standard_header_styles(body_font, bold_font)

    logo_url = str(branding.get("header_logo_url") or "").strip()
    header_enabled = bool(branding.get("header_enabled"))

    if header_enabled and logo_url:
        try:
            req = urllib.request.Request(logo_url, headers={"User-Agent": "Classio/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                img_data = resp.read()
            img_buf = _BytesIO(img_data)
            story.append(
                RLImage(
                    img_buf,
                    width=LOGO_MAX_HEIGHT_CM * cm,
                    height=LOGO_MAX_HEIGHT_CM * cm,
                    kind="proportional",
                )
            )
            story.append(Spacer(1, 6))
        except Exception:
            if os.path.isfile(_DEFAULT_LOGO_PATH):
                story.append(
                    RLImage(
                        _DEFAULT_LOGO_PATH,
                        width=2.8 * cm,
                        height=2.8 * cm,
                        kind="proportional",
                    )
                )
                story.append(Spacer(1, 6))
    else:
        if os.path.isfile(_DEFAULT_LOGO_PATH):
            story.append(
                RLImage(
                    _DEFAULT_LOGO_PATH,
                    width=2.8 * cm,
                    height=2.8 * cm,
                    kind="proportional",
                )
            )
            story.append(Spacer(1, 6))

    if header_enabled and branding.get("brand_name"):
        story.append(Paragraph(_pdf_safe_text(branding["brand_name"]), _hs["brand"]))

    story.append(
        Paragraph(
            _pdf_safe_text(ws.get("title") or _t_pdf("untitled_worksheet")),
            _hs["title"],
        )
    )

    meta_line = []

    if subject:
        subject_key = "subject_" + str(subject).strip().lower().replace(" ", "_")
        subject_label = _t_pdf(subject_key)
        if subject_label == subject_key:
            subject_label = str(subject).strip()
        meta_line.append(
            f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('subject_label'))}:</font> "
            f"{_pdf_safe_text(subject_label)}"
        )

    if topic:
        meta_line.append(
            f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('topic_label'))}:</font> "
            f"{_pdf_safe_text(topic)}"
        )

    if ws_type:
        meta_line.append(
            f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('worksheet_type_label'))}:</font> "
            f"{_pdf_safe_text(_t_pdf(ws_type))}"
        )

    if learner_stage:
        stage_label = _t_pdf(learner_stage)
        meta_line.append(
            f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('learner_stage'))}:</font> "
            f"{_pdf_safe_text(stage_label)}"
        )

    if level_or_band:
        lbl = level_or_band if level_or_band in ["A1", "A2", "B1", "B2", "C1", "C2"] else _t_pdf(level_or_band)
        meta_line.append(
            f"<font name='{bold_font}'>{_pdf_safe_text(_t_pdf('level_or_band'))}:</font> "
            f"{_pdf_safe_text(lbl)}"
        )

    if meta_line:
        story.append(Paragraph(" | ".join(meta_line), _hs["body"]))
        story.append(Spacer(1, 8))


def build_pdf_footer_handler(branding: dict, bold_font: str = "Helvetica"):
    """
    Return a ReportLab onPage callback that draws the footer.
    If branding footer is enabled and an image URL exists, draw it.
    Otherwise draw the default 'Classio | page#' footer.
    """
    import urllib.request

    footer_enabled = bool(branding.get("footer_enabled"))
    footer_url = str(branding.get("footer_image_url") or "").strip()
    brand_name = str(branding.get("brand_name") or "").strip()

    footer_image_bytes = None
    if footer_enabled and footer_url:
        try:
            req = urllib.request.Request(footer_url, headers={"User-Agent": "Classio/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                footer_image_bytes = resp.read()
        except Exception:
            footer_image_bytes = None

    def _draw_footer(canvas, doc):
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.lib.utils import ImageReader

        canvas.saveState()

        if footer_image_bytes:
            try:
                img_buf = BytesIO(footer_image_bytes)
                img_reader = ImageReader(img_buf)
                x = doc.leftMargin
                y = 0.3 * cm
                max_w = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
                max_h = FOOTER_MAX_HEIGHT_CM * cm
                canvas.drawImage(
                    img_reader,
                    x,
                    y,
                    width=max_w,
                    height=max_h,
                    preserveAspectRatio=True,
                    anchor="sw",
                    mask="auto",
                )
            except Exception:
                pass

        footer_label = brand_name if (footer_enabled and brand_name) else "Classio"
        footer_text = f"{footer_label} | {canvas.getPageNumber()}"
        canvas.setFont(bold_font, 9)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawRightString(
            doc.pagesize[0] - doc.rightMargin,
            0.9 * cm,
            footer_text,
        )

        canvas.restoreState()

    return _draw_footer


# ── Settings UI ──────────────────────────────────────────────────────

def render_branding_settings() -> None:
    """
    Render branding settings inside the profile dialog.

    Behavior:
    - One toggle only.
    - ON  -> custom branding active, documents become private.
    - OFF -> reset to Classio defaults, documents become public.
    """
    uid = get_current_user_id()
    if not uid:
        st.warning(t("login_required"))
        return

    branding = get_user_branding(uid)

    st.markdown(f"#### 🎨 {t('branding_settings_title')}")

    default_branding = _default_branding()

    custom_branding_enabled = st.toggle(
        t("branding_custom_enabled"),
        value=has_custom_branding(branding),
        key="branding_custom_enabled_toggle",
        help=t("branding_settings_caption"),
    )

    # ── Branding OFF: Classio defaults ────────────────────────────────
    if not custom_branding_enabled:
        st.info(t("branding_default_classio_notice"))

        st.markdown(f"**{t('branding_preview')}**")
        preview_cols = st.columns([1, 3, 1])
        with preview_cols[1]:
            if os.path.isfile(_DEFAULT_LOGO_PATH):
                st.markdown(
                    f"""
                    <div style="text-align:center; margin-bottom:14px;">
                        <img src="data:image/png;base64,{_image_file_to_base64(_DEFAULT_LOGO_PATH)}"
                             style="max-width:120px; height:auto; display:inline-block;" />
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"""
                <div style="text-align:center; font-weight:800; font-size:1.5rem; line-height:1.2; margin-bottom:14px; color:#1D4ED8;">
                    {t("branding_preview_sample_title")}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
                <div style="text-align:justify; font-size:0.98rem; line-height:1.55; color:#334155; margin-bottom:8px;">
                    <b>{t("subject_label")}:</b> {t("english")} |
                    <b>{t("topic_label")}:</b> {t("branding_preview_sample_topic")} |
                    <b>{t("learner_stage")}:</b> {t("stage_upper_primary")} |
                    <b>{t("level_or_band")}:</b> B1
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption(t("branding_public_documents_notice"))

        if st.button(
            t("branding_save_btn"),
            key="branding_save_settings_default",
            use_container_width=True,
            type="primary",
        ):
            delete_all_branding_images()

            ok = save_user_branding(
                brand_name="",
                department="",
                header_style="standard",
                header_enabled=False,
                footer_enabled=False,
                header_logo_url="",
                footer_image_url="",
                branding_font="dejavu",
                branding_font_size="standard",
            )
            if ok:
                st.success(t("branding_saved"))
                clear_branding_cache()
                st.rerun()
        return

    # ── Branding ON: custom settings ──────────────────────────────────
    brand_name = st.text_input(
        t("branding_brand_name"),
        value=branding.get("brand_name", ""),
        max_chars=200,
        key="branding_brand_name_input",
    )

    department = st.text_input(
        t("branding_department"),
        value=branding.get("department", ""),
        max_chars=200,
        key="branding_department_input",
    )

    style_options = ["standard", "school"]
    style_labels = {
        "standard": t("branding_style_standard"),
        "school": t("branding_style_school"),
    }
    current_style = branding.get("header_style", "standard")
    if current_style not in style_options:
        current_style = "standard"

    header_style = st.selectbox(
        t("branding_header_style"),
        style_options,
        index=style_options.index(current_style),
        format_func=lambda x: style_labels.get(x, x),
        key="branding_header_style_select",
    )

    from helpers.font_manager import get_font_options, get_size_options

    font_options = get_font_options()
    font_keys = [k for k, _ in font_options]
    font_labels = {k: lbl for k, lbl in font_options}
    current_font = branding.get("branding_font", "dejavu")
    if current_font not in font_keys:
        current_font = "dejavu"

    branding_font = st.selectbox(
        t("branding_font_label"),
        font_keys,
        index=font_keys.index(current_font),
        format_func=lambda x: font_labels.get(x, x),
        key="branding_font_select",
    )

    size_options = get_size_options()
    size_keys = [k for k, _ in size_options]
    size_labels = {k: t(lbl_key) for k, lbl_key in size_options}
    current_size = branding.get("branding_font_size", "standard")
    if current_size not in size_keys:
        current_size = "standard"

    branding_font_size = st.selectbox(
        t("branding_font_size_label"),
        size_keys,
        index=size_keys.index(current_size),
        format_func=lambda x: size_labels.get(x, x),
        key="branding_font_size_select",
    )

    # Header logo
    st.markdown(f"**{t('branding_header_logo')}**")
    current_logo = str(branding.get("header_logo_url") or "").strip()

    if current_logo:
        st.image(current_logo, width=120, caption=t("branding_current_logo"))
        if st.button(t("branding_remove_logo"), key="branding_remove_header_logo"):
            delete_branding_image("header")
            current_logo = ""
            clear_branding_cache()
            st.rerun()

    header_file = st.file_uploader(
        t("branding_upload_logo"),
        type=list(ALLOWED_IMAGE_TYPES),
        key="branding_header_file_upload",
    )
    if header_file:
        error = _validate_image_upload(header_file)
        if error:
            st.error(error)
            header_file = None

    # Footer image
    st.markdown(f"**{t('branding_footer_image')}**")
    current_footer = str(branding.get("footer_image_url") or "").strip()

    if current_footer:
        st.image(current_footer, width=200, caption=t("branding_current_footer"))
        if st.button(t("branding_remove_footer"), key="branding_remove_footer_image"):
            delete_branding_image("footer")
            current_footer = ""
            clear_branding_cache()
            st.rerun()

    footer_file = st.file_uploader(
        t("branding_upload_footer"),
        type=list(ALLOWED_IMAGE_TYPES),
        key="branding_footer_file_upload",
    )
    if footer_file:
        error = _validate_image_upload(footer_file)
        if error:
            st.error(error)
            footer_file = None

    st.info(t("branding_privacy_notice"))

    # Preview
    st.markdown(f"**{t('branding_preview')}**")
    preview_cols = st.columns([1, 3, 1])
    with preview_cols[1]:
        if current_logo:
            st.markdown(
                f"""
                <div style="text-align:center; margin-bottom:10px;">
                    <img src="{current_logo}"
                         style="max-width:80px; height:auto; display:inline-block;" />
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif os.path.isfile(_DEFAULT_LOGO_PATH):
            st.markdown(
                f"""
                <div style="text-align:center; margin-bottom:10px;">
                    <img src="data:image/png;base64,{_image_file_to_base64(_DEFAULT_LOGO_PATH)}"
                         style="max-width:80px; height:auto; display:inline-block;" />
                </div>
                """,
                unsafe_allow_html=True,
            )

        if brand_name:
            st.markdown(
                f"<div style='text-align:center;font-weight:700;font-size:1.1rem;color:#1D4ED8'>{brand_name}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='text-align:center;font-weight:700;font-size:1.05rem;'>Classio</div>",
                unsafe_allow_html=True,
            )

        if department:
            st.markdown(
                f"<div style='text-align:center;font-size:0.9rem;color:#475569'>{department}</div>",
                unsafe_allow_html=True,
            )

        if header_style == "school":
            st.markdown(
                f"<div style='text-align:center;font-weight:600;margin-top:4px'>{t('branding_preview_title')}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;margin-top:8px;font-size:0.9rem'>"
                f"<span><b>{t('student_name_label')}:</b> ___________</span>"
                f"<span><b>{t('class_label')}:</b> ___________</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if st.button(
        t("branding_save_btn"),
        key="branding_save_settings_custom",
        use_container_width=True,
        type="primary",
    ):
        new_logo_url = current_logo
        new_footer_url = current_footer

        if header_file:
            try:
                new_logo_url = upload_branding_image(header_file, "header")
                st.success(t("branding_logo_uploaded"))
            except RuntimeError as e:
                st.error(str(e))
                return

        if footer_file:
            try:
                new_footer_url = upload_branding_image(footer_file, "footer")
                st.success(t("branding_footer_uploaded"))
            except RuntimeError as e:
                st.error(str(e))
                return

        ok = save_user_branding(
            brand_name=brand_name,
            department=department,
            header_style=header_style,
            header_enabled=True,
            footer_enabled=True,
            header_logo_url=new_logo_url,
            footer_image_url=new_footer_url,
            branding_font=branding_font,
            branding_font_size=branding_font_size,
        )
        if ok:
            st.success(t("branding_saved"))
            clear_branding_cache()
            st.rerun()
