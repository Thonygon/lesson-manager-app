# ============================================================
# CLASS MANAGER (Single-file Streamlit App)
# Dark HOME + Light APP + Sidebar "Menu" Expander Navigation
# ============================================================

# =========================
# 00) IMPORTS
# =========================
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta
from typing import List, Tuple, Optional
import math
import json
import streamlit.components.v1 as components

# =========================
# 01) PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Class Manager",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed",   # ✅ key fix
)

# =========================
# 02) THEMES (DARK HOME + LIGHT APP)
# =========================
def load_css_home_dark():
    st.markdown(
        """
        <style>
        :root{
          --bg:#0b1220;
          --text:#e5e7eb;
          --muted:rgba(229,231,235,0.72);
          --shadow:0 18px 44px rgba(0,0,0,0.45);
        }
        .stApp{
          background: radial-gradient(1200px 700px at 20% 0%, rgba(59,130,246,0.18), transparent 55%),
                      radial-gradient(1000px 600px at 85% 15%, rgba(16,185,129,0.14), transparent 55%),
                      var(--bg);
          color: var(--text);
        }
        section[data-testid="stMain"] > div {
          padding-top: 1.0rem;
          padding-bottom: 2.2rem;
          max-width: 1100px;
        }
        html, body, [class*="css"]{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }
        a { text-decoration: none; }

        .home-wrap{ margin-top: 1.6rem; display:flex; justify-content:center; }
        .home-card{
          width: min(820px, 94vw);
          border-radius: 28px;
          padding: 28px 22px 18px 22px;
          box-shadow: var(--shadow);
          background: rgba(255,255,255,0.035);
          border: 1px solid rgba(255,255,255,0.08);
          position: relative;
          overflow:hidden;
        }
        .home-glow{
          position:absolute; inset:-2px;
          background: radial-gradient(600px 260px at 10% 10%, rgba(59,130,246,0.20), transparent 55%),
                      radial-gradient(520px 240px at 90% 20%, rgba(16,185,129,0.14), transparent 60%);
          pointer-events:none;
        }
        .home-title{
          text-align:center;
          font-size: clamp(2.0rem, 3.6vw, 3.0rem);
          font-weight: 900;
          letter-spacing: -0.045em;
          margin: 0.6rem 0 0.35rem 0;
        }
        .home-sub{
          text-align:center;
          color: var(--muted);
          margin: 0 0 1.4rem 0;
          font-size: 0.98rem;
        }

        /* HOME pill links (reliable gradients) */
        .home-pill{
          display:block;
          width: 100%;
          border-radius: 999px;
          padding: 0.95rem 1.1rem;
          margin: 0.95rem 0;
          font-weight: 800;
          text-align: center;
          color: #ffffff !important;
          border: 1px solid rgba(255,255,255,0.16);
          box-shadow: 0 14px 30px rgba(0,0,0,0.35);
          transition: transform 160ms ease, filter 160ms ease;
        }
        .home-pill:hover{
          transform: translateY(-2px);
          filter: brightness(1.05);
        }

        .home-indicator{
          width: 92px; height: 7px; border-radius: 999px;
          background: rgba(255,255,255,0.22);
          margin: 1.55rem auto 0.4rem auto;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def load_css_app_light():
    st.markdown(
        """
        <style>
        :root{
          --bg:#f6f7fb;
          --panel:#ffffff;
          --border:rgba(17,24,39,0.08);
          --border2:rgba(17,24,39,0.10);
          --text:#0f172a;
          --muted:#475569;
          --shadow:0 10px 26px rgba(15,23,42,0.08);
          --shadow2:0 16px 42px rgba(15,23,42,0.10);
        }
        .stApp{
          background: var(--bg);
          color: var(--text);
        }
        section[data-testid="stMain"] > div {
  padding-top: 2.2rem;
  padding-bottom: 2.2rem;
  max-width: 1200px;
}

@media (max-width: 768px){
  section[data-testid="stMain"] > div {
    padding-top: 3.0rem; /* ✅ prevents the “cut” titles */
  }
}

        }
        html, body, [class*="css"]{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }
        h1,h2,h3{ letter-spacing:-0.02em; }
        .stCaption, .stMarkdown p { color: var(--muted); }

        /* Blocks */
        div[data-testid="stVerticalBlockBorderWrapper"]{
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 18px;
          padding: 18px;
          box-shadow: var(--shadow);
        }

        /* Buttons */
        div[data-testid="stButton"] button{
          border-radius: 14px !important;
          padding: 0.62rem 1.0rem !important;
          border: 1px solid var(--border2) !important;
          background: white !important;
          color: var(--text) !important;
          font-weight: 650 !important;
          transition: all 160ms ease;
        }
        div[data-testid="stButton"] button:hover{
          box-shadow: 0 0 0 4px rgba(59,130,246,0.12);
          border-color: rgba(59,130,246,0.35) !important;
          transform: translateY(-1px);
        }

        /* Inputs */
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input,
        div[data-testid="stSelectbox"] div{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
        }

        /* Dataframe */
        div[data-testid="stDataFrame"]{
          border-radius: 18px !important;
          overflow: hidden !important;
          border: 1px solid var(--border) !important;
          box-shadow: var(--shadow);
        }

        /* Metrics */
        div[data-testid="metric-container"]{
          background: white;
          border: 1px solid var(--border);
          padding: 14px 16px;
          border-radius: 18px;
          box-shadow: var(--shadow);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# =========================
# 03) NAVIGATION (QUERY PARAM ROUTER + SIDEBAR MENU)
# =========================
PAGES = [
    ("dashboard", "Dashboard", "linear-gradient(90deg,#3B82F6,#2563EB)"),
    ("students",  "Students",  "linear-gradient(90deg,#10B981,#059669)"),
    ("add_lesson","Lesson","linear-gradient(90deg,#F59E0B,#D97706)"),
    ("add_payment","Payment","linear-gradient(90deg,#EF4444,#DC2626)"),
    ("schedule",  "Schedule",  "linear-gradient(90deg,#8B5CF6,#7C3AED)"),
    ("calendar",  "Calendar",  "linear-gradient(90deg,#06B6D4,#0891B2)"),
    ("analytics", "Analytics", "linear-gradient(90deg,#F97316,#EA580C)"),
]
PAGE_KEYS = {"home"} | {k for k, _, _ in PAGES}

def _get_query_page() -> str:
    try:
        qp = st.query_params
        v = qp.get("page", "home")
        if isinstance(v, list):
            v = v[0] if v else "home"
        return str(v)
    except Exception:
        qp = st.experimental_get_query_params()
        v = qp.get("page", ["home"])
        return str(v[0]) if v else "home"

def _set_query_page(page: str) -> None:
    try:
        st.query_params["page"] = page
    except Exception:
        st.experimental_set_query_params(page=page)

if "page" not in st.session_state:
    st.session_state.page = "home"

qp_page = _get_query_page()
if qp_page in PAGE_KEYS:
    st.session_state.page = qp_page
else:
    st.session_state.page = "home"
    _set_query_page("home")

def go_to(page_name: str):
    if page_name not in PAGE_KEYS:
        page_name = "home"

    st.session_state.page = page_name
    _set_query_page(page_name)

    # ✅ force close sidebar immediately after navigation
    force_close_sidebar()

    st.session_state.menu_open = False
    st.session_state.page = page_name
    _set_query_page(page_name)

def render_sidebar_nav(active_page: str):
    items = [("home", "Home")] + [(k, label) for (k, label, _) in PAGES]

    with st.sidebar:
        st.markdown("### Menu")

        for k, label in items:
            if k == active_page:
                st.markdown(f"**👉 {label}**")
            else:
                if st.button(label, key=f"side_{k}", use_container_width=True):
                    go_to(k)
                    st.rerun()


def page_header(title: str):
    st.markdown(f"## {title}")

def force_close_sidebar():
    # Tries to click Streamlit’s collapse control if the sidebar is open.
    components.html(
        """
        <script>
        (function() {
          const tryClose = () => {
            // The collapse button exists when sidebar is open
            const collapseBtn =
              parent.document.querySelector('button[data-testid="collapsedControl"]') ||
              parent.document.querySelector('button[title="Close sidebar"]') ||
              parent.document.querySelector('button[aria-label="Close sidebar"]');

            // Some Streamlit versions: collapsedControl toggles sidebar
            if (collapseBtn) collapseBtn.click();
          };
          setTimeout(tryClose, 50);
          setTimeout(tryClose, 200);
          setTimeout(tryClose, 500);
        })();
        </script>
        """,
        height=0,
    )

# =========================
# 04) SUPABASE CONNECTION
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 05) DATA ACCESS HELPERS
# =========================
def load_table(name: str, limit: int = 10000, page_size: int = 1000) -> pd.DataFrame:
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
    student = str(student).strip()
    if not student:
        return
    try:
        supabase.table("students").insert({"student": student}).execute()
    except Exception:
        pass

