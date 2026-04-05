# CLASSIO — Global PDF Typography & Layout System
# ============================================================
"""
Centralised PDF style definitions for all Classio exports:
worksheets, lesson plans, answer keys, and future exam builder.

Usage:
    from styles.pdf_styles import (
        ensure_pdf_fonts_registered,
        get_student_pdf_styles,
        get_plan_pdf_styles,
        get_answer_key_pdf_styles,
        get_pdf_layout_constants,
    )

    body_font, bold_font = ensure_pdf_fonts_registered()
    S = get_student_pdf_styles(body_font, bold_font)
    L = get_pdf_layout_constants()

    doc = SimpleDocTemplate(buf, pagesize=A4, **L["margins"])
"""
import os
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm


# ── Font registration ────────────────────────────────────────────────

_FONT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "static", "fonts")
)

_FONT_CANDIDATES = [
    # 1. Project-local (preferred)
    (
        os.path.join(_FONT_DIR, "DejaVuSans.ttf"),
        os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf"),
    ),
    # 2. macOS supplemental
    (
        "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf",
    ),
    # 3. Debian / Ubuntu
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    # 4. Generic Linux
    (
        "/usr/share/fonts/DejaVuSans.ttf",
        "/usr/share/fonts/DejaVuSans-Bold.ttf",
    ),
]

# Registered font names — must stay stable for backwards compat
BODY_FONT_NAME = "ClassioUnicode"
BOLD_FONT_NAME = "ClassioUnicode-Bold"

_fonts_registered = False


def ensure_pdf_fonts_registered() -> tuple[str, str]:
    """
    Register DejaVuSans (regular + bold) and return (body_font, bold_font).
    Falls back to Helvetica only if no DejaVuSans file is found.
    Safe to call multiple times — registration is idempotent.
    """
    global _fonts_registered

    if _fonts_registered:
        return BODY_FONT_NAME, BOLD_FONT_NAME

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for regular_path, bold_path in _FONT_CANDIDATES:
        if os.path.isfile(regular_path) and os.path.isfile(bold_path):
            try:
                pdfmetrics.registerFont(TTFont(BODY_FONT_NAME, regular_path))
                pdfmetrics.registerFont(TTFont(BOLD_FONT_NAME, bold_path))
                _fonts_registered = True
                return BODY_FONT_NAME, BOLD_FONT_NAME
            except Exception:
                pass

    # Graceful fallback — should never trigger in production
    return "Helvetica", "Helvetica-Bold"


# ── Colour palette (restrained, professional) ────────────────────────

class C:
    """PDF colour constants — academic / publishing palette."""
    # Text
    TEXT          = colors.HexColor("#0F172A")
    TEXT_MUTED    = colors.HexColor("#334155")
    TEXT_SUBTLE   = colors.HexColor("#64748B")

    # Accent
    PRIMARY       = colors.HexColor("#1D4ED8")

    # Borders & rules
    BORDER        = colors.HexColor("#CBD5E1")
    BORDER_LIGHT  = colors.HexColor("#E2E8F0")
    LINE          = colors.HexColor("#64748B")

    # Backgrounds
    BG_SUBTLE     = colors.HexColor("#F8FAFC")
    BG_WHITE      = colors.white

    # Section accents (lesson plans)
    FLOW_GREEN    = colors.HexColor("#22C55E")
    NOTE_AMBER    = colors.HexColor("#F59E0B")
    MATERIAL_PURPLE = colors.HexColor("#8B5CF6")
    OVERVIEW_BLUE = colors.HexColor("#3B82F6")

    # Highlight
    HIGHLIGHT_BG  = colors.HexColor("#DBEAFE")
    HIGHLIGHT_BOX = colors.HexColor("#2563EB")

    # Grid
    GRID          = colors.HexColor("#94A3B8")


# ── Layout constants ─────────────────────────────────────────────────

def get_pdf_layout_constants() -> dict:
    """
    Return a dict of layout primitives shared across all PDF types.
    Keys: margins, spacers, paddings, border_colors, page.
    """
    return {
        "margins": {
            "leftMargin":   1.8 * cm,
            "rightMargin":  1.8 * cm,
            "topMargin":    1.5 * cm,
            "bottomMargin": 1.5 * cm,
        },
        "plan_margins": {
            "leftMargin":   2.0 * cm,
            "rightMargin":  2.0 * cm,
            "topMargin":    1.5 * cm,
            "bottomMargin": 1.5 * cm,
        },
        "spacers": {
            "xs":  2,
            "sm":  4,
            "md":  6,
            "lg":  10,
            "xl":  14,
            "section": 8,
        },
        "paddings": {
            "cell":      6,
            "cell_snug": 4,
            "card":     10,
            "card_v":    8,
        },
        "page": {
            "size": A4,
            "width": A4[0],
            "height": A4[1],
        },
    }


