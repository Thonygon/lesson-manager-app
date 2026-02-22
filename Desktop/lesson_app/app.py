# ============================================================
# CLASS MANAGER (Single-file Streamlit App)
# Dark HOME + Light APP + Sidebar Navigation
# + Bilingual UI (EN/ES)
# + Bilingual payments (English/Spanish/English,Spanish)
# + Lesson language (auto + manual when both)
# + Bulk edit payments + bulk edit lessons
# + Analytics upgrades (This Year bubble, flexible Month/Year, Language & Modality charts)
# + Forecast fixed (behavior-based + active-only incl. finished last 3 months)
# + Calendar overrides UI (reschedule/cancel/notes)
# + KPI bubbles fixed via components.html (no more code text)
# ============================================================

# =========================
# 00) IMPORTS
# =========================
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, date, timedelta, timezone
from typing import List, Tuple, Optional, Dict
import math
import json
import re
import urllib.parse
import streamlit.components.v1 as components

# =========================
# 01) PAGE CONFIG
# =========================
st.set_page_config(
    page_title="Class Manager",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
# 02) I18N (EN/ES)
# =========================
I18N: Dict[str, Dict[str, str]] = {
    "en": {
        "menu": "Menu",
        "home": "Home",
        "dashboard": "Dashboard",
        "students": "Students",
        "lesson": "Lesson",
        "payment": "Payment",
        "schedule": "Schedule",
        "calendar": "Calendar",
        "analytics": "Analytics",
        "language_ui": "Language",
        "english": "English",
        "spanish": "Spanish",
        "both": "English + Spanish",

        "add": "Add",
        "save": "Save",
        "delete": "Delete",
        "reset": "Reset",
        "view": "View",
        "today": "Today",
        "this_week": "This Week",
        "this_month": "This Month",

        "filter_students": "Filter students",
        "search": "Search",
        "select_student": "Select a student",

        "no_data": "No data yet.",
        "no_students": "No students found yet.",
        "no_events": "No events to show.",

        "compact_mode": "Compact mode (mobile friendly)",

        "status_overview": "Status overview",
        "action_finish_soon": "Finish soon",

        "active": "Active",
        "finished": "Finished",
        "mismatch": "Mismatch",

        "open_whatsapp": "Open WhatsApp with message",
        "whatsapp_message": "WhatsApp message",

        "current_students": "Current students",
        "mismatches": "Mismatches",

        "student_profile": "Edit Student Profile",
        "student_history": "Student History",
        "delete_student": "Delete Student",
        "delete_student_warning": "Removes the student profile only (does not delete classes/payments history).",
        "confirm_delete_student": "I understand this removes the student profile (does not delete classes/payments history).",

        "calendar_color": "Calendar Color",
        "whatsapp_phone": "WhatsApp phone (flexible format)",
        "examples_phone": "Examples: +90 555 123 4567 | 0555 123 45 67 | 905551234567 | +1 212 555 0199",
        "zoom_link": "Zoom Link",
        "email": "Email",
        "notes": "Notes",

        "add_students": "Add Students",
        "new_student_name": "New student name",
        "see_all_students": "See All Students",
        "current_student_list": "Current student list",

        "add_lesson_title": "Add and manage your lessons.",
        "add_payment_title": "Add and manage your payments (packages).",
        "create_weekly_program": "Create your students weekly program.",
        "see_timetable": "See and manage your timetable.",

        "lesson_language": "Lesson language",
        "package_languages": "Package languages",
        "modality": "Modality",
        "online": "Online",
        "offline": "Offline",

        "paid_amount": "Paid amount",
        "lessons_paid": "Lessons paid",
        "payment_date": "Payment date",
        "package_dates": "Package dates",
        "package_start": "Package start date",
        "package_expiry": "Package expiry date",
        "close_package": "Close this package (expiry date)",
        "starts_different": "Package starts on a different date",

        "advanced_optional": "Advanced (optional)",
        "adjust_units": "Lesson adjustment units",
        "normalized_flag": "Mark package as normalized",
        "normalized_note": "Normalization note",

        "payments_editor": "Edit payments (bulk)",
        "lessons_editor": "Edit lessons (bulk)",
        "apply_changes": "Apply changes",
        "warning_apply": "Make sure IDs are correct. Changes overwrite the database.",

        "income_analytics": "Income Analytics",
        "forecast": "Forecast",
        "payment_buffer": "Payment reminder buffer",
        "on_finish": "On finish date",
        "days_before": "days before finish",

        "this_week_income": "This week",
        "this_month_income": "This month",
        "this_year_income": "This year",
        "all_time_income": "All time",

        "group_by": "Group by",
        "monthly": "Monthly",
        "yearly": "Yearly",

        "income_table": "Income table",
        "sold_by_language": "Sold by language (payments)",
        "sold_by_modality": "Sold by modality (payments)",
        "teaching_by_language": "Lessons by language (classes)",
        "teaching_by_modality": "Lessons by modality (classes)",
        "top_students": "Top profitable students",

        "done_ok": "Done ✅",
        "normalize": "Normalize",
        "normalize_failed": "Normalize failed.",
        "normalized_default_note": "Normalized mismatch (dashboard)",

        "calendar_overrides": "Calendar overrides",
        "override_add": "Add / reschedule an override",
        "override_list": "Current overrides",
        "override_student": "Student",
        "override_original_date": "Original date",
        "override_new_datetime": "New date & time",
        "override_duration": "Duration (min)",
        "override_status": "Status",
        "override_note": "Note",
        "override_add_btn": "Save override",
        "override_delete_btn": "Delete override",
        "override_cancel": "cancelled",
        "override_scheduled": "scheduled",
    },
    "es": {
        "menu": "Menú",
        "home": "Inicio",
        "dashboard": "Panel",
        "students": "Estudiantes",
        "lesson": "Clase",
        "payment": "Pago",
        "schedule": "Horario",
        "calendar": "Calendario",
        "analytics": "Analítica",
        "language_ui": "Idioma",
        "english": "Inglés",
        "spanish": "Español",
        "both": "Inglés + Español",

        "add": "Añadir",
        "save": "Guardar",
        "delete": "Eliminar",
        "reset": "Reiniciar",
        "view": "Vista",
        "today": "Hoy",
        "this_week": "Esta semana",
        "this_month": "Este mes",

        "filter_students": "Filtrar estudiantes",
        "search": "Buscar",
        "select_student": "Selecciona un estudiante",

        "no_data": "Aún no hay datos.",
        "no_students": "Aún no hay estudiantes.",
        "no_events": "No hay eventos para mostrar.",

        "compact_mode": "Modo compacto (móvil)",

        "status_overview": "Resumen de estado",
        "action_finish_soon": "Por terminar",

        "active": "Activo",
        "finished": "Finalizado",
        "mismatch": "Descuadre",

        "open_whatsapp": "Abrir WhatsApp con mensaje",
        "whatsapp_message": "Mensaje de WhatsApp",

        "current_students": "Estudiantes actuales",
        "mismatches": "Descuadres",

        "student_profile": "Editar perfil del estudiante",
        "student_history": "Historial del estudiante",
        "delete_student": "Eliminar estudiante",
        "delete_student_warning": "Elimina solo el perfil (no borra historial de clases/pagos).",
        "confirm_delete_student": "Entiendo que esto elimina solo el perfil (no borra historial de clases/pagos).",

        "calendar_color": "Color del calendario",
        "whatsapp_phone": "Teléfono WhatsApp (formato flexible)",
        "examples_phone": "Ejemplos: +90 555 123 4567 | 0555 123 45 67 | 905551234567 | +1 212 555 0199",
        "zoom_link": "Link Zoom",
        "email": "Email",
        "notes": "Notas",

        "add_students": "Añadir estudiantes",
        "new_student_name": "Nombre del estudiante",
        "see_all_students": "Ver estudiantes",
        "current_student_list": "Lista actual",

        "add_lesson_title": "Añade y gestiona tus clases.",
        "add_payment_title": "Añade y gestiona tus pagos (paquetes).",
        "create_weekly_program": "Crea el horario semanal.",
        "see_timetable": "Ver y gestionar tu calendario.",

        "lesson_language": "Idioma de la clase",
        "package_languages": "Idiomas del paquete",
        "modality": "Modalidad",
        "online": "Online",
        "offline": "Presencial",

        "paid_amount": "Monto pagado",
        "lessons_paid": "Clases pagadas",
        "payment_date": "Fecha de pago",
        "package_dates": "Fechas del paquete",
        "package_start": "Inicio del paquete",
        "package_expiry": "Fin del paquete",
        "close_package": "Cerrar paquete (fecha fin)",
        "starts_different": "El paquete inicia en otra fecha",

        "advanced_optional": "Avanzado (opcional)",
        "adjust_units": "Unidades de ajuste",
        "normalized_flag": "Marcar paquete como normalizado",
        "normalized_note": "Nota de normalización",

        "payments_editor": "Editar pagos (masivo)",
        "lessons_editor": "Editar clases (masivo)",
        "apply_changes": "Aplicar cambios",
        "warning_apply": "Verifica los IDs. Los cambios sobrescriben la base de datos.",

        "income_analytics": "Analítica de ingresos",
        "forecast": "Pronóstico",
        "payment_buffer": "Recordatorio de pago",
        "on_finish": "En la fecha de finalización",
        "days_before": "días antes de finalizar",

        "this_week_income": "Esta semana",
        "this_month_income": "Este mes",
        "this_year_income": "Este año",
        "all_time_income": "Histórico",

        "group_by": "Agrupar por",
        "monthly": "Mensual",
        "yearly": "Anual",

        "income_table": "Tabla de ingresos",
        "sold_by_language": "Vendido por idioma (pagos)",
        "sold_by_modality": "Vendido por modalidad (pagos)",
        "teaching_by_language": "Clases por idioma (clases)",
        "teaching_by_modality": "Clases por modalidad (clases)",
        "top_students": "Top estudiantes más rentables",

        "done_ok": "Hecho ✅",
        "normalize": "Normalizar",
        "normalize_failed": "Error al normalizar.",
        "normalized_default_note": "Descuadre normalizado (panel)",

        "calendar_overrides": "Ajustes del calendario",
        "override_add": "Añadir / reprogramar un ajuste",
        "override_list": "Ajustes actuales",
        "override_student": "Estudiante",
        "override_original_date": "Fecha original",
        "override_new_datetime": "Nueva fecha y hora",
        "override_duration": "Duración (min)",
        "override_status": "Estado",
        "override_note": "Nota",
        "override_add_btn": "Guardar ajuste",
        "override_delete_btn": "Eliminar ajuste",
        "override_cancel": "cancelado",
        "override_scheduled": "programado",
    }
}

# Keep ui_lang consistent: only "en" or "es"
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"

def t(key: str) -> str:
    lang = st.session_state.get("ui_lang", "en")
    return I18N.get(lang, I18N["en"]).get(key, key)

# =========================
# 03) THEMES (DARK HOME + LIGHT APP + COMPACT)
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
          color: rgba(229,231,235,0.72);
          margin: 0 0 1.4rem 0;
          font-size: 0.98rem;
        }

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

