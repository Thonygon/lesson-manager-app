import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional


st.set_page_config(page_title="Lesson Manager", layout="wide")

# ---- Supabase connection (Streamlit Secrets) ----
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# Helpers
# =========================
def load_table(name: str, limit: int = 10000, page_size: int = 1000) -> pd.DataFrame:
    """
    Loads in pages so a single huge request doesn't fail.
    Also gives a clear Streamlit error if Supabase returns HTML/500.
    """
    all_rows = []
    offset = 0

    try:
        while offset < limit:
            resp = (
                supabase.table(name)
                .select("*")
                .range(offset, min(offset + page_size - 1, limit - 1))
                .execute()
            )
            batch = resp.data or []
            all_rows.extend(batch)

            if len(batch) < page_size:
                break
            offset += page_size

        return pd.DataFrame(all_rows)

    except Exception as e:
        st.error(f"Supabase error loading table '{name}'.\n\n{e}")
        return pd.DataFrame()


def norm_student(x: str) -> str:
    return str(x).strip().casefold()

def ensure_student(student: str) -> None:
    """Insert student into students table; ignore if it already exists."""
    student = str(student).strip()
    if not student:
        return
    try:
        supabase.table("students").insert({"student": student}).execute()
    except Exception:
        pass

def load_students() -> List[str]:
    """Return sorted unique student names from students + classes + payments."""
    students_df = load_table("students")
    classes_df = load_table("classes")
    payments_df = load_table("payments")

    names = set()
    for df, col in [(students_df, "student"), (classes_df, "student"), (payments_df, "student")]:
        if not df.empty and col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            names.update(df[col].dropna().tolist())

    names = sorted([n for n in names if n and n.lower() != "nan"])
    return names

# =========================
# Write helpers
# =========================
def add_class(student: str, number_of_lesson: int, lesson_date: str, modality: str, note: str = "") -> None:
    student = str(student).strip()
    ensure_student(student)
    data = {
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,  # YYYY-MM-DD
        "modality": str(modality).strip(),
        "note": str(note).strip() if note else ""
    }
    supabase.table("classes").insert(data).execute()

def add_payment(student: str, number_of_lesson: int, payment_date: str, paid_amount: float, modality: str) -> None:
    student = str(student).strip()
    ensure_student(student)
    data = {
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "payment_date": payment_date,  # YYYY-MM-DD
        "paid_amount": float(paid_amount),
        "modality": str(modality).strip(),
    }
    supabase.table("payments").insert(data).execute()

def delete_row(table_name: str, row_id: int) -> None:
    supabase.table(table_name).delete().eq("id", int(row_id)).execute()

def update_student_profile(student: str, email: str, zoom_link: str, notes: str, color: str) -> None:
    supabase.table("students").update({
        "email": email,
        "zoom_link": zoom_link,
        "notes": notes,
        "color": color
    }).eq("student", student).execute()

def add_override(
    student: str,
    original_date: Optional[date],
    new_datetime: datetime,
    duration_minutes: int,
    status: str,
    note: str = ""
) -> None:
    data = {
        "student": student,
        "original_date": original_date.isoformat() if original_date else None,
        "new_datetime": new_datetime.isoformat(),
        "duration_minutes": int(duration_minutes),
        "status": status,
        "note": str(note).strip() if note else ""
    }
    supabase.table("calendar_overrides").insert(data).execute()

# =========================
# Schedule helpers
# =========================
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def load_schedules() -> pd.DataFrame:
    df = load_table("schedules")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "weekday", "time", "duration_minutes", "active"])

    df["student"] = df["student"].astype(str).str.strip()
    df["weekday"] = pd.to_numeric(df["weekday"], errors="coerce").fillna(0).astype(int)
    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["active"] = df["active"].fillna(True).astype(bool)
    df["time"] = df["time"].astype(str).str.strip()

    return df

def add_schedule(student: str, weekday: int, time_str: str, duration_minutes: int, active: bool = True) -> None:
    student = str(student).strip()
    ensure_student(student)
    data = {
        "student": student,
        "weekday": int(weekday),              # 0=Mon ... 6=Sun
        "time": str(time_str).strip(),        # "HH:MM"
        "duration_minutes": int(duration_minutes),
        "active": bool(active),
    }
    supabase.table("schedules").insert(data).execute()

