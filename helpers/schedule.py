import streamlit as st
import datetime
import re as _re
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, get_app_tz
from core.database import get_sb, load_table, register_cache, load_profile_row
from typing import Optional
import pandas as pd
from datetime import date
from core.timezone import UTC_TZ, DEFAULT_TZ_NAME
from core.state import with_owner
from core.database import ensure_student, clear_app_caches
from helpers.ui_components import to_dt_naive
from zoneinfo import ZoneInfo


def _validate_hhmm(value: str) -> str:
    s = str(value or "").strip()
    if _re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", s):
        return s
    raise ValueError(t("invalid_time_format"))

# 07.9) SCHEDULE / OVERRIDES HELPERS
# =========================
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _schedule_creation_tz_name() -> str:
    uid = get_current_user_id()
    profile = load_profile_row(uid) if uid else {}
    tz_name = str((profile or {}).get("timezone") or "").strip()
    if not tz_name:
        tz_name = getattr(get_app_tz(), "key", "") or DEFAULT_TZ_NAME
    try:
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return DEFAULT_TZ_NAME


def _legacy_schedule_fallback_tz_name() -> str:
    # Legacy recurring schedules were originally interpreted in the app's
    # default timezone. Do not rebind them to a mutable profile timezone.
    return DEFAULT_TZ_NAME

@st.cache_data(ttl=45, show_spinner=False)
def _load_schedules_cached(uid: str) -> pd.DataFrame:
    df = load_table("schedules")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "weekday", "time", "duration_minutes", "active", "timezone"])

    for c, default in {
        "id": None, "student": "", "weekday": 0, "time": "", "duration_minutes": 60, "active": True, "timezone": _legacy_schedule_fallback_tz_name()
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["weekday"] = pd.to_numeric(df["weekday"], errors="coerce").fillna(0).astype(int)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["active"] = df["active"].fillna(True).astype(bool)
    df["time"] = df["time"].astype(str).str.strip()
    df["timezone"] = df["timezone"].fillna(_legacy_schedule_fallback_tz_name()).astype(str).str.strip()
    df["timezone"] = df["timezone"].apply(lambda value: value if value and _is_valid_timezone_name(value) else _legacy_schedule_fallback_tz_name())
    return df


def _is_valid_timezone_name(value: str) -> bool:
    try:
        ZoneInfo(str(value or "").strip())
        return True
    except Exception:
        return False

def load_schedules() -> pd.DataFrame:
    uid = get_current_user_id()
    return _load_schedules_cached(uid)

register_cache(_load_schedules_cached)

def add_schedule(student: str, weekday: int, time_str: str, duration_minutes: int, active: bool = True) -> None:
    student = str(student).strip()
    ensure_student(student)

    payload = with_owner({
        "student": student,
        "weekday": int(weekday),
        "time": _validate_hhmm(time_str),
        "duration_minutes": int(duration_minutes),
        "active": bool(active),
        "timezone": _schedule_creation_tz_name(),
    })

    try:
        get_sb().table("schedules").insert(payload).execute()
    except Exception as exc:
        if "timezone" not in str(exc).lower():
            raise
        legacy_payload = dict(payload)
        legacy_payload.pop("timezone", None)
        get_sb().table("schedules").insert(legacy_payload).execute()
    clear_app_caches()


def delete_schedule(schedule_id: int) -> None:
    uid = get_current_user_id()
    q = get_sb().table("schedules").delete().eq("id", int(schedule_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()

@st.cache_data(ttl=45, show_spinner=False)
def _load_overrides_cached(uid: str, tz_name: str) -> pd.DataFrame:
    df = load_table("calendar_overrides")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "original_date", "new_datetime", "duration_minutes", "status", "note", "gcal_event_id"])

    for c, default in {
        "id": None, "student": "", "original_date": None, "new_datetime": None,
        "duration_minutes": 60, "status": "", "note": "", "gcal_event_id": None
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["original_date"] = to_dt_naive(df["original_date"], utc=True)
    df["new_datetime"] = pd.to_datetime(df["new_datetime"], errors="coerce", utc=True)
    df["new_datetime"] = df["new_datetime"].dt.tz_convert(ZoneInfo(tz_name)).dt.tz_localize(None)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["note"] = df["note"].astype(str).fillna("")
    return df

def load_overrides() -> pd.DataFrame:
    uid = get_current_user_id()
    tz_name = getattr(get_app_tz(), "key", "") or DEFAULT_TZ_NAME
    return _load_overrides_cached(uid, tz_name)

register_cache(_load_overrides_cached)

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
    note: str = "",
    gcal_event_id: Optional[str] = None,
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
    if gcal_event_id:
        payload["gcal_event_id"] = gcal_event_id

    get_sb().table("calendar_overrides").insert(payload).execute()
    clear_app_caches()


def find_gcal_event_id(student: str, original_date: date) -> Optional[str]:
    """Find the Google Calendar event ID for a student+date override."""
    overrides = load_overrides()
    if overrides.empty or "gcal_event_id" not in overrides.columns:
        return None
    match = overrides[
        (overrides["student"].str.strip().str.lower() == student.strip().lower())
        & (overrides["original_date"].dt.date == original_date)
        & (overrides["gcal_event_id"].notna())
        & (overrides["gcal_event_id"] != "")
    ]
    if match.empty:
        return None
    return str(match.iloc[-1]["gcal_event_id"])


def delete_override(override_id: int) -> None:
    uid = get_current_user_id()
    # Look up gcal_event_id before deleting
    try:
        row = (
            get_sb().table("calendar_overrides")
            .select("gcal_event_id")
            .eq("id", int(override_id))
            .limit(1)
            .execute()
        )
        gcal_eid = (row.data[0].get("gcal_event_id") if row.data else None)
        if gcal_eid:
            from helpers.google_calendar import delete_gcal_event
            delete_gcal_event(gcal_eid)
    except Exception:
        pass

    q = get_sb().table("calendar_overrides").delete().eq("id", int(override_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()


# =========================
