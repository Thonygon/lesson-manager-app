from datetime import date
import html as _html
import re

import streamlit as st

from core.database import load_profile_row
from core.i18n import t
from core.navigation import go_to
from core.state import get_current_user_id
from core.timezone import today_local
from app_pages.student_assignments import (
    _assignment_scope_groups,
    _inject_assignment_page_styles,
    _program_subject_groups,
    _render_student_pagination,
    _slice_student_page,
    render_assigned_learning_programs_section,
)
from helpers.lesson_planner import QUICK_SUBJECTS, normalize_subject, subject_label as _subject_label
from helpers.learning_programs import load_enriched_program_assignments_for_current_student
from helpers.exposure_telemetry import attach_student_recommendation_exposures
from helpers.quick_exam_storage import load_exam_record
from helpers.resource_gallery import (
    extract_gallery_image_url,
    extract_gallery_language_label,
    inject_resource_gallery_styles,
    render_gallery_card_html,
)
from helpers.material_recommendations import find_similar_materials
from helpers.student_recommendation_ml import log_student_recommendation_impressions, log_student_recommendation_open
from helpers.teacher_student_integration import get_student_assignment_summary, has_active_teacher_relationships, load_student_assignments
from helpers.worksheet_storage import load_worksheet_record
from helpers.empty_states import render_empty_state


_SMART_PLAN_NS = "student_smart_plan"
_LESSON_TOPIC_PAGE_SIZE = 6
_SMART_PLAN_STOPWORDS = {
    "about", "after", "again", "always", "around", "because", "before", "being", "between",
    "daily", "during", "each", "from", "have", "into", "just", "learn", "lesson", "make",
    "more", "most", "plan", "practice", "review", "smart", "study", "that", "their", "them",
    "these", "they", "this", "today", "topic", "topics", "unit", "using", "what", "when",
    "where", "which", "with", "your",
}


def _smart_plan_user_key(suffix: str) -> str:
    uid = str(get_current_user_id() or "").strip() or "anon"
    return f"{_SMART_PLAN_NS}_{suffix}_{uid}"


def _smart_plan_pagination_key(suffix: str) -> str:
    return _smart_plan_user_key(f"page_{suffix}")