def delete_schedule(schedule_id: int) -> None:
    supabase.table("schedules").delete().eq("id", int(schedule_id)).execute()

def load_overrides() -> pd.DataFrame:
    df = load_table("calendar_overrides")
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "student", "original_date",
            "new_datetime", "duration_minutes", "status", "note"
        ])

    df["student"] = df["student"].astype(str).str.strip()
    df["original_date"] = pd.to_datetime(df["original_date"], errors="coerce")

    new_dt = pd.to_datetime(df["new_datetime"], errors="coerce", utc=True)
    df["new_datetime"] = new_dt.dt.tz_convert(None)  # tz-naive

    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["status"] = df["status"].astype(str).str.strip()
    if "note" not in df.columns:
        df["note"] = ""
    df["note"] = df["note"].fillna("").astype(str)

    return df

# =========================
# Student meta helpers
# =========================
def load_students_df() -> pd.DataFrame:
    df = load_table("students")
    if df.empty:
        return pd.DataFrame(columns=["student", "email", "zoom_link", "notes", "color"])

    df["student"] = df["student"].astype(str).str.strip()

    if "color" not in df.columns:
        df["color"] = "#3B82F6"
    df["color"] = df["color"].fillna("#3B82F6").astype(str).str.strip()

    if "zoom_link" not in df.columns:
        df["zoom_link"] = ""
    df["zoom_link"] = df["zoom_link"].fillna("").astype(str).str.strip()

    if "email" not in df.columns:
        df["email"] = ""
    df["email"] = df["email"].fillna("").astype(str).str.strip()

    if "notes" not in df.columns:
        df["notes"] = ""
    df["notes"] = df["notes"].fillna("").astype(str)

    return df

def student_meta_maps():
    s = load_students_df()
    if s.empty:
        return {}, {}, {}

    s["student_norm"] = s["student"].apply(norm_student)

    color_map = dict(zip(s["student_norm"], s["color"]))
    zoom_map = dict(zip(s["student_norm"], s["zoom_link"]))
    email_map = dict(zip(s["student_norm"], s["email"]))

    return color_map, zoom_map, email_map

# =========================
# Calendar event generation
# =========================
def _parse_time_value(x) -> Tuple[int, int]:
    """
    Supabase may return time as 'HH:MM:SS' or 'HH:MM'.
    Returns (hour, minute). Falls back to 0:00 if invalid.
    """
    if x is None:
        return (0, 0)
    s = str(x).strip()
    if not s:
        return (0, 0)
    parts = s.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return (h, m)
    except Exception:
        return (0, 0)

def build_calendar_events(start_day: date, end_day: date) -> pd.DataFrame:
    schedules = load_schedules()
    overrides = load_overrides()
    color_map, zoom_map, _ = student_meta_maps()

    events = []

    # 1) Generate recurring events from schedules
    if not schedules.empty:
        schedules_active = schedules[schedules["active"] == True].copy()

        cur = start_day
        while cur <= end_day:
            wd = cur.weekday()
            day_slots = schedules_active[schedules_active["weekday"] == wd]

            for _, row in day_slots.iterrows():
                h, m = _parse_time_value(row.get("time"))
                dt = datetime(cur.year, cur.month, cur.day, h, m)

                student = str(row.get("student", "")).strip()
                k = norm_student(student)

                duration = int(row.get("duration_minutes", 60))
                color = color_map.get(k, "#3B82F6")
                zoom = zoom_map.get(k, "")

                events.append({
                    "DateTime": dt,
                    "Date": dt.date(),
                    "Student": student,
                    "Duration_Min": duration,
                    "Color": color,
                    "Zoom_Link": zoom,
                    "Source": "recurring"
                })

            cur += timedelta(days=1)

    events_df = pd.DataFrame(events)

    # 2) Apply overrides
    if not overrides.empty:
        for _, row in overrides.iterrows():
            student = str(row.get("student", "")).strip()
            k = norm_student(student)

            status = str(row.get("status", "")).strip()
            new_dt = row.get("new_datetime")
            original_date = row.get("original_date")
            duration = int(row.get("duration_minutes", 60))

            # Remove original recurring event if original_date specified
            if pd.notna(original_date) and not events_df.empty:
                try:
                    od = original_date.date()
                    events_df = events_df[
                        ~(
                            (events_df["Student"] == student) &
                            (events_df["Date"] == od)
                        )
                    ]
                except Exception:
                    pass

            # Add rescheduled / extra event
            if status == "scheduled" and pd.notna(new_dt):
                if start_day <= new_dt.date() <= end_day:
                    add_row = pd.DataFrame([{
                        "DateTime": new_dt,
                        "Date": new_dt.date(),
                        "Student": student,
                        "Duration_Min": duration,
                        "Color": color_map.get(k, "#3B82F6"),
                        "Zoom_Link": zoom_map.get(k, ""),
                        "Source": "override"
                    }])
                    events_df = pd.concat([events_df, add_row], ignore_index=True)

    if events_df.empty:
        return events_df

    # Normalize datetime
    events_df["DateTime"] = pd.to_datetime(events_df["DateTime"], errors="coerce")
    events_df["DateTime"] = events_df["DateTime"].dt.tz_localize(None)

    events_df = events_df.sort_values("DateTime").reset_index(drop=True)
    events_df["Time"] = events_df["DateTime"].dt.strftime("%H:%M")
    events_df["Date"] = events_df["DateTime"].dt.strftime("%Y-%m-%d")

    return events_df

