import streamlit as st
from core.database import _execute_query_with_diagnostics, get_sb, load_table_filtered
import pandas as pd
from core.database import norm_student, register_cache
import re

# 07.10) STUDENT META
# =========================
_STUDENT_META_COLUMNS = (
    "student,email,zoom_link,notes,color,phone,address,native_language,"
    "linked_student_user_id,teacher_student_link_id,student_source,linked_at"
)
_STUDENT_META_COLUMN_LIST = [column.strip() for column in _STUDENT_META_COLUMNS.split(",") if column.strip()]


def _is_missing_student_column_error(exc: Exception | str | None, column_name: str) -> bool:
    text = str(exc or "").strip().lower()
    target = str(column_name or "").strip().lower()
    if not text or not target:
        return False
    target_patterns = [
        re.escape(f".{target}"),
        re.escape(f"'{target}'"),
        re.escape(f'"{target}"'),
        re.escape(f" {target} "),
        re.escape(f"({target})"),
        re.escape(f",{target}"),
    ]
    target_match = any(re.search(pattern, text) for pattern in target_patterns)
    return target_match and any(
        marker in text
        for marker in (
            "column",
            "schema cache",
            "could not find",
            "does not exist",
            "not found",
        )
    )


def _extract_missing_student_column(exc: Exception | str | None, requested_columns: list[str]) -> str:
    for column_name in requested_columns:
        if _is_missing_student_column_error(exc, column_name):
            return column_name
    return ""


def _load_student_meta_rows(uid: str, columns: str) -> list[dict]:
    safe_uid = str(uid or "").strip()
    if not safe_uid:
        return []
    query = (
        get_sb()
        .table("students")
        .select(columns)
        .eq("user_id", safe_uid)
        .order("student", desc=False)
        .limit(5000)
    )
    result = _execute_query_with_diagnostics(
        query,
        function_name="load_students_df",
        source_name="students",
    )
    return list(getattr(result, "data", None) or [])


def _load_student_meta_rows_with_fallback(uid: str) -> pd.DataFrame:
    remaining_columns = list(_STUDENT_META_COLUMN_LIST)
    while remaining_columns:
        try:
            return pd.DataFrame(_load_student_meta_rows(uid, ",".join(remaining_columns)))
        except Exception as exc:
            missing_column = _extract_missing_student_column(exc, remaining_columns)
            if not missing_column:
                raise
            remaining_columns = [column for column in remaining_columns if column != missing_column]
    return pd.DataFrame()


@st.cache_data(ttl=45, show_spinner=False)
def load_students_df() -> pd.DataFrame:
    uid = str(st.session_state.get("user_id") or "").strip()
    if not uid:
        from core.state import get_current_user_id

        uid = str(get_current_user_id() or "").strip()
    try:
        df = _load_student_meta_rows_with_fallback(uid)
    except Exception:
        df = load_table_filtered(
            "students",
            columns=_STUDENT_META_COLUMNS,
            limit=5000,
            page_size=500,
            order_by="student",
            order_desc=False,
        )

    if df.empty:
        return pd.DataFrame(columns=["student", "email", "zoom_link", "notes", "color", "phone", "address", "native_language", "linked_student_user_id", "teacher_student_link_id", "student_source", "linked_at"])

    for c, default in {
        "student": "", "email": "", "zoom_link": "", "notes": "", "color": "#3B82F6", "phone": "", "address": "", "native_language": "",
        "linked_student_user_id": "", "teacher_student_link_id": None, "student_source": "manual", "linked_at": None,
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["color"] = df["color"].fillna("#3B82F6").astype(str).str.strip()
    df["zoom_link"] = df["zoom_link"].fillna("").astype(str).str.strip()
    df["email"] = df["email"].fillna("").astype(str).str.strip()
    df["notes"] = df["notes"].fillna("").astype(str)
    df["phone"] = df["phone"].fillna("").astype(str).str.strip()
    df["address"] = df["address"].fillna("").astype(str).str.strip()
    df["native_language"] = df["native_language"].fillna("").astype(str).str.strip()
    df["linked_student_user_id"] = df["linked_student_user_id"].fillna("").astype(str).str.strip()
    df["student_source"] = df["student_source"].fillna("manual").astype(str).str.strip()

    return df


register_cache(load_students_df)

def student_meta_maps():
    s = load_students_df()
    if s.empty:
        return {}, {}, {}, {}, {}
    s["student_norm"] = s["student"].apply(norm_student)
    color_map   = dict(zip(s["student_norm"], s["color"]))
    zoom_map    = dict(zip(s["student_norm"], s["zoom_link"]))
    email_map   = dict(zip(s["student_norm"], s["email"]))
    phone_map   = dict(zip(s["student_norm"], s["phone"]))
    address_map = dict(zip(s["student_norm"], s["address"]))
    return color_map, zoom_map, email_map, phone_map, address_map


student_meta_maps = st.cache_data(ttl=45, show_spinner=False)(student_meta_maps)
register_cache(student_meta_maps)

# =========================
