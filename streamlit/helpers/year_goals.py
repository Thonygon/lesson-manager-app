import streamlit as st
import datetime
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local
from core.database import get_sb, load_table
from core.state import with_owner
from core.database import clear_app_caches
from helpers.goals import YEAR_GOAL_SCOPE, _parse_float_loose

# 07.12)YEAR GOALS
# =========================
def _settings_client():
    # anon client with logged-in session applied via get_sb().auth.set_session(...)
    return get_sb()

def _year_goal_key(year: int, scope: str = YEAR_GOAL_SCOPE) -> str:
    """
    scope lets you separate goals if you ever want:
      - "personal" (default)
      - "business"
      - etc
    """
    y = int(year)
    s = str(scope or YEAR_GOAL_SCOPE).strip().casefold()
    return f"year_goal_{y}_{s}"

def get_year_goal(year: int, scope: str = YEAR_GOAL_SCOPE, default: float = 0.0) -> float:
    key = _year_goal_key(year, scope=scope)
    uid = get_current_user_id()

    try:
        q = _settings_client().table("app_settings").select("value").eq("key", key)
        if uid:
            q = q.eq("user_id", uid)

        res = q.limit(1).execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            return float(default or 0.0)

        v = rows[0].get("value")
        return float(_parse_float_loose(v, default or 0.0))
    except Exception:
        return float(default or 0.0)


def set_year_goal(year: int, value: float, scope: str = YEAR_GOAL_SCOPE) -> bool:
    key = _year_goal_key(year, scope=scope)
    payload = with_owner({"key": key, "value": str(value)})

    try:
        _settings_client().table("app_settings").upsert(
            payload,
            on_conflict="user_id,key"
        ).execute()
        clear_app_caches()
        return True
    except Exception:
        return False

# =========================
