# ============================================================
# CLASS MANAGER — I18N / TRANSLATIONS
# ------------------------------------------------------------

from typing import Dict

# =========================
# I18N / TRANSLATIONS
# =========================
I18N: Dict[str, Dict[str, str]] = {
    "en": {
        # -------------------------
        # AUTH
        # -------------------------
        "login_required": "Login required",
        "sign_in": "Sign in",
        "sign_up": "Create account",
        "sign_out": "Sign out",
        "password": "Password",
        "email": "Email",
        "login_title": "Log in",
        "forgot_password": "Forgot password?",
        "email_reset_link": "Email for reset link",
        "send_reset_email": "Send reset email",
        "create_account": "Create account",

        "logged_in_ok": "Logged in ✅",
        "login_failed": "Login failed",
        "reset_email_sent": "Reset email sent. Check your inbox.",
        "reset_failed": "Reset failed",
        "account_created_check_email": "Account created. If confirmations are enabled, check your email, then log in.",
        "signup_failed": "Sign up failed",

        "update_profile_photo": "Update profile photo",
        "choose_photo": "Choose a photo",
        "close": "Close",
        "save": "Save",
        "profile_photo_updated": "Profile photo updated ✅",
        "upload_failed": "Upload failed",

        "signin_failed_no_session": "Sign-in failed (no session).",
        "signin_error": "Sign-in error",
        "signup_error": "Sign-up error",
        "account_created_now_signin": "Account created. Now sign in.",
        "user_name": "User name",

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
        "avatar_upload_invalid_image": "Please upload an image file.",
        "avatar_upload_empty": "The uploaded file is empty.",
        "avatar_upload_too_large": "Image is too large. Maximum size is {max_size_mb} MB.",
        "avatar_upload_missing_user": "Missing user ID.",
        "avatar_upload_storage_failed": "Storage upload failed",
        "avatar_upload_url_failed": "Could not generate avatar URL",
        "avatar_upload_no_public_url": "Upload succeeded, but no public URL was returned.",

        # -------------------------
        # ROFILE
        # -------------------------
        "profile": "Profile",
        "edit_profile": "Edit profile",
        "profile_updated": "Profile updated ✅",
        "preferred_ui_language": "Preferred UI language",
        "preferred_currency": "Preferred currency",
        "payment_currency": "Payment currency",
        "timezone_label": "Time zone",
        "country_label": "Country",
        "primary_subjects_label": "Primary subjects",
        "teaching_stages_label": "Teaching stages",
        "teaching_languages_label": "Teaching languages",
        "default_lesson_duration_label": "Default lesson duration",
        "onboarding_completed": "Onboarding completed",
        "save_profile": "Save profile",
        "teacher_role": "Teacher",
        "tutor_role": "Tutor",
        "role_label": "Role",
        "subject_english": "English",
        "subject_spanish": "Spanish",
        "subject_mathematics": "Mathematics",
        "subject_science": "Science",
        "subject_music": "Music",
        "subject_study_skills": "Study Skills",
        "stage_early_primary": "Early Primary (6–8)",
        "stage_upper_primary": "Upper Primary (9–11)",
        "stage_lower_secondary": "Lower Secondary (12–14)",
        "stage_upper_secondary": "Upper Secondary (15–18)",
        "stage_adult": "Adult",
        "duration_30": "30 minutes",
        "duration_45": "45 minutes",
        "duration_60": "60 minutes",
        "duration_90": "90 minutes",

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
        "subject": "Subject",
        "subject_other": "Please specify subject",
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
        # FILES
        # -------------------------        
        "files": "Files",
        "all": "All",
        "my_plans": "My Plans",
        "community_library": "Community Library",
        "no_saved_lesson_plans": "You do not have any saved lesson plans yet.",
        "community_library_empty": "The community library is empty for now.",
        "search_by_topic": "Search by topic",
        "search_community_topic": "Search community topic",
        "community_subject": "Community subject",
        "close_files": "Close",
        "quick_plan_topic_placeholder": "Fractions / Photosynthesis / Travel / Rhythm / Time management",
        "view_plan": "View plan",
        "plan_preview": "Plan preview",
        "close_plan": "Close plan",
        "untitled_plan": "Untitled plan",
        "author_name": "Author",
        "source_type": "Source",
        "download_pdf": "Download PDF",

        # -------------------------
        # QUICK LESSON PLANNER
        # -------------------------
        "quick_lesson_planner": "Quick lesson planner",
        "quick_lesson_caption": "Generate a ready-to-use 45-minute emergency lesson",
        "student_type": "Student type",
        "kid": "Kid",
        "adult": "Adult",
        "lesson_type": "Lesson type",
        "reading": "Reading",
        "listening": "Listening",
        "speaking": "Speaking",
        "writing": "Writing",
        "level_cefr": "Level",
        "subject_label": "Subject",
        "topic_label": "Topic",
        "generate_plan": "Generate plan",
        "lesson_plan_ready": "Lesson plan ready ✅",
        "lesson_objective": "Lesson objective",
        "warm_up": "Warm-up",
        "main_activity": "Main activity",
        "guided_practice": "Guided practice",
        "freer_task": "Freer task",
        "wrap_up": "Wrap-up",
        "reading_passage": "Reading passage",
        "listening_script": "Listening script",
        "comprehension_questions": "Comprehension questions",
        "teacher_notes": "Teacher notes",
        "optional_homework": "Optional homework",
        "plan_title": "Lesson title",
        "lesson_duration_45": "45-minute lesson",
        "enter_topic": "Please enter a topic.",
        "learner_stage": "Learner stage",
        "lesson_purpose": "Lesson purpose",
        "level_or_band": "Level / band",
        "early_primary": "Early Primary (6–8)",
        "upper_primary": "Upper Primary (9–11)",
        "lower_secondary": "Lower Secondary (12–14)",
        "upper_secondary": "Upper Secondary (15–18)",
        "adult_stage": "Adult",
        "beginner_band": "Beginner",
        "intermediate_band": "Intermediate",
        "advanced_band": "Advanced",
        "introduce_concept": "Introduce a concept",
        "practice_skill": "Practice a skill",
        "review_topic": "Review a topic",
        "diagnose_difficulty": "Diagnose a difficulty",
        "discussion_exploration": "Discussion / exploration",
        "success_criteria": "Success criteria",
        "extension_task": "Extension task",
        "keep_plan": "Keep plan",
        "delete_plan": "Delete plan",
        "plan_kept": "Plan kept in the app ✅",
        "plan_deleted": "Plan deleted ✅",
        "teacher_moves": "Teacher moves",
        "core_examples": "Core examples",
        "practice_questions": "Practice questions",
        "recommended_level": "Recommended level",
        "quick_plan_saved_label": "Saved plan",
        "target_vocabulary": "Target vocabulary",
        "pre_task_questions": "Before the task",
        "gist_questions": "Main idea questions",
        "detail_questions": "Detail questions",
        "post_task": "After the task",
        "worked_example": "Worked example",
        "independent_practice": "Independent practice",
        "common_error_alert": "Common error alert",
        "concept_explanation": "Concept explanation",
        "real_life_application": "Real-life application",
        "strategy_steps": "Strategy steps",
        "performance_goal": "Performance goal",
        "plan_language_note": "The plan follows the app language.",
        "student_material_language": "Student material language",
        "plan_language": "Plan language",

        # -------------------------
        # AI PLANNER
        # -------------------------
        "generation_mode": "Generation mode",
        "mode_template": "Template",
        "mode_ai": "AI",
        "ai_plans_left_today": "AI plans left today: {remaining} / {limit}",
        "mode_used": "Mode used: {mode}",
        "save_template_plan": "Save template plan",
        "template_plan_saved": "Template plan saved.",
        "ai_limit_reached": "AI daily limit reached. Template plan generated instead.",
        "ai_cooldown_active": "AI cooldown active. Please wait {seconds} seconds. Template plan generated instead.",
        "ai_unavailable_fallback": "AI planner unavailable. Template plan generated instead.",

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
        "time": "Time", 
        "duration_minutes": "Duration (min)", 
        "active": "Active",
        "invalid_time_format": "Incorrect time inserted. Please use 24-hour (HH:MM) format.",

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
        "all_time_income": "Total income",
        "yearly": "Yearly",
        "monthly": "Monthly",
        "weekly": "Weekly",
        "all_time_monthly_income": "All time monthly income",
        "monthly_income": "Monthly",
        "yearly_income": "Yearly",
        "yearly_totals": "Yearly",
        "weekly_income": "Weekly",
        "last_7_days": "Last 7 days",
        "most_profitable_students": "Most profitable students",
        "packages_by_language": "Packages by language",
        "packages_by_subject": "Packages by subject",
        "packages_by_modality": "Packages by modality",
        "lessons_by_language": "Lessons by language",
        "lessons_by_subject": "Lessons by subject",
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
        "pricing_set_price_hint": "Please set your prices below before registering payments.",
        
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
        
        # -------------------------
        # ANALYTICS PAGE
        # -------------------------

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
        "total_revenue_language": "Total income by subject",
        "total_revenue_modality": "Total income by modality",
        "top_segment_share": "Top segment share",
        "total_units": "Total lesson units",
        "top_language": "Top lesson language",
        "top_subject": "Top subject",
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
        "takeaway_language": "Your strongest subject segment is {name} ({share} of subject income).",
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

        # Currency & inflation
        "display_settings": "Display settings",
        "base_currency": "Base currency (your data)",
        "display_currency": "Display currency",
        "adjust_inflation": "Adjust for inflation",
        "inflation_country": "Country (CPI source)",
        "values_adjusted_to": "Values adjusted to",
        "inflation_data_up_to": "Inflation data available up to",
        "nominal_values": "Nominal values (no adjustment)",
        "total_year_income": "Total income",
        "total_lessons": "Total lessons",
        "all_time": "All time",
        "fx_rate_caption": "Exchange rate",
        "cpi_no_data": "No CPI data available for this country",
    },

    "es": {
        # -------------------------
        # AUTH
        # -------------------------
        "login_required": "Inicio de sesión requerido",
        "sign_in": "Iniciar sesión",
        "sign_up": "Crear cuenta",
        "sign_out": "Cerrar sesión",
        "password": "Contraseña",
        "email": "Correo electrónico",
        "login_title": "Iniciar sesión",
        "forgot_password": "¿Olvidaste tu contraseña?",
        "email_reset_link": "Correo para enlace de restablecimiento",
        "send_reset_email": "Enviar correo de restablecimiento",
        "create_account": "Crear cuenta",

        "logged_in_ok": "Sesión iniciada ✅",
        "login_failed": "Error al iniciar sesión",
        "reset_email_sent": "Correo de restablecimiento enviado. Revisa tu bandeja de entrada.",
        "reset_failed": "Error al restablecer la contraseña",
        "account_created_check_email": "Cuenta creada. Si las confirmaciones están activadas, revisa tu correo y luego inicia sesión.",
        "signup_failed": "Error al crear la cuenta",

        "update_profile_photo": "Actualizar foto de perfil",
        "choose_photo": "Elegir una foto",
        "close": "Cerrar",
        "save": "Guardar",
        "profile_photo_updated": "Foto de perfil actualizada ✅",
        "upload_failed": "Error al subir la foto",

        "signin_failed_no_session": "Error al iniciar sesión (sin sesión).",
        "signin_error": "Error de inicio de sesión",
        "signup_error": "Error al crear la cuenta",
        "account_created_now_signin": "Cuenta creada. Ahora inicia sesión.",
        "user_name": "Nombre de usuario",

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
        "avatar_upload_invalid_image": "Por favor sube un archivo de imagen.",
        "avatar_upload_empty": "La imagen subida está vacía.",
        "avatar_upload_too_large": "La imagen es demasiado grande. El tamaño máximo es de {max_size_mb} MB.",
        "avatar_upload_missing_user": "Falta el ID del usuario.",
        "avatar_upload_storage_failed": "Error al subir la imagen al almacenamiento",
        "avatar_upload_url_failed": "No se pudo generar la URL pública de la imagen",
        "avatar_upload_no_public_url": "La imagen se subió, pero no se obtuvo una URL pública.",

        # -------------------------
        # PROFILE
        # -------------------------
        "profile": "Perfil",
        "edit_profile": "Editar perfil",
        "profile_updated": "Perfil actualizado ✅",
        "preferred_ui_language": "Idioma de la interfaz",
        "preferred_currency": "Moneda preferida",
        "payment_currency": "Moneda del pago",
        "timezone_label": "Zona horaria",
        "country_label": "País",
        "primary_subjects_label": "Materias principales",
        "teaching_stages_label": "Etapas que enseñas",
        "teaching_languages_label": "Idiomas que enseñas",
        "default_lesson_duration_label": "Duración predeterminada de clase",
        "onboarding_completed": "Onboarding completado",
        "save_profile": "Guardar perfil",
        "teacher_role": "Profesor",
        "tutor_role": "Tutor",
        "role_label": "Rol",
        "subject_english": "Inglés",
        "subject_spanish": "Español",
        "subject_mathematics": "Matemáticas",
        "subject_science": "Ciencias",
        "subject_music": "Música",
        "subject_study_skills": "Técnicas de estudio",
        "stage_early_primary": "Primaria inicial (6–8)",
        "stage_upper_primary": "Primaria superior (9–11)",
        "stage_lower_secondary": "Secundaria baja (12–14)",
        "stage_upper_secondary": "Secundaria alta (15–18)",
        "stage_adult": "Adulto",
        "duration_30": "30 minutos",
        "duration_45": "45 minutos",
        "duration_60": "60 minutos",
        "duration_90": "90 minutos",

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
        "subject": "Materia",
        "subject_other": "Especifica la materia",
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
        # FILES
        # -------------------------  
        "files": "Archivos",
        "all": "Todos",
        "my_plans": "Mis planes",
        "community_library": "Biblioteca comunitaria",
        "no_saved_lesson_plans": "Todavía no tienes planes de clase guardados.",
        "community_library_empty": "La biblioteca comunitaria está vacía por ahora.",
        "search_by_topic": "Buscar por tema",
        "search_community_topic": "Buscar tema en la comunidad",
        "community_subject": "Materia de la comunidad",
        "close_files": "Cerrar",
        "quick_plan_topic_placeholder": "Fracciones / Fotosíntesis / Viajes / Ritmo / Gestión del tiempo",
        "view_plan": "Ver plan",
        "plan_preview": "Vista previa del plan",
        "close_plan": "Cerrar plan",
        "untitled_plan": "Plan sin título",
        "author_name": "Autor",
        "source_type": "Fuente",
        "download_pdf": "Descargar PDF",


        # -------------------------
        # QUICK LESSON PLANNER
        # -------------------------
        "quick_lesson_planner": "Planificador rápido de clases",
        "quick_lesson_caption": "Genera una clase de emergencia de 45 minutos lista para usar",
        "student_type": "Tipo de estudiante",
        "kid": "Niño",
        "adult": "Adulto",
        "lesson_type": "Tipo de clase",
        "reading": "Lectura",
        "listening": "Escucha",
        "speaking": "Conversación",
        "writing": "Escritura",
        "level_cefr": "Nivel",
        "subject_label": "Materia",
        "topic_label": "Tema",
        "generate_plan": "Generar plan",
        "lesson_plan_ready": "Plan de clase listo ✅",
        "lesson_objective": "Objetivo de la clase",
        "warm_up": "Calentamiento",
        "main_activity": "Actividad principal",
        "guided_practice": "Práctica guiada",
        "freer_task": "Tarea libre",
        "wrap_up": "Cierre",
        "reading_passage": "Texto de lectura",
        "listening_script": "Guion de escucha",
        "comprehension_questions": "Preguntas de comprensión",
        "teacher_notes": "Notas para el profesor",
        "optional_homework": "Tarea opcional",
        "plan_title": "Título de la clase",
        "lesson_duration_45": "Clase de 45 minutos",
        "enter_topic": "Por favor escribe el tema.",
        "learner_stage": "Etapa del estudiante",
        "lesson_purpose": "Propósito de la clase",
        "level_or_band": "Nivel / banda",
        "early_primary": "Primaria inicial (6–8)",
        "upper_primary": "Primaria superior (9–11)",
        "lower_secondary": "Secundaria baja (12–14)",
        "upper_secondary": "Secundaria alta (15–18)",
        "adult_stage": "Adulto",
        "beginner_band": "Principiante",
        "intermediate_band": "Intermedio",
        "advanced_band": "Avanzado",
        "introduce_concept": "Introducir un concepto",
        "practice_skill": "Practicar una habilidad",
        "review_topic": "Repasar un tema",
        "diagnose_difficulty": "Diagnosticar una dificultad",
        "discussion_exploration": "Discusión / exploración",
        "success_criteria": "Criterios de logro",
        "extension_task": "Actividad de extensión",
        "keep_plan": "Guardar plan",
        "delete_plan": "Eliminar plan",
        "plan_kept": "Plan guardado en la app ✅",
        "plan_deleted": "Plan eliminado ✅",
        "teacher_moves": "Movimientos del profesor",
        "core_examples": "Ejemplos clave",
        "practice_questions": "Preguntas de práctica",
        "recommended_level": "Nivel recomendado",
        "quick_plan_saved_label": "Plan guardado",
        "target_vocabulary": "Vocabulario objetivo",
        "pre_task_questions": "Antes de la actividad",
        "gist_questions": "Preguntas globales",
        "detail_questions": "Preguntas de detalle",
        "post_task": "Después de la actividad",
        "worked_example": "Ejemplo resuelto",
        "independent_practice": "Práctica independiente",
        "common_error_alert": "Error común",
        "concept_explanation": "Explicación del concepto",
        "real_life_application": "Aplicación en la vida real",
        "strategy_steps": "Pasos de la estrategia",
        "performance_goal": "Objetivo de desempeño",
        "plan_language_note": "El plan sigue el idioma de la app.",
        "student_material_language": "Idioma del material del estudiante",
        "plan_language": "Idioma del plan",

        # -------------------------
        # AI PLANNER
        # -------------------------
        "generation_mode": "Modo de generación",
        "mode_template": "Plantilla",
        "mode_ai": "IA",
        "ai_plans_left_today": "Planes de IA disponibles hoy: {remaining} / {limit}",
        "mode_used": "Modo usado: {mode}",
        "save_template_plan": "Guardar plan de plantilla",
        "template_plan_saved": "Plan de plantilla guardado.",
        "ai_limit_reached": "Se alcanzó el límite diario de IA. Se generó un plan de plantilla en su lugar.",
        "ai_cooldown_active": "La IA está en enfriamiento. Espera {seconds} segundos. Se generó un plan de plantilla en su lugar.",
        "ai_unavailable_fallback": "El planificador con IA no está disponible. Se generó un plan de plantilla en su lugar.",


        # -------------------------
        # DASHBOARD
        # -------------------------
        "manage_current_students": "Administra tus estudiantes y paquetes actuales",
        "take_action": "Toma acción",
        "current_packages": "Paquetes actuales",
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
        "time": "Hora", 
        "duration_minutes": "Duración (min)", 
        "active": "Activo",
        "invalid_time_format": "Hora incorrecta. Utilice el formato 24 horas HH:MM.",

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
        "all_time_income": "Total",
        "yearly": "Anual",
        "monthly": "Mensual",
        "weekly": "Semanal",
        "all_time_monthly_income": "Ingresos mensuales históricos",
        "monthly_income": "Mensual",
        "yearly_income": "Anual",
        "yearly_totals": "Totales anuales",
        "weekly_income": "Semanal",
        "last_7_days": "Últimos 7 días",
        "most_profitable_students": "Estudiantes más rentables",
        "packages_by_language": "Paquetes por idioma",
        "packages_by_subject": "Paquetes por materia",
        "packages_by_modality": "Paquetes por modalidad",
        "lessons_by_language": "Clases por idioma",
        "lessons_by_subject": "Clases por materia",
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
        "pricing_set_price_hint": "Por favor establece tus precios antes de registrar pagos.",
        
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
                # -------------------------
        # ANALYTICS PAGE
        # -------------------------

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
        "total_revenue_language": "Ingreso total por materia",
        "total_revenue_modality": "Ingreso total por modalidad",
        "top_segment_share": "Participación del segmento líder",
        "total_units": "Unidades de clase totales",
        "top_language": "Idioma principal",
        "top_subject": "Materia principal",
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
        "takeaway_language": "Tu materia más fuerte es {name} ({share} del ingreso por materia).",
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

        # Currency & inflation
        "display_settings": "Configuración de visualización",
        "base_currency": "Moneda base (tus datos)",
        "display_currency": "Moneda de visualización",
        "adjust_inflation": "Ajustar por inflación",
        "inflation_country": "País (fuente de IPC)",
        "values_adjusted_to": "Valores ajustados a",
        "inflation_data_up_to": "Datos de inflación disponibles hasta",
        "nominal_values": "Valores nominales (sin ajuste)",
        "total_year_income": "Ingreso total",
        "total_lessons": "Total de clases",
        "all_time": "Todo el historial",
        "fx_rate_caption": "Tipo de cambio",
        "cpi_no_data": "No hay datos de IPC disponibles para este país",
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
    },
    }