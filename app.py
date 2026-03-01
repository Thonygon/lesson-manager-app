# ============================================================
# CLASS MANAGER (Single-file Streamlit App)
# Dark HOME + Light APP + Top Nav (NO SIDEBAR)
# + Bilingual UI (EN/ES)
# + Bilingual payments (English/Spanish/English,Spanish)
# + Lesson language (auto + manual when both)
# + Bulk edit payments + bulk edit lessons
# + Analytics upgrades
# + Forecast fixed
# + Calendar overrides UI (reschedule/cancel/notes)
# + KPI bubbles fixed via components.html
# ============================================================

# =========================
# 00) IMPORTS
# =========================
import streamlit as st
import pandas as pd
import math
import json
import re
import urllib.parse
import base64
import os
import plotly.express as px
import uuid
import streamlit.components.v1 as components
from zoneinfo import ZoneInfo
from supabase import create_client
from datetime import datetime, date, timedelta, timezone
from typing import List, Tuple, Optional, Dict

LOCAL_TZ = ZoneInfo("Europe/Istanbul")
UTC_TZ = timezone.utc

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
# 01.1) PAGE CONFIG
# =========================
def remove_streamlit_top_spacing():
    st.markdown(
        """
        <style>
        /* --- Remove Streamlit chrome --- */
        header, [data-testid="stHeader"] { display:none !important; height:0 !important; }
        [data-testid="stToolbar"] { display:none !important; height:0 !important; }
        div[data-testid="stDecoration"] { display:none !important; height:0 !important; }

        /* --- Kill top padding everywhere Streamlit may add it --- */
        html, body { margin:0 !important; padding:0 !important; }

        [data-testid="stAppViewContainer"] { padding-top:0 !important; margin-top:0 !important; }
        [data-testid="stMain"] { padding-top:0 !important; margin-top:0 !important; }

        /* Newer Streamlit main container */
        div[data-testid="stMainBlockContainer"]{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }

        /* Some builds wrap it differently */
        section[data-testid="stMain"] > div {
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }

        /* Legacy */
        .block-container{
          padding-top: 0rem !important;
          margin-top: 0rem !important;
        }

        /* If Streamlit injects a top padding via inline style, force it off */
        div.block-container { padding-top: 0rem !important; }

        </style>
        """,
        unsafe_allow_html=True,
    )

remove_streamlit_top_spacing()

# =========================
# 02) I18N (EN/ES) ✅ (CURATED FULL APP DICTIONARY)
# =========================
I18N: Dict[str, Dict[str, str]] = {
    "en": {
        # -------------------------
        # NAV / PAGES
        # -------------------------
        "menu": "Menu",
        "home": "Home",
        "dashboard": "Dashboard",
        "students": "Students",
        "lessons": "Lessons",
        "lesson": "Lesson",
        "payments": "Payments",
        "payment": "Payment",
        "schedule": "Schedule",
        "calendar": "Calendar",
        "analytics": "Analytics",

        # -------------------------
        # HOME / TOP NAV
        # -------------------------
        "choose_where_to_go": "Choose where you want to go",
        "language_ui": "Language",
        "english": "English",
        "spanish": "Spanish",
        "both": "English & Spanish",
        "compact_mode": "Mobile mode",
        "welcome": "Welcome",
        "alerts": "Alerts",
        "settings": "Settings",
        "home_slogan": "One student is all it takes to start",
        "find_private_students": "Find private students",
        "home_find_students": "Find private students",
        "home_menu_title": "Manage current students",
        "ytd_income": "YTD income",
        "next": "Next lesson",
        "goal": "Goal",
        "completed": "Completed",

        # -------------------------
        # COMMON ACTIONS / STATES
        # -------------------------
        "add": "Add",
        "save": "Save",
        "delete": "Delete",
        "reset": "Reset",
        "view": "View",
        "search": "Search",
        "select_student": "Select a student",
        "select_year": "Select year",
        "apply_changes": "Apply changes",
        "warning_apply": "Be careful. Changes are applied immediately.",
        "no_data": "No data yet.",
        "no_students": "No students found yet.",
        "no_events": "No events found.",
        "saved": "Saved ✅",
        "updated": "Updated ✅",
        "deleted": "Deleted ✅",
        "some_updates_failed": "Some updates failed.",
        "delete_failed": "Delete failed",
        "delete_warning_undo": "I understand this cannot be undone",

        # -------------------------
        # COMMON LABELS
        # -------------------------
        "student": "Student",
        "date": "Date",
        "time": "Time",
        "weekday": "Weekday",
        "units": "Units",
        "modality": "Modality",
        "online": "Online",
        "offline": "Offline",
        "lesson_language": "Lesson language",
        "package_languages": "Package languages",
        "languages": "Languages",
        "note": "Note",
        "notes": "Notes",
        "notes_optional": "Note (optional)",
        "unknown": "Unknown",
        "id": "ID",
        "year": "Year",
        "month": "Month",
        "day": "Day",
        "income": "Income",

        # -------------------------
        # DASHBOARD
        # -------------------------
        "manage_current_students": "Manage your current students and packages",
        "take_action": "Take Action",
        "academic_status": "Academic status",
        "current_packages": "Current packages",
        "mismatches": "Mismatches",
        "normalize": "Normalize",
        "all_good_no_action_required": "All good! No action required ✅",
        "whatsapp_message": "WhatsApp message",
        "open_whatsapp": "Open WhatsApp",
        "contact_student": "Contact the student",
        "lessons_left": "Lessons left",
        "last_lesson_date": "Last lesson date",

        # status (canonical + UI)
        "status": "Status",
        "active": "Active",
        "finished": "Finished",
        "mismatch": "Mismatch",
        "almost_finished": "Almost finished",
        "dropout": "Dropout",
        "action_finish_soon": "Finish soon",

        # mismatch table labels (snake_case columns shown)
        "overused_units": "Overused units",
        "lessons_left_units": "Units left",
        "lessons_taken_units": "Units taken",
        "lessons_paid_total": "Lessons paid",
        "payment_date": "Payment date",
        "package_start_date": "Package start date",
        "package_expiry_date": "Package expiry date",
        "payment_id": "Payment ID",
        "normalize_allowed": "Normalization allowed",
        "total_paid": "Price paid",
        "is_active_6m": "Active",

        # today
        "todays_lessons": "Today's lessons",
        "open_link": "Join lesson",
        "mark_done": "Mark as done",
        "no_events_today": "No events for today. Take a cup of coffee ☕.",
        "online": "Online",

        # -------------------------
        # STUDENTS PAGE
        # -------------------------
        "add_and_manage_students": "Add and manage students",
        "add_new": "Add new",
        "new_student_name": "New student name",
        "student_profile": "Student profile",
        "student_list": "Student list",
        "student_history": "Student history",
        "delete_student": "Delete student",
        "delete_student_warning": "This deletes the student profile. Lessons/payments remain in the database unless you delete them separately.",
        "confirm_delete_student": "I understand and want to delete this student",

        # student profile fields
        "email": "Email",
        "zoom_link": "Zoom link",
        "whatsapp_phone": "WhatsApp phone",
        "examples_phone": "Example: +90 555 555 55 55",
        "calendar_color": "Calendar color",
        "phone_warning_short": "Phone seems short/ambiguous. Use international format for direct WhatsApp chat.",

        # -------------------------
        # LESSONS PAGE
        # -------------------------
        "keep_track_of_your_lessons": "Record lessons and keep track of attendance",
        "record_attendance": "Take attendance",
        "lesson_editor": "Lesson editor",
        "delete_lesson": "Delete lesson",
        "delete_lesson_help": "Use this if you registered a lesson by mistake.",
        "lesson_id": "Lesson ID",
        "lesson_date": "Lesson date",

        # -------------------------
        # PAYMENTS PAGE
        # -------------------------
        "add_and_manage_your_payments": "Add and manage your payments",
        "paid_amount": "Paid amount",
        "lessons_paid": "Lessons paid",
        "starts_different": "First lesson starts on a different date",
        "package_start": "Package start date",
        "package_expiry": "Package expiry date",
        "adjust_units": "Adjustment units",
        "package_normalized": "Normalized",
        "normalized_note": "Normalization note",
        "normalized_at": "Normalized at",
        "payment_editor": "Payment editor",
        "delete_payment": "Delete payment",
        "delete_payment_help": "Use this if you registered a payment by mistake.",
        "payment_deleted": "Payment deleted ✅",
        "adjustment_units": "Adjusted units",

        # -------------------------
        # CALENDAR PAGE
        # -------------------------
        "create_and_manage_your_weekly_program": "Create and manage your weekly program",
        "today": "Today",
        "this_week": "This week",
        "this_month": "This month",
        "filter_students": "Filter students",
        "schedule_id": "Schedule ID",
        "time_hhmm": "Time (HH:MM)",
        "duration_min": "Duration (min)",
        "active_flag": "Active",
        "current_schedule": "Current schedule",
        "delete_scheduled_lesson": "Delete a scheduled lesson",
        "delete_schedule_warning": "Be careful! This deletes permanently.",
        "id": "ID", 
        "student": "Student", 
        "weekday": "Weekday", 
        "time": "Time", 
        "duration_minutes": "Duration (min)", 
        "active": "Active",

        # overrides
        "modify_calendar": "Modify calendar",
        "cancel_or_reschedule": "Cancel or reschedule a lesson",
        "override_student": "Student",
        "override_original_date": "Original date",
        "override_status": "Status",
        "override_scheduled": "Rescheduled",
        "override_cancel": "Cancelled",
        "override_new_date": "New date",
        "override_new_time_hhmm": "New time (HH:MM)",
        "override_duration": "Duration (min)",
        "override_note": "Note",
        "previous_changes": "Previous changes",
        "change": "Change",
        "select_new_date_time": "Please select a new date & time.",
        "override_save_failed": "Could not save override.",
        "override_delete_failed": "Could not delete override.",
        "override_id": "Override ID",
        "original_date": "Original date",
        "new_datetime": "New date",

        # -------------------------
        # ANALYTICS PAGE
        # -------------------------
        "view_your_income_and_business_indicators": "View your income and business indicators",
        "all_time_income": "All-time income",
        "yearly": "Yearly",
        "monthly": "Monthly",
        "weekly": "Weekly",
        "all_time_monthly_income": "All Time Monthly Income",
        "monthly_income": "Monthly income",
        "yearly_income": "Yearly Income",
        "yearly_totals": "Yearly totals",
        "weekly_income": "Weekly Income",
        "last_7_days": "Last 7 days",
        "most_profitable_students": "Most profitable students",
        "packages_by_language": "Packages by language",
        "packages_by_modality": "Packages by modality",
        "lessons_by_language": "Lessons by language",
        "lessons_by_modality": "Lessons by modality",
        "estimated_finish_date": "Estimated finish date",
        "reminder_date": "Reminder date",


        # forecast inside analytics
        "forecast": "Forecast",
        "payment_buffer": "Reminder buffer",
        "on_finish": "On finish date",
        "days_before": "days before",
        "units_per_day": "Classes per day",

        # -------------------------
        # MISSING KEYS
        # -------------------------
        "manage_students": "Manage students",
        "done_ok": "Done ✅",
        "normalize_failed": "Normalization failed.",
        "normalized_default_note": "Package normalized / adjustment applied.",
        "package_normalized": "Package normalized",
        "packages_bought": "Total packages",
        # =========================
        # PRICING SECTION
        # =========================

        "pricing_editor_title": "💳 Pricing & Packages",

        "pricing_online_title": "Online lessons",
        "pricing_offline_title": "Face-to-face lessons",

        "pricing_hourly_caption": "Hourly (pay each lesson)",
        "pricing_hourly_price_label": "Hourly price",
        "pricing_hourly_updated": "Hourly price updated ✅",
        "pricing_hourly_load_error": "Could not create/load hourly row. Check RLS/policies.",

        "pricing_no_packages": "No packages yet. Add one below.",

        "pricing_edit": "Edit",
        "pricing_save": "Save",
        "pricing_delete": "Delete",

        "pricing_package_updated": "Package updated ✅",
        "pricing_package_deleted": "Package deleted ✅",
        "pricing_package_added": "Package added ✅",

        "pricing_hours": "Hours",
        "pricing_price_label": "Price (TL)",
        "pricing_per_hour": "per hour",

        "pricing_add_package": "Add a package",
        "pricing_add": "Add",
        
        # -------------------------
        # WHATSAPP (DASHBOARD)
        # -------------------------
        "whatsapp_templates_title": "WhatsApp Templates",
        "whatsapp_message_language": "Message language",
        "whatsapp_choose_template": "Choose a template",

        "whatsapp_tpl_package": "1) Package offer",
        "whatsapp_tpl_confirm": "2) Confirm lesson",
        "whatsapp_tpl_cancel": "3) Cancel lesson",

        "whatsapp_no_students_for_template": "No students available for this template right now.",
    },

    "es": {
        # -------------------------
        # NAV / PAGES
        # -------------------------
        "menu": "Menú",
        "home": "Inicio",
        "dashboard": "Panel",
        "students": "Estudiantes",
        "lessons": "Clases",
        "lesson": "Clase",
        "payments": "Pagos",
        "payment": "Pago",
        "schedule": "Horario",
        "calendar": "Calendario",
        "analytics": "Analítica",

        # -------------------------
        # HOME / TOP NAV
        # -------------------------
        "choose_where_to_go": "Elige a dónde quieres ir",
        "language_ui": "Idioma",
        "english": "Inglés",
        "spanish": "Español",
        "both": "Inglés & Español",
        "compact_mode": "Modo móvil",
        "welcome": "Bienvenido",
        "alerts": "Alertas",
        "settings": "Ajustes",
        "home_slogan": "Solo un estudiante basta",
        "home_find_students": "Encuentra estudiantes privados",
        "home_menu_title": "Gestiona estudiantes actuales",
        "next": "Siguiente clase",
        "goal": "Meta",
        "completed": "Completado",
        "ytd_income": "Ingreso del año",

        # -------------------------
        # COMMON ACTIONS / STATES
        # -------------------------
        "add": "Añadir",
        "save": "Guardar",
        "delete": "Eliminar",
        "reset": "Reiniciar",
        "view": "Vista",
        "search": "Buscar",
        "select_student": "Selecciona un estudiante",
        "select_year": "Selecciona un año",
        "apply_changes": "Aplicar cambios",
        "warning_apply": "Ten cuidado. Los cambios se aplican de inmediato.",
        "no_data": "Aún no hay datos.",
        "no_students": "Aún no hay estudiantes.",
        "no_events": "No hay eventos.",
        "saved": "Guardado ✅",
        "updated": "Actualizado ✅",
        "deleted": "Eliminado ✅",
        "some_updates_failed": "Algunos cambios fallaron.",
        "delete_failed": "Error al eliminar",
        "delete_warning_undo": "Entiendo que no se puede deshacer",

        # -------------------------
        # COMMON LABELS
        # -------------------------
        "student": "Estudiante",
        "date": "Fecha",
        "time": "Hora",
        "weekday": "Día de la semana",
        "units": "Unidades",
        "modality": "Modalidad",
        "online": "Online",
        "offline": "Presencial",
        "lesson_language": "Idioma de la clase",
        "package_languages": "Idiomas del paquete",
        "languages": "Idiomas",
        "note": "Nota",
        "notes": "Notas",
        "notes_optional": "Nota (opcional)",
        "unknown": "Desconocido",
        "id": "ID",
        "year": "Año",
        "month": "Mes",
        "day": "Día",
        "income": "Ingresos",

        # -------------------------
        # DASHBOARD
        # -------------------------
        "manage_current_students": "Administra tus estudiantes y paquetes actuales",
        "take_action": "Toma acción",
        "current_packages": "Packets actuales",
        "academic_status": "Estado académico",
        "mismatches": "Descuadres",
        "normalize": "Normalizar",
        "all_good_no_action_required": "¡Todo bien! No se requiere acción ✅",
        "whatsapp_message": "Mensaje de WhatsApp",
        "open_whatsapp": "Abrir WhatsApp",
        "contact_student": "Contactar al estudiante",
        "lessons_left": "Clases restantes",
        "last_lesson_date": "Fecha de última clase",

        # status (canonical + UI)
        "status": "Estado",
        "active": "Activo",
        "finished": "Finalizado",
        "mismatch": "Descuadre",
        "almost_finished": "Por terminar",
        "dropout": "Desertor",
        "action_finish_soon": "Termina pronto",

        # mismatch table labels (snake_case columns shown)
        "overused_units": "Unidades excedidas",
        "lessons_left_units": "Unidades restantes",
        "lessons_taken_units": "Unidades tomadas",
        "lessons_paid_total": "Clases pagadas",
        "payment_date": "Fecha de pago",
        "package_start_date": "Inicio del paquete",
        "package_expiry_date": "Fin del paquete",
        "payment_id": "ID del pago",
        "normalize_allowed": "Normalización permitida",
        "total_paid": "Monto pagado",
        "is_active_6m": "Activo",

        # today
        "todays_lessons": "Clases de hoy",
        "open_link": "Conectate",
        "mark_done": "Marcar como hecha",
        "no_events_today": "No hay eventos hoy. Toma una taza de café ☕.",
        "online": "En línea",

        # -------------------------
        # STUDENTS PAGE
        # -------------------------
        "add_and_manage_students": "Añade y gestiona estudiantes",
        "add_new": "Añadir nuevo",
        "new_student_name": "Nombre del nuevo estudiante",
        "student_profile": "Perfil del estudiante",
        "student_list": "Lista de estudiantes",
        "student_history": "Historial del estudiante",
        "delete_student": "Eliminar estudiante",
        "delete_student_warning": "Esto elimina el perfil del estudiante. Las clases/pagos permanecen en la base de datos a menos que los elimines por separado.",
        "confirm_delete_student": "Entiendo y quiero eliminar este estudiante",

        # student profile fields
        "email": "Correo",
        "zoom_link": "Enlace de Zoom",
        "whatsapp_phone": "Teléfono de WhatsApp",
        "examples_phone": "Ejemplo: +90 555 555 55 55",
        "calendar_color": "Color del calendario",
        "phone_warning_short": "El teléfono parece corto/ambiguo. Usa formato internacional para abrir WhatsApp directo.",

        # -------------------------
        # LESSONS PAGE
        # -------------------------
        "keep_track_of_your_lessons": "Registra clases y controla la asistencia",
        "record_attendance": "Registra asistencia",
        "lesson_editor": "Editor de clases",
        "delete_lesson": "Eliminar clase",
        "delete_lesson_help": "Usa esto si registraste una clase por error.",
        "lesson_id": "ID de clase",
        "lesson_date": "Fecha de clase",

        # -------------------------
        # PAYMENTS PAGE
        # -------------------------
        "add_and_manage_your_payments": "Añade y gestiona tus pagos",
        "paid_amount": "Monto pagado",
        "lessons_paid": "Clases pagadas",
        "starts_different": "La primera clase comienza en otra fecha",
        "package_start": "Inicio del paquete",
        "package_expiry": "Fin del paquete",
        "adjust_units": "Unidades de ajuste",
        "package_normalized": "Normalizado",
        "normalized_note": "Nota de normalización",
        "normalized_at": "Normalizado el",
        "payment_editor": "Editor de pagos",
        "delete_payment": "Eliminar pago",
        "delete_payment_help": "Usa esto si registraste un pago por error.",
        "payment_deleted": "Pago eliminado ✅",
        "adjustment_units": "Unidades ajustadas",

        # -------------------------
        # CALENDAR PAGE
        # -------------------------
        "create_and_manage_your_weekly_program": "Crea y gestiona tu programa semanal",
        "today": "Hoy",
        "this_week": "Esta semana",
        "this_month": "Este mes",
        "filter_students": "Filtrar estudiantes",
        "schedule_id": "ID del horario",
        "time_hhmm": "Hora (HH:MM)",
        "duration_min": "Duración (min)",
        "active_flag": "Activo",
        "current_schedule": "Horario actual",
        "delete_scheduled_lesson": "Eliminar una clase programada",
        "delete_schedule_warning": "¡Cuidado! Esto se elimina permanentemente.",
        "id": "ID", 
        "student": "estudiante", 
        "weekday": "Día de la sema", 
        "time": "Hora", 
        "duration_minutes": "Duración (min)", 
        "active": "Activo",

        # overrides
        "modify_calendar": "Modificar calendario",
        "cancel_or_reschedule": "Cancelar o reprogramar una clase",
        "override_student": "Estudiante",
        "override_original_date": "Fecha original",
        "override_status": "Estado",
        "override_scheduled": "Reprogramada",
        "override_cancel": "Cancelada",
        "override_new_date": "Nueva fecha",
        "override_new_time_hhmm": "Nueva hora (HH:MM)",
        "override_duration": "Duración (min)",
        "override_note": "Nota",
        "previous_changes": "Cambios anteriores",
        "change": "Cambiar",
        "select_new_date_time": "Por favor selecciona nueva fecha y hora.",
        "override_save_failed": "No se pudo guardar el cambio.",
        "override_delete_failed": "No se pudo eliminar el cambio.",
        "override_id": "ID del cambio",
        "original_date": "Fecha original",
        "new_datetime": "Fecha nueva",

        # -------------------------
        # ANALYTICS PAGE
        # -------------------------
        "view_your_income_and_business_indicators": "Consulta tus ingresos e indicadores de negocio",
        "all_time_income": "Ingresos históricos",
        "yearly": "Anual",
        "monthly": "Mensual",
        "weekly": "Semanal",
        "all_time_monthly_income": "Ingresos mensuales históricos",
        "monthly_income": "Ingresos mensuales",
        "yearly_income": "Ingresos anuales",
        "yearly_totals": "Totales anuales",
        "weekly_income": "Ingresos semanales",
        "last_7_days": "Últimos 7 días",
        "most_profitable_students": "Estudiantes más rentables",
        "packages_by_language": "Paquetes por idioma",
        "packages_by_modality": "Paquetes por modalidad",
        "lessons_by_language": "Clases por idioma",
        "lessons_by_modality": "Clases por modalidad",
        "units_per_day": "Clases por día",
        "estimated_finish_date": "Fecha de cierre estimada",
        "reminder_date": "Fecha de recordatorio",

        # forecast inside analytics
        "forecast": "Proyección",
        "payment_buffer": "Margen de recordatorio",
        "on_finish": "En la fecha de finalización",
        "days_before": "días antes",
        # -------------------------
        # MISSING KEYS
        # -------------------------
        "manage_students": "Gestionar estudiantes",
        "done_ok": "Listo ✅",
        "normalize_failed": "Falló la normalización.",
        "normalized_default_note": "Paquete normalizado / ajuste aplicado.",
        "package_normalized": "Paquete normalizado",
        "packages_bought": "Paquetes comprados",
        "add_student": "Añadir estudiante",

        # =========================
        # PRICING SECTION
        # =========================

        "pricing_editor_title": "💳 Precios y Paquetes",

        "pricing_online_title": "Clases en línea",
        "pricing_offline_title": "Clases presenciales",

        "pricing_hourly_caption": "Por hora (paga cada clase)",
        "pricing_hourly_price_label": "Precio por hora",
        "pricing_hourly_updated": "Precio por hora actualizado ✅",
        "pricing_hourly_load_error": "No se pudo crear/cargar la tarifa por hora. Revisa RLS/políticas.",

        "pricing_no_packages": "Aún no hay paquetes. Agrega uno abajo.",

        "pricing_edit": "Editar",
        "pricing_save": "Guardar",
        "pricing_delete": "Eliminar",

        "pricing_package_updated": "Paquete actualizado ✅",
        "pricing_package_deleted": "Paquete eliminado ✅",
        "pricing_package_added": "Paquete agregado ✅",

        "pricing_hours": "Horas",
        "pricing_price_label": "Precio (TL)",
        "pricing_per_hour": "por hora",

        "pricing_add_package": "Agregar un paquete",
        "pricing_add": "Agregar",
        
        # -------------------------
        # WHATSAPP (DASHBOARD)
        # -------------------------
        "whatsapp_templates_title": "Plantillas de WhatsApp",
        "whatsapp_message_language": "Idioma del mensaje",
        "whatsapp_choose_template": "Elige una plantilla",

        "whatsapp_tpl_package": "1) Enviar paquetes",
        "whatsapp_tpl_confirm": "2) Confirmar clase",
        "whatsapp_tpl_cancel": "3) Cancelar clase",

        "whatsapp_no_students_for_template": "No hay estudiantes disponibles para esta plantilla en este momento.",
    },

    "tr": {
        # -------------------------
        # WHATSAPP (DASHBOARD)
        # -------------------------
        "whatsapp_templates_title": "WhatsApp Şablonları",
        "whatsapp_message_language": "Mesaj dili",
        "whatsapp_choose_template": "Şablon seç",

        "whatsapp_tpl_package": "1) Paket bitti / bitmek üzere",
        "whatsapp_tpl_confirm": "2) Bugünkü dersi teyit et",
        "whatsapp_tpl_cancel": "3) Bugünkü dersi iptal et",

        "whatsapp_no_students_for_template": "Şu anda bu şablon için uygun öğrenci yok.",
    }
 }
if "ui_lang" not in st.session_state:
    st.session_state.ui_lang = "en"

if "compact_mode" not in st.session_state:
    st.session_state.compact_mode = False


def t(key: str) -> str:
    lang = st.session_state.get("ui_lang", "en")
    d = I18N.get(lang, I18N["en"])

    k = str(key or "").strip()
    if not k:
        return ""

    # exact match
    if k in d:
        return d[k]

    # normalized match: "Most profitable students" -> "most_profitable_students"
    k2 = k.casefold().replace(" ", "_")
    if k2 in d:
        return d[k2]

    # fallback to English
    d_en = I18N["en"]
    if k in d_en:
        return d_en[k]
    if k2 in d_en:
        return d_en[k2]

    return k

# =========================
# 03) SMALL UI HELPERS
# =========================
def to_dt_naive(x, utc: bool = True):
    """
    Parse to pandas datetime and return tz-naive timestamps.

    - If x is a Series/array-like -> returns a Series[datetime64[ns]] (tz-naive)
    - If x is scalar -> returns a Timestamp or NaT (tz-naive)
    - If utc=True -> parse/convert to UTC then drop tz
    """
    s = pd.to_datetime(x, errors="coerce", utc=utc)

    # Series path
    if isinstance(s, pd.Series):
        try:
            return s.dt.tz_convert(None)  # tz-aware -> drop tz
        except Exception:
            return s  # already tz-naive or not datetimelike

    # Scalar path
    try:
        if getattr(s, "tzinfo", None) is not None:
            return s.tz_convert(None)
        return s
    except Exception:
        return s


def ts_today_naive() -> pd.Timestamp:
    # Always tz-naive "today" at midnight
    return pd.Timestamp.now().normalize().tz_localize(None)


def pretty_df(df: pd.DataFrame) -> pd.DataFrame:
    """Light formatting helper used across the app (values only; keeps column names)."""
    if df is None or df.empty:
        return df

    out = df.copy()

    # Trim object columns
    for c in out.columns:
        if out[c].dtype == "object":
            out[c] = out[c].astype(str).str.strip()

    return out


