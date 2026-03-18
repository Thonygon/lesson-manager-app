import streamlit as st
import pandas as pd
import os
from datetime import datetime, timezone
from typing import List, Optional
from supabase import create_client

from core.state import get_current_user_id, with_owner, _set_logged_in_user, _clear_logged_in_user

# ---- Supabase client (lazy singleton) ----
_sb = None


def get_sb():
    global _sb
    if _sb is None:
        url = st.secrets.get("SUPABASE_URL", None) or os.getenv("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY", None) or os.getenv("SUPABASE_KEY")
        if not url or not key:
            st.error("Missing Supabase secrets: SUPABASE_URL / SUPABASE_KEY")
            st.stop()
        _sb = create_client(url, key)
    return _sb


# ---- Cache registry for clear_app_caches ----
_CACHE_REGISTRY = []


def register_cache(func):
    """Register a cached function so clear_app_caches() can clear it."""
    if func not in _CACHE_REGISTRY:
        _CACHE_REGISTRY.append(func)
    return func


def clear_app_caches() -> None:
    for fn in _CACHE_REGISTRY:
        try:
            fn.clear()
        except Exception:
            pass


# ---- Auth helpers ----
def apply_auth_session() -> None:
    at = st.session_state.get("sb_access_token")
    rt = st.session_state.get("sb_refresh_token")
    if not at or not rt:
        return
    try:
        sb = get_sb()
        sb.auth.set_session(at, rt)
        user = sb.auth.get_user().user
        profile_name = get_user_display_name(
            (user.id if hasattr(user, "id") else "")
        )
        _set_logged_in_user(user, profile_name=profile_name)
    except Exception:
        st.session_state["sb_access_token"] = None
        st.session_state["sb_refresh_token"] = None
        _clear_logged_in_user()


def get_user_display_name(user_id: str) -> str:
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select("display_name")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows and rows[0].get("display_name"):
            return rows[0]["display_name"]
    except Exception:
        pass
    return ""


# ---- Data access ----
@st.cache_data(ttl=45, show_spinner=False)
def _load_table_cached(name: str, uid: str, limit: int = 10000, page_size: int = 1000) -> pd.DataFrame:
    all_rows = []
    owner_scoped_tables = {
        "students", "classes", "payments", "schedules", "calendar_overrides",
        "pricing_items", "app_settings", "profiles", "lesson_plans",
        "ai_usage_logs", "user_activity_log",
    }
    try:
        sb = get_sb()
        offset = 0
        while offset < limit:
            q = sb.table(name).select("*")
            if name in owner_scoped_tables:
                if not uid:
                    return pd.DataFrame(columns=[])
                q = q.eq("user_id", uid)
            resp = q.range(offset, min(offset + page_size - 1, limit - 1)).execute()
            batch = resp.data or []
            all_rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return pd.DataFrame(all_rows)
    except Exception as e:
        st.error(f"Supabase error loading table '{name}'.\n\n{e}")
        return pd.DataFrame()

register_cache(_load_table_cached)


def load_table(name: str, limit: int = 10000, page_size: int = 1000) -> pd.DataFrame:
    uid = get_current_user_id()
    return _load_table_cached(name, uid, limit, page_size)


def norm_student(x: str) -> str:
    return str(x).strip().casefold()


def ensure_student(student: str) -> None:
    student = str(student).strip()
    if not student:
        return
    uid = get_current_user_id()
    if not uid:
        raise ValueError("Missing user_id while ensuring student.")
    sb = get_sb()
    existing = (
        sb.table("students")
        .select("id")
        .eq("student", student)
        .eq("user_id", uid)
        .limit(1)
        .execute()
    )
    rows = getattr(existing, "data", None) or []
    if rows:
        return
    payload = with_owner({"student": student})
    sb.table("students").insert(payload).execute()
    clear_app_caches()


@st.cache_data(ttl=45, show_spinner=False)
def _load_students_cached(uid: str) -> List[str]:
    df = load_table("students")
    if df.empty or "student" not in df.columns:
        return []
    names = (
        df["student"].astype(str).str.strip()
        .replace("", pd.NA).dropna().unique().tolist()
    )
    return sorted([n for n in names if str(n).lower() != "nan"])

register_cache(_load_students_cached)


def load_students() -> List[str]:
    uid = get_current_user_id()
    return _load_students_cached(uid)