def load_css_app_light(compact: bool = False):
    compact_css = """
      section[data-testid="stMain"] > div { padding-top: 1.4rem !important; padding-bottom: 1.4rem !important; }
      div[data-testid="stVerticalBlockBorderWrapper"]{ padding: 12px !important; border-radius: 16px !important; }
      div[data-testid="stButton"] button{ padding: 0.58rem 0.85rem !important; border-radius: 14px !important; }
      div[data-testid="metric-container"]{ padding: 12px 14px !important; border-radius: 16px !important; }
    """ if compact else ""

    st.markdown(
        f"""
        <style>
        :root{{
          --bg:#f6f7fb;
          --panel:#ffffff;
          --border:rgba(17,24,39,0.08);
          --border2:rgba(17,24,39,0.10);
          --text:#0f172a;
          --muted:#475569;
          --shadow:0 10px 26px rgba(15,23,42,0.08);
        }}

        .stApp{{ background: var(--bg); color: var(--text); }}

        section[data-testid="stMain"] > div {{
          padding-top: 2.2rem;
          padding-bottom: 2.2rem;
          max-width: 1200px;
        }}

        @media (max-width: 768px){{
          section[data-testid="stMain"] > div {{ padding-top: 1.6rem; padding-bottom: 1.6rem; }}
        }}

        html, body, [class*="css"]{{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
        h1,h2,h3{{ letter-spacing:-0.02em; }}
        .stCaption, .stMarkdown p {{ color: var(--muted); }}

        div[data-testid="stVerticalBlockBorderWrapper"]{{
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: 18px;
          padding: 18px;
          box-shadow: var(--shadow);
        }}

        div[data-testid="stButton"] button{{
          border-radius: 14px !important;
          padding: 0.62rem 1.0rem !important;
          border: 1px solid var(--border2) !important;
          background: white !important;
          color: var(--text) !important;
          font-weight: 650 !important;
          transition: all 160ms ease;
        }}
        div[data-testid="stButton"] button:hover{{
          box-shadow: 0 0 0 4px rgba(59,130,246,0.12);
          border-color: rgba(59,130,246,0.35) !important;
          transform: translateY(-1px);
        }}

        label[data-testid="stWidgetLabel"]{{ background: transparent !important; border: 0 !important; padding: 0 !important; margin-bottom: .25rem !important; border-radius: 0 !important; }}
        label[data-testid="stWidgetLabel"] > div{{ background: transparent !important; border: 0 !important; padding: 0 !important; border-radius: 0 !important; }}

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input{{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
        }}

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div{{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
        }}

        div[data-testid="stDataFrame"]{{
          border-radius: 18px !important;
          overflow: hidden !important;
          border: 1px solid var(--border) !important;
          box-shadow: var(--shadow);
        }}

        div[data-testid="metric-container"]{{
          background: white;
          border: 1px solid var(--border);
          padding: 14px 16px;
          border-radius: 18px;
          box-shadow: var(--shadow);
        }}

        {compact_css}
        </style>
        """,
        unsafe_allow_html=True
    )