def translate_df_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Translate dataframe column headers using t() with robust normalization."""
    if df is None or df.empty:
        return df

    out = df.copy()

    def norm_key(col: str) -> str:
        k = str(col or "").strip()
        k = k.replace("-", " ").replace("/", " ")
        k = re.sub(r"\s+", " ", k)

        # normalize common display variants
        k = k.replace(" ID", " Id")
        k = k.replace("Id", "ID")
        k = k.replace("ID", " id ")

        k = k.strip().casefold()
        k = k.replace(" ", "_")
        k = re.sub(r"__+", "_", k).strip("_")
        return k

    out.columns = [t(norm_key(c)) for c in out.columns]
    return out


def translate_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Translate headers + common coded values (Status/Modality/Languages) when present.
    Works for snake_case or pretty title columns.
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    # headers
    out = translate_df_headers(out)

    cols = set(out.columns.astype(str))

    # values
    for status_col in [t("status"), "Status", "status"]:
        if status_col in cols:
            out[status_col] = out[status_col].astype(str).str.strip().str.casefold().apply(translate_status)

    for mod_col in [t("modality"), "Modality", "modality"]:
        if mod_col in cols:
            out[mod_col] = out[mod_col].astype(str).apply(translate_modality_value)

    for lang_col in [t("languages"), "Languages", "languages"]:
        if lang_col in cols:
            out[lang_col] = out[lang_col].astype(str).apply(translate_language_value)

    return out


def chart_series(df: pd.DataFrame, index_col: str, value_col: str, index_key: str, value_key: str):
    """
    Builds a Series for Streamlit charts with translated axis labels.
    index_key/value_key are I18N keys (e.g., "student", "income").
    """
    if df is None or df.empty or index_col not in df.columns or value_col not in df.columns:
        return None

    s = df[[index_col, value_col]].copy()
    s[index_col] = s[index_col].astype(str)
    s[value_col] = pd.to_numeric(s[value_col], errors="coerce").fillna(0.0)

    series = s.set_index(index_col)[value_col]
    series.index.name = t(index_key)
    series.name = t(value_key)
    return series


def dash_chart_series(
    df: pd.DataFrame,
    group_col: str,
    group_key_for_label: str,
    value_key_for_label: str,
) -> Optional[pd.Series]:
    """
    Build a Series for st.bar_chart with translated:
      - series name (e.g. "Students")
      - index name (e.g. "Status", "Modality", "Languages")
      - index values when they are coded (status/modality/languages)
    """
    if df is None or df.empty or group_col not in df.columns:
        return None

    tmp = df.copy()
    tmp[group_col] = tmp[group_col].fillna("").astype(str).str.strip()
    tmp = tmp[tmp[group_col].astype(str).str.len() > 0]
    if tmp.empty:
        return None

    s = tmp.groupby(group_col).size().sort_values(ascending=False)

    # Translate index values when needed
    if group_col.casefold() == "status":
        s.index = [translate_status(x) for x in s.index.astype(str)]
    elif group_col.casefold() == "modality":
        s.index = [translate_modality_value(x) for x in s.index.astype(str)]
    elif group_col.casefold() == "languages":
        s.index = [translate_language_value(x) for x in s.index.astype(str)]

    s.index.name = t(group_key_for_label)
    s.name = t(value_key_for_label)
    return s


# =========================
# 03.1) APP SETTINGS (GOALS) HELPERS — upgraded
# =========================
def _guess_user_id() -> str:
    for k in ("user_id", "uid", "owner_id"):
        v = st.session_state.get(k, None)
        if v:
            return str(v).strip()
    return "default"


def _first_col(df: pd.DataFrame, candidates) -> str | None:
    if df is None or df.empty:
        return None
    norm = {str(c).strip().casefold(): c for c in df.columns}
    for cand in candidates:
        k = str(cand).strip().casefold()
        if k in norm:
            return norm[k]
    return None


def _parse_float_loose(v, default=0.0) -> float:
    """
    Parses numbers from: 150000, 150.000, 150,000, '150000 TL', Decimal, etc.
    """
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return float(default)
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == "":
            return float(default)

        # remove currency/text
        s = re.sub(r"[^\d,.\-]", "", s)

        # handle "150.000" as 150000 (common in TR) if no comma decimals pattern
        # Strategy:
        # - If both ',' and '.' exist -> assume thousand separators, remove both then parse
        # - If only '.' exists and it's like 150.000 -> treat as thousands separator -> remove dots
        # - If only ',' exists -> could be decimal OR thousands; for goals usually thousands -> remove commas
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", "")
        elif "." in s:
            # if dot groups of 3 at end -> thousands
            if re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
                s = s.replace(".", "")
        elif "," in s:
            if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):
                s = s.replace(",", "")
            else:
                # could be decimal comma, convert to dot
                s = s.replace(",", ".")

        return float(s)
    except Exception:
        return float(default)


def load_app_setting(key: str, default=None, key_fallbacks: list[str] | None = None):
    """
    Reads setting from `app_settings`.
    Supports schema:
      - (key, value)
      - (user_id, key, value)
    Also supports flexible column names.
    """
    try:
        df = load_table("app_settings")
    except Exception:
        return default

    if df is None or df.empty:
        return default

    key_col = _first_col(df, ["key", "setting_key", "name"])
    val_col = _first_col(df, ["value", "setting_value", "val"])
    uid_col = _first_col(df, ["user_id", "uid", "owner_id"])

    if not key_col or not val_col:
        return default

    keys_to_try = [str(key).strip()]
    if key_fallbacks:
        keys_to_try += [str(k).strip() for k in key_fallbacks if str(k).strip()]

    tmp = df.copy()
    tmp[key_col] = tmp[key_col].astype(str).str.strip()

    # Prefer user-specific row if available; fallback to any if none found
    if uid_col:
        uid = _guess_user_id()
        tmp[uid_col] = tmp[uid_col].astype(str).str.strip()

        user_rows = tmp[(tmp[uid_col] == uid) & (tmp[key_col].isin(keys_to_try))]
        if not user_rows.empty:
            v = user_rows.iloc[0][val_col]
            return _parse_float_loose(v, default) if isinstance(default, (int, float)) else v

        any_rows = tmp[tmp[key_col].isin(keys_to_try)]
        if any_rows.empty:
            return default
        v = any_rows.iloc[0][val_col]
        return _parse_float_loose(v, default) if isinstance(default, (int, float)) else v

    # no uid column
    rows = tmp[tmp[key_col].isin(keys_to_try)]
    if rows.empty:
        return default
    v = rows.iloc[0][val_col]
    return _parse_float_loose(v, default) if isinstance(default, (int, float)) else v


def save_app_setting(key: str, value, key_fallbacks: list[str] | None = None) -> bool:
    """
    Upsert setting into `app_settings`.
    If table has user_id, writes under current user.
    """
    try:
        df = load_table("app_settings")
    except Exception:
        df = pd.DataFrame()

    uid_col = _first_col(df, ["user_id", "uid", "owner_id"]) if (df is not None and not df.empty) else None
    key_col = _first_col(df, ["key", "setting_key", "name"]) or "key"
    val_col = _first_col(df, ["value", "setting_value", "val"]) or "value"

    payload = {key_col: str(key).strip(), val_col: value}
    on_conflict = key_col

    if uid_col:
        payload[uid_col] = _guess_user_id()
        on_conflict = f"{uid_col},{key_col}"

    client = supabase_admin if ("supabase_admin" in globals() and supabase_admin is not None) else supabase

    try:
        client.table("app_settings").upsert(payload, on_conflict=on_conflict).execute()
        # if you use @st.cache_data anywhere, this forces fresh reads
        try:
            st.cache_data.clear()
        except Exception:
            pass
        return True
    except Exception:
        return False


def get_year_goal_progress_snapshot(year: int | None = None, goal_key: str = "yearly_income_goal") -> dict:
    today = ts_today_naive()
    yr = int(year or today.year)

    goal = load_app_setting(
        goal_key,
        default=0.0,
        key_fallbacks=["annual_income_goal", "year_income_goal", "income_goal_year"],
    )
    goal = _parse_float_loose(goal, 0.0)

    # YTD income from payments
    ytd = 0.0
    try:
        p = load_table("payments")
        if p is not None and not p.empty:
            if "payment_date" not in p.columns:
                p["payment_date"] = None
            if "paid_amount" not in p.columns:
                p["paid_amount"] = 0.0

            p = p.copy()
            p["payment_date"] = to_dt_naive(p["payment_date"], utc=True)
            p["paid_amount"] = pd.to_numeric(p["paid_amount"], errors="coerce").fillna(0.0).astype(float)
            p = p.dropna(subset=["payment_date"])
            p = p[p["payment_date"].dt.year == yr]
            ytd = float(p["paid_amount"].sum())
    except Exception:
        ytd = 0.0

    progress = 0.0
    if goal > 0:
        progress = max(0.0, min(1.0, ytd / goal))

    remaining = max(0.0, goal - ytd)

    return {"year": yr, "goal": float(goal), "ytd_income": float(ytd), "progress": float(progress), "remaining": float(remaining)}

def upload_avatar_to_supabase(file, user_id: str) -> str:
    if file is None:
        return ""

    if not (file.type or "").startswith("image/"):
        raise ValueError("Please upload an image file.")

    ext = (file.name.split(".")[-1] or "png").lower()
    object_path = f"{user_id}/{uuid.uuid4().hex}.{ext}"

    # ✅ Upload using ADMIN client (bypasses RLS)
    supabase_admin.storage.from_("avatars").upload(
        path=object_path,
        file=file.getvalue(),
        file_options={"content-type": file.type, "upsert": "true"},
    )

    # If bucket is public:
    return supabase_admin.storage.from_("avatars").get_public_url(object_path)


def render_home_indicator(
    status: str = t("online"),
    badge: str = t("today"),
    items=None,                     # list[tuple[str,str]]
    progress: float | None = None,  # 0..1
    accent: str = "#3B82F6",
    progress_label: str | None = None,  # e.g. "completed" / t("completed")
):
    if items is None:
        items = [
            ("students", "0"),
            ("ydt_income", "₺0"),
            ("goal", "0"),
            ("next", "no_events"),
        ]

    if progress_label is None:
        progress_label = t("completed")

    # progress percent
    pct = None
    if progress is not None:
        try:
            pct = int(round(max(0.0, min(1.0, float(progress))) * 100))
        except Exception:
            pct = None

    kpis_html = "".join(
        f"""
        <div class="home-indicator-kpi">
          <div class="k">{lbl}</div>
          <div class="v">{val}</div>
        </div>
        """
        for (lbl, val) in items
    )

    badge_html = ""
    if badge:
        badge_html = f'<span class="home-indicator-badge">{badge}</span>'

    right_html = ""
    if pct is not None:
        right_html = f"""
        <div class="home-indicator-mini">{pct}% {progress_label}</div>
        <div class="home-indicator-progress">
          <div style="width:{pct}%;"></div>
        </div>
        """

    html = f"""
<div class="home-indicator-wrap">
  <div class="home-indicator">

    <div class="home-indicator-left">
      <div class="home-indicator-dot"></div>
      <div class="home-indicator-title">
        <div class="s">{status} {badge_html}</div>
      </div>
    </div>

    <div class="home-indicator-mid">
      {kpis_html}
    </div>

    <div class="home-indicator-right">
      {right_html}
    </div>

  </div>
</div>

<style>
.home-indicator-wrap {{
  width: 100%;
  margin: 0.25rem 0 1.0rem 0;
}}

.home-indicator {{
  display: flex;
  align-items: center;
  justify-content: center-justified;
  gap: 14px;

  padding: 14px 16px;
  border-radius: 18px;

  background: linear-gradient(
      135deg,
      rgba(59,130,246,0.12),
      rgba(255,255,255,0.10)
  );
  border: 1px solid rgba(59,130,246,0.25);
  box-shadow: 0 10px 28px rgba(37,99,235,0.18);
  color: rgba(255,255,255,0.95);   
  }}

.home-indicator-left {{
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 240px;
}}

.home-indicator-dot {{
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: {accent};
  box-shadow: 0 0 0 6px rgba(59,130,246,0.18);
}}

.home-indicator-title {{
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}}

.home-indicator-title .s {{
  font-size: 0.82rem;
  opacity: 0.78;
}}

.home-indicator-badge {{
  margin-left: 6px;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.14);
}}

.home-indicator-mid {{
  flex: 1;
  display: flex;              
  align-items: center;
  gap: 14px;
  overflow-x: auto;           
}}
/* Hide scrollbar but allow scroll */
.home-indicator-mid::-webkit-scrollbar {{
  display: none;
}}
.home-indicator-mid {{
  -ms-overflow-style: none;  /* IE */
  scrollbar-width: none;     /* Firefox */
}}

.home-indicator-kpi {{
  padding: 6px 12px;
  border-radius: 14px;         /* ← change the size of the box*/
  background: rgba(0,0,0,0.18); /* darker contrast */
  border: 1px solid rgba(255,255,255,0.14);
  flex: 0 0 130px;     /* ← all capsules same width */
  min-width: 130px;
  max-width: 130px;

  /* keeps text tidy */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;        /* prevents wrapping */
}}

.home-indicator-kpi .k {{
  font-size: 0.70rem;
  opacity: 0.72;
  margin-bottom: 2px;
}}

.home-indicator-kpi .v {{
  font-size: 0.92rem;
  font-weight: 900;
}}

.home-indicator-right {{
  min-width: 210px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-end;
}}

.home-indicator-progress {{
  width: 100%;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.12);
}}

.home-indicator-progress > div {{
  height: 100%;
  background: linear-gradient(90deg, {accent}, rgba(255,255,255,0.25));
  border-radius: 999px;
  box-shadow: 0 0 18px rgba(59,130,246,0.22);
}}

.home-indicator-mini {{
  font-size: 0.78rem;
  opacity: 0.8;
}}
.home-indicator-mid{{
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
}}

.home-indicator-kpi{{
  flex: 1 1 0;         /* ← equal widths */
  min-width: 140px;    /* ← prevents tiny */
  max-width: 220px;    /* ← prevents huge */
  border-radius: 14px;
}}