def load_students() -> List[str]:
    students_df = load_table("students")
    classes_df = load_table("classes")
    payments_df = load_table("payments")

    names = set()
    for df, col in [(students_df, "student"), (classes_df, "student"), (payments_df, "student")]:
        if not df.empty and col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            names.update(df[col].dropna().tolist())

    return sorted([n for n in names if n and n.lower() != "nan"])

# =========================
# 06) CRUD HELPERS
# =========================
def add_class(student: str, number_of_lesson: int, lesson_date: str, modality: str, note: str = "") -> None:
    student = str(student).strip()
    ensure_student(student)
    supabase.table("classes").insert({
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,
        "modality": str(modality).strip(),
        "note": str(note).strip() if note else ""
    }).execute()

def add_payment(student: str, number_of_lesson: int, payment_date: str, paid_amount: float, modality: str) -> None:
    student = str(student).strip()
    ensure_student(student)
    supabase.table("payments").insert({
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "payment_date": payment_date,
        "paid_amount": float(paid_amount),
        "modality": str(modality).strip(),
    }).execute()

def delete_row(table_name: str, row_id: int) -> None:
    supabase.table(table_name).delete().eq("id", int(row_id)).execute()

def update_student_profile(student: str, email: str, zoom_link: str, notes: str, color: str) -> None:
    supabase.table("students").update({
        "email": email,
        "zoom_link": zoom_link,
        "notes": notes,
        "color": color
    }).eq("student", student).execute()

