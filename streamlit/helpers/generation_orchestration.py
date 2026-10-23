from __future__ import annotations

from typing import Any

from helpers.generation_capabilities import (
    GenerationSurfaceCapabilities,
    mark_anonymous_ai_generation,
    resolve_effective_subject,
)


def run_lesson_plan_generation(
    *,
    capabilities: GenerationSurfaceCapabilities,
    mode: str,
    subject: str,
    custom_subject_name: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
    student_profile: dict | None = None,
    anonymous_counter_key: str = "",
) -> dict[str, Any]:
    import helpers.lesson_planner as lp
    from services.ai_economic_events import latest_successful_generation_operation_id

    effective_subject = resolve_effective_subject(subject, custom_subject_name)
    previous_operation_id = latest_successful_generation_operation_id(allow_anonymous=not capabilities.enforce_platform_usage_limits)
    plan, mode_used, warning = lp.generate_quick_lesson_plan_with_fallback(
        mode=mode,
        subject=effective_subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        lesson_purpose=lesson_purpose,
        topic=str(topic or "").strip(),
        student_profile=student_profile or {},
        enforce_usage_limits=capabilities.enforce_platform_usage_limits,
        page_key=capabilities.page_key,
        user_face=capabilities.user_face,
    )
    latest_operation_id = latest_successful_generation_operation_id(allow_anonymous=not capabilities.enforce_platform_usage_limits)
    generation_operation_id = latest_operation_id if mode_used == "ai" and plan and latest_operation_id != previous_operation_id else ""
    if anonymous_counter_key and str(mode).strip().lower() == "ai" and str(mode_used).strip().lower() == "ai" and bool(plan):
        mark_anonymous_ai_generation(anonymous_counter_key)
    return {
        "subject": effective_subject,
        "plan": plan,
        "mode_used": mode_used,
        "warning": warning,
        "generation_operation_id": generation_operation_id,
    }


def run_worksheet_generation(
    *,
    capabilities: GenerationSurfaceCapabilities,
    subject: str,
    custom_subject_name: str,
    learner_stage: str,
    level_or_band: str,
    worksheet_type: str,
    topic: str,
    student_profile: dict | None = None,
    anonymous_counter_key: str = "",
) -> dict[str, Any]:
    from helpers.worksheet_builder import generate_worksheet_with_limit
    from helpers.worksheet_storage import _normalize_worksheet_unicode
    from helpers.visual_support import enrich_worksheet_with_visuals
    from services.ai_economic_events import latest_successful_generation_operation_id

    effective_subject = resolve_effective_subject(subject, custom_subject_name)
    previous_operation_id = latest_successful_generation_operation_id(allow_anonymous=not capabilities.enforce_platform_usage_limits)
    ws, warning = generate_worksheet_with_limit(
        subject=effective_subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        worksheet_type=worksheet_type,
        topic=str(topic or "").strip(),
        student_profile=student_profile or {},
        enforce_usage_limits=capabilities.enforce_platform_usage_limits,
    )
    latest_operation_id = latest_successful_generation_operation_id(allow_anonymous=not capabilities.enforce_platform_usage_limits)
    generation_operation_id = latest_operation_id if ws and latest_operation_id != previous_operation_id else ""
    if anonymous_counter_key and bool(ws):
        mark_anonymous_ai_generation(anonymous_counter_key)
    if ws:
        ws = _normalize_worksheet_unicode(ws)
        ws = enrich_worksheet_with_visuals(
            ws,
            subject=effective_subject,
            learner_stage=learner_stage,
            topic=str(topic or "").strip(),
        )
    return {
        "subject": effective_subject,
        "worksheet": ws,
        "warning": warning,
        "generation_operation_id": generation_operation_id,
    }


def run_exam_generation(
    *,
    capabilities: GenerationSurfaceCapabilities,
    subject: str,
    custom_subject_name: str,
    learner_stage: str,
    level_or_band: str,
    topic: str,
    exam_title: str,
    exam_length: str,
    exercise_types: list[str],
    instructions: str = "",
    student_profile: dict | None = None,
    anonymous_counter_key: str = "",
) -> dict[str, Any]:
    from helpers.quick_exam_builder import _LENGTH_SPEC, generate_exam_with_limit
    from helpers.visual_support import enrich_exam_with_visuals
    from services.ai_economic_events import latest_successful_generation_operation_id

    effective_subject = resolve_effective_subject(subject, custom_subject_name)
    previous_operation_id = latest_successful_generation_operation_id(allow_anonymous=not capabilities.enforce_platform_usage_limits)
    selected_types = list(exercise_types or [])
    length_spec = _LENGTH_SPEC.get(exam_length, _LENGTH_SPEC["medium"])
    max_recommended_sections = int(length_spec.get("sections", len(selected_types) or 1))
    if len(selected_types) > max_recommended_sections:
        selected_types = selected_types[:max_recommended_sections]

    exam_data, answer_key, warning = generate_exam_with_limit(
        subject=effective_subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        topic=str(topic or "").strip(),
        exam_title=exam_title,
        exam_length=exam_length,
        exercise_types=selected_types,
        instructions=instructions,
        student_profile=student_profile or {},
        enforce_usage_limits=capabilities.enforce_platform_usage_limits,
    )
    latest_operation_id = latest_successful_generation_operation_id(allow_anonymous=not capabilities.enforce_platform_usage_limits)
    generation_operation_id = latest_operation_id if exam_data and latest_operation_id != previous_operation_id else ""
    if anonymous_counter_key and bool(exam_data):
        mark_anonymous_ai_generation(anonymous_counter_key)
    if exam_data:
        exam_data = enrich_exam_with_visuals(
            exam_data,
            subject=effective_subject,
            learner_stage=learner_stage,
            topic=str(topic or "").strip(),
        )
    return {
        "subject": effective_subject,
        "exam_data": exam_data,
        "answer_key": answer_key,
        "warning": warning,
        "generation_operation_id": generation_operation_id,
        "exercise_types": selected_types,
    }


def build_learning_program_request_payload(
    *,
    subject: str,
    custom_subject_name: str,
    learner_stage: str,
    level_or_band: str,
    units: int,
    lessons_per_unit: int,
    additional_notes: str,
    capabilities: GenerationSurfaceCapabilities,
    student_native_language: str = "",
    program_track: str = "general_language",
    exam_prep_target: str = "",
    generation_path: str = "standalone",
    parent_program_id: int | None = None,
    sequence_group_id: str = "",
    sequence_order: int | None = None,
    prerequisite_summary: str = "",
    previous_program: dict | None = None,
    visibility: str = "private",
) -> dict[str, Any]:
    payload = {
        "subject": resolve_effective_subject(subject, custom_subject_name),
        "learner_stage": learner_stage,
        "level_or_band": level_or_band,
        "units": int(units),
        "lessons_per_unit": int(lessons_per_unit),
        "additional_notes": str(additional_notes or "").strip(),
        "custom_subject_name": str(custom_subject_name or "").strip(),
    }
    if capabilities.allow_direct_library_save:
        payload.update(
            {
                "visibility": visibility,
                "student_native_language": student_native_language,
                "program_track": program_track,
                "exam_prep_target": exam_prep_target,
                "generation_path": generation_path,
                "parent_program_id": parent_program_id,
                "sequence_group_id": sequence_group_id,
                "sequence_order": sequence_order,
                "prerequisite_summary": prerequisite_summary,
                "previous_program": previous_program,
            }
        )
    return payload
