import streamlit as st
import json
from datetime import datetime, timezone, timedelta
from core.i18n import t
from core.state import get_current_user_id
from helpers.practice_engine import (
    worksheet_to_exercises,
    exam_to_exercises,
    render_practice_session,
    save_practice_session,
    save_practice_answers,
    update_practice_progress,
    update_practice_session,
    load_practice_history,
    load_practice_progress,
    get_completed_source_ids,
    get_total_xp,
    get_global_best_streak,
    get_rank,
    calculate_session_xp,
)

_DEMO_LINGER_HOURS = 24


# ── Demo progress helpers ───────────────────────────────────────

def _demo_done_key() -> str:
    uid = str(get_current_user_id() or "").strip()
    return f"demo_completed_ids::{uid}" if uid else "demo_completed_ids::anon"


def _demo_done_ts_key() -> str:
    uid = str(get_current_user_id() or "").strip()
    return f"demo_all_done_ts::{uid}" if uid else "demo_all_done_ts::anon"


def _get_demo_completed_ids() -> set:
    return set(st.session_state.get(_demo_done_key(), []))


def _mark_demo_completed(demo_id: str) -> None:
    key = _demo_done_key()
    done = set(st.session_state.get(key, []))
    done.add(demo_id)
    st.session_state[key] = list(done)


def _all_demos_done() -> bool:
    from helpers.practice_test_data import DEMO_IDS
    return _get_demo_completed_ids() >= set(DEMO_IDS)


def _mark_demos_all_done() -> None:
    key = _demo_done_ts_key()
    if key not in st.session_state:
        st.session_state[key] = datetime.now(timezone.utc).isoformat()


def _demo_section_expired() -> bool:
    ts_str = st.session_state.get(_demo_done_ts_key())
    if not ts_str:
        return False
    try:
        done_at = datetime.fromisoformat(ts_str)
        return datetime.now(timezone.utc) - done_at > timedelta(hours=_DEMO_LINGER_HOURS)
    except Exception:
        return False


def _should_show_demo() -> bool:
    """Show demo section until all 3 are done AND 24h have passed."""
    if _all_demos_done():
        _mark_demos_all_done()
        return not _demo_section_expired()
    return True


def _open_practice_item(exercise_data: dict, meta: dict | None = None, *, demo_id: str | None = None) -> bool:
    """Open a practice item only if it contains runnable exercises."""
    exercises = (exercise_data or {}).get("exercises") or []
    if not exercises:
        st.warning(t("no_exercises_available"))
        return False

    st.session_state["practice_exercise_data"] = exercise_data
    st.session_state["practice_meta"] = meta or {}
    if demo_id:
        st.session_state["_practice_demo_id"] = demo_id
    else:
        st.session_state.pop("_practice_demo_id", None)
    return True


def render_student_practice():
    st.markdown(f"## 🧠 {t('smart_practice')}")

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


# ── Browse & start ──────────────────────────────────────────────