def _inject_smart_plan_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-smart-teacher-grid {
            margin-top: 0.45rem;
        }
        .classio-smart-teacher-row-gap {
            height: 1rem;
        }
        .classio-smart-teacher-cta-gap {
            height: 1rem;
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


def _smart_plan_tokens(*values: object) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip().casefold()
        if not text:
            continue
        for token in re.findall(r"[a-z0-9]+", text):
            if len(token) < 3 or token in _SMART_PLAN_STOPWORDS:
                continue
            tokens.add(token)
    return tokens


def _smart_plan_goal_profile(goal: str) -> dict[str, object]:
    profiles = {
        "exam_preparation": {
            "resource_weights": {"exam": 1.8, "worksheet": 0.85, "video": 0.25},
            "keywords": {"exam", "test", "quiz", "mock", "questions"},
        },
        "review_mistakes": {
            "resource_weights": {"worksheet": 1.35, "exam": 0.95, "video": 0.35},
            "keywords": {"review", "mistakes", "correction", "revision"},
        },
        "improve_reading": {
            "resource_weights": {"worksheet": 1.2, "exam": 0.8, "video": 0.45},
            "keywords": {"reading", "text", "comprehension", "story"},
        },
        "improve_vocabulary": {
            "resource_weights": {"worksheet": 1.15, "video": 0.8, "exam": 0.55},
            "keywords": {"vocabulary", "words", "verbs", "phrases"},
        },
        "improve_grammar": {
            "resource_weights": {"worksheet": 1.2, "exam": 0.7, "video": 0.25},
            "keywords": {"grammar", "tense", "sentence", "structure"},
        },
        "improve_speaking": {
            "resource_weights": {"video": 1.45, "worksheet": 0.7, "exam": 0.2},
            "keywords": {"speaking", "conversation", "dialogue", "pronunciation"},
        },
        "problem_solving": {
            "resource_weights": {"worksheet": 1.25, "exam": 0.9, "video": 0.25},
            "keywords": {"problems", "solve", "operations", "strategy"},
        },
        "equation_confidence": {
            "resource_weights": {"worksheet": 1.2, "exam": 0.8, "video": 0.2},
            "keywords": {"equation", "algebra", "expressions", "solve"},
        },
        "concept_understanding": {
            "resource_weights": {"video": 1.0, "worksheet": 1.0, "exam": 0.45},
            "keywords": {"concept", "understanding", "explain", "science"},
        },
        "general_practice": {
            "resource_weights": {"worksheet": 1.0, "exam": 0.8, "video": 0.6},
            "keywords": {"practice", "general", "skills"},
        },
        "homework_support": {
            "resource_weights": {"worksheet": 1.1, "exam": 0.8, "video": 0.55},
            "keywords": {"homework", "support", "classwork"},
        },
    }
    return profiles.get(
        goal,
        {
            "resource_weights": {"worksheet": 1.0, "exam": 0.75, "video": 0.55},
            "keywords": set(),
        },
    )


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


def _load_smart_plan_state(scope_key: str = "") -> dict:
    key = _smart_plan_user_key(f"data_{scope_key}" if scope_key else "data")
    existing = st.session_state.get(key)
    defaults = _default_smart_plan_state()
    if not isinstance(existing, dict):
        st.session_state[key] = defaults
        return defaults.copy()
    merged = defaults | existing
    st.session_state[key] = merged
    return merged.copy()


def _save_smart_plan_state(state: dict, scope_key: str = "") -> None:
    suffix = f"data_{scope_key}" if scope_key else "data"
    st.session_state[_smart_plan_user_key(suffix)] = dict(state)


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
                "is_done": bool(progress_map.get(topic_id, {}).get("teacher_done")),
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


def _generate_smart_plan_recommendations(
    state: dict,
    progress_state: dict,
    program_anchor: dict | None = None,
) -> list[dict]:
    return _recommend_smart_plan_resources(state, progress_state, program_anchor)


def _generate_smart_plan(subject: str, goal: str, minutes: int, program_anchor: dict | None = None) -> dict:
    tasks = _generate_smart_plan_tasks(subject, goal, minutes, program_anchor)
    progress = _calculate_smart_plan_progress(tasks)
    weekly_preview = _generate_smart_plan_weekly_preview(subject, goal, minutes, tasks, program_anchor)
    recommendation_state = {
        "subject": subject,
        "goal": goal,
        "minutes_per_day": minutes,
        "tasks": tasks,
        "weekly_preview": weekly_preview,
    }
    return {
        "generated_for": _today_iso(),
        "tasks": tasks,
        "weekly_preview": weekly_preview,
        "recommendations": _generate_smart_plan_recommendations(recommendation_state, progress, program_anchor),
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


def _smart_plan_focus_topics(
    state: dict,
    program_anchor: dict | None = None,
) -> list[str]:
    topic_labels: list[str] = []
    if program_anchor:
        for topic in (program_anchor.get("next_topics") or [])[:5]:
            title = str(topic.get("title") or "").strip()
            if title:
                topic_labels.append(title)
    if not topic_labels:
        for row in (state.get("weekly_preview") or [])[:5]:
            label = str(row.get("focus_label") or "").strip()
            if label:
                topic_labels.append(label)
    if not topic_labels:
        for task in state.get("tasks", []) or []:
            title = _task_title(task)
            if title:
                topic_labels.append(title)
    return topic_labels


def _smart_plan_focus_topic_ids(program_anchor: dict | None = None) -> list[int]:
    topic_ids: list[int] = []
    for topic in (program_anchor or {}).get("next_topics") or []:
        topic_id = int(topic.get("topic_id") or 0)
        if topic_id > 0:
            topic_ids.append(topic_id)
    return topic_ids


def _smart_plan_request_context(state: dict, program_anchor: dict | None = None) -> dict[str, str]:
    user_id = get_current_user_id()
    profile = load_profile_row(user_id) if user_id else {}
    return {
        "subject": str(state.get("subject") or ""),
        "learner_stage": str(program_anchor.get("learner_stage") or profile.get("learner_stage") or "").strip() if program_anchor else str(profile.get("learner_stage") or "").strip(),
        "level_or_band": str(program_anchor.get("level_or_band") or profile.get("level_or_band") or "").strip() if program_anchor else str(profile.get("level_or_band") or "").strip(),
    }


def _smart_plan_material_requests(
    state: dict,
    program_anchor: dict | None = None,
) -> list[dict[str, object]]:
    context = _smart_plan_request_context(state, program_anchor)
    focus_topics = _smart_plan_focus_topics(state, program_anchor)
    topic_requests: list[dict[str, object]] = []
    seen_topics: set[str] = set()
    task_subtitles = [_task_subtitle(task) for task in (state.get("tasks") or [])]
    next_topics = list((program_anchor or {}).get("next_topics") or [])

    for idx, topic_text in enumerate(focus_topics[:4]):
        normalized_topic = str(topic_text or "").strip()
        if not normalized_topic:
            continue
        topic_key = normalized_topic.casefold()
        if topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)
        topic_requests.append(
            {
                "kind": "",
                "subject": context["subject"],
                "learner_stage": context["learner_stage"],
                "level_or_band": context["level_or_band"],
                "topic": normalized_topic,
                "objective": task_subtitles[idx] if idx < len(task_subtitles) else "",
                "next_topics": focus_topics[:4],
                "goal": str(state.get("goal") or ""),
                "learning_program_topic_id": int((next_topics[idx].get("topic_id") or 0)) if idx < len(next_topics) else 0,
            }
        )
    return topic_requests


def _smart_plan_resource_reason_lines(
    match: dict,
    *,
    plan_topic: str,
) -> list[str]:
    reasons: list[str] = []
    bucket = str(match.get("recommendation_bucket") or "")
    if bucket == "very_close":
        reasons.append(f"Direct match for your plan topic: {plan_topic}.")
    elif bucket == "close":
        reasons.append(f"Strongly aligned with your plan topic: {plan_topic}.")
    elif bucket == "related":
        reasons.append(f"Related support for your plan topic: {plan_topic}.")
    topic_focus = match.get("topic_focus") or {}
    requested_type = str(topic_focus.get("requested_type") or "").strip()
    row_type = str(topic_focus.get("row_type") or "").strip()
    if requested_type and row_type and requested_type == row_type:
        reasons.append("Matches the same activity format.")
    if int(match.get("learning_program_topic_id") or 0) > 0:
        reasons.append("Linked to your learning-program progression.")
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        key = reason.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reason)
    return deduped[:3]