# =========================
# 07) SCHEDULE / OVERRIDES
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
    supabase.table("schedules").insert({
        "student": student,
        "weekday": int(weekday),
        "time": str(time_str).strip(),
        "duration_minutes": int(duration_minutes),
        "active": bool(active),
    }).execute()

def delete_schedule(schedule_id: int) -> None:
    supabase.table("schedules").delete().eq("id", int(schedule_id)).execute()

def load_overrides() -> pd.DataFrame:
    df = load_table("calendar_overrides")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "original_date", "new_datetime", "duration_minutes", "status", "note"])

    df["student"] = df["student"].astype(str).str.strip()
    df["original_date"] = pd.to_datetime(df["original_date"], errors="coerce")

    new_dt = pd.to_datetime(df["new_datetime"], errors="coerce", utc=True)
    df["new_datetime"] = new_dt.dt.tz_convert(None)

    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["status"] = df["status"].astype(str).str.strip()
    if "note" not in df.columns:
        df["note"] = ""
    df["note"] = df["note"].fillna("").astype(str)

    return df

# =========================
# 08) STUDENT META (COLOR / ZOOM / EMAIL)
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
    zoom_map  = dict(zip(s["student_norm"], s["zoom_link"]))
    email_map = dict(zip(s["student_norm"], s["email"]))
    return color_map, zoom_map, email_map

