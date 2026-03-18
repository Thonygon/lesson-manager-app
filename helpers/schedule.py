import streamlit as st
import datetime
import re as _re
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, get_app_tz
from core.database import get_sb, load_table, register_cache
from typing import Optional
import pandas as pd
from datetime import date
from core.timezone import UTC_TZ
from core.state import with_owner
from core.database import ensure_student, clear_app_caches
from helpers.ui_components import to_dt_naive


def _validate_hhmm(value: str) -> str:
    s = str(value or "").strip()
    if _re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", s):
        return s
    raise ValueError(t("invalid_time_format"))

# 07.9) SCHEDULE / OVERRIDES HELPERS
# =========================
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

@st.cache_data(ttl=45, show_spinner=False)
def _load_schedules_cached(uid: str) -> pd.DataFrame:
    df = load_table("schedules")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "weekday", "time", "duration_minutes", "active"])

    for c, default in {
        "id": None, "student": "", "weekday": 0, "time": "", "duration_minutes": 60, "active": True
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["weekday"] = pd.to_numeric(df["weekday"], errors="coerce").fillna(0).astype(int)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["active"] = df["active"].fillna(True).astype(bool)
    df["time"] = df["time"].astype(str).str.strip()
    return df

def load_schedules() -> pd.DataFrame:
    uid = get_current_user_id()
    return _load_schedules_cached(uid)

def add_schedule(student: str, weekday: int, time_str: str, duration_minutes: int, active: bool = True) -> None:
    student = str(student).strip()
    ensure_student(student)

    payload = with_owner({
        "student": student,
        "weekday": int(weekday),
        "time": _validate_hhmm(time_str),
        "duration_minutes": int(duration_minutes),
        "active": bool(active),
    })

    get_sb().table("schedules").insert(payload).execute()
    clear_app_caches()


def delete_schedule(schedule_id: int) -> None:
    uid = get_current_user_id()
    q = get_sb().table("schedules").delete().eq("id", int(schedule_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()

@st.cache_data(ttl=45, show_spinner=False)
def _load_overrides_cached(uid: str) -> pd.DataFrame:
    df = load_table("calendar_overrides")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "original_date", "new_datetime", "duration_minutes", "status", "note"])

    for c, default in {
        "id": None, "student": "", "original_date": None, "new_datetime": None,
        "duration_minutes": 60, "status": "", "note": ""
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["original_date"] = to_dt_naive(df["original_date"], utc=True)
    df["new_datetime"] = pd.to_datetime(df["new_datetime"], errors="coerce", utc=True)
    df["new_datetime"] = df["new_datetime"].dt.tz_convert(get_app_tz()).dt.tz_localize(None)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["note"] = df["note"].astype(str).fillna("")
    return df

def load_overrides() -> pd.DataFrame:
    uid = get_current_user_id()
    return _load_overrides_cached(uid)

def _to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert a datetime to a UTC ISO string for storage.
    - If naive: assume LOCAL_TZ (Europe/Istanbul)
    - If aware: respect its tz
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_app_tz())
    return dt.astimezone(UTC_TZ).isoformat()


def add_override(
    student: str,
    original_date: date,
    new_dt: Optional[datetime],
    duration_minutes: int = 60,
    status: str = "scheduled",
    note: str = ""
) -> None:
    student = str(student).strip()
    ensure_student(student)

    status_clean = str(status).strip().lower()

    payload = with_owner({
        "student": student,
        "original_date": original_date.isoformat(),
        "duration_minutes": int(duration_minutes),
        "status": status_clean,
        "note": str(note or "").strip(),
        "new_datetime": _to_utc_iso(new_dt) if status_clean == "scheduled" else None,
    })

    get_sb().table("calendar_overrides").insert(payload).execute()
    clear_app_caches()


def delete_override(override_id: int) -> None:
    uid = get_current_user_id()
    q = get_sb().table("calendar_overrides").delete().eq("id", int(override_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()


# =========================
