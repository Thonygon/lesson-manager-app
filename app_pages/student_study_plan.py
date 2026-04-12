from datetime import date

import streamlit as st

from core.database import load_profile_row
from core.i18n import t
from core.navigation import go_to
from core.state import get_current_user_id
from core.timezone import today_local
from app_pages.student_assignments import _inject_assignment_page_styles, render_assigned_learning_programs_section
from helpers.lesson_planner import QUICK_SUBJECTS, normalize_subject, subject_label as _subject_label
from helpers.learning_programs import load_enriched_program_assignments_for_current_student
from helpers.teacher_student_integration import get_student_assignment_summary, has_active_teacher_relationships


_SMART_PLAN_NS = "student_smart_plan"


def _smart_plan_user_key(suffix: str) -> str:
    uid = str(get_current_user_id() or "").strip() or "anon"
    return f"{_SMART_PLAN_NS}_{suffix}_{uid}"


def _inject_smart_plan_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-smart-teacher-grid {
            margin-top: 0.45rem;
        }
        .classio-smart-teacher-card {
            height: 100%;
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at top right, rgba(59,130,246,.08), transparent 40%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 86%, white 14%));
            border: 1px solid color-mix(in srgb, var(--border) 78%, rgba(59,130,246,.22) 22%);
            border-radius: 22px;
            padding: 18px 18px 16px;
            box-shadow: 0 12px 30px rgba(15,23,42,.08);
        }
        .classio-smart-teacher-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, #38bdf8, #6366f1 55%, #14b8a6);
        }
        .classio-smart-teacher-name {
            font-size: 0.82rem;
            color: var(--muted);
            font-weight: 800;
        }
        .classio-smart-teacher-title {
            margin-top: 0.5rem;
            font-size: 1rem;
            line-height: 1.45;
            font-weight: 800;
            color: var(--text);
        }
        .classio-smart-teacher-subject {
            margin-top: 0.55rem;
            color: var(--muted);
            font-size: 0.88rem;
            font-weight: 700;
        }
        .classio-smart-teacher-meta {
            margin-top: 0.95rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
        }
        .classio-smart-status-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.38rem 0.72rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 800;
            border: 1px solid rgba(148,163,184,.18);
            background: rgba(148,163,184,.08);
            color: var(--text);
        }
        .classio-smart-secondary-pill {
            display: inline-flex;
            align-items: center;
            padding: 0.38rem 0.72rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            color: var(--muted);
            background: rgba(148,163,184,.08);
            border: 1px solid rgba(148,163,184,.14);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _smart_plan_subject_options() -> list[str]:
    return QUICK_SUBJECTS


def _smart_plan_goal_options() -> list[str]:
    return _all_smart_plan_goals()


def _smart_plan_goal_groups() -> dict[str, list[str]]:
    return {
        "language": [
            "improve_vocabulary",
            "improve_reading",
            "improve_grammar",
            "improve_speaking",
            "review_mistakes",
            "exam_preparation",
            "homework_support",
            "general_practice",
        ],
        "math": [
            "mental_math_fluency",
            "problem_solving",
            "equation_confidence",
            "review_mistakes",
            "exam_preparation",
            "homework_support",
            "general_practice",
        ],
        "science": [
            "science_terminology",
            "concept_understanding",
            "classification_skills",
            "review_mistakes",
            "exam_preparation",
            "homework_support",
            "general_practice",
        ],
        "music": [
            "music_terminology",
            "rhythm_practice",
            "theory_review",
            "symbol_identification",
            "review_mistakes",
            "exam_preparation",
            "general_practice",
        ],
        "study_skills": [
            "focus_and_routine",
            "organization_skills",
            "memory_review",
            "reflection_and_planning",
            "homework_support",
            "general_practice",
        ],
    }


def _all_smart_plan_goals() -> list[str]:
    ordered = []
    for group_goals in _smart_plan_goal_groups().values():
        for goal in group_goals:
            if goal not in ordered:
                ordered.append(goal)
    return ordered


def _smart_plan_goal_options_for_subject(subject: str) -> list[str]:
    subject = normalize_subject(subject)
    group_map = {
        "english": "language",
        "spanish": "language",
        "mathematics": "math",
        "science": "science",
        "music": "music",
        "study_skills": "study_skills",
        "other": "all",
    }
    target = group_map.get(subject, "all")
    if target == "all":
        return _all_smart_plan_goals()
    return _smart_plan_goal_groups().get(target, _all_smart_plan_goals())


def _smart_plan_time_options() -> list[int]:
    return [10, 15, 20, 30, 45, 60]


def _smart_plan_focus_label(goal_key: str) -> str:
    return t(f"smart_plan_goal_{goal_key}")


def _smart_plan_time_label(minutes: int) -> str:
    return t("smart_plan_minutes_option", minutes=minutes)


def _safe_ui_label(key: str, fallback: str | None = None) -> str:
    value = t(key)
    if value != key:
        return value
    if fallback:
        fallback_value = t(fallback)
        if fallback_value != fallback:
            return fallback_value
    return key.replace("_", " ").strip().title()


def _default_subject_from_profile() -> str:
    user_id = get_current_user_id()
    profile = load_profile_row(user_id) if user_id else {}
    primary = profile.get("primary_subjects") or []
    if isinstance(primary, list) and primary:
        normalized = normalize_subject(primary[0])
        if normalized in QUICK_SUBJECTS:
            return normalized
    return "english"


def _default_smart_plan_state() -> dict:
    default_subject = _default_subject_from_profile()
    default_goal_options = _smart_plan_goal_options_for_subject(default_subject)
    return {
        "subject": default_subject,
        "goal": default_goal_options[0] if default_goal_options else "general_practice",
        "minutes_per_day": 15,
        "custom_subject": "",
        "generated_for": "",
        "tasks": [],
        "weekly_preview": [],
        "recommendations": [],
        "points": 0,
        "streak": 0,
        "last_completion_date": "",
        "last_active_date": "",
        "setup_complete": False,
        "program_anchor_signature": "",
    }


def _load_smart_plan_state() -> dict:
    key = _smart_plan_user_key("data")
    existing = st.session_state.get(key)
    defaults = _default_smart_plan_state()
    if not isinstance(existing, dict):
        st.session_state[key] = defaults
        return defaults.copy()
    merged = defaults | existing
    st.session_state[key] = merged
    return merged.copy()


def _save_smart_plan_state(state: dict) -> None:
    st.session_state[_smart_plan_user_key("data")] = dict(state)


def _today_iso() -> str:
    return today_local().isoformat()


def _format_day_label(day: date) -> str:
    if day == today_local():
        return t("smart_plan_today_label")
    if day.toordinal() == today_local().toordinal() + 1:
        return t("smart_plan_tomorrow_label")
    return t(f"smart_plan_day_{day.strftime('%a').lower()}")


def _calculate_smart_plan_level(points: int) -> int:
    if points < 100:
        return 1
    if points < 250:
        return 2
    if points < 450:
        return 3
    if points < 700:
        return 4
    return 5 + max(0, (points - 700) // 300)


def _calculate_smart_plan_progress(tasks: list[dict]) -> dict:
    total = len(tasks or [])
    completed = sum(1 for task in (tasks or []) if task.get("done"))
    pct = round((completed / total) * 100) if total else 0
    return {"total": total, "completed": completed, "pct": pct, "all_done": total > 0 and completed == total}


def _smart_plan_anchor_signature(anchor: dict | None) -> str:
    if not anchor:
        return ""
    topic_ids = ",".join(str(item.get("topic_id") or 0) for item in (anchor.get("next_topics") or [])[:5])
    return "|".join(
        [
            str(anchor.get("assignment_id") or 0),
            str(anchor.get("program_id") or 0),
            str(anchor.get("progress_pct") or 0),
            topic_ids,
        ]
    )


def _topic_category(topic: dict) -> str:
    lesson_purpose = str(topic.get("lesson_purpose") or "").strip().lower()
    if "speak" in lesson_purpose or "discussion" in lesson_purpose:
        return "speaking"
    if "read" in lesson_purpose:
        return "reading"
    if "review" in lesson_purpose or "diagnose" in lesson_purpose:
        return "review"
    if topic.get("suggested_exam_exercise_types"):
        return "quiz"
    if topic.get("suggested_worksheet_types"):
        first = str((topic.get("suggested_worksheet_types") or [""])[0]).lower()
        if "read" in first:
            return "reading"
        if "vocab" in first or "word" in first:
            return "vocabulary"
        if "grammar" in first or "fill" in first or "error" in first:
            return "grammar"
    return "practice"


def _build_program_anchor(program_assignments: list[dict]) -> dict | None:
    if not program_assignments:
        return None
    item = program_assignments[0]
    program = item.get("program") or {}
    units = program.get("units") or []
    progress_map = {
        int(topic_id): data
        for topic_id, data in (item.get("progress_map") or {}).items()
    }

    next_topics: list[dict] = []
    completed_topics: list[dict] = []
    global_number = 0
    for unit in units:
        for topic in unit.get("topics") or []:
            global_number += 1
            topic_id = int(topic.get("topic_id") or 0)
            topic_row = {
                **topic,
                "global_number": global_number,
                "unit_number": int(unit.get("unit_number") or 0),
                "unit_title": unit.get("title") or "",
                "is_done": bool(progress_map.get(topic_id, {}).get("is_done")),
            }
            if topic_row["is_done"]:
                completed_topics.append(topic_row)
            else:
                next_topics.append(topic_row)

    return {
        "assignment_id": int(item.get("id") or 0),
        "program_id": int(item.get("program_id") or 0),
        "program_title": program.get("title") or t("assigned_learning_program"),
        "teacher_name": item.get("teacher_name") or "—",
        "subject": program.get("subject") or "other",
        "subject_display": item.get("subject_display") or program.get("subject_display") or "—",
        "level_or_band": program.get("level_or_band") or "",
        "progress_pct": int(item.get("progress_pct") or 0),
        "completed_topics": int(item.get("completed_topics") or 0),
        "total_topics": int(item.get("total_topics") or 0),
        "next_topics": next_topics[:5],
        "recent_topics": list(reversed(completed_topics[-3:])),
    }


def _goal_category(goal_key: str) -> str:
    mapping = {
        "improve_vocabulary": "vocabulary",
        "improve_reading": "reading",
        "improve_grammar": "grammar",
        "improve_speaking": "speaking",
        "mental_math_fluency": "practice",
        "problem_solving": "quiz",
        "equation_confidence": "practice",
        "science_terminology": "vocabulary",
        "concept_understanding": "reading",
        "classification_skills": "practice",
        "music_terminology": "vocabulary",
        "rhythm_practice": "practice",
        "theory_review": "review",
        "symbol_identification": "review",
        "focus_and_routine": "practice",
        "organization_skills": "practice",
        "memory_review": "review",
        "reflection_and_planning": "review",
        "review_mistakes": "review",
        "exam_preparation": "quiz",
        "homework_support": "review",
        "general_practice": "practice",
    }
    return mapping.get(goal_key, "practice")


def _task_template(title_key: str, subtitle_key: str, minutes: int, category: str, xp: int) -> dict:
    return {
        "title_key": title_key,
        "subtitle_key": subtitle_key,
        "minutes": minutes,
        "category": category,
        "xp": xp,
    }


def _subject_task_templates(subject: str, goal: str) -> list[dict]:
    subject = normalize_subject(subject)
    goal_category = _goal_category(goal)

    shared = {
        "english": [
            _task_template("smart_plan_task_vocab_review", "smart_plan_task_vocab_review_desc", 5, "vocabulary", 10),
            _task_template("smart_plan_task_reading_mini", "smart_plan_task_reading_mini_desc", 10, "reading", 10),
            _task_template("smart_plan_task_grammar_boost", "smart_plan_task_grammar_boost_desc", 8, "grammar", 10),
            _task_template("smart_plan_task_speaking_prompt", "smart_plan_task_speaking_prompt_desc", 8, "speaking", 10),
            _task_template("smart_plan_task_review_mistakes", "smart_plan_task_review_mistakes_desc", 5, "review", 10),
            _task_template("smart_plan_task_quick_challenge", "smart_plan_task_quick_challenge_desc", 7, "quiz", 15),
        ],
        "spanish": [
            _task_template("smart_plan_task_vocab_review", "smart_plan_task_vocab_review_desc", 5, "vocabulary", 10),
            _task_template("smart_plan_task_reading_mini", "smart_plan_task_reading_mini_desc", 10, "reading", 10),
            _task_template("smart_plan_task_grammar_boost", "smart_plan_task_grammar_boost_desc", 8, "grammar", 10),
            _task_template("smart_plan_task_speaking_prompt", "smart_plan_task_speaking_prompt_desc", 8, "speaking", 10),
            _task_template("smart_plan_task_review_mistakes", "smart_plan_task_review_mistakes_desc", 5, "review", 10),
            _task_template("smart_plan_task_quick_challenge", "smart_plan_task_quick_challenge_desc", 7, "quiz", 15),
        ],
        "mathematics": [
            _task_template("smart_plan_task_mental_math", "smart_plan_task_mental_math_desc", 5, "practice", 10),
            _task_template("smart_plan_task_problem_solving", "smart_plan_task_problem_solving_desc", 10, "quiz", 15),
            _task_template("smart_plan_task_formula_recall", "smart_plan_task_formula_recall_desc", 5, "review", 10),
            _task_template("smart_plan_task_error_review_math", "smart_plan_task_error_review_math_desc", 5, "review", 10),
            _task_template("smart_plan_task_show_your_work", "smart_plan_task_show_your_work_desc", 10, "practice", 15),
        ],
        "science": [
            _task_template("smart_plan_task_science_terms", "smart_plan_task_science_terms_desc", 5, "vocabulary", 10),
            _task_template("smart_plan_task_classification", "smart_plan_task_classification_desc", 8, "practice", 10),
            _task_template("smart_plan_task_concept_explain", "smart_plan_task_concept_explain_desc", 8, "reading", 10),
            _task_template("smart_plan_task_science_quiz", "smart_plan_task_science_quiz_desc", 7, "quiz", 15),
            _task_template("smart_plan_task_science_review", "smart_plan_task_science_review_desc", 5, "review", 10),
        ],
        "music": [
            _task_template("smart_plan_task_music_terms", "smart_plan_task_music_terms_desc", 5, "vocabulary", 10),
            _task_template("smart_plan_task_rhythm_count", "smart_plan_task_rhythm_count_desc", 8, "practice", 10),
            _task_template("smart_plan_task_symbol_review", "smart_plan_task_symbol_review_desc", 6, "review", 10),
            _task_template("smart_plan_task_theory_check", "smart_plan_task_theory_check_desc", 7, "quiz", 15),
            _task_template("smart_plan_task_composer_match", "smart_plan_task_composer_match_desc", 8, "practice", 10),
        ],
        "study_skills": [
            _task_template("smart_plan_task_focus_sprint", "smart_plan_task_focus_sprint_desc", 10, "practice", 10),
            _task_template("smart_plan_task_memory_review", "smart_plan_task_memory_review_desc", 5, "review", 10),
            _task_template("smart_plan_task_organize_notes", "smart_plan_task_organize_notes_desc", 8, "practice", 10),
            _task_template("smart_plan_task_reflection", "smart_plan_task_reflection_desc", 5, "review", 10),
            _task_template("smart_plan_task_planning_check", "smart_plan_task_planning_check_desc", 7, "quiz", 15),
        ],
        "other": [
            _task_template("smart_plan_task_focus_sprint", "smart_plan_task_focus_sprint_desc", 10, "practice", 10),
            _task_template("smart_plan_task_review_mistakes", "smart_plan_task_review_mistakes_desc", 5, "review", 10),
            _task_template("smart_plan_task_quick_challenge", "smart_plan_task_quick_challenge_desc", 7, "quiz", 15),
        ],
    }
    templates = shared.get(subject, shared["other"])
    preferred = [tpl for tpl in templates if tpl["category"] == goal_category]
    others = [tpl for tpl in templates if tpl["category"] != goal_category]
    return preferred + others


def _program_anchor_tasks(anchor: dict, minutes: int) -> list[dict]:
    target_count = 3 if minutes <= 15 else 4 if minutes <= 30 else 5
    chosen_topics = (anchor.get("next_topics") or [])[:target_count]
    if not chosen_topics:
        chosen_topics = (anchor.get("recent_topics") or [])[:target_count]
    if not chosen_topics:
        return []

    base_minutes = max(5, round(minutes / max(1, len(chosen_topics))))
    tasks: list[dict] = []
    for idx, topic in enumerate(chosen_topics, 1):
        topic_number = int(topic.get("global_number") or idx)
        topic_title = str(topic.get("title") or t("assigned_learning_program")).strip()
        summary = (
            str(topic.get("student_summary") or "").strip()
            or str(topic.get("lesson_focus") or "").strip()
            or str(topic.get("subtopic") or "").strip()
            or t("smart_plan_program_anchor_default_summary")
        )
        tasks.append(
            {
                "id": f"{_today_iso()}_program_{int(topic.get('topic_id') or idx)}",
                "title": t("smart_plan_program_task_title", number=topic_number, title=topic_title),
                "subtitle": t(
                    "smart_plan_program_task_subtitle",
                    unit=topic.get("unit_number") or 1,
                    summary=summary,
                ),
                "minutes": base_minutes,
                "category": _topic_category(topic),
                "xp": 15,
                "done": False,
            }
        )
    return tasks


def _generate_smart_plan_tasks(subject: str, goal: str, minutes: int, program_anchor: dict | None = None) -> list[dict]:
    if program_anchor:
        anchor_tasks = _program_anchor_tasks(program_anchor, minutes)
        if anchor_tasks:
            return anchor_tasks

    templates = _subject_task_templates(subject, goal)
    target_count = 3 if minutes <= 15 else 4 if minutes <= 30 else 5
    selected = templates[:target_count]
    total_minutes = sum(task["minutes"] for task in selected)

    if total_minutes < minutes and selected:
        selected[-1] = {**selected[-1], "minutes": selected[-1]["minutes"] + min(10, minutes - total_minutes)}

    return [
        {
            "id": f"{_today_iso()}_{idx}",
            "title_key": task["title_key"],
            "subtitle_key": task["subtitle_key"],
            "minutes": task["minutes"],
            "category": task["category"],
            "xp": task["xp"],
            "done": False,
        }
        for idx, task in enumerate(selected, 1)
    ]


def _generate_smart_plan_weekly_preview(subject: str, goal: str, minutes: int, tasks: list[dict], program_anchor: dict | None = None) -> list[dict]:
    progress = _calculate_smart_plan_progress(tasks)
    today = today_local()
    if program_anchor and (program_anchor.get("next_topics") or program_anchor.get("recent_topics")):
        focus_topics = (program_anchor.get("next_topics") or program_anchor.get("recent_topics") or [])[:5]
        rows = []
        for offset, topic in enumerate(focus_topics):
            day = date.fromordinal(today.toordinal() + offset)
            status = "completed" if offset == 0 and progress["all_done"] else ("in_progress" if offset == 0 else "coming_next")
            rows.append(
                {
                    "day_label": _format_day_label(day),
                    "focus_label": t(
                        "smart_plan_program_weekly_focus",
                        number=int(topic.get("global_number") or offset + 1),
                        title=str(topic.get("title") or t("assigned_learning_program")),
                    ),
                    "status": status,
                    "minutes": minutes,
                    "subject": subject,
                }
            )
        return rows

    daily_focus = [
        goal,
        "review_mistakes" if goal != "review_mistakes" else "general_practice",
        "general_practice" if goal != "general_practice" else "exam_preparation",
        "exam_preparation",
        "review_mistakes",
    ]

    rows = []
    for offset, focus in enumerate(daily_focus):
        day = date.fromordinal(today.toordinal() + offset)
        if offset == 0:
            status = "completed" if progress["all_done"] else "in_progress"
        elif offset == 1:
            status = "coming_next"
        else:
            status = "coming_next"
        rows.append(
            {
                "day_label": _format_day_label(day),
                "focus_label": _smart_plan_focus_label(focus),
                "status": status,
                "minutes": minutes,
                "subject": subject,
            }
        )
    return rows


def _generate_smart_plan_recommendations(subject: str, goal: str, progress_state: dict, program_anchor: dict | None = None) -> list[dict]:
    if program_anchor:
        recommendation_topics = (program_anchor.get("next_topics") or program_anchor.get("recent_topics") or [])[:3]
        if recommendation_topics:
            return [
                {
                    "label": t(
                        "smart_plan_program_recommendation",
                        number=int(topic.get("global_number") or idx + 1),
                        title=str(topic.get("title") or t("assigned_learning_program")),
                    )
                }
                for idx, topic in enumerate(recommendation_topics)
            ]
    subject = normalize_subject(subject)
    by_subject = {
        "english": ["review_mistakes", "improve_vocabulary", "improve_reading"],
        "spanish": ["improve_vocabulary", "improve_speaking", "review_mistakes"],
        "mathematics": ["problem_solving", "equation_confidence", "review_mistakes"],
        "science": ["concept_understanding", "science_terminology", "review_mistakes"],
        "music": ["theory_review", "rhythm_practice", "symbol_identification"],
        "study_skills": ["focus_and_routine", "organization_skills", "reflection_and_planning"],
        "other": ["general_practice", "review_mistakes", "exam_preparation"],
    }
    ordered = [goal] + [item for item in by_subject.get(subject, by_subject["other"]) if item != goal]
    if progress_state.get("all_done"):
        ordered = ["exam_preparation", "review_mistakes"] + [item for item in ordered if item not in {"exam_preparation", "review_mistakes"}]
    return [{"goal_key": item} for item in ordered[:3]]


def _generate_smart_plan(subject: str, goal: str, minutes: int, program_anchor: dict | None = None) -> dict:
    tasks = _generate_smart_plan_tasks(subject, goal, minutes, program_anchor)
    progress = _calculate_smart_plan_progress(tasks)
    return {
        "generated_for": _today_iso(),
        "tasks": tasks,
        "weekly_preview": _generate_smart_plan_weekly_preview(subject, goal, minutes, tasks, program_anchor),
        "recommendations": _generate_smart_plan_recommendations(subject, goal, progress, program_anchor),
        "program_anchor_signature": _smart_plan_anchor_signature(program_anchor),
    }


def _ensure_today_plan(state: dict, program_anchor: dict | None = None) -> dict:
    current_signature = _smart_plan_anchor_signature(program_anchor)
    if state.get("generated_for") == _today_iso() and state.get("tasks") and state.get("program_anchor_signature", "") == current_signature:
        return state
    generated = _generate_smart_plan(state["subject"], state["goal"], int(state["minutes_per_day"]), program_anchor)
    state.update(generated)
    state["last_active_date"] = _today_iso()
    return state


def _task_title(task: dict) -> str:
    direct = str(task.get("title") or "").strip()
    if direct:
        return direct
    return t(task.get("title_key", ""))


def _task_subtitle(task: dict) -> str:
    direct = str(task.get("subtitle") or "").strip()
    if direct:
        subtitle = direct
    else:
        subtitle = t(task.get("subtitle_key", ""))
    return t("smart_plan_task_meta", subtitle=subtitle, minutes=task.get("minutes", 0))


def _status_badge(status: str) -> tuple[str, str]:
    mapping = {
        "completed": ("#10B981", t("completed")),
        "in_progress": ("#F59E0B", t("in_progress")),
        "coming_next": ("#64748B", t("smart_plan_coming_next")),
    }
    return mapping.get(status, ("#64748B", t("smart_plan_coming_next")))


def _sync_rewards(state: dict, old_tasks: list[dict], new_tasks: list[dict]) -> dict:
    old_done = {task.get("id"): bool(task.get("done")) for task in old_tasks or []}
    gained = 0
    for task in new_tasks or []:
        task_id = task.get("id")
        now_done = bool(task.get("done"))
        was_done = old_done.get(task_id, False)
        if now_done and not was_done:
            gained += int(task.get("xp", 10))
        elif was_done and not now_done:
            gained -= int(task.get("xp", 10))

    state["points"] = max(0, int(state.get("points", 0)) + gained)

    new_progress = _calculate_smart_plan_progress(new_tasks)
    old_progress = _calculate_smart_plan_progress(old_tasks)
    today_iso = _today_iso()

    if new_progress["all_done"] and not old_progress["all_done"]:
        state["points"] += 20
        last_completion = str(state.get("last_completion_date") or "")
        if last_completion:
            last_date = date.fromisoformat(last_completion)
            today = today_local()
            if last_date.toordinal() == today.toordinal() - 1:
                state["streak"] = max(1, int(state.get("streak", 0)) + 1)
            elif last_date.isoformat() != today_iso:
                state["streak"] = 1
        else:
            state["streak"] = 1
        state["last_completion_date"] = today_iso
    elif not new_progress["all_done"] and old_progress["all_done"]:
        state["points"] = max(0, state["points"] - 20)
        if str(state.get("last_completion_date") or "") == today_iso:
            state["last_completion_date"] = ""
            state["streak"] = max(0, int(state.get("streak", 0)) - 1)

    state["last_active_date"] = today_iso
    return state


def _render_smart_plan_setup(state: dict, program_anchor: dict | None = None) -> tuple[dict, bool]:
    st.markdown(f"### {t('smart_plan_setup_title')}")
    st.caption(t("smart_plan_program_anchor_setup_hint") if program_anchor else t("smart_plan_setup_subtitle"))

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        anchor_subject = normalize_subject(str(program_anchor.get("subject") or "")) if program_anchor else ""
        subject_options = _smart_plan_subject_options()
        selected_subject = anchor_subject if anchor_subject in subject_options else state["subject"]
        with col1:
            subject = st.selectbox(
                t("subject_label"),
                options=subject_options,
                index=max(0, subject_options.index(selected_subject)) if selected_subject in subject_options else 0,
                format_func=_subject_label,
                key="student_smart_plan_subject",
                disabled=bool(program_anchor and anchor_subject in subject_options),
            )
            custom_subject = state.get("custom_subject", "")
            if subject == "other":
                custom_subject = st.text_input(
                    t("other_subject_label"),
                    value=str(program_anchor.get("subject_display") or custom_subject) if program_anchor else custom_subject,
                    key="student_smart_plan_custom_subject",
                    disabled=bool(program_anchor),
                ).strip()
        with col2:
            goal_options = _smart_plan_goal_options_for_subject(subject)
            current_goal = state["goal"] if state["goal"] in goal_options else (goal_options[0] if goal_options else "general_practice")
            goal = st.selectbox(
                t("smart_plan_focus_area"),
                options=goal_options,
                index=max(0, goal_options.index(current_goal)) if current_goal in goal_options else 0,
                format_func=_smart_plan_focus_label,
                key="student_smart_plan_goal",
            )
        with col3:
            minutes = st.selectbox(
                t("smart_plan_time_per_day"),
                options=_smart_plan_time_options(),
                index=max(0, _smart_plan_time_options().index(int(state["minutes_per_day"]))) if int(state["minutes_per_day"]) in _smart_plan_time_options() else 1,
                format_func=_smart_plan_time_label,
                key="student_smart_plan_minutes",
            )

        b1, b2 = st.columns(2)
        with b1:
            save_clicked = st.button(
                t("smart_plan_update_preferences") if state.get("setup_complete") else t("smart_plan_save_preferences"),
                key="student_smart_plan_save",
                use_container_width=True,
            )
        with b2:
            generate_clicked = st.button(
                t("smart_plan_generate_plan"),
                key="student_smart_plan_generate",
                type="primary",
                use_container_width=True,
            )

    updated = dict(state)
    updated["subject"] = subject
    updated["goal"] = goal
    updated["minutes_per_day"] = int(minutes)
    updated["custom_subject"] = custom_subject if subject == "other" else ""

    plan_regenerated = False
    if save_clicked or generate_clicked:
        updated["setup_complete"] = True
        if save_clicked or generate_clicked or updated.get("generated_for") != _today_iso():
            updated.update(_generate_smart_plan(updated["subject"], updated["goal"], updated["minutes_per_day"], program_anchor))
            plan_regenerated = True
        st.success(t("smart_plan_preferences_saved"))

    return updated, plan_regenerated


def _render_smart_plan_progress(state: dict) -> None:
    level = _calculate_smart_plan_level(int(state.get("points", 0)))
    progress = _calculate_smart_plan_progress(state.get("tasks", []))

    st.markdown(f"### {t('smart_plan_your_progress')}")
    cols = st.columns(3)
    cards = [
        ("smart_plan_level", level, "#2563EB"),
        ("smart_plan_points", int(state.get("points", 0)), "#8B5CF6"),
        ("smart_plan_streak", int(state.get("streak", 0)), "#F59E0B"),
    ]
    for col, (label_key, value, color) in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:18px 16px;">
                    <div style="font-size:0.85rem;color:var(--muted);font-weight:700;">{t(label_key)}</div>
                    <div style="font-size:1.8rem;font-weight:900;color:{color};margin-top:6px;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.caption(t("smart_plan_progress_hint", completed=progress["completed"], total=progress["total"]))


def _render_smart_plan_today(state: dict) -> dict:
    tasks = [dict(task) for task in state.get("tasks", [])]
    if not tasks:
        return state

    st.markdown(f"### {t('smart_plan_today_section')}")
    progress_text_slot = st.empty()
    progress_bar_slot = st.empty()

    updated_tasks = []
    for idx, task in enumerate(tasks):
        done = st.checkbox(
            f"{_task_title(task)}",
            value=bool(task.get("done")),
            key=f"student_smart_plan_task_{task.get('id', idx)}",
            help=_task_subtitle(task),
        )
        color_map = {
            "reading": "#2563EB",
            "vocabulary": "#10B981",
            "grammar": "#A855F7",
            "review": "#F59E0B",
            "quiz": "#EF4444",
            "speaking": "#14B8A6",
            "practice": "#64748B",
        }
        badge_color = color_map.get(task.get("category"), "#64748B")
        st.markdown(
            f"""
            <div style="margin:-4px 0 12px 0;padding:10px 14px;border:1px solid var(--border);border-radius:14px;background:var(--panel-soft);">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
                    <div style="font-size:0.86rem;color:var(--muted);">{_task_subtitle(task)}</div>
                    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                        <span style="font-size:0.72rem;padding:4px 10px;border-radius:999px;background:{badge_color}18;color:{badge_color};font-weight:700;">
                            {t(f"smart_plan_category_{task.get('category')}")}
                        </span>
                        <span style="font-size:0.78rem;color:var(--muted);">+{int(task.get('xp', 10))} XP</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        updated_tasks.append({**task, "done": done})

    old_tasks = state.get("tasks", [])
    state["tasks"] = updated_tasks
    state = _sync_rewards(state, old_tasks, updated_tasks)
    progress = _calculate_smart_plan_progress(updated_tasks)

    progress_text_slot.caption(
        t("smart_plan_progress_text", completed=progress["completed"], total=progress["total"])
    )
    progress_bar_slot.progress(progress["pct"] / 100 if progress["total"] else 0.0)

    if progress["all_done"]:
        st.success(t("smart_plan_all_done_message"))
    return state


def _render_smart_plan_weekly(state: dict) -> None:
    st.markdown(f"### {t('smart_plan_weekly_title')}")
    rows = state.get("weekly_preview", [])
    if not rows:
        st.info(t("smart_plan_generate_weekly_hint"))
        return

    for row in rows:
        color, status_label = _status_badge(row.get("status", "coming_next"))
        st.markdown(
            f"""
            <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:14px 16px;margin-bottom:10px;">
                <div>
                    <div style="font-weight:800;">{row.get("day_label", "")}</div>
                    <div style="font-size:0.88rem;color:var(--muted);">{row.get("focus_label", "")} • {_smart_plan_time_label(int(row.get("minutes", 0)))}</div>
                </div>
                <span style="font-size:0.75rem;padding:5px 10px;border-radius:999px;background:{color}18;color:{color};font-weight:800;">
                    {status_label}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_smart_plan_recommendations(state: dict) -> None:
    st.markdown(f"### {t('smart_plan_recommendations_title')}")
    recommendations = state.get("recommendations", [])
    if not recommendations:
        st.info(t("smart_plan_generate_recommendations_hint"))
        return

    cols = st.columns(len(recommendations))
    for col, item in zip(cols, recommendations):
        with col:
            label = _smart_plan_focus_label(item.get("goal_key")) if item.get("goal_key") else str(item.get("label") or "—")
            st.markdown(
                f"""
                <div style="height:100%;background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:16px;">
                    <div style="font-size:0.82rem;color:var(--muted);font-weight:700;">{t('smart_plan_recommended_label')}</div>
                    <div style="margin-top:6px;font-size:1rem;font-weight:800;">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_smart_plan_teacher_summary() -> None:
    assignments = get_student_assignment_summary(limit=3)
    has_links = has_active_teacher_relationships()
    if not has_links and not assignments:
        return

    st.markdown(f"### {t('smart_plan_teacher_assignments_title')}")
    if not assignments:
        st.info(t("smart_plan_teacher_assignments_empty"))
        return

    cols = st.columns(len(assignments))
    for col, item in zip(cols, assignments):
        with col:
            due_text = str(item.get("due_at") or "").strip()
            status = str(item.get("status") or "").strip()
            status_map = {
                "assigned": ("#2563eb", "rgba(37,99,235,.12)"),
                "started": ("#d97706", "rgba(217,119,6,.12)"),
                "submitted": ("#7c3aed", "rgba(124,58,237,.12)"),
                "graded": ("#059669", "rgba(5,150,105,.12)"),
                "completed": ("#059669", "rgba(5,150,105,.12)"),
                "overdue": ("#dc2626", "rgba(220,38,38,.12)"),
                "cancelled": ("#64748b", "rgba(100,116,139,.12)"),
            }
            status_color, status_bg = status_map.get(status, ("var(--text)", "rgba(148,163,184,.08)"))
            st.markdown(
                f"""
                <div class="classio-smart-teacher-card">
                    <div class="classio-smart-teacher-name">{item.get('teacher_name', '—')}</div>
                    <div class="classio-smart-teacher-title">{item.get('title', '—')}</div>
                    <div class="classio-smart-teacher-subject">{item.get('subject_display', '—')}</div>
                    <div class="classio-smart-teacher-meta">
                        <span class="classio-smart-status-pill" style="color:{status_color};background:{status_bg};border-color:{status_color}22;">
                            {t(f'assignment_status_{status}')}
                        </span>
                        <span class="classio-smart-secondary-pill">
                            {(_safe_ui_label('due_date', 'assignment_set_due_date') + ': ' + due_text[:10]) if due_text else t('new_from_your_teachers')}
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    if st.button(t("view_all_assignments"), key="smart_plan_view_assignments", use_container_width=True):
        go_to("student_assignments")
        st.rerun()


def render_student_study_plan():
    _inject_smart_plan_styles()
    _inject_assignment_page_styles()
    state = _load_smart_plan_state()
    program_assignments = load_enriched_program_assignments_for_current_student()
    program_anchor = _build_program_anchor(program_assignments)

    if program_anchor:
        anchor_subject = normalize_subject(str(program_anchor.get("subject") or ""))
        if anchor_subject in _smart_plan_subject_options():
            state["subject"] = anchor_subject
        elif program_anchor.get("subject_display"):
            state["subject"] = "other"
            state["custom_subject"] = str(program_anchor.get("subject_display") or "")

    st.markdown(f"## 📚 {t('smart_study_plan')}")
    st.caption(t("smart_plan_page_subtitle"))

    tab_plan, tab_programs, tab_teacher = st.tabs(
        [
            f"✨ {t('smart_study_plan')}",
            f"📚 {t('assigned_learning_program')}",
            f"🗂️ {t('smart_plan_teacher_assignments_title')}",
        ]
    )

    with tab_plan:
        state, plan_regenerated = _render_smart_plan_setup(state, program_anchor)
        if state.get("setup_complete") and not plan_regenerated:
            state = _ensure_today_plan(state, program_anchor)

        if state.get("setup_complete"):
            if program_anchor:
                st.caption(
                    f"{program_anchor.get('program_title', t('assigned_learning_program'))} · "
                    f"{t('smart_plan_program_anchor_progress', completed=program_anchor.get('completed_topics', 0), total=program_anchor.get('total_topics', 0), percent=program_anchor.get('progress_pct', 0))}"
                )
            _render_smart_plan_progress(state)
            state = _render_smart_plan_today(state)
            state["weekly_preview"] = _generate_smart_plan_weekly_preview(
                state["subject"],
                state["goal"],
                int(state["minutes_per_day"]),
                state.get("tasks", []),
                program_anchor,
            )
            state["recommendations"] = _generate_smart_plan_recommendations(
                state["subject"],
                state["goal"],
                _calculate_smart_plan_progress(state.get("tasks", [])),
                program_anchor,
            )
            _render_smart_plan_weekly(state)
            _render_smart_plan_recommendations(state)
        else:
            st.info(t("smart_plan_setup_prompt"))

    with tab_programs:
        render_assigned_learning_programs_section(program_assignments, [])

    with tab_teacher:
        _render_smart_plan_teacher_summary()

    _save_smart_plan_state(state)
