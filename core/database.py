import streamlit as st
import pandas as pd
import os
import re
import html as _html
from datetime import datetime, timezone
from typing import List, Optional
from supabase import create_client

from core.state import get_current_user_id, with_owner, _set_logged_in_user, _clear_logged_in_user


LESSON_NOTE_DEFAULT_TOKEN = "__NO_TOPIC_REGISTERED__"


def get_profile_by_email(email: str) -> dict:
    if not email:
        return {}
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select("*")
            .eq("email", str(email).strip().lower())
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def _normalize_lesson_note(note) -> str:
    text = str(note or "").strip()
    if text == LESSON_NOTE_DEFAULT_TOKEN:
        return None
    if not text:
        return None
    for _ in range(3):
        text = _html.unescape(text).strip()
    text = re.sub(r"(?i)</?\s*div\b[^>]*>", " ", text)
    text = re.sub(r"(?i)\b/?\s*div\s*>", " ", text)
    text = re.sub(r"(?i)^/?\s*div\s*$", " ", text)
    text = " ".join(text.split()).strip()
    return text or None


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


# ---- Auth helpers (OIDC-compatible) ----
def apply_auth_session() -> None:
    """
    Compatibility helper for the new Streamlit OIDC auth flow.

    Restores the current app user from:
    1) st.user.email when available, or
    2) st.session_state['user_email'] as fallback.

    Also runs the login-count / redirect logic once per session.
    """
    email = ""

    if getattr(st.user, "is_logged_in", False):
        email = str(getattr(st.user, "email", "") or "").strip().lower()

    if not email:
        email = str(st.session_state.get("user_email") or "").strip().lower()

    if not email:
        return

    try:
        sb = get_sb()
        profile = get_profile_by_email(email)
        if not profile:
            return

        uid = str(profile.get("user_id") or "").strip()
        if not uid:
            return

        display_name = str(profile.get("display_name") or "").strip()
        username = str(profile.get("username") or "").strip()

        oidc_user = {
            "email": email,
            "user_metadata": {
                "display_name": str(getattr(st.user, "name", "") or display_name).strip(),
            },
        }

        _set_logged_in_user(
            oidc_user,
            profile_name=display_name,
            profile_username=username,
            user_id=uid,
            user_role=resolve_active_mode(profile),
        )

        # Sync email into profiles once per session if needed
        if not st.session_state.get("_email_synced_to_profile"):
            try:
                sb.table("profiles").update({"email": email}).eq("user_id", uid).execute()
            except Exception:
                pass
            st.session_state["_email_synced_to_profile"] = True

        # Login-count & redirect logic (run once per session)
        if uid and not st.session_state.get("_login_redirect_done"):
            st.session_state["_login_redirect_done"] = True
            try:
                _pres = (
                    sb.table("profiles")
                    .select("login_count, last_page, onboarding_completed, account_status, deleted_at, username")
                    .eq("user_id", uid)
                    .limit(1)
                    .execute()
                )
                _prow = (getattr(_pres, "data", None) or [{}])[0]

                if _prow.get("account_status") == "deleted":
                    st.session_state["_post_login_action"] = "restore_account"
                    st.session_state["_deleted_at"] = _prow.get("deleted_at")
                    return

                _login_count = int(_prow.get("login_count") or 0)
                _last_page = str(_prow.get("last_page") or "").strip() or "dashboard"
                _has_username = bool(str(_prow.get("username") or "").strip())
                _user_role = resolve_active_mode(profile)

                _new_count = _login_count + 1
                sb.table("profiles").update({"login_count": _new_count}).eq("user_id", uid).execute()

                if _login_count == 0:
                    st.session_state["_post_login_action"] = "choose_role"
                elif not _has_username:
                    st.session_state["_post_login_action"] = "choose_username"
                elif _user_role == "student":
                    _student_default = "student_home"
                    _target = _last_page if _last_page.startswith("student_") else _student_default
                    st.session_state["_post_login_action"] = f"page:{_target}"
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
                pass

    except Exception:
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
        rows = getattr(res, "data", None) or []
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
        rows = getattr(res, "data", None) or []
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
        "students",
        "classes",
        "payments",
        "schedules",
        "calendar_overrides",
        "pricing_items",
        "app_settings",
        "profiles",
        "lesson_plans",
        "learning_programs",
        "ai_usage_logs",
        "user_activity_log",
        "professional_profiles",
        "worksheets",
        "quick_exams",
        "practice_sessions",
        "practice_answers",
        "practice_progress",
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