# =========================
# 09) DASHBOARD (PACKAGE STATUS)
# =========================
def rebuild_dashboard() -> pd.DataFrame:
    classes = load_table("classes")
    payments = load_table("payments")

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

    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")

    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)

    payments = payments.dropna(subset=["payment_date"])
    if payments.empty:
        return pd.DataFrame(columns=[
            "Student","Packages_Bought","Lessons_Paid_Total","Total_Paid","Payment_Date",
            "Package_Start_Date","Lessons_Taken","Lessons_Left","Status","Modality"
        ])

    packages_bought = (
        payments.groupby("student", as_index=False)
        .size()
        .rename(columns={"size": "Packages_Bought"})
    )

    payments_sorted = payments.sort_values(["student", "payment_date"]).copy()
    payments_sorted["Prev_Payment_Date"] = payments_sorted.groupby("student")["payment_date"].shift(1)

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

    classes_tmp = classes.sort_values(["student", "lesson_date"]).copy()
    classes_tmp = classes_tmp.merge(latest_payment[["student", "Prev_Payment_Date"]], on="student", how="left")

    mask = classes_tmp["Prev_Payment_Date"].isna() | (classes_tmp["lesson_date"] > classes_tmp["Prev_Payment_Date"])
    package_start = (
        classes_tmp[mask]
        .groupby("student", as_index=False)["lesson_date"]
        .min()
        .rename(columns={"lesson_date": "Package_Start_Date"})
    )

    package_start = package_start.merge(latest_payment[["student", "Payment_Date"]], on="student", how="right")
    package_start["Package_Start_Date"] = package_start["Package_Start_Date"].fillna(package_start["Payment_Date"])

    classes_for_count = classes.merge(package_start[["student", "Package_Start_Date"]], on="student", how="left")
    current = classes_for_count[
        classes_for_count["Package_Start_Date"].notna()
        & (classes_for_count["lesson_date"] >= classes_for_count["Package_Start_Date"])
    ]

    lessons_taken = (
        current.groupby("student", as_index=False)["number_of_lesson"]
        .sum()
        .rename(columns={"number_of_lesson": "Lessons_Taken"})
    )

    dash = (
        latest_payment
        .merge(packages_bought, on="student", how="left")
        .merge(package_start[["student","Package_Start_Date"]], on="student", how="left")
        .merge(lessons_taken, on="student", how="left")
    )

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

    classes_resp = supabase.table("classes").select("*").eq("student", student).limit(5000).execute()
    payments_resp = supabase.table("payments").select("*").eq("student", student).limit(5000).execute()

    classes = pd.DataFrame(classes_resp.data or [])
    payments = pd.DataFrame(payments_resp.data or [])

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

    lessons.index = range(1, len(lessons) + 1)
    pay.index = range(1, len(pay) + 1)
    return lessons, pay

