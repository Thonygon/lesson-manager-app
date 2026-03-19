"""Student report PDF builder – lesson & payment history with branding."""

import os, re, urllib.parse
from io import BytesIO
from datetime import datetime as _dt

import pandas as pd
import streamlit as st

from core.i18n import t


# ── Logo helper (shared) ──────────────────────────────────────────────
_LOGO_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "static", "logo_classio_light.png")


def _logo_abs() -> str:
    return os.path.abspath(_LOGO_PATH)


# ── Student report PDF ────────────────────────────────────────────────

def build_student_report_pdf(
    student_name: str,
    lessons_df: pd.DataFrame,
    payments_df: pd.DataFrame,
    package_df: pd.DataFrame | None = None,
) -> bytes:
    """Build a professional PDF report with lesson & payment history."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, Image as RLImage,
    )
    from reportlab.lib import colors

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    sty_title = ParagraphStyle("RptTitle", parent=styles["Title"], fontSize=18, leading=22,
                               textColor=colors.HexColor("#1D4ED8"), spaceAfter=2)
    sty_sub = ParagraphStyle("RptSub", parent=styles["Normal"], fontSize=11,
                             textColor=colors.HexColor("#475569"), spaceAfter=6)
    sty_sec = ParagraphStyle("RptSection", parent=styles["Heading2"], fontSize=13, leading=16,
                             textColor=colors.HexColor("#1E40AF"), spaceBefore=12, spaceAfter=4)
    sty_body = ParagraphStyle("RptBody", parent=styles["BodyText"], fontSize=9.5, leading=12,
                              textColor=colors.HexColor("#1E293B"))
    sty_hdr_cell = ParagraphStyle("RptHdrCell", parent=styles["Normal"], fontSize=9,
                                  textColor=colors.white, leading=11)
    sty_cell = ParagraphStyle("RptCell", parent=styles["Normal"], fontSize=9, leading=11,
                              textColor=colors.HexColor("#1E293B"))

    story: list = []

    # ── Top-left logo, then left-aligned header ────────────────────────
    logo_path = _logo_abs()
    if os.path.isfile(logo_path):
        logo = RLImage(logo_path, width=2.8 * cm, height=2.8 * cm, kind="proportional")
        story.append(logo)
        story.append(Spacer(1, 6))

    story.append(Paragraph(t("student_report_title"), sty_title))
    story.append(Paragraph(student_name, sty_sub))
    story.append(Paragraph(_dt.now().strftime("%Y-%m-%d"), sty_body))

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=8))

    # ── Lessons table ─────────────────────────────────────────────────
    story.append(Paragraph(t("lessons"), sty_sec))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#BFDBFE"), spaceAfter=4))

    l_cols = ["lesson_date", "lessons", "modality", "subject", "note"]
    l_headers = [t("lesson_date"), t("lessons"), t("modality"), t("subject"), t("note")]

    if lessons_df.empty:
        story.append(Paragraph(t("no_data"), sty_body))
    else:
        tdata = [[Paragraph(h, sty_hdr_cell) for h in l_headers]]
        for _, row in lessons_df.iterrows():
            tdata.append([Paragraph(str(row.get(c, "") or ""), sty_cell) for c in l_cols])
        tbl = Table(tdata, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)

    story.append(Spacer(1, 12))

    # ── Payments table ────────────────────────────────────────────────
    story.append(Paragraph(t("payments"), sty_sec))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#BFDBFE"), spaceAfter=4))

    p_cols = ["payment_date", "lessons_paid", "paid_amount", "modality", "subject",
              "package_start_date", "package_expiry_date"]
    p_headers = [t("payment_date"), t("lessons_paid"), t("paid_amount"), t("modality"),
                 t("subject"), t("package_start_date"), t("package_expiry_date")]

    if payments_df.empty:
        story.append(Paragraph(t("no_data"), sty_body))
    else:
        tdata = [[Paragraph(h, sty_hdr_cell) for h in p_headers]]
        for _, row in payments_df.iterrows():
            tdata.append([Paragraph(str(row.get(c, "") or ""), sty_cell) for c in p_cols])
        tbl = Table(tdata, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)

    # ── Current package balance ────────────────────────────────────────
    if package_df is not None and not package_df.empty:
        story.append(Spacer(1, 4))
        story.append(Paragraph(t("current_package_balance"), sty_sec))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#BFDBFE"), spaceAfter=4))

        pkg_cols = ["Subject", "Modality", "Lessons_Paid_Total",
                    "Lessons_Taken_Units", "Lessons_Left_Units"]
        pkg_headers = [t("subject"), t("modality"), t("lessons_paid"),
                       t("lessons_taken"), t("lessons_left")]

        # ensure columns exist
        for c in pkg_cols:
            if c not in package_df.columns:
                package_df[c] = ""

        tdata = [[Paragraph(h, sty_hdr_cell) for h in pkg_headers]]
        for _, row in package_df.iterrows():
            tdata.append([Paragraph(str(row.get(c, "") or ""), sty_cell) for c in pkg_cols])
        tbl = Table(tdata, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)

    # ── Summary row ───────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    total_lessons = int(lessons_df["lessons"].sum()) if not lessons_df.empty else 0
    total_paid = float(payments_df["paid_amount"].sum()) if not payments_df.empty else 0.0
    summary = f"{t('total_lessons')}: {total_lessons}   |   {t('total_paid')}: {total_paid:,.2f}"
    story.append(Paragraph(summary, sty_sub))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ── Share helpers ─────────────────────────────────────────────────────

def build_report_whatsapp_url(student_name: str, phone: str) -> str:
    """Build wa.me URL with a pre-formatted message about the report."""
    from helpers.whatsapp import normalize_phone_for_whatsapp
    lang = st.session_state.get("ui_lang", "en")
    msg = _share_message(student_name, lang)
    encoded = urllib.parse.quote(msg)
    wa_phone = normalize_phone_for_whatsapp(phone)
    if wa_phone:
        return f"https://wa.me/{wa_phone}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def build_report_email_url(student_name: str, email: str) -> str:
    """Build mailto: URL with subject + body about the report."""
    lang = st.session_state.get("ui_lang", "en")
    subject = _email_subject(student_name, lang)
    body = _share_message(student_name, lang)
    return f"mailto:{urllib.parse.quote(email)}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"


def _share_message(student_name: str, lang: str) -> str:
    if lang == "es":
        return (
            f"Hola {student_name},\n\n"
            "Adjunto encontrarás el reporte con tu historial de clases y pagos.\n"
            "Por favor revísalo y no dudes en contactarme si tienes alguna pregunta.\n\n"
            "¡Saludos!"
        )
    return (
        f"Hi {student_name},\n\n"
        "Please find attached your lesson and payment history report.\n"
        "Feel free to reach out if you have any questions.\n\n"
        "Best regards!"
    )


def _email_subject(student_name: str, lang: str) -> str:
    if lang == "es":
        return f"Reporte de clases y pagos – {student_name}"
    return f"Lesson & Payment Report – {student_name}"