# ── Student worksheet styles ─────────────────────────────────────────

def get_student_pdf_styles(
    body_font: str = "",
    bold_font: str = "",
) -> dict:
    """
    Return a dict of ParagraphStyle objects for student-facing PDFs
    (worksheets, exams).

    Keys: title, section, instruction, body, body_justified, small,
          footer, name_class, mc_stem, mc_option, line, box_label,
          tf_label.
    """
    bf, bld = _resolve_fonts(body_font, bold_font)
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CL_WsTitle",
            parent=styles["Title"],
            fontName=bld,
            fontSize=16,
            leading=20,
            textColor=C.PRIMARY,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "CL_WsSection",
            parent=styles["Heading2"],
            fontName=bld,
            fontSize=13,
            leading=16,
            textColor=C.TEXT,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "instruction": ParagraphStyle(
            "CL_WsInstruction",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=11,
            leading=15,
            textColor=C.TEXT,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
        ),
        "body": ParagraphStyle(
            "CL_WsBody",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=11,
            leading=15,
            textColor=C.TEXT,
            spaceAfter=3,
            alignment=TA_JUSTIFY,
        ),
        "body_left": ParagraphStyle(
            "CL_WsBodyLeft",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=11,
            leading=15,
            textColor=C.TEXT,
            spaceAfter=3,
            alignment=TA_LEFT,
        ),
        "small": ParagraphStyle(
            "CL_WsSmall",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9,
            leading=12,
            textColor=C.TEXT_MUTED,
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "CL_WsFooter",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9,
            leading=11,
            textColor=C.TEXT_SUBTLE,
        ),
        "name_class": ParagraphStyle(
            "CL_WsNameClass",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=10.5,
            leading=14,
            textColor=C.TEXT,
        ),
        "mc_stem": ParagraphStyle(
            "CL_WsMcStem",
            parent=styles["BodyText"],
            fontName=bld,
            fontSize=11,
            leading=15,
            textColor=C.TEXT,
            spaceAfter=2,
            alignment=TA_JUSTIFY,
        ),
        "mc_option": ParagraphStyle(
            "CL_WsMcOption",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=11,
            leading=14,
            textColor=C.TEXT,
            spaceAfter=1,
        ),
        "line": ParagraphStyle(
            "CL_WsLine",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=11,
            leading=17,
            textColor=C.TEXT,
            spaceAfter=2,
        ),
        "box_label": ParagraphStyle(
            "CL_WsBoxLabel",
            parent=styles["BodyText"],
            fontName=bld,
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=C.TEXT,
        ),
        "tf_label": ParagraphStyle(
            "CL_WsTFLabel",
            parent=styles["BodyText"],
            fontName=bld,
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=C.TEXT,
        ),
    }


# ── Lesson plan styles ───────────────────────────────────────────────

def get_plan_pdf_styles(
    body_font: str = "",
    bold_font: str = "",
) -> dict:
    """
    Return ParagraphStyle objects for lesson plan PDFs.

    Keys: title, section, body, small, card_title, meta, footer.
    """
    bf, bld = _resolve_fonts(body_font, bold_font)
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CL_PlanTitle",
            parent=styles["Title"],
            fontName=bld,
            fontSize=15,
            leading=19,
            textColor=C.PRIMARY,
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "CL_PlanSection",
            parent=styles["Heading2"],
            fontName=bld,
            fontSize=12.5,
            leading=16,
            textColor=C.TEXT,
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "CL_PlanBody",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=10.5,
            leading=14,
            textColor=C.TEXT,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "CL_PlanSmall",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9,
            leading=12,
            textColor=C.TEXT_MUTED,
            spaceAfter=2,
        ),
        "card_title": ParagraphStyle(
            "CL_PlanCardTitle",
            parent=styles["Heading3"],
            fontName=bld,
            fontSize=10.5,
            leading=13,
            textColor=C.TEXT,
            spaceAfter=3,
        ),
        "meta": ParagraphStyle(
            "CL_PlanMeta",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9.5,
            leading=12,
            textColor=C.TEXT_MUTED,
            spaceAfter=5,
        ),
        "footer": ParagraphStyle(
            "CL_PlanFooter",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9,
            leading=11,
            textColor=C.TEXT_SUBTLE,
        ),
        "brand": ParagraphStyle(
            "CL_PlanBrand",
            parent=styles["Heading2"],
            fontName=bld,
            fontSize=13,
            leading=16,
            textColor=C.PRIMARY,
            spaceAfter=3,
            alignment=TA_CENTER,
        ),
    }


# ── Answer key styles ────────────────────────────────────────────────