def _render_browse_tab():
    st.caption(t("choose_practice_source"))

    # ── Demo section with medals & progress ───────────────────────
    if _should_show_demo():
        _render_demo_section()

    # Supported worksheet types for interactive practice
    _PRACTICE_WS_TYPES = {
        "multiple_choice", "true_false", "fill_in_the_blanks",
        "short_answer", "matching", "reading_comprehension", "error_correction",
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
                _ws_base = _ws_base.head(12)

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
                    _ws_rows = _ws_cat.head(8).reset_index(drop=True).to_dict("records")
                    for idx in range(0, len(_ws_rows), 2):
                        pair = _ws_rows[idx:idx + 2]
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
                filtered = filtered.head(8)

            if filtered.empty:
                st.info(t("no_data"))
            else:
                rows = filtered.reset_index(drop=True).to_dict("records")
                for idx in range(0, len(rows), 2):
                    pair = rows[idx:idx + 2]
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
                                color="#A78BFA",
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
                                    ex_data = exam_to_exercises(exam_data, answer_key, row_id=row.get("id"))
                                    if _open_practice_item(ex_data, {
                                        "subject": row.get("subject", ""),
                                        "topic": row.get("topic", ""),
                                        "learner_stage": row.get("learner_stage", ""),
                                        "level": row.get("level", ""),
                                    }):
                                        st.rerun()


# ── Demo section with medals ────────────────────────────────────

def _render_demo_section():
    """Render demo exercises with progress bar and medals (like welcome page)."""
    from helpers.practice_test_data import get_demo_activities, DEMO_IDS
    import html as _html

    demos = get_demo_activities()
    completed = _get_demo_completed_ids()
    done_count = sum(1 for d in demos if d["id"] in completed)
    total = len(demos)
    all_done = done_count == total
    pct = int(done_count / total * 100) if total else 0

    if pct == 0:
        progress_text = t("demo_progress_start")
    elif pct < 100:
        progress_text = t("demo_progress_almost")
    else:
        progress_text = t("demo_progress_done")

    # Build medal chips HTML
    medal_html = ""
    for d in demos:
        is_done = d["id"] in completed
        icon = "🏅" if is_done else d["emoji"]
        label = _html.escape(d["label"])
        medal_html += f'<span style="margin-right:12px;">{"🏅" if is_done else icon} {label}</span>'

    with st.expander(f"🧪 {t('try_demo')}", expanded=not all_done):
        # Progress bar & medals
        st.markdown(
            f"""<div style="
padding:12px 16px; border-radius:14px;
background:var(--panel); border:1px solid var(--border);
margin-bottom:12px;
">
<div style="font-weight:700;margin-bottom:8px;color:var(--text);">
🚀 {t('demo_progress')}
</div>
<div style="
width:100%;background:var(--panel-2, rgba(148,163,184,0.15));
border-radius:14px;overflow:hidden;height:14px;margin-bottom:8px;
border:1px solid var(--border-strong, rgba(148,163,184,0.25));
">
<div style="
width:{pct}%;height:14px;
background:linear-gradient(90deg,#8B5CF6,#6D28D9);
box-shadow:0 0 10px rgba(139,92,246,0.5);
transition:width 0.4s ease;
"></div>
</div>
<div style="font-size:0.85rem;color:var(--muted);font-weight:600;">
{pct}% — {progress_text}
</div>
<div style="
display:flex;gap:14px;font-size:0.85rem;color:var(--muted);
padding:10px 0 4px;flex-wrap:wrap;
">
{medal_html}
</div>
</div>""",
            unsafe_allow_html=True,
        )

        if all_done:
            st.success(t("demo_all_complete"))
        else:
            # Render demo buttons
            demo_cols = st.columns(total, gap="small")
            for i, demo in enumerate(demos):
                with demo_cols[i]:
                    is_done = demo["id"] in completed
                    btn_label = f"🏅 {demo['label']}" if is_done else f"▶ {demo['label']}"
                    if st.button(
                        btn_label,
                        key=f"demo_{i}",
                        use_container_width=True,
                        disabled=is_done,
                    ):
                        if _open_practice_item(
                            demo["exercise_data"],
                            demo.get("meta", {}),
                            demo_id=demo["id"],
                        ):
                            st.rerun()


def _render_practice_card(
    title: str, subject: str, topic: str, level: str,
    ws_type: str, btn_key: str, color: str = "#A78BFA",
):
    """Render a compact practice card matching teacher-page styling."""
    import html as _html

    subject_label = t(f"subject_{subject.lower().replace(' ', '_')}") if subject else ""
    level_label = level if level in ("A1", "A2", "B1", "B2", "C1", "C2") else (t(level) if level else "")

    chip_style = (
        f"background:rgba(167,139,250,0.10);border:1px solid rgba(167,139,250,0.18);"
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
border-radius: 20px;
padding: 16px;
background: linear-gradient(180deg, var(--panel, rgba(255,255,255,0.96)), var(--panel-2, rgba(248,250,255,0.92)));
border: 1px solid var(--border-strong, rgba(17,24,39,0.08));
border-left: 5px solid {color};
box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06));
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
    is_demo = exercise_data.get("source_type") == "demo"

    if st.button(f"← {t('back')}", key="practice_back"):
        # Clear all practice-related session state
        for key in list(st.session_state.keys()):
            if key.startswith("_start_sp_") or key.startswith("_practice_"):
                del st.session_state[key]
        st.session_state.pop("practice_exercise_data", None)
        st.session_state.pop("practice_meta", None)
        st.session_state.pop("_practice_retry_session_id", None)
        st.rerun()

    result = render_practice_session(exercise_data, session_key="sp")

    # When submitted, save results ONCE (guard against duplicate saves on rerender)
    if result and not st.session_state.get("_practice_saved_sp"):
        st.session_state["_practice_saved_sp"] = True

        if is_demo:
            # Demo: mark medal earned (no DB save)
            demo_id = st.session_state.get("_practice_demo_id")
            if demo_id:
                _mark_demo_completed(demo_id)
        else:
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
                save_practice_answers(
                    session_id, exercise_data, result["answers"], session_key="sp",
                )
            # Always save progress (even if session save failed)
            update_practice_progress(
                exercise_data, result["answers"],
                meta=meta, session_key="sp",
                xp_earned=xp, best_streak=strk,
            )


