"""
Google Calendar integration for Classio.

Flow:
1. Teacher clicks "Connect Google Calendar" → redirected to Google OAuth consent.
2. After consent, Google redirects back with ?code=… query parameter.
3. App exchanges the code for tokens, stores refresh_token in Supabase profiles.
4. When a schedule/override is created, a Google Calendar event is created/updated.

Required secrets (.streamlit/secrets.toml):
    GOOGLE_CAL_CLIENT_ID = "…"
    GOOGLE_CAL_CLIENT_SECRET = "…"
"""

import os
import json
import requests as _requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from core.state import get_current_user_id
from core.database import get_sb
from core.timezone import get_app_tz_name


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

_REDIRECT_URI_FALLBACK = "http://localhost:8501"


def _get_client_config() -> dict:
    client_id = st.secrets.get("GOOGLE_CAL_CLIENT_ID", "") or os.getenv("GOOGLE_CAL_CLIENT_ID", "")
    client_secret = st.secrets.get("GOOGLE_CAL_CLIENT_SECRET", "") or os.getenv("GOOGLE_CAL_CLIENT_SECRET", "")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _get_redirect_uri() -> str:
    return (
        st.secrets.get("GOOGLE_CAL_REDIRECT_URI", "")
        or os.getenv("GOOGLE_CAL_REDIRECT_URI", "")
        or _REDIRECT_URI_FALLBACK
    )


def gcal_configured() -> bool:
    cfg = _get_client_config()
    cid = cfg.get("web", {}).get("client_id", "")
    return bool(cid)


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_google_auth_url() -> str:
    cfg = _get_client_config()["web"]
    params = urlencode({
        "client_id": cfg["client_id"],
        "redirect_uri": _get_redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": "gcal_connect",
    })
    return f"https://accounts.google.com/o/oauth2/auth?{params}"


def exchange_code_for_tokens(code: str) -> Optional[dict]:
    try:
        cfg = _get_client_config()["web"]
        resp = _requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": _get_redirect_uri(),
            "grant_type": "authorization_code",
        })
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            err_msg = data.get("error_description") or data.get("error") or resp.text
            st.session_state["_gcal_debug_error"] = f"Token exchange failed: {err_msg}"
            return None
        return {
            "token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "scopes": SCOPES,
        }
    except Exception as exc:
        import traceback
        st.session_state["_gcal_debug_error"] = f"{exc}\n\nRedirect URI: {_get_redirect_uri()}\n\n{traceback.format_exc()}"
        return None


# ---------------------------------------------------------------------------
# Token persistence (Supabase profiles table)
# ---------------------------------------------------------------------------

def save_gcal_tokens(token_data: dict) -> None:
    uid = get_current_user_id()
    if not uid:
        return
    get_sb().table("profiles").update(
        {"gcal_tokens": json.dumps(token_data)}
    ).eq("user_id", uid).execute()


def load_gcal_tokens() -> Optional[dict]:
    uid = get_current_user_id()
    if not uid:
        return None
    try:
        res = (
            get_sb()
            .table("profiles")
            .select("gcal_tokens")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return None
        raw = rows[0].get("gcal_tokens")
        if not raw:
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None


def clear_gcal_tokens() -> None:
    uid = get_current_user_id()
    if not uid:
        return
    try:
        get_sb().table("profiles").update(
            {"gcal_tokens": None}
        ).eq("user_id", uid).execute()
    except Exception:
        pass


def is_gcal_connected() -> bool:
    tokens = load_gcal_tokens()
    return bool(tokens and tokens.get("refresh_token"))


# ---------------------------------------------------------------------------
# Calendar API client
# ---------------------------------------------------------------------------

def _get_calendar_service():
    tokens = load_gcal_tokens()
    if not tokens or not tokens.get("refresh_token"):
        return None

    creds = Credentials(
        token=tokens.get("token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=tokens.get("client_id") or _get_client_config()["web"]["client_id"],
        client_secret=tokens.get("client_secret") or _get_client_config()["web"]["client_secret"],
        scopes=SCOPES,
    )

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    if creds.token != tokens.get("token"):
        tokens["token"] = creds.token
        save_gcal_tokens(tokens)

    return service


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------

def _get_student_info(student: str) -> dict:
    """Look up student profile data (email, zoom, phone, address, notes)."""
    from helpers.student_meta import load_students_df
    from core.database import norm_student
    df = load_students_df()
    if df.empty:
        return {}
    df["_norm"] = df["student"].apply(norm_student)
    match = df[df["_norm"] == norm_student(student)]
    if match.empty:
        return {}
    row = match.iloc[0]
    return {
        "email": row.get("email", "") or "",
        "zoom_link": row.get("zoom_link", "") or "",
        "phone": row.get("phone", "") or "",
        "address": row.get("address", "") or "",
        "notes": row.get("notes", "") or "",
    }


def _build_event_body(student: str, start_dt: datetime, duration_minutes: int, note: str = "") -> dict:
    """Build a rich Google Calendar event body with student info."""
    tz = get_app_tz_name()
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    info = _get_student_info(student)

    # Build description with available student info
    desc_parts = []
    if note:
        desc_parts.append(note)
    if info.get("zoom_link"):
        desc_parts.append(f"Zoom: {info['zoom_link']}")
    if info.get("phone"):
        desc_parts.append(f"Phone: {info['phone']}")
    if info.get("address"):
        desc_parts.append(f"Address: {info['address']}")
    if info.get("notes"):
        desc_parts.append(f"Notes: {info['notes']}")
    description = "\n".join(desc_parts) if desc_parts else f"Lesson with {student}"

    event_body = {
        "summary": f"Classio: {student}",
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        "reminders": {"useDefault": True},
    }

    # Add student as attendee so they receive an email invitation
    if info.get("email"):
        event_body["attendees"] = [
            {"email": info["email"], "displayName": student},
        ]

    # Set location (physical address takes priority over Zoom link)
    if info.get("address"):
        event_body["location"] = info["address"]
    elif info.get("zoom_link"):
        event_body["location"] = info["zoom_link"]

    return event_body


def create_gcal_event(
    student: str,
    start_dt: datetime,
    duration_minutes: int = 60,
    note: str = "",
) -> Optional[str]:
    service = _get_calendar_service()
    if not service:
        return None

    event_body = _build_event_body(student, start_dt, duration_minutes, note)

    try:
        event = service.events().insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all",
        ).execute()
        return event.get("id")
    except Exception:
        return None


def delete_gcal_event(event_id: str) -> bool:
    service = _get_calendar_service()
    if not service or not event_id:
        return False
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True
    except Exception:
        return False


def update_gcal_event(
    event_id: str,
    student: str,
    start_dt: datetime,
    duration_minutes: int = 60,
    note: str = "",
) -> bool:
    service = _get_calendar_service()
    if not service or not event_id:
        return False

    event_body = _build_event_body(student, start_dt, duration_minutes, note)

    try:
        service.events().patch(
            calendarId="primary", eventId=event_id, body=event_body,
            sendUpdates="all",
        ).execute()
        return True
    except Exception:
        return False