# =========================
# 10) INCOME ANALYTICS
# =========================
def build_income_analytics():
    payments = load_table("payments")
    classes = load_table("classes")

    if payments.empty:
        payments = pd.DataFrame(columns=["student","payment_date","paid_amount","number_of_lesson","modality"])

    payments["student"] = payments.get("student", "").astype(str).str.strip()
    payments["payment_date"] = pd.to_datetime(payments.get("payment_date"), errors="coerce")
    payments["paid_amount"] = pd.to_numeric(payments.get("paid_amount"), errors="coerce").fillna(0.0)

    payments = payments.dropna(subset=["payment_date"])
    payments = payments[payments["student"].astype(str).str.len() > 0]

    payments["Month"] = payments["payment_date"].dt.to_period("M").astype(str)

    monthly_income = (
        payments.groupby("Month", as_index=False)["paid_amount"]
        .sum()
        .rename(columns={"paid_amount": "Income"})
        .sort_values("Month")
        .reset_index(drop=True)
    )

    by_student = (
        payments.groupby("student", as_index=False)
        .agg(
            Total_Paid=("paid_amount","sum"),
            Packages=("paid_amount","size"),
            Last_Payment=("payment_date","max"),
        )
        .rename(columns={"student":"Student"})
        .sort_values("Total_Paid", ascending=False)
        .reset_index(drop=True)
    )

    if classes.empty:
        classes = pd.DataFrame(columns=["student","lesson_date","number_of_lesson"])

    classes["student"] = classes.get("student", "").astype(str).str.strip()
    classes["lesson_date"] = pd.to_datetime(classes.get("lesson_date"), errors="coerce")
    classes["number_of_lesson"] = pd.to_numeric(classes.get("number_of_lesson"), errors="coerce").fillna(0).astype(int)

    today = pd.Timestamp.today().normalize()
    last_30 = today - pd.Timedelta(days=30)

    recent = classes.dropna(subset=["lesson_date"]).copy()
    recent = recent[recent["lesson_date"] >= last_30]

    lessons_30 = (
        recent.groupby("student", as_index=False)["number_of_lesson"]
        .sum()
        .rename(columns={"student":"Student", "number_of_lesson":"Lessons_Last_30D"})
    )

    by_student = by_student.merge(lessons_30, on="Student", how="left")
    by_student["Lessons_Last_30D"] = by_student["Lessons_Last_30D"].fillna(0).astype(int)
    by_student["Lessons_per_Week"] = (by_student["Lessons_Last_30D"] / 4.2857).round(2)

    income_all_time = float(payments["paid_amount"].sum()) if not payments.empty else 0.0
    this_month_key = str(today.to_period("M"))
    income_this_month = float(payments.loc[payments["Month"] == this_month_key, "paid_amount"].sum()) if not payments.empty else 0.0
    income_last_30 = float(payments.loc[payments["payment_date"] >= last_30, "paid_amount"].sum()) if not payments.empty else 0.0

    kpis = {
        "income_all_time": income_all_time,
        "income_this_month": income_this_month,
        "income_last_30": income_last_30,
    }

    return kpis, monthly_income, by_student

def money_fmt(x: float) -> str:
    try:
        return f"₺{x:,.0f}"
    except Exception:
        return str(x)

