"""Metadata-only records of Streamlit PDF/Word download handoff requests."""

from __future__ import annotations

from pathlib import PurePath
from datetime import datetime, timezone
from uuid import UUID, uuid4

import streamlit as st

from core.database import get_sb
from core.state import get_current_user_id


def _variant(file_name: str) -> str:
    name = PurePath(file_name).stem.lower()
    if name.endswith(("_student", "-student")):
        return "student"
    if name.endswith(("_teacher", "-teacher")):
        return "teacher"
    if name.endswith(("_answers", "-answers", "_answer_key", "-answer-key")):
        return "answers"
    return "full"


def record_export_handoff(format: str, document_kind: str, variant: str = "full") -> None:
    """A handoff request is not proof that the browser saved the file."""
    if format not in {"pdf", "docx"} or document_kind not in {"lesson_plan", "worksheet", "exam", "cv", "cover_letter", "student_report", "student_history", "dashboard_report", "other"} or variant not in {"full", "student", "teacher", "answers"}:
        raise ValueError("Invalid document export metadata")
    user_id = str(get_current_user_id() or "").strip()
    if not user_id:
        return  # Public Explorer downloads have no billable account.
    try:
        actor = str(UUID(user_id))
    except (TypeError, ValueError, AttributeError):
        raise RuntimeError("Sign in to export a document") from None
    payload = {
        "event_id": str(uuid4()),
        "actor_user_id": actor,
        "source": "streamlit",
        "format": format,
        "document_kind": document_kind,
        "variant": variant,
        "status": "handoff_requested",
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    get_sb().table("classio_document_export_events").insert(payload).execute()


def recorded_download_button(*args, document_kind: str, variant: str | None = None, **kwargs):
    """Preserve Streamlit's button result while recording each observed click."""
    clicked = st.download_button(*args, **kwargs)
    if clicked:
        file_name = str(kwargs.get("file_name") or "")
        mime = str(kwargs.get("mime") or "").lower()
        format = "docx" if file_name.lower().endswith(".docx") or "wordprocessingml" in mime else "pdf" if file_name.lower().endswith(".pdf") or mime == "application/pdf" else ""
        record_export_handoff(format, document_kind, variant or _variant(file_name))
    return clicked