@media (max-width: 820px) {{
  .home-indicator {{
    flex-direction: column;
    align-items: stretch;
  }}

@media (max-width: 820px){{
  .home-indicator-mid{{
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }}
}}
  .home-indicator-mid {{
    display: flex;
    overflow-x: auto;
  }}
  .home-indicator-right {{
    align-items: flex-start;
  }}
}}
</style>
"""
    components.html(html, height=160, scrolling=False)


def get_next_lesson_display() -> str:
    """
    Returns next lesson time like 'Tue 19:15' or '--:--' if none.
    Uses schedules + overrides (scheduled only).
    """
    try:
        sched = load_schedules()
        ov = load_overrides()
    except Exception:
        return "--:--"

    now = datetime.now()  # local
    now_ts = pd.Timestamp(now).tz_localize(None)

    candidates = []

    # --- 1) Overrides: take upcoming scheduled new_datetime ---
    if ov is not None and not ov.empty and "new_datetime" in ov.columns:
        tmp = ov.copy()
        tmp["status"] = tmp.get("status", "").astype(str).str.lower()
        tmp = tmp[tmp["status"] == "scheduled"].copy()
        tmp["new_datetime"] = pd.to_datetime(tmp["new_datetime"], errors="coerce")
        tmp = tmp[tmp["new_datetime"].notna()].copy()
        tmp["new_datetime"] = tmp["new_datetime"].dt.tz_localize(None)

        upcoming = tmp[tmp["new_datetime"] >= now_ts].sort_values("new_datetime")
        for _, r in upcoming.head(20).iterrows():
            candidates.append(pd.Timestamp(r["new_datetime"]).to_pydatetime())

    # --- 2) Weekly schedules: generate next occurrence for each active schedule ---
    if sched is not None and not sched.empty:
        s = sched.copy()
        s = s[s.get("active", True) == True].copy()

        # weekday: 0=Mon ... 6=Sun in your code
        for _, r in s.iterrows():
            try:
                wd = int(r.get("weekday", 0))
                time_str = str(r.get("time", "00:00")).strip()
                hh, mm = [int(x) for x in time_str.split(":")[:2]]

                days_ahead = (wd - now_ts.weekday()) % 7
                dt = (now_ts + pd.Timedelta(days=days_ahead)).normalize() + pd.Timedelta(hours=hh, minutes=mm)

                if dt < now_ts:
                    dt = dt + pd.Timedelta(days=7)

                candidates.append(dt.to_pydatetime())
            except Exception:
                continue

    if not candidates:
        return "--:--"

    next_dt = min(candidates)
    return next_dt.strftime("%a %H:%M")

# =========================
# 03.2) YEAR GOALS (PERSISTENT) — Supabase app_settings
# =========================
def _settings_client():
    """
    Prefer admin client if available; otherwise fall back to normal client.
    """
    return globals().get("supabase_admin") or globals().get("supabase")


def get_year_goal(year: int, scope: str = "global", default: float = 0.0) -> float:
    try:
        client = _settings_client()
        res = (
            client.table("app_settings")
            .select("value")
            .eq("scope", scope)
            .eq("key", "year_goal")
            .eq("year", int(year))
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if not rows:
            return float(default)
        v = rows[0].get("value", default)
        return float(v or 0.0)
    except Exception:
        return float(default)


def set_year_goal(year: int, goal_value: float, scope: str = "global") -> bool:
    try:
        client = _settings_client()
        payload = {
            "scope": scope,
            "key": "year_goal",
            "year": int(year),
            "value": float(goal_value or 0.0),
        }
        client.table("app_settings").upsert(payload, on_conflict="scope,key,year").execute()

        # If you use cached reads anywhere, clear them
        try:
            st.cache_data.clear()
        except Exception:
            pass

        return True
    except Exception:
        return False

# =========================
# 04) PWA HEAD INJECTION (Base64 icons — works in Streamlit)
# =========================
def inject_pwa_head():
    components.html(
        """
        <script>
        (function () {
          const w = window.parent;
          const doc = w.document;

          const icon192 = w.location.origin + "/app/static/icon-192.png";
          const icon512 = w.location.origin + "/app/static/icon-512.png";
          const apple180 = w.location.origin + "/app/static/apple-touch-icon.png";

          // Remove old injected items
          doc.querySelectorAll('link[rel="manifest"][data-cm="1"]').forEach(el => el.remove());
          doc.querySelectorAll('link[rel="apple-touch-icon"][data-cm="1"]').forEach(el => el.remove());

          // Build manifest dynamically
          const manifest = {
            name: "Classman",
            short_name: "Classman",
            start_url: w.location.origin + "/",
            scope: w.location.origin + "/",
            display: "standalone",
            background_color: "#0b1220",
            theme_color: "#0b1220",
            icons: [
              { src: icon192, sizes: "192x192", type: "image/png", purpose: "any" },
              { src: icon512, sizes: "512x512", type: "image/png", purpose: "any" }
            ]
          };

          const blob = new Blob([JSON.stringify(manifest)], { type: "application/manifest+json" });
          const manifestURL = URL.createObjectURL(blob);

          const link = doc.createElement("link");
          link.rel = "manifest";
          link.href = manifestURL;
          link.setAttribute("data-cm", "1");
          doc.head.appendChild(link);

          // Apple touch icon
          doc.querySelectorAll('link[rel="apple-touch-icon"][data-cm="1"]').forEach(el => el.remove());
          const ati = doc.createElement("link");
          ati.rel = "apple-touch-icon";
          ati.href = apple180;
          ati.sizes = "180x180";
          ati.setAttribute("data-cm", "1");
          doc.head.appendChild(ati);

          // Favicon override
          doc.querySelectorAll('link[rel="icon"][data-cm="1"]').forEach(el => el.remove());
          const fav = doc.createElement("link");
          fav.rel = "icon";
          fav.href = apple180;
          fav.setAttribute("data-cm", "1");
          doc.head.appendChild(fav);

          // Meta tags
          const metas = [
            { name: "apple-mobile-web-app-capable", content: "yes" },
            { name: "mobile-web-app-capable", content: "yes" },
            { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" },
            { name: "apple-mobile-web-app-title", content: "Class Manager" },
            { name: "theme-color", content: "#0b1220" }
          ];

          metas.forEach(m => {
            let el = doc.querySelector('meta[name="' + m.name + '"][data-cm="1"]');
            if (!el) {
              el = doc.createElement("meta");
              el.setAttribute("data-cm", "1");
              el.name = m.name;
              doc.head.appendChild(el);
            }
            el.content = m.content;
          });

        })();
        </script>
        """,
        height=0,
    )

inject_pwa_head()

# =========================
# 05) THEMES (DARK HOME) and (LIGHT NAV)
# =========================

def load_css_home_dark():
    st.markdown(
        """
        <style>
        :root{ color-scheme: dark; }
        html, body{ color-scheme: dark; }

        :root{
          --bg:#07101d;
          --text:#eaf0ff;
          --muted:rgba(234,240,255,0.72);
          --glass: rgba(255,255,255,0.06);
          --glass2: rgba(255,255,255,0.08);
          --stroke: rgba(255,255,255,0.12);
          --stroke2: rgba(255,255,255,0.16);
          --shadow: 0 18px 44px rgba(0,0,0,0.45);
          --shadow2: 0 12px 26px rgba(0,0,0,0.28);
          --blue: rgba(59,130,246,0.95);
          --blueGlow: rgba(59,130,246,0.22);
          --greenGlow: rgba(16,185,129,0.16);
        }

        /* ✅ IMPORTANT: prevent whole-page horizontal scrolling */
        html, body, .stApp { overflow-x: hidden !important; }
        /* (Keep vertical scroll normal) */

        /* Background like the picture */
        .stApp{
          background:
            radial-gradient(900px 520px at 22% 6%, rgba(59,130,246,0.35), transparent 58%),
            radial-gradient(760px 520px at 76% 14%, rgba(34,197,94,0.18), transparent 62%),
            radial-gradient(820px 560px at 60% 86%, rgba(14,165,233,0.14), transparent 62%),
            linear-gradient(180deg, #0a1c35 0%, #07101d 60%, #050b15 100%);
          color: var(--text);
          min-height: 100vh;
        }

        /* Hide Streamlit chrome */
        header { display:none !important; }
        div[data-testid="stDecoration"]{ display:none !important; }

        /* Container sizing (phone-friendly) */
        section[data-testid="stMain"] > div {
          padding-top: 0rem !important;
          padding-bottom: 0rem !important;
          max-width: 1100px;
        }

        html, body, [class*="css"]{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }

        /* ✅ Stop the whole Home page from scrolling left/right */
        html, body {
          overflow-x: hidden !important;
          width: 100% !important;
        }

        html, body { background: #07101d !important; }
        [data-testid="stAppViewContainer"] { background: #07101d !important; }

        .stApp, [data-testid="stAppViewContainer"] {
          overflow-x: hidden !important;
          width: 100% !important;
        }

        /* Streamlit main container can also cause overflow */
        section[data-testid="stMain"],
        section[data-testid="stMain"] > div,
        div.block-container {
          overflow-x: hidden !important;
          max-width: 100% !important;
        }

        /* ✅ Make ALL elements respect the screen width */
        * { box-sizing: border-box; }

        /* If any long row tries to exceed width, clamp it */
        .home-wrap,
        .home-card,
        .home-topbar,
        .home-hero { max-width: 100% !important; }

        /* ✅ ONLY the external links row can scroll sideways */
        .home-links-row {
          overflow-x: auto !important;
          overflow-y: hidden !important;
          max-width: 100% !important;
        }

        a { text-decoration:none !important; }

        /* Home layout */
        .home-wrap{ display:flex; justify-content:center; }
        .home-card{
          width: 100%;
          max-width: 680px;
          padding: 18px 16px 22px 16px;
          position: relative;
          box-sizing: border-box;
        }

        /* Subtle floating particles vibe */
        .home-card::before{
          content:"";
          position:absolute;
          inset:100px -20px auto -20px;
          height: 240px;
          background:
            radial-gradient(circle at 20% 40%, rgba(255,255,255,0.10), transparent 55%),
            radial-gradient(circle at 55% 65%, rgba(255,255,255,0.08), transparent 58%),
            radial-gradient(circle at 85% 35%, rgba(255,255,255,0.07), transparent 60%);
          filter: blur(1px);
          opacity: 0.10;
          pointer-events:none;
        }

        /* --- Top bar --- */
        .home-topbar{
          display:flex;
          align-items:center;
          justify-content:space-between;
          gap:12px;
          padding: 12px 12px;
          border-radius: 22px;
          background: linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.05));
          border: 1px solid rgba(255,255,255,0.14);
          box-shadow: var(--shadow2);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          margin-bottom: 14px;
          box-sizing: border-box;
        }

        .home-user{ display:flex; align-items:center; gap:12px; min-width:0; }

        /* Clickable avatar wrapper */
        .home-avatar-wrap{
          position:relative;
          display:inline-flex;
          width:46px;
          height:46px;
          border-radius:999px;
          flex: 0 0 auto;
        }

        /* Avatar circle (single definition only) */
        .home-avatar{
          width:46px;
          height:46px;
          border-radius:999px;
          overflow:hidden;
          background-size:cover;
          background-position:center;
          background-repeat:no-repeat;
          border: 1px solid rgba(255,255,255,0.18);
          box-shadow: 0 0 0 6px rgba(59,130,246,0.10);
          box-sizing:border-box;
        }

        /* Small camera badge */
        .home-avatar-badge{
          position:absolute;
          right:-6px;
          bottom:-6px;
          width:20px;
          height:20px;
          border-radius:999px;
          display:flex;
          align-items:center;
          justify-content:center;
          font-size:12px;
          background: rgba(0,0,0,0.55);
          border:1px solid rgba(255,255,255,0.18);
          box-shadow: 0 8px 18px rgba(0,0,0,0.35);
          box-sizing:border-box;
        }

        .home-usertext{ display:flex; flex-direction:column; line-height:1.05; min-width:0; }
        .home-welcome{ font-size: 12px; color: rgba(234,240,255,0.72); font-weight: 750; white-space:nowrap; }
        .home-username{
          font-size: 18px;
          font-weight: 950;
          letter-spacing:-0.02em;
          white-space:nowrap;
          overflow:hidden;
          text-overflow:ellipsis;
        }

        .home-actions{ display:flex; align-items:center; gap:10px; flex: 0 0 auto; }

        .home-badge{
          position:absolute;
          top:-6px; right:-6px;
          min-width: 18px; height: 18px;
          padding: 0 5px;
          border-radius: 999px;
          background: rgba(239,68,68,0.95);
          color: white;
          font-size: 11px;
          font-weight: 900;
          display:flex; align-items:center; justify-content:center;
          border: 2px solid rgba(7,16,29,0.95);
          box-sizing:border-box;
        }

        /* Segmented language control */
        .home-lang{
          display:inline-flex;
          align-items:center;
          border-radius: 999px;
          background: rgba(0,0,0,0.18);
          border: 1px solid rgba(255,255,255,0.12);
          overflow:hidden;
          height:44px;
          flex: 0 0 auto;
        }
        .home-langbtn{
          width:56px; height:44px;
          display:inline-flex; align-items:center; justify-content:center;
          color:#fff !important;
          font-weight: 950;
          letter-spacing: 0.02em;
          text-decoration:none !important;
          box-sizing:border-box;
        }
        .home-langbtn.on{
          background: rgba(59,130,246,0.28);
          box-shadow: inset 0 0 0 2px rgba(59,130,246,0.85);
        }

        /* --- Title + hero --- */
        .home-title{
          text-align:center;
          font-size: clamp(2.0rem, 3.4vw, 2.8rem);
          font-weight: 950;
          letter-spacing: -0.045em;
          margin: 8px 0 10px 0;
          opacity: 0.95;
        }

        .home-hero{
          margin: 10px 0 16px 0;
          padding: 18px 16px;
          border-radius: 22px;
          background:
            radial-gradient(520px 180px at 20% 10%, rgba(16,185,129,0.22), transparent 60%),
            radial-gradient(520px 180px at 80% 20%, rgba(59,130,246,0.22), transparent 60%),
            linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
          border: 1px solid rgba(255,255,255,0.14);
          box-shadow: var(--shadow2);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          box-sizing: border-box;
          position: relative;   /* IMPORTANT */
        }
        
        .home-hero::after {
          content: "";
          position: absolute;
          left: 19px;
          right: 19px;
          bottom: -2px;
          height: 1.5px;
          border-radius: 999px;

          background: linear-gradient(90deg,#3B82F6,#60A5FA,#3B82F6);

          box-shadow:
              0 0 6px rgba(59,130,246,0.9),
              0 0 14px rgba(59,130,246,0.6),
              0 0 24px rgba(59,130,246,0.4);
          animation: neonPulse 2.5s infinite ease-in-out;
        }
        
        @keyframes neonPulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
        }

        .home-slogan{
          text-align:center;
          font-size: 26px;
          font-weight: 950;
          letter-spacing: -0.03em;
          margin-bottom: 8px;
          text-shadow: 0 10px 30px rgba(0,0,0,0.35);
        }
        .home-sub{
          text-align:center;
          color: rgba(234,240,255,0.72);
          margin: 0;
          font-size: 1.02rem;
        }

        /* --- Lead source section --- */
        .home-links{ margin: 16px 0 10px 0; position:relative; }
        .home-links-title{
          text-align:center;
          font-size: 18px;
          font-weight: 850;
          letter-spacing: 0.02em;
          color: rgba(234,240,255,0.68);
          margin: 2px 0 12px 0;
          position: relative;
        }
        .home-links-title:before,
        .home-links-title:after{
          content:"";
          position:absolute;
          top:50%;
          width: 28%;
          height: 1px;
          background: rgba(255,255,255,0.12);
        }
        .home-links-title:before{ left: 0; }
        .home-links-title:after{ right: 0; }

        /* ✅ Only this row scrolls horizontally */
        .home-links-row{
          display:flex;
          gap:14px;
          overflow-x:auto;
          overflow-y:hidden;
          padding: 6px 2px 14px 2px;
          scroll-snap-type: x mandatory;
          -webkit-overflow-scrolling: touch;
          overscroll-behavior-x: contain;   /* ✅ prevents page swipe */
          touch-action: pan-x;              /* ✅ allow horizontal pan only here */
        }
        .home-links-row::-webkit-scrollbar{ display:none; }
        .home-links-row{ scrollbar-width:none; }

        .home-linkchip{
          flex: 0 0 220px;
          scroll-snap-align: start;
          display:flex;
          align-items:center;
          justify-content:center;
          gap:10px;
          padding: 14px 12px;
          border-radius: 16px;
          border: 1px solid rgba(255,255,255,0.14);
          background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04));
          color:#fff !important;
          font-weight: 900;
          box-shadow: 0 14px 26px rgba(0,0,0,0.26);
          backdrop-filter: blur(10px);
          -webkit-backdrop-filter: blur(10px);
          box-sizing:border-box;
        }
        .home-linkchip .dot{
          width:12px; height:12px; border-radius:999px;
          background: rgba(59,130,246,0.92);
          box-shadow: 0 0 0 5px rgba(59,130,246,0.14);
          display:inline-block;
        }

        /* Fade edge (keep, but not tall enough to affect whole page) */
        .home-links::after{
          content:"";
          position:absolute;
          right:0;
          top:44px;
          height: 64px;
          width:44px;
          background: linear-gradient(to left, rgba(7,16,29,1), transparent);
          pointer-events:none;
        }

        /* --- Menu pills (PREMIUM GLASS + subtle neon) --- */
        .home-pill{
          display:block;
          width: 100%;
          border-radius: 18px;
          padding: 1.05rem 1.15rem;
          margin: 0.95rem 0;

          font-weight: 950;
          text-align: center;
          color: #ffffff !important;

          background:
          linear-gradient(
          180deg,
          rgba(255,255,255,0.12),
          rgba(255,255,255,0.05)
          );

          border: 1px solid rgba(255,255,255,0.18);

          box-shadow:
          0 18px 34px rgba(0,0,0,0.32),
          inset 0 1px 0 rgba(255,255,255,0.12);

          backdrop-filter: blur(14px);
          -webkit-backdrop-filter: blur(14px);

          position: relative;
          isolation: isolate;
          overflow: hidden;

          transition: transform 160ms ease,
          box-shadow 200ms ease;
       }
        .home-pill::before{
          content:"";
          position:absolute;
          inset:-1px;               /* slightly outside = border glow */
          border-radius: 20px;
          background: linear-gradient(90deg,
            rgba(59,130,246,0.10),
            rgba(96,165,250,0.55),
            rgba(59,130,246,0.10)
          );
          filter: blur(10px);
          opacity: 0.40;
          z-index: -1;              /* behind the pill */
         animation: pillGlow 5.2s ease-in-out infinite;
          pointer-events:none;
        }

        .home-pill::after{
          content:"";
          position:absolute;
          left: 16px;
          right: 16px;
          bottom: 8px;
          height: 2px;
          border-radius: 999px;

          background: linear-gradient(90deg,
          rgba(59,130,246,0.00),
          rgba(59,130,246,0.65),
          rgba(96,165,250,0.55),
          rgba(59,130,246,0.00)
           );

          box-shadow:
          0 0 10px rgba(59,130,246,0.25),
          0 0 22px rgba(59,130,246,0.14);

          opacity: 0.55;
          transform: translateX(-12%);
          animation: pillNeon 4.8s ease-in-out infinite;
          pointer-events:none;
        }

        .home-pill:hover{
          transform: translateY(-2px);
          filter: brightness(1.06);
          box-shadow:
          0 20px 40px rgba(0,0,0,0.34),
          inset 0 1px 0 rgba(255,255,255,0.12);
        }

        .home-pill:hover::after{
          opacity: 0.75;
          box-shadow:
          0 0 14px rgba(59,130,246,0.34),
          0 0 26px rgba(59,130,246,0.18);
        }

        .home-pill::before{
          content:"";
          position:absolute;
          inset:-1px;
          border-radius: 20px;

        background: linear-gradient(
          90deg,
          transparent,
          var(--pill-glow),
          transparent
          );

        filter: blur(12px);
          opacity: 0.45;
          z-index:-1;
          animation: pillGlow 5s ease-in-out infinite;
          pointer-events:none;
       }

        @keyframes pillNeon{
          0%   { transform: translateX(-16%); opacity: 0.45; }
          50%  { transform: translateX(16%);  opacity: 0.75; }
          100% { transform: translateX(-16%); opacity: 0.45; }
        }
        @keyframes pillGlow{
          0%   { opacity: 0.25; filter: blur(12px); }
          50%  { opacity: 0.55; filter: blur(9px); }
          100% { opacity: 0.25; filter: blur(12px); }
        }

        @media (prefers-reduced-motion: reduce){
          .home-pill::after{ animation: none; }
        }

        /* Bottom indicator */
        .home-bottom-indicator {
          position: fixed;
          left: 50%;
          transform: translateX(-50%);
          bottom: calc(env(safe-area-inset-bottom) + 10px);
          width: 110px;
          height: 5px;
          border-radius: 999px;
          opacity: 0.30;
          background: rgba(255,255,255,0.75);
          z-index: 9999;
          pointer-events: none;
        }

        .home-dashboard { --pill-glow: rgba(59,130,246,0.75); }   /* blue */
        .home-students  { --pill-glow: rgba(16,185,129,0.75); }   /* green */
        .home-add_lesson{ --pill-glow: rgba(245,158,11,0.75); }   /* amber */
        .home-add_payment{ --pill-glow: rgba(239,68,68,0.75); }   /* red */
        .home-calendar  { --pill-glow: rgba(6,182,212,0.75); }    /* cyan */
        .home-analytics { --pill-glow: rgba(168,85,247,0.75); }   /* purple */
        @keyframes pillGlow{
         0%   { opacity: 0.30; filter: blur(14px); }
         50%  { opacity: 0.65; filter: blur(10px); }
         100% { opacity: 0.30; filter: blur(14px); }
    }

        /* Mobile tightening */
        @media (max-width: 520px){
          .home-card{ padding: 16px 14px 20px 14px; }
          .home-slogan{ font-size: 22px; }
          .home-links-title:before, .home-links-title:after{ width: 24%; }
        }

        /* Remove default Streamlit padding */
        .block-container {
          padding-top: 0rem !important;
          padding-bottom: 0rem !important;
          padding-left: 1rem !important;
          padding-right: 1rem !important;
        }


        </style>
        """,
        unsafe_allow_html=True,
    )


def load_css_app_light(compact: bool = False):
    compact_css = """
      section[data-testid="stMain"] > div { padding-top: 1.0rem !important; padding-bottom: 1.0rem !important; }
      div[data-testid="stVerticalBlockBorderWrapper"]{ padding: 12px !important; border-radius: 16px !important; }
      div[data-testid="stButton"] button{ padding: 0.58rem 0.85rem !important; border-radius: 14px !important; }
      div[data-testid="metric-container"]{ padding: 12px 14px !important; border-radius: 16px !important; }
    """ if compact else ""

    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: light !important; }}
        html, body {{ color-scheme: light !important; }}

        :root{{
          --bg:#f6f7fb;
          --panel:#ffffff;
          --border:rgba(17,24,39,0.08);
          --border2:rgba(17,24,39,0.10);
          --text:#0f172a;
          --muted:#475569;
          --shadow:0 10px 26px rgba(15,23,42,0.08);
          --primary-color:#2563EB !important;
        }}

        /* Prevent iOS/system dark-mode from creating odd horizontal bars */
        html, body {{ overflow-x: hidden !important; }}

        .stApp{{ background: var(--bg) !important; color: var(--text) !important; }}
        [data-testid="stAppViewContainer"], .stApp {{ background: var(--bg) !important; }}
        .stApp {{ overflow-x: hidden !important; }}

        /* Base text */
        .stApp, .stApp * {{
          color: var(--text);
          -webkit-text-fill-color: var(--text) !important; /* iOS Safari dark-mode safeguard */
        }}

        /* Muted text for captions/paragraphs */
        .stCaption, .stMarkdown p, .stMarkdown span, .stMarkdown li {{
          color: var(--muted) !important;
          -webkit-text-fill-color: var(--muted) !important;
        }}

        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        label, label * {{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        section[data-testid="stMain"] > div {{
          padding-top: 1.6rem;
          padding-bottom: 1.6rem;
          max-width: 1200px;
        }}

        @media (max-width: 768px){{
          section[data-testid="stMain"] > div {{
            padding-top: 1.0rem;
            padding-bottom: 1.2rem;
          }}
        }}

        html, body, [class*="css"]{{
          font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        }}
        h1,h2,h3{{ letter-spacing:-0.02em; }}

        div[data-testid="stVerticalBlockBorderWrapper"]{{
          background: var(--panel) !important;
          border: 1px solid var(--border) !important;
          border-radius: 18px !important;
          padding: 18px !important;
          box-shadow: var(--shadow) !important;
        }}

        div[data-testid="stButton"] button{{
          border-radius: 14px !important;
          padding: 0.62rem 1.0rem !important;
          border: 1px solid var(--border2) !important;
          background: white !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
          font-weight: 650 !important;
          transition: all 160ms ease;
        }}

        div[data-testid="stButton"] button:hover{{
          box-shadow: 0 0 0 4px rgba(59,130,246,0.12);
          border-color: rgba(59,130,246,0.35) !important;
          transform: translateY(-1px);
        }}

        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input{{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        div[data-testid="stSelectbox"] [data-baseweb="select"] > div{{
          border-radius: 14px !important;
          background: white !important;
          border: 1px solid var(--border2) !important;
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        /* Radios + toggles disappearing on iPhone dark mode: force text fill */
        .stRadio, .stRadio *, .stToggle, .stToggle * {{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}

        div[data-testid="stDataFrame"]{{
          border-radius: 18px !important;
          overflow: hidden !important;
          border: 1px solid var(--border) !important;
          box-shadow: var(--shadow) !important;
        }}

        div[data-testid="metric-container"]{{
          background: white !important;
          border: 1px solid var(--border) !important;
          padding: 14px 16px !important;
          border-radius: 18px !important;
          box-shadow: var(--shadow) !important;
        }}

        /* =========================
           BLUE TOGGLES (OFF light / ON dark)
           ========================= */

        /* Toggle track (OFF) */
        div[data-baseweb="checkbox"] div[role="checkbox"]{{
          width: 42px;
          height: 24px;
          border-radius: 12px;   /* more capsule, less pill */
          background: #BFDBFE !important; /* Light Blue */
          border: 1px solid #93C5FD !important;
          position: relative;
          transition: all 180ms ease;
        }}

        /* Toggle track (ON) */
        div[data-baseweb="checkbox"] div[role="checkbox"][aria-checked="true"]{{
          background: #1D4ED8 !important; /* Dark Blue */
          border-color: #1D4ED8 !important;
        }}

        /* White knob */
        div[data-baseweb="checkbox"] div[role="checkbox"]::after{{
          content: "";
          position: absolute;
          width: 18px;
          height: 18px;
          top: 2px;
          left: 2px;
          background: #ffffff;
          border-radius: 8px;
          transition: transform 180ms ease;
        }}
        
        /* Move knob when ON */
        div[data-baseweb="checkbox"] div[role="checkbox"][aria-checked="true"]::after{{
          transform: translateX(18px);
        }}
        
        /* Label always visible */
        div[data-baseweb="checkbox"] label,
        div[data-baseweb="checkbox"] label *{{
          color: var(--text) !important;
          -webkit-text-fill-color: var(--text) !important;
        }}
        /* =========================
           FORCE Streamlit st.toggle colors (Chrome-safe)
           ========================= */

        /* Target ONLY Streamlit toggles */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]{{
          width: 42px !important;
          height: 24px !important;
          border-radius: 12px !important;
          background: #BFDBFE !important;  /* OFF = light blue */
          border: 1px solid #93C5FD !important;
          position: relative !important;
          box-shadow: none !important;
        }}

        /* ON state */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"][aria-checked="true"]{{
          background: #1D4ED8 !important;  /* ON = dark blue */
          border-color: #1D4ED8 !important;
        }}

        /* Knob */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]::after{{
          content: "" !important;
          position: absolute !important;
          width: 18px !important;
          height: 18px !important;
          top: 2px !important;
          left: 2px !important;
          background: #ffffff !important;
          border-radius: 8px !important;
          transform: translateX(0) !important;
          transition: transform 180ms ease !important;
        }}

        /* Move knob when ON */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"][aria-checked="true"]::after{{
          transform: translateX(18px) !important;
        }}

        /* Kill the red (it’s usually the check/icon or focus styles) */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] svg,
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] svg path{{
          fill: #ffffff !important;   /* ON icon white */
        }}

        /* Remove focus ring that sometimes shows as red */
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]:focus,
        div[data-testid="stToggle"] div[data-baseweb="checkbox"] div[role="checkbox"]:focus-visible{{
          outline: none !important;
          box-shadow: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def mobile_fullscreen_css():
    st.markdown(
        """
        <style>
        .main .block-container{
          padding-top: 0rem !important;
          padding-bottom: 0rem !important;
          padding-left: 0rem !important;
          padding-right: 0rem !important;
          max-width: 100% !important;
        }
        header[data-testid="stHeader"]{ height: 0px !important; }
        div[data-testid="stDecoration"]{ display:none !important; }
        html, body, [data-testid="stAppViewContainer"]{ height: 100%; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# Only apply fullscreen “mobile” css when compact_mode is ON
if bool(st.session_state.get("compact_mode", False)):
    mobile_fullscreen_css()

# =========================
# 06) NAVIGATION (QUERY PARAM ROUTER)
# =========================
PAGES = [
    ("dashboard", "dashboard", "linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06))"),
    ("students",  "students",  "linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06))"),
    ("add_lesson","lessons",   "linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06))"),
    ("add_payment","payments", "linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06))"),
    ("calendar",  "calendar",  "linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06))"),
    ("analytics", "analytics", "linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06))"),
]
PAGE_KEYS = {"home"} | {k for k, _, _ in PAGES}


def _get_qp(key: str, default=None):
    """Safe query param getter (new + old Streamlit)."""
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


def _get_query_page() -> str:
    v = _get_qp("page", "home")
    return str(v) if v is not None else "home"


def _set_query(page: Optional[str] = None, lang: Optional[str] = None) -> None:
    """Set query params safely (preserves existing when None)."""
    new_page = page if page is not None else st.session_state.get("page", "home")
    new_lang = lang if lang is not None else st.session_state.get("ui_lang", "en")
    try:
        st.query_params["page"] = new_page
        st.query_params["lang"] = new_lang
    except Exception:
        st.experimental_set_query_params(page=new_page, lang=new_lang)


# Defaults
if "page" not in st.session_state:
    st.session_state.page = "home"

# Sync language from URL first (so UI matches instantly)
lang_qp = _get_qp("lang", None)
if lang_qp in ("en", "es"):
    st.session_state.ui_lang = lang_qp

# Read page from URL
qp_page = _get_query_page()
if qp_page in PAGE_KEYS:
    st.session_state.page = qp_page
else:
    st.session_state.page = "home"
    _set_query(page="home", lang=st.session_state.ui_lang)


def go_to(page_name: str):
    """Navigation helper for top-nav buttons/links."""
    if page_name not in PAGE_KEYS:
        page_name = "home"
    st.session_state.page = page_name
    _set_query(page=page_name, lang=st.session_state.get("ui_lang", "en"))


def page_header(title: str):
    st.markdown(f"## {title}")

# =========================
# 07) SUPABASE CONNECTION
# =========================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]  # anon/public
    SUPABASE_SERVICE_ROLE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
except Exception as e:
    st.error("Missing Streamlit secrets: SUPABASE_URL / SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY")
    st.code(str(e))
    st.stop()

# Public client (RLS applies)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Admin client (bypasses RLS)
supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# =========================
# 07) HELPERS
# =========================

# =========================
# 07.1) DATA ACCESS HELPERS
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

def get_profile_avatar_url(user_id: str) -> str:
    try:
        resp = supabase_admin.table("profiles").select("avatar_url").eq("user_id", user_id).limit(1).execute()
        rows = resp.data or []
        return (rows[0].get("avatar_url") or "") if rows else ""
    except Exception:
        return ""

def save_profile_avatar_url(user_id: str, avatar_url: str) -> None:
    payload = {"user_id": user_id, "avatar_url": avatar_url}
    supabase_admin.table("profiles").upsert(payload).execute()

# =========================
# 07.2) QUERY PARAM HELPERS
# =========================
def _clear_qp(*keys: str) -> None:
    """Remove query params safely (new + old Streamlit)."""
    try:
        for k in keys:
            if k in st.query_params:
                del st.query_params[k]
    except Exception:
        qp = st.experimental_get_query_params()
        for k in keys:
            qp.pop(k, None)
        st.experimental_set_query_params(**qp)

# =========================
# 07.3) TODAY LESSONS HELPER
# =========================
def build_today_lessons() -> pd.DataFrame:
    today = date.today()

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
# 07.4) LANGUAGE HELPERS
# =========================
LANG_EN = "English"
LANG_ES = "Spanish"
LANG_BOTH = "English,Spanish"
ALLOWED_LANGS = {LANG_EN, LANG_ES, LANG_BOTH}
ALLOWED_LESSON_LANGS = {LANG_EN, LANG_ES, LANG_BOTH}
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
        return [langs[0]], langs[0]
    return [LANG_EN, LANG_ES], None


def translate_status(val: str) -> str:
    if not val:
        return ""
    key_map = {
        "dropout": "dropout",
        "finished": "finished_status",
        "mismatch": "mismatch_status",
        "almost_finished": "almost_finished",
        "active": "active_status",
    }
    return t(key_map.get(str(val).strip().casefold(), str(val)))


def translate_modality_value(x: str) -> str:
    v = str(x or "").strip().casefold()
    if v == "online":
        return t("online")
    if v == "offline":
        return t("offline")
    return str(x or "").strip()


def translate_language_value(x: str) -> str:
    v = str(x or "").strip()
    if v == LANG_EN:
        return t("english")
    if v == LANG_ES:
        return t("spanish")
    if v == LANG_BOTH:
        return t("both")
    if v.casefold() in ("unknown", ""):
        return t("unknown")
    return v


# =========================
# 07.5) WHATSAPP HELPERS
# =========================

def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", str(s or ""))


def normalize_phone_for_whatsapp(raw_phone: str) -> str:
    """
    WhatsApp expects international format digits only (no +).
    Designed for Turkey numbers but tolerant of other formats.

    Examples:
      +90 5xx xxx xx xx  -> 905xxxxxxxxx
      05xx xxx xx xx     -> 905xxxxxxxxx
      5xx xxx xx xx      -> 905xxxxxxxxx
      00<country><num>   -> <country><num>
    """
    d = _digits_only(raw_phone)
    if not d:
        return ""

    # Remove leading 00
    if d.startswith("00") and len(d) > 2:
        d = d[2:]

    # Already looks like an international number (e.g., 90xxxxxxxxxx, 4917..., 1...)
    # Keep as-is if >= 11 digits and doesn't start with trunk '0'
    if len(d) >= 11 and not d.startswith("0"):
        return d

    # Turkey specific normalization
    # 0 + 10 digits starting with 5xxxxxxxxx  -> add country code
    if len(d) == 11 and d.startswith("0") and d[1] == "5":
        return "90" + d[1:]

    # 10 digits starting with 5xxxxxxxxx -> add country code
    if len(d) == 10 and d.startswith("5"):
        return "90" + d

    # If we can't safely normalize, return empty (so we fall back to wa.me/?text=...)
    return ""


def build_whatsapp_url(message: str, raw_phone: str = "") -> str:
    encoded = urllib.parse.quote(message or "")
    phone = normalize_phone_for_whatsapp(raw_phone)
    if phone:
        return f"https://wa.me/{phone}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def _msg_lang_label(lang: str) -> str:
    return {"en": "English", "es": "Español", "tr": "Türkçe"}.get(lang, lang)


def _package_status_text(status: str, lang: str) -> str:
    """
    status expected like: 'almost_finished', 'finished', etc.
    We map 'almost'/'soon' variations → "almost finished"
    """
    s = str(status or "").strip().casefold()
    is_almost = (
        ("almost_finished" in s)
        or ("almost" in s)
        or ("finish_soon" in s)
        or ("soon" in s)
        or ("about" in s and "finish" in s)
    )

    if lang == "es":
        return "por terminar" if is_almost else "finalizado"
    if lang == "tr":
        return "bitmek üzere" if is_almost else "tamamlandı"
    return "almost finished" if is_almost else "finished"


def build_msg_confirm(name: str, lang: str, time_text: str = "") -> str:
    """
    Template #2: confirm today's lesson (EN/ES/TR)
    time_text optional; if empty, we omit time.
    """
    name = (name or "").strip()
    tt = (time_text or "").strip()

    if lang == "es":
        return (
            f"Hola {name}! Solo para confirmar nuestra clase de hoy"
            f"{f' a las {tt}' if tt else ''}. ¿Todo bien por tu lado?"
        )
    if lang == "tr":
        return (
            f"Merhaba {name}! Bugünkü dersimizi"
            f"{f' {tt} için' if tt else ''} teyit etmek istiyorum. Sizin için uygun mu?"
        )
    return (
        f"Hi {name}! Just confirming our lesson today"
        f"{f' at {tt}' if tt else ''}. Is everything okay for you?"
    )


def build_msg_cancel(name: str, lang: str) -> str:
    """
    Template #3: cancel today's lesson (EN/ES/TR)
    """
    name = (name or "").strip()

    if lang == "es":
        return f"Hola {name}. Lo siento, pero necesito cancelar la clase de hoy. ¿Quieres reprogramarla?"
    if lang == "tr":
        return f"Merhaba {name}. Üzgünüm, bugünkü dersi iptal etmem gerekiyor. Yeniden planlayalım mı?"
    return f"Hi {name}. I’m sorry, but I need to cancel today’s lesson. Would you like to reschedule?"


def build_msg_package_header(name: str, lang: str, status: str) -> str:
    """
    Template #1 header: finished / almost finished package (EN/ES/TR)
    Pricing block is appended separately.
    """
    name = (name or "").strip()
    stxt = _package_status_text(status, lang)

    if lang == "es":
        return (
            f"Hola {name}! Espero que estés bien.\n"
            f"Tu paquete actual está {stxt}. Si quieres continuar, aquí están mis precios actuales:\n"
        )
    if lang == "tr":
        return (
            f"Merhaba {name}, umarım iyisinizdir.\n"
            f"Mevcut paketiniz {stxt}. Devam etmek isterseniz güncel fiyatlarım aşağıdadır:\n"
        )
    return (
        f"Hi {name}! Hope you’re doing well.\n"
        f"Your current package is {stxt}. If you’d like to continue, here are my current prices:\n"
    )


def _get_pricing_snapshot() -> dict:
    """
    Loads active pricing from Supabase via load_pricing_items().

    Returns:
      {
        "online_hourly": int,
        "offline_hourly": int,
        "online_packages": [(hours:int, price:int, per:int), ...],
        "offline_packages": [(hours:int, price:int, per:int), ...],
      }
    """
    df = load_pricing_items()
    if df is None or df.empty:
        return {
            "online_hourly": 0,
            "offline_hourly": 0,
            "online_packages": [],
            "offline_packages": [],
        }

    df = df.copy()
    if "active" in df.columns:
        df = df[df["active"] == True].copy()

    # normalize
    df["modality"] = df["modality"].fillna("").astype(str).str.strip().str.lower()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower()
    df["price_try"] = pd.to_numeric(df["price_try"], errors="coerce").fillna(0).astype(int)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")  # NaN ok for hourly

    def _hourly(mod: str) -> int:
        h = df[(df["modality"] == mod) & (df["kind"] == "hourly")].copy()
        if h.empty:
            return 0
        if "sort_order" in h.columns:
            h["sort_order"] = pd.to_numeric(h["sort_order"], errors="coerce").fillna(0).astype(int)
            h = h.sort_values(["sort_order", "id"], na_position="last")
        return int(h.iloc[0].get("price_try") or 0)

    def _packages(mod: str) -> list:
        p = df[(df["modality"] == mod) & (df["kind"] == "package")].copy()
        if p.empty:
            return []
        p["hours"] = pd.to_numeric(p["hours"], errors="coerce").fillna(0).astype(int)
        p["sort_order"] = pd.to_numeric(p.get("sort_order", 0), errors="coerce").fillna(0).astype(int)

        # Sort packages: sort_order ascending, then hours descending (e.g., 44, 20, 10, 5)
        p = p.sort_values(["sort_order", "hours"], ascending=[True, False], na_position="last")

        out = []
        for _, r in p.iterrows():
            hours = int(r.get("hours") or 0)
            price = int(r.get("price_try") or 0)
            if hours <= 0:
                continue
            per = int(round(price / hours))
            out.append((hours, price, per))
        return out

    return {
        "online_hourly": _hourly("online"),
        "offline_hourly": _hourly("offline"),
        "online_packages": _packages("online"),
        "offline_packages": _packages("offline"),
    }


def build_pricing_block(lang: str = "tr") -> str:
    """
    WhatsApp-friendly pricing list built from pricing_items.
    Prints both online and offline sections (matches your original Turkish message style).
    """
    s = _get_pricing_snapshot()

    online_hourly = int(s.get("online_hourly") or 0)
    offline_hourly = int(s.get("offline_hourly") or 0)
    online_pk = s.get("online_packages") or []
    offline_pk = s.get("offline_packages") or []

    # ---- Text labels ----
    if lang == "es":
        header = "📌 Las clases duran 50–60 minutos (1 hora).\n"
        online_title = "💻 Precios de clases online:\n"
        offline_title = "🏫 Precios de clases presenciales:\n"
        hourly_note = "*La clase se paga el mismo día.\n"
        prepaid_title = "📦 Paquetes online (prepago):\n"
        prepaid_note = "*El pago debe hacerse antes de empezar. Puedes tomar clases con la frecuencia que quieras.\n"
        offline_pk_title = "📦 Paquetes presenciales (prepago):\n"
        line_hourly = lambda price: f"1 hora → {money_try(price)}\n"
        line_pkg = lambda h, price, per: f"{h} horas → {money_try(price)} (≈ {money_try(per)} / hora)\n"
        no_online_hourly = "(No hay precio por hora online configurado)\n"
        no_online_pk = "(No hay paquetes online)\n"
        no_offline_pk = "(No hay paquetes presenciales)\n"

    elif lang == "en":
        header = "📌 Lessons are 50–60 minutes (1 hour).\n"
        online_title = "💻 Online lesson prices:\n"
        offline_title = "🏫 In-person lesson prices:\n"
        hourly_note = "*Each lesson is paid on the same day.\n"
        prepaid_title = "📦 Online prepaid packages:\n"
        prepaid_note = "*Payment must be made before starting. Lessons can be taken as frequently as you want.\n"
        offline_pk_title = "📦 In-person prepaid packages:\n"
        line_hourly = lambda price: f"1 hour → {money_try(price)}\n"
        line_pkg = lambda h, price, per: f"{h} hours → {money_try(price)} (≈ {money_try(per)} / hour)\n"
        no_online_hourly = "(No online hourly price set)\n"
        no_online_pk = "(No online packages)\n"
        no_offline_pk = "(No in-person packages)\n"

    else:  # TR default
        header = "Derslerim 50-60 dakika sürer (1 saat).\n"
        online_title = "Çevrimiçi ders fiyatları:\n"
        offline_title = "Yüz yüze ders fiyatları:\n"
        hourly_note = "*Her ders aynı gün ödenmelidir.\n"
        prepaid_title = "Çevrimiçi Ders Ön ödemeli paketler:\n"
        prepaid_note = "*Kursa başlamadan önce ödeme yapılmalıdır. Dersler istediğiniz sıklıkta alınabilir.\n"
        offline_pk_title = "Yüz yüze Ders Ön ödemeli paketler:\n"
        line_hourly = lambda price: f"1 saat → {money_try(price)}\n"
        line_pkg = lambda h, price, per: f"{h} saat → {money_try(price)} (≈ {money_try(per)} ders/saati)\n"
        no_online_hourly = "(Çevrimiçi saat ücreti ayarlanmamış)\n"
        no_online_pk = "(Çevrimiçi paket yok)\n"
        no_offline_pk = "(Yüz yüze paket yok)\n"

    # ---- Build block ----
    out = []
    out.append(header)

    # Online
    out.append(online_title)
    if online_hourly > 0:
        out.append(line_hourly(online_hourly))
        out.append(hourly_note)
    else:
        out.append(no_online_hourly)

    out.append("\n" + prepaid_title)
    if online_pk:
        for h, price, per in online_pk:
            out.append(line_pkg(h, price, per))
        out.append(prepaid_note)
    else:
        out.append(no_online_pk)

    # Offline
    out.append("\n" + offline_title)

    # Optional: include offline hourly in EN/ES only (as you had it)
    if offline_hourly > 0 and lang in ("en", "es"):
        out.append(line_hourly(offline_hourly))
        out.append(hourly_note)

    out.append("\n" + offline_pk_title)
    if offline_pk:
        for h, price, per in offline_pk:
            out.append(line_pkg(h, price, per))
        out.append(prepaid_note)
    else:
        out.append(no_offline_pk)

    return "".join(out).strip() + "\n"
# =========================
# 07.6) CRUD HELPERS (CLASSES / PAYMENTS)
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
        "id": row["id"],
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
        # Backward compatible if DB schema is older
        for k in ["languages", "lesson_adjustment_units", "package_normalized", "normalized_note", "normalized_at"]:
            payload.pop(k, None)
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
# 07.8) CRUD HELPERS (PRICING ITEMS) — I18N READY (EN/ES)
# =========================

def load_pricing_items() -> pd.DataFrame:
    """
    Loads pricing_items from Supabase.
    Expected columns:
      id, modality (online/offline), kind (hourly/package),
      hours (NULL for hourly), price_try, active, sort_order
    """
    try:
        res = supabase.table("pricing_items").select("*").order("sort_order").execute()
        rows = res.data or []
        df = pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["id", "modality", "kind", "hours", "price_try", "active", "sort_order"])

    if df.empty:
        return pd.DataFrame(columns=["id", "modality", "kind", "hours", "price_try", "active", "sort_order"])

    # Ensure expected columns exist
    defaults = {
        "id": None,
        "modality": "",
        "kind": "",
        "hours": None,
        "price_try": 0,
        "active": True,
        "sort_order": 0,
    }
    for c, default in defaults.items():
        if c not in df.columns:
            df[c] = default

    # Normalize
    df["active"] = df["active"].fillna(True).astype(bool)
    df["sort_order"] = pd.to_numeric(df["sort_order"], errors="coerce").fillna(0).astype(int)

    df["modality"] = df["modality"].fillna("").astype(str).str.strip().str.lower()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower()

    df["price_try"] = pd.to_numeric(df["price_try"], errors="coerce").fillna(0).astype(int)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")  # keep NaN for hourly

    return df


