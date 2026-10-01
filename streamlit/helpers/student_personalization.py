from __future__ import annotations

from typing import Any

import pandas as pd

from core.database import get_sb, load_profile_row
from core.state import get_current_user_id
from helpers.learning_programs import (
    load_assignment_progress_map,
    load_learning_program,
    load_program_assignments_for_student,
)
from helpers.native_language import NATIVE_LANGUAGE_OPTIONS, is_language_subject, native_language_label, normalize_native_language
from helpers.student_meta import load_students_df


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        return default


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def apply_native_language_context(profile: dict[str, Any] | None, native_language: str = "") -> dict[str, Any]:
    out = dict(profile or {})
    normalized = normalize_native_language(native_language)
    if normalized:
        out["native_language"] = normalized
    return out


_SUBJECT_NORMALIZE = {
    "english": "english", "inglés": "english", "ingilizce": "english",
    "spanish": "spanish", "español": "spanish", "ispanyolca": "spanish",
    "mathematics": "mathematics", "matemáticas": "mathematics", "matematik": "mathematics",
    "math": "mathematics", "maths": "mathematics",
    "science": "science", "ciencias": "science", "fen": "science", "fen_bilimleri": "science",
    "music": "music", "música": "music", "müzik": "music",
    "study_skills": "study_skills", "técnicas_de_estudio": "study_skills",
    "çalışma_becerileri": "study_skills",
    "turkish": "turkish", "turco": "turkish", "türkçe": "turkish",
    "other": "other", "otro": "other", "otra_materia": "other",
    "diğer": "other", "otra": "other",
}


def normalize_subject(raw: str) -> str:
    key = str(raw or "").strip().lower().replace(" ", "_")
    return _SUBJECT_NORMALIZE.get(key, key)


def recommend_default_level(subject: str, learner_stage: str) -> str:
    if normalize_subject(subject) in {"english", "spanish", "turkish"}:
        defaults = {
            "early_primary": "A1",
            "upper_primary": "A1",
            "lower_secondary": "A2",
            "upper_secondary": "B1",
            "adult_stage": "B1",
        }
        return defaults.get(learner_stage, "A1")

    defaults = {
        "early_primary": "beginner_band",
        "upper_primary": "beginner_band",
        "lower_secondary": "intermediate_band",
        "upper_secondary": "intermediate_band",
        "adult_stage": "advanced_band",
    }
    return defaults.get(learner_stage, "beginner_band")


def load_teacher_personalization_students() -> list[dict]:
    students_df = load_students_df()
    if students_df is None or students_df.empty:
        return []

    options: list[dict] = []
    for _, row in students_df.iterrows():
        student_user_id = _clean_text(row.get("linked_student_user_id"))
        if not student_user_id:
            continue
        name = _clean_text(row.get("student"))
        email = _clean_text(row.get("email"))
        label = name
        if email:
            label = f"{label} · {email}"
        options.append(
            {
                "student_user_id": student_user_id,
                "label": label or student_user_id,
                "student_name": name,
                "email": email,
            }
        )

    options.sort(key=lambda item: item["label"].casefold())
    return options


def _load_teacher_assignment_rows(student_user_id: str, subject: str = "") -> list[dict]:
    teacher_id = _clean_text(get_current_user_id())
    if not teacher_id or not student_user_id:
        return []
    try:
        query = (
            get_sb()
            .table("teacher_assignments")
            .select("*")
            .eq("teacher_id", teacher_id)
            .eq("student_id", _clean_text(student_user_id))
            .neq("status", "archived")
            .order("updated_at", desc=True)
            .limit(200)
        )
        if subject:
            query = query.eq("subject_key", normalize_subject(subject))
        return _rows(query.execute())
    except Exception:
        return []


def _load_teacher_attempt_rows(student_user_id: str) -> list[dict]:
    teacher_id = _clean_text(get_current_user_id())
    if not teacher_id or not student_user_id:
        return []
    try:
        return _rows(
            get_sb()
            .table("teacher_assignment_attempts")
            .select("*")
            .eq("teacher_id", teacher_id)
            .eq("student_id", _clean_text(student_user_id))
            .order("created_at", desc=True)
            .limit(300)
            .execute()
        )
    except Exception:
        return []


