import streamlit as st
import datetime
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.database import load_table, load_students
import numpy as np
from helpers.ui_components import to_dt_naive, ts_today_naive
from helpers.language import translate_status, translate_modality_value, translate_language_value
from helpers.package_lang_lookups import _is_free_note, _units_multiplier

# 07.13) DASHBOARD (PACKAGE STATUS) ✅ + chart-translation helper
# =========================
def dash_chart_series(
    df: pd.DataFrame,
    group_col: str,
    value_col: str = None,
    agg: str = "count",
    *,
    translate_group_values: bool = True,
    group_key_for_label: str = None,
    value_key_for_label: str = None,
):
    """
    Build a Streamlit-ready Series where:
      - Index labels are translatable (Status/Modality/Languages, or raw strings)
      - Series name is translatable (so chart title/legend shows translated label)
    """
    if df is None or df.empty:
        return None
    if group_col not in df.columns:
        return None
    if agg in ("sum", "mean", "min", "max") and (value_col is None or value_col not in df.columns):
        return None

    tmp = df.copy()

    # Translate grouped values when they are coded
    if translate_group_values:
        if group_col == "Status":
            tmp[group_col] = tmp[group_col].astype(str).str.strip().str.casefold().apply(translate_status)
        elif group_col == "Modality":
            tmp[group_col] = tmp[group_col].astype(str).apply(translate_modality_value)
        elif group_col == "Subject":
            tmp[group_col] = tmp[group_col].astype(str).apply(translate_language_value)

    # Build series
    if agg == "count":
        ser = tmp.groupby(group_col).size()
    else:
        tmp["_v"] = pd.to_numeric(tmp[value_col], errors="coerce").fillna(0.0)
        if agg == "sum":
            ser = tmp.groupby(group_col)["_v"].sum()
        elif agg == "mean":
            ser = tmp.groupby(group_col)["_v"].mean()
        elif agg == "min":
            ser = tmp.groupby(group_col)["_v"].min()
        elif agg == "max":
            ser = tmp.groupby(group_col)["_v"].max()
        else:
            ser = tmp.groupby(group_col).size()

    # Sort desc for nicer charts
    try:
        ser = ser.sort_values(ascending=False)
    except Exception:
        pass

    # ----- translated axis label + series label -----
    if group_key_for_label is None:
        group_key_for_label = str(group_col).strip().casefold().replace(" ", "_")

    if value_key_for_label is None:
        if agg == "count":
            value_key_for_label = "students"
        else:
            value_key_for_label = str(value_col or "").strip().casefold().replace(" ", "_") or "income"

    ser.index.name = t(group_key_for_label)
    ser.name = t(value_key_for_label)

    return ser

