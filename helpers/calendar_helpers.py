import streamlit as st
import datetime
from datetime import datetime as _dt, date, timedelta
import pandas as pd
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local, get_app_tz, get_app_tz_name
from core.database import load_table, load_students, register_cache
import re
import json
from typing import Tuple
import streamlit.components.v1 as components
from core.database import norm_student
from helpers.schedule import load_schedules, load_overrides
from helpers.student_meta import student_meta_maps
from helpers.ui_components import to_dt_naive

# 07.17) CALENDAR (EVENTS + RENDER) ✅ bilingual-safe + tz-safe + FullCalendar i18n
# =========================
def _parse_time_value(x) -> Tuple[int, int]:
    if x is None:
        return (0, 0)

    s = str(x).strip()
    if not s:
        return (0, 0)

    parts = s.split(":")

    try:
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except Exception:
        return (0, 0)


def validate_hhmm(value: str) -> str:
    """
    Ensures a time string is in HH:MM 24h format.
    Returns the cleaned value or raises a user-friendly error.
    """
    s = str(value or "").strip()

    if re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", s):
        return s

    raise ValueError(t("invalid_time_format"))


def best_text_color(hex_color: str) -> str:
    try:
        c = str(hex_color or "").lstrip("#")
        if len(c) != 6:
            return "#0F172A"

        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        lum = (0.299 * r + 0.587 * g + 0.114 * b)

        return "#0F172A" if lum > 160 else "#FFFFFF"
    except Exception:
        return "#0F172A"


@st.cache_data(ttl=45, show_spinner=False)
def build_calendar_events(start_day: date, end_day: date) -> pd.DataFrame:
    schedules = load_schedules()
    overrides = load_overrides()
    color_map, zoom_map, _, _ = student_meta_maps()

    events = []

    # -------------------------
    # Recurring schedules
    # -------------------------
    if schedules is not None and not schedules.empty:
        for c in ["student", "weekday", "time", "duration_minutes", "active"]:
            if c not in schedules.columns:
                schedules[c] = None

        schedules_active = schedules[schedules["active"] == True].copy()

        cur = start_day
        while cur <= end_day:
            wd = cur.weekday()  # 0=Mon .. 6=Sun
            day_slots = schedules_active[schedules_active["weekday"] == wd]

            for _, row in day_slots.iterrows():
                h, m = _parse_time_value(row.get("time"))
                dt = _dt(cur.year, cur.month, cur.day, h, m)

                student = str(row.get("student", "")).strip()
                k = norm_student(student)
                duration = int(
                    pd.to_numeric(row.get("duration_minutes", 60), errors="coerce") or 60
                )

                events.append(
                    {
                        "DateTime": dt,
                        "Date": dt.date(),
                        "Student": student,
                        "Duration_Min": duration,
                        "Color": color_map.get(k, "#3B82F6"),
                        "Zoom_Link": zoom_map.get(k, ""),
                        "Source": "recurring",
                        "Override_ID": None,
                        "Original_Date": dt.date(),
                    }
                )

            cur += timedelta(days=1)

    events_df = pd.DataFrame(events)

    # -------------------------
    # Apply overrides
    # - cancel: remove recurring on original_date
    # - scheduled: remove recurring on original_date + add new slot
    # -------------------------
    if overrides is not None and not overrides.empty:
        for c in ["id", "student", "status", "new_datetime", "original_date", "duration_minutes"]:
            if c not in overrides.columns:
                overrides[c] = None

        for _, row in overrides.iterrows():
            student = str(row.get("student", "")).strip()
            k = norm_student(student)

            status = str(row.get("status", "")).strip().lower()
            new_dt = row.get("new_datetime")
            original_date = row.get("original_date")
            duration = int(pd.to_numeric(row.get("duration_minutes", 60), errors="coerce") or 60)

            # Remove recurring on original date
            if pd.notna(original_date) and events_df is not None and not events_df.empty:
                try:
                    od = pd.to_datetime(original_date, errors="coerce").date()
                    events_df = events_df[
                        ~((events_df["Student"] == student) & (events_df["Date"] == od))
                    ]
                except Exception:
                    pass

            # Add scheduled override slot
            if status == "scheduled" and pd.notna(new_dt):
                try:
                    nd = pd.to_datetime(new_dt, errors="coerce")
                    if pd.isna(nd):
                        continue

                    if start_day <= nd.date() <= end_day:
                        add_row = {
                            "DateTime": nd.to_pydatetime() if hasattr(nd, "to_pydatetime") else nd,
                            "Date": nd.date(),
                            "Student": student,
                            "Duration_Min": duration,
                            "Color": color_map.get(k, "#3B82F6"),
                            "Zoom_Link": zoom_map.get(k, ""),
                            "Source": "override",
                            "Override_ID": int(row.get("id")) if pd.notna(row.get("id")) else None,
                            "Original_Date": (
                                pd.to_datetime(original_date, errors="coerce").date()
                                if pd.notna(original_date)
                                else nd.date()
                            ),
                        }
                        events_df = pd.concat(
                            [events_df, pd.DataFrame([add_row])],
                            ignore_index=True,
                        )
                except Exception:
                    pass

    if events_df is None or events_df.empty:
        return events_df

    events_df["DateTime"] = to_dt_naive(events_df["DateTime"], utc=False)
    events_df = events_df.dropna(subset=["DateTime"]).sort_values("DateTime").reset_index(drop=True)
    events_df["Time"] = pd.to_datetime(events_df["DateTime"], errors="coerce").dt.strftime("%H:%M")
    events_df["Date"] = pd.to_datetime(events_df["DateTime"], errors="coerce").dt.strftime("%Y-%m-%d")

    return events_df