def _build_program_context(student_user_id: str, subject: str = "") -> dict[str, Any]:
    context = {
        "active_program_subjects": [],
        "next_topics": [],
        "suggested_worksheet_types": [],
        "suggested_exam_types": [],
        "current_program_title": "",
    }
    assignments_df = load_program_assignments_for_student(student_user_id=student_user_id)
    if assignments_df is None or assignments_df.empty:
        return context

    for _, row in assignments_df.iterrows():
        program_id = _safe_int(row.get("program_id"))
        assignment_id = _safe_int(row.get("id"))
        if program_id <= 0 or assignment_id <= 0:
            continue
        program = load_learning_program(program_id)
        if not program:
            continue
        program_subject = normalize_subject(program.get("subject"))
        if subject and program_subject and program_subject != normalize_subject(subject):
            continue
        if not context["current_program_title"]:
            context["current_program_title"] = _clean_text(program.get("title"))
        if program_subject and program_subject not in context["active_program_subjects"]:
            context["active_program_subjects"].append(program_subject)

        progress_map = load_assignment_progress_map(assignment_id)
        for unit in program.get("units") or []:
            for topic in unit.get("topics") or []:
                topic_id = _safe_int(topic.get("topic_id"))
                if topic_id and bool(progress_map.get(topic_id, {}).get("teacher_done")):
                    continue
                title = _clean_text(topic.get("title"))
                if title and title not in context["next_topics"]:
                    context["next_topics"].append(title)
                for worksheet_type in topic.get("suggested_worksheet_types") or []:
                    cleaned = _clean_text(worksheet_type)
                    if cleaned and cleaned not in context["suggested_worksheet_types"]:
                        context["suggested_worksheet_types"].append(cleaned)
                for exam_type in topic.get("suggested_exam_exercise_types") or []:
                    cleaned = _clean_text(exam_type)
                    if cleaned and cleaned not in context["suggested_exam_types"]:
                        context["suggested_exam_types"].append(cleaned)
                if len(context["next_topics"]) >= 5:
                    return context
    return context


def build_student_generation_profile(student_user_id: str, subject: str = "") -> dict[str, Any]:
    student_user_id = _clean_text(student_user_id)
    if not student_user_id:
        return {}

    student_profile = load_profile_row(student_user_id)
    local_student_row = {}
    try:
        students_df = load_students_df()
        if students_df is not None and not students_df.empty and "linked_student_user_id" in students_df.columns:
            matches = students_df[students_df["linked_student_user_id"].astype(str) == student_user_id]
            if not matches.empty:
                local_student_row = matches.iloc[0].to_dict()
    except Exception:
        local_student_row = {}
    subject_key = normalize_subject(subject) if subject else ""
    assignment_rows = _load_teacher_assignment_rows(student_user_id, subject=subject_key)
    attempt_rows = _load_teacher_attempt_rows(student_user_id)
    program_context = _build_program_context(student_user_id, subject=subject_key)

    subject_attempt_rows = []
    relevant_assignment_ids = {
        _safe_int(row.get("id"))
        for row in assignment_rows
        if _safe_int(row.get("id")) > 0
    }
    for row in attempt_rows:
        assignment_id = _safe_int(row.get("assignment_id"))
        if relevant_assignment_ids and assignment_id not in relevant_assignment_ids:
            continue
        subject_attempt_rows.append(row)

    weak_topics: list[str] = []
    weak_formats: list[str] = []
    strong_topics: list[str] = []
    topic_scores: dict[str, list[float]] = {}
    format_scores: dict[str, list[float]] = {}

    for row in assignment_rows:
        topic = _clean_text(row.get("topic"))
        assignment_type = _clean_text(row.get("assignment_type"))
        score = _safe_float(row.get("score_pct"), default=-1.0)
        if topic and score >= 0:
            topic_scores.setdefault(topic, []).append(score)
        if assignment_type and score >= 0:
            format_scores.setdefault(assignment_type, []).append(score)

    for row in subject_attempt_rows:
        score = _safe_float(row.get("score_pct"), default=-1.0)
        if score < 0:
            continue
        source_type = _clean_text(row.get("source_type"))
        if source_type:
            format_scores.setdefault(source_type, []).append(score)

    averaged_topics = [
        (topic, sum(scores) / len(scores))
        for topic, scores in topic_scores.items()
        if scores
    ]
    averaged_topics.sort(key=lambda item: item[1])
    weak_topics = [topic for topic, _score in averaged_topics[:3]]
    strong_topics = [topic for topic, score in sorted(averaged_topics, key=lambda item: item[1], reverse=True)[:2] if score >= 80]

    averaged_formats = [
        (fmt, sum(scores) / len(scores))
        for fmt, scores in format_scores.items()
        if scores
    ]
    averaged_formats.sort(key=lambda item: item[1])
    weak_formats = [fmt for fmt, _score in averaged_formats[:3]]

    completed_count = sum(1 for row in assignment_rows if _clean_text(row.get("status")) == "completed")
    active_topics = [_clean_text(row.get("topic")) for row in assignment_rows if _clean_text(row.get("status")) in {"assigned", "started", "submitted"} and _clean_text(row.get("topic"))]

    primary_subjects = [normalize_subject(value) for value in (student_profile.get("primary_subjects") or []) if _clean_text(value)]
    learner_stage = ""
    inferred_level = ""

    for row in assignment_rows:
        snapshot = row.get("content_snapshot") or {}
        meta = snapshot.get("meta") if isinstance(snapshot, dict) else {}
        learner_stage = learner_stage or _clean_text((meta or {}).get("learner_stage"))
        inferred_level = inferred_level or _clean_text((meta or {}).get("level_or_band"))

    if not inferred_level:
        if subject_key:
            learner_stage = learner_stage or "lower_secondary"
            inferred_level = recommend_default_level(subject_key, learner_stage)

    overall_average = 0.0
    scored_rows = [row for row in subject_attempt_rows if _safe_float(row.get("score_pct"), default=-1.0) >= 0]
    if scored_rows:
        overall_average = sum(_safe_float(row.get("score_pct")) for row in scored_rows) / len(scored_rows)
    elif averaged_topics:
        overall_average = sum(score for _topic, score in averaged_topics) / len(averaged_topics)

    display_name = _clean_text(student_profile.get("display_name") or student_profile.get("username") or student_profile.get("email"))
    summary_parts = []
    if weak_topics:
        summary_parts.append(f"Needs reinforcement in {', '.join(weak_topics[:2])}")
    if weak_formats:
        pretty_formats = [fmt.replace("_", " ") for fmt in weak_formats[:2]]
        summary_parts.append(f"Benefits from more support through {', '.join(pretty_formats)}")
    if program_context.get("next_topics"):
        summary_parts.append(f"Current program is moving into {program_context['next_topics'][0]}")
    if overall_average:
        summary_parts.append(f"Recent average performance is {round(overall_average)}%")

    return {
        "student_user_id": student_user_id,
        "student_name": display_name,
        "native_language": normalize_native_language(
            local_student_row.get("native_language") or student_profile.get("native_language")
        ),
        "subject_focus": subject_key,
        "primary_subjects": primary_subjects,
        "learner_stage": learner_stage,
        "level_or_band": inferred_level,
        "weak_topics": weak_topics,
        "strong_topics": strong_topics,
        "weak_formats": weak_formats,
        "active_assignment_topics": active_topics[:5],
        "completed_assignments": completed_count,
        "recent_average_score_pct": round(overall_average, 1) if overall_average else 0.0,
        "program_context": program_context,
        "summary": ". ".join(summary_parts),
    }


