import streamlit as st
from core.i18n import t
from core.state import get_current_user_id
from core.database import get_sb
from helpers.language import LANG_ES, ALLOWED_LANGS

# 07.7) PACKAGE/LANGUAGE LOOKUPS
# =========================
def latest_payment_languages_for_student(student: str) -> str:
    try:
        uid = get_current_user_id()

        q = (
            get_sb().table("payments")
            .select("id, payment_date, package_start_date, subject")
            .eq("student", str(student).strip())
        )

        if uid:
            q = q.eq("user_id", uid)

        resp = (
            q.order("payment_date", desc=True)
             .order("id", desc=True)
             .limit(1)
             .execute()
        )

        rows = resp.data or []
        if not rows:
            return LANG_ES

        v = str(rows[0].get("subject") or LANG_ES).strip()
        return v if v in ALLOWED_LANGS else LANG_ES
    except Exception:
        return LANG_ES


def _units_multiplier(modality: str) -> int:
    return 1


def _is_free_note(note: str) -> bool:
    n = str(note or "").upper()
    return ("[FREE]" in n) or ("[DEMO]" in n) or ("[DONT COUNT]" in n) or ("[DON'T COUNT]" in n)


# =========================