# =========================
# 11) FORECAST
# =========================
def build_forecast_table(payment_buffer_days: int = 0) -> pd.DataFrame:
    dash = rebuild_dashboard().copy()
    if dash.empty:
        return pd.DataFrame(columns=[
            "Student","Lessons_Left","Lessons_Per_Week",
            "Estimated_Finish_Date","Estimated_Next_Payment_Date"
        ])

    dash["Student"] = dash["Student"].astype(str).str.strip()
    dash["Lessons_Left"] = pd.to_numeric(dash["Lessons_Left"], errors="coerce").fillna(0).astype(int)

    today = pd.Timestamp(date.today())

    schedules = load_schedules()
    if schedules.empty:
        sched_rate = pd.DataFrame(columns=["Student","Lessons_Per_Week_Schedule"])
    else:
        s = schedules.copy()
        s["student"] = s["student"].astype(str).str.strip()
        s = s[s["active"] == True]
        sched_rate = (
            s.groupby("student", as_index=False)
             .size()
             .rename(columns={"student":"Student","size":"Lessons_Per_Week_Schedule"})
        )

    dash = dash.merge(sched_rate, on="Student", how="left")
    dash["Lessons_Per_Week_Schedule"] = pd.to_numeric(dash.get("Lessons_Per_Week_Schedule"), errors="coerce").fillna(0).astype(float)

    classes = load_table("classes")
    if classes.empty:
        hist_rate = pd.DataFrame(columns=["Student","Lessons_Per_Week_History"])
    else:
        c = classes.copy()
        c["student"] = c.get("student", "").astype(str).str.strip()
        c["lesson_date"] = pd.to_datetime(c.get("lesson_date"), errors="coerce")
        c = c.dropna(subset=["lesson_date"])
        if c.empty:
            hist_rate = pd.DataFrame(columns=["Student","Lessons_Per_Week_History"])
        else:
            c = c.sort_values(["student","lesson_date"]).groupby("student").tail(8)
            g = c.groupby("student")["lesson_date"].agg(["min","max","count"]).reset_index()
            span_days = (g["max"] - g["min"]).dt.days.clip(lower=1)
            g["Lessons_Per_Week_History"] = (g["count"] / (span_days / 7.0)).clip(lower=0.1)
            hist_rate = g.rename(columns={"student":"Student"})[["Student","Lessons_Per_Week_History"]]

    dash = dash.merge(hist_rate, on="Student", how="left")
    dash["Lessons_Per_Week_History"] = pd.to_numeric(dash.get("Lessons_Per_Week_History"), errors="coerce").fillna(0.0)

    dash["Lessons_Per_Week"] = dash["Lessons_Per_Week_Schedule"].where(
        dash["Lessons_Per_Week_Schedule"] > 0,
        dash["Lessons_Per_Week_History"]
    )
    dash["Lessons_Per_Week"] = dash["Lessons_Per_Week"].where(dash["Lessons_Per_Week"] > 0, 1.0)

    def _weeks_needed(left: int, per_week: float) -> int:
        if left <= 0:
            return 0
        return int(math.ceil(left / float(per_week)))

    dash["Weeks_Needed"] = dash.apply(lambda r: _weeks_needed(r["Lessons_Left"], r["Lessons_Per_Week"]), axis=1)
    dash["Estimated_Finish_Date"] = dash["Weeks_Needed"].apply(lambda w: today + pd.Timedelta(days=7*w))
    dash["Estimated_Next_Payment_Date"] = dash["Estimated_Finish_Date"] - pd.Timedelta(days=int(payment_buffer_days))
    dash.loc[dash["Estimated_Next_Payment_Date"] < today, "Estimated_Next_Payment_Date"] = today

    out = dash[[
        "Student","Lessons_Left","Lessons_Per_Week",
        "Estimated_Finish_Date","Estimated_Next_Payment_Date"
    ]].copy()

    out["Estimated_Finish_Date"] = pd.to_datetime(out["Estimated_Finish_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Estimated_Next_Payment_Date"] = pd.to_datetime(out["Estimated_Next_Payment_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return out.sort_values("Estimated_Next_Payment_Date").reset_index(drop=True)

# =========================
# 12) CALENDAR (EVENTS + RENDER)
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

def best_text_color(hex_color: str) -> str:
    try:
        c = hex_color.lstrip("#")
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        lum = (0.299*r + 0.587*g + 0.114*b)
        return "#0F172A" if lum > 160 else "#FFFFFF"
    except Exception:
        return "#0F172A"

def build_calendar_events(start_day: date, end_day: date) -> pd.DataFrame:
    schedules = load_schedules()
    overrides = load_overrides()
    color_map, zoom_map, _ = student_meta_maps()

    events = []
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
                events.append({
                    "DateTime": dt,
                    "Date": dt.date(),
                    "Student": student,
                    "Duration_Min": duration,
                    "Color": color_map.get(k, "#3B82F6"),
                    "Zoom_Link": zoom_map.get(k, ""),
                    "Source": "recurring"
                })
            cur += timedelta(days=1)

    events_df = pd.DataFrame(events)

    if not overrides.empty:
        for _, row in overrides.iterrows():
            student = str(row.get("student", "")).strip()
            k = norm_student(student)

            status = str(row.get("status", "")).strip()
            new_dt = row.get("new_datetime")
            original_date = row.get("original_date")
            duration = int(row.get("duration_minutes", 60))

            if pd.notna(original_date) and not events_df.empty:
                try:
                    od = original_date.date()
                    events_df = events_df[~((events_df["Student"] == student) & (events_df["Date"] == od))]
                except Exception:
                    pass

            if status == "scheduled" and pd.notna(new_dt):
                if start_day <= new_dt.date() <= end_day:
                    events_df = pd.concat([events_df, pd.DataFrame([{
                        "DateTime": new_dt,
                        "Date": new_dt.date(),
                        "Student": student,
                        "Duration_Min": duration,
                        "Color": color_map.get(k, "#3B82F6"),
                        "Zoom_Link": zoom_map.get(k, ""),
                        "Source": "override"
                    }])], ignore_index=True)

    if events_df.empty:
        return events_df

    events_df["DateTime"] = pd.to_datetime(events_df["DateTime"], errors="coerce").dt.tz_localize(None)
    events_df = events_df.sort_values("DateTime").reset_index(drop=True)
    events_df["Time"] = events_df["DateTime"].dt.strftime("%H:%M")
    events_df["Date"] = events_df["DateTime"].dt.strftime("%Y-%m-%d")
    return events_df

def render_fullcalendar(events: pd.DataFrame, height: int = 750):
    if events.empty:
        st.info("No events to show.")
        return

    df = events.copy()
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")
    df = df.dropna(subset=["DateTime"])

    df["end"] = df["DateTime"] + pd.to_timedelta(df["Duration_Min"].fillna(60).astype(int), unit="m")

    fc_events = []
    for _, r in df.iterrows():
        zoom = str(r.get("Zoom_Link", "") or "").strip()
        title = str(r.get("Student", "")).strip()
        color = str(r.get("Color", "#3B82F6")).strip()
        tc = best_text_color(color)

        fc_events.append({
            "title": title,
            "start": r["DateTime"].isoformat(),
            "end": r["end"].isoformat(),
            "backgroundColor": color,
            "borderColor": color,
            "textColor": tc,
            "url": zoom if zoom.startswith("http") else None,
        })

    payload = json.dumps(fc_events)

    html = f"""
    <div id="calendar" style="background:#ffffff;border:1px solid rgba(17,24,39,0.10);border-radius:16px;padding:10px;"></div>
    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js"></script>

    <style>
      .fc {{ color:#0f172a; }}
      .fc .fc-toolbar-title {{ color:#0f172a; font-weight:800; }}
      .fc .fc-button {{ border-radius:10px; border:1px solid rgba(17,24,39,0.14); background:#fff; color:#0f172a; }}
      .fc .fc-col-header-cell-cushion,
      .fc .fc-daygrid-day-number {{ color:#0f172a; }}
      .fc .fc-timegrid-slot-label-cushion {{ color:#334155; }}
    </style>

    <script>
      const events = {payload};
      const calendarEl = document.getElementById('calendar');

      const calendar = new FullCalendar.Calendar(calendarEl, {{
  initialView: 'timeGridWeek',
  height: {height},
  expandRows: true,
  nowIndicator: true,
  stickyHeaderDates: true,
  handleWindowResize: true,
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
    components.html(html, height=height + 70, scrolling=True)

# =========================
# 13) HOME SCREEN UI (DARK)
# =========================
def render_home():
    st.markdown(
        "<div class='home-wrap'><div class='home-card'><div class='home-glow'></div>",
        unsafe_allow_html=True
    )

    st.markdown("<div class='home-title'>CLASS MANAGER</div>", unsafe_allow_html=True)
    st.markdown("<div class='home-sub'>Choose where you want to go</div>", unsafe_allow_html=True)

    for key, label, grad in PAGES:
        st.markdown(
            f"""
            <a class="home-pill home-{key}"
               href="?page={key}"
               target="_self"
               rel="noopener noreferrer"
               style="background:{grad};">
              {label}
            </a>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div class='home-indicator'></div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# =========================
# 14) APP ENTRYPOINT (ROUTER + THEME SWITCH)
# =========================
page = st.session_state.page

if page != "home":
    force_close_sidebar()

if page == "home":
    load_css_home_dark()
else:
    load_css_app_light()

students = load_students()

if page == "home":
    render_home()
    st.stop()

# ✅ Sidebar nav on non-home pages
render_sidebar_nav(page)

# =========================
# 15) PAGE: DASHBOARD
# =========================
if page == "dashboard":
    page_header("Dashboard")
    st.subheader("Current Package Dashboard")
    dash = rebuild_dashboard()
    st.dataframe(dash, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Student History")

    if not students:
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

# =========================
# 16) PAGE: STUDENTS
# =========================
elif page == "students":
    page_header("Students")

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

    # ✅ DELETE STUDENT (must stay INSIDE students page)
    st.divider()
    st.markdown("### Delete Student")

    if not students:
        st.info("No students to delete.")
    else:
        del_student = st.selectbox("Select a student to delete", students, key="delete_student_select")
        confirm = st.checkbox(
            "I understand this removes the student profile (does not delete classes/payments history).",
            key="delete_student_confirm"
        )

        if st.button("Delete Student", type="primary", disabled=not confirm, key="btn_delete_student"):
            try:
                supabase.table("students").delete().eq("student", del_student).execute()
                st.success(f"Deleted student profile: {del_student}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not delete student.\n\n{e}")

# =========================
# 17) PAGE: ADD LESSON
# =========================
elif page == "add_lesson":
    page_header("Lessons")

    if not students:
        st.info("Add a student first in Students.")
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

# =========================
# 18) PAGE: ADD PAYMENT
# =========================
elif page == "add_payment":
    page_header("Payment")

    if not students:
        st.info("Add a student first in Students.")
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

# =========================
# 19) PAGE: SCHEDULE
# =========================
elif page == "schedule":
    page_header("Schedule")

    st.caption("Create each student's weekly program (0 = Monday, 6 = Sunday).")
    if not students:
        st.info("Add students first.")
    else:
        schedules = load_schedules()

        st.markdown("### Add a schedule slot")
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

        with c1:
            sch_student = st.selectbox("Student", students, key="sch_student")
        with c2:
            sch_weekday = st.selectbox("Weekday", list(range(7)), format_func=lambda x: f"{x} ({WEEKDAYS[x]})", key="sch_weekday")
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

# =========================
# 20) PAGE: CALENDAR
# =========================
elif page == "calendar":
    page_header("Calendar")

    st.caption("Generated from weekly schedules (app is the master).")
    view = st.radio("View", ["Today", "This Week", "This Month"], horizontal=True, key="calendar_view")
    today_d = date.today()

    if view == "Today":
        start_day = today_d
        end_day = today_d
    elif view == "This Week":
        start_day = today_d - timedelta(days=today_d.weekday())
        end_day = start_day + timedelta(days=6)
    else:
        start_day = date(today_d.year, today_d.month, 1)
        next_month = date(today_d.year + 1, 1, 1) if today_d.month == 12 else date(today_d.year, today_d.month + 1, 1)
        end_day = next_month - timedelta(days=1)

    events = build_calendar_events(start_day, end_day)

    if events.empty:
        st.info("No scheduled lessons in this range yet. Add them in Schedule.")
    else:
        students_list = sorted(events["Student"].unique().tolist())

        # ✅ default = ALL students (and auto-heal if list changes)
        if "calendar_filter_students" not in st.session_state:
            st.session_state.calendar_filter_students = students_list
        else:
            missing = [s for s in students_list if s not in st.session_state.calendar_filter_students]
            if missing:
                st.session_state.calendar_filter_students = students_list

        colA, colB = st.columns([3, 1])
        with colA:
            selected_students = st.multiselect(
                "Filter students",
                students_list,
                key="calendar_filter_students"
            )
        with colB:
            if st.button("Reset", use_container_width=True, key="calendar_reset"):
                st.session_state.calendar_filter_students = students_list
                st.rerun()

        filtered = events[events["Student"].isin(selected_students)].copy()
        render_fullcalendar(filtered, height=1050)

# =========================
# 21) PAGE: ANALYTICS
# =========================
elif page == "analytics":
    page_header("Analytics")
    st.info("Analytics page content goes here...")  # keep your analytics code here

else:
    go_to("home")
    st.rerun()