# =========================
# Analytics (Dashboard)
# =========================
def rebuild_dashboard() -> pd.DataFrame:
    classes = load_table("classes")
    payments = load_table("payments")

    # Guarantee required columns exist
    if classes.empty:
        classes = pd.DataFrame(columns=["student","number_of_lesson","lesson_date","modality","note"])
    else:
        for c in ["student","number_of_lesson","lesson_date","modality","note"]:
            if c not in classes.columns:
                classes[c] = None

    if payments.empty:
        payments = pd.DataFrame(columns=["student","number_of_lesson","payment_date","paid_amount","modality"])
    else:
        for c in ["student","number_of_lesson","payment_date","paid_amount","modality"]:
            if c not in payments.columns:
                payments[c] = None

    # Clean types
    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")

    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)

    payments = payments.dropna(subset=["payment_date"])

    if payments.empty:
        # No payments -> empty dashboard
        return pd.DataFrame(columns=[
            "Student","Packages_Bought","Lessons_Paid_Total","Total_Paid","Payment_Date",
            "Package_Start_Date","Lessons_Taken","Lessons_Left","Status","Modality"
        ])

    # Packages bought = count of payment rows per student
    packages_bought = (
        payments.groupby("student", as_index=False)
        .size()
        .rename(columns={"size": "Packages_Bought"})
    )

    # Sort payments and compute previous payment date
    payments_sorted = payments.sort_values(["student", "payment_date"]).copy()
    payments_sorted["Prev_Payment_Date"] = payments_sorted.groupby("student")["payment_date"].shift(1)

    # Latest payment = current package
    latest_payment = (
        payments_sorted.groupby("student", as_index=False)
        .tail(1)
        .rename(columns={
            "number_of_lesson": "Lessons_Paid_Total",
            "paid_amount": "Total_Paid",
            "payment_date": "Payment_Date",
            "modality": "Modality"
        })[["student","Lessons_Paid_Total","Total_Paid","Payment_Date","Modality","Prev_Payment_Date"]]
    )

    # Package starts at first lesson AFTER previous payment (or first lesson ever)
    classes_tmp = classes.sort_values(["student", "lesson_date"]).copy()
    classes_tmp = classes_tmp.merge(
        latest_payment[["student", "Prev_Payment_Date"]],
        on="student",
        how="left"
    )

    mask = classes_tmp["Prev_Payment_Date"].isna() | (classes_tmp["lesson_date"] > classes_tmp["Prev_Payment_Date"])
    package_start = (
        classes_tmp[mask]
        .groupby("student", as_index=False)["lesson_date"]
        .min()
        .rename(columns={"lesson_date": "Package_Start_Date"})
    )

    # If no lessons after prev payment, fallback to Payment_Date
    package_start = package_start.merge(
        latest_payment[["student", "Payment_Date"]],
        on="student",
        how="right"
    )
    package_start["Package_Start_Date"] = package_start["Package_Start_Date"].fillna(package_start["Payment_Date"])

    # Lessons taken since Package_Start_Date
    classes_for_count = classes.merge(
        package_start[["student", "Package_Start_Date"]],
        on="student",
        how="left"
    )

    current = classes_for_count[
        classes_for_count["Package_Start_Date"].notna()
        & (classes_for_count["lesson_date"] >= classes_for_count["Package_Start_Date"])
    ]

    lessons_taken = (
        current.groupby("student", as_index=False)["number_of_lesson"]
        .sum()
        .rename(columns={"number_of_lesson": "Lessons_Taken"})
    )

    dash = (latest_payment
            .merge(packages_bought, on="student", how="left")
            .merge(package_start[["student","Package_Start_Date"]], on="student", how="left")
            .merge(lessons_taken, on="student", how="left"))

    dash["Packages_Bought"] = dash["Packages_Bought"].fillna(0).astype(int)
    dash["Lessons_Taken"] = dash["Lessons_Taken"].fillna(0).astype(int)
    dash["Lessons_Left"] = (dash["Lessons_Paid_Total"] - dash["Lessons_Taken"]).astype(int)

    def status(x: int) -> str:
        if x <= 0:
            return "Finished"
        if x <= 3:
            return "Almost Finished"
        return "Active"

    dash["Status"] = dash["Lessons_Left"].apply(status)

    dash = dash.sort_values("Lessons_Left").reset_index(drop=True)
    dash = dash.rename(columns={"student": "Student"})
    dash["Payment_Date"] = pd.to_datetime(dash["Payment_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Start_Date"] = pd.to_datetime(dash["Package_Start_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return dash[[
        "Student","Packages_Bought","Lessons_Paid_Total","Total_Paid","Payment_Date",
        "Package_Start_Date","Lessons_Taken","Lessons_Left","Status","Modality"
    ]]

def show_student_history(student: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    student = str(student).strip()

    classes_resp = (
        supabase.table("classes")
        .select("*")
        .eq("student", student)
        .limit(5000)
        .execute()
    )
    payments_resp = (
        supabase.table("payments")
        .select("*")
        .eq("student", student)
        .limit(5000)
        .execute()
    )

    classes = pd.DataFrame(classes_resp.data or [])
    payments = pd.DataFrame(payments_resp.data or [])

    # ---- Lessons ----
    if classes.empty:
        lessons = pd.DataFrame(columns=["ID","Lesson_Date","Number_of_Lesson","Modality","Note"])
    else:
        for c in ["id","lesson_date","number_of_lesson","modality","note"]:
            if c not in classes.columns:
                classes[c] = None

        classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
        classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)

        lessons = classes.sort_values("lesson_date", ascending=False).copy()
        lessons["lesson_date"] = lessons["lesson_date"].dt.strftime("%Y-%m-%d")

        lessons = lessons.rename(columns={
            "id": "ID",
            "lesson_date": "Lesson_Date",
            "number_of_lesson": "Number_of_Lesson",
            "modality": "Modality",
            "note": "Note"
        })[["ID","Lesson_Date","Number_of_Lesson","Modality","Note"]]

    # ---- Payments ----
    if payments.empty:
        pay = pd.DataFrame(columns=["ID","Payment_Date","Lessons_Paid","Paid_Amount","Modality"])
    else:
        for c in ["id","payment_date","number_of_lesson","paid_amount","modality"]:
            if c not in payments.columns:
                payments[c] = None

        payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
        payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
        payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)

        pay = payments.sort_values("payment_date", ascending=False).copy()
        pay["payment_date"] = pay["payment_date"].dt.strftime("%Y-%m-%d")

        pay = pay.rename(columns={
            "id": "ID",
            "payment_date": "Payment_Date",
            "number_of_lesson": "Lessons_Paid",
            "paid_amount": "Paid_Amount",
            "modality": "Modality"
        })[["ID","Payment_Date","Lessons_Paid","Paid_Amount","Modality"]]

    # Visual row numbering
    lessons.index = range(1, len(lessons) + 1)
    pay.index = range(1, len(pay) + 1)

    return lessons, pay