@st.cache_data(ttl=45, show_spinner=False)
def rebuild_dashboard(active_window_days: int = 183, expiry_days: int = 365, grace_days: int = 0) -> pd.DataFrame:
    classes = load_table("classes")
    payments = load_table("payments")

    if classes.empty:
        classes = pd.DataFrame(columns=["id","student","number_of_lesson","lesson_date","modality","note","subject"])
    if payments.empty:
        payments = pd.DataFrame(columns=[
            "id","student","number_of_lesson","payment_date","paid_amount","modality","subject",
            "package_start_date","package_expiry_date",
            "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
        ])

    # Ensure columns exist
    for c in ["id","student","number_of_lesson","lesson_date","modality","note","subject"]:
        if c not in classes.columns:
            classes[c] = None

    for c in [
        "id","student","number_of_lesson","payment_date","paid_amount","modality","subject",
        "package_start_date","package_expiry_date",
        "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
    ]:
        if c not in payments.columns:
            payments[c] = None

    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    classes["lesson_date"] = to_dt_naive(classes["lesson_date"], utc=True)
    payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
    payments["package_start_date"] = to_dt_naive(payments["package_start_date"], utc=True)
    payments["package_expiry_date"] = to_dt_naive(payments["package_expiry_date"], utc=True)

    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)

    payments["lesson_adjustment_units"] = pd.to_numeric(payments["lesson_adjustment_units"], errors="coerce").fillna(0).astype(int)
    payments["package_normalized"] = payments["package_normalized"].fillna(False).astype(bool)

    if "note" not in classes.columns:
        classes["note"] = ""
    classes["note"] = classes["note"].fillna("").astype(str)

    payments = payments.dropna(subset=["payment_date"])
    if payments.empty:
        return pd.DataFrame(columns=[
            "Student","Packages_Bought","Lessons_Paid_Total","Total_Paid","Payment_Date",
            "Package_Start_Date","Package_Expiry_Date",
            "Lessons_Taken_Units","Lessons_Left_Units","Overused_Units",
            "Status","Modality","Last_Lesson_Date","Is_Active_6m",
            "Payment_ID","Normalize_Allowed","Subject"
        ])

    today = ts_today_naive()
    active_cutoff = today - pd.Timedelta(days=int(active_window_days))
    expiry_cutoff = today - pd.Timedelta(days=int(expiry_days))
    _ = grace_days

    payments["pkg_start"] = payments["package_start_date"].fillna(payments["payment_date"])
    p = payments.sort_values(["student", "pkg_start", "payment_date", "id"]).copy()
    p["next_pkg_start"] = p.groupby("student")["pkg_start"].shift(-1)
    latest = p.groupby("student", as_index=False).tail(1).copy()

    packages_bought = (
        p.groupby("student", as_index=False)
         .size()
         .rename(columns={"size":"packages_bought"})
    )

    last_lesson = (
        classes.dropna(subset=["lesson_date"])
              .groupby("student", as_index=False)["lesson_date"]
              .max()
              .rename(columns={"lesson_date":"Last_Lesson_Date"})
    )

    cls = classes.dropna(subset=["lesson_date"]).copy()
    cls = cls[cls["student"].astype(str).str.len() > 0]

    cls = cls.merge(
        latest[[
            "student","id","pkg_start","package_expiry_date","next_pkg_start",
            "modality","number_of_lesson","lesson_adjustment_units","package_normalized",
            "payment_date","paid_amount","subject"
        ]].rename(columns={
            "id":"Payment_ID",
            "number_of_lesson":"Lessons_Paid_Total",
            "paid_amount":"Total_Paid",
            "payment_date":"Payment_Date",
            "modality":"Modality",
            "subject":"Subject"
        }),
        on="student",
        how="inner"
    )

    def _window_end(row) -> pd.Timestamp:
        ends = [today]
        if pd.notna(row.get("package_expiry_date")):
            ends.append(pd.to_datetime(row["package_expiry_date"], errors="coerce"))
        if pd.notna(row.get("next_pkg_start")):
            ends.append(pd.to_datetime(row["next_pkg_start"], errors="coerce"))
        ends = [e for e in ends if pd.notna(e)]
        return min(ends) if ends else today

    latest["window_end"] = latest.apply(_window_end, axis=1)
    cls = cls.merge(latest[["student","window_end"]], on="student", how="left")

    cls = cls[
        (cls["lesson_date"] >= cls["pkg_start"]) &
        (cls["lesson_date"] < cls["window_end"])
    ].copy()

    # Remove accidental duplicate columns before computing units
    cls = cls.loc[:, ~cls.columns.duplicated()].copy()

    note_col = cls["note"] if "note" in cls.columns else ""
    num_col = pd.to_numeric(cls["number_of_lesson"], errors="coerce").fillna(0) if "number_of_lesson" in cls.columns else 0
    mod_col = cls["modality"].fillna("") if "modality" in cls.columns else ""

    free_mask = pd.Series(note_col).astype(str).apply(_is_free_note)
    units_mult = pd.Series(mod_col).astype(str).apply(_units_multiplier)

    cls["units_row"] = np.where(
    free_mask,
    0,
    num_col.astype(int) * units_mult.astype(int)
    )

    taken_units = (
        cls.groupby("student", as_index=False)["units_row"]
           .sum()
           .rename(columns={"units_row":"Lessons_Taken_Units"})
    )

    dash = latest.rename(columns={
        "student":"Student",
        "id":"Payment_ID",
        "number_of_lesson":"Lessons_Paid_Total",
        "paid_amount":"Total_Paid",
        "payment_date":"Payment_Date",
        "modality":"Modality",
        "package_expiry_date":"Package_Expiry_Date",
        "subject":"Subject",
    }).copy()

    dash["Package_Start_Date"] = dash["pkg_start"]

    dash = (
        dash.merge(packages_bought, left_on="Student", right_on="student", how="left")
            .drop(columns=["student"], errors="ignore")
            .merge(taken_units, left_on="Student", right_on="student", how="left")
            .drop(columns=["student"], errors="ignore")
            .merge(last_lesson, left_on="Student", right_on="student", how="left")
            .drop(columns=["student"], errors="ignore")
    )

    # packages_bought merge creates "packages_bought"
    dash["Packages_Bought"] = pd.to_numeric(dash.get("packages_bought"), errors="coerce").fillna(0).astype(int)
    dash["Lessons_Taken_Units"] = pd.to_numeric(dash["Lessons_Taken_Units"], errors="coerce").fillna(0).astype(int)

    dash["Purchased_Units"] = dash.apply(
        lambda r: int(r["Lessons_Paid_Total"]) * _units_multiplier(r.get("Modality","")),
        axis=1
    )
    dash["Adjustment_Units"] = pd.to_numeric(dash.get("lesson_adjustment_units"), errors="coerce").fillna(0).astype(int)
    dash["Effective_Purchased_Units"] = dash["Purchased_Units"] + dash["Adjustment_Units"]

    dash["Raw_Left_Units"] = dash["Effective_Purchased_Units"] - dash["Lessons_Taken_Units"]
    dash["Overused_Units"] = dash["Raw_Left_Units"].apply(lambda x: abs(int(x)) if int(x) < 0 else 0)
    dash["Lessons_Left_Units"] = dash["Raw_Left_Units"].clip(lower=0).astype(int)

    dash["Last_Lesson_Date"] = pd.to_datetime(dash["Last_Lesson_Date"], errors="coerce")
    dash["Payment_Date_dt"] = pd.to_datetime(dash["Payment_Date"], errors="coerce")

    dash["Has_Recent_Lesson"] = dash["Last_Lesson_Date"].notna() & (dash["Last_Lesson_Date"] >= active_cutoff)
    dash["Has_Recent_Payment"] = dash["Payment_Date_dt"].notna() & (dash["Payment_Date_dt"] >= active_cutoff)
    dash["Is_Active_6m"] = dash["Has_Recent_Lesson"] | dash["Has_Recent_Payment"]

    dash["Package_Expiry_Date"] = pd.to_datetime(dash["Package_Expiry_Date"], errors="coerce")
    dash["Closed_By_Expiry"] = dash["Package_Expiry_Date"].notna() & (dash["Package_Expiry_Date"] <= today)
    dash["Closed_By_Old_Payment"] = dash["Payment_Date_dt"].notna() & (dash["Payment_Date_dt"] <= expiry_cutoff)

    dash["Is_Dropout"] = (~dash["Is_Active_6m"]) & (~dash["Closed_By_Expiry"])
    dash.loc[dash["Closed_By_Expiry"] | dash["Closed_By_Old_Payment"] | dash["Is_Dropout"], "Lessons_Left_Units"] = 0

    def _status(r) -> str:
        # return ONLY lowercase codes
        if bool(r.get("Is_Dropout")):
            return "dropout"
        if bool(r.get("Closed_By_Expiry")) or bool(r.get("Closed_By_Old_Payment")):
            return "finished"
        if int(r.get("Overused_Units", 0)) > 0 and bool(r.get("Is_Active_6m")) and (not bool(r.get("package_normalized", False))):
            return "mismatch"
        left = int(r.get("Lessons_Left_Units", 0))
        if left <= 0:
            return "finished"
        if left <= 3:
            return "almost_finished"
        return "active"

    dash["Status"] = dash.apply(_status, axis=1)

    dash["Payment_Date"] = pd.to_datetime(dash["Payment_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Start_Date"] = pd.to_datetime(dash["Package_Start_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Expiry_Date"] = pd.to_datetime(dash["Package_Expiry_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Last_Lesson_Date"] = pd.to_datetime(dash["Last_Lesson_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    dash["Normalize_Allowed"] = (
        (dash["Status"] == "mismatch")
        & dash["Is_Active_6m"]
        & (~dash.get("package_normalized", False).astype(bool))
    )

    order = {"mismatch": 0, "almost_finished": 1, "active": 2, "finished": 3, "dropout": 9}
    dash["__o"] = dash["Status"].map(order).fillna(99).astype(int)
    dash = dash.sort_values(["__o","Lessons_Left_Units","Student"]).reset_index(drop=True)
    dash = dash.drop(columns=["__o"], errors="ignore")

    return dash[[
        "Student",
        "Packages_Bought",
        "Lessons_Paid_Total",
        "Total_Paid",
        "Payment_Date",
        "Package_Start_Date",
        "Package_Expiry_Date",
        "Lessons_Taken_Units",
        "Lessons_Left_Units",
        "Overused_Units",
        "Status",
        "Modality",
        "Subject",
        "Last_Lesson_Date",
        "Is_Active_6m",
        "Payment_ID",
        "Normalize_Allowed"
    ]]

# =========================