def get_profile_primary_role(profile: dict) -> str:
    role = str((profile or {}).get("primary_role") or (profile or {}).get("role") or "teacher").strip().lower()
    return role if role in ("teacher", "student", "tutor") else "teacher"


def profile_can_teach(profile: dict) -> bool:
    if profile is None:
        return False
    if profile.get("can_teach") is not None:
        return bool(profile.get("can_teach"))
    return get_profile_primary_role(profile) in ("teacher", "tutor")


def profile_can_study(profile: dict) -> bool:
    if profile is None:
        return False
    if profile.get("can_study") is not None:
        return bool(profile.get("can_study"))
    return get_profile_primary_role(profile) == "student"


def resolve_active_mode(profile: dict) -> str:
    desired = str((profile or {}).get("last_active_mode") or "").strip().lower()
    if desired == "student" and profile_can_study(profile):
        return "student"
    if desired == "teacher" and profile_can_teach(profile):
        return "teacher"
    if profile_can_teach(profile):
        return "teacher"
    if profile_can_study(profile):
        return "student"
    return "teacher"


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


def enable_profile_mode(user_id: str, target_role: str) -> bool:
    role = str(target_role or "").strip().lower()
    if not user_id or role not in ("teacher", "student"):
        return False
    profile = load_profile_row(user_id)
    payload = {"last_active_mode": role}
    if role == "teacher":
        payload["can_teach"] = True
        if not str(profile.get("role") or "").strip():
            payload["role"] = "teacher"
        if not str(profile.get("primary_role") or "").strip():
            payload["primary_role"] = "teacher"
    else:
        payload["can_study"] = True
        if not str(profile.get("role") or "").strip():
            payload["role"] = "student"
        if not str(profile.get("primary_role") or "").strip():
            payload["primary_role"] = "student"
    return upsert_profile_row(user_id, payload)


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
        "note": _normalize_lesson_note(note),
        "subject": subject,
        "subject_custom": subject_custom,
    })
    sb.table("classes").insert(payload).execute()
    clear_app_caches()
    recalculate_package_dates(str(student).strip())


def add_payment(
    student: str,
    number_of_lesson: int,
    payment_date: str,
    paid_amount: float,
    modality: str,
    subject: str = "",
    subject_custom: Optional[str] = None,
    package_start_date: Optional[str] = None,
    package_expiry_date: Optional[str] = None,
    lesson_adjustment_units: int = 0,
    package_normalized: bool = False,
    normalized_note: str = "",
    currency: str = "TRY",
) -> None:
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
    recalculate_package_dates(student)


