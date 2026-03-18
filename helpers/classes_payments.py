import streamlit as st
import datetime
from datetime import datetime as _dt, timezone
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.database import get_sb, load_table, load_students
from typing import Optional
from core.state import with_owner
from core.database import ensure_student, clear_app_caches
# 07.5) CLASSES / PAYMENTS HELPERS
# =========================
def add_class(
    student: str,
    number_of_lesson: int,
    lesson_date: str,
    modality: str,
    note: str = "",
    subject: Optional[str] = None
) -> None:
    student = str(student).strip()
    ensure_student(student)

    payload = with_owner({
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,
        "modality": str(modality).strip(),
        "note": str(note).strip() if note else "",
        "subject": str(subject).strip() if subject else None,
    })

    get_sb().table("classes").insert(payload).execute()
    clear_app_caches()

def add_payment(
    student: str,
    number_of_lesson: int,
    payment_date: str,
    paid_amount: float,
    modality: str,
    subject: str = "",
    package_start_date: Optional[str] = None,
    package_expiry_date: Optional[str] = None,
    lesson_adjustment_units: int = 0,
    package_normalized: bool = False,
    normalized_note: str = ""
) -> None:
    student = str(student).strip()
    ensure_student(student)

    if not package_start_date:
        package_start_date = payment_date

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
        "normalized_at": _dt.now(timezone.utc).isoformat() if (package_normalized or normalized_note) else None,
    })

    get_sb().table("payments").insert(payload).execute()
    clear_app_caches()

def delete_row(table_name: str, row_id: int) -> None:
    uid = get_current_user_id()
    q = get_sb().table(table_name).delete().eq("id", int(row_id))
    if uid:
        q = q.eq("user_id", uid)
    q.execute()
    clear_app_caches()

def normalize_latest_package(student: str, payment_id: int, note: str = "") -> bool:
    try:
        uid = get_current_user_id()
        payload = {
            "package_normalized": True,
            "normalized_note": str(note or "").strip(),
            "normalized_at": _dt.now(timezone.utc).isoformat()
        }
        q = get_sb().table("payments").update(payload).eq("id", int(payment_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        return True
    except Exception:
        return False

def update_student_profile(student: str, email: str, zoom_link: str, notes: str, color: str, phone: str) -> None:
    uid = get_current_user_id()

    q = get_sb().table("students").update({
        "email": email,
        "zoom_link": zoom_link,
        "notes": notes,
        "color": color,
        "phone": phone
    }).eq("student", student)

    if uid:
        q = q.eq("user_id", uid)

    q.execute()
    clear_app_caches()

def update_payment_row(payment_id: int, updates: dict) -> bool:
    try:
        uid = get_current_user_id()
        q = get_sb().table("payments").update(updates).eq("id", int(payment_id))
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
        q = get_sb().table("classes").update(updates).eq("id", int(class_id))
        if uid:
            q = q.eq("user_id", uid)
        q.execute()
        clear_app_caches()
        return True
    except Exception:
        return False

# =========================
