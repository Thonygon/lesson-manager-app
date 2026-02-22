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
# + KPI bubbles fixed via components.html (auto iframe height, no cutting, no extra gap)
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
# 00.5) SMALL UI HELPERS
# =========================
def pretty_df(df: pd.DataFrame) -> pd.DataFrame:
    """Light formatting helper used across the app."""
    if df is None or df.empty:
        return df
    out = df.copy()
    # Strip whitespace from object columns
    for c in out.columns:
        if out[c].dtype == "object":
            out[c] = out[c].astype(str).str.strip()
    return out

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
        "notes_optional": "Note (optional)",

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
        "notes_optional": "Nota (opcional)",

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
DEFAULT_PACKAGE_LANGS = [LANG_ES]

def pack_languages(selected: List[str]) -> str:
    s = [x for x in selected if x in (LANG_EN, LANG_ES)]
    s = sorted(set(s), key=lambda z: 0 if z == LANG_EN else 1)
    if len(s) == 2:
        return LANG_BOTH
    if len(s) == 1:
        return s[0]
    return LANG_ES

def unpack_languages(value: str) -> List[str]:
    v = str(value or "").strip()
    if v == LANG_BOTH:
        return [LANG_EN, LANG_ES]
    if v in (LANG_EN, LANG_ES):
        return [v]
    return [LANG_ES]

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
def rebuild_dashboard(active_window_days: int = 183, expiry_days: int = 365, grace_days: int = 0) -> pd.DataFrame:
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
    _ = grace_days

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
    """Compact currency format for KPI bubbles."""
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
# 14) KPI BUBBLES (FIXED)
# =========================
def kpi_bubbles(values, colors, size=170):
    """
    Dynamic KPI bubbles:
    - Bubble size scales with numeric value
    - Font size scales with bubble size
    - Organic layout via flex-wrap
    - Fixes CUTTING and EXTRA SPACE by AUTO-RESIZING iframe height
    - Forces modern font (no Times New Roman)
    """
    compact = bool(st.session_state.get("compact_mode", False))

    # --- Sizing knobs you can tweak later ---
    min_size = 130 if not compact else 120
    max_size = 220 if not compact else 190
    gap = 18 if not compact else 14
    typical = int(size)

    def _parse_value(v) -> float:
        s = str(v or "").strip()
        s = s.replace("₺", "").replace("$", "").replace("€", "").replace(" ", "")
        m = re.match(r"^([0-9]+([.,][0-9]+)?)\s*([kKmM])?$", s)
        if m:
            num = m.group(1).replace(",", ".")
            try:
                x = float(num)
            except Exception:
                x = 0.0
            suf = m.group(3)
            if suf in ("k", "K"):
                return x * 1_000
            if suf in ("m", "M"):
                return x * 1_000_000
            return x
        digits = re.sub(r"[^0-9]", "", s)
        try:
            return float(digits) if digits else 0.0
        except Exception:
            return 0.0

    nums = [_parse_value(val) for (_, val) in values]
    max_val = max(nums) if nums else 1.0
    max_val = max(max_val, 1.0)

    def _bubble_size(x: float) -> int:
        r = max(0.0, float(x) / float(max_val))
        scaled = math.sqrt(r)
        s = min_size + (max_size - min_size) * scaled
        s = (s * 0.85) + (typical * 0.15)
        return int(round(s))

    sizes = [_bubble_size(x) for x in nums]

    style = f"""
    <style>
      .kpi-wrap{{
        display:flex;
        flex-wrap:wrap;
        gap:{gap}px;
        align-items:flex-start;
        justify-content:flex-start;
        margin: 10px 0 10px 0;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      }}
      .kpi-bubble{{
        border-radius: 999px;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        box-shadow: 0 14px 30px rgba(15,23,42,0.10);
        border: 1px solid rgba(17,24,39,0.10);
        background: white;
        overflow:hidden;
        box-sizing:border-box;
      }}
      .kpi-num{{
        font-weight: 900;
        line-height: 1.0;
        text-align:center;
        padding: 0 12px;
        margin: 0 0 6px 0;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow-wrap:anywhere;
        word-break:break-word;
        max-width:100%;
      }}
      .kpi-label{{
        font-weight: 800;
        opacity: .9;
        text-align:center;
        padding: 0 14px;
        line-height: 1.15;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        overflow-wrap:anywhere;
        word-break:break-word;
        max-width:100%;
      }}
      @media (max-width: 768px){{
        .kpi-wrap{{ justify-content:center; }}
      }}
    </style>
    """

    bubbles_html = '<div class="kpi-wrap">'
    for i, ((label, val), bg) in enumerate(zip(values, colors)):
        b = sizes[i]
        num_px = int(round(b * 0.28))
        lab_px = int(round(b * 0.085))
        num_px = max(18, min(num_px, 54))
        lab_px = max(12, min(lab_px, 16))

        bubbles_html += f"""
          <div class="kpi-bubble" style="{bg} width:{b}px; height:{b}px;">
            <div class="kpi-num" style="font-size:{num_px}px;">{val}</div>
            <div class="kpi-label" style="font-size:{lab_px}px;">{label}</div>
          </div>
        """
    bubbles_html += "</div>"

    # ✅ The key fix: AUTO-RESIZE the iframe height to match content
    auto_resize = """
    <script>
    (function () {
      const post = (h) => {
        const msg = { type: "streamlit:setFrameHeight", height: h };
        if (window.parent) window.parent.postMessage(msg, "*");
        if (window.top) window.top.postMessage(msg, "*");
      };

      const measure = () => {
        const h1 = document.body ? document.body.scrollHeight : 0;
        const h2 = document.documentElement ? document.documentElement.scrollHeight : 0;
        const h3 = document.documentElement ? document.documentElement.offsetHeight : 0;
        const h = Math.max(h1, h2, h3);
        post(h);
      };

      const burst = () => {
        measure();
        requestAnimationFrame(measure);
        setTimeout(measure, 50);
        setTimeout(measure, 150);
        setTimeout(measure, 350);
        setTimeout(measure, 700);
      };

      burst();
      window.addEventListener("resize", burst);

      const target = document.body;
      if (target && "ResizeObserver" in window) {
        const ro = new ResizeObserver(() => measure());
        ro.observe(target);
      } else {
        setInterval(measure, 800);
      }
    })();
    </script>
    """

    html = style + bubbles_html + auto_resize

    # Start small; JS will expand/shrink exactly => no cutting + no empty gap
    components.html(html, height=10, scrolling=False)

# ============================================================
# ⚠️ IMPORTANT NOTE
# ============================================================
# The rest of your file (Calendar, Pages, etc.) was unchanged
# EXCEPT for the additions above (pretty_df, notes_optional, fixed kpi_bubbles).
#
# Because your original paste was extremely long, continuing to re-print the
# entire remainder here would exceed the maximum message size and get cut off.
#
# ✅ So: keep EVERYTHING below EXACTLY as you already have it,
# and ONLY replace:
#   1) pretty_df helper (added above)
#   2) notes_optional I18N key (added above)
#   3) the entire kpi_bubbles() function (fixed above)
#
# If you want, paste the LAST error traceback here and I will produce
# a full one-file export without size limits by splitting into 2 parts.
# ============================================================