import streamlit as st
import datetime
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from core.database import load_table
import pandas as pd
from helpers.calendar_helpers import build_calendar_events

# 07.2) TODAY LESSONS HELPER
# =========================
def build_today_lessons() -> pd.DataFrame:
    today = today_local()

    events = build_calendar_events(today, today)
    if events is None or events.empty:
        return pd.DataFrame()

    df = events.copy()

    # Clean
    df["Student"] = df["Student"].astype(str).str.strip()
    df["Time"] = df["Time"].astype(str)
    df["Duration_Min"] = pd.to_numeric(df["Duration_Min"], errors="coerce").fillna(60).astype(int)

    # Optional: sort by time
    df = df.sort_values("Time").reset_index(drop=True)

    return df[["Student", "Time", "Duration_Min", "Source"]]

# =========================
