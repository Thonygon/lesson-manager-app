import streamlit as st
import html as _html
import math
from core.i18n import t
from core.state import get_current_user_id
from core.database import load_community_profiles, profile_can_teach, profile_can_study
from helpers.lesson_planner import QUICK_SUBJECTS, subject_label as _subject_label
from helpers.teacher_student_integration import archive_teacher_student_link, create_teacher_request, load_student_teacher_links

_FIND_TEACHER_PAGE_SIZE = 6


def _slice_finder_page(rows: list, state_key: str, *, page_size: int = _FIND_TEACHER_PAGE_SIZE):
    total_items = len(rows or [])
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    return list((rows or [])[start_idx:end_idx]), current_page, total_pages, start_idx, end_idx, total_items


def _render_finder_pagination(rows: list, state_key: str, *, page_size: int = _FIND_TEACHER_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_finder_page(
        rows, state_key, page_size=page_size,
    )
    if total_items <= page_size:
        return
    prev_col, info_col, next_col = st.columns([1, 3, 1])
    with prev_col:
        if st.button("←", key=f"{state_key}_prev", use_container_width=True, disabled=current_page <= 1):
            st.session_state[state_key] = max(1, current_page - 1)
            st.rerun()
    with info_col:
        st.caption(f"{start_idx + 1}-{end_idx} / {total_items} · {current_page}/{total_pages}")
    with next_col:
        if st.button("→", key=f"{state_key}_next", use_container_width=True, disabled=current_page >= total_pages):
            st.session_state[state_key] = min(total_pages, current_page + 1)
            st.rerun()


def _render_end_relationship_action(*, link_id: int, key_prefix: str) -> None:
    with st.popover(t("end_relationship"), use_container_width=True):
        st.warning(t("relationship_end_warning"))
        confirm = st.checkbox(
            t("relationship_end_confirm_checkbox"),
            key=f"{key_prefix}_confirm_end_relationship",
        )
        if st.button(
            t("relationship_end_confirm_button"),
            key=f"{key_prefix}_confirm_end_relationship_btn",
            use_container_width=True,
            type="primary",
            disabled=not confirm,
        ):
            ok, msg = archive_teacher_student_link(int(link_id))
            if ok:
                st.success(t(msg))
                st.rerun()
            st.error(t(msg))


def _lang_flag(code: str) -> str:
    return {"en": "🇬🇧", "es": "🇪🇸", "tr": "🇹🇷"}.get(code, code)


def _inject_find_teacher_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-teacher-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(16,185,129,.10), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 80%, white 20%));
            border: 1px solid color-mix(in srgb, var(--border) 76%, rgba(16,185,129,.22) 24%);
            border-radius: 22px;
            padding: 18px 18px;
            margin-bottom: 0.55rem;
            box-shadow: 0 14px 34px rgba(15,23,42,.08);
        }
        .classio-teacher-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #14b8a6, #38bdf8 58%, #8b5cf6);
        }
        .classio-teacher-name {
            font-weight: 800;
            font-size: 1.08rem;
            color: var(--text);
            line-height: 1.2;
        }
        .classio-teacher-meta {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-teacher-status {
            display: inline-flex;
            align-items: center;
            margin: 0.1rem 0 1rem 0.15rem;
            padding: 0.42rem 0.78rem;
            border-radius: 999px;
            background: rgba(59,130,246,.10);
            color: #2563eb;
            border: 1px solid rgba(59,130,246,.18);
            font-size: 0.78rem;
            font-weight: 800;
        }
        .classio-teacher-action-label {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin: 0.25rem 0 0.55rem 0.1rem;
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            border-radius: 16px;
            min-height: 3rem;
            font-weight: 800;
            box-shadow: 0 14px 28px rgba(37,99,235,.18);
        }
        div[data-testid="stButton"] > button[kind="secondary"] {
            border-radius: 16px;
            min-height: 3rem;
            font-weight: 700;
            border-color: rgba(148,163,184,.28);
            box-shadow: 0 8px 18px rgba(15,23,42,.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_community_member_cards(profiles: list, role_filter: str = "teacher"):
    """Render profile cards for a list of community members.

    role_filter: 'teacher' shows teacher/tutor profiles,
                 'student' shows student profiles.
    """
    if role_filter == "teacher":
        members = [
            p for p in profiles
            if p.get("show_community_profile")
            and profile_can_teach(p)
        ]
    else:
        members = [
            p for p in profiles
            if p.get("show_community_profile")
            and profile_can_study(p)
        ]

    if not members:
        st.info(t("no_teachers_found") if role_filter == "teacher" else t("no_students_found"))
        return

    st.markdown(
        f"**{len(members)}** {t('teachers_found') if role_filter == 'teacher' else t('students_found')}"
    )

    current_links = {
        str(row.get("teacher_id") or ""): row
        for row in load_student_teacher_links()
    }

    members_page, *_ = _slice_finder_page(members, f"community_{role_filter}_page")
    for member in members_page:
        relationship = current_links.get(str(member.get("user_id") or "").strip())
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

        card_col, action_col = st.columns([6, 2], gap="medium")
        with card_col:
            st.markdown(
                f"<div class='classio-teacher-card' style='display:flex; align-items:center; gap:14px;'>"
                f"{_avatar_html}"
                f"<div style='flex:1; min-width:0;'>"
                f"<div class='classio-teacher-name'>{_name}</div>"
                f"<div class='classio-teacher-meta'>{_info_line}</div>"
                f"{_contact_line}"
                f"</div></div>",
                unsafe_allow_html=True,
            )

            status = str((relationship or {}).get("status") or "").strip()
            if status:
                st.markdown(
                    f"<div class='classio-teacher-status'>{_html.escape(t(f'teacher_relationship_{status}'))}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

        if role_filter == "teacher":
            available_subjects = []
            for item in _primary:
                available_subjects.append(item)
            for item in _custom:
                if item:
                    available_subjects.append(item)
            available_subjects = list(dict.fromkeys(available_subjects))

            with action_col:
                st.markdown(
                    f"<div class='classio-teacher-action-label'>{_html.escape(t('relationship_end_prompt') if status == 'active' else t('add_as_my_teacher'))}</div>",
                    unsafe_allow_html=True,
                )
                if status in {"pending", "active"}:
                    if status == "active":
                        _render_end_relationship_action(
                            link_id=int(relationship.get("id") or 0),
                            key_prefix=f"teacher_rel_archive_{member.get('user_id')}",
                        )
                else:
                    with st.popover(t("add_as_my_teacher"), use_container_width=True):
                        chosen_subjects = st.multiselect(
                            t("active_subjects"),
                            options=available_subjects,
                            format_func=lambda x: _subject_label(x) if x in QUICK_SUBJECTS else _clean_custom_subject_label(x),
                            key=f"teacher_req_subjects_{member.get('user_id')}",
                        )
                        request_note = st.text_area(
                            t("teacher_note"),
                            key=f"teacher_req_note_{member.get('user_id')}",
                            height=80,
                            placeholder=t("teacher_request_note_placeholder"),
                        )
                        if st.button(
                            t("request_teacher"),
                            key=f"teacher_req_btn_{member.get('user_id')}",
                            use_container_width=True,
                            type="primary",
                        ):
                            ok, msg = create_teacher_request(
                                str(member.get("user_id") or ""),
                                chosen_subjects,
                                note=request_note,
                            )
                            if ok:
                                st.success(t(msg))
                                st.rerun()
                            st.error(t(msg))
    _render_finder_pagination(members, f"community_{role_filter}_page")


def _clean_custom_subject_label(value: str) -> str:
    text = str(value or "").strip()
    return text[:1].upper() + text[1:] if text else ""


_LANG_OPTIONS = ["en", "es", "tr"]
_LANG_LABELS = {"en": "🇬🇧 English", "es": "🇪🇸 Español", "tr": "🇹🇷 Türkçe"}


def render_student_find_teacher():
    _inject_find_teacher_styles()
    st.markdown(f"## 🔍 {t('find_my_teacher')}")
    st.markdown(f"*{t('find_my_teacher_subtitle')}*")

    relationships = load_student_teacher_links()
    if relationships:
        st.markdown(f"### {t('my_teachers')}")
        for row in relationships:
            teacher_name = row.get("teacher_name", "—")
            status = str(row.get("status") or "").strip()
            subjects = ", ".join(
                s.get("subject_label", "")
                for s in (row.get("active_subjects") or row.get("requested_subjects") or [])
                if s.get("subject_label")
            )
            st.markdown(f"**{teacher_name}**")
            st.caption(f"{t(f'teacher_relationship_{status}')} · {subjects}" if subjects else t(f"teacher_relationship_{status}"))

    # ── Load community teachers ──
    try:
        all_profiles = load_community_profiles()
    except Exception:
        all_profiles = []

    # Only show opted-in teacher/tutor profiles
    all_teachers = [
        p for p in all_profiles
        if p.get("show_community_profile")
        and profile_can_teach(p)
    ]

    # ── Step 1: Instructional language (multiselect) ──

    lang_filter = st.multiselect(
        t('filter_by_language'),
        _LANG_OPTIONS,
        format_func=lambda x: _LANG_LABELS.get(x, x.title() if x else x),
        placeholder=t("filter_by_language_helper"),
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
