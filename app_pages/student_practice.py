import streamlit as st
import json
import math
from core.i18n import t
from core.navigation import go_to
from helpers.practice_engine import (
    autosave_practice_draft_if_needed,
    worksheet_to_exercises,
    exam_to_exercises,
    normalize_exercise_data_for_web,
    render_practice_session,
    save_practice_session,
    save_practice_draft,
    save_practice_answers,
    update_practice_progress,
    update_practice_session,
    load_practice_history,
    load_practice_progress,
    load_in_progress_practice_session,
    load_practice_draft_answers,
    get_completed_source_ids,
    get_total_xp,
    get_global_best_streak,
    get_rank,
    calculate_session_xp,
)
from helpers.teacher_student_integration import (
    _clean_teacher_feedback_text,
    create_teacher_review_request,
    get_reviewable_teacher_links_for_subject,
    load_assignment_state_map,
    load_student_review_requests_for_session,
)

_STUDENT_PRACTICE_PAGE_SIZE = 4


def _slice_practice_page(rows: list[dict], state_key: str, *, page_size: int = _STUDENT_PRACTICE_PAGE_SIZE):
    total_items = len(rows or [])
    total_pages = max(1, math.ceil(total_items / page_size)) if total_items else 1
    current_page = int(st.session_state.get(state_key, 1) or 1)
    current_page = max(1, min(current_page, total_pages))
    st.session_state[state_key] = current_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)
    return list((rows or [])[start_idx:end_idx]), current_page, total_pages, start_idx, end_idx, total_items