# ---- Profile ----
def get_profile_avatar_url(user_id: str) -> str:
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select("avatar_url")
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return ""
        return str(rows[0].get("avatar_url") or "")
    except Exception as e:
        st.error(f"Could not load profile avatar: {e}")
        return ""


def save_profile_avatar_url(user_id: str, avatar_url: str) -> None:
    sb = get_sb()
    payload = {"user_id": str(user_id), "avatar_url": str(avatar_url)}
    try:
        sb.table("profiles").upsert(payload, on_conflict="user_id").execute()
    except Exception as e:
        st.error(f"Could not save profile avatar: {e}")
        raise


def load_profile_row(user_id: str) -> dict:
    if not user_id:
        return {}
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select("*")
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if rows:
            return rows[0] or {}
    except Exception as e:
        st.error(f"Could not load profile: {e}")
    return {}


def upsert_profile_row(user_id: str, payload: dict) -> bool:
    if not user_id:
        return False
    clean = dict(payload or {})
    clean["user_id"] = str(user_id)
    try:
        sb = get_sb()
        sb.table("profiles").upsert(clean, on_conflict="user_id").execute()
        clear_app_caches()
        return True
    except Exception as e:
        st.error(f"Could not save profile: {e}")
        return False


# ---- CRUD ----
def add_class(student: str, number_of_lesson: int, lesson_date: str,
              modality: str, note: str = "", subject: Optional[str] = None) -> None:
    student = str(student).strip()
    ensure_student(student)
    sb = get_sb()
    payload = with_owner({
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,
        "modality": str(modality).strip(),
        "note": str(note).strip() if note else "",
        "subject": str(subject).strip() if subject else None,
    })
    sb.table("classes").insert(payload).execute()
    clear_app_caches()


def add_payment(student: str, number_of_lesson: int, payment_date: str,
                paid_amount: float, modality: str, subject: str = "",
                package_start_date: Optional[str] = None,
                package_expiry_date: Optional[str] = None,
                lesson_adjustment_units: int = 0,
                package_normalized: bool = False,
                normalized_note: str = "",
                currency: str = "TRY") -> None:
    student = str(student).strip()
    ensure_student(student)
    if not package_start_date:
        package_start_date = payment_date
    sb = get_sb()
    payload = with_owner({
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "payment_date": payment_date,
        "paid_amount": float(paid_amount),
        "modality": str(modality).strip(),
        "subject": str(subject).strip() if subject else "",
        "package_start_date": package_start_date,
        "package_expiry_date": package_expiry_date if package_expiry_date else None,
        "lesson_adjustment_units": int(lesson_adjustment_units),
        "package_normalized": bool(package_normalized),
        "normalized_note": str(normalized_note or "").strip(),
        "normalized_at": datetime.now(timezone.utc).isoformat() if (package_normalized or normalized_note) else None,
        "currency": str(currency or "TRY").strip(),
    })
    sb.table("payments").insert(payload).execute()
    clear_app_caches()


def delete_row(table_name: str, row_id: int) -> None:
    uid = get_current_user_id()
    sb = get_sb()
    q = sb.table(table_name).delete().eq("id", int(row_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()


def normalize_latest_package(student: str, payment_id: int, note: str = "") -> bool:
    try:
        uid = get_current_user_id()
        sb = get_sb()
        payload = {
            "package_normalized": True,
            "normalized_note": str(note or "").strip(),
            "normalized_at": datetime.now(timezone.utc).isoformat()
        }
        q = sb.table("payments").update(payload).eq("id", int(payment_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        return True
    except Exception:
        return False


def update_student_profile(student: str, email: str, zoom_link: str,
                           notes: str, color: str, phone: str) -> None:
    uid = get_current_user_id()
    sb = get_sb()
    q = sb.table("students").update({
        "email": email, "zoom_link": zoom_link,
        "notes": notes, "color": color, "phone": phone,
    }).eq("student", student)
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()


def update_payment_row(payment_id: int, updates: dict) -> bool:
    try:
        uid = get_current_user_id()
        sb = get_sb()
        q = sb.table("payments").update(updates).eq("id", int(payment_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        return True
    except Exception:
        return False


def update_class_row(class_id: int, updates: dict) -> bool:
    try:
        uid = get_current_user_id()
        sb = get_sb()
        q = sb.table("classes").update(updates).eq("id", int(class_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        return True
    except Exception:
        return False