def _recommend_smart_plan_resources(
    state: dict,
    progress_state: dict,
    program_anchor: dict | None = None,
) -> list[dict]:
    goal = str(state.get("goal") or "").strip()
    goal_profile = _smart_plan_goal_profile(goal)
    requests = _smart_plan_material_requests(state, program_anchor)
    candidates: list[dict] = []

    for request in requests:
        matches = find_similar_materials(request, limit=4, min_score=7.5)
        if not matches:
            continue
        for match in matches:
            kind = str(match.get("kind") or "").strip()
            row = dict(match.get("row") or {})
            score = float(match.get("score") or 0.0)
            score += float((goal_profile.get("resource_weights") or {}).get(kind, 0.0))
            if progress_state.get("all_done") and kind == "exam":
                score += 0.5
            bucket = str(match.get("recommendation_bucket") or "")
            if bucket == "very_close":
                score += 2.0
            elif bucket == "close":
                score += 1.0
            elif bucket == "related":
                score -= 0.75
            candidates.append(
                {
                    "resource_type": kind,
                    "id": row.get("id"),
                    "title": str(row.get("title") or "").strip(),
                    "subject": str(row.get("subject") or "").strip(),
                    "topic": str(row.get("topic") or "").strip(),
                    "learner_stage": str(row.get("learner_stage") or "").strip(),
                    "level": str(row.get("level_or_band") or row.get("level") or "").strip(),
                    "exercise_type": str(row.get("worksheet_type") or row.get("lesson_purpose") or row.get("exam_length") or "").strip(),
                    "score": round(score, 4),
                    "reasons": _smart_plan_resource_reason_lines(
                        match,
                        plan_topic=str(request.get("topic") or "").strip(),
                    ),
                    "assigned_resource": False,
                    "assignment_id": 0,
                    "assignment_status": "",
                    "assignment_attempt_count": 0,
                    "assignment_teacher_name": "",
                    "learning_program_assignment_id": int((program_anchor or {}).get("assignment_id") or 0),
                    "learning_program_topic_id": int(request.get("learning_program_topic_id") or 0),
                    "program_id": int((program_anchor or {}).get("program_id") or 0),
                    "program_teacher_name": str((program_anchor or {}).get("teacher_name") or "").strip(),
                    "program_teacher_id": "",
                    "subject_display": str((program_anchor or {}).get("subject_display") or row.get("subject") or "").strip(),
                    "program_level": str((program_anchor or {}).get("level_or_band") or "").strip(),
                    "row": row,
                    "recommendation_bucket": bucket,
                    "matched_plan_topic": str(request.get("topic") or "").strip(),
                }
            )

    if not candidates:
        return []

    candidates.sort(
        key=lambda item: (
            {"very_close": 0, "close": 1, "related": 2}.get(str(item.get("recommendation_bucket") or ""), 9),
            -float(item.get("score") or 0.0),
            str(item.get("topic") or "").casefold(),
            str(item.get("title") or "").casefold(),
        )
    )

    strongest_bucket = str(candidates[0].get("recommendation_bucket") or "")
    if strongest_bucket in {"very_close", "close"}:
        candidates = [
            item
            for item in candidates
            if str(item.get("recommendation_bucket") or "") in {"very_close", "close"}
        ]

    selected: list[dict] = []
    seen_keys: set[tuple[str, object]] = set()
    covered_topics: set[str] = set()
    for item in candidates:
        unique_key = (str(item.get("resource_type") or ""), item.get("id"))
        matched_topic = str(item.get("matched_plan_topic") or "").casefold()
        if unique_key in seen_keys:
            continue
        if matched_topic and matched_topic not in covered_topics:
            selected.append(item)
            seen_keys.add(unique_key)
            covered_topics.add(matched_topic)
        if len(selected) >= 3:
            break
    for item in candidates:
        if len(selected) >= 6:
            break
        unique_key = (str(item.get("resource_type") or ""), item.get("id"))
        if unique_key in seen_keys:
            continue
        selected.append(item)
        seen_keys.add(unique_key)
    return selected[:6]


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


