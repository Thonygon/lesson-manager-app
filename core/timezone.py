import streamlit as st
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Istanbul")
UTC_TZ = timezone.utc
DEFAULT_TZ_NAME = "Europe/Istanbul"


def _get_qp(key: str, default=None):
    try:
        qp = st.query_params
        v = qp.get(key, default)
        if isinstance(v, list):
            v = v[0] if v else default
        return v if v is not None else default
    except Exception:
        qp = st.experimental_get_query_params()
        v = qp.get(key, [default])
        return v[0] if v else default


def detect_browser_timezone():
    tz_qp = _get_qp("browser_tz", "")
    if tz_qp:
        st.session_state["browser_tz"] = str(tz_qp).strip()
        st.session_state["_browser_tz_checked"] = True
        return

    if st.session_state.get("_browser_tz_checked"):
        return

    # Avoid injecting startup HTML/iframe blocks into the first page render.
    # If the browser timezone is not already present in query params, we fall
    # back to the default app timezone for this session.
    st.session_state["_browser_tz_checked"] = True


def get_app_tz_name() -> str:
    tz_name = str(
        st.session_state.get("browser_tz") or DEFAULT_TZ_NAME
    ).strip()
    try:
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return DEFAULT_TZ_NAME


def get_app_tz() -> ZoneInfo:
    return ZoneInfo(get_app_tz_name())


def now_local() -> datetime:
    return datetime.now(get_app_tz())


def today_local() -> date:
    return now_local().date()