def get_answer_key_pdf_styles(
    body_font: str = "",
    bold_font: str = "",
) -> dict:
    """
    Return ParagraphStyle objects for answer key PDFs.

    Keys: title, section, body, small, footer.
    """
    bf, bld = _resolve_fonts(body_font, bold_font)
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CL_AKTitle",
            parent=styles["Title"],
            fontName=bld,
            fontSize=14,
            leading=18,
            textColor=C.PRIMARY,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "CL_AKSection",
            parent=styles["Heading2"],
            fontName=bld,
            fontSize=12,
            leading=15,
            textColor=C.TEXT,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "CL_AKBody",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=10,
            leading=14,
            textColor=C.TEXT,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "CL_AKSmall",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9,
            leading=12,
            textColor=C.TEXT_MUTED,
            spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "CL_AKFooter",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=9,
            leading=11,
            textColor=C.TEXT_SUBTLE,
        ),
    }


# ── School header styles (branding.py) ───────────────────────────────

def get_school_header_styles(
    body_font: str = "",
    bold_font: str = "",
) -> dict:
    """
    Styles used by the school-format header in branding.py.
    Keys: brand, department, title, field, instr_heading, instr_body.
    """
    bf, bld = _resolve_fonts(body_font, bold_font)
    styles = getSampleStyleSheet()

    return {
        "brand": ParagraphStyle(
            "CL_SchoolBrand",
            parent=styles["Title"],
            fontName=bld,
            fontSize=13,
            leading=16,
            textColor=C.PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "department": ParagraphStyle(
            "CL_SchoolDept",
            parent=styles["Title"],
            fontName=bld,
            fontSize=12,
            leading=15,
            textColor=C.PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "title": ParagraphStyle(
            "CL_SchoolTitle",
            parent=styles["Title"],
            fontName=bld,
            fontSize=13,
            leading=16,
            textColor=C.TEXT,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "field": ParagraphStyle(
            "CL_SchoolField",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=10.5,
            leading=14,
            textColor=C.TEXT,
        ),
        "instr_heading": ParagraphStyle(
            "CL_SchoolInstrH",
            parent=styles["Heading2"],
            fontName=bld,
            fontSize=11,
            leading=15,
            textColor=C.TEXT,
            spaceBefore=4,
            spaceAfter=3,
        ),
        "instr_body": ParagraphStyle(
            "CL_SchoolInstrBody",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=11,
            leading=15,
            textColor=C.TEXT,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
        ),
    }


# ── Standard header styles (branding.py) ─────────────────────────────

def get_standard_header_styles(
    body_font: str = "",
    bold_font: str = "",
) -> dict:
    """
    Styles for the standard (non-school) header in branding.py.
    Keys: title, body, brand.
    """
    bf, bld = _resolve_fonts(body_font, bold_font)
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "CL_StdTitle",
            parent=styles["Title"],
            fontName=bld,
            fontSize=16,
            leading=20,
            textColor=C.PRIMARY,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "CL_StdBody",
            parent=styles["BodyText"],
            fontName=bf,
            fontSize=10,
            leading=13,
            textColor=C.TEXT,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
        ),
        "brand": ParagraphStyle(
            "CL_StdBrand",
            parent=styles["Heading2"],
            fontName=bld,
            fontSize=13,
            leading=16,
            textColor=C.PRIMARY,
            spaceAfter=4,
        ),
    }


# ── Table style helpers ──────────────────────────────────────────────

def card_box_style(border_color=None):
    """
    TableStyle for a boxed card block (lesson plan sections).
    """
    bc = border_color or C.BORDER
    return [
        ("BACKGROUND", (0, 0), (-1, -1), C.BG_WHITE),
        ("BOX",        (0, 0), (-1, -1), 0.8, bc),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
    ]


def subtle_row_bg_style():
    """Alternating white / subtle-blue row backgrounds."""
    return [
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C.BG_WHITE, C.BG_SUBTLE]),
    ]


def clean_table_style():
    """Minimal padding, top-aligned, no decoration."""
    return [
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]


def draw_footer_text(canvas, doc, label: str = "Classio", font: str = "Helvetica"):
    """
    Draw a simple right-aligned footer: 'label | page#'.
    Call from an onPage callback.
    """
    canvas.saveState()
    canvas.setFont(font, 9)
    canvas.setFillColor(C.TEXT_SUBTLE)
    footer_text = f"{label} | {canvas.getPageNumber()}"
    canvas.drawRightString(
        doc.pagesize[0] - doc.rightMargin,
        0.9 * cm,
        footer_text,
    )
    canvas.restoreState()


# ── Private helpers ──────────────────────────────────────────────────

def _resolve_fonts(body_font: str, bold_font: str) -> tuple[str, str]:
    """Ensure we have valid font names, registering if needed."""
    if body_font and bold_font:
        return body_font, bold_font
    return ensure_pdf_fonts_registered()