import json
import streamlit.components.v1 as components

def render_fullcalendar(events: pd.DataFrame, height: int = 750):
    if events.empty:
        st.info("No events to show.")
        return

    df = events.copy()
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")
    df = df.dropna(subset=["DateTime"])

    df["end"] = df["DateTime"] + pd.to_timedelta(
        df["Duration_Min"].fillna(60).astype(int),
        unit="m"
    )

    fc_events = []
    for _, r in df.iterrows():
        zoom = str(r.get("Zoom_Link", "") or "").strip()
        title = str(r.get("Student", "")).strip()

        fc_events.append({
            "title": title,
            "start": r["DateTime"].isoformat(),
            "end": r["end"].isoformat(),
            "backgroundColor": str(r.get("Color", "#3B82F6")),
            "borderColor": str(r.get("Color", "#3B82F6")),
            "textColor": "#ffffff",
            "url": zoom if zoom.startswith("http") else None,
        })

    payload = json.dumps(fc_events)

    html = f"""
    <div id="calendar"></div>

    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js"></script>

    <script>
      const events = {payload};

      const calendarEl = document.getElementById('calendar');
      const calendar = new FullCalendar.Calendar(calendarEl, {{
        initialView: 'timeGridWeek',
        height: {height},
        nowIndicator: true,
        firstDay: 1,
        headerToolbar: {{
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
        }},
        slotMinTime: '06:00:00',
        slotMaxTime: '23:00:00',
        allDaySlot: false,
        events: events,
        eventClick: function(info) {{
          if (info.event.url) {{
            info.jsEvent.preventDefault();
            window.open(info.event.url, '_blank');
          }}
        }}
      }});

      calendar.render();
    </script>
    """

    components.html(html, height=height + 50, scrolling=True)