def _render_smart_plan_setup(
    state: dict,
    program_anchor: dict | None = None,
    *,
    key_prefix: str = "",
) -> tuple[dict, bool]:
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
                key=f"student_smart_plan_subject_{key_prefix or 'default'}",
                disabled=bool(program_anchor and anchor_subject in subject_options),
            )
            custom_subject = state.get("custom_subject", "")
            if subject == "other":
                custom_subject = st.text_input(
                    t("other_subject_label"),
                    value=str(program_anchor.get("subject_display") or custom_subject) if program_anchor else custom_subject,
                    key=f"student_smart_plan_custom_subject_{key_prefix or 'default'}",
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
                key=f"student_smart_plan_goal_{key_prefix or 'default'}",
            )
        with col3:
            minutes = st.selectbox(
                t("smart_plan_time_per_day"),
                options=_smart_plan_time_options(),
                index=max(0, _smart_plan_time_options().index(int(state["minutes_per_day"]))) if int(state["minutes_per_day"]) in _smart_plan_time_options() else 1,
                format_func=_smart_plan_time_label,
                key=f"student_smart_plan_minutes_{key_prefix or 'default'}",
            )

        b1, b2 = st.columns(2)
        with b1:
            save_clicked = st.button(
                t("smart_plan_update_preferences") if state.get("setup_complete") else t("smart_plan_save_preferences"),
                key=f"student_smart_plan_save_{key_prefix or 'default'}",
                use_container_width=True,
            )
        with b2:
            generate_clicked = st.button(
                t("smart_plan_generate_plan"),
                key=f"student_smart_plan_generate_{key_prefix or 'default'}",
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


def _render_smart_plan_today(state: dict, *, key_prefix: str = "") -> dict:
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
            key=f"student_smart_plan_task_{key_prefix or 'default'}_{task.get('id', idx)}",
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


def _smart_plan_resource_label(resource_type: str) -> str:
    if resource_type == "worksheet":
        return _safe_ui_label("worksheet_label")
    if resource_type == "exam":
        return _safe_ui_label("exam_label")
    if resource_type == "video":
        return _safe_ui_label("video_label")
    return resource_type.replace("_", " ").title()


def _open_smart_plan_recommendation(item: dict) -> bool:
    resource_type = str(item.get("resource_type") or "").strip()
    assignment_id = int(item.get("assignment_id") or 0)
    if assignment_id > 0 and resource_type in {"worksheet", "exam"}:
        from app_pages.student_assignments import _open_assignment_practice
        from helpers.teacher_student_integration import load_student_assignment_by_id

        assignment_row = load_student_assignment_by_id(assignment_id)
        if assignment_row:
            _open_assignment_practice(assignment_row)
            return True

    row = dict(item.get("row") or {})
    if resource_type == "worksheet":
        from app_pages.student_practice import _open_worksheet_practice_from_row

        return _open_worksheet_practice_from_row(row, return_page="student_study_plan")
    if resource_type == "exam":
        from app_pages.student_practice import _open_exam_practice_from_row

        return _open_exam_practice_from_row(row, return_page="student_study_plan")
    if resource_type == "video":
        from app_pages.student_practice import _open_video_item

        return _open_video_item(
            row,
            {
                "subject": str(item.get("subject") or row.get("subject") or ""),
                "topic": str(item.get("topic") or row.get("topic") or ""),
                "learner_stage": str(row.get("learner_stage") or ""),
                "level": str(item.get("level") or row.get("level_or_band") or row.get("level") or ""),
            },
            assignment_id=assignment_id,
            return_page="student_study_plan",
        )
    return False


def _render_smart_plan_recommendations(state: dict) -> None:
    st.markdown(f"### {t('smart_plan_recommendations_title')}")
    recommendations = state.get("recommendations", [])
    if not recommendations:
        st.info(t("smart_plan_generate_recommendations_hint"))
        return

    recommendations = attach_student_recommendation_exposures(recommendations, surface="student_smart_plan")
    log_student_recommendation_impressions(recommendations, surface="student_smart_plan")

    for idx in range(0, len(recommendations), 3):
        group = recommendations[idx:idx + 3]
        cols = st.columns(len(group))
        for col, item in zip(cols, group):
            with col:
                row = item.get("row") or {}
                resource_type = str(item.get("resource_type") or "worksheet")
                payload = dict(row)
                if resource_type in {"worksheet", "exam"} and not extract_gallery_image_url(payload) and row.get("id"):
                    full_row = load_worksheet_record(row.get("id")) if resource_type == "worksheet" else load_exam_record(row.get("id"))
                    payload = full_row or payload
                hero_image = extract_gallery_image_url(payload)
                language_label = extract_gallery_language_label(payload)
                resource_label = _smart_plan_resource_label(resource_type)
                chips = "".join(
                    [
                        f'<span class="cm-resource-chip">{_html.escape(resource_label)}</span>',
                        f'<span class="cm-resource-chip">🌐 {_html.escape(language_label)}</span>' if language_label else "",
                        f'<span class="cm-resource-chip">🏷️ {_html.escape(str(item.get("level") or ""))}</span>' if item.get("level") else "",
                        f'<span class="cm-resource-chip">📌 {_html.escape(t("assignment_status_assigned"))}</span>' if item.get("assigned_resource") else "",
                    ]
                )
                meta = "".join(
                    f"<div class='cm-resource-meta'>✨ {_html.escape(reason)}</div>"
                    for reason in (item.get("reasons") or [])[:2]
                )
                st.markdown(
                    render_gallery_card_html(
                        kind="video" if resource_type == "video" else "exam" if resource_type == "exam" else "worksheet",
                        title=str(item.get("title") or "—"),
                        chips_html=chips,
                        description=str(item.get("topic") or t("no_description_available")),
                        meta_html=meta,
                        image_url=hero_image,
                        placeholder_label=resource_label,
                    ),
                    unsafe_allow_html=True,
                )
                action_label = _safe_ui_label("watch_video") if resource_type == "video" else t("start_practice")
                if st.button(
                    f"▶ {action_label}",
                    key=f"student_smart_plan_recommendation_{resource_type}_{item.get('id', idx)}",
                    type="primary",
                    use_container_width=True,
                ):
                    if _open_smart_plan_recommendation(item):
                        log_student_recommendation_open(item, surface="student_smart_plan")
                        go_to("student_practice")
                        st.rerun()


def _render_smart_plan_teacher_summary(
    assignments_override: list[dict] | None = None,
    *,
    render_heading: bool = True,
    render_cta: bool = True,
) -> None:
    assignments = (
        assignments_override
        if assignments_override is not None
        else get_student_assignment_summary(limit=60)
    )
    has_links = bool(assignments_override) or has_active_teacher_relationships()
    if not has_links and not assignments:
        render_empty_state(
            title_key="student_study_plan_teacher_empty_title",
            body_key="student_study_plan_teacher_empty_body",
            steps=[
                "student_study_plan_teacher_empty_step_connect",
                "student_study_plan_teacher_empty_step_assignments",
                "student_study_plan_teacher_empty_step_review",
            ],
            icon="🗂️",
        )
        if st.button(t("student_assignments_empty_find_teacher"), key="smart_plan_empty_find_teacher", use_container_width=True):
            go_to("student_find_teacher")
            st.rerun()
        return

    if render_heading:
        st.markdown(f"### {t('smart_plan_teacher_assignments_title')}")
    if not assignments:
        render_empty_state(
            title_key="student_study_plan_teacher_waiting_title",
            body_key="student_study_plan_teacher_waiting_body",
            steps=[
                "student_study_plan_teacher_empty_step_assignments",
                "student_study_plan_teacher_empty_step_review",
                "student_home_recommendations_empty_step_return",
            ],
            icon="📝",
        )
        return

    if assignments_override is None:
        scope_groups = _assignment_scope_groups(assignments)
        if len(scope_groups) > 1:
            tabs = st.tabs([f"📚 {group.get('label') or ''}" for group in scope_groups])
            for tab, group in zip(tabs, scope_groups):
                with tab:
                    _render_smart_plan_teacher_summary(
                        group.get("rows") or [],
                        render_heading=False,
                        render_cta=False,
                    )
            st.markdown("<div class='classio-smart-teacher-cta-gap'></div>", unsafe_allow_html=True)
            if st.button(
                t("view_all_assignments"),
                key="smart_plan_view_assignments",
                use_container_width=True,
            ):
                go_to("student_assignments")
                st.rerun()
            return

    worksheets = [row for row in assignments if str(row.get("assignment_type") or "").strip() == "worksheet"]
    exams = [row for row in assignments if str(row.get("assignment_type") or "").strip() == "exam"]
    videos = [row for row in assignments if str(row.get("assignment_type") or "").strip() == "video"]

    def _render_teacher_assignment_cards(items: list[dict], empty_icon: str) -> None:
        if not items:
            render_empty_state(
                title_key="student_assignments_group_empty_title",
                body_key="student_assignments_group_empty_body",
                steps=[
                    "student_assignments_group_empty_step_teacher",
                    "student_assignments_group_empty_step_status",
                    "student_assignments_group_empty_step_practice",
                ],
                icon=empty_icon,
            )
            return

        cols = st.columns(min(len(items), 3))
        for col, item in zip(cols, items[:3]):
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

    tab_ws, tab_exams, tab_videos = st.tabs(
        [
            f"📋 {t('worksheet_assignments')} ({len(worksheets)})",
            f"📝 {t('exam_assignments')} ({len(exams)})",
            f"🎬 {t('video_assignments')} ({len(videos)})",
        ]
    )

    with tab_ws:
        _render_teacher_assignment_cards(worksheets, "📋")
    with tab_exams:
        _render_teacher_assignment_cards(exams, "📝")
    with tab_videos:
        _render_teacher_assignment_cards(videos, "🎬")

    if render_cta:
        st.markdown("<div class='classio-smart-teacher-cta-gap'></div>", unsafe_allow_html=True)
        if st.button(t("view_all_assignments"), key="smart_plan_view_assignments", use_container_width=True):
            go_to("student_assignments")
            st.rerun()


def _apply_program_anchor_subject(state: dict, program_anchor: dict | None) -> None:
    if program_anchor:
        anchor_subject = normalize_subject(str(program_anchor.get("subject") or ""))
        if anchor_subject in _smart_plan_subject_options():
            state["subject"] = anchor_subject
        elif program_anchor.get("subject_display"):
            state["subject"] = "other"
            state["custom_subject"] = str(program_anchor.get("subject_display") or "")


def _render_smart_plan_scope(
    program_anchor: dict | None,
    *,
    scope_key: str = "",
) -> None:
    state = _load_smart_plan_state(scope_key)
    _apply_program_anchor_subject(state, program_anchor)
    state, plan_regenerated = _render_smart_plan_setup(
        state,
        program_anchor,
        key_prefix=scope_key,
    )
    if state.get("setup_complete") and not plan_regenerated:
        state = _ensure_today_plan(state, program_anchor)

    if state.get("setup_complete"):
        if program_anchor:
            st.caption(
                f"{program_anchor.get('program_title', t('assigned_learning_program'))} · "
                f"{t('smart_plan_program_anchor_progress', completed=program_anchor.get('completed_topics', 0), total=program_anchor.get('total_topics', 0), percent=program_anchor.get('progress_pct', 0))}"
            )
        _render_smart_plan_progress(state)
        state = _render_smart_plan_today(state, key_prefix=scope_key)
        state["weekly_preview"] = _generate_smart_plan_weekly_preview(
            state["subject"],
            state["goal"],
            int(state["minutes_per_day"]),
            state.get("tasks", []),
            program_anchor,
        )
        state["recommendations"] = _generate_smart_plan_recommendations(
            state,
            _calculate_smart_plan_progress(state.get("tasks", [])),
            program_anchor,
        )
        _render_smart_plan_weekly(state)
        _render_smart_plan_recommendations(state)
    else:
        render_empty_state(
            title_key="student_study_plan_empty_title",
            body_key="student_study_plan_empty_body",
            steps=[
                "student_study_plan_empty_step_setup",
                "student_study_plan_empty_step_daily",
                "student_study_plan_empty_step_recommendations",
            ],
            icon="📚",
        )
    _save_smart_plan_state(state, scope_key)


def _render_lesson_plan_topic_card(row: dict) -> None:
    title = _html.escape(str(row.get("title") or "—").strip() or "—")
    teacher_name = _html.escape(str(row.get("teacher_name") or "—").strip() or "—")
    subject_display = _html.escape(str(row.get("subject_display") or "—").strip() or "—")
    created_at = str(row.get("created_at") or "").strip()
    created_label = created_at[:10] if created_at else "—"
    st.markdown(
        f"""
        <div class="classio-assign-card classio-assign-card--lesson">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;">
                <div>
                    <div class="classio-assign-title">{title}</div>
                    <div class="classio-assign-meta">
                        {teacher_name} · {subject_display} · {_html.escape(t('created_at_label'))}: {_html.escape(created_label)}
                    </div>
                </div>
                <div>
                    <span class="classio-inline-chip">📒 {_html.escape(t('lesson_plan'))}</span>
                    <span class="classio-inline-chip">📌 {_html.escape(t('assigned'))}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_lesson_plan_topics_tab(topic_rows: list[dict]) -> None:
    st.markdown(f"### {t('lesson_plan')}")
    st.caption(t("lesson_plan_topic_student_caption"))
    if not topic_rows:
        render_empty_state(
            title_key="student_lesson_plan_topics_empty_title",
            body_key="student_lesson_plan_topics_empty_body",
            steps=[
                "student_lesson_plan_topics_empty_step_teacher",
                "student_lesson_plan_topics_empty_step_prepare",
                "student_study_plan_programs_empty_step_plan",
            ],
            icon="📒",
        )
        return

    scope_groups = _assignment_scope_groups(topic_rows)
    if len(scope_groups) > 1:
        tabs = st.tabs([f"📚 {group.get('label') or ''}" for group in scope_groups])
        for tab, group in zip(tabs, scope_groups):
            with tab:
                rows = group.get("rows") or []
                page_key = _smart_plan_pagination_key(
                    f"lesson_plan_topics_{group.get('key') or 'scope'}"
                )
                page_rows, *_ = _slice_student_page(rows, page_key, page_size=_LESSON_TOPIC_PAGE_SIZE)
                for row in page_rows:
                    _render_lesson_plan_topic_card(row)
                _render_student_pagination(rows, page_key, page_size=_LESSON_TOPIC_PAGE_SIZE)
        return

    rows = scope_groups[0].get("rows") if scope_groups else topic_rows
    page_key = _smart_plan_pagination_key("lesson_plan_topics")
    page_rows, *_ = _slice_student_page(rows or [], page_key, page_size=_LESSON_TOPIC_PAGE_SIZE)
    for row in page_rows:
        _render_lesson_plan_topic_card(row)
    _render_student_pagination(rows or [], page_key, page_size=_LESSON_TOPIC_PAGE_SIZE)


def render_student_study_plan():
    _inject_smart_plan_styles()
    _inject_assignment_page_styles()
    inject_resource_gallery_styles()
    program_assignments = load_enriched_program_assignments_for_current_student()
    topic_assignments = [
        row
        for row in load_student_assignments()
        if str(row.get("assignment_type") or "").strip() == "lesson_plan_topic"
    ]

    st.markdown(f"## 📚 {t('smart_study_plan')}")
    st.caption(t("smart_plan_page_subtitle"))

    tab_plan, tab_programs, tab_topics = st.tabs(
        [
            f"✨ {t('smart_study_plan')}",
            f"📚 {t('assigned_learning_program')}",
            f"📒 {t('assigned_topics')}",
        ]
    )

    with tab_plan:
        program_groups = _program_subject_groups(program_assignments)
        if len(program_groups) > 1:
            subject_tabs = st.tabs([f"📚 {label}" for _scope, label, _rows in program_groups])
            for subject_tab, (scope_key, _label, scoped_programs) in zip(subject_tabs, program_groups):
                with subject_tab:
                    _render_smart_plan_scope(
                        _build_program_anchor(scoped_programs),
                        scope_key=scope_key,
                    )
        else:
            scoped_programs = program_groups[0][2] if program_groups else program_assignments
            _render_smart_plan_scope(
                _build_program_anchor(scoped_programs),
            )

    with tab_programs:
        if program_assignments:
            render_assigned_learning_programs_section(program_assignments, [])
        else:
            render_empty_state(
                title_key="student_study_plan_programs_empty_title",
                body_key="student_study_plan_programs_empty_body",
                steps=[
                    "student_study_plan_programs_empty_step_teacher",
                    "student_study_plan_programs_empty_step_progress",
                    "student_study_plan_programs_empty_step_plan",
                ],
                icon="📘",
            )
            if st.button(t("student_assignments_empty_find_teacher"), key="smart_plan_programs_find_teacher", use_container_width=True):
                go_to("student_find_teacher")
                st.rerun()

    with tab_topics:
        _render_lesson_plan_topics_tab(topic_assignments)
