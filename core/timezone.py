import streamlit as st
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Istanbul")
UTC_TZ = timezone.utc
DEFAULT_TZ_NAME = "Europe/Istanbul"


def _inject_browser_timezone_sync(current_tz_qp: str) -> None:
    try:
        import streamlit.components.v1 as components

        safe_current = str(current_tz_qp or "").replace("\\", "\\\\").replace('"', '\\"')
        components.html(
            f"""
            <script>
            (function() {{
              const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
              const current = "{safe_current}";
              if (!tz || tz === current) return;
              const url = new URL(window.parent.location.href);
              url.searchParams.set("browser_tz", tz);
              window.parent.location.replace(url.toString());
            }})();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        pass


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
    elif not st.session_state.get("_browser_tz_checked"):
        st.session_state["_browser_tz_checked"] = True

    _inject_browser_timezone_sync(str(tz_qp or st.session_state.get("browser_tz") or ""))


def get_app_tz_name() -> str:
    profile_tz = str(st.session_state.get("profile_timezone") or "").strip()
    if not profile_tz:
        try:
            from core.state import get_current_user_id
            from core.database import load_profile_row

            uid = get_current_user_id()
            profile = load_profile_row(uid) if uid else {}
            profile_tz = str((profile or {}).get("timezone") or "").strip()
        except Exception:
            profile_tz = ""

    tz_name = str(
        st.session_state.get("browser_tz") or profile_tz or DEFAULT_TZ_NAME
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
