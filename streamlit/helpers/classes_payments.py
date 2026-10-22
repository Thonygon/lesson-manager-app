import streamlit as st
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.database import get_sb, load_table, load_students
from core.database import add_class as _transactional_add_class, add_payment as _transactional_add_payment
from core.database import delete_row as _transactional_delete_row, _mutate_teacher_ledger
from typing import Optional
from core.database import clear_cache_domains


def _clear_operational_caches(*domains: str) -> None:
    clear_cache_domains(*domains, "dashboard", "notifications")
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
    _transactional_add_class(student, number_of_lesson, lesson_date, modality, note, subject)
    _clear_operational_caches("classes")

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
    _transactional_add_payment(student, number_of_lesson, payment_date, paid_amount, modality,
                               subject, package_start_date=package_start_date,
                               package_expiry_date=package_expiry_date,
                               lesson_adjustment_units=lesson_adjustment_units,
                               package_normalized=package_normalized,
                               normalized_note=normalized_note)
    _clear_operational_caches("payments")

def delete_row(table_name: str, row_id: int) -> None:
    _transactional_delete_row(table_name, row_id)
    _clear_operational_caches(table_name)

def normalize_latest_package(student: str, payment_id: int, note: str = "") -> bool:
    try:
        _mutate_teacher_ledger("payment", "update", int(payment_id), {
            "package_normalized": True,
            "normalized_note": str(note or "").strip(),
        })
        _clear_operational_caches("payments")
        return True
    except Exception:
        return False

def update_student_profile(student: str, email: str, zoom_link: str, notes: str, color: str, phone: str, address: str = "") -> None:
    uid = get_current_user_id()

    q = get_sb().table("students").update({
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
    _clear_operational_caches("students", "calendar")

def update_payment_row(payment_id: int, updates: dict, *, invalidate_cache: bool = True) -> bool:
    try:
        _mutate_teacher_ledger("payment", "update", int(payment_id), dict(updates or {}))
        if invalidate_cache:
            _clear_operational_caches("payments")
        return True
    except Exception:
        return False


def update_class_row(class_id: int, updates: dict, *, invalidate_cache: bool = True) -> bool:
    try:
        _mutate_teacher_ledger("class", "update", int(class_id), dict(updates or {}))
        if invalidate_cache:
            _clear_operational_caches("classes", "payments")
        return True
    except Exception:
        return False

# =========================