# =========================
# UI
# =========================
st.title("Lesson Manager")

students = load_students()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Dashboard", "Students", "Add Lesson", "Add Payment", "Schedule", "Calendar"]
)

# ---- Dashboard ----
with tab1:
    st.subheader("Current Package Dashboard")
    dash = rebuild_dashboard()
    st.dataframe(dash, use_container_width=True)

    st.divider()
    st.subheader("Student History")

    if len(students) == 0:
        st.info("No students found yet.")
    else:
        selected = st.selectbox("Select a student", students, key="history_student")
        lessons_df, payments_df = show_student_history(selected)

        colA, colB = st.columns(2)
        with colA:
            st.markdown("### Lessons")
            st.dataframe(lessons_df, use_container_width=True)

            st.markdown("#### Delete a lesson record (by ID)")
            lesson_id = st.number_input("Lesson ID to delete", min_value=0, step=1, key="del_lesson_id")
            if st.button("Delete Lesson", key="btn_delete_lesson"):
                delete_row("classes", lesson_id)
                st.success("Lesson deleted ✅")
                st.rerun()

        with colB:
            st.markdown("### Payments")
            st.dataframe(payments_df, use_container_width=True)

            st.markdown("#### Delete a payment record (by ID)")
            payment_id = st.number_input("Payment ID to delete", min_value=0, step=1, key="del_payment_id")
            if st.button("Delete Payment", key="btn_delete_payment"):
                delete_row("payments", payment_id)
                st.success("Payment deleted ✅")
                st.rerun()

# ---- Students ----
with tab2:
    st.subheader("Students")
    st.caption("Manage student profiles, contact info and calendar color.")

    students_df = load_students_df()

    st.markdown("### Add New Student")
    new_student = st.text_input("New student name", key="new_student_name")
    if st.button("Add Student", key="btn_add_student"):
        if not new_student.strip():
            st.error("Please enter a student name.")
        else:
            ensure_student(new_student)
            st.success("Student added ✅")
            st.rerun()

    st.divider()

    if students_df.empty:
        st.info("No students yet.")
    else:
        st.markdown("### Edit Student Profile")

        student_list = sorted(students_df["student"].unique().tolist())
        selected_student = st.selectbox("Select student", student_list, key="edit_student_select")

        student_row = students_df[students_df["student"] == selected_student].iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("Email", value=student_row.get("email", ""), key="student_email")
            zoom_link = st.text_input("Zoom Link", value=student_row.get("zoom_link", ""), key="student_zoom")
        with col2:
            color = st.color_picker("Calendar Color", value=student_row.get("color", "#3B82F6"), key="student_color")
            notes = st.text_area("Notes", value=student_row.get("notes", ""), key="student_notes")

        if st.button("Save Changes", key="btn_save_student_profile"):
            update_student_profile(selected_student, email, zoom_link, notes, color)
            st.success("Student updated ✅")
            st.rerun()

    st.divider()
    st.markdown("### Current student list")
    st.write(sorted(students))

