import streamlit as st
import html as _html
from core.i18n import t
from core.state import get_current_user_id
from core.database import load_community_profiles
from helpers.lesson_planner import QUICK_SUBJECTS, subject_label as _subject_label


def _lang_flag(code: str) -> str:
    return {"en": "🇬🇧", "es": "🇪🇸", "tr": "🇹🇷"}.get(code, code)


def render_community_member_cards(profiles: list, role_filter: str = "teacher"):
    """Render profile cards for a list of community members.

    role_filter: 'teacher' shows teacher/tutor profiles,
                 'student' shows student profiles.
    """
    if role_filter == "teacher":
        members = [
            p for p in profiles
            if p.get("show_community_profile")
            and str(p.get("role") or "teacher") in ("teacher", "tutor")
        ]
    else:
        members = [
            p for p in profiles
            if p.get("show_community_profile")
            and str(p.get("role") or "teacher") == "student"
        ]

    if not members:
        st.info(t("no_teachers_found") if role_filter == "teacher" else t("no_students_found"))
        return

    st.markdown(
        f"**{len(members)}** {t('teachers_found') if role_filter == 'teacher' else t('students_found')}"
    )

    for member in members:
        _name = _html.escape(
            str(member.get("display_name") or member.get("username") or "").strip() or "—"
        )
        _primary = [s for s in (member.get("primary_subjects") or []) if s != "other"]
        _custom = member.get("custom_subjects") or []
        _subjects = ", ".join(
            [_subject_label(s) for s in _primary] + [s.title() for s in _custom if s]
        )
        _languages = " ".join(
            _lang_flag(l) for l in (member.get("teaching_languages") or [])
        )
        _country = _html.escape(str(member.get("country") or "").strip())
        _avatar = str(member.get("avatar_url") or "").strip()
        _show_contact = bool(member.get("show_community_contact"))
        _email = str(member.get("email") or "").strip()

        # Build info line
        _info_parts = []
        if _subjects:
            _info_parts.append(_html.escape(_subjects))
        if _languages:
            _info_parts.append(_languages)
        if _country:
            _info_parts.append(f"🌍 {_country}")
        _info_line = " · ".join(_info_parts) if _info_parts else ""

        # Contact line
        _contact_line = ""
        if _show_contact and _email:
            _safe_email = _html.escape(_email)
            _contact_line = (
                f"<div style='margin-top:4px; font-size:0.82rem;'>"
                f"<a href='mailto:{_safe_email}' style='color:var(--primary-light, #60A5FA); text-decoration:none;'>"
                f"✉️ {_safe_email}</a></div>"
            )

        # Avatar
        if _avatar:
            _avatar_html = (
                f"<img src='{_html.escape(_avatar)}' "
                f"style='width:48px;height:48px;border-radius:50%;object-fit:cover;flex-shrink:0;' "
                f"referrerpolicy='no-referrer' />"
            )
        else:
            _avatar_html = (
                "<div style='width:48px;height:48px;border-radius:50%;flex-shrink:0;"
                "background:linear-gradient(135deg,#60A5FA,#A78BFA);"
                "display:flex;align-items:center;justify-content:center;"
                "font-size:1.2rem;color:#fff;'>👤</div>"
            )

        st.markdown(
            f"<div style='"
            f"background:var(--panel-soft, rgba(127,127,127,0.06));"
            f"border-radius:14px; padding:14px 16px; margin-bottom:10px;"
            f"border:1px solid var(--border); display:flex; align-items:center; gap:14px;'>"
            f"{_avatar_html}"
            f"<div style='flex:1; min-width:0;'>"
            f"<div style='font-weight:700; font-size:1.02rem;'>{_name}</div>"
            f"<div style='opacity:0.75; font-size:0.88rem;'>{_info_line}</div>"
            f"{_contact_line}"
            f"</div></div>",
            unsafe_allow_html=True,
        )


_LANG_OPTIONS = ["en", "es", "tr"]
_LANG_LABELS = {"en": "🇬🇧 English", "es": "🇪🇸 Español", "tr": "🇹🇷 Türkçe"}


def render_student_find_teacher():
    st.markdown(f"## 🔍 {t('find_my_teacher')}")
    st.markdown(f"*{t('find_my_teacher_subtitle')}*")

    # ── Load community teachers ──
    try:
        all_profiles = load_community_profiles()
    except Exception:
        all_profiles = []

    # Only show opted-in teacher/tutor profiles
    all_teachers = [
        p for p in all_profiles
        if p.get("show_community_profile")
        and str(p.get("role") or "teacher") in ("teacher", "tutor")
    ]

    # ── Step 1: Instructional language (multiselect) ──

    st.markdown(f"<span style='font-weight:600;'>{t('filter_by_language')}</span>", unsafe_allow_html=True)
    st.caption(t("filter_by_language_helper"))
    lang_filter = st.multiselect(
        "",
        _LANG_OPTIONS,
        format_func=lambda x: _LANG_LABELS.get(x, x),
        key="find_teacher_lang",
    )

    # Filter teachers by selected language(s)
    if lang_filter:
        teachers_by_lang = [
            p for p in all_teachers
            if any(l in (p.get("teaching_languages") or []) for l in lang_filter)
        ]
    else:
        teachers_by_lang = all_teachers

    # ── Step 2: Subject — built dynamically from language-filtered teachers ──
    _available_subjects: list[str] = []
    for p in teachers_by_lang:
        for s in (p.get("primary_subjects") or []):
            if s and s != "other" and s not in _available_subjects:
                _available_subjects.append(s)
        for s in (p.get("custom_subjects") or []):
            if s and s not in _available_subjects:
                _available_subjects.append(s)
    _available_subjects.sort()

    # Build options: known subjects first, then custom ones, "other" at the end for free-text search
    _known = [s for s in _available_subjects if s in QUICK_SUBJECTS and s != "other"]
    _custom = [s for s in _available_subjects if s not in QUICK_SUBJECTS]
    _subject_options = _known + _custom + ["other"]

    subject_filter = st.selectbox(
        t("filter_by_subject"),
        [""] + _subject_options,
        format_func=lambda x: (
            _subject_label(x) if x in QUICK_SUBJECTS
            else x.title() if x
            else t("all_subjects")
        ),
        key="find_teacher_subject",
    )

    custom_subject = ""
    if subject_filter == "other":
        custom_subject = st.text_input(
            t("other_subject_label"),
            key="find_teacher_custom_subject",
        ).strip()

    # ── Apply subject filter ──
    teachers = teachers_by_lang
    if subject_filter:
        if subject_filter == "other" and custom_subject:
            _cust_low = custom_subject.lower()
            teachers = [
                p for p in teachers
                if any(_cust_low in str(s).lower() for s in (p.get("custom_subjects") or []))
                or any(_cust_low in str(s).lower() for s in (p.get("primary_subjects") or []))
            ]
        elif subject_filter == "other":
            pass  # "other" selected but nothing typed — show all
        elif subject_filter in QUICK_SUBJECTS:
            teachers = [
                p for p in teachers
                if subject_filter in (p.get("primary_subjects") or [])
            ]
        else:
            # Custom subject from dropdown
            teachers = [
                p for p in teachers
                if subject_filter in (p.get("custom_subjects") or [])
            ]

    render_community_member_cards(teachers, role_filter="teacher")

