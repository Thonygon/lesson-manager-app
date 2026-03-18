import streamlit as st
import datetime
import pandas as pd
import numpy as np
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.database import load_table, register_cache
import math
from helpers.dashboard import rebuild_dashboard
from helpers.ui_components import to_dt_naive, ts_today_naive
from helpers.language import translate_status, translate_modality_value, translate_language_value
from helpers.package_lang_lookups import _is_free_note, _units_multiplier

# 07.15) FORECAST (BEHAVIOR-BASED + PIPELINE-AWARE + FINISHED LAST 3 MONTHS)
# =========================
def build_forecast_table(
    payment_buffer_days: int = 0,
    active_window_days: int = 183,
    finished_keep_days: int = 90,
    lookback_days_for_rate: int = 56,
) -> pd.DataFrame:

    dash = rebuild_dashboard(active_window_days=active_window_days, expiry_days=365, grace_days=0)
    if dash is None or dash.empty:
        return pd.DataFrame()

    # Need raw classes to estimate burn rate
    classes = load_table("classes")
    if classes is None or classes.empty:
        classes = pd.DataFrame(columns=["student", "lesson_date", "number_of_lesson", "modality", "note"])
    else:
        for c in ["student", "lesson_date", "number_of_lesson", "modality", "note"]:
            if c not in classes.columns:
                classes[c] = None

    classes["student"] = classes["student"].fillna("").astype(str).str.strip()
    classes["lesson_date"] = to_dt_naive(classes["lesson_date"], utc=True)
    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    classes["modality"] = classes["modality"].fillna("Online").astype(str).str.strip()
    classes["note"] = classes["note"].fillna("").astype(str)

    today = ts_today_naive()
    active_cutoff = today - pd.Timedelta(days=int(active_window_days))
    finished_cutoff = today - pd.Timedelta(days=int(finished_keep_days))
    rate_cutoff = today - pd.Timedelta(days=int(lookback_days_for_rate))

    # Work on dashboard output
    df = dash.copy()

    # Defensive: ensure expected columns exist
    for c in [
        "Student", "Status", "Payment_Date", "Package_Start_Date", "Package_Expiry_Date",
        "Last_Lesson_Date", "Lessons_Left_Units", "Overused_Units", "Modality", "Languages"
    ]:
        if c not in df.columns:
            df[c] = None

    df["Student"] = df["Student"].fillna("").astype(str).str.strip()
    df = df[df["Student"].str.len() > 0].copy()
    if df.empty:
        return pd.DataFrame()

    # Parse dates (dashboard stores these as YYYY-MM-DD strings)
    df["Payment_Date_dt"] = pd.to_datetime(df["Payment_Date"], errors="coerce")
    df["Package_Start_dt"] = pd.to_datetime(df["Package_Start_Date"], errors="coerce")
    df["Expiry_dt"] = pd.to_datetime(df["Package_Expiry_Date"], errors="coerce")
    df["Last_Lesson_dt"] = pd.to_datetime(df["Last_Lesson_Date"], errors="coerce")

    # Remaining units (dashboard column exists; be defensive)
    df["Lessons_Left_Units"] = pd.to_numeric(df["Lessons_Left_Units"], errors="coerce").fillna(0).astype(int)

    # Determine active
    df["Has_Recent_Lesson"] = df["Last_Lesson_dt"].notna() & (df["Last_Lesson_dt"] >= active_cutoff)
    df["Has_Recent_Payment"] = df["Payment_Date_dt"].notna() & (df["Payment_Date_dt"] >= active_cutoff)
    df["Is_Active"] = df["Has_Recent_Lesson"] | df["Has_Recent_Payment"]

    # Recent finished: status == finished (internal code) + last lesson (fallback: payment) in last N days
    status_code = df["Status"].fillna("").astype(str).str.strip().str.casefold()
    df["Is_Finished"] = status_code.eq("finished")
    df["Finished_Recently"] = df["Is_Finished"] & (
        (df["Last_Lesson_dt"].notna() & (df["Last_Lesson_dt"] >= finished_cutoff)) |
        (df["Payment_Date_dt"].notna() & (df["Payment_Date_dt"] >= finished_cutoff))
    )

    # -------------------------
    # NEW: pipeline-aware keep
    # Keep if:
    # - Active OR Finished_Recently OR has units left (>0)
    # -------------------------
    df = df[df["Is_Active"] | df["Finished_Recently"] | (df["Lessons_Left_Units"] > 0)].copy()
    if df.empty:
        return pd.DataFrame()

    # Estimate burn rate (units/day) from last lookback window per student
    def _units_row(r) -> int:
        if _is_free_note(r.get("note", "")):
            return 0
        return int(r.get("number_of_lesson", 0)) * _units_multiplier(r.get("modality", ""))

    recent = classes.dropna(subset=["lesson_date"]).copy()
    recent = recent[recent["lesson_date"] >= rate_cutoff]

    if not recent.empty:
        recent["Units_Last_Lookback"] = recent.apply(_units_row, axis=1)
        rate_tbl = (
            recent.groupby("student", as_index=False)["Units_Last_Lookback"].sum()
            .rename(columns={"student": "Student"})
        )
        # Global median units/day (better fallback than constant)
        lookback_days = float(max(1, int(lookback_days_for_rate)))
        tmpu = rate_tbl["Units_Last_Lookback"] / lookback_days
        global_median_upd = float(pd.to_numeric(tmpu, errors="coerce").replace([math.inf, -math.inf], 0).fillna(0).median())
    else:
        rate_tbl = pd.DataFrame(columns=["Student", "Units_Last_Lookback"])
        global_median_upd = 0.0

    df = df.merge(rate_tbl, on="Student", how="left")
    df["Units_Last_Lookback"] = pd.to_numeric(df.get("Units_Last_Lookback"), errors="coerce").fillna(0.0)

    lookback_days = float(max(1, int(lookback_days_for_rate)))
    df["Units_Per_Day"] = (df["Units_Last_Lookback"] / lookback_days).replace([math.inf, -math.inf], 0).fillna(0.0)

    # Better fallback: global median, then constant
    # (median might be 0 if there are no recent lessons in the lookback window)
    if global_median_upd and global_median_upd > 0:
        df.loc[df["Units_Per_Day"] <= 0, "Units_Per_Day"] = float(global_median_upd)
    df.loc[df["Units_Per_Day"] <= 0, "Units_Per_Day"] = 0.10  # last resort

    # Estimate finish
    df["Days_To_Finish"] = (df["Lessons_Left_Units"] / df["Units_Per_Day"]).replace([math.inf, -math.inf], 0).fillna(0)
    df["Days_To_Finish"] = df["Days_To_Finish"].clip(lower=0, upper=3650)

    df["Estimated_Finish_Date_dt"] = today + pd.to_timedelta(df["Days_To_Finish"].round().astype(int), unit="D")
    df["Reminder_Date_dt"] = df["Estimated_Finish_Date_dt"] - pd.to_timedelta(int(payment_buffer_days), unit="D")

    # If already finished (0 left), set estimate to today
    done_mask = df["Lessons_Left_Units"] <= 0
    df.loc[done_mask, "Estimated_Finish_Date_dt"] = today
    df.loc[done_mask, "Reminder_Date_dt"] = today - pd.to_timedelta(int(payment_buffer_days), unit="D")

    # Clamp by expiry if expiry exists and is earlier than estimate
    has_exp = df["Expiry_dt"].notna()
    clamp_mask = has_exp & (df["Expiry_dt"] < df["Estimated_Finish_Date_dt"])
    df.loc[clamp_mask, "Estimated_Finish_Date_dt"] = df.loc[clamp_mask, "Expiry_dt"]
    df.loc[clamp_mask, "Reminder_Date_dt"] = df.loc[clamp_mask, "Expiry_dt"] - pd.to_timedelta(int(payment_buffer_days), unit="D")

    # Format for display
    out = df.copy()
    out["Estimated_Finish_Date"] = pd.to_datetime(out["Estimated_Finish_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Reminder_Date"] = pd.to_datetime(out["Reminder_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Units_Per_Day"] = pd.to_numeric(out.get("Units_Per_Day"), errors="coerce").fillna(0).round(2)
    out["Days_To_Finish"] = pd.to_numeric(out.get("Days_To_Finish"), errors="coerce").fillna(0).round(1)

    # NEW: due flag for UI filtering (buffer becomes meaningful in Analytics)
    out["_rem_dt"] = pd.to_datetime(out["Reminder_Date"], errors="coerce")
    out["Due_Now"] = out["_rem_dt"].notna() & (out["_rem_dt"] <= today)

    # Translate coded values for bilingual UI
    out["Status"] = out.get("Status", "").astype(str).str.strip().str.casefold().apply(translate_status)
    out["Modality"] = out.get("Modality", "").astype(str).apply(translate_modality_value)
    out["Languages"] = out.get("Languages", "").astype(str).apply(translate_language_value)

    keep_cols = [
        "Student",
        "Status",
        "Lessons_Left_Units",
        "Overused_Units",
        "Modality",
        "Languages",
        "Last_Lesson_Date",
        "Payment_Date",
        "Package_Start_Date",
        "Package_Expiry_Date",
        "Units_Per_Day",
        "Days_To_Finish",
        "Estimated_Finish_Date",
        "Reminder_Date",
        "Due_Now",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols].copy()

    # Sort: soonest reminder first, then lowest remaining
    out["_rem"] = pd.to_datetime(out.get("Reminder_Date"), errors="coerce")
    out["_left"] = pd.to_numeric(out.get("Lessons_Left_Units"), errors="coerce").fillna(0)
    out = (
        out.sort_values(["_rem", "_left", "Student"])
           .drop(columns=["_rem", "_left"], errors="ignore")
           .reset_index(drop=True)
    )

    return out

# =========================