# ── History tab ─────────────────────────────────────────────────

def _render_history_tab():
    history = load_practice_history()
    if history.empty:
        st.info(t("no_practice_history"))
        return

    for h_idx, row in history.iterrows():
        title   = str(row.get("title") or t("smart_practice"))
        score   = row.get("score_pct", 0)
        total   = row.get("total_questions", 0)
        correct = row.get("correct_count", 0)
        xp      = row.get("xp_earned", 0)
        streak  = row.get("best_streak", 0)
        created = str(row.get("created_at") or "")[:16]
        session_id = row.get("id")

        if score >= 80:
            color = "#10B981"
        elif score >= 60:
            color = "#F59E0B"
        else:
            color = "#EF4444"

        xp_badge = f'<span style="background:linear-gradient(135deg,#8B5CF6,#6D28D9);color:#fff;font-size:0.7rem;font-weight:700;padding:2px 8px;border-radius:10px;margin-left:6px;">+{xp} XP</span>' if xp else ""
        streak_txt = f" · 🔥{streak}" if streak >= 2 else ""

        st.markdown(
            f"""<div style="
display:flex; justify-content:space-between; align-items:center;
padding:12px 16px; border-radius:12px;
background:var(--panel); border:1px solid var(--border);
border-left: 5px solid #A78BFA;
margin-bottom:4px;
">
<div>
<div style="font-weight:700;font-size:0.92rem;">{title}{xp_badge}</div>
<div style="font-size:0.78rem;color:var(--muted);">{created} · {correct}/{total}{streak_txt}</div>
</div>
<div style="
font-size:1.1rem; font-weight:800; color:{color};
background:{color}15; padding:6px 14px; border-radius:10px;
">{round(score)}%</div>
</div>""",
            unsafe_allow_html=True,
        )

        # Try Again button — reload the exercise data from the saved session
        exercise_data = row.get("exercise_data")
        if exercise_data:
            if isinstance(exercise_data, str):
                try:
                    exercise_data = json.loads(exercise_data)
                except Exception:
                    exercise_data = None
            if exercise_data and st.button(
                f"🔄 {t('try_again')}",
                key=f"hist_retry_{session_id}_{h_idx}",
                use_container_width=True,
            ):
                if _open_practice_item(exercise_data, {
                    "subject": str(row.get("subject") or ""),
                    "topic": str(row.get("topic") or ""),
                    "learner_stage": str(row.get("learner_stage") or ""),
                    "level": str(row.get("level") or ""),
                }):
                    st.session_state["_practice_retry_session_id"] = session_id
                    st.rerun()


# ── Progress tab ────────────────────────────────────────────────

def _render_progress_tab():
    progress = load_practice_progress()
    if progress.empty:
        st.info(t("no_practice_progress"))
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
    for _, row in progress.iterrows():
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

        xp_chip = f'<span style="background:#8B5CF620;color:#8B5CF6;font-size:0.68rem;font-weight:700;padding:1px 6px;border-radius:8px;margin-left:6px;">{row_xp} XP</span>' if row_xp else ""

        st.markdown(
            f"""
            <div style="
                padding:10px 14px; border-radius:12px;
                background:var(--panel); border:1px solid var(--border);
                margin-bottom:6px;
            ">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                    <span style="font-weight:700;font-size:0.88rem;">{label}{xp_chip}</span>
                    <span style="font-weight:800;color:{bar_color};font-size:0.88rem;">{round(accuracy)}%</span>
                </div>
                <div style="background:var(--border);border-radius:6px;height:8px;overflow:hidden;">
                    <div style="width:{min(accuracy, 100)}%;height:100%;background:{bar_color};border-radius:6px;"></div>
                </div>
                <div style="font-size:0.72rem;color:var(--muted);margin-top:4px;">{attempted} {t('questions_attempted')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