# =========================
# 04) NAVIGATION (QUERY PARAM ROUTER + SIDEBAR)
# =========================
PAGES = [
    ("dashboard", "dashboard", "linear-gradient(90deg,#3B82F6,#2563EB)"),
    ("students",  "students",  "linear-gradient(90deg,#10B981,#059669)"),
    ("add_lesson","lesson",    "linear-gradient(90deg,#F59E0B,#D97706)"),
    ("add_payment","payment",  "linear-gradient(90deg,#EF4444,#DC2626)"),
    ("schedule",  "schedule",  "linear-gradient(90deg,#8B5CF6,#7C3AED)"),
    ("calendar",  "calendar",  "linear-gradient(90deg,#06B6D4,#0891B2)"),
    ("analytics", "analytics", "linear-gradient(90deg,#F97316,#EA580C)"),
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

def force_close_sidebar():
    components.html(
        """
        <script>
        (function() {
          const tryClose = () => {
            const collapseBtn =
              parent.document.querySelector('button[data-testid="collapsedControl"]') ||
              parent.document.querySelector('button[title="Close sidebar"]') ||
              parent.document.querySelector('button[aria-label="Close sidebar"]');
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

def go_to(page_name: str):
    if page_name not in PAGE_KEYS:
        page_name = "home"
    st.session_state.page = page_name
    _set_query_page(page_name)
    force_close_sidebar()
    st.session_state.menu_open = False

def render_sidebar_nav(active_page: str):
    items = [("home", t("home"))] + [(k, t(label_key)) for (k, label_key, _) in PAGES]
    with st.sidebar:
        st.markdown(f"### {t('menu')}")
        st.radio(
            t("language_ui"),
            options=["en", "es"],
            format_func=lambda x: "English" if x == "en" else "Español",
            horizontal=True,
            key="ui_lang",
        )
        st.checkbox(
            t("compact_mode"),
            value=st.session_state.get("compact_mode", False),
            key="compact_mode"
        )

        st.divider()
        for k, label in items:
            if k == active_page:
                st.markdown(f"**👉 {label}**")
            else:
                if st.button(label, key=f"side_{k}", use_container_width=True):
                    go_to(k)
                    st.rerun()

def page_header(title: str):
    st.markdown(f"## {title}")

# =========================
# 05) SUPABASE CONNECTION
# =========================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 06) DATA ACCESS HELPERS
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
# 06.5) LANGUAGE HELPERS
# =========================
LANG_EN = "English"
LANG_ES = "Spanish"
LANG_BOTH = "English,Spanish"
ALLOWED_LANGS = {LANG_EN, LANG_ES, LANG_BOTH}

# Default package languages: Spanish (your preference)
DEFAULT_PACKAGE_LANGS = [LANG_ES]

def pack_languages(selected: List[str]) -> str:
    s = [x for x in selected if x in (LANG_EN, LANG_ES)]
    s = sorted(set(s), key=lambda z: 0 if z == LANG_EN else 1)
    if len(s) == 2:
        return LANG_BOTH
    if len(s) == 1:
        return s[0]
    return LANG_ES  # default to Spanish

def unpack_languages(value: str) -> List[str]:
    v = str(value or "").strip()
    if v == LANG_BOTH:
        return [LANG_EN, LANG_ES]
    if v in (LANG_EN, LANG_ES):
        return [v]
    return [LANG_ES]  # default to Spanish

def allowed_lesson_language_from_package(languages_value: str) -> Tuple[List[str], Optional[str]]:
    langs = unpack_languages(languages_value)
    if len(langs) == 1:
        return langs, langs[0]
    return [LANG_EN, LANG_ES], None

# =========================
# 06.6) WHATSAPP HELPERS
# =========================
def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", str(s or ""))

def normalize_phone_for_whatsapp(raw_phone: str) -> str:
    d = _digits_only(raw_phone)
    if not d:
        return ""
    if d.startswith("00") and len(d) > 2:
        d = d[2:]
    if len(d) >= 11 and not d.startswith("0"):
        return d
    if len(d) == 11 and d.startswith("0") and d[1] == "5":
        return "90" + d[1:]
    if len(d) == 10 and d.startswith("5"):
        return "90" + d
    return ""

def build_whatsapp_url(message: str, raw_phone: str = "") -> str:
    encoded = urllib.parse.quote(message or "")
    phone = normalize_phone_for_whatsapp(raw_phone)
    if phone:
        return f"https://wa.me/{phone}?text={encoded}"
    return f"https://wa.me/?text={encoded}"

# =========================
# 07) CRUD HELPERS (CLASSES / PAYMENTS)
# =========================
def add_class(
    student: str,
    number_of_lesson: int,
    lesson_date: str,
    modality: str,
    note: str = "",
    lesson_language: Optional[str] = None
) -> None:
    student = str(student).strip()
    ensure_student(student)
    payload = {
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "lesson_date": lesson_date,
        "modality": str(modality).strip(),
        "note": str(note).strip() if note else "",
        "lesson_language": str(lesson_language).strip() if lesson_language else None,
    }
    try:
        supabase.table("classes").insert(payload).execute()
    except Exception:
        payload.pop("lesson_language", None)
        supabase.table("classes").insert(payload).execute()

def add_payment(
    student: str,
    number_of_lesson: int,
    payment_date: str,
    paid_amount: float,
    modality: str,
    languages: str,
    package_start_date: Optional[str] = None,
    package_expiry_date: Optional[str] = None,
    lesson_adjustment_units: int = 0,
    package_normalized: bool = False,
    normalized_note: str = ""
) -> None:
    student = str(student).strip()
    ensure_student(student)

    if not package_start_date:
        package_start_date = payment_date

    payload = {
        "student": student,
        "number_of_lesson": int(number_of_lesson),
        "payment_date": payment_date,
        "paid_amount": float(paid_amount),
        "modality": str(modality).strip(),
        "languages": str(languages).strip() if languages else LANG_ES,
        "package_start_date": package_start_date,
        "package_expiry_date": package_expiry_date if package_expiry_date else None,
        "lesson_adjustment_units": int(lesson_adjustment_units),
        "package_normalized": bool(package_normalized),
        "normalized_note": str(normalized_note or "").strip(),
        "normalized_at": datetime.now(timezone.utc).isoformat() if (package_normalized or normalized_note) else None,
    }

    try:
        supabase.table("payments").insert(payload).execute()
    except Exception:
        payload.pop("languages", None)
        payload.pop("lesson_adjustment_units", None)
        payload.pop("package_normalized", None)
        payload.pop("normalized_note", None)
        payload.pop("normalized_at", None)
        supabase.table("payments").insert(payload).execute()

def delete_row(table_name: str, row_id: int) -> None:
    supabase.table(table_name).delete().eq("id", int(row_id)).execute()

def normalize_latest_package(student: str, payment_id: int, note: str = "") -> bool:
    try:
        payload = {
            "package_normalized": True,
            "normalized_note": str(note or "").strip(),
            "normalized_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("payments").update(payload).eq("id", int(payment_id)).execute()
        return True
    except Exception:
        return False

def update_student_profile(student: str, email: str, zoom_link: str, notes: str, color: str, phone: str) -> None:
    supabase.table("students").update({
        "email": email,
        "zoom_link": zoom_link,
        "notes": notes,
        "color": color,
        "phone": phone
    }).eq("student", student).execute()

def update_payment_row(payment_id: int, updates: dict) -> bool:
    try:
        supabase.table("payments").update(updates).eq("id", int(payment_id)).execute()
        return True
    except Exception:
        return False

def update_class_row(class_id: int, updates: dict) -> bool:
    try:
        supabase.table("classes").update(updates).eq("id", int(class_id)).execute()
        return True
    except Exception:
        return False

# =========================
# 07.5) PACKAGE/LANGUAGE LOOKUPS
# =========================
def latest_payment_languages_for_student(student: str) -> str:
    try:
        resp = (
            supabase.table("payments")
            .select("id, payment_date, package_start_date, languages")
            .eq("student", str(student).strip())
            .order("payment_date", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return LANG_ES
        v = rows[0].get("languages") or LANG_ES
        v = str(v).strip()
        return v if v in ALLOWED_LANGS else LANG_ES
    except Exception:
        return LANG_ES

def _is_offline(modality: str) -> bool:
    m = str(modality or "").strip().casefold()
    return ("offline" in m) or ("face" in m) or ("yüz" in m) or ("yuzyuze" in m) or ("yüzyüze" in m)

def _units_multiplier(modality: str) -> int:
    return 2 if _is_offline(modality) else 1

def _is_free_note(note: str) -> bool:
    n = str(note or "").upper()
    return ("[FREE]" in n) or ("[DEMO]" in n) or ("[DONT COUNT]" in n) or ("[DON'T COUNT]" in n)

# =========================
# 08) HISTORY HELPERS
# =========================
def show_student_history(student: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    student = str(student).strip()

    classes = load_table("classes")
    payments = load_table("payments")

    if classes.empty:
        classes = pd.DataFrame(columns=["id", "student", "number_of_lesson", "lesson_date", "modality", "note", "lesson_language"])
    if payments.empty:
        payments = pd.DataFrame(columns=[
            "id","student","number_of_lesson","payment_date","paid_amount","modality","languages",
            "package_start_date","package_expiry_date",
            "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
        ])

    for col in ["id","student","number_of_lesson","lesson_date","modality","note","lesson_language"]:
        if col not in classes.columns:
            classes[col] = None
    for col in [
        "id","student","number_of_lesson","payment_date","paid_amount","modality","languages",
        "package_start_date","package_expiry_date",
        "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
    ]:
        if col not in payments.columns:
            payments[col] = None

    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    lessons_df = classes[classes["student"] == student].copy()
    payments_df = payments[payments["student"] == student].copy()

    lessons_df["lesson_date"] = pd.to_datetime(lessons_df["lesson_date"], errors="coerce")
    payments_df["payment_date"] = pd.to_datetime(payments_df["payment_date"], errors="coerce")
    payments_df["package_start_date"] = pd.to_datetime(payments_df["package_start_date"], errors="coerce")
    payments_df["package_expiry_date"] = pd.to_datetime(payments_df["package_expiry_date"], errors="coerce")

    lessons_df["number_of_lesson"] = pd.to_numeric(lessons_df["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments_df["number_of_lesson"] = pd.to_numeric(payments_df["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments_df["paid_amount"] = pd.to_numeric(payments_df["paid_amount"], errors="coerce").fillna(0.0)

    lessons_df = lessons_df.sort_values(["lesson_date","id"], ascending=[False, False]).reset_index(drop=True)
    payments_df = payments_df.sort_values(["payment_date","id"], ascending=[False, False]).reset_index(drop=True)

    lessons_df = lessons_df.rename(columns={
        "id":"Lesson_ID",
        "number_of_lesson":"Lessons",
        "lesson_date":"Lesson_Date",
        "modality":"Modality",
        "note":"Note",
        "lesson_language":"Lesson_Language",
    })[["Lesson_ID","Lesson_Date","Lessons","Modality","Lesson_Language","Note"]]

    payments_df = payments_df.rename(columns={
        "id":"Payment_ID",
        "number_of_lesson":"Lessons_Paid",
        "payment_date":"Payment_Date",
        "paid_amount":"Paid_Amount",
        "modality":"Modality",
        "languages":"Languages",
        "package_start_date":"Package_Start_Date",
        "package_expiry_date":"Package_Expiry_Date",
        "lesson_adjustment_units":"Adjustment_Units",
        "package_normalized":"Package_Normalized",
        "normalized_note":"Normalized_Note",
        "normalized_at":"Normalized_At",
    })[[
        "Payment_ID","Payment_Date","Lessons_Paid","Paid_Amount","Modality","Languages",
        "Package_Start_Date","Package_Expiry_Date",
        "Adjustment_Units","Package_Normalized","Normalized_Note","Normalized_At"
    ]]

    lessons_df["Lesson_Date"] = pd.to_datetime(lessons_df["Lesson_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["Payment_Date"] = pd.to_datetime(payments_df["Payment_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["Package_Start_Date"] = pd.to_datetime(payments_df["Package_Start_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["Package_Expiry_Date"] = pd.to_datetime(payments_df["Package_Expiry_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return lessons_df, payments_df

# =========================
# 09) SCHEDULE / OVERRIDES
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

def _to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        # treat naive as local time; store as UTC by attaching local offset? Simplest:
        # attach UTC (consistent with your previous behavior)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def add_override(
    student: str,
    original_date: date,
    new_dt: datetime,
    duration_minutes: int = 60,
    status: str = "scheduled",
    note: str = ""
) -> None:
    student = str(student).strip()
    ensure_student(student)
    payload = {
        "student": student,
        "original_date": original_date.isoformat(),
        "new_datetime": _to_utc_iso(new_dt),
        "duration_minutes": int(duration_minutes),
        "status": str(status).strip(),
        "note": str(note or "").strip(),
    }
    supabase.table("calendar_overrides").insert(payload).execute()

def update_override(
    override_id: int,
    new_dt: datetime,
    duration_minutes: int = 60,
    status: str = "scheduled",
    note: str = ""
) -> None:
    payload = {
        "new_datetime": _to_utc_iso(new_dt),
        "duration_minutes": int(duration_minutes),
        "status": str(status).strip(),
        "note": str(note or "").strip(),
    }
    supabase.table("calendar_overrides").update(payload).eq("id", int(override_id)).execute()

def delete_override(override_id: int) -> None:
    supabase.table("calendar_overrides").delete().eq("id", int(override_id)).execute()

# =========================
# 10) STUDENT META
# =========================
def load_students_df() -> pd.DataFrame:
    df = load_table("students")
    if df.empty:
        return pd.DataFrame(columns=["student", "email", "zoom_link", "notes", "color", "phone"])

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

    if "phone" not in df.columns:
        df["phone"] = ""
    df["phone"] = df["phone"].fillna("").astype(str).str.strip()

    return df

def student_meta_maps():
    s = load_students_df()
    if s.empty:
        return {}, {}, {}, {}
    s["student_norm"] = s["student"].apply(norm_student)
    color_map = dict(zip(s["student_norm"], s["color"]))
    zoom_map  = dict(zip(s["student_norm"], s["zoom_link"]))
    email_map = dict(zip(s["student_norm"], s["email"]))
    phone_map = dict(zip(s["student_norm"], s["phone"]))
    return color_map, zoom_map, email_map, phone_map

# =========================
# 11) DASHBOARD (PACKAGE STATUS)
# =========================
def rebuild_dashboard(
    active_window_days: int = 183,
    expiry_days: int = 365,
    grace_days: int = 0
) -> pd.DataFrame:
    classes = load_table("classes")
    payments = load_table("payments")

    if classes.empty:
        classes = pd.DataFrame(columns=["id","student","number_of_lesson","lesson_date","modality","note","lesson_language"])
    else:
        for c in ["id","student","number_of_lesson","lesson_date","modality","note","lesson_language"]:
            if c not in classes.columns:
                classes[c] = None

    if payments.empty:
        payments = pd.DataFrame(columns=[
            "id","student","number_of_lesson","payment_date","paid_amount","modality","languages",
            "package_start_date","package_expiry_date",
            "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
        ])
    else:
        for c in [
            "id","student","number_of_lesson","payment_date","paid_amount","modality","languages",
            "package_start_date","package_expiry_date",
            "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
        ]:
            if c not in payments.columns:
                payments[c] = None

    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce")
    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
    payments["package_start_date"] = pd.to_datetime(payments["package_start_date"], errors="coerce")
    payments["package_expiry_date"] = pd.to_datetime(payments["package_expiry_date"], errors="coerce")

    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)

    payments["lesson_adjustment_units"] = pd.to_numeric(payments["lesson_adjustment_units"], errors="coerce").fillna(0).astype(int)
    payments["package_normalized"] = payments["package_normalized"].fillna(False).astype(bool)

    if "note" not in classes.columns:
        classes["note"] = ""
    classes["note"] = classes["note"].fillna("").astype(str)

    payments = payments.dropna(subset=["payment_date"])
    if payments.empty:
        return pd.DataFrame(columns=[
            "Student","Packages_Bought","Lessons_Paid_Total","Total_Paid","Payment_Date",
            "Package_Start_Date","Package_Expiry_Date",
            "Lessons_Taken_Units","Lessons_Left_Units","Overused_Units",
            "Status","Modality","Last_Lesson_Date","Is_Active_6m",
            "Payment_ID","Normalize_Allowed","Languages"
        ])

    today = pd.Timestamp(date.today())
    active_cutoff = today - pd.Timedelta(days=int(active_window_days))
    expiry_cutoff = today - pd.Timedelta(days=int(expiry_days))
    _ = grace_days  # compatibility

    payments["pkg_start"] = payments["package_start_date"].fillna(payments["payment_date"])
    p = payments.sort_values(["student", "pkg_start", "payment_date", "id"]).copy()
    p["next_pkg_start"] = p.groupby("student")["pkg_start"].shift(-1)
    latest = p.groupby("student", as_index=False).tail(1).copy()

    packages_bought = (
        p.groupby("student", as_index=False)
         .size()
         .rename(columns={"size":"Packages_Bought"})
    )

    last_lesson = (
        classes.dropna(subset=["lesson_date"])
              .groupby("student", as_index=False)["lesson_date"]
              .max()
              .rename(columns={"lesson_date":"Last_Lesson_Date"})
    )

    cls = classes.dropna(subset=["lesson_date"]).copy()
    cls = cls[cls["student"].astype(str).str.len() > 0]

    cls = cls.merge(
        latest[[
            "student","id","pkg_start","package_expiry_date","next_pkg_start",
            "modality","number_of_lesson","lesson_adjustment_units","package_normalized","payment_date","paid_amount","languages"
        ]].rename(columns={
            "id":"Payment_ID",
            "number_of_lesson":"Lessons_Paid_Total",
            "paid_amount":"Total_Paid",
            "payment_date":"Payment_Date",
            "modality":"Modality",
            "languages":"Languages"
        }),
        on="student",
        how="inner"
    )

    def _window_end(row) -> pd.Timestamp:
        ends = [today]
        if pd.notna(row.get("package_expiry_date")):
            ends.append(pd.to_datetime(row["package_expiry_date"]))
        if pd.notna(row.get("next_pkg_start")):
            ends.append(pd.to_datetime(row["next_pkg_start"]))
        return min(ends)

    latest["window_end"] = latest.apply(_window_end, axis=1)
    cls = cls.merge(latest[["student","window_end"]], on="student", how="left")

    cls = cls[
        (cls["lesson_date"] >= cls["pkg_start"]) &
        (cls["lesson_date"] < cls["window_end"])
    ].copy()

    cls["units_row"] = cls.apply(
        lambda r: 0 if _is_free_note(r.get("note",""))
        else int(r.get("number_of_lesson", 0)) * _units_multiplier(r.get("modality","")),
        axis=1
    )

    taken_units = (
        cls.groupby("student", as_index=False)["units_row"]
           .sum()
           .rename(columns={"units_row":"Lessons_Taken_Units"})
    )

    dash = latest.rename(columns={
        "student":"Student",
        "id":"Payment_ID",
        "number_of_lesson":"Lessons_Paid_Total",
        "paid_amount":"Total_Paid",
        "payment_date":"Payment_Date",
        "modality":"Modality",
        "package_expiry_date":"Package_Expiry_Date",
        "languages":"Languages",
    }).copy()

    dash["Package_Start_Date"] = dash["pkg_start"]

    dash = (
        dash.merge(packages_bought, left_on="Student", right_on="student", how="left")
            .drop(columns=["student"], errors="ignore")
            .merge(taken_units, left_on="Student", right_on="student", how="left")
            .drop(columns=["student"], errors="ignore")
            .merge(last_lesson, left_on="Student", right_on="student", how="left")
            .drop(columns=["student"], errors="ignore")
    )

    dash["Packages_Bought"] = dash["Packages_Bought"].fillna(0).astype(int)
    dash["Lessons_Taken_Units"] = pd.to_numeric(dash["Lessons_Taken_Units"], errors="coerce").fillna(0).astype(int)

    dash["Purchased_Units"] = dash.apply(
        lambda r: int(r["Lessons_Paid_Total"]) * _units_multiplier(r.get("Modality","")),
        axis=1
    )
    dash["Adjustment_Units"] = pd.to_numeric(dash.get("lesson_adjustment_units"), errors="coerce").fillna(0).astype(int)
    dash["Effective_Purchased_Units"] = dash["Purchased_Units"] + dash["Adjustment_Units"]

    dash["Raw_Left_Units"] = dash["Effective_Purchased_Units"] - dash["Lessons_Taken_Units"]
    dash["Overused_Units"] = dash["Raw_Left_Units"].apply(lambda x: abs(int(x)) if int(x) < 0 else 0)
    dash["Lessons_Left_Units"] = dash["Raw_Left_Units"].clip(lower=0).astype(int)

    dash["Last_Lesson_Date"] = pd.to_datetime(dash["Last_Lesson_Date"], errors="coerce")
    dash["Payment_Date_dt"] = pd.to_datetime(dash["Payment_Date"], errors="coerce")

    dash["Has_Recent_Lesson"] = dash["Last_Lesson_Date"].notna() & (dash["Last_Lesson_Date"] >= active_cutoff)
    dash["Has_Recent_Payment"] = dash["Payment_Date_dt"].notna() & (dash["Payment_Date_dt"] >= active_cutoff)
    dash["Is_Active_6m"] = dash["Has_Recent_Lesson"] | dash["Has_Recent_Payment"]

    dash["Package_Expiry_Date"] = pd.to_datetime(dash["Package_Expiry_Date"], errors="coerce")
    dash["Closed_By_Expiry"] = dash["Package_Expiry_Date"].notna() & (dash["Package_Expiry_Date"] <= today)
    dash["Closed_By_Old_Payment"] = dash["Payment_Date_dt"].notna() & (dash["Payment_Date_dt"] <= expiry_cutoff)

    dash["Is_Dropout"] = (~dash["Is_Active_6m"]) & (~dash["Closed_By_Expiry"])
    dash.loc[dash["Closed_By_Expiry"] | dash["Closed_By_Old_Payment"] | dash["Is_Dropout"], "Lessons_Left_Units"] = 0

    def _status(r) -> str:
        if bool(r.get("Is_Dropout")):
            return "Dropout"
        if bool(r.get("Closed_By_Expiry")) or bool(r.get("Closed_By_Old_Payment")):
            return "Finished"
        if int(r.get("Overused_Units", 0)) > 0 and bool(r.get("Is_Active_6m")) and (not bool(r.get("package_normalized", False))):
            return "Mismatch"
        left = int(r.get("Lessons_Left_Units", 0))
        if left <= 0:
            return "Finished"
        if left <= 3:
            return "Almost Finished"
        return "Active"

    dash["Status"] = dash.apply(_status, axis=1)

    dash["Payment_Date"] = pd.to_datetime(dash["Payment_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Start_Date"] = pd.to_datetime(dash["Package_Start_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Expiry_Date"] = pd.to_datetime(dash["Package_Expiry_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Last_Lesson_Date"] = pd.to_datetime(dash["Last_Lesson_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    dash["Normalize_Allowed"] = True
    if "package_normalized" not in payments.columns:
        dash["Normalize_Allowed"] = False

    order = {"Mismatch":0, "Almost Finished":1, "Active":2, "Finished":3, "Dropout":9}
    dash["__o"] = dash["Status"].map(order).fillna(99).astype(int)
    dash = dash.sort_values(["__o","Lessons_Left_Units","Student"]).reset_index(drop=True)
    dash = dash.drop(columns=["__o"], errors="ignore")

    return dash[[
        "Student",
        "Packages_Bought",
        "Lessons_Paid_Total",
        "Total_Paid",
        "Payment_Date",
        "Package_Start_Date",
        "Package_Expiry_Date",
        "Lessons_Taken_Units",
        "Lessons_Left_Units",
        "Overused_Units",
        "Status",
        "Modality",
        "Languages",
        "Last_Lesson_Date",
        "Is_Active_6m",
        "Payment_ID",
        "Normalize_Allowed"
    ]]

# =========================
# 12) ANALYTICS (INCOME + CHARTS)
# =========================
def money_fmt(x: float) -> str:
    """
    Compact currency format for KPI bubbles.
    Examples:
    1_400_000 → 1,4M
    100_000   → 100K
    48_500    → 48,5K
    950       → 950
    """
    try:
        x = float(x)

        if abs(x) >= 1_000_000:
            val = x / 1_000_000
            return f"{val:.1f}".replace(".", ",").rstrip("0").rstrip(",") + "M"

        elif abs(x) >= 1_000:
            val = x / 1_000
            formatted = f"{val:.1f}".replace(".", ",").rstrip("0").rstrip(",")
            return formatted + "K"

        else:
            return str(int(round(x)))

    except Exception:
        return str(x)

def build_income_analytics(group: str = "monthly"):
    payments = load_table("payments")
    if payments.empty:
        payments = pd.DataFrame(columns=["student","payment_date","paid_amount","number_of_lesson","modality","languages"])

    payments["student"] = payments.get("student", "").astype(str).str.strip()
    payments["payment_date"] = pd.to_datetime(payments.get("payment_date"), errors="coerce")
    payments["paid_amount"] = pd.to_numeric(payments.get("paid_amount"), errors="coerce").fillna(0.0)
    payments["languages"] = payments.get("languages", LANG_ES).fillna(LANG_ES).astype(str)
    payments["modality"] = payments.get("modality", "Online").fillna("Online").astype(str)

    payments = payments.dropna(subset=["payment_date"])
    payments = payments[payments["student"].astype(str).str.len() > 0]

    today = pd.Timestamp.today().normalize()
    week_start = today - pd.Timedelta(days=int(today.weekday()))
    week_end = week_start + pd.Timedelta(days=6)

    income_all_time = float(payments["paid_amount"].sum()) if not payments.empty else 0.0
    income_this_year = float(payments.loc[payments["payment_date"].dt.year == today.year, "paid_amount"].sum()) if not payments.empty else 0.0
    this_month_key = str(today.to_period("M"))
    income_this_month = float(payments.loc[payments["payment_date"].dt.to_period("M").astype(str) == this_month_key, "paid_amount"].sum()) if not payments.empty else 0.0
    income_this_week = float(payments.loc[(payments["payment_date"] >= week_start) & (payments["payment_date"] <= week_end), "paid_amount"].sum()) if not payments.empty else 0.0

    kpis = {
        "income_all_time": income_all_time,
        "income_this_year": income_this_year,
        "income_this_month": income_this_month,
        "income_this_week": income_this_week,
    }

    if group == "yearly":
        payments["Key"] = payments["payment_date"].dt.to_period("Y").astype(str)
    else:
        payments["Key"] = payments["payment_date"].dt.to_period("M").astype(str)

    income_table = (
        payments.groupby("Key", as_index=False)["paid_amount"]
        .sum()
        .rename(columns={"paid_amount": "Income"})
        .sort_values("Key")
        .reset_index(drop=True)
    )

    by_student = (
        payments.groupby("student", as_index=False)
        .agg(Total_Paid=("paid_amount","sum"), Packages=("paid_amount","size"), Last_Payment=("payment_date","max"))
        .rename(columns={"student":"Student"})
        .sort_values("Total_Paid", ascending=False)
        .reset_index(drop=True)
    )

    sold_by_language = (
        payments.assign(_lang=payments["languages"].replace({LANG_BOTH: "English+Spanish"}))
        .groupby("_lang", as_index=False)["paid_amount"].sum()
        .rename(columns={"_lang":"Language","paid_amount":"Income"})
        .sort_values("Income", ascending=False)
        .reset_index(drop=True)
    )

    sold_by_modality = (
        payments.groupby("modality", as_index=False)["paid_amount"].sum()
        .rename(columns={"modality":"Modality","paid_amount":"Income"})
        .sort_values("Income", ascending=False)
        .reset_index(drop=True)
    )

    return kpis, income_table, by_student, sold_by_language, sold_by_modality

# =========================
# 13) FORECAST (ACTIVE ONLY + BEHAVIOR BASED)
# =========================
def build_forecast_table(payment_buffer_days: int = 0) -> pd.DataFrame:
    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=0).copy()
    if dash.empty:
        return pd.DataFrame(columns=["Student","Lessons_Left","Lessons_Per_Week","Estimated_Finish_Date","Estimated_Next_Payment_Date"])

    dash["Student"] = dash["Student"].astype(str).str.strip()
    dash["Lessons_Left"] = pd.to_numeric(dash.get("Lessons_Left_Units"), errors="coerce").fillna(0).astype(int)

    today = pd.Timestamp(date.today())
    three_months_ago = today - pd.Timedelta(days=90)

    dash["Last_Lesson_Date_dt"] = pd.to_datetime(dash.get("Last_Lesson_Date"), errors="coerce")
    dash["Finished_Recent_3m"] = (dash["Status"] == "Finished") & dash["Last_Lesson_Date_dt"].notna() & (dash["Last_Lesson_Date_dt"] >= three_months_ago)
    dash = dash[(dash["Status"].isin(["Active","Almost Finished"])) | (dash["Finished_Recent_3m"] == True)].copy()

    if dash.empty:
        return pd.DataFrame(columns=["Student","Lessons_Left","Lessons_Per_Week","Estimated_Finish_Date","Estimated_Next_Payment_Date"])

    classes = load_table("classes")
    schedules = load_schedules()

    if classes.empty:
        classes = pd.DataFrame(columns=["student","lesson_date"])
    classes["student"] = classes.get("student","").astype(str).str.strip()
    classes["lesson_date"] = pd.to_datetime(classes.get("lesson_date"), errors="coerce")
    classes = classes.dropna(subset=["lesson_date"])

    if classes.empty:
        hist_rate = pd.DataFrame(columns=["Student","Lessons_Per_Week_History"])
    else:
        c = classes.sort_values(["student","lesson_date"]).copy()
        c = c.groupby("student").tail(10)
        g = c.groupby("student")["lesson_date"].agg(["min","max","count"]).reset_index()
        span_days = (g["max"] - g["min"]).dt.days.clip(lower=1)
        g["Lessons_Per_Week_History"] = (g["count"] / (span_days / 7.0)).clip(lower=0.1)
        hist_rate = g.rename(columns={"student":"Student"})[["Student","Lessons_Per_Week_History"]]

    if schedules.empty:
        sched_rate = pd.DataFrame(columns=["Student","Lessons_Per_Week_Schedule"])
    else:
        s = schedules.copy()
        s["student"] = s["student"].astype(str).str.strip()
        s = s[s["active"] == True]
        sched_rate = (
            s.groupby("student", as_index=False).size()
             .rename(columns={"student":"Student","size":"Lessons_Per_Week_Schedule"})
        )

    dash = dash.merge(hist_rate, on="Student", how="left").merge(sched_rate, on="Student", how="left")
    dash["Lessons_Per_Week_History"] = pd.to_numeric(dash.get("Lessons_Per_Week_History"), errors="coerce").fillna(0.0)
    dash["Lessons_Per_Week_Schedule"] = pd.to_numeric(dash.get("Lessons_Per_Week_Schedule"), errors="coerce").fillna(0.0)

    dash["Lessons_Per_Week"] = dash["Lessons_Per_Week_History"].where(dash["Lessons_Per_Week_History"] > 0, dash["Lessons_Per_Week_Schedule"])
    dash["Lessons_Per_Week"] = dash["Lessons_Per_Week"].where(dash["Lessons_Per_Week"] > 0, 1.0)

    def _weeks_needed(left: int, per_week: float) -> int:
        if left <= 0:
            return 0
        return int(math.ceil(left / float(per_week)))

    dash["Weeks_Needed"] = dash.apply(lambda r: _weeks_needed(int(r["Lessons_Left"]), float(r["Lessons_Per_Week"])), axis=1)
    dash["Estimated_Finish_Date"] = dash["Weeks_Needed"].apply(lambda w: today + pd.Timedelta(days=7*w))
    dash["Estimated_Next_Payment_Date"] = dash["Estimated_Finish_Date"] - pd.Timedelta(days=int(payment_buffer_days))
    dash.loc[dash["Estimated_Next_Payment_Date"] < today, "Estimated_Next_Payment_Date"] = today

    out = dash[["Student","Lessons_Left","Lessons_Per_Week","Estimated_Finish_Date","Estimated_Next_Payment_Date"]].copy()
    out["Estimated_Finish_Date"] = pd.to_datetime(out["Estimated_Finish_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Estimated_Next_Payment_Date"] = pd.to_datetime(out["Estimated_Next_Payment_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    return out.sort_values("Estimated_Next_Payment_Date").reset_index(drop=True)

# =========================
# 14) UI HELPERS
# =========================
def pretty_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    out.columns = [
        str(c)
        .replace("_", " ")
        .replace("  ", " ")
        .strip()
        .title()
        .replace("Id", "ID")
        .replace("Url", "URL")
        for c in out.columns
    ]
    return out

def kpi_bubbles(values, colors, size=170):
    """
    Mobile-safe KPI bubbles renderer.
    Responsive sizing via CSS clamp() so bubbles + numbers never overflow on phones.
    """
    # If compact mode is on, bias smaller
    compact = bool(st.session_state.get("compact_mode", False))
    base = int(size * (0.88 if compact else 1.0))

    style = f"""
    <style>
      .kpi-wrap {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 14px;
        align-items: stretch;
        margin: 10px 0 10px 0;
      }}

      /* Bubble size becomes responsive:
         - small phones: ~110–120px
         - tablets: ~140–160px
         - desktop: up to base size
      */
      .kpi-bubble {{
        width: clamp(112px, 28vw, {base}px);
        height: clamp(112px, 28vw, {base}px);
        border-radius: 999px;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        box-shadow: 0 14px 30px rgba(15,23,42,0.10);
        border: 1px solid rgba(17,24,39,0.10);
        background: white;
        overflow: hidden;
        padding: 10px;
        box-sizing: border-box;
      }}

      /* Number scales down on mobile and never overflows */
      .kpi-num {{
        font-weight: 900;
        line-height: 1.0;
        text-align: center;
        padding: 0 10px;
        margin: 0 0 6px 0;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;

        /* Key fix: responsive font size */
        font-size: clamp(18px, 5.2vw, 44px);

        /* Safety: prevent overflow */
        max-width: 100%;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      .kpi-label {{
        font-size: clamp(12px, 3.4vw, 14px);
        font-weight: 800;
        opacity: .9;
        text-align: center;
        padding: 0 12px;
        line-height: 1.15;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;

        /* Allow 2 lines, avoid cut-off */
        max-width: 100%;
        overflow-wrap: anywhere;
        word-break: break-word;
      }}

      @media (max-width: 380px) {{
        .kpi-wrap {{
          grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
          gap: 10px;
        }}
      }}
    </style>
    """

    bubbles_html = '<div class="kpi-wrap">'
    for (label, val), bg in zip(values, colors):
        bubbles_html += f"""
          <div class="kpi-bubble" style="{bg}">
            <div class="kpi-num">{val}</div>
            <div class="kpi-label">{label}</div>
          </div>
        """
    bubbles_html += "</div>"

    # Height estimation: compute rows based on a conservative "3 bubbles per row" for mobile
    n = len(values)
    # On wide screens auto-fit handles it; for iframe height, assume up to 4 per row in practice
    per_row = 3 if compact else 4
    rows = max(1, math.ceil(n / per_row))
    bubble_px = min(base, 180)
    height = int(rows * (bubble_px + 28) + 40)

    components.html(style + bubbles_html, height=height)
# =========================
# 15) CALENDAR (EVENTS + RENDER)
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
    color_map, zoom_map, _, _ = student_meta_maps()

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
                    "Source": "recurring",
                    "Override_ID": None,
                    "Original_Date": dt.date(),
                })
            cur += timedelta(days=1)

    events_df = pd.DataFrame(events)

    # Apply overrides:
    # - cancel removes recurring on original_date
    # - scheduled removes recurring on original_date and adds new slot
    if not overrides.empty:
        for _, row in overrides.iterrows():
            student = str(row.get("student", "")).strip()
            k = norm_student(student)

            status = str(row.get("status", "")).strip().lower()
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
                    events_df = pd.concat(
                        [
                            events_df,
                            pd.DataFrame([{
                                "DateTime": new_dt,
                                "Date": new_dt.date(),
                                "Student": student,
                                "Duration_Min": duration,
                                "Color": color_map.get(k, "#3B82F6"),
                                "Zoom_Link": zoom_map.get(k, ""),
                                "Source": "override",
                                "Override_ID": int(row.get("id")) if pd.notna(row.get("id")) else None,
                                "Original_Date": original_date.date() if pd.notna(original_date) else new_dt.date(),
                            }])
                        ],
                        ignore_index=True
                    )

    if events_df.empty:
        return events_df

    events_df["DateTime"] = pd.to_datetime(events_df["DateTime"], errors="coerce").dt.tz_localize(None)
    events_df = events_df.sort_values("DateTime").reset_index(drop=True)
    events_df["Time"] = events_df["DateTime"].dt.strftime("%H:%M")
    events_df["Date"] = events_df["DateTime"].dt.strftime("%Y-%m-%d")
    return events_df

def render_fullcalendar(events: pd.DataFrame, height: int = 750):
    if events.empty:
        st.info(t("no_events"))
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
      .fc .fc-button {{
        border-radius:10px;
        border:1px solid rgba(17,24,39,0.14);
        background:#fff;
        color:#0f172a;
      }}
      .fc .fc-col-header-cell-cushion,
      .fc .fc-daygrid-day-number {{ color:#0f172a; }}
      .fc .fc-timegrid-slot-label-cushion {{ color:#334155; }}
      .fc .fc-toolbar-title {{
        color:#0f172a;
        font-weight:800;
        font-size:1.1rem;
        line-height:1.15;
      }}
      @media (max-width: 768px){{
        .fc .fc-toolbar-title {{ font-size:0.95rem; }}
        .fc .fc-button {{
          padding:0.35rem 0.55rem;
          font-size:0.85rem;
        }}
      }}
    </style>

    <script>
      const events = {payload};
      const calendarEl = document.getElementById('calendar');
      const isMobile = () => window.innerWidth < 768;

      const toolbarDesktop = {{
        left: 'prev,next today',
        center: 'title',
        right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek'
      }};

      const toolbarMobile = {{
        left: 'prev,next',
        center: 'title',
        right: 'timeGridDay,timeGridWeek,dayGridMonth'
      }};

      const calendar = new FullCalendar.Calendar(calendarEl, {{
        initialView: 'timeGridWeek',
        height: {height},
        expandRows: true,
        nowIndicator: true,
        stickyHeaderDates: true,
        handleWindowResize: true,
        firstDay: 1,
        headerToolbar: isMobile() ? toolbarMobile : toolbarDesktop,
        titleFormat: {{ year: 'numeric', month: 'short', day: 'numeric' }},
        dayHeaderFormat: {{ weekday: 'short' }},
        slotLabelFormat: {{ hour: 'numeric', minute: '2-digit', meridiem: 'short' }},
        windowResize: function() {{
          calendar.setOption('headerToolbar', isMobile() ? toolbarMobile : toolbarDesktop);
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
# 16) HOME SCREEN UI (DARK)
# =========================
def render_home():
    st.markdown("<div class='home-wrap'><div class='home-card'><div class='home-glow'></div>", unsafe_allow_html=True)
    st.markdown("<div class='home-title'>CLASS MANAGER</div>", unsafe_allow_html=True)
    st.markdown("<div class='home-sub'>Choose where you want to go</div>", unsafe_allow_html=True)

    for key, label_key, grad in PAGES:
        st.markdown(
            f"""
            <a class="home-pill home-{key}"
               href="?page={key}"
               target="_self"
               rel="noopener noreferrer"
               style="background:{grad};">
              {t(label_key)}
            </a>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<div class='home-indicator'></div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# =========================
# 17) APP ENTRYPOINT (ROUTER + THEME SWITCH)
# =========================
page = st.session_state.page

if page != "home":
    force_close_sidebar()

if page == "home":
    load_css_home_dark()
else:
    load_css_app_light(compact=bool(st.session_state.get("compact_mode", False)))

students = load_students()

if page == "home":
    render_home()
    st.stop()

render_sidebar_nav(page)

# =========================
# 18) PAGE: DASHBOARD
# =========================
if page == "dashboard":
    page_header(t("dashboard"))

    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)

    if dash.empty:
        st.info(t("no_data"))
        st.stop()

    d = dash.copy()
    d["Is_Active_6m"] = d.get("Is_Active_6m", False).fillna(False).astype(bool)
    d["Status"] = d.get("Status", "").fillna("").astype(str)

    d = d[d["Status"] != "Dropout"].copy()
    d = d[
        (d["Status"].isin(["Active", "Almost Finished"])) |
        ((d["Status"] == "Finished") & (d["Is_Active_6m"] == True)) |
        (d["Status"] == "Mismatch")
    ].copy()

    total_students = int(len(d))
    active_count = int((d["Status"] == "Active").sum())
    finish_soon_count = int((d["Status"] == "Almost Finished").sum())
    finished_recent_count = int((d["Status"] == "Finished").sum())
    mismatch_count = int((d["Status"] == "Mismatch").sum())

    kpi_bubbles(
        values=[
            (t("students"), str(total_students)),
            (t("active"), str(active_count)),
            (t("action_finish_soon"), str(finish_soon_count)),
            (t("finished"), str(finished_recent_count)),
            (t("mismatch"), str(mismatch_count)),
        ],
        colors=[
            "background: radial-gradient(90px 90px at 30% 25%, rgba(59,130,246,.35), transparent 60%), #ffffff;",
            "background: radial-gradient(90px 90px at 30% 25%, rgba(16,185,129,.30), transparent 60%), #ffffff;",
            "background: radial-gradient(90px 90px at 30% 25%, rgba(245,158,11,.30), transparent 60%), #ffffff;",
            "background: radial-gradient(90px 90px at 30% 25%, rgba(139,92,246,.32), transparent 60%), #ffffff;",
            "background: radial-gradient(90px 90px at 30% 25%, rgba(239,68,68,.26), transparent 60%), #ffffff;",
        ],
        size=160,
    )

    st.divider()
    st.subheader(t("status_overview"))
    status_order = ["Active", "Almost Finished", "Finished", "Mismatch"]
    status_counts = (
        d["Status"]
        .value_counts()
        .reindex(status_order)
        .fillna(0)
        .astype(int)
    )
    st.bar_chart(status_counts)

    st.divider()
    st.subheader(t("action_finish_soon"))

    due_df = d[d["Status"] == "Almost Finished"].copy()
    due_df["Lessons_Left"] = pd.to_numeric(due_df.get("Lessons_Left_Units"), errors="coerce").fillna(0).astype(int)
    due_df = due_df.sort_values(["Lessons_Left", "Student"])

    if due_df.empty:
        st.caption(t("no_data"))
    else:
        cols_due = ["Student","Lessons_Left","Status","Modality","Languages","Payment_Date","Last_Lesson_Date"]
        cols_due = [c for c in cols_due if c in due_df.columns]
        st.dataframe(pretty_df(due_df[cols_due]), use_container_width=True, hide_index=True)

        _, _, _, phone_map = student_meta_maps()
        pick = st.selectbox(t("select_student"), due_df["Student"].tolist(), key="dash_pick_student")
        raw_phone = phone_map.get(norm_student(pick), "")

        default_msg = (
            f"Hello. I hope you are fine. {pick} has finished the package. "
            "If (s/he) wishes to continue, here you have my current prices. "
            "Please let me know to plan accordingly. Thanks."
        )
        msg = st.text_area(t("whatsapp_message"), value=default_msg, height=160, key="dash_wa_msg")

        wa_url = build_whatsapp_url(msg, raw_phone=raw_phone)
        st.markdown(
            f"""
            <a href="{wa_url}" target="_blank" style="text-decoration:none;">
              <button style="width:100%;padding:0.7rem 1rem;border-radius:14px;border:1px solid rgba(17,24,39,0.12);background:white;font-weight:700;cursor:pointer;">
                {t("open_whatsapp")}
              </button>
            </a>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader(t("current_students"))
    st.dataframe(pretty_df(d), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader(t("mismatches"))
    mismatch_df = d[d["Status"] == "Mismatch"].copy()
    if mismatch_df.empty:
        st.caption(t("no_data"))
    else:
        cols_mm = [
            "Student","Overused_Units","Lessons_Taken_Units","Lessons_Paid_Total",
            "Payment_Date","Package_Start_Date","Modality","Languages","Payment_ID","Normalize_Allowed"
        ]
        cols_mm = [c for c in cols_mm if c in mismatch_df.columns]
        st.dataframe(pretty_df(mismatch_df[cols_mm]), use_container_width=True, hide_index=True)

        pick_m = st.selectbox(t("select_student"), mismatch_df["Student"].tolist(), key="dash_mismatch_student")
        rowm = mismatch_df[mismatch_df["Student"] == pick_m].iloc[0]
        pid = int(rowm.get("Payment_ID", 0))
        can_norm = bool(rowm.get("Normalize_Allowed", False))
        norm_note = st.text_input(t("normalized_note"), value=t("normalized_default_note"), key="dash_norm_note")

        if st.button(t("normalize"), disabled=not can_norm, key="dash_mismatch_norm"):
            ok = normalize_latest_package(pick_m, pid, note=norm_note)
            if ok:
                st.success(t("done_ok"))
                st.rerun()
            else:
                st.error(t("normalize_failed"))

# =========================
# 19) PAGE: STUDENTS
# =========================
elif page == "students":
    page_header(t("students"))
    students_df = load_students_df()

    st.markdown(f"### {t('add_students')}")
    new_student = st.text_input(t("new_student_name"), key="new_student_name")
    if st.button(f"{t('add')} {t('students')}", key="btn_add_student"):
        if not new_student.strip():
            st.error("Please enter a student name.")
        else:
            ensure_student(new_student)
            st.success("Saved ✅")
            st.rerun()

    st.markdown(f"### {t('see_all_students')}")
    if students_df.empty:
        st.info(t("no_students"))
    else:
        with st.expander(t("student_profile"), expanded=False):
            student_list = sorted(students_df["student"].unique().tolist())
            selected_student = st.selectbox(t("select_student"), student_list, key="edit_student_select")
            student_row = students_df[students_df["student"] == selected_student].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input(t("email"), value=student_row.get("email", ""), key="student_email")
                zoom_link = st.text_input(t("zoom_link"), value=student_row.get("zoom_link", ""), key="student_zoom")
                phone = st.text_input(t("whatsapp_phone"), value=student_row.get("phone", ""), key="student_phone")
                st.caption(t("examples_phone"))
            with col2:
                color = st.color_picker(t("calendar_color"), value=student_row.get("color", "#3B82F6"), key="student_color")
                notes = st.text_area(t("notes"), value=student_row.get("notes", ""), key="student_notes")

            if phone and not normalize_phone_for_whatsapp(phone) and len(_digits_only(phone)) < 11:
                st.warning("Phone seems short/ambiguous. Use international format for direct WhatsApp chat.")

            if st.button(t("save"), key="btn_save_student_profile"):
                update_student_profile(selected_student, email, zoom_link, notes, color, phone)
                st.success("Saved ✅")
                st.rerun()

    with st.expander(t("current_student_list"), expanded=False):
        s_col1, s_col2 = st.columns([2, 1])
        with s_col1:
            q = st.text_input(t("search"), value="", placeholder="Type a name…", key="students_list_search")
        with s_col2:
            st.caption(f"Total: **{len(students)}**")

        shown = students
        if q.strip():
            shown = [s for s in students if q.strip().lower() in s.lower()]

        list_df = pd.DataFrame({"Student": shown})
        st.dataframe(list_df, use_container_width=True, hide_index=True)

    with st.expander(t("student_history"), expanded=False):
        if not students:
            st.info(t("no_students"))
        else:
            hist_student = st.selectbox(t("select_student"), students, key="students_history_student")
            lessons_df, payments_df = show_student_history(hist_student)

            colA, colB = st.columns(2)
            with colA:
                st.markdown("### Lessons")
                st.dataframe(pretty_df(lessons_df), use_container_width=True)

                st.markdown("#### Delete a lesson record (by ID)")
                st.caption("Be careful: this deletes permanently.")
                lesson_id = st.number_input("Lesson ID", min_value=0, step=1, key="students_del_lesson_id")
                if st.button(t("delete"), key="students_btn_delete_lesson"):
                    delete_row("classes", lesson_id)
                    st.success("Deleted ✅")
                    st.rerun()

            with colB:
                st.markdown("### Payments")
                st.dataframe(pretty_df(payments_df), use_container_width=True)

                st.markdown("#### Delete a payment record (by ID)")
                st.caption("Be careful: this deletes permanently.")
                payment_id = st.number_input("Payment ID", min_value=0, step=1, key="students_del_payment_id")
                if st.button(t("delete"), key="students_btn_delete_payment"):
                    delete_row("payments", payment_id)
                    st.success("Deleted ✅")
                    st.rerun()

    st.divider()
    with st.expander(t("delete_student"), expanded=False):
        st.caption(t("delete_student_warning"))
        if not students:
            st.info(t("no_students"))
        else:
            del_student = st.selectbox(t("select_student"), students, key="delete_student_select")
            confirm = st.checkbox(t("confirm_delete_student"), key="delete_student_confirm")
            if st.button(t("delete"), type="primary", disabled=not confirm, key="btn_delete_student"):
                try:
                    supabase.table("students").delete().eq("student", del_student).execute()
                    st.success(f"Deleted profile: {del_student}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not delete student.\n\n{e}")

# =========================
# 20) PAGE: ADD LESSON
# =========================
elif page == "add_lesson":
    page_header(t("lesson"))
    st.caption(t("add_lesson_title"))

    if not students:
        st.info(t("no_students"))
    else:
        student = st.selectbox(t("select_student"), students, key="lesson_student")
        number = st.number_input("Units", min_value=1, max_value=10, value=1, step=1, key="lesson_number")
        lesson_date = st.date_input("Date", key="lesson_date")
        modality = st.selectbox(t("modality"), [t("online"), t("offline")], key="lesson_modality")
        note = st.text_input(t("notes_optional"), key="lesson_note") if "notes_optional" in I18N["en"] else st.text_input("Note (optional)", key="lesson_note")

        pkg_lang = latest_payment_languages_for_student(student)
        lang_options, lang_default = allowed_lesson_language_from_package(pkg_lang)

        if lang_default is not None:
            lesson_lang = lang_default
        else:
            lesson_lang = st.selectbox(t("lesson_language"), lang_options, key="lesson_lang_select")

        if st.button(t("save"), key="btn_save_lesson"):
            add_class(
                student=student,
                number_of_lesson=int(number),
                lesson_date=lesson_date.isoformat(),
                modality=("Offline" if modality == t("offline") else "Online"),
                note=note,
                lesson_language=lesson_lang
            )
            st.success("Saved ✅")
            st.rerun()

        st.divider()
        with st.expander(t("lessons_editor"), expanded=True):
            st.caption(t("warning_apply"))
            classes = load_table("classes")
            if classes.empty:
                st.info(t("no_data"))
            else:
                classes["student"] = classes.get("student","").astype(str).str.strip()
                classes = classes[classes["student"] == student].copy()
                if classes.empty:
                    st.info(t("no_data"))
                else:
                    for c in ["id","lesson_date","number_of_lesson","modality","lesson_language","note"]:
                        if c not in classes.columns:
                            classes[c] = None

                    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce").dt.date
                    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(1).astype(int)
                    classes["modality"] = classes["modality"].fillna("Online").astype(str)
                    classes["lesson_language"] = classes["lesson_language"].fillna("").astype(str)

                    show_cols = ["id","lesson_date","number_of_lesson","modality","lesson_language","note"]
                    ed = classes[show_cols].sort_values(["lesson_date","id"], ascending=[False, False]).reset_index(drop=True)

                    if lang_default is not None:
                        ed["lesson_language"] = ed["lesson_language"].replace({"": lang_default, None: lang_default})

                    edited = st.data_editor(
                        ed,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "id": st.column_config.NumberColumn("ID", disabled=True),
                            "lesson_date": st.column_config.DateColumn("Date"),
                            "number_of_lesson": st.column_config.NumberColumn("Units", min_value=1, step=1),
                            "modality": st.column_config.SelectboxColumn("Modality", options=["Online","Offline"]),
                            "lesson_language": st.column_config.SelectboxColumn("Lesson language", options=[LANG_EN, LANG_ES, ""]),
                            "note": st.column_config.TextColumn("Note"),
                        }
                    )

                    if st.button(t("apply_changes"), key="apply_class_bulk"):
                        ok_all = True
                        for _, r in edited.iterrows():
                            cid = int(r["id"])
                            ll = str(r.get("lesson_language","") or "").strip()
                            if lang_default is not None and not ll:
                                ll = lang_default
                            updates = {
                                "lesson_date": pd.to_datetime(r["lesson_date"]).date().isoformat() if pd.notna(r["lesson_date"]) else None,
                                "number_of_lesson": int(r["number_of_lesson"]),
                                "modality": str(r["modality"]).strip(),
                                "note": str(r.get("note","") or "").strip(),
                                "lesson_language": ll if ll in (LANG_EN, LANG_ES) else None,
                            }
                            if not update_class_row(cid, updates):
                                ok_all = False
                        if ok_all:
                            st.success("Updated ✅")
                            st.rerun()
                        else:
                            st.error("Some updates failed.")

# =========================
# 21) PAGE: ADD PAYMENT
# =========================
elif page == "add_payment":
    page_header(t("payment"))
    st.caption(t("add_payment_title"))

    if not students:
        st.info(t("no_students"))
    else:
        student_p = st.selectbox(t("select_student"), students, key="pay_student")
        lessons_paid = st.number_input(t("lessons_paid"), min_value=1, max_value=500, value=44, step=1, key="pay_lessons_paid")
        payment_date = st.date_input(t("payment_date"), key="pay_date")
        paid_amount = st.number_input(t("paid_amount"), min_value=0.0, value=0.0, step=100.0, key="pay_amount")
        modality_p = st.selectbox(t("modality"), [t("online"), t("offline")], key="pay_modality")

        langs_selected = st.multiselect(
            t("package_languages"),
            options=[LANG_EN, LANG_ES],
            default=DEFAULT_PACKAGE_LANGS,
            key="pay_languages_multi"
        )
        languages_value = pack_languages(langs_selected)

        st.divider()
        st.markdown(f"### {t('package_dates')}")

        use_custom_start = st.checkbox(t("starts_different"), value=False, key="pay_custom_start")
        if use_custom_start:
            pkg_start = st.date_input(t("package_start"), value=payment_date, key="pay_pkg_start")
        else:
            pkg_start = payment_date

        close_package = st.checkbox(t("close_package"), value=False, key="pay_has_expiry")
        pkg_expiry = None
        if close_package:
            pkg_expiry = st.date_input(t("package_expiry"), value=date.today(), key="pay_pkg_expiry")

        st.divider()
        st.markdown(f"### {t('advanced_optional')}")

        lesson_adjustment_units = st.number_input(
            t("adjust_units"),
            min_value=-1000,
            max_value=1000,
            value=0,
            step=1,
            key="pay_adjust_units"
        )
        package_normalized = st.checkbox(t("normalized_flag"), value=False, key="pay_norm_flag")
        normalized_note = st.text_input(t("normalized_note"), value="", key="pay_norm_note")

        if st.button(t("save"), key="btn_save_payment"):
            add_payment(
                student=student_p,
                number_of_lesson=int(lessons_paid),
                payment_date=payment_date.isoformat(),
                paid_amount=float(paid_amount),
                modality=("Offline" if modality_p == t("offline") else "Online"),
                languages=languages_value,
                package_start_date=pkg_start.isoformat() if pkg_start else payment_date.isoformat(),
                package_expiry_date=pkg_expiry.isoformat() if pkg_expiry else None,
                lesson_adjustment_units=int(lesson_adjustment_units),
                package_normalized=bool(package_normalized),
                normalized_note=normalized_note
            )
            st.success("Saved ✅")
            st.rerun()

        st.divider()
        with st.expander(t("payments_editor"), expanded=True):
            st.caption(t("warning_apply"))

            payments = load_table("payments")
            if payments.empty:
                st.info(t("no_data"))
            else:
                payments["student"] = payments.get("student","").astype(str).str.strip()
                payments = payments[payments["student"] == student_p].copy()
                if payments.empty:
                    st.info(t("no_data"))
                else:
                    for c in [
                        "id","payment_date","number_of_lesson","paid_amount","modality","languages",
                        "package_start_date","package_expiry_date",
                        "lesson_adjustment_units","package_normalized","normalized_note"
                    ]:
                        if c not in payments.columns:
                            payments[c] = None

                    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce").dt.date
                    payments["package_start_date"] = pd.to_datetime(payments["package_start_date"], errors="coerce").dt.date
                    payments["package_expiry_date"] = pd.to_datetime(payments["package_expiry_date"], errors="coerce").dt.date
                    payments["number_of_lesson"] = pd.to_numeric(payments["number_of_lesson"], errors="coerce").fillna(0).astype(int)
                    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
                    payments["lesson_adjustment_units"] = pd.to_numeric(payments["lesson_adjustment_units"], errors="coerce").fillna(0).astype(int)
                    payments["package_normalized"] = payments["package_normalized"].fillna(False).astype(bool)
                    payments["languages"] = payments["languages"].fillna(LANG_ES).astype(str)

                    show_cols = [
                        "id","payment_date","number_of_lesson","paid_amount","modality","languages",
                        "package_start_date","package_expiry_date",
                        "lesson_adjustment_units","package_normalized","normalized_note"
                    ]
                    ed = payments[show_cols].sort_values(["payment_date","id"], ascending=[False, False]).reset_index(drop=True)

                    edited = st.data_editor(
                        ed,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "id": st.column_config.NumberColumn("ID", disabled=True),
                            "payment_date": st.column_config.DateColumn("Payment date"),
                            "number_of_lesson": st.column_config.NumberColumn("Lessons paid", min_value=1, step=1),
                            "paid_amount": st.column_config.NumberColumn("Amount", min_value=0.0, step=100.0),
                            "modality": st.column_config.SelectboxColumn("Modality", options=["Online","Offline"]),
                            "languages": st.column_config.SelectboxColumn("Languages", options=[LANG_EN, LANG_ES, LANG_BOTH]),
                            "package_start_date": st.column_config.DateColumn("Start date"),
                            "package_expiry_date": st.column_config.DateColumn("Expiry date"),
                            "lesson_adjustment_units": st.column_config.NumberColumn("Adjustment units", step=1),
                            "package_normalized": st.column_config.CheckboxColumn("Normalized"),
                            "normalized_note": st.column_config.TextColumn("Note"),
                        }
                    )

                    if st.button(t("apply_changes"), key="apply_payment_bulk"):
                        ok_all = True
                        for _, r in edited.iterrows():
                            pid = int(r["id"])
                            languages_val = str(r.get("languages") or LANG_ES).strip()
                            if languages_val not in ALLOWED_LANGS:
                                languages_val = LANG_ES

                            updates = {
                                "payment_date": pd.to_datetime(r["payment_date"]).date().isoformat() if pd.notna(r["payment_date"]) else None,
                                "number_of_lesson": int(r["number_of_lesson"]),
                                "paid_amount": float(r["paid_amount"]),
                                "modality": str(r["modality"]).strip(),
                                "languages": languages_val,
                                "package_start_date": pd.to_datetime(r["package_start_date"]).date().isoformat() if pd.notna(r["package_start_date"]) else None,
                                "package_expiry_date": pd.to_datetime(r["package_expiry_date"]).date().isoformat() if pd.notna(r["package_expiry_date"]) else None,
                                "lesson_adjustment_units": int(r.get("lesson_adjustment_units", 0)),
                                "package_normalized": bool(r.get("package_normalized", False)),
                                "normalized_note": str(r.get("normalized_note","") or "").strip(),
                                "normalized_at": datetime.now(timezone.utc).isoformat() if (bool(r.get("package_normalized", False)) or str(r.get("normalized_note","") or "").strip()) else None,
                            }
                            if not update_payment_row(pid, updates):
                                ok_all = False

                        # Auto-fill missing lesson_language when package becomes single-language
                        latest_lang = latest_payment_languages_for_student(student_p)
                        _, single_default = allowed_lesson_language_from_package(latest_lang)
                        if single_default is not None:
                            try:
                                cls = load_table("classes")
                                if not cls.empty:
                                    cls["student"] = cls.get("student","").astype(str).str.strip()
                                    cls = cls[cls["student"] == student_p].copy()
                                    if "lesson_language" not in cls.columns:
                                        cls["lesson_language"] = None
                                    cls["lesson_language"] = cls["lesson_language"].fillna("").astype(str)
                                    missing = cls[(cls["lesson_language"].str.strip() == "") | (cls["lesson_language"].isna())]
                                    for _, rr in missing.iterrows():
                                        update_class_row(int(rr["id"]), {"lesson_language": single_default})
                            except Exception:
                                pass

                        if ok_all:
                            st.success("Updated ✅")
                            st.rerun()
                        else:
                            st.error("Some updates failed.")

# =========================
# 22) PAGE: SCHEDULE
# =========================
elif page == "schedule":
    page_header(t("schedule"))
    st.caption(t("create_weekly_program"))

    if not students:
        st.info(t("no_students"))
    else:
        schedules = load_schedules()

        st.markdown(f"### {t('add')} {t('schedule')}")
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

        with c1:
            sch_student = st.selectbox(t("select_student"), students, key="sch_student")
        with c2:
            sch_weekday = st.selectbox("Weekday", list(range(7)), format_func=lambda x: f"{x} ({WEEKDAYS[x]})", key="sch_weekday")
        with c3:
            sch_time = st.text_input("Time (HH:MM)", value="10:00", key="sch_time")
        with c4:
            sch_duration = st.number_input("Duration (min)", min_value=15, max_value=360, value=60, step=15, key="sch_duration")
        with c5:
            sch_active = st.checkbox("Active", value=True, key="sch_active")

        if st.button(t("add"), key="btn_add_schedule"):
            add_schedule(sch_student, sch_weekday, sch_time, sch_duration, sch_active)
            st.success("Saved ✅")
            st.rerun()

        st.divider()
        st.markdown("### Current schedule")
        if schedules.empty:
            st.info(t("no_data"))
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
            st.dataframe(pretty_df(show), use_container_width=True, hide_index=True)

            st.markdown("#### Delete a schedule lesson")
            st.caption("Be careful: this deletes permanently.")
            del_id = st.number_input("Schedule ID", min_value=0, step=1, key="del_schedule_id")
            if st.button(t("delete"), key="btn_delete_schedule"):
                delete_schedule(del_id)
                st.success("Deleted ✅")
                st.rerun()

# =========================
# 23) PAGE: CALENDAR
# =========================
elif page == "calendar":
    page_header(t("calendar"))
    st.caption(t("see_timetable"))

    view = st.radio(t("view"), [t("today"), t("this_week"), t("this_month")], horizontal=True, key="calendar_view")
    today_d = date.today()

    if view == t("today"):
        start_day = today_d
        end_day = today_d
    elif view == t("this_week"):
        start_day = today_d - timedelta(days=today_d.weekday())
        end_day = start_day + timedelta(days=6)
    else:
        start_day = date(today_d.year, today_d.month, 1)
        next_month = date(today_d.year + 1, 1, 1) if today_d.month == 12 else date(today_d.year, today_d.month + 1, 1)
        end_day = next_month - timedelta(days=1)

    events = build_calendar_events(start_day, end_day)

    if events.empty:
        st.info(t("no_data"))
    else:
        students_list = sorted(events["Student"].unique().tolist())

        if "calendar_filter_students" not in st.session_state:
            st.session_state.calendar_filter_students = students_list
        else:
            missing = [s for s in students_list if s not in st.session_state.calendar_filter_students]
            if missing:
                st.session_state.calendar_filter_students = students_list

        colA, colB = st.columns([3, 1])
        with colA:
            selected_students = st.multiselect(t("filter_students"), students_list, key="calendar_filter_students")
        with colB:
            if st.button(t("reset"), use_container_width=True, key="calendar_reset"):
                st.session_state.calendar_filter_students = students_list
                st.rerun()

        filtered = events[events["Student"].isin(selected_students)].copy()
        render_fullcalendar(filtered, height=980 if st.session_state.get("compact_mode", False) else 1050)

    # --- Calendar overrides UI (the missing part you asked for) ---
    st.divider()
    st.subheader(t("calendar_overrides"))

    overrides = load_overrides()
    students_master = load_students()

    with st.expander(t("override_add"), expanded=False):
        if not students_master:
            st.info(t("no_students"))
        else:
            c1, c2 = st.columns(2)
            with c1:
                ov_student = st.selectbox(t("override_student"), students_master, key="ov_student")
                ov_original_date = st.date_input(t("override_original_date"), value=today_d, key="ov_original_date")
                ov_status = st.selectbox(
                    t("override_status"),
                    options=["scheduled", "cancelled"],
                    format_func=lambda x: t("override_scheduled") if x == "scheduled" else t("override_cancel"),
                    key="ov_status"
                )
            with c2:
                # new datetime only relevant if scheduled
                ov_new_dt = st.date_input("New date", value=today_d, key="ov_new_date")
                ov_new_time = st.text_input("New time (HH:MM)", value="10:00", key="ov_new_time")
                ov_duration = st.number_input(t("override_duration"), min_value=15, max_value=360, value=60, step=15, key="ov_duration")

            ov_note = st.text_input(t("override_note"), value="", key="ov_note")

            new_dt = None
            if ov_status == "scheduled":
                hh, mm = _parse_time_value(ov_new_time)
                new_dt = datetime(ov_new_dt.year, ov_new_dt.month, ov_new_dt.day, hh, mm)

            if st.button(t("override_add_btn"), key="ov_add_btn"):
                try:
                    if ov_status == "scheduled" and new_dt is None:
                        st.error("Please select a new date & time.")
                    else:
                        # Always insert a new override row (simple and robust)
                        add_override(
                            student=ov_student,
                            original_date=ov_original_date,
                            new_dt=new_dt if new_dt else datetime(ov_original_date.year, ov_original_date.month, ov_original_date.day, 0, 0),
                            duration_minutes=int(ov_duration),
                            status=ov_status,
                            note=ov_note
                        )
                        st.success("Saved ✅")
                        st.rerun()
                except Exception as e:
                    st.error(f"Could not save override.\n\n{e}")

    with st.expander(t("override_list"), expanded=True):
        if overrides.empty:
            st.caption(t("no_data"))
        else:
            show = overrides.copy()
            show["original_date"] = pd.to_datetime(show["original_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            show["new_datetime"] = pd.to_datetime(show["new_datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            show = show.rename(columns={
                "id": "ID",
                "student": "Student",
                "original_date": "Original_Date",
                "new_datetime": "New_Datetime",
                "duration_minutes": "Duration_Min",
                "status": "Status",
                "note": "Note"
            })[["ID","Student","Original_Date","New_Datetime","Duration_Min","Status","Note"]].sort_values(["Original_Date","Student"])

            st.dataframe(pretty_df(show), use_container_width=True, hide_index=True)

            del_id = st.number_input("Override ID", min_value=0, step=1, key="ov_del_id")
            if st.button(t("override_delete_btn"), key="ov_del_btn"):
                try:
                    delete_override(del_id)
                    st.success("Deleted ✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not delete override.\n\n{e}")

# =========================
# 24) PAGE: ANALYTICS
# =========================
elif page == "analytics":
    page_header(t("analytics"))

    group = st.selectbox(
        t("group_by"),
        options=["monthly", "yearly"],
        format_func=lambda x: t("monthly") if x == "monthly" else t("yearly"),
        index=0,
        key="analytics_group"
    )

    kpis, income_table, by_student, sold_by_language, sold_by_modality = build_income_analytics(group=group)

    kpi_bubbles(
        values=[
            (t("all_time_income"), money_fmt(kpis.get("income_all_time", 0.0))),
            (t("this_year_income"), money_fmt(kpis.get("income_this_year", 0.0))),
            (t("this_month_income"), money_fmt(kpis.get("income_this_month", 0.0))),
            (t("this_week_income"), money_fmt(kpis.get("income_this_week", 0.0))),
        ],
        colors=[
            "background: radial-gradient(100px 100px at 30% 25%, rgba(59,130,246,.35), transparent 60%), #ffffff;",
            "background: radial-gradient(100px 100px at 30% 25%, rgba(16,185,129,.30), transparent 60%), #ffffff;",
            "background: radial-gradient(100px 100px at 30% 25%, rgba(245,158,11,.30), transparent 60%), #ffffff;",
            "background: radial-gradient(100px 100px at 30% 25%, rgba(139,92,246,.32), transparent 60%), #ffffff;",
        ],
        size=180
    )

    st.divider()
    st.subheader(t("income_table"))
    if income_table.empty:
        st.info(t("no_data"))
    else:
        chart_df = income_table.set_index("Key")[["Income"]]
        st.line_chart(chart_df)
        show_table = income_table.copy()
        show_table["Income"] = show_table["Income"].apply(money_fmt)
        st.dataframe(pretty_df(show_table.rename(columns={"Key": "Period"})), use_container_width=True, hide_index=True)

    # ✅ Missing piece: Top profitable students
    st.divider()
    st.subheader(t("top_students"))
    if by_student.empty:
        st.info(t("no_data"))
    else:
        top = by_student.head(20).copy()
        top["Total_Paid"] = top["Total_Paid"].apply(money_fmt)
        top["Last_Payment"] = pd.to_datetime(top["Last_Payment"], errors="coerce").dt.strftime("%Y-%m-%d")
        st.dataframe(pretty_df(top), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader(t("sold_by_language"))
    if sold_by_language.empty:
        st.info(t("no_data"))
    else:
        st.bar_chart(sold_by_language.set_index("Language")["Income"])
        tmp = sold_by_language.copy()
        tmp["Income"] = tmp["Income"].apply(money_fmt)
        st.dataframe(pretty_df(tmp), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader(t("sold_by_modality"))
    if sold_by_modality.empty:
        st.info(t("no_data"))
    else:
        st.bar_chart(sold_by_modality.set_index("Modality")["Income"])
        tmp = sold_by_modality.copy()
        tmp["Income"] = tmp["Income"].apply(money_fmt)
        st.dataframe(pretty_df(tmp), use_container_width=True, hide_index=True)

    st.divider()
    classes = load_table("classes")
    if classes.empty:
        st.info(t("no_data"))
    else:
        for c in ["student","lesson_language","modality","number_of_lesson","lesson_date","note"]:
            if c not in classes.columns:
                classes[c] = None
        classes["student"] = classes["student"].fillna("").astype(str).str.strip()
        classes["lesson_language"] = classes["lesson_language"].fillna("").astype(str).str.strip()
        classes["modality"] = classes["modality"].fillna("Online").astype(str).str.strip()
        classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
        classes = classes[classes["student"].astype(str).str.len() > 0].copy()

        teach_lang = (
            classes.assign(Lang=classes["lesson_language"].replace({"": "Unknown"}))
            .groupby("Lang", as_index=False)["number_of_lesson"].sum()
            .rename(columns={"number_of_lesson":"Units"})
            .sort_values("Units", ascending=False)
        )
        st.subheader(t("teaching_by_language"))
        st.bar_chart(teach_lang.set_index("Lang")["Units"])

        teach_mod = (
            classes.groupby("modality", as_index=False)["number_of_lesson"].sum()
            .rename(columns={"modality":"Modality","number_of_lesson":"Units"})
            .sort_values("Units", ascending=False)
        )
        st.subheader(t("teaching_by_modality"))
        st.bar_chart(teach_mod.set_index("Modality")["Units"])

    st.divider()
    st.subheader(t("forecast"))
    buffer_days = st.selectbox(
        t("payment_buffer"),
        [0, 7, 14],
        index=0,
        format_func=lambda x: t("on_finish") if x == 0 else f"{x} {t('days_before')}",
        key="forecast_buffer"
    )

    forecast_df = build_forecast_table(payment_buffer_days=int(buffer_days))
    if forecast_df.empty:
        st.info(t("no_data"))
    else:
        st.dataframe(pretty_df(forecast_df), use_container_width=True, hide_index=True)

# =========================
# FALLBACK
# =========================
else:
    go_to("home")
    st.rerun()