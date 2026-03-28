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
        uid = user.id if hasattr(user, "id") else ""
        profile_name = get_user_display_name(uid)
        profile_username = get_user_username(uid)
        _set_logged_in_user(user, profile_name=profile_name, profile_username=profile_username)

        # Sync auth email → profiles table (once per session, catches post-confirmation changes)
        if not st.session_state.get("_email_synced_to_profile"):
            _auth_email = getattr(user, "email", None)
            if uid and _auth_email:
                try:
                    sb.table("profiles").update({"email": _auth_email}).eq("user_id", str(uid)).execute()
                except Exception:
                    pass
            st.session_state["_email_synced_to_profile"] = True

        # ── Login-count & last-page redirect (run once per session) ──────────
        if uid and not st.session_state.get("_login_redirect_done"):
            st.session_state["_login_redirect_done"] = True
            try:
                _pres = sb.table("profiles").select(
                    "login_count, last_page, onboarding_completed, account_status, deleted_at, username"
                ).eq("user_id", str(uid)).limit(1).execute()
                _prow = (getattr(_pres, "data", None) or [{}])[0]

                # ── Check for deleted account ──
                if _prow.get("account_status") == "deleted":
                    st.session_state["_post_login_action"] = "restore_account"
                    st.session_state["_deleted_at"] = _prow.get("deleted_at")
                    return  # skip login count increment

                _login_count = int(_prow.get("login_count") or 0)
                _last_page   = str(_prow.get("last_page") or "").strip() or "dashboard"
                _onboarded   = bool(_prow.get("onboarding_completed"))
                _has_username = bool(str(_prow.get("username") or "").strip())

                # Increment and persist
                _new_count = _login_count + 1
                sb.table("profiles").update({"login_count": _new_count}).eq("user_id", str(uid)).execute()

                # Decide where to land
                if _login_count == 0:
                    st.session_state["_post_login_action"] = "page:home"
                elif not _has_username:
                    st.session_state["_post_login_action"] = "choose_username"
                else:
                    try:
                        from app_pages.render_home_welcome import get_welcome_progress
                        _welcome_progress = get_welcome_progress()
                    except Exception:
                        _welcome_progress = {"all_done": True}

                    if not _welcome_progress.get("all_done", True):
                        st.session_state["_post_login_action"] = "page:home"
                    elif _login_count == 1:
                        st.session_state["_post_login_action"] = "dashboard"
                    else:
                        st.session_state["_post_login_action"] = f"page:{_last_page}"
            except Exception:
                pass  # Non-fatal; app just opens normally

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


def get_user_username(user_id: str) -> str:
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select("username")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows and rows[0].get("username"):
            return rows[0]["username"]
    except Exception:
        pass
    return ""


def is_username_taken(username: str) -> bool:
    """Check if a username is already in use by any profile."""
    if not username or not username.strip():
        return False
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select("user_id")
            .eq("username", username.strip().lower())
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return len(rows) > 0
    except Exception:
        return False