def _render_practice_pagination(rows: list[dict], state_key: str, *, page_size: int = _STUDENT_PRACTICE_PAGE_SIZE) -> None:
    _, current_page, total_pages, start_idx, end_idx, total_items = _slice_practice_page(
        rows,
        state_key,
        page_size=page_size,
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


def _open_practice_item(exercise_data: dict, meta: dict | None = None, *, demo_id: str | None = None) -> bool:
    """Open a practice item only if it contains runnable exercises."""
    exercise_data = normalize_exercise_data_for_web(exercise_data or {})
    exercises = (exercise_data or {}).get("exercises") or []
    if not exercises:
        st.warning(t("no_exercises_available"))
        return False

    draft = load_in_progress_practice_session(
        str((exercise_data or {}).get("source_type") or ""),
        (exercise_data or {}).get("source_id"),
    )
    if draft:
        draft_exercise_data = draft.get("exercise_data") or exercise_data
        if isinstance(draft_exercise_data, str):
            try:
                draft_exercise_data = json.loads(draft_exercise_data)
            except Exception:
                draft_exercise_data = exercise_data
        draft_exercise_data = normalize_exercise_data_for_web(draft_exercise_data or exercise_data)
        st.session_state["practice_exercise_data"] = draft_exercise_data
        st.session_state["practice_meta"] = meta or {}
        st.session_state["_practice_resume_session_id"] = draft.get("id")
        st.session_state["_practice_resume_answers"] = load_practice_draft_answers(int(draft.get("id")))
        st.session_state["_practice_resume_notice"] = True
    else:
        st.session_state["practice_exercise_data"] = exercise_data
        st.session_state["practice_meta"] = meta or {}
        st.session_state.pop("_practice_resume_session_id", None)
        st.session_state.pop("_practice_resume_answers", None)
        st.session_state.pop("_practice_resume_notice", None)

    if demo_id:
        st.session_state["_practice_demo_id"] = demo_id
    else:
        st.session_state.pop("_practice_demo_id", None)
    return True


def render_student_practice():
    st.markdown(f"## 🧠 {t('smart_practice')}")
    _inject_student_practice_styles()

    # ── Active practice session ─────────────────────────────────
    exercise_data = st.session_state.get("practice_exercise_data")
    if exercise_data:
        _render_active_session(exercise_data)
        return

    # ── Gamification dashboard ──────────────────────────────────
    _render_xp_dashboard()

    # ── Main menu ───────────────────────────────────────────────
    tab_browse, tab_history, tab_progress = st.tabs([
        f"🎯 {t('start_practice')}",
        f"📊 {t('practice_history')}",
        f"📈 {t('my_progress')}",
    ])

    with tab_browse:
        _render_browse_tab()

    with tab_history:
        _render_history_tab()

    with tab_progress:
        _render_progress_tab()


# ── XP Dashboard ────────────────────────────────────────────────

def _render_xp_dashboard():
    """Compact XP / rank / streak bar at the top."""
    total_xp    = get_total_xp()
    best_streak = get_global_best_streak()
    rank_key, rank_emoji, xp_into, xp_span = get_rank(total_xp)
    rank_label = t(f"rank_{rank_key}") if t(f"rank_{rank_key}") != f"rank_{rank_key}" else rank_key.replace("_", " ").title()

    pct = min(round(xp_into / xp_span * 100), 100) if xp_span else 100

    # Find next rank name
    from helpers.practice_engine import RANKS
    next_rank_label = ""
    for i, (thr, key, _em) in enumerate(RANKS):
        if total_xp >= thr and i < len(RANKS) - 1:
            nk = RANKS[i + 1][1]
            next_rank_label = t(f"rank_{nk}") if t(f"rank_{nk}") != f"rank_{nk}" else nk.replace("_", " ").title()

    progress_label = f"{xp_into}/{xp_span} XP" if xp_span else "MAX"

    st.markdown(
        f"""
        <div style="
            display:flex; align-items:center; gap:14px;
            padding:10px 16px; border-radius:14px;
            background:var(--panel); border:1px solid var(--border);
            margin-bottom:14px; flex-wrap:wrap;
        ">
            <div style="font-size:1.6rem;">{rank_emoji}</div>
            <div style="flex:1;min-width:140px;">
                <div style="font-weight:800;font-size:0.92rem;">{rank_label}</div>
                <div style="background:var(--border);border-radius:6px;height:8px;overflow:hidden;margin-top:4px;">
                    <div style="width:{pct}%;height:100%;background:linear-gradient(90deg,#8B5CF6,#6D28D9);border-radius:6px;transition:width 0.4s;"></div>
                </div>
                <div style="font-size:0.7rem;color:var(--muted);margin-top:2px;">
                    {progress_label}{(' → ' + next_rank_label) if next_rank_label else ''}
                </div>
            </div>
            <div style="text-align:center;min-width:70px;">
                <div style="font-size:1.1rem;font-weight:800;color:#8B5CF6;">{total_xp}</div>
                <div style="font-size:0.68rem;color:var(--muted);">XP</div>
            </div>
            <div style="text-align:center;min-width:70px;">
                <div style="font-size:1.1rem;font-weight:800;color:#F59E0B;">🔥 {best_streak}</div>
                <div style="font-size:0.68rem;color:var(--muted);">{t('best_streak')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _inject_student_practice_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-practice-card {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(99,102,241,.10), transparent 36%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(99,102,241,.22) 22%);
            border-radius: 22px;
            padding: 18px 20px;
            box-shadow: 0 14px 32px rgba(15,23,42,.08);
            margin-bottom: 0.55rem;
        }
        .classio-practice-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #38bdf8, #6366f1 58%, #8b5cf6);
        }
        .classio-practice-card--worksheet {
            background:
              radial-gradient(circle at top right, rgba(167,139,250,.12), transparent 36%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border-color: color-mix(in srgb, var(--border) 78%, rgba(167,139,250,.22) 22%);
        }
        .classio-practice-card--worksheet::before {
            background: linear-gradient(180deg, #a78bfa, #8b5cf6 58%, #6366f1);
        }
        .classio-practice-card--exam {
            background:
              radial-gradient(circle at top right, rgba(248,113,113,.12), transparent 36%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border-color: color-mix(in srgb, var(--border) 78%, rgba(248,113,113,.22) 22%);
        }
        .classio-practice-card--exam::before {
            background: linear-gradient(180deg, #f87171, #ef4444 58%, #f59e0b);
        }
        .classio-practice-card--topic {
            background:
              radial-gradient(circle at top right, rgba(96,165,250,.12), transparent 36%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border-color: color-mix(in srgb, var(--border) 78%, rgba(96,165,250,.22) 22%);
        }
        .classio-practice-card--topic::before {
            background: linear-gradient(180deg, #60a5fa, #3b82f6 58%, #38bdf8);
        }
        .classio-practice-title {
            font-size: 1.06rem;
            font-weight: 800;
            line-height: 1.25;
            color: var(--text);
        }
        .classio-practice-meta {
            margin-top: 0.65rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .classio-practice-statgrid {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            margin-top: 0.95rem;
        }
        .classio-practice-stat {
            min-width: 96px;
            padding: 0.72rem 0.85rem;
            border-radius: 15px;
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.16);
        }
        .classio-practice-stat-label {
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
        }
        .classio-practice-stat-value {
            margin-top: 0.22rem;
            font-size: 1rem;
            font-weight: 800;
            color: var(--text);
        }
        .classio-practice-action-label {
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin: 0.2rem 0 0.55rem 0.1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Browse & start ──────────────────────────────────────────────

def _render_browse_tab():
    st.caption(t("choose_practice_source"))

    # Supported worksheet types for interactive practice
    _PRACTICE_WS_TYPES = {
        "multiple_choice", "true_false", "fill_in_the_blanks",
        "short_answer", "matching", "reading_comprehension", "error_correction",
        "word_search_vocab",
    }

    # Use the same subject / level / stage lists as teacher pages
    from helpers.lesson_planner import (
        QUICK_SUBJECTS, LEARNER_STAGES, LANGUAGE_LEVELS, ACADEMIC_BANDS,
        subject_label as _subject_label, get_level_options,
    )

    _sp_options = ["__all__"] + QUICK_SUBJECTS

    def _format_subject(x):
        if x == "__all__":
            return t("all_subjects")
        return _subject_label(x)

    # ── Subject / Level / Stage filters (above tabs) ─────────────
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        sp_subject = st.selectbox(
            t("filter_by_subject"),
            options=_sp_options,
            format_func=_format_subject,
            key="sp_filter_subject",
        )

    # "Other" → text input for custom subject name
    sp_other_subject = ""
    if sp_subject == "other":
        sp_other_subject = st.text_input(
            t("other_subject_label"),
            key="sp_other_subject",
        ).strip()

    # Level options depend on subject (CEFR for languages, academic bands for others)
    if sp_subject in ("__all__", "other"):
        _all_levels = sorted(set(LANGUAGE_LEVELS + ACADEMIC_BANDS), key=lambda x: (LANGUAGE_LEVELS + ACADEMIC_BANDS).index(x))
    else:
        _all_levels = get_level_options(sp_subject)

    def _format_level(x):
        if x == "__all__":
            return t("all_levels")
        translated = t(x)
        return translated if translated != x else x

    with f_col2:
        sp_level = st.selectbox(
            t("level_cefr"),
            options=["__all__"] + _all_levels,
            format_func=_format_level,
            key="sp_filter_level",
        )

    _stage_options = ["__all__"] + LEARNER_STAGES

    with f_col3:
        sp_stage = st.selectbox(
            t("learner_stage"),
            options=_stage_options,
            format_func=lambda x: t("all_stages") if x == "__all__" else t(x),
            key="sp_filter_stage",
        )

    # Resolve effective subject for filtering
    _effective_subject = sp_other_subject if sp_subject == "other" else sp_subject

    # ── Pre-load data ────────────────────────────────────────────
    from helpers.worksheet_storage import load_public_worksheets
    from helpers.quick_exam_storage import load_public_exams
    pub_ws = load_public_worksheets()
    pub_ex = load_public_exams()

    if not pub_ws.empty and "worksheet_type" in pub_ws.columns:
        pub_ws = pub_ws[pub_ws["worksheet_type"].isin(_PRACTICE_WS_TYPES)].reset_index(drop=True)

    # Hide worksheets/exams already completed by this student
    _done = get_completed_source_ids()
    if not pub_ws.empty and _done["worksheet"] and "id" in pub_ws.columns:
        pub_ws = pub_ws[~pub_ws["id"].isin(_done["worksheet"])].reset_index(drop=True)
    if not pub_ex.empty and _done["exam"] and "id" in pub_ex.columns:
        pub_ex = pub_ex[~pub_ex["id"].isin(_done["exam"])].reset_index(drop=True)

    src_tab_ws, src_tab_exam = st.tabs([
        f"📋 {t('community_worksheets')}",
        f"📄 {t('community_exams')}",
    ])

    with src_tab_ws:
        # Apply subject/level/stage filters
        if not pub_ws.empty and _effective_subject and _effective_subject != "__all__" and "subject" in pub_ws.columns:
            pub_ws = pub_ws[pub_ws["subject"].str.lower() == _effective_subject.lower()].reset_index(drop=True)
        if not pub_ws.empty and sp_level != "__all__" and "level_or_band" in pub_ws.columns:
            pub_ws = pub_ws[pub_ws["level_or_band"] == sp_level].reset_index(drop=True)
        if not pub_ws.empty and sp_stage != "__all__" and "learner_stage" in pub_ws.columns:
            pub_ws = pub_ws[pub_ws["learner_stage"] == sp_stage].reset_index(drop=True)
        if pub_ws.empty:
            st.info(t("community_library_empty"))
        else:
            ws_q = st.text_input(
                t("explore_resource_search"),
                key="sp_ws_search",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip().lower()

            # ── Neon category filter cards ───────────────────────
            _CATEGORY_CARDS = [
                ("__all__",                  "🎯", t("all"),                    "59,130,246"),   # blue
                ("multiple_choice",          "🔘", t("multiple_choice"),        "168,85,247"),   # purple
                ("true_false",               "✅", t("true_false"),             "16,185,129"),   # green
                ("fill_in_the_blanks",       "✏️", t("fill_in_the_blanks"),    "245,158,11"),   # amber
                ("short_answer",             "📝", t("short_answer"),           "239,68,68"),    # red
                ("matching",                 "🔗", t("matching"),               "6,182,212"),    # cyan
                ("reading_comprehension",    "📖", t("reading_comprehension"),  "234,179,8"),    # gold
                ("error_correction",         "🔍", t("error_correction"),       "20,184,166"),   # teal
                ("word_search_vocab",        "🔠", t("word_search_vocab"),      "99,102,241"),   # indigo
            ]

            active_cat = st.session_state.get("sp_filter_ws_type")

            import html as _html_cat

            # Pre-filter worksheets once
            _ws_base = pub_ws.copy()
            if ws_q and not _ws_base.empty:
                from helpers.goal_explorer import _rank_search
                _ws_base = _rank_search(_ws_base, ws_q, weights={
                    "title": 5, "topic": 4, "subject": 3,
                    "worksheet_type": 3, "learner_stage": 2,
                    "level_or_band": 2, "author_name": 1,
                })
            else:
                _ws_base = _ws_base.head(24)

            if ws_q:
                st.caption(t("search_results"))
                ws_search_rows = _ws_base.reset_index(drop=True).to_dict("records")
                ws_search_page_rows, *_ = _slice_practice_page(ws_search_rows, "student_practice_ws_search_page")
                if not ws_search_page_rows:
                    st.info(t("no_data"))
                else:
                    for idx in range(0, len(ws_search_page_rows), 2):
                        pair = ws_search_page_rows[idx:idx + 2]
                        _ws_cols = st.columns(2, gap="medium")
                        for col_i, row in enumerate(pair):
                            with _ws_cols[col_i]:
                                _render_practice_card(
                                    title=str(row.get("title") or t("untitled_worksheet")),
                                    subject=str(row.get("subject") or ""),
                                    topic=str(row.get("topic") or ""),
                                    level=str(row.get("level_or_band") or ""),
                                    ws_type=str(row.get("worksheet_type") or ""),
                                    btn_key=f"sp_ws_search_{row.get('id', idx)}_{idx}_{col_i}",
                                    color="#A78BFA",
                                )
                                if st.session_state.pop(f"_start_sp_ws_search_{row.get('id', idx)}_{idx}_{col_i}", False):
                                    ws_json = row.get("worksheet_json") or {}
                                    if isinstance(ws_json, str):
                                        try:
                                            ws_json = json.loads(ws_json)
                                        except Exception:
                                            ws_json = {}
                                    if ws_json:
                                        from helpers.worksheet_builder import normalize_worksheet_output
                                        ws_json = normalize_worksheet_output(ws_json)
                                        ex_data = worksheet_to_exercises(ws_json, row_id=row.get("id"))
                                        if _open_practice_item(ex_data, {
                                            "subject": row.get("subject", ""),
                                            "topic": row.get("topic", ""),
                                            "learner_stage": row.get("learner_stage", ""),
                                            "level": row.get("level_or_band", ""),
                                        }):
                                            st.rerun()
                    _render_practice_pagination(ws_search_rows, "student_practice_ws_search_page")
                return

            # Expander-like behaviour:
            # - No category open → show all category cards in a 2-col grid
            # - Category open → show only that card + its worksheets below
            if active_cat is not None:
                # ── Expanded: show active category + worksheets ──
                _active_info = next(
                    (c for c in _CATEGORY_CARDS if c[0] == active_cat),
                    _CATEGORY_CARDS[0],
                )
                cat_key, emoji, label, rgb = _active_info
                glow = f"rgba({rgb},0.55)"
                shadow = (
                    f"box-shadow: 0 4px 18px {glow}, "
                    f"0 0 10px {glow}, "
                    f"0 0 22px rgba({rgb},0.22);"
                )
                st.markdown(
                    f'<div style="'
                    f'background: linear-gradient(180deg, rgba({rgb},0.10), rgba({rgb},0.04)); '
                    f'border: 2.5px solid rgba(234,179,8,0.85); border-radius:16px; '
                    f'padding:12px 10px 8px 10px; text-align:center; '
                    f'min-height:70px; color:var(--text); margin-bottom:2px; {shadow}">'
                    f'<div style="font-size:1.3rem;margin-bottom:2px;">{emoji}</div>'
                    f'<div style="font-weight:700;font-size:0.82rem;color:var(--text,#0f172a);">'
                    f'{_html_cat.escape(label)}</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"✦ {t('close')}",
                    key=f"sp_cat_{cat_key}",
                    use_container_width=True,
                ):
                    st.session_state["sp_filter_ws_type"] = None
                    st.rerun()

                st.markdown("---")

                # Show worksheets for this category
                _ws_cat = _ws_base.copy()
                if active_cat != "__all__" and not _ws_cat.empty and "worksheet_type" in _ws_cat.columns:
                    _ws_cat = _ws_cat[_ws_cat["worksheet_type"] == active_cat].reset_index(drop=True)

                if _ws_cat.empty:
                    st.info(t("no_data"))
                else:
                    _ws_rows = _ws_cat.reset_index(drop=True).to_dict("records")
                    _ws_page_rows, *_ = _slice_practice_page(_ws_rows, f"student_practice_ws_cat_{active_cat}")
                    for idx in range(0, len(_ws_page_rows), 2):
                        pair = _ws_page_rows[idx:idx + 2]
                        _ws_cols = st.columns(2, gap="medium")
                        for col_i, row in enumerate(pair):
                            with _ws_cols[col_i]:
                                _render_practice_card(
                                    title=str(row.get("title") or t("untitled_worksheet")),
                                    subject=str(row.get("subject") or ""),
                                    topic=str(row.get("topic") or ""),
                                    level=str(row.get("level_or_band") or ""),
                                    ws_type=str(row.get("worksheet_type") or ""),
                                    btn_key=f"sp_ws_{row.get('id', idx)}_{idx}_{col_i}",
                                    color="#A78BFA",
                                )
                                if st.session_state.pop(f"_start_sp_ws_{row.get('id', idx)}_{idx}_{col_i}", False):
                                    ws_json = row.get("worksheet_json") or {}
                                    if isinstance(ws_json, str):
                                        try:
                                            ws_json = json.loads(ws_json)
                                        except Exception:
                                            ws_json = {}
                                    if ws_json:
                                        from helpers.worksheet_builder import normalize_worksheet_output
                                        ws_json = normalize_worksheet_output(ws_json)
                                        ex_data = worksheet_to_exercises(ws_json, row_id=row.get("id"))
                                        if _open_practice_item(ex_data, {
                                            "subject": row.get("subject", ""),
                                            "topic": row.get("topic", ""),
                                            "learner_stage": row.get("learner_stage", ""),
                                            "level": row.get("level_or_band", ""),
                                        }):
                                            st.rerun()
                    _render_practice_pagination(_ws_rows, f"student_practice_ws_cat_{active_cat}")
            else:
                # ── Collapsed: show all category cards in 2-col grid ─
                for row_start in range(0, len(_CATEGORY_CARDS), 2):
                    pair = _CATEGORY_CARDS[row_start:row_start + 2]
                    _cat_cols = st.columns(2, gap="medium")
                    for ci, (cat_key, emoji, label, rgb) in enumerate(pair):
                        with _cat_cols[ci]:
                            glow = f"rgba({rgb},0.55)"
                            shadow = (
                                f"box-shadow: 0 4px 18px {glow}, "
                                f"0 0 10px {glow}, "
                                f"0 0 22px rgba({rgb},0.22);"
                            )
                            st.markdown(
                                f'<div style="'
                                f'background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.92)), '
                                f'var(--panel-2, rgba(248,250,255,0.85))); '
                                f'border: 1px solid var(--border-strong, rgba(17,24,39,0.08)); '
                                f'border-radius:16px; padding:12px 10px 8px 10px; text-align:center; '
                                f'min-height:70px; color:var(--text); margin-bottom:2px; {shadow}">'
                                f'<div style="font-size:1.3rem;margin-bottom:2px;">{emoji}</div>'
                                f'<div style="font-weight:700;font-size:0.82rem;color:var(--text,#0f172a);">'
                                f'{_html_cat.escape(label)}</div></div>',
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                label,
                                key=f"sp_cat_{cat_key}",
                                use_container_width=True,
                            ):
                                st.session_state["sp_filter_ws_type"] = cat_key
                                st.rerun()

    with src_tab_exam:
        # Apply subject/level/stage filters
        if not pub_ex.empty and _effective_subject and _effective_subject != "__all__" and "subject" in pub_ex.columns:
            pub_ex = pub_ex[pub_ex["subject"].str.lower() == _effective_subject.lower()].reset_index(drop=True)
        if not pub_ex.empty and sp_level != "__all__" and "level" in pub_ex.columns:
            pub_ex = pub_ex[pub_ex["level"] == sp_level].reset_index(drop=True)
        if not pub_ex.empty and sp_stage != "__all__" and "learner_stage" in pub_ex.columns:
            pub_ex = pub_ex[pub_ex["learner_stage"] == sp_stage].reset_index(drop=True)
        if pub_ex.empty:
            st.info(t("community_library_empty"))
        else:
            ex_q = st.text_input(
                t("explore_resource_search"),
                key="sp_exam_search",
                placeholder=t("explore_resource_search_placeholder"),
            ).strip().lower()
            filtered = pub_ex.copy()
            if ex_q:
                from helpers.goal_explorer import _rank_search
                filtered = _rank_search(filtered, ex_q, weights={
                    "title": 5, "topic": 4, "subject": 3,
                    "learner_stage": 2, "level": 2, "author_name": 1,
                })
            else:
                filtered = filtered.head(24)

            if filtered.empty:
                st.info(t("no_data"))
            else:
                rows = filtered.reset_index(drop=True).to_dict("records")
                page_rows, *_ = _slice_practice_page(rows, "student_practice_exams_page")
                for idx in range(0, len(page_rows), 2):
                    pair = page_rows[idx:idx + 2]
                    cols = st.columns(2, gap="medium")
                    for col_i, row in enumerate(pair):
                        with cols[col_i]:
                            _render_practice_card(
                                title=str(row.get("title") or t("untitled_plan")),
                                subject=str(row.get("subject") or ""),
                                topic=str(row.get("topic") or ""),
                                level=str(row.get("level") or ""),
                                ws_type=str(row.get("exam_length") or ""),
                                btn_key=f"sp_ex_{row.get('id', idx)}_{idx}_{col_i}",
                                color="#F87171",
                            )
                            if st.session_state.pop(f"_start_sp_ex_{row.get('id', idx)}_{idx}_{col_i}", False):
                                exam_data = row.get("exam_data") or {}
                                answer_key = row.get("answer_key") or {}
                                if isinstance(exam_data, str):
                                    try:
                                        exam_data = json.loads(exam_data)
                                    except Exception:
                                        exam_data = {}
                                if isinstance(answer_key, str):
                                    try:
                                        answer_key = json.loads(answer_key)
                                    except Exception:
                                        answer_key = {}
                                if exam_data:
                                    if isinstance(exam_data, dict):
                                        exam_data.setdefault("subject", row.get("subject", ""))
                                        exam_data.setdefault("topic", row.get("topic", ""))
                                        exam_data.setdefault("learner_stage", row.get("learner_stage", ""))
                                    ex_data = exam_to_exercises(exam_data, answer_key, row_id=row.get("id"))
                                    if _open_practice_item(ex_data, {
                                        "subject": row.get("subject", ""),
                                        "topic": row.get("topic", ""),
                                        "learner_stage": row.get("learner_stage", ""),
                                        "level": row.get("level", ""),
                                    }):
                                        st.rerun()
                _render_practice_pagination(rows, "student_practice_exams_page")


def _render_practice_card(
    title: str, subject: str, topic: str, level: str,
    ws_type: str, btn_key: str, color: str = "#A78BFA",
):
    """Render a compact practice card matching assignment-page styling."""
    import html as _html

    # Derive color family from the accent color
    _COLOR_FAMILIES = {
        "#A78BFA": {"rgb": "167,139,250", "chip_bg": "rgba(167,139,250,0.10)", "chip_border": "rgba(167,139,250,0.18)"},
        "#F87171": {"rgb": "248,113,113", "chip_bg": "rgba(248,113,113,0.10)", "chip_border": "rgba(248,113,113,0.18)"},
        "#60A5FA": {"rgb": "96,165,250",  "chip_bg": "rgba(96,165,250,0.10)",  "chip_border": "rgba(96,165,250,0.18)"},
    }
    family = _COLOR_FAMILIES.get(color, _COLOR_FAMILIES["#A78BFA"])
    rgb = family["rgb"]

    subject_label = t(f"subject_{subject.lower().replace(' ', '_')}") if subject else ""
    level_label = level if level in ("A1", "A2", "B1", "B2", "C1", "C2") else (t(level) if level else "")

    chip_style = (
        f"background:{family['chip_bg']};border:1px solid {family['chip_border']};"
        f"border-radius:999px;padding:3px 8px;font-size:0.72rem;font-weight:700;"
    )
    chips = ""
    if subject_label:
        chips += f'<span style="{chip_style}">📚 {_html.escape(subject_label)}</span> '
    if level_label:
        chips += f'<span style="{chip_style}">🏷️ {_html.escape(level_label)}</span> '
    if ws_type:
        chips += f'<span style="{chip_style}">🧩 {_html.escape(t(ws_type) if t(ws_type) != ws_type else ws_type)}</span>'

    preview = _html.escape((topic or t("no_description_available"))[:120])

    st.markdown(
        f"""<div style="
position: relative;
overflow: hidden;
border-radius: 22px;
padding: 18px 20px;
background:
  radial-gradient(circle at top right, rgba({rgb},.12), transparent 38%),
  linear-gradient(180deg, var(--panel, rgba(255,255,255,0.96)), color-mix(in srgb, var(--panel, rgba(255,255,255,0.96)) 84%, white 16%));
border: 1px solid color-mix(in srgb, var(--border, rgba(17,24,39,0.08)) 76%, rgba({rgb},.28) 24%);
border-left: 5px solid {color};
box-shadow: 0 12px 34px rgba(15,23,42,.08);
margin-bottom: 6px;
min-height: 140px;
color: var(--text);
">
<div style="font-weight:800;font-size:0.95rem;margin-bottom:6px;color:var(--text);">{_html.escape(title)}</div>
<div style="margin-bottom:8px;">{chips}</div>
<div style="font-size:0.82rem;color:var(--muted);">{preview}</div>
</div>""",
        unsafe_allow_html=True,
    )

    if st.button(
        f"▶ {t('start_practice')}",
        key=btn_key,
        use_container_width=True,
    ):
        st.session_state[f"_start_{btn_key}"] = True
        st.rerun()


# ── Active session ──────────────────────────────────────────────

def _render_active_session(exercise_data: dict):
    """Render the interactive practice and handle completion."""
    if st.button(f"← {t('back')}", key="practice_back"):
        autosave_practice_draft_if_needed(
            exercise_data,
            session_key="sp",
            meta=st.session_state.get("practice_meta") or {},
            force=True,
        )
        # Clear all practice-related session state
        for key in list(st.session_state.keys()):
            if key.startswith("_start_sp_") or key.startswith("_practice_") or key.startswith("sp_"):
                del st.session_state[key]
        st.session_state.pop("practice_exercise_data", None)
        st.session_state.pop("practice_meta", None)
        st.session_state.pop("_practice_retry_session_id", None)
        st.session_state.pop("_practice_assignment_id", None)
        st.session_state.pop("_practice_assignment_type", None)
        st.session_state.pop("_practice_resume_session_id", None)
        st.session_state.pop("_practice_resume_answers", None)
        st.session_state.pop("_practice_resume_notice", None)
        st.session_state.pop("_practice_last_autosave_payload_sp", None)
        st.session_state.pop("_practice_last_autosave_at_sp", None)
        st.session_state.pop("_practice_last_autosave_failed_sp", None)
        st.rerun()

    if st.session_state.pop("_practice_resume_notice", False):
        st.info(t("practice_resumed_notice"))

    result = render_practice_session(exercise_data, session_key="sp")

    # When submitted, save results ONCE (guard against duplicate saves on rerender)
    if result and not st.session_state.get("_practice_saved_sp"):
        st.session_state["_practice_saved_sp"] = True

        if str(exercise_data.get("source_type") or "").strip() != "demo":
            # Real exercise: save to DB
            meta = st.session_state.get("practice_meta") or {}
            xp   = result.get("xp_earned", 0)
            strk = result.get("best_streak", 0)

            retry_id = st.session_state.get("_practice_retry_session_id")
            if retry_id:
                update_practice_session(
                    retry_id,
                    exercise_data,
                    total=result["total"],
                    correct=result["correct"],
                    score_pct=result["score_pct"],
                    xp_earned=xp,
                    best_streak=strk,
                )
                session_id = retry_id
            elif st.session_state.get("_practice_resume_session_id"):
                resumed_id = int(st.session_state["_practice_resume_session_id"])
                update_practice_session(
                    resumed_id,
                    exercise_data,
                    total=result["total"],
                    correct=result["correct"],
                    score_pct=result["score_pct"],
                    xp_earned=xp,
                    best_streak=strk,
                )
                session_id = resumed_id
            else:
                session_id = save_practice_session(
                    exercise_data,
                    total=result["total"],
                    correct=result["correct"],
                    score_pct=result["score_pct"],
                    xp_earned=xp,
                    best_streak=strk,
                    meta=meta,
                )
            if session_id:
                st.session_state["_practice_last_session_id"] = session_id
                save_practice_answers(
                    session_id, exercise_data, result["answers"], session_key="sp",
                    replace_existing=bool(retry_id or st.session_state.get("_practice_resume_session_id")),
                )
            assignment_id = st.session_state.get("_practice_assignment_id")
            if assignment_id:
                try:
                    from helpers.teacher_student_integration import record_assignment_attempt_from_practice

                    record_assignment_attempt_from_practice(
                        int(assignment_id),
                        session_id,
                        result,
                        exercise_data,
                    )
                except Exception:
                    pass
            # Always save progress (even if session save failed)
            update_practice_progress(
                exercise_data, result["answers"],
                meta=meta, session_key="sp",
                xp_earned=xp, best_streak=strk,
            )
            st.session_state.pop("_practice_resume_session_id", None)
            st.session_state.pop("_practice_resume_answers", None)

    if result and str(exercise_data.get("source_type") or "").strip() != "demo":
        _render_teacher_review_request_panel(exercise_data)


def _render_teacher_review_request_panel(exercise_data: dict) -> None:
    session_id = st.session_state.get("_practice_last_session_id")
    if not session_id:
        return

    source_type = str(exercise_data.get("source_type") or "").strip()
    if source_type not in {"worksheet", "exam"}:
        return

    meta = st.session_state.get("practice_meta") or {}
    subject_key = str(meta.get("subject") or "").strip()
    links = get_reviewable_teacher_links_for_subject(subject_key)
    requests = load_student_review_requests_for_session(int(session_id))

    st.markdown(
        """
        <div style="
            margin-top:1rem;
            padding:20px 22px;
            border-radius:22px;
            background:
              radial-gradient(circle at top right, rgba(16,185,129,.10), transparent 36%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border:1px solid color-mix(in srgb, var(--border) 78%, rgba(16,185,129,.20) 22%);
            box-shadow:0 14px 32px rgba(15,23,42,.08);
            margin-bottom:0.85rem;
        ">
            <div style="font-size:1.1rem;font-weight:800;color:var(--text);">🧑‍🏫 """
        + t("request_teacher_review")
        + """</div>
            <div style="margin-top:0.35rem;color:var(--muted);font-size:0.92rem;">"""
        + t("teacher_review_note_placeholder")
        + """</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if requests:
        latest = requests[0]
        teacher_name = latest.get("teacher_name") or "—"
        status_key = f"teacher_review_status_{latest.get('status')}"
        st.success(t("teacher_review_requested_with_name", teacher=teacher_name))
        st.caption(f"{t('teacher_review_current_status')}: {t(status_key)}")
        feedback = _clean_teacher_feedback_text(latest.get("teacher_feedback"))
        if feedback:
            st.info(f"{t('teacher_review_feedback')}: {feedback}")
        return

    if not links:
        st.info(t("teacher_review_not_connected"))
        if st.button(t("teacher_review_find_teacher"), key=f"find_teacher_review_{session_id}", type="primary"):
            go_to("student_find_teacher")
            st.rerun()
        return

    selected_teacher_idx = st.selectbox(
        t("teacher_review_select_teacher"),
        options=list(range(len(links))),
        format_func=lambda idx: f"{links[idx].get('teacher_name', '—')} · {', '.join(s.get('subject_label', '') for s in links[idx].get('active_subjects', []) if s.get('subject_label'))}",
        key=f"teacher_review_teacher_{session_id}",
    )
    review_note = st.text_area(
        t("teacher_review_note"),
        key=f"teacher_review_note_{session_id}",
        height=90,
        placeholder=t("teacher_review_note_placeholder"),
    )
    if st.button(t("request_teacher_review"), key=f"teacher_review_request_btn_{session_id}", use_container_width=True, type="primary"):
        selected = links[selected_teacher_idx]
        ok, msg = create_teacher_review_request(
            practice_session_id=int(session_id),
            teacher_id=str(selected.get("teacher_id") or ""),
            assignment_id=st.session_state.get("_practice_assignment_id"),
            request_note=review_note,
        )
        if ok:
            st.success(t(msg))
            st.rerun()
        st.error(t(msg))


# ── History tab ─────────────────────────────────────────────────

def _render_history_tab():
    history = load_practice_history()
    if history.empty:
        st.info(t("no_practice_history"))
        return

    history_rows = history.reset_index(drop=True).to_dict("records")
    history_page_rows, *_ = _slice_practice_page(history_rows, "student_practice_history_page")

    assignment_ids = []
    for row in history_page_rows:
        source_type = str(row.get("source_type") or "").strip()
        source_id = int(row.get("source_id") or 0)
        if source_type in {"worksheet", "exam"} and source_id > 0:
            assignment_ids.append(source_id)
    assignment_state_map = load_assignment_state_map(assignment_ids)

    for h_idx, row in enumerate(history_page_rows):
        title   = str(row.get("title") or t("smart_practice"))
        score   = row.get("score_pct", 0)
        total   = row.get("total_questions", 0)
        correct = row.get("correct_count", 0)
        xp      = row.get("xp_earned", 0)
        streak  = row.get("best_streak", 0)
        created = str(row.get("created_at") or "")[:16]
        session_id = row.get("id")
        subject = str(row.get("subject") or "").strip()
        topic = str(row.get("topic") or "").strip()
        assignment_state = assignment_state_map.get(int(row.get("source_id") or 0), {})
        assignment_removed = str(assignment_state.get("status") or "").strip() == "archived"
        source_archived = bool(assignment_state.get("source_archived"))

        source_type = str(row.get("source_type") or "").strip()
        if source_type == "exam":
            card_accent = "#F87171"
        elif source_type == "worksheet":
            card_accent = "#A78BFA"
        else:
            card_accent = "#60A5FA"

        if score >= 80:
            color = "#10B981"
        elif score >= 60:
            color = "#F59E0B"
        else:
            color = "#EF4444"
        subject_label = t(f"subject_{subject.lower().replace(' ', '_')}") if subject else ""
        if subject_label == f"subject_{subject.lower().replace(' ', '_')}":
            subject_label = subject

        left_col, right_col = st.columns([6, 2], gap="medium")
        with left_col:
            meta_bits = [bit for bit in [subject_label, topic, created] if bit]
            stat_blocks = [
                (
                    f"<div class='classio-practice-stat'>"
                    f"<div class='classio-practice-stat-label'>{t('correct')}</div>"
                    f"<div class='classio-practice-stat-value'>{correct}/{total}</div>"
                    f"</div>"
                )
            ]
            if streak >= 2:
                stat_blocks.append(
                    f"<div class='classio-practice-stat'><div class='classio-practice-stat-label'>{t('best_streak')}</div>"
                    f"<div class='classio-practice-stat-value'>🔥 {streak}</div></div>"
                )
            if xp:
                stat_blocks.append(
                    f"<div class='classio-practice-stat'><div class='classio-practice-stat-label'>XP</div>"
                    f"<div class='classio-practice-stat-value'>+{xp}</div></div>"
                )
            st.markdown(
                f"""
                <div class="classio-practice-card" style="border-left:5px solid {card_accent};">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                        <div>
                            <div class="classio-practice-title">{_escape_html(title)}</div>
                            <div class="classio-practice-meta">{_escape_html(' · '.join(meta_bits))}</div>
                        </div>
                        <div style="font-size:1.05rem;font-weight:800;color:{color};background:{color}15;padding:8px 14px;border-radius:999px;border:1px solid {color}33;">
                            {round(score)}%
                        </div>
                    </div>
                    <div class="classio-practice-statgrid">
                        {''.join(stat_blocks)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Try Again button — reload the exercise data from the saved session
        exercise_data = row.get("exercise_data")
        with right_col:
            if assignment_removed or source_archived:
                if st.button(
                    t("archived_label"),
                    key=f"hist_archived_{session_id}_{h_idx}",
                    use_container_width=True,
                ):
                    st.info(t("assignment_source_archived_notice"))
            elif exercise_data:
                if isinstance(exercise_data, str):
                    try:
                        exercise_data = json.loads(exercise_data)
                    except Exception:
                        exercise_data = None
                if exercise_data and st.button(
                    t("try_again"),
                    key=f"hist_retry_{session_id}_{h_idx}",
                    use_container_width=True,
                    type="primary",
                ):
                    if _open_practice_item(exercise_data, {
                        "subject": str(row.get("subject") or ""),
                        "topic": str(row.get("topic") or ""),
                        "learner_stage": str(row.get("learner_stage") or ""),
                        "level": str(row.get("level") or ""),
                    }):
                        st.session_state["_practice_retry_session_id"] = session_id
                        st.rerun()
        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    _render_practice_pagination(history_rows, "student_practice_history_page")


# ── Progress tab ────────────────────────────────────────────────

def _render_progress_tab():
    progress = load_practice_progress()
    if progress.empty:
        st.info(t("no_practice_progress"))
        return

    subject_options = ["__all__"]
    if "subject" in progress.columns:
        for subject in sorted({str(s).strip() for s in progress["subject"].fillna("").tolist() if str(s).strip()}):
            subject_options.append(subject)

    selected_subject = st.selectbox(
        t("filter_by_subject"),
        options=subject_options,
        format_func=lambda value: (
            t("all_subjects")
            if value == "__all__"
            else (
                translated if (translated := t(f"subject_{str(value).lower().replace(' ', '_')}")) != f"subject_{str(value).lower().replace(' ', '_')}" else str(value)
            )
        ),
        key="student_progress_subject_filter",
    )

    if selected_subject != "__all__" and "subject" in progress.columns:
        progress = progress[progress["subject"].fillna("").astype(str).str.strip().str.lower() == selected_subject.lower()].reset_index(drop=True)
        if progress.empty:
            st.info(t("no_data"))
            return

    # ── Aggregate XP + rank banner ──────────────────────────────
    total_xp = int(progress["total_xp"].sum()) if "total_xp" in progress.columns else 0
    total_attempted = int(progress["total_attempted"].sum()) if "total_attempted" in progress.columns else 0
    total_correct   = int(progress["total_correct"].sum()) if "total_correct" in progress.columns else 0
    overall_pct     = round(total_correct / total_attempted * 100) if total_attempted else 0

    st.markdown(
        f"""
        <div style="
            display:flex; gap:12px; margin-bottom:14px; flex-wrap:wrap;
        ">
            <div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--border);">
                <div style="font-size:1.3rem;font-weight:800;color:#8B5CF6;">{total_xp}</div>
                <div style="font-size:0.72rem;color:var(--muted);">{t('total_xp')}</div>
            </div>
            <div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--border);">
                <div style="font-size:1.3rem;font-weight:800;color:#10B981;">{overall_pct}%</div>
                <div style="font-size:0.72rem;color:var(--muted);">{t('overall_accuracy')}</div>
            </div>
            <div style="flex:1;min-width:100px;text-align:center;padding:12px;border-radius:12px;background:var(--panel);border:1px solid var(--border);">
                <div style="font-size:1.3rem;font-weight:800;">{total_attempted}</div>
                <div style="font-size:0.72rem;color:var(--muted);">{t('questions_attempted')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Per-topic breakdown ─────────────────────────────────────
    progress_rows = progress.reset_index(drop=True).to_dict("records")
    progress_page_rows, *_ = _slice_practice_page(progress_rows, "student_practice_progress_page")

    for row in progress_page_rows:
        subject  = str(row.get("subject") or "").strip()
        topic    = str(row.get("topic") or "").strip()
        ex_type  = str(row.get("exercise_type") or "").strip()
        accuracy = row.get("accuracy_pct", 0)
        attempted = row.get("total_attempted", 0)
        row_xp   = row.get("total_xp", 0)

        label = " · ".join(filter(None, [
            t(f"subject_{subject.lower().replace(' ', '_')}") if subject else "",
            topic,
            t(ex_type) if t(ex_type) != ex_type else ex_type,
        ]))

        if accuracy >= 80:
            bar_color = "#10B981"
        elif accuracy >= 60:
            bar_color = "#F59E0B"
        else:
            bar_color = "#EF4444"

        st.markdown(
            f"""
            <div class="classio-practice-card" style="margin-bottom:0.75rem;border-left:5px solid {bar_color};">
                <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                    <div>
                        <div class="classio-practice-title">{_escape_html(label)}</div>
                        <div class="classio-practice-meta">{attempted} {t('questions_attempted')}</div>
                    </div>
                    <div style="font-size:1.05rem;font-weight:800;color:{bar_color};background:{bar_color}15;padding:8px 14px;border-radius:999px;border:1px solid {bar_color}33;">
                        {round(accuracy)}%
                    </div>
                </div>
                <div style="background:var(--border);border-radius:999px;height:10px;overflow:hidden;margin-top:0.95rem;">
                    <div style="width:{min(accuracy, 100)}%;height:100%;background:{bar_color};border-radius:999px;"></div>
                </div>
                <div class="classio-practice-statgrid">
                    <div class="classio-practice-stat">
                        <div class="classio-practice-stat-label">{t('score_label')}</div>
                        <div class="classio-practice-stat-value">{round(accuracy)}%</div>
                    </div>
                    <div class="classio-practice-stat">
                        <div class="classio-practice-stat-label">{t('questions_attempted')}</div>
                        <div class="classio-practice-stat-value">{attempted}</div>
                    </div>
                    <div class="classio-practice-stat">
                        <div class="classio-practice-stat-label">XP</div>
                        <div class="classio-practice-stat-value">{row_xp}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    _render_practice_pagination(progress_rows, "student_practice_progress_page")


def _escape_html(value: str) -> str:
    import html as _html
    return _html.escape(str(value or ""))
