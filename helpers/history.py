import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local
from core.database import load_table
from typing import Tuple
from helpers.ui_components import to_dt_naive
from helpers.language import translate_modality_value, translate_language_value

# 07.8) HISTORY HELPERS
# =========================
def show_student_history(student: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    student = str(student).strip()

    classes = load_table("classes")
    payments = load_table("payments")

    if classes.empty:
        classes = pd.DataFrame(columns=["id", "student", "number_of_lesson", "lesson_date", "modality", "note", "subject"])
    if payments.empty:
        payments = pd.DataFrame(columns=[
            "id","student","number_of_lesson","payment_date","paid_amount","modality","subject",
            "package_start_date","package_expiry_date",
            "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
        ])

    # Ensure columns exist
    for col in ["id","student","number_of_lesson","lesson_date","modality","note","subject"]:
        if col not in classes.columns:
            classes[col] = None

    for col in [
        "id","student","number_of_lesson","payment_date","paid_amount","modality","subject",
        "package_start_date","package_expiry_date",
        "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
    ]:
        if col not in payments.columns:
            payments[col] = None

    # Filter by student
    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    lessons_df = classes[classes["student"] == student].copy()
    payments_df = payments[payments["student"] == student].copy()

    # Parse dates (tz-naive)
    lessons_df["lesson_date"] = to_dt_naive(lessons_df["lesson_date"], utc=True)
    payments_df["payment_date"] = to_dt_naive(payments_df["payment_date"], utc=True)
    payments_df["package_start_date"] = to_dt_naive(payments_df["package_start_date"], utc=True)
    payments_df["package_expiry_date"] = to_dt_naive(payments_df["package_expiry_date"], utc=True)

    # Numeric
    lessons_df["number_of_lesson"] = pd.to_numeric(lessons_df["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments_df["number_of_lesson"] = pd.to_numeric(payments_df["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments_df["paid_amount"] = pd.to_numeric(payments_df["paid_amount"], errors="coerce").fillna(0.0)

    # Sort
    lessons_df = lessons_df.sort_values(["lesson_date","id"], ascending=[False, False]).reset_index(drop=True)
    payments_df = payments_df.sort_values(["payment_date","id"], ascending=[False, False]).reset_index(drop=True)

    # Select + rename to stable internal keys (snake_case)
    lessons_df = lessons_df.rename(columns={
        "id": "lesson_id",
        "number_of_lesson": "lessons",
    })[["lesson_id","lesson_date","lessons","modality","subject","note"]]

    payments_df = payments_df.rename(columns={
        "id": "payment_id",
        "number_of_lesson": "lessons_paid",
        "lesson_adjustment_units": "adjustment_units",
    })[[
        "payment_id","payment_date","lessons_paid","paid_amount","modality","subject",
        "package_start_date","package_expiry_date",
        "adjustment_units","package_normalized","normalized_note","normalized_at"
    ]]

    # Format dates for display (safe on Series)
    lessons_df["lesson_date"] = pd.to_datetime(lessons_df["lesson_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["payment_date"] = pd.to_datetime(payments_df["payment_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["package_start_date"] = pd.to_datetime(payments_df["package_start_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["package_expiry_date"] = pd.to_datetime(payments_df["package_expiry_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Translate coded values (optional)
    lessons_df["modality"] = lessons_df["modality"].apply(translate_modality_value)
    lessons_df["subject"] = lessons_df["subject"].fillna("").astype(str)

    payments_df["modality"] = payments_df["modality"].apply(translate_modality_value)
    payments_df["subject"] = payments_df["subject"].fillna("").astype(str)

    return lessons_df, payments_df

# =========================