def render_fullcalendar(events: pd.DataFrame, height: int = 750):
    """
    FullCalendar renderer with:
      ✅ Mon-first week (firstDay=1)
      ✅ Translated calendar UI buttons
      ✅ Dark/light/auto theme support inside iframe
      ✅ Safe for mobile
    """
    if events is None or events.empty:
        st.info(t("no_events"))
        return

    df = events.copy()
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")
    df = df.dropna(subset=["DateTime"])

    df["Duration_Min"] = pd.to_numeric(
        df.get("Duration_Min"),
        errors="coerce",
    ).fillna(60).astype(int)

    df["end"] = df["DateTime"] + pd.to_timedelta(df["Duration_Min"], unit="m")

    fc_events = []
    for _, r in df.iterrows():
        zoom = str(r.get("Zoom_Link", "") or "").strip()
        title = str(r.get("Student", "")).strip()
        color = str(r.get("Color", "#3B82F6")).strip()
        tc = best_text_color(color)

        fc_events.append(
            {
                "title": title,
                "start": r["DateTime"].isoformat(),
                "end": r["end"].isoformat(),
                "backgroundColor": color,
                "borderColor": color,
                "textColor": tc,
                "url": zoom if zoom.startswith("http") else None,
            }
        )

    payload = json.dumps(fc_events)

    ui_lang = st.session_state.get("ui_lang", "en")
    theme_mode = str(st.session_state.get("ui_theme_mode", "auto")).strip().lower()
    is_es = ui_lang == "es"

    fc_locale = "es" if is_es else "en"

    btn_today = "Hoy" if is_es else "Today"
    btn_month = "Mes" if is_es else "Month"
    btn_week = "Semana" if is_es else "Week"
    btn_day = "Día" if is_es else "Day"
    btn_list = "Lista" if is_es else "List"

    all_day_text = "Todo el día" if is_es else "All-day"
    more_template = "+{n} más" if is_es else "+{n} more"

    html = f"""
    <div id="calendar-wrap">
      <div id="calendar"></div>
    </div>

    <script>
      window.__THEME_MODE__ = "{theme_mode}";
    </script>

    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js"></script>

    <style>
      :root {{
        --cal-bg: #ffffff;
        --cal-panel: #ffffff;
        --cal-border: rgba(17,24,39,0.10);
        --cal-text: #0f172a;
        --cal-muted: #334155;
        --cal-btn-bg: rgba(96,165,250,0.22);
        --cal-btn-bg-hover: rgba(96,165,250,0.32);
        --cal-btn-border: rgba(96,165,250,0.45);
        --cal-btn-border-strong: rgba(96,165,250,0.60);
      }}

      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
      }}

      body.theme-dark {{
        --cal-bg: #0f172a;
        --cal-panel: #1e293b;
        --cal-border: rgba(255,255,255,0.10);
        --cal-text: #f1f5f9;
        --cal-muted: #cbd5e1;
        --cal-btn-bg: rgba(96,165,250,0.18);
        --cal-btn-bg-hover: rgba(96,165,250,0.28);
        --cal-btn-border: rgba(96,165,250,0.35);
        --cal-btn-border-strong: rgba(96,165,250,0.52);
      }}

      #calendar-wrap {{
        background: var(--cal-panel);
        border: 1px solid var(--cal-border);
        border-radius: 16px;
        padding: 10px;
      }}

      #calendar,
      .fc {{
        color: var(--cal-text) !important;
      }}

      .fc-theme-standard td,
      .fc-theme-standard th,
      .fc-theme-standard .fc-scrollgrid,
      .fc-theme-standard .fc-list {{
        border-color: var(--cal-border) !important;
      }}

      .fc .fc-scrollgrid,
      .fc .fc-timegrid,
      .fc .fc-view-harness,
      .fc .fc-timegrid-body,
      .fc .fc-timegrid-slots,
      .fc .fc-timegrid-cols,
      .fc .fc-col-header,
      .fc .fc-col-header-cell,
      .fc .fc-timegrid-axis,
      .fc .fc-timegrid-slot,
      .fc .fc-timegrid-slot-lane {{
        background: var(--cal-panel) !important;
      }}

      .fc .fc-col-header-cell,
      .fc .fc-timegrid-axis {{
        background: rgba(255,255,255,0.04) !important;
      }}

      .fc .fc-col-header-cell-cushion {{
        color: var(--cal-text) !important;
        text-decoration: none !important;
        font-weight: 700;
      }}    

      .fc .fc-button,
      .fc .fc-button-primary {{
        border-radius: 10px;
        border: 1px solid var(--cal-btn-border) !important;
        background: var(--cal-btn-bg) !important;
        color: var(--cal-text) !important;
        box-shadow: none !important;
      }}

      .fc .fc-button:hover,
      .fc .fc-button-primary:hover {{
        border: 1px solid var(--cal-btn-border-strong) !important;
        background: var(--cal-btn-bg-hover) !important;
        color: var(--cal-text) !important;
      }}

      .fc .fc-button:focus,
      .fc .fc-button-primary:focus,
      .fc .fc-button:active,
      .fc .fc-button-primary:active,
      .fc .fc-button-active,
      .fc .fc-button-primary.fc-button-active {{
        border: 1px solid var(--cal-btn-border-strong) !important;
        background: var(--cal-btn-bg-hover) !important;
        color: var(--cal-text) !important;
        box-shadow: none !important;
      }}

      .fc .fc-button:disabled,
      .fc .fc-button-primary:disabled {{
        opacity: 0.65 !important;
        color: var(--cal-muted) !important;
      }}

      .fc .fc-toolbar-title,
      .fc .fc-col-header-cell-cushion,
      .fc .fc-daygrid-day-number,
      .fc .fc-list-day-text,
      .fc .fc-list-day-side-text {{
        color: var(--cal-text) !important;
        text-decoration: none !important;
      }}

      .fc .fc-timegrid-slot-label-cushion,
      .fc .fc-list-event-time,
      .fc .fc-list-event-title {{
        color: var(--cal-muted) !important;
      }}

      .fc .fc-day-today {{
        background: rgba(96,165,250,0.10) !important;
      }}

      .fc .fc-toolbar-title {{
        font-weight: 800;
        font-size: 1.1rem;
        line-height: 1.15;
      }}

      @media (max-width: 768px) {{
        .fc .fc-toolbar-title {{
          font-size: 0.95rem;
        }}

        .fc .fc-button {{
          padding: 0.35rem 0.55rem;
          font-size: 0.85rem;
        }}
      }}
    </style>

    <script>
      const events = {payload};
      const calendarEl = document.getElementById("calendar");
      const isMobile = () => window.innerWidth < 768;

      function applyTheme() {{
        const mode = window.__THEME_MODE__ || "auto";
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        const dark = mode === "dark" || (mode === "auto" && prefersDark);

        document.body.classList.toggle("theme-dark", dark);
      }}

      applyTheme();

      const media = window.matchMedia("(prefers-color-scheme: dark)");
      if (media && media.addEventListener) {{
        media.addEventListener("change", () => {{
          applyTheme();
        }});
      }}

      const toolbarDesktop = {{
        left: "prev,next today",
        center: "title",
        right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
      }};

      const toolbarMobile = {{
        left: "prev,next",
        center: "title",
        right: "timeGridDay,timeGridWeek,dayGridMonth"
      }};

      const calendar = new FullCalendar.Calendar(calendarEl, {{
        initialView: "timeGridWeek",
        height: {height},
        expandRows: true,
        nowIndicator: true,
        stickyHeaderDates: true,
        handleWindowResize: true,
        firstDay: 1,

        headerToolbar: isMobile() ? toolbarMobile : toolbarDesktop,

        locale: "{fc_locale}",
        buttonText: {{
          today: "{btn_today}",
          month: "{btn_month}",
          week: "{btn_week}",
          day: "{btn_day}",
          list: "{btn_list}"
        }},

        views: {{
          dayGridMonth: {{
            buttonText: "{btn_month}",
            dayHeaderFormat: {{ weekday: "short" }}
          }},
          timeGridWeek: {{
            buttonText: "{btn_week}",
            dayHeaderFormat: {{ weekday: "short", day: "numeric" }}
          }},
          timeGridDay: {{
            buttonText: "{btn_day}",
            dayHeaderFormat: {{ weekday: "short", day: "numeric", month: "short" }}
          }},
          listWeek: {{
            buttonText: "{btn_list}"
          }}
        }},

        allDayText: "{all_day_text}",
        moreLinkText: function(n) {{
          return "{more_template}".replace("{{n}}", n);
        }},

        titleFormat: {{ year: "numeric", month: "short", day: "numeric" }},
        dayHeaderFormat: {{ weekday: "short", day: "numeric" }},
        slotLabelFormat: {{ hour: "numeric", minute: "2-digit", meridiem: "short" }},

        windowResize: function() {{
          calendar.setOption("headerToolbar", isMobile() ? toolbarMobile : toolbarDesktop);
        }},

        slotMinTime: "06:00:00",
        slotMaxTime: "23:00:00",
        allDaySlot: false,
        events: events,

        eventClick: function(info) {{
          if (info.event.url) {{
            info.jsEvent.preventDefault();
            window.open(info.event.url, "_blank");
          }}
        }}
      }});

      calendar.render();
    </script>
    """

    components.html(html, height=height + 70, scrolling=True)

# =========================