# ---- Data access ----
@st.cache_data(ttl=45, show_spinner=False)
def _load_table_cached(name: str, uid: str, limit: int = 10000, page_size: int = 1000) -> pd.DataFrame:
    all_rows = []
    owner_scoped_tables = {
        "students", "classes", "payments", "schedules", "calendar_overrides",
        "pricing_items", "app_settings", "profiles", "lesson_plans",
        "ai_usage_logs", "user_activity_log", "professional_profiles",
        "worksheets",
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
        raise ValueError("missing_user_id")
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


def rename_student_everywhere(old_name: str, new_name: str) -> None:
    old_name = str(old_name or "").strip()
    new_name = str(new_name or "").strip()
    uid = get_current_user_id()

    if not uid:
        raise ValueError("missing_user_id")
    if not old_name or not new_name:
        raise ValueError("no_data")
    if norm_student(old_name) == norm_student(new_name):
        return

    sb = get_sb()

    existing = (
        sb.table("students")
        .select("id, student")
        .eq("user_id", uid)
        .execute()
    )
    rows = getattr(existing, "data", None) or []

    if any(norm_student(r.get("student", "")) == norm_student(new_name) for r in rows):
        raise ValueError("student_name_exists")

    (
        sb.table("students")
        .update({"student": new_name})
        .eq("user_id", uid)
        .eq("student", old_name)
        .execute()
    )

    failed_tables = []

    for table_name in ["classes", "payments", "schedules", "calendar_overrides"]:
        try:
            (
                sb.table(table_name)
                .update({"student": new_name})
                .eq("user_id", uid)
                .eq("student", old_name)
                .execute()
            )
        except Exception:
            failed_tables.append(table_name)

        if failed_tables:
            raise ValueError("rename_student_partial_failed")

    clear_app_caches()


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

def _normalize_profile_sex(raw) -> str | None:
    v = str(raw or "").strip().lower()
    aliases = {
        "male": "male",
        "female": "female",
        "other": "other",
        "prefer_not_to_say": "prefer_not_to_say",
        "prefer not to say": "prefer_not_to_say",
        "prefer-not-to-say": "prefer_not_to_say",
        "": None,
        "none": None,
        "null": None,
    }
    return aliases.get(v, None)

def upsert_profile_row(user_id: str, payload: dict) -> bool:
    if not user_id:
        return False

    clean = dict(payload or {})
    clean["user_id"] = str(user_id)

    if "sex" in clean:
        clean["sex"] = _normalize_profile_sex(clean.get("sex"))

    try:
        sb = get_sb()
        sb.table("profiles").upsert(clean, on_conflict="user_id").execute()
        clear_app_caches()
        return True
    except Exception as e:
        st.error(f"Could not save profile: {e}")
        return False




# ---- CRUD ----
def add_class(
    student,
    number_of_lesson,
    lesson_date,
    modality,
    note="",
    subject=None,
    subject_custom=None,
): 
    sb = get_sb()
    payload = with_owner({
        "student": student,
        "number_of_lesson": number_of_lesson,
        "lesson_date": lesson_date,
        "modality": modality,
        "note": note,
        "subject": subject,
        "subject_custom": subject_custom,
    })
    sb.table("classes").insert(payload).execute()

def add_payment(student: str, number_of_lesson: int, payment_date: str,
                paid_amount: float, modality: str, subject: str = "",
                subject_custom: Optional[str] = None,
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
        "subject_custom": str(subject_custom).strip() if subject_custom else None,
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


def load_community_profiles() -> list:
    """Return all profiles that have opted into the community (show_community_profile=True or NULL).
    Returns a list of dicts with safe public fields only."""
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select(
                "user_id, display_name, username, avatar_url, country, primary_subjects, "
                "teaching_stages, education_level, active_student_count, "
                "show_community_profile, show_community_contact, phone_number, "
                "email, role"
            )
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return rows
    except Exception:
        return []


def update_active_student_count(user_id: str) -> None:
    """Refresh the cached active_student_count field in the profiles table for user_id."""
    if not user_id:
        return
    try:
        import pandas as pd
        import datetime as _dt
        sb = get_sb()
        cutoff = (_dt.date.today() - _dt.timedelta(days=183)).isoformat()

        # Count unique active students via recent lessons or payments
        cls_res = sb.table("classes").select("student, lesson_date").eq("user_id", str(user_id)).execute()
        cls_rows = getattr(cls_res, "data", None) or []
        pay_res  = sb.table("payments").select("student, payment_date").eq("user_id", str(user_id)).execute()
        pay_rows = getattr(pay_res, "data", None) or []

        active_students: set = set()
        for r in cls_rows:
            d = str(r.get("lesson_date") or "")[:10]
            if d >= cutoff:
                active_students.add(str(r.get("student") or "").strip())
        for r in pay_rows:
            d = str(r.get("payment_date") or "")[:10]
            if d >= cutoff:
                active_students.add(str(r.get("student") or "").strip())
        active_students.discard("")

        sb.table("profiles").upsert(
            {"user_id": str(user_id), "active_student_count": len(active_students)},
            on_conflict="user_id",
        ).execute()
    except Exception:
        pass


# ── Account deletion ────────────────────────────────────────────────────
_DELETE_TABLES = [
    "classes", "payments", "students", "schedules", "calendar_overrides",
    "pricing_items", "app_settings", "lesson_plans", "ai_usage_logs",
    "user_activity_log", "professional_profiles", "worksheets",
]


def delete_user_data(user_id: str) -> bool:
    """Hard-delete all user data from every content table, then mark profile as deleted."""
    if not user_id:
        return False
    sb = get_sb()
    for tbl in _DELETE_TABLES:
        try:
            sb.table(tbl).delete().eq("user_id", str(user_id)).execute()
        except Exception:
            pass
    # Mark profile as deleted (keep user_id + email for restore window)
    sb.table("profiles").update({
        "account_status": "deleted",
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "display_name": None,
        "avatar_url": None,
        "phone_number": None,
        "show_community_profile": False,
        "show_community_contact": False,
        "onboarding_completed": False,
        "login_count": 0,
        "active_student_count": 0,
    }).eq("user_id", str(user_id)).execute()
    clear_app_caches()
    return True


def restore_deleted_account(user_id: str) -> bool:
    """Re-activate a soft-deleted profile within the 90-day window."""
    if not user_id:
        return False
    sb = get_sb()
    sb.table("profiles").update({
        "account_status": "active",
        "deleted_at": None,
        "onboarding_completed": False,
    }).eq("user_id", str(user_id)).execute()
    clear_app_caches()
    return True


from typing import Optional
def check_deleted_account(user_id: str) -> Optional[dict]:
    """Return deletion info if profile is soft-deleted, else None."""
    if not user_id:
        return None
    sb = get_sb()
    res = sb.table("profiles").select(
        "account_status, deleted_at"
    ).eq("user_id", str(user_id)).limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        return None
    row = rows[0]
    if row.get("account_status") != "deleted":
        return None
    return row