def delete_row(table_name: str, row_id: int) -> None:
    uid = get_current_user_id()
    sb = get_sb()
    student_name = None
    if table_name in {"payments", "classes"}:
        try:
            q0 = sb.table(table_name).select("student").eq("id", int(row_id))
            if uid:
                q0 = q0.eq("user_id", uid)
            resp0 = q0.limit(1).execute()
            rows0 = getattr(resp0, "data", None) or []
            if rows0:
                student_name = str(rows0[0].get("student") or "").strip()
        except Exception:
            student_name = None
    q = sb.table(table_name).delete().eq("id", int(row_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()
    if student_name:
        recalculate_package_dates(student_name)


def normalize_latest_package(student: str, payment_id: int, note: str = "") -> bool:
    try:
        uid = get_current_user_id()
        sb = get_sb()
        payload = {
            "package_normalized": True,
            "normalized_note": str(note or "").strip(),
            "normalized_at": datetime.now(timezone.utc).isoformat(),
        }
        q = sb.table("payments").update(payload).eq("id", int(payment_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        return True
    except Exception:
        return False


def update_student_profile(student: str, email: str, zoom_link: str, notes: str, color: str, phone: str, address: str = "") -> None:
    uid = get_current_user_id()
    sb = get_sb()
    q = sb.table("students").update({
        "email": email,
        "zoom_link": zoom_link,
        "notes": notes,
        "color": color,
        "phone": phone,
        "address": address,
    }).eq("student", student)
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()


def update_payment_row(payment_id: int, updates: dict) -> bool:
    try:
        uid = get_current_user_id()
        sb = get_sb()
        student_name = None
        try:
            q0 = sb.table("payments").select("student").eq("id", int(payment_id))
            if uid:
                q0 = q0.eq("user_id", uid)
            resp0 = q0.limit(1).execute()
            rows0 = getattr(resp0, "data", None) or []
            if rows0:
                student_name = str(rows0[0].get("student") or "").strip()
        except Exception:
            student_name = None
        q = sb.table("payments").update(updates).eq("id", int(payment_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        if student_name:
            recalculate_package_dates(student_name)
        return True
    except Exception:
        return False


def update_class_row(class_id: int, updates: dict) -> bool:
    try:
        uid = get_current_user_id()
        sb = get_sb()
        student_name = None
        updates = dict(updates or {})
        if "note" in updates:
            updates["note"] = _normalize_lesson_note(updates.get("note"))
        try:
            q0 = sb.table("classes").select("student").eq("id", int(class_id))
            if uid:
                q0 = q0.eq("user_id", uid)
            resp0 = q0.limit(1).execute()
            rows0 = getattr(resp0, "data", None) or []
            if rows0:
                student_name = str(rows0[0].get("student") or "").strip()
        except Exception:
            student_name = None
        q = sb.table("classes").update(updates).eq("id", int(class_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        if student_name:
            recalculate_package_dates(student_name)
        return True
    except Exception:
        return False


def load_community_profiles() -> list:
    """Return all community-visible profiles."""
    try:
        sb = get_sb()
        res = (
            sb.table("profiles")
            .select(
                "user_id, display_name, username, avatar_url, country, primary_subjects, "
                "custom_subjects, "
                "teaching_stages, teaching_languages, education_level, active_student_count, "
                "show_community_profile, show_community_contact, phone_number, "
                "email, role, primary_role, can_teach, can_study, last_active_mode"
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
        import datetime as _dt
        sb = get_sb()
        cutoff = (_dt.date.today() - _dt.timedelta(days=183)).isoformat()

        cls_res = sb.table("classes").select("student, lesson_date").eq("user_id", str(user_id)).execute()
        cls_rows = getattr(cls_res, "data", None) or []
        pay_res = sb.table("payments").select("student, payment_date").eq("user_id", str(user_id)).execute()
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


def recalculate_package_dates(student: Optional[str] = None) -> dict:
    """Recompute package expiry dates from lesson usage.

    Rules:
    - package_start_date stays user-controlled; if missing, fill from payment_date
    - package_expiry_date becomes the date of the lesson that consumes the final paid unit
    - active / unfinished packages keep a blank expiry date
    - lessons after expiry still count for mismatch detection elsewhere, so expiry is descriptive
    """
    payments = load_table("payments")
    classes = load_table("classes")
    result = {"updated": 0, "students": 0, "mismatches": 0}

    if payments is None or payments.empty:
        return result

    if classes is None or classes.empty:
        classes = pd.DataFrame(columns=["student", "lesson_date", "number_of_lesson", "modality", "note"])

    for col in [
        "id", "student", "number_of_lesson", "payment_date", "package_start_date",
        "package_expiry_date", "lesson_adjustment_units", "modality"
    ]:
        if col not in payments.columns:
            payments[col] = None
    for col in ["student", "lesson_date", "number_of_lesson", "modality", "note"]:
        if col not in classes.columns:
            classes[col] = None

    payments = payments.copy()
    classes = classes.copy()
    payments["student"] = payments["student"].fillna("").astype(str).str.strip()
    classes["student"] = classes["student"].fillna("").astype(str).str.strip()

    if student:
        student = str(student).strip()
        payments = payments[payments["student"] == student].copy()
        classes = classes[classes["student"] == student].copy()

    if payments.empty:
        return result

    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
    payments["package_start_date"] = pd.to_datetime(payments["package_start_date"], errors="coerce")
    payments["package_expiry_date"] = pd.to_datetime(payments["package_expiry_date"], errors="coerce")
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["lesson_adjustment_units"] = pd.to_numeric(payments["lesson_adjustment_units"], errors="coerce").fillna(0).astype(int)
    payments["pkg_start"] = payments["package_start_date"].fillna(payments["payment_date"])

    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    classes["modality"] = classes["modality"].fillna("").astype(str)
    classes["note"] = classes["note"].fillna("").astype(str)

    from helpers.package_lang_lookups import _is_free_note, _units_multiplier

    classes["units_row"] = classes.apply(
        lambda row: 0
        if _is_free_note(row.get("note", ""))
        else int(row.get("number_of_lesson", 0)) * int(_units_multiplier(row.get("modality", ""))),
        axis=1,
    )

    updates_to_apply: list[tuple[int, dict]] = []

    ordered = payments.sort_values(["student", "pkg_start", "payment_date", "id"]).copy()
    for student_name, student_payments in ordered.groupby("student", sort=False):
        if not student_name:
            continue
        result["students"] += 1
        student_classes = (
            classes[
                (classes["student"] == student_name)
                & classes["lesson_date"].notna()
            ]
            .sort_values(["lesson_date", "id"], ascending=[True, True], kind="stable")
            .copy()
        )
        package_rows = student_payments.sort_values(["pkg_start", "payment_date", "id"], kind="stable").copy()
        package_rows["next_pkg_start"] = package_rows["pkg_start"].shift(-1)

        for _, pkg in package_rows.iterrows():
            payment_id = int(pkg["id"])
            pkg_start = pd.to_datetime(pkg.get("pkg_start"), errors="coerce")
            next_pkg_start = pd.to_datetime(pkg.get("next_pkg_start"), errors="coerce")
            purchased_units = int(pkg.get("number_of_lesson", 0)) * int(_units_multiplier(pkg.get("modality", "")))
            purchased_units += int(pkg.get("lesson_adjustment_units", 0) or 0)

            computed_start_iso = pkg_start.date().isoformat() if pd.notna(pkg_start) else None
            computed_expiry_iso = None
            mismatch_found = False

            if pd.notna(pkg_start) and purchased_units > 0:
                window = student_classes[student_classes["lesson_date"] >= pkg_start].copy()
                if pd.notna(next_pkg_start):
                    window = window[window["lesson_date"] < next_pkg_start].copy()
                cumulative = 0
                for _, lesson in window.iterrows():
                    cumulative += int(lesson.get("units_row", 0) or 0)
                    if computed_expiry_iso is None and cumulative >= purchased_units:
                        lesson_dt = pd.to_datetime(lesson.get("lesson_date"), errors="coerce")
                        if pd.notna(lesson_dt):
                            computed_expiry_iso = lesson_dt.date().isoformat()
                    if cumulative > purchased_units:
                        mismatch_found = True
                if mismatch_found:
                    result["mismatches"] += 1

            current_start_iso = pd.to_datetime(pkg.get("package_start_date"), errors="coerce")
            current_start_iso = current_start_iso.date().isoformat() if pd.notna(current_start_iso) else None
            current_expiry_iso = pd.to_datetime(pkg.get("package_expiry_date"), errors="coerce")
            current_expiry_iso = current_expiry_iso.date().isoformat() if pd.notna(current_expiry_iso) else None

            updates = {}
            if current_start_iso != computed_start_iso and computed_start_iso:
                updates["package_start_date"] = computed_start_iso
            if current_expiry_iso != computed_expiry_iso:
                updates["package_expiry_date"] = computed_expiry_iso

            if updates:
                updates_to_apply.append((payment_id, updates))

    if not updates_to_apply:
        return result

    uid = get_current_user_id()
    sb = get_sb()
    for payment_id, updates in updates_to_apply:
        q = sb.table("payments").update(updates).eq("id", int(payment_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        result["updated"] += 1

    clear_app_caches()
    return result


# ── Account deletion ────────────────────────────────────────────────────
_DELETE_TABLES = [
    "classes",
    "payments",
    "students",
    "schedules",
    "calendar_overrides",
    "pricing_items",
    "app_settings",
    "lesson_plans",
    "learning_programs",
    "ai_usage_logs",
    "user_activity_log",
    "professional_profiles",
    "worksheets",
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


def check_deleted_account(user_id: str) -> Optional[dict]:
    """Return deletion info if profile is soft-deleted, else None."""
    if not user_id:
        return None
    sb = get_sb()
    res = (
        sb.table("profiles")
        .select("account_status, deleted_at")
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    rows = getattr(res, "data", None) or []
    if not rows:
        return None
    row = rows[0]
    if row.get("account_status") != "deleted":
        return None
    return row
