import re
import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from helpers.lesson_planner import subject_label as _subject_label_fn
from core.timezone import now_local
from core.database import load_table
from helpers.ui_components import to_dt_naive, ts_today_naive

def money_fmt(value, symbol=""):
    try:
        v = float(value)
        return f"{symbol}{v:,.0f}"
    except Exception:
        return f"{symbol}0"

def _subject_to_t_key(subject: str) -> str:
    return _subject_label_fn(subject)


def _normalize_subject_combo(raw: str) -> str:
    """
    Convert subject text into a stable internal key.
    Examples:
    - 'English' -> 'english'
    - 'Spanish' -> 'spanish'
    - 'English,Spanish' -> 'english|spanish'
    - 'Spanish & English' -> 'english|spanish'
    """
    s = str(raw or "").strip()
    if not s:
        return ""

    parts = re.split(r"\s*(?:,|&|/|\+| and | y | ve )\s*", s, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]

    normalized = []
    seen = set()

    for part in parts:
        key = _subject_to_t_key(part)
        stable = key if key else part.lower()
        if stable not in seen:
            seen.add(stable)
            normalized.append(stable)

    normalized.sort()
    return "|".join(normalized)


def _display_subject_combo(subject_key: str) -> str:
    """
    Convert stable internal key into translated UI text.
    """
    if not subject_key:
        return ""

    parts = [p.strip() for p in str(subject_key).split("|") if p.strip()]
    translated = []

    for part in parts:
        translated.append(t(part) if part in {"english", "spanish"} else part.title())

    if len(translated) == 2 and set(parts) == {"english", "spanish"}:
        return t("english_spanish")

    return " + ".join(translated)


@st.cache_data(ttl=45, show_spinner=False)
def build_income_analytics(group: str = "monthly"):
    payments = load_table("payments")

    if payments is None or payments.empty:
        payments = pd.DataFrame(columns=["student", "payment_date", "paid_amount", "number_of_lesson", "modality", "subject"])

    for c, default in {
        "student": "",
        "payment_date": None,
        "paid_amount": 0.0,
        "number_of_lesson": 0,
        "modality": "Online",
        "subject": "",
    }.items():
        if c not in payments.columns:
            payments[c] = default

    payments["student"] = payments["student"].astype(str).str.strip()
    payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
    payments["subject"] = payments["subject"].fillna("").astype(str).str.strip()
    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()

    payments = payments.dropna(subset=["payment_date"])
    payments = payments[payments["student"].astype(str).str.len() > 0].copy()

    today = ts_today_naive()

    week_start = today - pd.Timedelta(days=int(today.weekday()))
    week_end = week_start + pd.Timedelta(days=6)

    income_all_time = float(payments["paid_amount"].sum()) if not payments.empty else 0.0
    income_this_year = float(
        payments.loc[payments["payment_date"].dt.year == today.year, "paid_amount"].sum()
    ) if not payments.empty else 0.0

    this_month_key = str(today.to_period("M"))
    income_this_month = float(
        payments.loc[payments["payment_date"].dt.to_period("M").astype(str) == this_month_key, "paid_amount"].sum()
    ) if not payments.empty else 0.0

    income_this_week = float(
        payments.loc[(payments["payment_date"] >= week_start) & (payments["payment_date"] <= week_end), "paid_amount"].sum()
    ) if not payments.empty else 0.0

    kpis = {
        "income_all_time": income_all_time,
        "income_this_year": income_this_year,
        "income_this_month": income_this_month,
        "income_this_week": income_this_week,
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
    }

    if group == "yearly":
        payments["Key"] = payments["payment_date"].dt.to_period("Y").astype(str)
    else:
        payments["Key"] = payments["payment_date"].dt.to_period("M").astype(str)

    income_table = (
        payments.groupby("Key", as_index=False)["paid_amount"]
        .sum()
        .rename(columns={"paid_amount": "income"})
        .sort_values("Key")
        .reset_index(drop=True)
    )

    by_student = (
        payments.groupby("student", as_index=False)
        .agg(
            total_paid=("paid_amount", "sum"),
            packages=("paid_amount", "size"),
            last_payment=("payment_date", "max"),
        )
        .sort_values("total_paid", ascending=False)
        .reset_index(drop=True)
    )

    payments["subject_key"] = payments["subject"].apply(_normalize_subject_combo)

    sold_by_subject = (
        payments.groupby("subject_key", as_index=False)["paid_amount"].sum()
        .rename(columns={"subject_key": "subject", "paid_amount": "income"})
        .sort_values("income", ascending=False)
        .reset_index(drop=True)
    )

    sold_by_subject["subject"] = sold_by_subject["subject"].apply(_display_subject_combo)

    sold_by_modality = (
        payments.groupby("modality", as_index=False)["paid_amount"].sum()
        .rename(columns={"paid_amount": "income"})
        .sort_values("income", ascending=False)
        .reset_index(drop=True)
    )

    return kpis, income_table, by_student, sold_by_subject, sold_by_modality
# =========================