# ---- Add Lesson ----
with tab3:
    st.subheader("Add a Lesson")
    if len(students) == 0:
        st.info("Add a student first in the Students tab.")
    else:
        student = st.selectbox("Student", students, key="lesson_student")
        number = st.number_input("Number of lessons", min_value=1, max_value=10, value=1, step=1, key="lesson_number")
        lesson_date = st.date_input("Lesson date", key="lesson_date")
        modality = st.selectbox("Modality", ["Online", "Offline"], key="lesson_modality")
        note = st.text_input("Note (optional)", key="lesson_note")

        if st.button("Save Lesson", key="btn_save_lesson"):
            add_class(student, number, lesson_date.isoformat(), modality, note)
            st.success("Lesson saved ✅")
            st.rerun()

# ---- Add Payment ----
with tab4:
    st.subheader("Add a Payment (New Package)")
    if len(students) == 0:
        st.info("Add a student first in the Students tab.")
    else:
        student_p = st.selectbox("Student", students, key="pay_student")
        lessons_paid = st.number_input("Lessons paid", min_value=1, max_value=500, value=44, step=1, key="pay_lessons_paid")
        payment_date = st.date_input("Payment date", key="pay_date")
        paid_amount = st.number_input("Paid amount", min_value=0.0, value=0.0, step=100.0, key="pay_amount")
        modality_p = st.selectbox("Modality", ["Online", "Offline"], key="pay_modality")

        if st.button("Save Payment", key="btn_save_payment"):
            add_payment(student_p, lessons_paid, payment_date.isoformat(), paid_amount, modality_p)
            st.success("Payment saved ✅")
            st.rerun()

# ---- Schedule ----
with tab5:
    st.subheader("Weekly Schedule")
    st.caption("Create each student's weekly program (0 = Monday, 6 = Sunday).")

    if len(students) == 0:
        st.info("Add students first.")
    else:
        schedules = load_schedules()

        st.markdown("### Add a schedule slot")
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

        with c1:
            sch_student = st.selectbox("Student", students, key="sch_student")
        with c2:
            sch_weekday = st.selectbox(
                "Weekday", list(range(7)),
                format_func=lambda x: f"{x} ({WEEKDAYS[x]})",
                key="sch_weekday"
            )
        with c3:
            sch_time = st.text_input("Time (HH:MM)", value="10:00", key="sch_time")
        with c4:
            sch_duration = st.number_input("Duration (min)", min_value=15, max_value=360, value=60, step=15, key="sch_duration")
        with c5:
            sch_active = st.checkbox("Active", value=True, key="sch_active")

        if st.button("Add Schedule Slot", key="btn_add_schedule"):
            add_schedule(sch_student, sch_weekday, sch_time, sch_duration, sch_active)
            st.success("Schedule slot added ✅")
            st.rerun()

        st.divider()
        st.markdown("### Current schedule (all students)")

        if schedules.empty:
            st.info("No schedule slots yet.")
        else:
            show = schedules.copy()
            show["weekday"] = show["weekday"].apply(lambda x: f"{int(x)} ({WEEKDAYS[int(x)]})")
            show = show.rename(columns={
                "id": "ID",
                "student": "Student",
                "weekday": "Weekday",
                "time": "Time",
                "duration_minutes": "Duration_Minutes",
                "active": "Active"
            })[["ID", "Student", "Weekday", "Time", "Duration_Minutes", "Active"]].sort_values(["Student", "Weekday", "Time"])

            show.index = range(1, len(show) + 1)
            st.dataframe(show, use_container_width=True)

            st.markdown("#### Delete schedule slot (by ID)")
            del_id = st.number_input("Schedule ID to delete", min_value=0, step=1, key="del_schedule_id")
            if st.button("Delete Schedule", key="btn_delete_schedule"):
                delete_schedule(del_id)
                st.success("Schedule deleted ✅")
                st.rerun()