def upsert_pricing_item(payload: dict) -> None:
    """
    No DB uniqueness restrictions required.
    Upsert will UPDATE when payload includes id; otherwise INSERT.
    """
    if supabase_admin is None:
        raise RuntimeError("Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets.")
    supabase_admin.table("pricing_items").upsert(payload).execute()


def delete_pricing_item(item_id: int) -> None:
    if supabase_admin is None:
        raise RuntimeError("Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets.")
    supabase_admin.table("pricing_items").delete().eq("id", int(item_id)).execute()


def money_try(x) -> str:
    try:
        return f"{int(round(float(x))):,} TL".replace(",", ".")
    except Exception:
        return str(x)


def _pricing_section(df: pd.DataFrame, modality: str, title_key: str, hourly_default: int) -> None:
    """
    Renders one modality pricing editor (online/offline).
    modality must be lowercase: "online" or "offline"
    title_key must be a translation key.
    """

    st.markdown(f"### {t(title_key)}")

    if df is None or df.empty:
        df = pd.DataFrame(columns=["id", "modality", "kind", "hours", "price_try", "active", "sort_order"])
    else:
        df = df.copy()

    # Ensure expected columns exist
    defaults = {
        "id": None,
        "modality": "",
        "kind": "",
        "hours": None,
        "price_try": 0,
        "active": True,
        "sort_order": 0,
    }
    for c, default in defaults.items():
        if c not in df.columns:
            df[c] = default

    # Active only
    df["active"] = df["active"].fillna(True).astype(bool)
    df = df[df["active"] == True].copy()

    # Normalize strings
    df["modality"] = df["modality"].fillna("").astype(str).str.strip().str.lower()
    df["kind"] = df["kind"].fillna("").astype(str).str.strip().str.lower()

    # Numeric
    df["price_try"] = pd.to_numeric(df["price_try"], errors="coerce").fillna(0).astype(int)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")  # NaN ok for hourly

    # ---------- Hourly ----------
    hourly = df[(df["modality"] == modality) & (df["kind"] == "hourly")].copy()

    # Seed hourly if missing
    if hourly.empty:
        upsert_pricing_item(
            {
                "modality": modality,
                "kind": "hourly",
                "hours": None,
                "price_try": int(hourly_default),
                "active": True,
                "sort_order": 0,
            }
        )
        df = load_pricing_items()
        df = df[df["active"] == True].copy()
        hourly = df[(df["modality"] == modality) & (df["kind"] == "hourly")].copy()

    if hourly.empty:
        st.error(t("pricing_hourly_load_error"))
        return

    # If multiple hourly rows exist, use the first by sort_order then id
    hourly = hourly.sort_values(["sort_order", "id"], na_position="last")
    hourly_row = hourly.iloc[0].to_dict()

    c1, c2 = st.columns([2, 1])
    with c1:
        st.caption(t("pricing_hourly_caption"))
    with c2:
        new_hourly = st.number_input(
            t("pricing_hourly_price_label"),
            min_value=0,
            step=50,
            value=int(hourly_row.get("price_try") or 0),
            key=f"hourly_price_{modality}",
            label_visibility="collapsed",
        )

    if int(new_hourly) != int(hourly_row.get("price_try") or 0):
        upsert_pricing_item(
            {
                "id": int(hourly_row["id"]),
                "modality": modality,
                "kind": "hourly",
                "hours": None,
                "price_try": int(new_hourly),
                "active": True,
                "sort_order": int(hourly_row.get("sort_order") or 0),
            }
        )
        st.success(t("pricing_hourly_updated"))
        st.rerun()

    st.divider()

    # ---------- Packages ----------
    pk = df[(df["modality"] == modality) & (df["kind"] == "package")].copy()
    pk["sort_order"] = pd.to_numeric(pk["sort_order"], errors="coerce").fillna(0).astype(int)
    pk["hours"] = pd.to_numeric(pk["hours"], errors="coerce").fillna(0).astype(int)
    pk = pk.sort_values(["sort_order", "hours", "id"], na_position="last")

    if pk.empty:
        st.info(t("pricing_no_packages"))
    else:
        # Use enumerate to guarantee unique Streamlit widget keys even if duplicate IDs appear
        for i, (_, row) in enumerate(pk.iterrows(), start=1):
            row_id = int(row.get("id") or 0)
            hours = int(row.get("hours") or 0)
            price = int(row.get("price_try") or 0)
            per = int(round(price / hours)) if hours > 0 else 0

            with st.container(border=True):
                a, b, c = st.columns([2, 2, 1])

                with a:
                    st.markdown(f"**{hours} {t('pricing_hours')}**")
                    st.caption(f"≈ {money_try(per)} {t('pricing_per_hour')}")

                with b:
                    st.markdown(f"**{money_try(price)}**")

                with c:
                    if st.button(t("pricing_edit"), key=f"edit_pkg_{modality}_{row_id}_{i}"):
                        st.session_state[f"edit_price_id_{modality}"] = row_id

                if st.session_state.get(f"edit_price_id_{modality}") == row_id:
                    e1, e2, e3 = st.columns([1, 1, 1])
                    with e1:
                        new_hours = st.number_input(
                            t("pricing_hours"),
                            min_value=1,
                            step=1,
                            value=max(1, hours),
                            key=f"pkg_hours_{modality}_{row_id}_{i}",
                        )
                    with e2:
                        new_price = st.number_input(
                            t("pricing_price_label"),
                            min_value=0,
                            step=50,
                            value=price,
                            key=f"pkg_price_{modality}_{row_id}_{i}",
                        )
                    with e3:
                        if st.button(t("pricing_save"), key=f"save_pkg_{modality}_{row_id}_{i}"):
                            upsert_pricing_item(
                                {
                                    "id": row_id,
                                    "modality": modality,
                                    "kind": "package",
                                    "hours": int(new_hours),
                                    "price_try": int(new_price),
                                    "active": True,
                                    "sort_order": int(row.get("sort_order") or new_hours),
                                }
                            )
                            st.session_state[f"edit_price_id_{modality}"] = None
                            st.success(t("pricing_package_updated"))
                            st.rerun()

                        if st.button(t("pricing_delete"), key=f"del_pkg_{modality}_{row_id}_{i}"):
                            delete_pricing_item(row_id)
                            st.session_state[f"edit_price_id_{modality}"] = None
                            st.success(t("pricing_package_deleted"))
                            st.rerun()

    st.divider()

    # ---------- Add package ----------
    st.markdown(f"**{t('pricing_add_package')}**")
    n1, n2, n3 = st.columns([1, 1, 1])

    with n1:
        add_hours = st.number_input(
            t("pricing_hours"),
            min_value=1,
            step=1,
            value=10,
            key=f"add_pkg_hours_{modality}",
        )
    with n2:
        add_price = st.number_input(
            t("pricing_price_label"),
            min_value=0,
            step=50,
            value=0,
            key=f"add_pkg_price_{modality}",
        )
    with n3:
        if st.button(t("pricing_add"), key=f"add_pkg_btn_{modality}"):
            upsert_pricing_item(
                {
                    "modality": modality,
                    "kind": "package",
                    "hours": int(add_hours),
                    "price_try": int(add_price),
                    "active": True,
                    "sort_order": int(add_hours),
                }
            )
            st.success(t("pricing_package_added"))
            st.rerun()


def render_pricing_editor() -> None:
    """
    Pricing editor UI. Call this ONLY inside a page (e.g. add_payment).
    """
    with st.expander(t("pricing_editor_title"), expanded=False):
        df = load_pricing_items()
        _pricing_section(df, modality="online", title_key="pricing_online_title", hourly_default=2000)

        st.divider()

        df = load_pricing_items()
        _pricing_section(df, modality="offline", title_key="pricing_offline_title", hourly_default=3500)

