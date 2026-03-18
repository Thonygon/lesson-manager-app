import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.database import load_table, register_cache
from helpers.language import LANG_ES, LANG_BOTH
from helpers.ui_components import to_dt_naive, ts_today_naive

# 07.14) ANALYTICS (INCOME + CHARTS) ✅ missing-columns safe (Section 24 compatible)
# =========================
def money_fmt(x: float, symbol: str = "") -> str:
    """Compact currency format for KPI bubbles.

    *symbol* is an optional currency symbol prepended to the result
    (e.g. ``"$"``, ``"€"``).
    """
    try:
        x = float(x)
        prefix = f"{symbol} " if symbol else ""
        if abs(x) >= 1_000_000:
            val = x / 1_000_000
            return prefix + f"{val:.1f}".replace(".", ",").rstrip("0").rstrip(",") + "M"
        elif abs(x) >= 1_000:
            val = x / 1_000
            formatted = f"{val:.1f}".replace(".", ",").rstrip("0").rstrip(",")
            return prefix + formatted + "K"
        else:
            return prefix + str(int(round(x)))
    except Exception:
        return str(x)

@st.cache_data(ttl=45, show_spinner=False)
def build_income_analytics(group: str = "monthly"):
    payments = load_table("payments")

    if payments is None or payments.empty:
        payments = pd.DataFrame(columns=["student", "payment_date", "paid_amount", "number_of_lesson", "modality", "subject"])

    # ✅ Ensure needed columns exist
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

    # ✅ Calendar week Mon–Sun (matches your preference)
    week_start = today - pd.Timedelta(days=int(today.weekday()))  # Monday
    week_end = week_start + pd.Timedelta(days=6)                  # Sunday

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

    # Group Key
    if group == "yearly":
        payments["Key"] = payments["payment_date"].dt.to_period("Y").astype(str)
    else:
        payments["Key"] = payments["payment_date"].dt.to_period("M").astype(str)

    # ✅ IMPORTANT: return columns that Section 24 expects
    income_table = (
        payments.groupby("Key", as_index=False)["paid_amount"]
        .sum()
        .rename(columns={"paid_amount": "income"})   # <-- was Income
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

    # Keep original language normalization (but return expected col names)
    sold_by_subject = (
        payments.assign(subject=payments["subject"].replace({"English,Spanish": "English & Spanish"}))
        .groupby("subject", as_index=False)["paid_amount"].sum()
        .rename(columns={"paid_amount": "income"})
        .sort_values("income", ascending=False)
        .reset_index(drop=True)
    )

    sold_by_modality = (
        payments.groupby("modality", as_index=False)["paid_amount"].sum()
        .rename(columns={"paid_amount": "income"})
        .sort_values("income", ascending=False)
        .reset_index(drop=True)
    )

    return kpis, income_table, by_student, sold_by_subject, sold_by_modality
# =========================