# ---- Calendar ----
with tab6:
    st.subheader("Calendar")
    st.caption("Generated from your weekly schedules (app is the master).")

    view = st.radio(
        "View",
        ["Today", "This Week", "This Month"],
        horizontal=True,
        key="calendar_view"
    )

    today = date.today()

    if view == "Today":
        start_day = today
        end_day = today

    elif view == "This Week":
        start_day = today - timedelta(days=today.weekday())
        end_day = start_day + timedelta(days=6)

    else:
        start_day = date(today.year, today.month, 1)
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        end_day = next_month - timedelta(days=1)

    events = build_calendar_events(start_day, end_day)

    if events.empty:
        st.info("No scheduled lessons in this range yet. Add them in the Schedule tab.")
    else:
        if "Zoom_Link" not in events.columns:
            events["Zoom_Link"] = ""

        students_list = sorted(events["Student"].unique().tolist())
        selected_students = st.multiselect(
            "Filter students",
            students_list,
            default=students_list,
            key="calendar_filter_students"
        )
        events = events[events["Student"].isin(selected_students)].copy()

        # ✅ Show REAL calendar grid
        render_fullcalendar(events, height=780)

        # Build display table
        display = events.copy()

        # Make sure Color exists and is valid-ish
        if "Color" not in display.columns:
            display["Color"] = "#3B82F6"
        display["Color"] = display["Color"].fillna("#3B82F6").astype(str).str.strip()

        # Color square ONLY (no hex text)
        display["Color"] = display["Color"].apply(
            lambda c: f"<span title='{c}' style='display:inline-block;width:16px;height:16px;background:{c};"
                      f"border-radius:4px;border:1px solid #999;'></span>"
        )

        # Zoom clickable label instead of URL
        # (leave blank if no link)
        display["Zoom"] = display["Zoom_Link"].fillna("").astype(str).apply(
            lambda z: f"<a href='{z}' target='_blank'>Zoom</a>" if z.strip().startswith("http") else ""
        )

        display = display.rename(columns={"Duration_Min": "Duration (min)"})[
            ["Date", "Time", "Student", "Duration (min)", "Color", "Zoom"]
        ]

        # Render as HTML so Color square + Zoom link work
        st.markdown(
            display.to_html(escape=False, index=False),
            unsafe_allow_html=True
        )

        st.divider()
        st.markdown("### Quick list (easy scanning)")
        for _, row in events.iterrows():
            zoom = row.get("Zoom_Link", "")
            zoom_part = f" — [Zoom]({zoom})" if isinstance(zoom, str) and zoom.strip().startswith("http") else ""
            st.markdown(
                f"- **{row['Date']} {row['Time']}** — "
                f"<span style='color:{row['Color']}; font-weight:700'>■</span> "
                f"**{row['Student']}** ({row['Duration_Min']} min){zoom_part}",
                unsafe_allow_html=True
            )

    st.divider()
    st.markdown("### Reschedule / Cancel a Lesson")

    if students:
        selected_student = st.selectbox("Student", students, key="override_student")

        is_extra = st.checkbox(
            "This is an extra lesson (no original date)",
            value=False,
            key="override_is_extra"
        )

        if is_extra:
            original_date = None
            st.caption("Extra lesson: no original recurring lesson will be removed.")
        else:
            original_date = st.date_input("Original lesson date", key="override_original_date")

        new_date = st.date_input("New date", key="override_new_date")
        new_time = st.text_input("New time (HH:MM)", value="10:00", key="override_new_time")

        duration = st.number_input(
            "Duration (min)",
            min_value=15,
            max_value=360,
            value=60,
            step=15,
            key="override_duration"
        )
        action = st.selectbox("Action", ["scheduled", "cancelled"], key="override_action")
        note = st.text_input("Note (optional)", key="override_note")

        if st.button("Apply Override", key="btn_apply_override"):
            h, m = _parse_time_value(new_time)
            new_dt = datetime(new_date.year, new_date.month, new_date.day, h, m)

            add_override(
                selected_student,
                original_date,
                new_dt,
                duration,
                action,
                note
            )

            st.success("Override applied ✅")
            st.rerun()