# =========================
# 07.9) PACKAGE/LANGUAGE LOOKUPS
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
        v = str(rows[0].get("languages") or LANG_ES).strip()
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
# 07.10) HISTORY HELPERS
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

    # Ensure columns exist
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

    # Filter by student
    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    lessons_df = classes[classes["student"] == student].copy()
    payments_df = payments[payments["student"] == student].copy()

    # Parse dates (tz-naive)
    lessons_df["lesson_date"] = to_dt_naive(lessons_df["lesson_date"], utc=True)
    payments_df["payment_date"] = to_dt_naive(payments_df["payment_date"], utc=True)
    payments_df["package_start_date"] = to_dt_naive(payments_df["package_start_date"], utc=True)
    payments_df["package_expiry_date"] = to_dt_naive(payments_df["package_expiry_date"], utc=True)

    # Numeric
    lessons_df["number_of_lesson"] = pd.to_numeric(lessons_df["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments_df["number_of_lesson"] = pd.to_numeric(payments_df["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    payments_df["paid_amount"] = pd.to_numeric(payments_df["paid_amount"], errors="coerce").fillna(0.0)

    # Sort
    lessons_df = lessons_df.sort_values(["lesson_date","id"], ascending=[False, False]).reset_index(drop=True)
    payments_df = payments_df.sort_values(["payment_date","id"], ascending=[False, False]).reset_index(drop=True)

    # Select + rename to stable internal keys (snake_case)
    lessons_df = lessons_df.rename(columns={
        "id": "lesson_id",
        "number_of_lesson": "lessons",
    })[["lesson_id","lesson_date","lessons","modality","lesson_language","note"]]

    payments_df = payments_df.rename(columns={
        "id": "payment_id",
        "number_of_lesson": "lessons_paid",
        "lesson_adjustment_units": "adjustment_units",
    })[[
        "payment_id","payment_date","lessons_paid","paid_amount","modality","languages",
        "package_start_date","package_expiry_date",
        "adjustment_units","package_normalized","normalized_note","normalized_at"
    ]]

    # Format dates for display (safe on Series)
    lessons_df["lesson_date"] = pd.to_datetime(lessons_df["lesson_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["payment_date"] = pd.to_datetime(payments_df["payment_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["package_start_date"] = pd.to_datetime(payments_df["package_start_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    payments_df["package_expiry_date"] = pd.to_datetime(payments_df["package_expiry_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # Translate coded values (optional)
    lessons_df["modality"] = lessons_df["modality"].apply(translate_modality_value)
    lessons_df["lesson_language"] = lessons_df["lesson_language"].apply(translate_language_value)

    payments_df["modality"] = payments_df["modality"].apply(translate_modality_value)
    payments_df["languages"] = payments_df["languages"].apply(translate_language_value)

    return lessons_df, payments_df

# =========================
# 08) SCHEDULE / OVERRIDES
# =========================
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_schedules() -> pd.DataFrame:
    df = load_table("schedules")
    if df.empty:
        return pd.DataFrame(columns=["id", "student", "weekday", "time", "duration_minutes", "active"])

    for c, default in {
        "id": None, "student": "", "weekday": 0, "time": "", "duration_minutes": 60, "active": True
    }.items():
        if c not in df.columns:
            df[c] = default

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

    for c, default in {
        "id": None, "student": "", "original_date": None, "new_datetime": None,
        "duration_minutes": 60, "status": "", "note": ""
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["original_date"] = to_dt_naive(df["original_date"], utc=True)

    new_dt = pd.to_datetime(df["new_datetime"], errors="coerce", utc=True)
    df["new_datetime"] = pd.NaT
    mask = new_dt.notna()
    df.loc[mask, "new_datetime"] = new_dt.loc[mask].dt.tz_convert(LOCAL_TZ).dt.tz_localize(None)

    df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce").fillna(60).astype(int)
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["note"] = df["note"].fillna("").astype(str)

    return df


def _to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert a datetime to a UTC ISO string for storage.
    - If naive: assume LOCAL_TZ (Europe/Istanbul)
    - If aware: respect its tz
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC_TZ).isoformat()


def add_override(
    student: str,
    original_date: date,
    new_dt: Optional[datetime],
    duration_minutes: int = 60,
    status: str = "scheduled",
    note: str = ""
) -> None:
    student = str(student).strip()
    ensure_student(student)

    status_clean = str(status).strip().lower()

    payload = {
        "student": student,
        "original_date": original_date.isoformat(),
        "duration_minutes": int(duration_minutes),
        "status": status_clean,
        "note": str(note or "").strip(),
        "new_datetime": _to_utc_iso(new_dt) if status_clean == "scheduled" else None
    }

    supabase.table("calendar_overrides").insert(payload).execute()


def delete_override(override_id: int) -> None:
    supabase.table("calendar_overrides").delete().eq("id", int(override_id)).execute()


# =========================
# 09) STUDENT META
# =========================
def load_students_df() -> pd.DataFrame:
    df = load_table("students")
    if df.empty:
        return pd.DataFrame(columns=["student", "email", "zoom_link", "notes", "color", "phone"])

    for c, default in {
        "student": "", "email": "", "zoom_link": "", "notes": "", "color": "#3B82F6", "phone": ""
    }.items():
        if c not in df.columns:
            df[c] = default

    df["student"] = df["student"].astype(str).str.strip()
    df["color"] = df["color"].fillna("#3B82F6").astype(str).str.strip()
    df["zoom_link"] = df["zoom_link"].fillna("").astype(str).str.strip()
    df["email"] = df["email"].fillna("").astype(str).str.strip()
    df["notes"] = df["notes"].fillna("").astype(str)
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
# 10) DASHBOARD (PACKAGE STATUS) ✅ + chart-translation helper
# =========================
def dash_chart_series(
    df: pd.DataFrame,
    group_col: str,
    value_col: str = None,
    agg: str = "count",
    *,
    translate_group_values: bool = True,
    group_key_for_label: str = None,
    value_key_for_label: str = None,
):
    """
    Build a Streamlit-ready Series where:
      - Index labels are translatable (Status/Modality/Languages, or raw strings)
      - Series name is translatable (so chart title/legend shows translated label)
    """
    if df is None or df.empty:
        return None
    if group_col not in df.columns:
        return None
    if agg in ("sum", "mean", "min", "max") and (value_col is None or value_col not in df.columns):
        return None

    tmp = df.copy()

    # Translate grouped values when they are coded
    if translate_group_values:
        if group_col == "Status":
            tmp[group_col] = tmp[group_col].astype(str).str.strip().str.casefold().apply(translate_status)
        elif group_col == "Modality":
            tmp[group_col] = tmp[group_col].astype(str).apply(translate_modality_value)
        elif group_col == "Languages":
            tmp[group_col] = tmp[group_col].astype(str).apply(translate_language_value)

    # Build series
    if agg == "count":
        ser = tmp.groupby(group_col).size()
    else:
        tmp["_v"] = pd.to_numeric(tmp[value_col], errors="coerce").fillna(0.0)
        if agg == "sum":
            ser = tmp.groupby(group_col)["_v"].sum()
        elif agg == "mean":
            ser = tmp.groupby(group_col)["_v"].mean()
        elif agg == "min":
            ser = tmp.groupby(group_col)["_v"].min()
        elif agg == "max":
            ser = tmp.groupby(group_col)["_v"].max()
        else:
            ser = tmp.groupby(group_col).size()

    # Sort desc for nicer charts
    try:
        ser = ser.sort_values(ascending=False)
    except Exception:
        pass

    # ----- translated axis label + series label -----
    if group_key_for_label is None:
        group_key_for_label = str(group_col).strip().casefold().replace(" ", "_")

    if value_key_for_label is None:
        if agg == "count":
            value_key_for_label = "students"
        else:
            value_key_for_label = str(value_col or "").strip().casefold().replace(" ", "_") or "income"

    ser.index.name = t(group_key_for_label)
    ser.name = t(value_key_for_label)

    return ser


def rebuild_dashboard(active_window_days: int = 183, expiry_days: int = 365, grace_days: int = 0) -> pd.DataFrame:
    classes = load_table("classes")
    payments = load_table("payments")

    if classes.empty:
        classes = pd.DataFrame(columns=["id","student","number_of_lesson","lesson_date","modality","note","lesson_language"])
    if payments.empty:
        payments = pd.DataFrame(columns=[
            "id","student","number_of_lesson","payment_date","paid_amount","modality","languages",
            "package_start_date","package_expiry_date",
            "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
        ])

    # Ensure columns exist
    for c in ["id","student","number_of_lesson","lesson_date","modality","note","lesson_language"]:
        if c not in classes.columns:
            classes[c] = None

    for c in [
        "id","student","number_of_lesson","payment_date","paid_amount","modality","languages",
        "package_start_date","package_expiry_date",
        "lesson_adjustment_units","package_normalized","normalized_note","normalized_at"
    ]:
        if c not in payments.columns:
            payments[c] = None

    classes["student"] = classes["student"].astype(str).str.strip()
    payments["student"] = payments["student"].astype(str).str.strip()

    classes["lesson_date"] = to_dt_naive(classes["lesson_date"], utc=True)
    payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
    payments["package_start_date"] = to_dt_naive(payments["package_start_date"], utc=True)
    payments["package_expiry_date"] = to_dt_naive(payments["package_expiry_date"], utc=True)

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

    today = ts_today_naive()
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
         .rename(columns={"size":"packages_bought"})
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
            "modality","number_of_lesson","lesson_adjustment_units","package_normalized",
            "payment_date","paid_amount","languages"
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
            ends.append(pd.to_datetime(row["package_expiry_date"], errors="coerce"))
        if pd.notna(row.get("next_pkg_start")):
            ends.append(pd.to_datetime(row["next_pkg_start"], errors="coerce"))
        ends = [e for e in ends if pd.notna(e)]
        return min(ends) if ends else today

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

    # packages_bought merge creates "packages_bought"
    dash["Packages_Bought"] = pd.to_numeric(dash.get("packages_bought"), errors="coerce").fillna(0).astype(int)
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
        # return ONLY lowercase codes
        if bool(r.get("Is_Dropout")):
            return "dropout"
        if bool(r.get("Closed_By_Expiry")) or bool(r.get("Closed_By_Old_Payment")):
            return "finished"
        if int(r.get("Overused_Units", 0)) > 0 and bool(r.get("Is_Active_6m")) and (not bool(r.get("package_normalized", False))):
            return "mismatch"
        left = int(r.get("Lessons_Left_Units", 0))
        if left <= 0:
            return "finished"
        if left <= 3:
            return "almost_finished"
        return "active"

    dash["Status"] = dash.apply(_status, axis=1)

    dash["Payment_Date"] = pd.to_datetime(dash["Payment_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Start_Date"] = pd.to_datetime(dash["Package_Start_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Package_Expiry_Date"] = pd.to_datetime(dash["Package_Expiry_Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    dash["Last_Lesson_Date"] = pd.to_datetime(dash["Last_Lesson_Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    dash["Normalize_Allowed"] = (
        (dash["Status"] == "mismatch")
        & dash["Is_Active_6m"]
        & (~dash.get("package_normalized", False).astype(bool))
    )

    order = {"mismatch": 0, "almost_finished": 1, "active": 2, "finished": 3, "dropout": 9}
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
# 11) ANALYTICS (INCOME + CHARTS) ✅ missing-columns safe (Section 24 compatible)
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

    if payments is None or payments.empty:
        payments = pd.DataFrame(columns=["student", "payment_date", "paid_amount", "number_of_lesson", "modality", "languages"])

    # ✅ Ensure needed columns exist
    for c, default in {
        "student": "",
        "payment_date": None,
        "paid_amount": 0.0,
        "number_of_lesson": 0,
        "modality": "Online",
        "languages": LANG_ES,
    }.items():
        if c not in payments.columns:
            payments[c] = default

    payments["student"] = payments["student"].astype(str).str.strip()
    payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
    payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
    payments["languages"] = payments["languages"].fillna(LANG_ES).astype(str).str.strip()
    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()

    payments = payments.dropna(subset=["payment_date"])
    payments = payments[payments["student"].astype(str).str.len() > 0].copy()

    today = ts_today_naive()

    # ✅ Calendar week Mon–Sun (matches your preference)
    week_start = today - pd.Timedelta(days=int(today.weekday()))  # Monday
    week_end = week_start + pd.Timedelta(days=6)                  # Sunday

    income_all_time = float(payments["paid_amount"].sum()) if not payments.empty else 0.0
    income_this_year = float(
        payments.loc[payments["payment_date"].dt.year == today.year, "paid_amount"].sum()
    ) if not payments.empty else 0.0

    this_month_key = str(today.to_period("M"))
    income_this_month = float(
        payments.loc[payments["payment_date"].dt.to_period("M").astype(str) == this_month_key, "paid_amount"].sum()
    ) if not payments.empty else 0.0

    income_this_week = float(
        payments.loc[(payments["payment_date"] >= week_start) & (payments["payment_date"] <= week_end), "paid_amount"].sum()
    ) if not payments.empty else 0.0

    kpis = {
        "income_all_time": income_all_time,
        "income_this_year": income_this_year,
        "income_this_month": income_this_month,
        "income_this_week": income_this_week,
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
    }

    # Group Key
    if group == "yearly":
        payments["Key"] = payments["payment_date"].dt.to_period("Y").astype(str)
    else:
        payments["Key"] = payments["payment_date"].dt.to_period("M").astype(str)

    # ✅ IMPORTANT: return columns that Section 24 expects
    income_table = (
        payments.groupby("Key", as_index=False)["paid_amount"]
        .sum()
        .rename(columns={"paid_amount": "income"})   # <-- was Income
        .sort_values("Key")
        .reset_index(drop=True)
    )

    by_student = (
        payments.groupby("student", as_index=False)
        .agg(
            total_paid=("paid_amount", "sum"),
            packages=("paid_amount", "size"),
            last_payment=("payment_date", "max"),
        )
        .sort_values("total_paid", ascending=False)
        .reset_index(drop=True)
    )

    # Keep original language normalization (but return expected col names)
    sold_by_language = (
        payments.assign(languages=payments["languages"].replace({LANG_BOTH: "English & Spanish"}))
        .groupby("languages", as_index=False)["paid_amount"].sum()
        .rename(columns={"paid_amount": "income"})
        .sort_values("income", ascending=False)
        .reset_index(drop=True)
    )

    sold_by_modality = (
        payments.groupby("modality", as_index=False)["paid_amount"].sum()
        .rename(columns={"paid_amount": "income"})
        .sort_values("income", ascending=False)
        .reset_index(drop=True)
    )

    return kpis, income_table, by_student, sold_by_language, sold_by_modality
# =========================
# 12) FORECAST (BEHAVIOR-BASED + PIPELINE-AWARE + FINISHED LAST 3 MONTHS)
# =========================
def build_forecast_table(
    payment_buffer_days: int = 0,
    active_window_days: int = 183,
    finished_keep_days: int = 90,
    lookback_days_for_rate: int = 56,
) -> pd.DataFrame:

    dash = rebuild_dashboard(active_window_days=active_window_days, expiry_days=365, grace_days=0)
    if dash is None or dash.empty:
        return pd.DataFrame()

    # Need raw classes to estimate burn rate
    classes = load_table("classes")
    if classes is None or classes.empty:
        classes = pd.DataFrame(columns=["student", "lesson_date", "number_of_lesson", "modality", "note"])
    else:
        for c in ["student", "lesson_date", "number_of_lesson", "modality", "note"]:
            if c not in classes.columns:
                classes[c] = None

    classes["student"] = classes["student"].fillna("").astype(str).str.strip()
    classes["lesson_date"] = to_dt_naive(classes["lesson_date"], utc=True)
    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
    classes["modality"] = classes["modality"].fillna("Online").astype(str).str.strip()
    classes["note"] = classes["note"].fillna("").astype(str)

    today = ts_today_naive()
    active_cutoff = today - pd.Timedelta(days=int(active_window_days))
    finished_cutoff = today - pd.Timedelta(days=int(finished_keep_days))
    rate_cutoff = today - pd.Timedelta(days=int(lookback_days_for_rate))

    # Work on dashboard output
    df = dash.copy()

    # Defensive: ensure expected columns exist
    for c in [
        "Student", "Status", "Payment_Date", "Package_Start_Date", "Package_Expiry_Date",
        "Last_Lesson_Date", "Lessons_Left_Units", "Overused_Units", "Modality", "Languages"
    ]:
        if c not in df.columns:
            df[c] = None

    df["Student"] = df["Student"].fillna("").astype(str).str.strip()
    df = df[df["Student"].str.len() > 0].copy()
    if df.empty:
        return pd.DataFrame()

    # Parse dates (dashboard stores these as YYYY-MM-DD strings)
    df["Payment_Date_dt"] = pd.to_datetime(df["Payment_Date"], errors="coerce")
    df["Package_Start_dt"] = pd.to_datetime(df["Package_Start_Date"], errors="coerce")
    df["Expiry_dt"] = pd.to_datetime(df["Package_Expiry_Date"], errors="coerce")
    df["Last_Lesson_dt"] = pd.to_datetime(df["Last_Lesson_Date"], errors="coerce")

    # Remaining units (dashboard column exists; be defensive)
    df["Lessons_Left_Units"] = pd.to_numeric(df["Lessons_Left_Units"], errors="coerce").fillna(0).astype(int)

    # Determine active
    df["Has_Recent_Lesson"] = df["Last_Lesson_dt"].notna() & (df["Last_Lesson_dt"] >= active_cutoff)
    df["Has_Recent_Payment"] = df["Payment_Date_dt"].notna() & (df["Payment_Date_dt"] >= active_cutoff)
    df["Is_Active"] = df["Has_Recent_Lesson"] | df["Has_Recent_Payment"]

    # Recent finished: status == finished (internal code) + last lesson (fallback: payment) in last N days
    status_code = df["Status"].fillna("").astype(str).str.strip().str.casefold()
    df["Is_Finished"] = status_code.eq("finished")
    df["Finished_Recently"] = df["Is_Finished"] & (
        (df["Last_Lesson_dt"].notna() & (df["Last_Lesson_dt"] >= finished_cutoff)) |
        (df["Payment_Date_dt"].notna() & (df["Payment_Date_dt"] >= finished_cutoff))
    )

    # -------------------------
    # NEW: pipeline-aware keep
    # Keep if:
    # - Active OR Finished_Recently OR has units left (>0)
    # -------------------------
    df = df[df["Is_Active"] | df["Finished_Recently"] | (df["Lessons_Left_Units"] > 0)].copy()
    if df.empty:
        return pd.DataFrame()

    # Estimate burn rate (units/day) from last lookback window per student
    def _units_row(r) -> int:
        if _is_free_note(r.get("note", "")):
            return 0
        return int(r.get("number_of_lesson", 0)) * _units_multiplier(r.get("modality", ""))

    recent = classes.dropna(subset=["lesson_date"]).copy()
    recent = recent[recent["lesson_date"] >= rate_cutoff]

    if not recent.empty:
        recent["Units_Last_Lookback"] = recent.apply(_units_row, axis=1)
        rate_tbl = (
            recent.groupby("student", as_index=False)["Units_Last_Lookback"].sum()
            .rename(columns={"student": "Student"})
        )
        # Global median units/day (better fallback than constant)
        lookback_days = float(max(1, int(lookback_days_for_rate)))
        tmpu = rate_tbl["Units_Last_Lookback"] / lookback_days
        global_median_upd = float(pd.to_numeric(tmpu, errors="coerce").replace([math.inf, -math.inf], 0).fillna(0).median())
    else:
        rate_tbl = pd.DataFrame(columns=["Student", "Units_Last_Lookback"])
        global_median_upd = 0.0

    df = df.merge(rate_tbl, on="Student", how="left")
    df["Units_Last_Lookback"] = pd.to_numeric(df.get("Units_Last_Lookback"), errors="coerce").fillna(0.0)

    lookback_days = float(max(1, int(lookback_days_for_rate)))
    df["Units_Per_Day"] = (df["Units_Last_Lookback"] / lookback_days).replace([math.inf, -math.inf], 0).fillna(0.0)

    # Better fallback: global median, then constant
    # (median might be 0 if there are no recent lessons in the lookback window)
    if global_median_upd and global_median_upd > 0:
        df.loc[df["Units_Per_Day"] <= 0, "Units_Per_Day"] = float(global_median_upd)
    df.loc[df["Units_Per_Day"] <= 0, "Units_Per_Day"] = 0.10  # last resort

    # Estimate finish
    df["Days_To_Finish"] = (df["Lessons_Left_Units"] / df["Units_Per_Day"]).replace([math.inf, -math.inf], 0).fillna(0)
    df["Days_To_Finish"] = df["Days_To_Finish"].clip(lower=0, upper=3650)

    df["Estimated_Finish_Date_dt"] = today + pd.to_timedelta(df["Days_To_Finish"].round().astype(int), unit="D")
    df["Reminder_Date_dt"] = df["Estimated_Finish_Date_dt"] - pd.to_timedelta(int(payment_buffer_days), unit="D")

    # If already finished (0 left), set estimate to today
    done_mask = df["Lessons_Left_Units"] <= 0
    df.loc[done_mask, "Estimated_Finish_Date_dt"] = today
    df.loc[done_mask, "Reminder_Date_dt"] = today - pd.to_timedelta(int(payment_buffer_days), unit="D")

    # Clamp by expiry if expiry exists and is earlier than estimate
    has_exp = df["Expiry_dt"].notna()
    clamp_mask = has_exp & (df["Expiry_dt"] < df["Estimated_Finish_Date_dt"])
    df.loc[clamp_mask, "Estimated_Finish_Date_dt"] = df.loc[clamp_mask, "Expiry_dt"]
    df.loc[clamp_mask, "Reminder_Date_dt"] = df.loc[clamp_mask, "Expiry_dt"] - pd.to_timedelta(int(payment_buffer_days), unit="D")

    # Format for display
    out = df.copy()
    out["Estimated_Finish_Date"] = pd.to_datetime(out["Estimated_Finish_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Reminder_Date"] = pd.to_datetime(out["Reminder_Date_dt"], errors="coerce").dt.strftime("%Y-%m-%d")
    out["Units_Per_Day"] = pd.to_numeric(out.get("Units_Per_Day"), errors="coerce").fillna(0).round(2)
    out["Days_To_Finish"] = pd.to_numeric(out.get("Days_To_Finish"), errors="coerce").fillna(0).round(1)

    # NEW: due flag for UI filtering (buffer becomes meaningful in Analytics)
    out["_rem_dt"] = pd.to_datetime(out["Reminder_Date"], errors="coerce")
    out["Due_Now"] = out["_rem_dt"].notna() & (out["_rem_dt"] <= today)

    # Translate coded values for bilingual UI
    out["Status"] = out.get("Status", "").astype(str).str.strip().str.casefold().apply(translate_status)
    out["Modality"] = out.get("Modality", "").astype(str).apply(translate_modality_value)
    out["Languages"] = out.get("Languages", "").astype(str).apply(translate_language_value)

    keep_cols = [
        "Student",
        "Status",
        "Lessons_Left_Units",
        "Overused_Units",
        "Modality",
        "Languages",
        "Last_Lesson_Date",
        "Payment_Date",
        "Package_Start_Date",
        "Package_Expiry_Date",
        "Units_Per_Day",
        "Days_To_Finish",
        "Estimated_Finish_Date",
        "Reminder_Date",
        "Due_Now",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols].copy()

    # Sort: soonest reminder first, then lowest remaining
    out["_rem"] = pd.to_datetime(out.get("Reminder_Date"), errors="coerce")
    out["_left"] = pd.to_numeric(out.get("Lessons_Left_Units"), errors="coerce").fillna(0)
    out = (
        out.sort_values(["_rem", "_left", "Student"])
           .drop(columns=["_rem", "_left"], errors="ignore")
           .reset_index(drop=True)
    )

    return out

# =========================
# 13) KPI BUBBLES (ROBUST: NO AUTO-RESIZE DEPENDENCY)
# =========================
def kpi_bubbles(values, colors, size=170):
    """
    Robust KPI bubbles:
    - Bubble size scales with numeric value
    - Font size scales with bubble size
    - Organic layout via flex-wrap
    - DOES NOT depend on iframe auto-resize
    """
    compact = bool(st.session_state.get("compact_mode", False))

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

    html = style + bubbles_html

    n = len(values)
    bubbles_per_row = 3 if not compact else 2
    rows = max(1, math.ceil(n / bubbles_per_row))
    frame_h = rows * (max_size + gap) + 80

    components.html(html, height=int(frame_h), scrolling=False)


# =========================
# 14) CALENDAR (EVENTS + RENDER) ✅ bilingual-safe + tz-safe + FullCalendar i18n
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


def build_calendar_events(start_day: date, end_day: date) -> pd.DataFrame:
    schedules = load_schedules()
    overrides = load_overrides()
    color_map, zoom_map, _, _ = student_meta_maps()

    events = []

    # -------------------------
    # Recurring schedules
    # -------------------------
    if schedules is not None and not schedules.empty:
        # be safe: ensure expected cols exist
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
                dt = datetime(cur.year, cur.month, cur.day, h, m)  # tz-naive local

                student = str(row.get("student", "")).strip()
                k = norm_student(student)
                duration = int(pd.to_numeric(row.get("duration_minutes", 60), errors="coerce") or 60)

                events.append(
                    {
                        "DateTime": dt,  # tz-naive local
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
            new_dt = row.get("new_datetime")  # tz-naive local (from load_overrides)
            original_date = row.get("original_date")  # date/timestamp-like
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

                    # keep only if inside current view window
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
                            "Original_Date": pd.to_datetime(original_date, errors="coerce").date()
                            if pd.notna(original_date)
                            else nd.date(),
                        }
                        events_df = pd.concat([events_df, pd.DataFrame([add_row])], ignore_index=True)
                except Exception:
                    pass

    if events_df is None or events_df.empty:
        return events_df

    # Ensure tz-naive (important for sorting + consistency)
    events_df["DateTime"] = to_dt_naive(events_df["DateTime"], utc=False)

    events_df = events_df.dropna(subset=["DateTime"]).sort_values("DateTime").reset_index(drop=True)
    events_df["Time"] = pd.to_datetime(events_df["DateTime"], errors="coerce").dt.strftime("%H:%M")
    events_df["Date"] = pd.to_datetime(events_df["DateTime"], errors="coerce").dt.strftime("%Y-%m-%d")

    return events_df


def render_fullcalendar(events: pd.DataFrame, height: int = 750):
    """
    FullCalendar renderer with:
      ✅ Mon-first week (firstDay=1)
      ✅ Translated calendar UI buttons (Today/Month/Week/Day/List)
      ✅ Translated all-day label
      ✅ Translated "+n more" link
      ✅ Safe for mobile dark mode rendering
    """
    if events is None or events.empty:
        st.info(t("no_events"))
        return

    df = events.copy()
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")
    df = df.dropna(subset=["DateTime"])

    df["Duration_Min"] = pd.to_numeric(df.get("Duration_Min"), errors="coerce").fillna(60).astype(int)
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

    # ---- FullCalendar UI translations (based on ui_lang) ----
    ui_lang = st.session_state.get("ui_lang", "en")
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
    <div id="calendar" style="background:#ffffff;border:1px solid rgba(17,24,39,0.10);border-radius:16px;padding:10px;"></div>

    <link href="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.11/index.global.min.js"></script>

    <style>
      .fc {{ color:#0f172a; }}
      /* Fix iPhone dark mode text disappearing */
      #calendar, #calendar * {{ color: #0f172a !important; }}

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

        // ✅ Monday first (Mon–Sun)
        firstDay: 1,

        headerToolbar: isMobile() ? toolbarMobile : toolbarDesktop,

        // ✅ i18n for the calendar UI
        locale: "{fc_locale}",
        buttonText: {{
          today: "{btn_today}",
          month: "{btn_month}",
          week: "{btn_week}",
          day: "{btn_day}",
          list: "{btn_list}"
        }},
        views: {{
          dayGridMonth: {{ buttonText: "{btn_month}" }},
          timeGridWeek: {{ buttonText: "{btn_week}" }},
          timeGridDay:  {{ buttonText: "{btn_day}" }},
          listWeek:     {{ buttonText: "{btn_list}" }}
        }},
        allDayText: "{all_day_text}",
        moreLinkText: function(n) {{
          return "{more_template}".replace("{{n}}", n);
        }},

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
# 15) HOME SCREEN UI (DARK) - upgraded (FIXED + PERSISTENT AVATAR)
# =========================
def render_home():
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es"):
        current_lang = "en"

    user_name = st.session_state.get("user_name", "Anthony Gonzalez")
    alerts_count = int(st.session_state.get("alerts_count", 0))
    user_id = st.session_state.get("user_id", "demo_user")
    panel = _get_qp("panel", "")

    # ✅ Load avatar from DB once per session (so it persists after refresh)
    if not st.session_state.get("avatar_url"):
        st.session_state["avatar_url"] = get_profile_avatar_url(user_id)

    avatar_url = st.session_state.get("avatar_url", "")
    avatar_style = f"background-image:url('{avatar_url}');" if avatar_url else ""

    # --- Top bar (welcome + icons + language) ---
    st.markdown(
        f"""<div class="home-topbar">
<div class="home-user">
  <a class="home-avatar-wrap"
     href="?page=home&lang={current_lang}&panel=photo"
     target="_self"
     rel="noopener noreferrer"
     title="Change photo">
    <div class="home-avatar" style="{avatar_style}"></div>
    <div class="home-avatar-badge">📷</div>
  </a>

  <div class="home-usertext">
    <div class="home-welcome">{t('welcome').strip()},</div>
    <div class="home-username">{user_name}</div>
  </div>
</div>

<div class="home-actions">
  <a class="home-iconbtn"
     href="?page=home&lang={current_lang}&panel=alerts"
     target="_self"
     rel="noopener noreferrer"
     title="{t('alerts')}">
    <span class="home-ico">🔔</span>
    {f'<span class="home-badge">{alerts_count}</span>' if alerts_count > 0 else ''}
  </a>
  <div class="home-lang">
    <a class="home-langbtn {('on' if current_lang=='en' else '')}"
       href="?page=home&lang=en"
       target="_self"
       rel="noopener noreferrer">EN</a>
    <a class="home-langbtn {('on' if current_lang=='es' else '')}"
       href="?page=home&lang=es"
       target="_self"
       rel="noopener noreferrer">ES</a>
  </div>
</div>
</div>""",
        unsafe_allow_html=True,
    )

    # --- Avatar upload dialog/panel (opens ONLY when clicking avatar) ---
    if panel == "photo":
        # ✅ Clear panel immediately so refresh does NOT reopen the dialog
        _clear_qp("panel")

        try:
            @st.dialog("Update profile photo")
            def _photo_dialog():
                up = st.file_uploader(
                    "Choose a photo",
                    type=["png", "jpg", "jpeg", "webp"],
                    label_visibility="collapsed",
                )

                c1, c2 = st.columns(2)
                with c1:
                    cancel = st.button("Cancel")
                with c2:
                    save = st.button("Save", disabled=(up is None))

                if cancel:
                    st.rerun()

                if save and up is not None:
                    try:
                        url = upload_avatar_to_supabase(up, user_id=user_id)

                        # ✅ Persist in session AND database
                        st.session_state["avatar_url"] = url
                        save_profile_avatar_url(user_id, url)

                        st.success("Profile photo updated ✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

            _photo_dialog()

        except Exception:
            # Fallback if st.dialog isn't available in your Streamlit version
            st.markdown("#### Update profile photo")
            up = st.file_uploader(
                "Choose a photo",
                type=["png", "jpg", "jpeg", "webp"],
                label_visibility="collapsed",
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Close"):
                    st.rerun()
            with col2:
                if st.button("Save", disabled=(up is None)) and up is not None:
                    try:
                        url = upload_avatar_to_supabase(up, user_id=user_id)
                        st.session_state["avatar_url"] = url
                        save_profile_avatar_url(user_id, url)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

    # ---- REAL values ----
    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)

    active_students = 0
    lessons_left_total = 0

    if dash is not None and not dash.empty:
        active_mask = dash["Status"].isin(["active", "almost_finished", "mismatch"])
        active_students = int(active_mask.sum())

        lessons_left_total = int(
            pd.to_numeric(
                dash.loc[active_mask, "Lessons_Left_Units"],
                errors="coerce"
            ).fillna(0).sum()
        )

    # Next lesson
    next_lesson = get_next_lesson_display()

    # Income this year
    kpis, *_ = build_income_analytics(group="monthly")
    income_this_year = float(kpis.get("income_this_year", 0.0))

    # Goal
    scope = "global"
    current_year = int(ts_today_naive().year)
    goal_val = float(get_year_goal(current_year, scope=scope, default=0.0) or 0.0)

    goal_progress = 0.0
    if goal_val > 0:
        goal_progress = max(0.0, min(1.0, income_this_year / goal_val))

    # ---- Render the indicator ----
    render_home_indicator(
        status= t("online"),
        badge= t("today"),
        items=[
            (t("goal"), money_try(goal_val) if goal_val > 0 else "—"),
            (t("ytd_income"), money_try(income_this_year)),
            (t("students"), str(active_students)),
            (t("next"), next_lesson),
        ],
        progress=goal_progress,
        accent="#3B82F6",
    )

    # --- Brand title ---
    st.markdown("<div class='home-title'>CLASS MANAGER</div>", unsafe_allow_html=True)

    # --- Slogan / hero ---
    st.markdown(
        f"""<div class="home-hero">
<div class="home-slogan">{t('home_slogan')}</div>
<div class="home-sub">{t('choose_where_to_go')}</div>
</div>""",
        unsafe_allow_html=True,
    )

    # --- Lead sources row (external links) ---
    st.markdown(
    f"""
    <div class="home-links">

      <div class="home-links-title">
        {t("home_find_students")}
      </div>

      <div class="home-links-row">
        <a class="home-linkchip" href="https://www.armut.com" target="_blank" rel="noopener noreferrer">
          <span class="dot"></span> Armut
        </a>
        <a class="home-linkchip" href="https://www.apprentus.com" target="_blank" rel="noopener noreferrer">
          <span class="dot"></span> Apprentus
        </a>
        <a class="home-linkchip" href="https://www.superprof.com" target="_blank" rel="noopener noreferrer">
          <span class="dot"></span> Superprof
        </a>
        <a class="home-linkchip" href="https://www.ozelders.com" target="_blank" rel="noopener noreferrer">
          <span class="dot"></span> ÖzelDers
        </a>
        <a class="home-linkchip" href="https://preply.com" target="_blank" rel="noopener noreferrer">
          <span class="dot"></span> Preply
        </a>
        <a class="home-linkchip" href="https://www.italki.com" target="_blank" rel="noopener noreferrer">
          <span class="dot"></span> italki
        </a>
      </div>

    </div>
    """,
        unsafe_allow_html=True,
    )

    # --- Section title between links and menu capsules ---
    st.markdown(
        f"""
    <div class="home-links-title home-section-divider">
      {t("home_menu_title")}
    </div>
    """,
        unsafe_allow_html=True,
    )

    # --- Capsule menu (your existing PAGES loop) ---
    for key, label_key, grad in PAGES:
        st.markdown(
            f"""<a class="home-pill home-{key}"
href="?page={key}&lang={current_lang}"
target="_self"
rel="noopener noreferrer"
style="background:{grad};">{t(label_key)}</a>""",
            unsafe_allow_html=True,
        )

    st.markdown("<div class='home-bottom-indicator'></div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)


# =========================
# 16) APP ENTRYPOINT (ROUTER + THEME SWITCH + TOP NAV)
# =========================

def render_top_nav(active_page: str):
    current_lang = st.session_state.get("ui_lang", "en")
    if current_lang not in ("en", "es"):
        current_lang = "en"

    items = [
        ("home",        t("home"),      "🏠"),
        ("dashboard",   t("dashboard"), "📊"),
        ("students",    t("students"),  "👥"),
        ("add_lesson",  t("lesson"),    "🗓️"),
        ("add_payment", t("payment"),   "💳"),
        ("calendar",    t("calendar"),  "📅"),
        ("analytics",   t("analytics"), "📈"),
    ]

    links_html = ""
    for key, label, icon in items:
        active_cls = "active" if key == active_page else ""
        links_html += (
            f'<a class="cm-nav-item {active_cls}" '
            f'href="?page={key}&lang={current_lang}" target="_self">'
            f'<span class="cm-nav-ico">{icon}</span>'
            f'<span class="cm-nav-lab">{label}</span>'
            f"</a>"
        )

    en_on = "on" if current_lang == "en" else ""
    es_on = "on" if current_lang == "es" else ""
    lang_buttons = (
        f'<a class="cm-lang-btn {en_on}" href="?page={active_page}&lang=en" target="_self">EN</a>'
        f'<a class="cm-lang-btn {es_on}" href="?page={active_page}&lang=es" target="_self">ES</a>'
    )

    st.markdown(
        f"""
<style>

/* ================= FIXED TOP NAV ================= */

.cm-topnav {{
 position: fixed;
 top: 0px;
 left: 0%;
 width: 100vw;
 z-index: 99999;

 /* 💎 Blue glass */
 background:
 linear-gradient(180deg,rgba(37,99,235,0.22), rgba(37,99,235,0.12));   
 backdrop-filter: blur(14px);
 -webkit-backdrop-filter: blur(14px);
 border-bottom: 0.8px solid rgba(59,130,246,0.25);
 box-shadow: 0 8px 24px rgba(37,99,235,0.18), 0 0 40px rgba(59,130,246,0.08);
 padding: 10px 12px;
}}

/* Spacer to prevent overlap */
.cm-topnav-spacer {{
  height: 20px;
}}

/* Layout */
.cm-topnav-row {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
}}

.cm-nav-scroll {{
  display:flex;
  gap:10px;
  align-items:center;
  overflow-x:auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 2px;
}}

.cm-nav-scroll::-webkit-scrollbar {{
  display:none;
}}

.cm-nav-item {{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 10px 12px;
  border-radius: 999px;
  border: 1px solid rgba(17,24,39,0.10);
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(6px);
  color:#0f172a !important;
  text-decoration:none !important;
  font-weight:700;
  white-space:nowrap;
  transition: transform 140ms ease,
              box-shadow 140ms ease,
              border-color 140ms ease;
}}

.cm-nav-item:hover {{
  transform: translateY(-1px);
  box-shadow: 0 0 0 4px rgba(59,130,246,0.10);
  border-color: rgba(59,130,246,0.35);
}}

.cm-nav-item.active {{
  border: 2px solid rgba(37,99,235,0.85);
  box-shadow: 0 0 0 4px rgba(37,99,235,0.10);
}}

.cm-nav-ico {{
  font-size:16px;
  line-height:1;
}}

.cm-nav-lab {{
  font-size:14px;
  line-height:1;
}}

.cm-lang {{
  display:flex;
  gap:8px;
  align-items:center;
}}

.cm-lang-btn {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:44px;
  height:44px;
  border-radius:999px;
  border:1px solid rgba(17,24,39,0.12);
  background: rgba(255,255,255,0.85);
  color:#0f172a !important;
  text-decoration:none !important;
  font-weight:800;
}}

.cm-lang-btn.on {{
  border:2px solid rgba(37,99,235,0.85);
  box-shadow: 0 0 0 4px rgba(37,99,235,0.10);
}}

@media (max-width: 720px) {{
  .cm-nav-lab {{
    display:none;
  }}
}}

</style>

<div class="cm-topnav">
  <div class="cm-topnav-row">
    <div class="cm-nav-scroll">{links_html}</div>
    <div class="cm-lang">{lang_buttons}</div>
  </div>
</div>

<div class="cm-topnav-spacer"></div>
""",
        unsafe_allow_html=True,
    )


# ---------- ROUTER + THEME ----------
page = st.session_state.page

if page == "home":
    load_css_home_dark()
else:
    load_css_app_light(
        compact=bool(st.session_state.get("compact_mode", False))
    )

students = load_students()

if page == "home":
    render_home()
    st.stop()
    
render_top_nav(page)

# =========================
# 17) PAGE: DASHBOARD
# =========================
if page == "dashboard":
    page_header(t("dashboard"))
    st.caption(t("manage_current_students"))

    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)
    if dash is None or dash.empty:
        st.info(t("no_data"))
        st.stop()

    d = dash.copy()

    # --- IMPORTANT: treat status as INTERNAL CODES (lowercase) ---
    d["Status"] = d.get("Status", "").fillna("").astype(str).str.strip().str.casefold()
    d["Is_Active_6m"] = pd.Series(d.get("Is_Active_6m", False)).fillna(False).astype(bool)

    d = d[
        (d["Status"].isin(["active", "almost_finished", "mismatch"])) |
        ((d["Status"] == "finished") & (d["Is_Active_6m"] == True))
    ].copy()

    # ---------------------------------------
    # TODAY'S LESSONS (row: done | student+time | link)
    # ---------------------------------------
    st.subheader("📅 " + t("todays_lessons"))

    st.markdown(
        """
        <style>
          .tl-row{ display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
          .tl-left{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    today = date.today()
    today_events = build_calendar_events(today, today)

    # Keep a DF for WhatsApp templates (confirm/cancel)
    today_df = pd.DataFrame()

    if today_events is None or today_events.empty:
        st.caption(t("no_events_today"))
    else:
        df = today_events.copy()
        df["Student"] = df["Student"].astype(str).str.strip()
        df["Time"] = df["Time"].astype(str).str.strip()
        df["Zoom_Link"] = df.get("Zoom_Link", "").fillna("").astype(str).str.strip()
        df["Source"] = df.get("Source", "").fillna("").astype(str).str.strip().str.lower()
        df = df.sort_values("Time").reset_index(drop=True)

        # Save for WhatsApp Templates
        today_df = df.copy()

        for _, r in df.iterrows():
            student = str(r.get("Student", "")).strip()
            when = str(r.get("Time", "")).strip()
            link = str(r.get("Zoom_Link", "")).strip()

            # Stable unique lesson key per event
            lesson_id = f"{today.isoformat()}_{student}_{when}"
            key_done = f"today_done_{lesson_id}"

            # ✅ Row layout: Done | Info | Link
            c_done, c_info, c_link = st.columns([0.55, 2.2, 1.3], vertical_alignment="center")

            with c_done:
                done_now = bool(st.session_state.get(key_done, False))
                done_now = st.toggle(t("mark_done"), value=done_now, key=key_done)

            # Styling AFTER the toggle value is known
            name_style = "font-weight:900;"
            time_style = "font-weight:900;"
            if done_now:
                name_style += "text-decoration:line-through; opacity:0.55;"
                time_style += "text-decoration:line-through; opacity:0.55;"

            with c_info:
                st.markdown(
                    f"""
                    <div class='tl-row'>
                      <div class='tl-left'>
                        <span style="{name_style}">{student}</span>
                        <span style="{time_style}">{when}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with c_link:
                # Link disappears when done (keeps dashboard clean)
                if (not done_now) and link.startswith("http"):
                    try:
                        st.link_button(
                            t("open_link"),
                            link,
                            use_container_width=True,
                            key=f"today_link_{lesson_id}",
                        )
                    except Exception:
                        st.markdown(
                            f"<a href='{link}' target='_blank' style='text-decoration:none;'>"
                            f"<button style='width:100%;padding:0.62rem 1.0rem;border-radius:14px;"
                            f"border:1px solid rgba(17,24,39,0.12);background:white;font-weight:700;cursor:pointer;'>"
                            f"{t('open_link')}</button></a>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown("<div style='height:38px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------
    # TAKE ACTION
    # ---------------------------------------
    st.subheader(t("take_action"))

    due_df = d[d["Status"] == "almost_finished"].copy()
    due_df["Lessons_Left"] = pd.to_numeric(due_df.get("Lessons_Left_Units"), errors="coerce").fillna(0).astype(int)
    due_df = due_df.sort_values(["Lessons_Left", "Student"])

    if due_df.empty:
        st.caption(t("no_data"))
    else:
        cols_due = ["Student", "Lessons_Left", "Status", "Modality", "Languages", "Payment_Date", "Last_Lesson_Date"]
        cols_due = [c for c in cols_due if c in due_df.columns]

        show_due = due_df[cols_due].copy()
        show_due["Status"] = show_due["Status"].apply(translate_status)
        show_due["Modality"] = show_due.get("Modality", "").apply(translate_modality_value)
        show_due["Languages"] = show_due.get("Languages", "").apply(translate_language_value)

        st.dataframe(translate_df(pretty_df(show_due)), use_container_width=True, hide_index=True)

    # ---------------------------------------
    # WHATSAPP TEMPLATES (PACKAGE / CONFIRM / CANCEL)
    # ---------------------------------------
    st.subheader(t("whatsapp_templates_title"))

    # IMPORTANT: Streamlit widgets keep value by key.
    # To ensure the message updates when user changes template/student/lang,
    # we overwrite st.session_state["wa_msg_box_visible"] when signature changes.

    # Language picker controls MESSAGE language
    ui_lang = st.session_state.get("ui_lang", "en")
    if ui_lang not in ("en", "es", "tr"):
        ui_lang = "en"

    wa_lang = st.selectbox(
        t("whatsapp_message_language"),
        ["en", "es", "tr"],
        format_func=_msg_lang_label,
        index=["en", "es", "tr"].index(ui_lang),
        key="wa_lang_pick",
    )

    template_type = st.radio(
        t("whatsapp_choose_template"),
        ["package", "confirm_today", "cancel_today"],
        format_func=lambda x: {
            "package": t("whatsapp_tpl_package"),
            "confirm_today": t("whatsapp_tpl_confirm"),
            "cancel_today": t("whatsapp_tpl_cancel"),
        }.get(x, x),
        horizontal=True,
        key="wa_template_type",
    )

    # Phone map
    _, _, _, phone_map = student_meta_maps()

    # Decide eligible list + pick student
    pick = ""
    default_msg = ""

    if template_type == "package":
        eligible = due_df.copy()
        if eligible is None or eligible.empty or ("Student" not in eligible.columns):
            st.info(t("whatsapp_no_students_for_template"))
            # Ensure textbox doesn't keep stale content when nothing is eligible
            st.session_state["wa_msg_box_visible"] = ""
            st.stop()

        pick = st.selectbox(
            t("contact_student"),
            eligible["Student"].tolist(),
            key="wa_pick_student_package",
        )

        st_row = eligible[eligible["Student"] == pick].iloc[0]
        status_val = st_row.get("Status", "almost_finished")

        default_msg = (
            build_msg_package_header(pick, wa_lang, status_val)
            + "\n"
            + build_pricing_block(wa_lang)
        )

    else:
        eligible = today_df.copy()
        if eligible is None or eligible.empty or ("Student" not in eligible.columns):
            st.info(t("whatsapp_no_students_for_template"))
            st.session_state["wa_msg_box_visible"] = ""
            st.stop()

        pick = st.selectbox(
            t("contact_student"),
            eligible["Student"].tolist(),
            key="wa_pick_student_today",
        )

        st_row = eligible[eligible["Student"] == pick].iloc[0]
        time_text = str(st_row.get("Time", "") or "").strip()

        if template_type == "confirm_today":
            default_msg = build_msg_confirm(pick, wa_lang, time_text=time_text)
        else:
            default_msg = build_msg_cancel(pick, wa_lang)

    raw_phone = phone_map.get(norm_student(pick), "")

    # -------------------------------------------------
    # Force refresh of textbox when selection changes
    # -------------------------------------------------
    sig_key = "wa_signature"
    signature = f"{template_type}||{wa_lang}||{pick}"

    if st.session_state.get(sig_key) != signature:
        st.session_state[sig_key] = signature
        st.session_state["wa_msg_box_visible"] = default_msg

    # Editable message (bound to state key)
    msg = st.text_area(
        t("whatsapp_message"),
        height=260,
        key="wa_msg_box_visible",
    )

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

    # ---------------------------------------
    # CURRENT STUDENTS AND PACKAGES (BUBBLES)
    # ---------------------------------------
    st.subheader(t("academic_status"))

    total_students = int(len(d))
    active_count = int((d["Status"] == "active").sum())
    finish_soon_count = int((d["Status"] == "almost_finished").sum())
    finished_recent_count = int((d["Status"] == "finished").sum())
    mismatch_count = int((d["Status"] == "mismatch").sum())

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
        size=70,
    )

    with st.expander(t("current_packages"), expanded=False):
        d_display = d.copy()
        d_display["Status"] = d_display["Status"].apply(translate_status)
        d_display["Modality"] = d_display.get("Modality", "").apply(translate_modality_value)
        d_display["Languages"] = d_display.get("Languages", "").apply(translate_language_value)

        st.dataframe(
            translate_df(pretty_df(d_display)),
            use_container_width=True,
            hide_index=True,
        )

    # ---------------------------------------
    # MISMATCHES
    # ---------------------------------------
    st.subheader(t("mismatches"))
    mismatch_df = d[d["Status"] == "mismatch"].copy()

    if mismatch_df.empty:
        st.caption(t("all_good_no_action_required"))
    else:
        cols_mm = [
            "Student",
            "Overused_Units",
            "Lessons_Left_Units",
            "Lessons_Taken_Units",
            "Lessons_Paid_Total",
            "Payment_Date",
            "Package_Start_Date",
            "Modality",
            "Languages",
            "Payment_ID",
            "Normalize_Allowed",
        ]
        cols_mm = [c for c in cols_mm if c in mismatch_df.columns]

        mm_show = mismatch_df[cols_mm].copy()
        if "Modality" in mm_show.columns:
            mm_show["Modality"] = mm_show["Modality"].apply(translate_modality_value)
        if "Languages" in mm_show.columns:
            mm_show["Languages"] = mm_show["Languages"].apply(translate_language_value)

        st.dataframe(translate_df(pretty_df(mm_show)), use_container_width=True, hide_index=True)

        st.markdown(f"### {t('normalize')}")

        pick_m = st.selectbox(
            t("select_student"),
            mismatch_df["Student"].tolist(),
            key="dash_norm_pick_student",
        )

        rowm = mismatch_df[mismatch_df["Student"] == pick_m].iloc[0]
        pid = int(rowm.get("Payment_ID", 0))
        can_norm = bool(rowm.get("Normalize_Allowed", False))

        st.caption(t("normalized_note"))

        adj_units = st.number_input(
            t("adjust_units"),
            min_value=-1000,
            max_value=1000,
            value=0,
            step=1,
            key="dash_norm_adj_units",
        )
        norm_note = st.text_input(
            t("normalized_note"),
            value=t("normalized_default_note"),
            key="dash_norm_note",
        )

        if st.button(t("normalize"), disabled=not can_norm, key="dash_norm_save_btn"):
            try:
                updates = {
                    "lesson_adjustment_units": int(adj_units),
                    "package_normalized": True,
                    "normalized_note": str(norm_note or "").strip(),
                    "normalized_at": datetime.now(timezone.utc).isoformat(),
                }
                ok = update_payment_row(pid, updates)
                if ok:
                    st.success(t("done_ok"))
                    st.rerun()
                else:
                    st.error(t("normalize_failed"))
            except Exception as e:
                st.error(f"{t('normalize_failed')}\n\n{e}")

# =========================
# 18) PAGE: STUDENTS
# =========================
elif page == "students":
    page_header(t("students"))
    st.caption(t("add_and_manage_students"))

    students_df = load_students_df()

    st.markdown(f"### {t('add_new')}")
    new_student = st.text_input(t("new_student_name"), key="new_student_name")

    if st.button(f"{t('add')} {t('student')}", key="add_student"):
        if not new_student.strip():
            st.error(t("no_data"))
        else:
            ensure_student(new_student)
            st.success(t("done_ok"))
            st.rerun()

    st.markdown(f"### {t('manage_students')}")
    if students_df.empty:
        st.info(t("no_students"))
    else:
        with st.expander(t("student_profile"), expanded=False):
            student_list = sorted(students_df["student"].unique().tolist())
            selected_student = st.selectbox(t("select_student"), student_list, key="edit_student_select")

            student_row = students_df.loc[students_df["student"] == selected_student].iloc[0]
            sid = norm_student(selected_student)  # stable per student

            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input(t("email"), value=student_row.get("email", ""), key=f"student_email_{sid}")
                zoom_link = st.text_input(t("zoom_link"), value=student_row.get("zoom_link", ""), key=f"student_zoom_{sid}")
                phone = st.text_input(t("whatsapp_phone"), value=student_row.get("phone", ""), key=f"student_phone_{sid}")
                st.caption(t("examples_phone"))
            with col2:
                color = st.color_picker(t("calendar_color"), value=student_row.get("color", "#3B82F6"), key=f"student_color_{sid}")
                notes = st.text_area(t("notes"), value=student_row.get("notes", ""), key=f"student_notes_{sid}")

            if phone and not normalize_phone_for_whatsapp(phone) and len(_digits_only(phone)) < 11:
                st.warning(t("examples_phone"))

            if st.button(t("save"), key=f"btn_save_student_profile_{sid}"):
                update_student_profile(selected_student, email, zoom_link, notes, color, phone)
                st.success(t("done_ok"))
                st.rerun()

    with st.expander(t("student_list"), expanded=False):
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
                st.markdown(f"### {t('lessons')}")
                st.dataframe(translate_df_headers(lessons_df), use_container_width=True, hide_index=True)
            with colB:
                st.markdown(f"### {t('payments')}")
                st.dataframe(translate_df_headers(payments_df), use_container_width=True, hide_index=True)

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
                    st.success(t("done_ok"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('delete')} failed.\n\n{e}")

# =========================
# 19) PAGE: ADD LESSON
# =========================
elif page == "add_lesson":
    page_header(t("lessons"))
    st.caption(t("keep_track_of_your_lessons"))

    st.markdown(f"### {t('record_attendance')}")
    if not students:
        st.info(t("no_students"))
    else:
        student = st.selectbox(t("select_student"), students, key="lesson_student")
        number = st.number_input(t("units"), min_value=1, max_value=10, value=1, step=1, key="lesson_number")
        lesson_date = st.date_input(t("date"), key="lesson_date")

        modality_internal = st.selectbox(
            t("modality"),
            ["Online", "Offline"],
            format_func=lambda x: t("online") if x == "Online" else t("offline"),
            key="lesson_modality",
        )
        note = st.text_input(t("notes_optional"), key="lesson_note")

        pkg_lang = latest_payment_languages_for_student(student)
        lang_options, lang_default = allowed_lesson_language_from_package(pkg_lang)

        if lang_default is not None:
            lesson_lang = lang_default
            st.caption(f"{t('lesson_language')}: **{translate_language_value(lesson_lang)}**")
        else:
            lesson_lang = st.selectbox(
                t("lesson_language"),
                lang_options,
                format_func=translate_language_value,
                key="lesson_lang_select",
            )

        if st.button(t("save"), key="btn_save_lesson"):
            add_class(
                student=student,
                number_of_lesson=int(number),
                lesson_date=lesson_date.isoformat(),
                modality=modality_internal,
                note=note,
                lesson_language=lesson_lang,
            )
            st.success(t("saved"))
            st.rerun()

        with st.expander(t("lesson_editor"), expanded=False):
            st.caption(t("warning_apply"))

            with st.expander(t("delete_lesson"), expanded=False):
                st.caption(t("warning_apply"))
                del_lesson_id = st.number_input(
                    t("lesson_id"),
                    min_value=1,
                    step=1,
                    key="del_lesson_id",
                )
                c1, c2 = st.columns([1, 2])
                with c1:
                    confirm_del = st.checkbox(t("confirm_delete_student"), key="confirm_del_lesson")  # reuse text
                with c2:
                    if st.button(t("delete_lesson"), disabled=not confirm_del, key="btn_delete_lesson"):
                        try:
                            delete_row("classes", int(del_lesson_id))
                            st.success(t("done_ok"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('delete')} failed: {e}")

            st.divider()

            classes = load_table("classes")
            if classes.empty:
                st.info(t("no_data"))
            else:
                classes["student"] = classes.get("student", "").astype(str).str.strip()
                classes = classes[classes["student"] == student].copy()
                if classes.empty:
                    st.info(t("no_data"))
                else:
                    for c in ["id", "lesson_date", "number_of_lesson", "modality", "lesson_language", "note"]:
                        if c not in classes.columns:
                            classes[c] = None

                    classes["lesson_date"] = pd.to_datetime(classes["lesson_date"], errors="coerce").dt.date
                    classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(1).astype(int)
                    classes["modality"] = classes["modality"].fillna("Online").astype(str)
                    classes["lesson_language"] = classes["lesson_language"].fillna("").astype(str)

                    show_cols = ["id", "lesson_date", "number_of_lesson", "modality", "lesson_language", "note"]
                    ed = (
                        classes[show_cols]
                        .sort_values(["lesson_date", "id"], ascending=[False, False])
                        .reset_index(drop=True)
                    )

                    if lang_default is not None:
                        ed["lesson_language"] = ed["lesson_language"].replace({"": lang_default, None: lang_default})

                    edited = st.data_editor(
                        ed,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "id": st.column_config.NumberColumn(t("id"), disabled=True),
                            "lesson_date": st.column_config.DateColumn(t("date")),
                            "number_of_lesson": st.column_config.NumberColumn(t("units"), min_value=1, step=1),
                            "modality": st.column_config.SelectboxColumn(t("modality"), options=["Online", "Offline"]),
                            "lesson_language": st.column_config.SelectboxColumn(t("lesson_language"), options=[LANG_EN, LANG_ES, ""]),
                            "note": st.column_config.TextColumn(t("note")),
                        },
                    )

                    if st.button(t("apply_changes"), key="apply_class_bulk"):
                        ok_all = True
                        for _, r in edited.iterrows():
                            cid = int(r["id"])
                            ll = str(r.get("lesson_language", "") or "").strip()
                            if lang_default is not None and not ll:
                                ll = lang_default

                            updates = {
                                "lesson_date": pd.to_datetime(r["lesson_date"]).date().isoformat()
                                if pd.notna(r["lesson_date"])
                                else None,
                                "number_of_lesson": int(r["number_of_lesson"]),
                                "modality": str(r["modality"]).strip(),
                                "note": str(r.get("note", "") or "").strip(),
                                "lesson_language": ll if ll in (LANG_EN, LANG_ES) else None,
                            }
                            if not update_class_row(cid, updates):
                                ok_all = False

                        if ok_all:
                            st.success(t("done_ok"))
                            st.rerun()
                        else:
                            st.error("Some updates failed.")  # add to dictionary if you want

# =========================
# 20) PAGE: ADD PAYMENT
# =========================
elif page == "add_payment":
    page_header(t("payment"))
    st.caption(t("add_and_manage_your_payments"))
    
    render_pricing_editor()

    if not students:
        st.info(t("no_students"))
    else:
        student_p = st.selectbox(t("select_student"), students, key="pay_student")

        lessons_paid = st.number_input(
            t("lessons_paid"),
            min_value=1,
            max_value=500,
            value=44,
            step=1,
            key="pay_lessons_paid",
        )
        payment_date = st.date_input(t("payment_date"), key="pay_date")
        paid_amount = st.number_input(
            t("paid_amount"),
            min_value=0.0,
            value=0.0,
            step=100.0,
            key="pay_amount",
        )

        # IMPORTANT: store canonical DB values ("Online"/"Offline"), display translated labels
        modality_p = st.selectbox(
            t("modality"),
            options=["Online", "Offline"],
            format_func=lambda x: t("online") if x == "Online" else t("offline"),
            key="pay_modality",
        )

        # IMPORTANT: store canonical DB values ("English"/"Spanish"/"English,Spanish")
        langs_selected = st.multiselect(
            t("package_languages"),
            options=[LANG_EN, LANG_ES],
            default=DEFAULT_PACKAGE_LANGS,
            key="pay_languages_multi",
        )
        languages_value = pack_languages(langs_selected)

        use_custom_start = st.checkbox(
            t("starts_different"),
            value=False,
            key="pay_custom_start",
        )
        if use_custom_start:
            pkg_start = st.date_input(t("package_start"), value=payment_date, key="pay_pkg_start")
        else:
            pkg_start = payment_date

        # If you later add expiry UI, set pkg_expiry to a date
        pkg_expiry = None

        if st.button(t("save"), key="btn_save_payment"):
            add_payment(
                student=student_p,
                number_of_lesson=int(lessons_paid),
                payment_date=payment_date.isoformat(),
                paid_amount=float(paid_amount),
                modality=str(modality_p),
                languages=languages_value,
                package_start_date=pkg_start.isoformat() if pkg_start else payment_date.isoformat(),
                package_expiry_date=pkg_expiry.isoformat() if pkg_expiry else None,
                lesson_adjustment_units=0,
                package_normalized=False,
                normalized_note="",
            )
            st.success(t("saved"))
            st.rerun()

        # ----------------------------
        # PAYMENT EDITOR (BULK + DELETE BY ID INSIDE)
        # ----------------------------
        with st.expander(t("payment_editor"), expanded=False):
            st.caption(t("warning_apply"))

            # Delete by ID (inside editor)
            with st.expander(t("delete_payment"), expanded=False):
                st.caption(t("delete_payment_help"))

                del_payment_id = st.number_input(
                    t("payment_id"),
                    min_value=1,
                    step=1,
                    key="del_payment_id",
                )
                c1, c2 = st.columns([1, 2])
                with c1:
                    confirm_del_p = st.checkbox(t("delete_warning_undo"), key="confirm_del_payment")
                with c2:
                    if st.button(t("delete_payment"), disabled=not confirm_del_p, key="btn_delete_payment"):
                        try:
                            delete_row("payments", int(del_payment_id))
                            st.success(t("payment_deleted"))
                            st.rerun()
                        except Exception as e:
                            st.error(f"{t('delete_failed')}: {e}")

            st.divider()

            payments = load_table("payments")
            if payments.empty:
                st.info(t("no_data"))
            else:
                payments["student"] = payments.get("student", "").astype(str).str.strip()
                payments = payments[payments["student"] == student_p].copy()

                if payments.empty:
                    st.info(t("no_data"))
                else:
                    for c in [
                        "id",
                        "payment_date",
                        "number_of_lesson",
                        "paid_amount",
                        "modality",
                        "languages",
                        "package_start_date",
                        "package_expiry_date",
                        "lesson_adjustment_units",
                        "package_normalized",
                        "normalized_note",
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
                    payments["languages"] = payments["languages"].fillna(LANG_ES).astype(str).str.strip()
                    payments["modality"] = payments["modality"].fillna("Online").astype(str).str.strip()

                    show_cols = [
                        "id",
                        "payment_date",
                        "number_of_lesson",
                        "paid_amount",
                        "modality",
                        "languages",
                        "package_start_date",
                        "package_expiry_date",
                        "lesson_adjustment_units",
                        "package_normalized",
                        "normalized_note",
                    ]
                    ed = (
                        payments[show_cols]
                        .sort_values(["payment_date", "id"], ascending=[False, False])
                        .reset_index(drop=True)
                    )

                    edited = st.data_editor(
                        ed,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "id": st.column_config.NumberColumn(t("id"), disabled=True),
                            "payment_date": st.column_config.DateColumn(t("payment_date")),
                            "number_of_lesson": st.column_config.NumberColumn(t("lessons_paid"), min_value=1, step=1),
                            "paid_amount": st.column_config.NumberColumn(t("paid_amount"), min_value=0.0, step=100.0),
                            # Canonical values in DB, translated labels in UI
                            "modality": st.column_config.SelectboxColumn(
                                t("modality"),
                                options=["Online", "Offline"],
                                format_func=lambda x: t("online") if x == "Online" else t("offline"),
                            ),
                            "languages": st.column_config.SelectboxColumn(
                                t("package_languages"),
                                options=[LANG_EN, LANG_ES, LANG_BOTH],
                                format_func=translate_language_value,
                            ),
                            "package_start_date": st.column_config.DateColumn(t("package_start")),
                            "package_expiry_date": st.column_config.DateColumn(t("package_expiry")),
                            "lesson_adjustment_units": st.column_config.NumberColumn(t("adjust_units"), step=1),
                            "package_normalized": st.column_config.CheckboxColumn(t("package_normalized")),
                            "normalized_note": st.column_config.TextColumn(t("normalized_note")),
                        },
                    )

                    if st.button(t("apply_changes"), key="apply_payment_bulk"):
                        ok_all = True

                        for _, r in edited.iterrows():
                            pid = int(r["id"])

                            languages_val = str(r.get("languages") or LANG_ES).strip()
                            if languages_val not in ALLOWED_LANGS:
                                languages_val = LANG_ES

                            modality_val = str(r.get("modality") or "Online").strip()
                            if modality_val not in ("Online", "Offline"):
                                modality_val = "Online"

                            updates = {
                                "payment_date": pd.to_datetime(r["payment_date"]).date().isoformat()
                                if pd.notna(r["payment_date"])
                                else None,
                                "number_of_lesson": int(r["number_of_lesson"]),
                                "paid_amount": float(r["paid_amount"]),
                                "modality": modality_val,
                                "languages": languages_val,
                                "package_start_date": pd.to_datetime(r["package_start_date"]).date().isoformat()
                                if pd.notna(r["package_start_date"])
                                else None,
                                "package_expiry_date": pd.to_datetime(r["package_expiry_date"]).date().isoformat()
                                if pd.notna(r["package_expiry_date"])
                                else None,
                                "lesson_adjustment_units": int(r.get("lesson_adjustment_units", 0)),
                                "package_normalized": bool(r.get("package_normalized", False)),
                                "normalized_note": str(r.get("normalized_note", "") or "").strip(),
                                "normalized_at": datetime.now(timezone.utc).isoformat()
                                if (
                                    bool(r.get("package_normalized", False))
                                    or str(r.get("normalized_note", "") or "").strip()
                                )
                                else None,
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
                                    cls["student"] = cls.get("student", "").astype(str).str.strip()
                                    cls = cls[cls["student"] == student_p].copy()
                                    if "lesson_language" not in cls.columns:
                                        cls["lesson_language"] = None
                                    cls["lesson_language"] = cls["lesson_language"].fillna("").astype(str)

                                    missing = cls[
                                        (cls["lesson_language"].str.strip() == "") | (cls["lesson_language"].isna())
                                    ]
                                    for _, rr in missing.iterrows():
                                        update_class_row(int(rr["id"]), {"lesson_language": single_default})
                            except Exception:
                                pass

                        if ok_all:
                            st.success(t("updated"))
                            st.rerun()
                        else:
                            st.error(t("some_updates_failed"))

# =========================
# 21) PAGE: SCHEDULE (legacy)
# =========================
elif page == "schedule":
    go_to("calendar")
    st.rerun()

# =========================
# 21.1) PAGE: CALENDAR
# =========================
elif page == "calendar":
    page_header(t("calendar"))
    st.caption(t("create_and_manage_your_weekly_program"))

    # ---------------------------------------
    # VIEW SELECTOR
    # ---------------------------------------
    view = st.radio(
        t("view"),
        options=["today", "this_week", "this_month"],
        index=1,
        horizontal=True,
        key="calendar_view",
        format_func=lambda k: t(k),
    )

    today_d = date.today()

    if view == "today":
        start_day = today_d
        end_day = today_d
    elif view == "this_week":
        start_day = today_d - timedelta(days=today_d.weekday())
        end_day = start_day + timedelta(days=6)
    else:
        start_day = date(today_d.year, today_d.month, 1)
        next_month = (
            date(today_d.year + 1, 1, 1)
            if today_d.month == 12
            else date(today_d.year, today_d.month + 1, 1)
        )
        end_day = next_month - timedelta(days=1)

    events = build_calendar_events(start_day, end_day)

    # ---------------------------------------
    # CALENDAR RENDER
    # ---------------------------------------
    if events.empty:
        st.info(t("no_data"))
    else:
        students_list = sorted(events["Student"].unique().tolist())

        if "calendar_filter_students" not in st.session_state:
            st.session_state.calendar_filter_students = students_list
        else:
            missing = [
                s for s in students_list
                if s not in st.session_state.calendar_filter_students
            ]
            if missing:
                st.session_state.calendar_filter_students = students_list

        colA, colB = st.columns([3, 1])
        with colA:
            selected_students = st.multiselect(
                t("filter_students"),
                students_list,
                key="calendar_filter_students",
            )
        with colB:
            if st.button(t("reset"), use_container_width=True, key="calendar_reset"):
                st.session_state.calendar_filter_students = students_list
                st.rerun()

        filtered = events[events["Student"].isin(selected_students)].copy()

        render_fullcalendar(
            filtered,
            height=980 if st.session_state.get("compact_mode", False) else 1050,
        )

    # =======================================
    # SCHEDULE SECTION
    # =======================================
    st.subheader(t("schedule"))

    if not students:
        st.info(t("no_students"))
    else:
        schedules = load_schedules()

        # ---------------------------------------
        # ADD SCHEDULE
        # ---------------------------------------
        with st.expander(f"{t('add')} {t('schedule')}", expanded=False):

            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

            with c1:
                sch_student = st.selectbox(
                    t("select_student"), students, key="cal_sch_student"
                )

            with c2:
                weekday_names = [
                    t("monday"), t("tuesday"), t("wednesday"),
                    t("thursday"), t("friday"), t("saturday"), t("sunday")
                ]
                sch_weekday = st.selectbox(
                    t("weekday"),
                    list(range(7)),
                    format_func=lambda x: f"{int(x)} ({weekday_names[int(x)]})",
                    key="cal_sch_weekday",
                )

            with c3:
                sch_time = st.text_input(
                    t("time_hhmm"), value="10:00", key="cal_sch_time"
                )

            with c4:
                sch_duration = st.number_input(
                    t("duration_minutes"),
                    min_value=15,
                    max_value=360,
                    value=60,
                    step=15,
                    key="cal_sch_duration",
                )

            with c5:
                sch_active = st.checkbox(
                    t("active_flag"), value=True, key="cal_sch_active"
                )

            if st.button(t("add"), key="cal_btn_add_schedule"):
                add_schedule(
                    sch_student,
                    sch_weekday,
                    sch_time,
                    sch_duration,
                    sch_active,
                )
                st.success(t("saved"))
                st.rerun()

        # ---------------------------------------
        # CURRENT SCHEDULE TABLE (TRANSLATED)
        # ---------------------------------------
        with st.expander(t("current_schedule"), expanded=False):

            if schedules.empty:
                st.info(t("no_data"))
            else:
                show = schedules.copy()

                for c in ["id", "student", "weekday", "time", "duration_minutes", "active"]:
                    if c not in show.columns:
                        show[c] = None

                weekday_names = [
                    t("monday"), t("tuesday"), t("wednesday"),
                    t("thursday"), t("friday"), t("saturday"), t("sunday")
                ]

                show["weekday"] = pd.to_numeric(
                    show["weekday"], errors="coerce"
                ).fillna(0).astype(int).clip(0, 6)

                show["weekday"] = show["weekday"].apply(
                    lambda i: f"{int(i)} ({weekday_names[int(i)]})"
                )

                show = show[
                    ["id", "student", "weekday", "time", "duration_minutes", "active"]
                ].sort_values(["student", "weekday", "time"])

                st.dataframe(
                    translate_df_headers(pretty_df(show)),
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown(f"#### {t('delete_scheduled_lesson')}")
                st.caption(t("delete_schedule_warning"))

                del_id = st.number_input(
                    t("schedule_id"),
                    min_value=1,
                    step=1,
                    key="cal_del_schedule_id",
                )

                confirm_del_s = st.checkbox(
                    t("delete_warning_undo"),
                    key="confirm_del_schedule",
                )

                if st.button(
                    t("delete"),
                    disabled=not confirm_del_s,
                    key="cal_btn_delete_schedule",
                ):
                    delete_schedule(del_id)
                    st.success(t("deleted"))
                    st.rerun()

    # =======================================
    # MODIFY CALENDAR (OVERRIDES)
    # =======================================
    st.subheader(t("modify_calendar"))

    overrides = load_overrides()
    students_master = load_students()

    # ---------------------------------------
    # CANCEL OR RESCHEDULE
    # ---------------------------------------
    with st.expander(t("cancel_or_reschedule"), expanded=False):

        if not students_master:
            st.info(t("no_students"))
        else:
            c1, c2 = st.columns(2)

            with c1:
                ov_student = st.selectbox(
                    t("override_student"),
                    students_master,
                    key="ov_student",
                )

                ov_original_date = st.date_input(
                    t("override_original_date"),
                    value=today_d,
                    key="ov_original_date",
                )

                ov_status = st.selectbox(
                    t("override_status"),
                    options=["scheduled", "cancelled"],
                    format_func=lambda x:
                        t("override_scheduled")
                        if x == "scheduled"
                        else t("override_cancel"),
                    key="ov_status",
                )

            with c2:
                ov_new_dt = st.date_input(
                    t("override_new_date"),
                    value=today_d,
                    key="ov_new_date",
                )

                ov_new_time = st.text_input(
                    t("override_new_time_hhmm"),
                    value="10:00",
                    key="ov_new_time",
                )

                ov_duration = st.number_input(
                    t("override_duration"),
                    min_value=15,
                    max_value=360,
                    value=60,
                    step=15,
                    key="ov_duration",
                )

            ov_note = st.text_input(
                t("override_note"),
                value="",
                key="ov_note",
            )

            new_dt = None
            if ov_status == "scheduled":
                hh, mm = _parse_time_value(ov_new_time)
                new_dt = datetime(
                    ov_new_dt.year,
                    ov_new_dt.month,
                    ov_new_dt.day,
                    hh,
                    mm,
                )

            if st.button(t("change"), key="ov_add_btn"):
                try:
                    add_override(
                        student=ov_student,
                        original_date=ov_original_date,
                        new_dt=new_dt if ov_status == "scheduled" else None,
                        duration_minutes=int(ov_duration),
                        status=ov_status,
                        note=ov_note,
                    )
                    st.success(t("saved"))
                    st.rerun()
                except Exception as e:
                    st.error(f"{t('override_save_failed')}\n\n{e}")

    # ---------------------------------------
    # PREVIOUS CHANGES TABLE (TRANSLATED)
    # ---------------------------------------
    with st.expander(t("previous_changes"), expanded=False):

        if overrides.empty:
            st.caption(t("no_data"))
        else:
            show = overrides.copy()

            for c in ["id", "student", "original_date", "new_datetime",
                      "duration_minutes", "status", "note"]:
                if c not in show.columns:
                    show[c] = None

            show["original_date"] = pd.to_datetime(
                show["original_date"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")

            show["new_datetime"] = pd.to_datetime(
                show["new_datetime"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M").fillna("—")

            show["duration_minutes"] = pd.to_numeric(
                show["duration_minutes"], errors="coerce"
            ).fillna(60).astype(int)

            def _translate_override_status(x):
                s = str(x or "").strip().lower()
                if s == "scheduled":
                    return t("override_scheduled")
                if s == "cancelled":
                    return t("override_cancel")
                return str(x)

            show["status"] = show["status"].apply(_translate_override_status)

            show = show[
                ["id", "student", "original_date",
                 "new_datetime", "duration_minutes",
                 "status", "note"]
            ].sort_values(["original_date", "student"])

            st.dataframe(
                translate_df_headers(pretty_df(show)),
                use_container_width=True,
                hide_index=True,
            )

            del_id = st.number_input(
                t("override_id"),
                min_value=1,
                step=1,
                key="ov_del_id",
            )

            confirm_del_o = st.checkbox(
                t("delete_warning_undo"),
                key="confirm_del_override",
            )

            if st.button(
                t("delete"),
                disabled=not confirm_del_o,
                key="ov_del_btn",
            ):
                delete_override(del_id)
                st.success(t("deleted"))
                st.rerun()

# =========================
# 22) PAGE: ANALYTICS (CLICKABLE KPI CAPSULES + TEACHER-FRIENDLY INSIGHTS)
# ✅ Section 12 compatible + Mon–Sun week
# ✅ Keeps your capsule-based views + same graphs
# ✅ Adds business-style (but teacher-friendly) Insights + Drivers + Operations + Forecast
# ✅ Raw tables are optional (toggle), not the default
# ✅ New micro-translator helper included (t_a)
# ✅ FIX: Summary shows AVERAGE monthly + AVERAGE yearly (not duplicates of capsules)
# ✅ UPGRADE: Estimated yearly revenue uses YTD + renewal pipeline (not this_month*12)
# ✅ NEW: Yearly goal stored in Supabase app_settings + progress bar
# ✅ FIX: Risk & Forecast buffer now changes who appears in "Students to contact"
# =========================
elif page == "analytics":
    page_header(t("analytics"))
    st.caption(t("view_your_income_and_business_indicators"))

    st.markdown(f"### {t('income')}")

    # -------------------------
    # Analytics-only translator
    # (business oriented, teacher friendly)
    # -------------------------
    ANALYTICS_I18N = {
        "en": {
            "insights_and_actions": "Insights & Actions",
            "summary": "Summary",
            "revenue_drivers": "Revenue drivers",
            "teaching_activity": "Teaching activity",
            "risk_and_forecast": "Risk & forecast",
            "show_raw_data": "Show raw data",
            "what_this_means": "What this means",
            "next_steps": "Next steps",
            "avg_monthly_income": "Average monthly income",
            "avg_yearly_income": "Average yearly income",
            "run_rate_annual": "Estimated yearly revenue",
            "effective_rate_unit": "Average income per lesson",
            "concentration_risk": "Income concentration",
            "top1_share": "Top student share",
            "top3_share": "Top 3 students share",
            "top10_revenue": "Top 10 income",
            "top5_quick_view": "Top 5 quick view",
            "segment_language": "Language segment",
            "segment_modality": "Modality segment",
            "total_revenue_language": "Total income by language",
            "total_revenue_modality": "Total income by modality",
            "top_segment_share": "Top segment share",
            "total_units": "Total lesson units",
            "top_language": "Top lesson language",
            "top_modality": "Top lesson modality",

            # Forecast (operational)
            "students_in_forecast": "Students in forecast",
            "due_now": "Due to contact now",
            "finishing_14d": "Finishing in next 14 days",
            "at_risk": "At risk",
            "students_to_contact": "Students to contact",
            "units_left": "units left",
            "finish": "finish",
            "remind": "remind",
            "next_up": "Next up",

            # Goal
            "goal": "Goal",
            "yearly_income_goal": "Yearly income goal",
            "goal_progress": "Goal progress",
            "ytd_income": "YTD income",
            "remaining_to_goal": "Remaining to goal",
            "avg_needed_month": "Avg needed / month",
            "expected_renewals": "Expected renewals",

            "takeaway_concentration": "Your top student contributes {p1} of all income; your top 3 students contribute {p3}.",
            "takeaway_language": "Your strongest language segment is {name} ({share} of language income).",
            "takeaway_modality": "Your strongest modality segment is {name} ({share} of modality income).",
            "takeaway_activity_language": "Most of your teaching units are in {name} ({share} of units).",
            "takeaway_activity_modality": "Most of your teaching units are delivered via {name} ({share} of units).",
            "takeaway_profitable": "{name} is currently your strongest income source. Keeping your best students satisfied supports stable income.",
            "takeaway_pipeline": "Use this section as a renewal list. Contact students before they reach zero units.",
            "action_check_week": "No income recorded this week — check renewals and pending payments.",
            "action_reduce_risk": "Income is concentrated — consider balancing your student base and pricing.",
            "action_review_pricing": "Average income per unit looks low — review packages, discounts, or lesson pricing.",
            "action_review_top": "Review your top students and plan renewals.",
            "action_compare_mix": "Compare language/modality mix with your pricing strategy.",
            "action_check_forecast": "Use the forecast to plan the next two weeks.",
            "important": "Important",
        },
        "es": {
            "insights_and_actions": "Información Estratégica",
            "summary": "Resumen",
            "revenue_drivers": "Impulsores de ingresos",
            "teaching_activity": "Actividad docente",
            "risk_and_forecast": "Riesgo y pronóstico",
            "show_raw_data": "Mostrar datos",
            "what_this_means": "Qué significa",
            "next_steps": "Próximos pasos",
            "avg_monthly_income": "Ingreso mensual promedio",
            "avg_yearly_income": "Ingreso anual promedio",
            "run_rate_annual": "Proyección de ingreso anual",
            "effective_rate_unit": "Ingreso promedio por clase",
            "concentration_risk": "Concentración de ingresos",
            "top1_share": "Participación del mejor estudiante",
            "top3_share": "Participación del top 3",
            "top10_revenue": "Ingreso del top 10",
            "top5_quick_view": "Vista rápida top 5",
            "segment_language": "Segmento por idioma",
            "segment_modality": "Segmento por modalidad",
            "total_revenue_language": "Ingreso total por idioma",
            "total_revenue_modality": "Ingreso total por modalidad",
            "top_segment_share": "Participación del segmento líder",
            "total_units": "Unidades de clase totales",
            "top_language": "Idioma principal",
            "top_modality": "Modalidad principal",

            # Forecast (operational)
            "students_in_forecast": "Estudiantes en pronóstico",
            "due_now": "Para contactar hoy",
            "finishing_14d": "Terminan en los próximos 14 días",
            "at_risk": "En riesgo",
            "students_to_contact": "Estudiantes a contactar",
            "units_left": "unidades restantes",
            "finish": "fin",
            "remind": "recordar",
            "next_up": "Próximos",

            # Goal
            "goal": "Meta",
            "yearly_income_goal": "Meta anual de ingresos",
            "goal_progress": "Progreso de la meta",
            "ytd_income": "Ingresos del año",
            "remaining_to_goal": "Falta para la meta",
            "avg_needed_month": "Promedio necesario / mes",
            "expected_renewals": "Renovaciones esperadas",

            "takeaway_concentration": "Tu mejor estudiante aporta {p1} del ingreso total; tu top 3 aporta {p3}.",
            "takeaway_language": "Tu segmento de idioma más fuerte es {name} ({share} del ingreso por idioma).",
            "takeaway_modality": "Tu segmento de modalidad más fuerte es {name} ({share} del ingreso por modalidad).",
            "takeaway_activity_language": "La mayoría de tus unidades de clase están en {name} ({share} de unidades).",
            "takeaway_activity_modality": "La mayoría de tus unidades se imparten por {name} ({share} de unidades).",
            "takeaway_profitable": "{name} es tu principal fuente de ingresos. Mantener satisfechos a tus mejores estudiantes ayuda a tener ingresos estables.",
            "takeaway_pipeline": "Usa esta sección como lista de renovaciones. Contacta a los estudiantes antes de llegar a cero unidades.",
            "action_check_week": "No hay ingresos registrados esta semana — revisa renovaciones y pagos pendientes.",
            "action_reduce_risk": "El ingreso está concentrado — considera equilibrar tu base de estudiantes y precios.",
            "action_review_pricing": "El ingreso promedio por unidad parece bajo — revisa paquetes, descuentos o precios.",
            "action_review_top": "Revisa tus estudiantes más rentables y planifica renovaciones.",
            "action_compare_mix": "Compara el mix de idioma/modalidad con tu estrategia de precios.",
            "action_check_forecast": "Usa el pronóstico para planificar las próximas dos semanas.",
            "important": "Importante",
        },
    }

    def t_a(key: str, **kwargs) -> str:
        lang = st.session_state.get("ui_lang", "en")
        s = ANALYTICS_I18N.get(lang, ANALYTICS_I18N["en"]).get(key, key)
        try:
            return s.format(**kwargs)
        except Exception:
            return s

    # --- Read analytics view from query param (av) ---
    def _get_qp_local(key: str, default=None):
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

    allowed_views = {"all_time", "year", "month", "week"}

    if "analytics_view" not in st.session_state:
        st.session_state.analytics_view = "all_time"

    av = _get_qp_local("av", None)
    if av in allowed_views:
        st.session_state.analytics_view = av

    current_lang = st.session_state.get("ui_lang", "en")
    current_view = st.session_state.get("analytics_view", "all_time")

    # ---------------------------------------
    # Load analytics data (Section 12 format)
    # ---------------------------------------
    kpis, income_table, by_student, sold_by_language, sold_by_modality = build_income_analytics(group="monthly")
    today = ts_today_naive()

    # ---------------------------------------
    # Capsule "theme" colors (match views)
    # ---------------------------------------
    BLUE = "#2563EB"    # all_time capsule
    GREEN = "#10B981"   # yearly capsule
    YELLOW = "#F59E0B"  # monthly capsule
    PURPLE = "#8B5CF6"  # weekly capsule

    # =======================================
    # CLICKABLE KPI CAPSULES (HTML LINKS)
    # =======================================
    capsules = [
        ("all_time", t("all_time_income"), money_fmt(kpis.get("income_all_time", 0.0))),
        ("year",     t("yearly_income"),   money_fmt(kpis.get("income_this_year", 0.0))),
        ("month",    t("monthly_income"),  money_fmt(kpis.get("income_this_month", 0.0))),
        ("week",     t("weekly_income"),   money_fmt(kpis.get("income_this_week", 0.0))),
    ]

    caps_html = """
    <style>
    .cm-caps-wrap{
      display:flex;
      flex-wrap:wrap;
      gap:12px;
      align-items:stretch;
      margin-top:10px;
      margin-bottom:6px;
      padding-bottom: 4px;
    }
    .cm-capsule{
      flex:1 1 160px;
      min-width:160px;
      max-width:280px;
      background:#ffffff;
      border:1px solid rgba(17,24,39,0.10);
      border-radius:999px;
      padding:18px 14px;
      text-align:center;
      text-decoration:none !important;
      color:#0f172a !important;
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      box-shadow:0 14px 26px rgba(15,23,42,0.10);
      transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
      position:relative;
      overflow:hidden;
      display:flex;
      flex-direction:column;
      justify-content:center;
    }
    .cm-capsule:hover{
      transform:translateY(-1px);
      box-shadow:0 18px 32px rgba(15,23,42,0.14);
      border-color:rgba(59,130,246,0.35);
    }
    .cm-capsule.active{
      border:2px solid #2563EB;
      box-shadow:0 0 0 3px rgba(37,99,235,0.10), 0 14px 26px rgba(15,23,42,0.10);
    }
    .cm-capsule-value{
      font-weight:900;
      font-size:30px;
      line-height:1.05;
      margin-bottom:6px;
      word-break:break-word;
    }
    .cm-capsule-label{
      font-weight:800;
      font-size:13px;
      opacity:.9;
      word-break:break-word;
    }
    .cm-capsule:nth-child(1)::before{
      content:""; position:absolute; width:110px; height:110px; top:18%; left:22%;
      background:radial-gradient(circle, rgba(59,130,246,.22), transparent 70%);
      filter:blur(12px); opacity:.9;
    }
    .cm-capsule:nth-child(2)::before{
      content:""; position:absolute; width:110px; height:110px; top:18%; left:22%;
      background:radial-gradient(circle, rgba(16,185,129,.20), transparent 70%);
      filter:blur(12px); opacity:.9;
    }
    .cm-capsule:nth-child(3)::before{
      content:""; position:absolute; width:110px; height:110px; top:18%; left:22%;
      background:radial-gradient(circle, rgba(245,158,11,.18), transparent 70%);
      filter:blur(12px); opacity:.9;
    }
    .cm-capsule:nth-child(4)::before{
      content:""; position:absolute; width:110px; height:110px; top:18%; left:22%;
      background:radial-gradient(circle, rgba(139,92,246,.20), transparent 70%);
      filter:blur(12px); opacity:.9;
    }
    @media (max-width: 700px){
      .cm-capsule{
        flex:1 1 calc(50% - 12px);
        min-width:140px;
        max-width:none;
        padding:14px 12px;
      }
      .cm-capsule-value{ font-size:24px; }
      .cm-capsule-label{ font-size:12px; }
    }
    </style>
    <div class="cm-caps-wrap">
    """

    for k, label, val in capsules:
        active_cls = "active" if k == current_view else ""
        caps_html += (
            f'<a class="cm-capsule {active_cls}" '
            f'href="?page=analytics&av={k}&lang={current_lang}" target="_self" rel="noopener noreferrer">'
            f'<div class="cm-capsule-value">{val}</div>'
            f'<div class="cm-capsule-label">{label}</div>'
            f'</a>'
        )

    caps_html += "</div>"
    st.markdown(caps_html, unsafe_allow_html=True)

    view = current_view

    # ---------------------------------------
    # Chart helpers (UNCHANGED)
    # ---------------------------------------
    def _monthly_line_chart_plotly(df: pd.DataFrame, title: str):
        import plotly.express as px

        if df is None or df.empty or "Key" not in df.columns:
            st.info(t("no_data"))
            return

        tmp = df.copy()
        ycol = "income" if "income" in tmp.columns else ("Income" if "Income" in tmp.columns else None)
        if ycol is None:
            st.info(t("no_data"))
            return

        tmp["date"] = pd.to_datetime(tmp["Key"].astype(str).str[:7] + "-01", errors="coerce")
        tmp = tmp.dropna(subset=["date"])
        if tmp.empty:
            st.info(t("no_data"))
            return

        tmp["income_val"] = pd.to_numeric(tmp[ycol], errors="coerce").fillna(0.0).astype(float)
        tmp = tmp.sort_values("date")

        fig = px.line(
            tmp,
            x="date",
            y="income_val",
            title=title,
            markers=True,
            labels={"date": t("month"), "income_val": t("income")},
        )

        fig.update_layout(
            margin=dict(l=10, r=10, t=48, b=10),
            height=360 if st.session_state.get("compact_mode", False) else 440,
            xaxis=dict(
                rangeslider=dict(visible=True),
                type="date",
                tickformat="%b %Y",
            ),
        )

        st.plotly_chart(fig, use_container_width=True)

    def _bar_chart_with_highlight(labels, values, highlight_label, base_color, highlight_color, title, xlabel, ylabel):
        import matplotlib.pyplot as plt

        colors = [highlight_color if l == highlight_label else base_color for l in labels]
        fig, ax = plt.subplots()
        ax.bar(labels, values, color=colors)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        if len(labels) > 12:
            step = max(1, len(labels) // 8)
            keep = set(range(0, len(labels), step))
            ax.set_xticks([i for i in range(len(labels)) if i in keep])
            ax.set_xticklabels([labels[i] for i in range(len(labels)) if i in keep], rotation=45, ha="right")
        else:
            ax.tick_params(axis="x", labelrotation=45)

        ax.margins(x=0.01)
        st.pyplot(fig, clear_figure=True)

    # ============================================
    # MAIN VIEW CONTENT (UNCHANGED)
    # ============================================
    if view == "all_time":
        st.subheader(t("all_time_monthly_income"))
        _monthly_line_chart_plotly(income_table, t("all_time_monthly_income"))

    elif view == "year":
        st.subheader(t("yearly_income"))
        _, yearly_table, *_ = build_income_analytics(group="yearly")
        if yearly_table is None or yearly_table.empty:
            st.info(t("no_data"))
        else:
            yt = yearly_table.copy()
            yt["Year"] = yt["Key"].astype(str).str[:4]

            if "income" in yt.columns:
                yt["Income"] = pd.to_numeric(yt["income"], errors="coerce").fillna(0.0).astype(float)
            else:
                yt["Income"] = pd.to_numeric(yt.get("Income"), errors="coerce").fillna(0.0).astype(float)

            yt = yt.sort_values("Year")

            current_year = str(today.year)
            years = yt["Year"].tolist()
            incomes = yt["Income"].tolist()

            _bar_chart_with_highlight(
                labels=years,
                values=incomes,
                highlight_label=current_year,
                base_color=BLUE,
                highlight_color=GREEN,
                title=t("yearly_totals"),
                xlabel=t("year"),
                ylabel=t("income"),
            )

    elif view == "month":
        st.subheader(t("monthly_income"))
        if income_table is None or income_table.empty:
            st.info(t("no_data"))
        else:
            year_options = sorted(income_table["Key"].astype(str).str[:4].dropna().unique().tolist(), reverse=True)
            current_year = str(today.year)
            default_idx = year_options.index(current_year) if current_year in year_options else 0

            selected_year = st.selectbox(t("select_year"), year_options, index=default_idx, key="analytics_year_pick")
            monthly = income_table[income_table["Key"].astype(str).str.startswith(selected_year)].copy()

            if monthly.empty:
                st.info(t("no_data"))
            else:
                monthly["MonthKey"] = monthly["Key"].astype(str).str[:7]

                if "income" in monthly.columns:
                    monthly["Income"] = pd.to_numeric(monthly["income"], errors="coerce").fillna(0.0).astype(float)
                else:
                    monthly["Income"] = pd.to_numeric(monthly.get("Income"), errors="coerce").fillna(0.0).astype(float)

                monthly = monthly.sort_values("MonthKey")

                labels = monthly["MonthKey"].tolist()
                values = monthly["Income"].tolist()

                highlight_month = today.strftime("%Y-%m") if selected_year == str(today.year) else "__none__"
                _bar_chart_with_highlight(
                    labels=labels,
                    values=values,
                    highlight_label=highlight_month,
                    base_color=BLUE,
                    highlight_color=YELLOW,
                    title=f"{t('monthly_income')} ({selected_year})",
                    xlabel=t("month"),
                    ylabel=t("income"),
                )

    elif view == "week":
        st.subheader(t("weekly_income"))

        week_start = today - pd.Timedelta(days=int(today.weekday()))
        week_end = week_start + pd.Timedelta(days=6)

        payments = load_table("payments")
        if payments is None or payments.empty:
            st.info(t("no_data"))
        else:
            if "payment_date" not in payments.columns:
                payments["payment_date"] = None
            if "paid_amount" not in payments.columns:
                payments["paid_amount"] = 0.0

            payments["payment_date"] = to_dt_naive(payments["payment_date"], utc=True)
            payments["paid_amount"] = pd.to_numeric(payments["paid_amount"], errors="coerce").fillna(0.0)
            payments = payments.dropna(subset=["payment_date"])

            week_df = payments[(payments["payment_date"] >= week_start) & (payments["payment_date"] <= week_end)].copy()
            if week_df.empty:
                daily = pd.DataFrame({
                    "Day": [(week_start + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)],
                    "Income": [0.0] * 7
                })
            else:
                week_df["Day"] = week_df["payment_date"].dt.strftime("%Y-%m-%d")
                daily = (
                    week_df.groupby("Day", as_index=False)["paid_amount"]
                    .sum()
                    .rename(columns={"paid_amount": "Income"})
                    .sort_values("Day")
                )
                days = [(week_start + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
                daily = pd.DataFrame({"Day": days}).merge(daily, on="Day", how="left").fillna({"Income": 0.0})

            labels = daily["Day"].tolist()
            values = daily["Income"].astype(float).tolist()

            highlight_day = today.strftime("%Y-%m-%d")
            _bar_chart_with_highlight(
                labels=labels,
                values=values,
                highlight_label=highlight_day,
                base_color=BLUE,
                highlight_color=PURPLE,
                title=t("last_7_days"),
                xlabel=t("day"),
                ylabel=t("income"),
            )

    # ============================================
    # INSIGHTS-FIRST SECTION (business oriented, teacher friendly)
    # ============================================
    # ---------- safe helpers ----------
    def _first_existing_col(df: pd.DataFrame, candidates):
        if df is None or df.empty:
            return None
        norm = {str(c).strip().casefold(): c for c in df.columns}
        for cand in candidates:
            k = str(cand).strip().casefold()
            if k in norm:
                return norm[k]
        return None

    def _safe_sum(df: pd.DataFrame, col: str) -> float:
        if df is None or df.empty or col is None or col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum())

    def _pct(a: float, b: float) -> float:
        b = float(b or 0.0)
        if b == 0:
            return 0.0
        return float(a) / b * 100.0

    def _fmt_pct(x: float) -> str:
        try:
            return f"{float(x):.1f}%"
        except Exception:
            return "0.0%"

    def _callout(title: str, body: str):
        st.markdown(
            f"""
            <div style="padding:10px 12px;border:1px solid rgba(15,23,42,.10);
                        background:rgba(37,99,235,.04);border-radius:12px;">
              <div style="font-weight:900;color:#0f172a;margin-bottom:4px;">{title}</div>
              <div style="font-weight:600;color:#0f172a;opacity:.95;">{body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _show_raw_toggle(df: pd.DataFrame, toggle_key: str):
        show_raw = st.toggle(t_a("show_raw_data"), value=False, key=toggle_key)
        if show_raw:
            st.dataframe(
                translate_df_headers(pretty_df(df)),
                use_container_width=True,
                hide_index=True,
            )

    # ---------- NEW: YTD + renewal pipeline projection (no more this_month*12) ----------
    def _ytd_income(payments_df: pd.DataFrame, year: int) -> float:
        if payments_df is None or payments_df.empty:
            return 0.0
        p = payments_df.copy()
        if "payment_date" not in p.columns:
            return 0.0
        if "paid_amount" not in p.columns:
            return 0.0
        p["payment_date"] = to_dt_naive(p["payment_date"], utc=True)
        p["paid_amount"] = pd.to_numeric(p["paid_amount"], errors="coerce").fillna(0.0).astype(float)
        p = p.dropna(subset=["payment_date"])
        p = p[p["payment_date"].dt.year == int(year)]
        return float(p["paid_amount"].sum())

    def _student_baseline_payment(payments_df: pd.DataFrame, student: str) -> float:
        """
        Student baseline renewal value = median of last up to 3 payments (safer than mean).
        """
        if payments_df is None or payments_df.empty:
            return 0.0
        if "student" not in payments_df.columns or "paid_amount" not in payments_df.columns:
            return 0.0

        p = payments_df.copy()
        p["student"] = p["student"].fillna("").astype(str).str.strip()
        p = p[p["student"] == str(student).strip()]
        if p.empty:
            return 0.0

        if "payment_date" in p.columns:
            p["payment_date"] = to_dt_naive(p["payment_date"], utc=True)
            p = p.dropna(subset=["payment_date"]).sort_values("payment_date")
        p["paid_amount"] = pd.to_numeric(p["paid_amount"], errors="coerce").fillna(0.0).astype(float)

        tail = p["paid_amount"].tail(3)
        if len(tail) == 0:
            return 0.0
        return float(tail.median())

    def _estimate_typical_units_from_dashboard(student_name: str) -> float:
        """
        If dashboard has a total-paid-units column, we use it as package-size proxy.
        Otherwise returns 0 (caller will fallback).
        """
        try:
            dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=0)
            if dash is None or dash.empty:
                return 0.0
            if "Student" not in dash.columns:
                return 0.0
            d = dash.copy()
            d["Student"] = d["Student"].fillna("").astype(str).str.strip()
            row = d[d["Student"] == str(student_name).strip()]
            if row.empty:
                return 0.0

            # Common candidates across your app versions:
            cand = _first_existing_col(row, ["Lessons_Paid_Total", "Lessons_Paid", "Paid_Units", "Package_Units"])
            if not cand:
                return 0.0
            v = row.iloc[0].get(cand, 0)
            v = float(pd.to_numeric(v, errors="coerce") or 0.0)
            return max(0.0, v)
        except Exception:
            return 0.0

    def estimate_year_projection_current_students(
        today_ts: pd.Timestamp,
        forecast_df: pd.DataFrame,
        payments_df: pd.DataFrame,
    ) -> dict:
        """
        Base projection (student-based):
          projected = YTD cash + expected renewals (prob=1.0 baseline, refined later)

        Renewals are simulated using:
          - student's baseline payment value (median last 3 payments)
          - next renewal = finish date
          - renewal cycle length = max(typical_units, 10) / units_per_day
        """
        year = int(today_ts.year)
        year_end = pd.Timestamp(year=year, month=12, day=31)

        ytd = _ytd_income(payments_df, year=year)
        if forecast_df is None or forecast_df.empty:
            return {"ytd": ytd, "expected_future": 0.0, "projected": ytd, "counted": 0, "missing_baseline": 0}

        # identify cols (from Section 12 output)
        student_col = _first_existing_col(forecast_df, ["Student", "student"])
        upd_col = _first_existing_col(forecast_df, ["Units_Per_Day", "units_per_day"])
        left_col = _first_existing_col(forecast_df, ["Lessons_Left_Units", "lessons_left_units"])
        finish_col = _first_existing_col(forecast_df, ["Estimated_Finish_Date", "estimated_finish_date"])

        if not student_col or not upd_col:
            return {"ytd": ytd, "expected_future": 0.0, "projected": ytd, "counted": 0, "missing_baseline": 0}

        f = forecast_df.copy()
        f[student_col] = f[student_col].fillna("").astype(str).str.strip()
        f[upd_col] = pd.to_numeric(f[upd_col], errors="coerce").fillna(0.0).astype(float)
        f.loc[f[upd_col] <= 0, upd_col] = 0.10

        if left_col and left_col in f.columns:
            f[left_col] = pd.to_numeric(f[left_col], errors="coerce").fillna(0.0).astype(float)
        else:
            f[left_col] = 0.0

        f["_finish_dt"] = pd.to_datetime(f.get(finish_col), errors="coerce") if finish_col else pd.NaT

        expected_future = 0.0
        counted = 0
        missing = 0

        for _, r in f.iterrows():
            s = str(r.get(student_col, "")).strip()
            if not s:
                continue

            baseline_value = _student_baseline_payment(payments_df, s)
            if baseline_value <= 0:
                missing += 1
                continue

            units_per_day = float(r.get(upd_col, 0.10) or 0.10)
            finish_dt = r.get("_finish_dt", pd.NaT)
            if pd.isna(finish_dt):
                continue

            # typical units: prefer dashboard (if available), else fallback to current remaining, clamped
            typical_units = _estimate_typical_units_from_dashboard(s)
            if typical_units <= 0:
                typical_units = float(r.get(left_col, 0.0) or 0.0)
            typical_units = max(10.0, typical_units)

            cycle_days = max(7, int(round(typical_units / max(0.01, units_per_day))))
            next_dt = pd.Timestamp(finish_dt)

            # simulate renewals until year end
            while next_dt <= year_end:
                expected_future += baseline_value
                next_dt = next_dt + pd.Timedelta(days=cycle_days)

            counted += 1

        projected = ytd + expected_future
        return {"ytd": float(ytd), "expected_future": float(expected_future), "projected": float(projected), "counted": int(counted), "missing_baseline": int(missing)}

    # ---------- metrics (capsules already show totals; summary will show averages) ----------
    total_all_time = float(kpis.get("income_all_time", 0.0) or 0.0)
    total_month = float(kpis.get("income_this_month", 0.0) or 0.0)
    total_week = float(kpis.get("income_this_week", 0.0) or 0.0)

    # Effective rate (income per lesson unit) — uses all-time totals
    classes_for_rate = load_table("classes")
    total_units = 0.0
    if classes_for_rate is not None and not classes_for_rate.empty and "number_of_lesson" in classes_for_rate.columns:
        total_units = float(pd.to_numeric(classes_for_rate["number_of_lesson"], errors="coerce").fillna(0).sum())
    eff_rate = (total_all_time / total_units) if (total_units and total_all_time) else 0.0

    # --- Average monthly income (last 12 months) ---
    avg_monthly_12m = 0.0
    try:
        if income_table is not None and not income_table.empty and "Key" in income_table.columns:
            tmpm = income_table.copy()
            ycol_m = "income" if "income" in tmpm.columns else ("Income" if "Income" in tmpm.columns else None)
            if ycol_m:
                tmpm["date"] = pd.to_datetime(tmpm["Key"].astype(str).str[:7] + "-01", errors="coerce")
                tmpm = tmpm.dropna(subset=["date"])
                tmpm["val"] = pd.to_numeric(tmpm[ycol_m], errors="coerce").fillna(0.0).astype(float)
                tmpm = tmpm.sort_values("date")
                cutoff = today - pd.Timedelta(days=365)
                last12 = tmpm[tmpm["date"] >= cutoff]
                if len(last12) >= 3:
                    avg_monthly_12m = float(last12["val"].mean())
                elif len(tmpm) >= 1:
                    avg_monthly_12m = float(tmpm["val"].mean())
    except Exception:
        avg_monthly_12m = 0.0

    # --- Average yearly income (average across available years) ---
    avg_yearly = 0.0
    try:
        _, yearly_table_avg, *_ = build_income_analytics(group="yearly")
        if yearly_table_avg is not None and not yearly_table_avg.empty and "Key" in yearly_table_avg.columns:
            ytmp = yearly_table_avg.copy()
            ycol_y = "income" if "income" in ytmp.columns else ("Income" if "Income" in ytmp.columns else None)
            if ycol_y:
                ytmp["val"] = pd.to_numeric(ytmp[ycol_y], errors="coerce").fillna(0.0).astype(float)
                if len(ytmp) >= 1:
                    avg_yearly = float(ytmp["val"].mean())
    except Exception:
        avg_yearly = 0.0

    # Income concentration (top student / top 3)
    top_income_col = _first_existing_col(by_student, ["total_paid", "Total_Paid", "income", "paid_amount", "Income"])
    student_col = _first_existing_col(by_student, ["student", "Student"])
    lastpay_col = _first_existing_col(by_student, ["last_payment", "Last_Payment"])

    by_student_total = _safe_sum(by_student, top_income_col)
    top1_share = 0.0
    top3_share = 0.0
    top1_name = None

    if by_student is not None and not by_student.empty and top_income_col and student_col:
        bs = by_student.copy()
        bs[top_income_col] = pd.to_numeric(bs[top_income_col], errors="coerce").fillna(0.0).astype(float)
        bs = bs.sort_values(top_income_col, ascending=False).reset_index(drop=True)

        if len(bs) >= 1:
            top1_name = str(bs.loc[0, student_col])
            top1_share = _pct(float(bs.loc[0, top_income_col]), float(by_student_total))
        if len(bs) >= 3:
            top3_share = _pct(float(bs.loc[:2, top_income_col].sum()), float(by_student_total))
        elif len(bs) >= 1:
            top3_share = _pct(float(bs.loc[:, top_income_col].sum()), float(by_student_total))

    # ---------- NEW: compute projection inputs once (used in Summary + Goal) ----------
    payments_all = load_table("payments")
    forecast_for_projection = build_forecast_table(payment_buffer_days=0)

    proj = estimate_year_projection_current_students(
        today_ts=today,
        forecast_df=forecast_for_projection,
        payments_df=payments_all,
    )
    projected_year = float(proj.get("projected", 0.0) or 0.0)
    ytd_cash = float(proj.get("ytd", 0.0) or 0.0)
    expected_future = float(proj.get("expected_future", 0.0) or 0.0)

    st.markdown(f"### {t_a('insights_and_actions')}")
    tab_summary, tab_rev, tab_delivery, tab_risk = st.tabs(
        [t_a("summary"), t_a("revenue_drivers"), t_a("teaching_activity"), t_a("risk_and_forecast")]
    )

    # ======================
    # TAB 1 — Summary
    # ======================
    with tab_summary:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(t_a("avg_yearly_income"), money_fmt(avg_yearly))
        with c2:
            st.metric(t_a("avg_monthly_income"), money_fmt(avg_monthly_12m))
        with c3:
            st.metric(t_a("run_rate_annual"), money_fmt(projected_year))
        with c4:
            st.metric(t_a("effective_rate_unit"), money_fmt(eff_rate))

        st.caption(
            f"{t_a('ytd_income')}: {money_fmt(ytd_cash)} — "
            f"{t_a('expected_renewals')}: {money_fmt(expected_future)}"
        ) 
        # -------------------------
        # NEW: Yearly goal (persistent across devices)
        # -------------------------
        st.markdown(f"#### {t_a('goal')}")
        scope = "global"
        current_year = int(today.year)

        if "year_goal_loaded" not in st.session_state:
            st.session_state.year_goal_loaded = {}
        if current_year not in st.session_state.year_goal_loaded:
            st.session_state[f"year_goal_{current_year}"] = get_year_goal(current_year, scope=scope, default=0.0)
            st.session_state.year_goal_loaded[current_year] = True

        gcol1, gcol2 = st.columns([2, 1])
        with gcol1:
            new_goal = st.number_input(
                f"{t_a('yearly_income_goal')} ({current_year})",
                min_value=0.0,
                value=float(st.session_state.get(f"year_goal_{current_year}", 0.0) or 0.0),
                step=1000.0,
                key=f"year_goal_input_{current_year}",
            )
        with gcol2:
            if st.button("Save", key=f"save_goal_{current_year}", use_container_width=True):
                ok = set_year_goal(current_year, float(new_goal), scope=scope)
                if ok:
                    st.session_state[f"year_goal_{current_year}"] = float(new_goal)
                    try:
                        st.cache_data.clear()
                    except Exception:
                        pass

                    st.toast("Saved", icon="✅")
                    st.rerun()   # ← forces refresh so Home reads updated value
                else:
                    st.toast("Could not save goal", icon="⚠️")

        goal_val = float(st.session_state.get(f"year_goal_{current_year}", 0.0) or 0.0)
        if goal_val > 0:
            prog = max(0.0, min(1.0, ytd_cash / goal_val))
            st.progress(prog)
            st.write(f"**{prog*100.0:.1f}%** — {t_a('goal_progress')}")

            remaining = max(0.0, goal_val - ytd_cash)
            months_left = max(0, 12 - int(today.month))
            avg_needed = (remaining / months_left) if months_left > 0 else remaining

            g1, g2, g3 = st.columns(3)
            with g1:
                st.metric(t_a("ytd_income"), money_fmt(ytd_cash))
            with g2:
                st.metric(t_a("remaining_to_goal"), money_fmt(remaining))
            with g3:
                st.metric(t_a("avg_needed_month"), money_fmt(avg_needed))
        else:
            st.info("Set a yearly goal to see your progress bar.")

        # -------------------------
        # Summary callout + actions (unchanged)
        # -------------------------
        if top1_name:
            _callout(
                t_a("important"),
                t_a("takeaway_concentration", p1=_fmt_pct(top1_share), p3=_fmt_pct(top3_share)),
            )
        else:
            _callout(
                t_a("what_this_means"),
                "This section explains your teaching business in simple numbers: income, stability, and what to do next.",
            )

        st.markdown(f"#### {t_a('next_steps')}")
        actions = []
        if total_week == 0 and total_month > 0:
            actions.append(t_a("action_check_week"))
        if top3_share >= 60:
            actions.append(t_a("action_reduce_risk"))
        if not actions:
            actions = [t_a("action_review_top"), t_a("action_compare_mix"), t_a("action_check_forecast")]

        for a in actions[:5]:
            st.write(f"• {a}")

    # ======================
    # TAB 2 — Revenue drivers
    # ======================
    with tab_rev:
        # (UNCHANGED from your current code)
        st.markdown(f"#### {t('most_profitable_students')}")
        if by_student is None or by_student.empty or not top_income_col or not student_col:
            st.info(t("no_data"))
        else:
            bs = by_student.copy()
            bs[top_income_col] = pd.to_numeric(bs[top_income_col], errors="coerce").fillna(0.0).astype(float)
            bs = bs.sort_values(top_income_col, ascending=False).reset_index(drop=True)
            top = bs.head(10).copy()

            top_total = float(top[top_income_col].sum())
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t_a("top10_revenue"), money_fmt(top_total))
            with c2:
                st.metric(t_a("top1_share"), _fmt_pct(top1_share))
            with c3:
                st.metric(t_a("top3_share"), _fmt_pct(top3_share))

            if top1_name:
                _callout(t_a("important"), t_a("takeaway_profitable", name=top1_name))

            ser = chart_series(top.rename(columns={student_col: "student"}), "student", top_income_col, "student", "income")
            if ser is None:
                st.info(t("no_data"))
            else:
                st.bar_chart(ser)

            st.markdown(f"##### {t_a('top5_quick_view')}")
            top5 = top.head(5).copy()
            cols = st.columns(5)
            for i in range(min(5, len(top5))):
                name = str(top5.loc[i, student_col])
                val = float(top5.loc[i, top_income_col])
                share = _fmt_pct(_pct(val, by_student_total))
                with cols[i]:
                    st.metric(name, money_fmt(val), share)

            top_show = top.copy()
            top_show[top_income_col] = top_show[top_income_col].apply(money_fmt)
            if lastpay_col and lastpay_col in top_show.columns:
                top_show[lastpay_col] = pd.to_datetime(top_show[lastpay_col], errors="coerce").dt.strftime("%Y-%m-%d")
            _show_raw_toggle(top_show, "raw_top_students")

        st.markdown(f"#### {t('packages_by_language')}")
        if sold_by_language is None or sold_by_language.empty:
            st.info(t("no_data"))
        else:
            lang_df = sold_by_language.copy()
            lang_col = _first_existing_col(lang_df, ["languages", "Language"])
            inc_col = _first_existing_col(lang_df, ["income", "Income", "paid_amount", "total_paid"])
            if not lang_col or not inc_col:
                st.info(t("no_data"))
            else:
                lang_df[lang_col] = lang_df[lang_col].astype(str).apply(translate_language_value)
                lang_df[inc_col] = pd.to_numeric(lang_df[inc_col], errors="coerce").fillna(0.0).astype(float)
                lang_df = lang_df.sort_values(inc_col, ascending=False).reset_index(drop=True)

                total_lang = float(lang_df[inc_col].sum())
                top_lang = str(lang_df.loc[0, lang_col]) if len(lang_df) else ""
                top_lang_share = _fmt_pct(_pct(float(lang_df.loc[0, inc_col]) if len(lang_df) else 0.0, total_lang))

                c1, c2 = st.columns(2)
                with c1:
                    st.metric(t_a("total_revenue_language"), money_fmt(total_lang))
                with c2:
                    st.metric(t_a("top_segment_share"), top_lang_share)

                if top_lang:
                    _callout(t_a("important"), t_a("takeaway_language", name=top_lang, share=top_lang_share))

                ser = chart_series(lang_df.rename(columns={lang_col: "languages"}), "languages", inc_col, "languages", "income")
                if ser is None:
                    st.info(t("no_data"))
                else:
                    st.bar_chart(ser)

                lang_show = lang_df.copy()
                lang_show[inc_col] = lang_show[inc_col].apply(money_fmt)
                _show_raw_toggle(lang_show, "raw_lang")

        st.markdown(f"#### {t('packages_by_modality')}")
        if sold_by_modality is None or sold_by_modality.empty:
            st.info(t("no_data"))
        else:
            mod_df = sold_by_modality.copy()
            mod_col = _first_existing_col(mod_df, ["modality", "Modality"])
            inc_col = _first_existing_col(mod_df, ["income", "Income", "paid_amount", "total_paid"])
            if not mod_col or not inc_col:
                st.info(t("no_data"))
            else:
                mod_df[mod_col] = mod_df[mod_col].astype(str).apply(translate_modality_value)
                mod_df[inc_col] = pd.to_numeric(mod_df[inc_col], errors="coerce").fillna(0.0).astype(float)
                mod_df = mod_df.sort_values(inc_col, ascending=False).reset_index(drop=True)

                total_mod = float(mod_df[inc_col].sum())
                top_mod = str(mod_df.loc[0, mod_col]) if len(mod_df) else ""
                top_mod_share = _fmt_pct(_pct(float(mod_df.loc[0, inc_col]) if len(mod_df) else 0.0, total_mod))

                c1, c2 = st.columns(2)
                with c1:
                    st.metric(t_a("total_revenue_modality"), money_fmt(total_mod))
                with c2:
                    st.metric(t_a("top_segment_share"), top_mod_share)

                if top_mod:
                    _callout(t_a("important"), t_a("takeaway_modality", name=top_mod, share=top_mod_share))

                ser = chart_series(mod_df.rename(columns={mod_col: "modality"}), "modality", inc_col, "modality", "income")
                if ser is None:
                    st.info(t("no_data"))
                else:
                    st.bar_chart(ser)

                mod_show = mod_df.copy()
                mod_show[inc_col] = mod_show[inc_col].apply(money_fmt)
                _show_raw_toggle(mod_show, "raw_mod")

    # ======================
    # TAB 3 — Teaching activity
    # ======================
    with tab_delivery:
        # (UNCHANGED from your current code)
        st.markdown(f"#### {t('lessons_by_language')}")
        classes = load_table("classes")
        if classes is None or classes.empty:
            st.info(t("no_data"))
        else:
            for c in ["student", "lesson_language", "modality", "number_of_lesson", "lesson_date", "note"]:
                if c not in classes.columns:
                    classes[c] = None

            classes["student"] = classes["student"].fillna("").astype(str).str.strip()
            classes["lesson_language"] = classes["lesson_language"].fillna("").astype(str).str.strip()
            classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
            classes = classes[classes["student"].astype(str).str.len() > 0].copy()

            teach_lang = (
                classes.assign(lesson_language=classes["lesson_language"].replace({"": t("unknown")}))
                .groupby("lesson_language", as_index=False)["number_of_lesson"].sum()
                .rename(columns={"number_of_lesson": "units"})
                .sort_values("units", ascending=False)
                .reset_index(drop=True)
            )

            teach_lang["lesson_language"] = teach_lang["lesson_language"].astype(str).apply(translate_language_value)

            total_u = float(pd.to_numeric(teach_lang["units"], errors="coerce").fillna(0.0).sum())
            top_lang = str(teach_lang.loc[0, "lesson_language"]) if len(teach_lang) else ""
            top_lang_units = float(teach_lang.loc[0, "units"]) if len(teach_lang) else 0.0
            top_lang_share = _fmt_pct(_pct(top_lang_units, total_u))

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t_a("total_units"), f"{int(total_u)}")
            with c2:
                st.metric(t_a("top_language"), top_lang if top_lang else "-")
            with c3:
                st.metric(t_a("top_segment_share"), top_lang_share)

            if top_lang:
                _callout(t_a("important"), t_a("takeaway_activity_language", name=top_lang, share=top_lang_share))

            ser = chart_series(teach_lang, "lesson_language", "units", "lesson_language", "units")
            if ser is None:
                st.info(t("no_data"))
            else:
                st.bar_chart(ser)

            _show_raw_toggle(teach_lang, "raw_lessons_lang")

        st.markdown(f"#### {t('lessons_by_modality')}")
        classes = load_table("classes")
        if classes is None or classes.empty:
            st.info(t("no_data"))
        else:
            for c in ["student", "lesson_language", "modality", "number_of_lesson", "lesson_date", "note"]:
                if c not in classes.columns:
                    classes[c] = None

            classes["student"] = classes["student"].fillna("").astype(str).str.strip()
            classes["modality"] = classes["modality"].fillna("Online").astype(str).str.strip()
            classes["number_of_lesson"] = pd.to_numeric(classes["number_of_lesson"], errors="coerce").fillna(0).astype(int)
            classes = classes[classes["student"].astype(str).str.len() > 0].copy()

            teach_mod = (
                classes.groupby("modality", as_index=False)["number_of_lesson"].sum()
                .rename(columns={"number_of_lesson": "units"})
                .sort_values("units", ascending=False)
                .reset_index(drop=True)
            )

            teach_mod["modality"] = teach_mod["modality"].astype(str).apply(translate_modality_value)

            total_u = float(pd.to_numeric(teach_mod["units"], errors="coerce").fillna(0.0).sum())
            top_mod = str(teach_mod.loc[0, "modality"]) if len(teach_mod) else ""
            top_mod_units = float(teach_mod.loc[0, "units"]) if len(teach_mod) else 0.0
            top_mod_share = _fmt_pct(_pct(top_mod_units, total_u))

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t_a("total_units"), f"{int(total_u)}")
            with c2:
                st.metric(t_a("top_modality"), top_mod if top_mod else "-")
            with c3:
                st.metric(t_a("top_segment_share"), top_mod_share)

            if top_mod:
                _callout(t_a("important"), t_a("takeaway_activity_modality", name=top_mod, share=top_mod_share))

            ser = chart_series(teach_mod, "modality", "units", "modality", "units")
            if ser is None:
                st.info(t("no_data"))
            else:
                st.bar_chart(ser)

            _show_raw_toggle(teach_mod, "raw_lessons_mod")

    # ======================
    # TAB 4 — Risk & forecast (UPGRADED)
    # ======================
    with tab_risk:
        st.markdown(f"#### {t('forecast')}")

        buffer_days = st.selectbox(
            t("payment_buffer"),
            [0, 7, 14],
            index=0,
            format_func=lambda x: t("on_finish") if x == 0 else f"{x} {t('days_before')}",
            key="forecast_buffer_analytics",
        )

        forecast_df = build_forecast_table(payment_buffer_days=int(buffer_days))
        if forecast_df is None or forecast_df.empty:
            st.info(t("no_data"))
        else:
            # Column picks (Section 12 output)
            student_like = _first_existing_col(forecast_df, ["Student", "student", "name"])
            left_like = _first_existing_col(forecast_df, ["Lessons_Left_Units", "lessons_left_units", "lessons_left", "units_left"])
            remind_like = _first_existing_col(forecast_df, ["Reminder_Date", "reminder_date"])
            finish_like = _first_existing_col(forecast_df, ["Estimated_Finish_Date", "estimated_finish_date"])
            due_like = _first_existing_col(forecast_df, ["Due_Now", "due_now"])

            ftmp = forecast_df.copy()

            if left_like and left_like in ftmp.columns:
                ftmp[left_like] = pd.to_numeric(ftmp[left_like], errors="coerce").fillna(0.0).astype(float)
            else:
                ftmp[left_like or "_left_tmp"] = 0.0
                left_like = left_like or "_left_tmp"

            # Parse dates
            ftmp["_rem_dt"] = pd.to_datetime(ftmp.get(remind_like), errors="coerce") if remind_like else pd.NaT
            ftmp["_fin_dt"] = pd.to_datetime(ftmp.get(finish_like), errors="coerce") if finish_like else pd.NaT

            # Due logic: prefer Due_Now column from Forecast; else compute from reminder date
            if due_like and due_like in ftmp.columns:
                ftmp["_due_now"] = ftmp[due_like].astype(bool)
            else:
                ftmp["_due_now"] = ftmp["_rem_dt"].notna() & (ftmp["_rem_dt"] <= today)

            # Count metrics
            due_now_df = ftmp[ftmp["_due_now"]].copy()
            finishing_14d_df = ftmp[ftmp["_fin_dt"].notna() & (ftmp["_fin_dt"] <= (today + pd.Timedelta(days=14)))].copy()
            at_risk_count = int((ftmp[left_like] <= 2).sum())

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(t_a("students_in_forecast"), f"{len(ftmp)}")
            with c2:
                st.metric(t_a("due_now"), f"{len(due_now_df)}")
            with c3:
                st.metric(t_a("finishing_14d"), f"{len(finishing_14d_df)}")

            # Smaller second row metric (still useful)
            st.caption(f"{t_a('at_risk')} (≤2 {t_a('units_left')}): **{at_risk_count}**")

            _callout(t_a("important"), t_a("takeaway_pipeline"))

            st.markdown(f"##### {t_a('students_to_contact')}")

            # Show due now; if none, show next up (soonest reminders)
            if not due_now_df.empty:
                show_df = due_now_df.sort_values(["_rem_dt", left_like, student_like if student_like else "Student"]).head(10)
                st.caption("Due now based on your reminder buffer.")
            else:
                upcoming = ftmp[ftmp["_rem_dt"].notna() & (ftmp["_rem_dt"] > today)].copy()
                show_df = upcoming.sort_values(["_rem_dt", left_like, student_like if student_like else "Student"]).head(10)
                if not show_df.empty:
                    soonest = show_df["_rem_dt"].min()
                    st.caption(f"{t_a('next_up')}: {soonest.strftime('%Y-%m-%d')}")
                else:
                    st.info("No upcoming reminders found.")
                    show_df = pd.DataFrame()

            if not show_df.empty and student_like and student_like in show_df.columns:
                for _, row in show_df.iterrows():
                    sname = str(row.get(student_like, "")).strip() or "(student)"
                    units_left = row.get(left_like, None)
                    rem = row.get("_rem_dt", None)
                    fin = row.get("_fin_dt", None)

                    parts = [sname]
                    if units_left is not None and str(units_left) != "nan":
                        try:
                            parts.append(f"{t_a('units_left')}: {int(float(units_left))}")
                        except Exception:
                            pass
                    if rem is not None and pd.notna(rem):
                        parts.append(f"{t_a('remind')}: {pd.Timestamp(rem).strftime('%Y-%m-%d')}")
                    if fin is not None and pd.notna(fin):
                        parts.append(f"{t_a('finish')}: {pd.Timestamp(fin).strftime('%Y-%m-%d')}")
                    st.write("• " + " — ".join(parts))
            else:
                st.write("• " + t("no_data"))

            # Raw toggle (keeps your pattern)
            _show_raw_toggle(ftmp.drop(columns=["_rem_dt", "_fin_dt", "_due_now"], errors="ignore"), "raw_forecast")

# =========================
# FALLBACK
# =========================
else:
    go_to("home")
    st.rerun()