def build_student_profile_prompt_block(
    profile: dict[str, Any],
    *,
    product: str = "general",
    selected_formats: list[str] | None = None,
) -> str:
    if not profile:
        return ""

    program = profile.get("program_context") or {}
    normalized_selected_formats = [
        _clean_text(item).replace("-", "_").casefold()
        for item in (selected_formats or [])
        if _clean_text(item)
    ]
    include_format_hints = product == "lesson_plan" or not normalized_selected_formats
    lines = [
        "Student personalization profile:",
        f"- Student: {_clean_text(profile.get('student_name')) or 'Selected student'}",
    ]
    if _clean_text(profile.get("learner_stage")):
        lines.append(f"- Learner stage signal: {_clean_text(profile.get('learner_stage'))}")
    if _clean_text(profile.get("level_or_band")):
        lines.append(f"- Level signal: {_clean_text(profile.get('level_or_band'))}")
    native_language = normalize_native_language(profile.get("native_language"))
    if native_language:
        lines.append(f"- Student native language/background: {native_language_label(native_language)}")
    if profile.get("weak_topics"):
        lines.append(f"- Priority weak topics: {', '.join(profile['weak_topics'][:3])}")
    if include_format_hints and profile.get("weak_formats"):
        pretty_formats = [str(item).replace("_", " ") for item in profile["weak_formats"][:3]]
        lines.append(f"- Formats needing support: {', '.join(pretty_formats)}")
    if profile.get("strong_topics"):
        lines.append(f"- Stronger topics to build on: {', '.join(profile['strong_topics'][:2])}")
    if profile.get("recent_average_score_pct"):
        lines.append(f"- Recent scored work average: {profile['recent_average_score_pct']}%")
    if program.get("current_program_title"):
        lines.append(f"- Active learning program: {_clean_text(program.get('current_program_title'))}")
    if program.get("next_topics"):
        lines.append(f"- Upcoming program topics: {', '.join(program['next_topics'][:4])}")
    if include_format_hints and program.get("suggested_worksheet_types"):
        lines.append(f"- Program-suggested worksheet types: {', '.join(program['suggested_worksheet_types'][:4])}")
    if include_format_hints and program.get("suggested_exam_types"):
        lines.append(f"- Program-suggested exam exercise types: {', '.join(program['suggested_exam_types'][:4])}")
    if profile.get("summary"):
        lines.append(f"- Personalization summary: {_clean_text(profile.get('summary'))}")
    lines.extend(
        [
            "- Use this profile to calibrate difficulty, scaffolding, and focus.",
            "- Target the student's real needs instead of generating a generic resource.",
            "- Prefer resources that help the student overcome current difficulties while still moving toward the next level.",
        ]
    )
    if native_language:
        lines.extend(
            [
                "- Use the student's native language as background for explanations, examples, cognates, false friends, and support choices.",
                "- For beginner/A1/A2 or low-confidence language work, add brief native-language support only when it helps access the task.",
                "- Do not over-translate higher-level materials; keep the requested student material language as the main language.",
            ]
        )
    if product in {"worksheet", "exam"}:
        lines.extend(
            [
                "- Personalize topic emphasis, scaffolding, wording, and support level without changing the requested resource format.",
                "- Keep the selected worksheet type or exam section types exactly as requested.",
                "- Do not invent alternative exercise formats just because the student profile mentions other needs.",
            ]
        )
    elif product == "lesson_plan":
        lines.append("- Use the profile to differentiate pacing, modelling, guided practice, and extension inside the requested lesson purpose.")
    return "\n".join(lines)
