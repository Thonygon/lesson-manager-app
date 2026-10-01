from __future__ import annotations

import re
from typing import Any

import streamlit as st

from helpers.generation_guidance import infer_subject_family

PROGRAM_TOPIC_CONTEXT_STATE_KEY = "_program_topic_generation_context"
_HOME_SMART_TOOL_DIALOG_VERSION = 1


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", (), {}):
        return []
    return [value]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = _clean_text(item)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _context_signature(context: dict | None) -> str:
    context = dict(context or {})
    parts = [
        _clean_text(context.get("subject")),
        _clean_text(context.get("custom_subject_name")),
        _clean_text(context.get("program_title")),
        _clean_text(context.get("unit_title")),
        _clean_text(context.get("topic_title")),
        _clean_text(context.get("learner_stage")),
        _clean_text(context.get("level_or_band")),
    ]
    return "||".join(parts)


def _apply_recommended_default_once(state_key: str, value: Any, *, context_signature: str) -> None:
    cleaned_value = _clean_text(value)
    if not state_key or not cleaned_value:
        return
    signature_key = f"_{state_key}_program_topic_default_signature"
    if st.session_state.get(signature_key) != context_signature:
        st.session_state[state_key] = cleaned_value
        st.session_state[signature_key] = context_signature
        return
    if not _clean_text(st.session_state.get(state_key)):
        st.session_state[state_key] = cleaned_value


def _apply_recommended_list_default_once(state_key: str, values: list[str], *, context_signature: str) -> None:
    cleaned_values = [item for item in (_clean_text(value) for value in values) if item]
    if not state_key or not cleaned_values:
        return
    signature_key = f"_{state_key}_program_topic_default_signature"
    current_values = st.session_state.get(state_key)
    normalized_current = [_clean_text(value) for value in _ensure_list(current_values) if _clean_text(value)]
    if st.session_state.get(signature_key) != context_signature:
        st.session_state[state_key] = cleaned_values
        st.session_state[signature_key] = context_signature
        return
    if not normalized_current:
        st.session_state[state_key] = cleaned_values


def _wb():
    import helpers.worksheet_builder as wb

    return wb


def _eb():
    import helpers.quick_exam_builder as eb

    return eb


def _keyword_blob(program: dict, unit: dict | None = None, topic: dict | None = None) -> str:
    bits: list[str] = []
    for item in (
        program.get("title"),
        program.get("program_overview"),
        program.get("teacher_rationale"),
        program.get("assessment_strategy"),
        program.get("resource_strategy"),
        (unit or {}).get("title"),
        (unit or {}).get("overview"),
        (topic or {}).get("title"),
        (topic or {}).get("subtopic"),
        (topic or {}).get("lesson_focus"),
        (topic or {}).get("student_summary"),
    ):
        text = _clean_text(item)
        if text:
            bits.append(text)
    return " ".join(bits).casefold()


def _match_word(blob: str, *patterns: str) -> bool:
    return any(re.search(pattern, blob, flags=re.IGNORECASE) for pattern in patterns)


def infer_exam_prep_family(
    subject: str,
    *,
    program: dict | None = None,
    unit: dict | None = None,
    topic: dict | None = None,
) -> str:
    subject_key = _clean_text(subject).lower().replace(" ", "_")
    if subject_key not in {"english", "spanish"}:
        return ""
    blob = _keyword_blob(program or {}, unit, topic)
    if not blob:
        return ""
    if _match_word(blob, r"\bsat\b", r"\bdigital sat\b", r"\bsat reading\b", r"\bsat writing\b"):
        return "sat_rw"
    if _match_word(blob, r"\bielts academic\b"):
        return "ielts_academic"
    if _match_word(blob, r"\bielts general\b"):
        return "ielts_general"
    if _match_word(blob, r"\bielts\b"):
        return "ielts"
    if _match_word(blob, r"\btoefl\b", r"\btoefl ibt\b", r"\bibt\b"):
        return "toefl_ibt"
    if _match_word(blob, r"\bdele\b", r"\bdiplomas? de espa[ñn]ol\b"):
        return "dele"
    return ""


def _exam_display_name(exam_family: str) -> str:
    labels = {
        "sat_rw": "Digital SAT Reading and Writing",
        "ielts_academic": "IELTS Academic",
        "ielts_general": "IELTS General Training",
        "ielts": "IELTS",
        "toefl_ibt": "TOEFL iBT",
        "dele": "DELE",
    }
    return labels.get(exam_family, "")


def _exam_focus_areas(exam_family: str) -> list[str]:
    mapping = {
        "sat_rw": [
            "Information and Ideas",
            "Craft and Structure",
            "Expression of Ideas",
            "Standard English Conventions",
        ],
        "ielts_academic": [
            "Academic reading accuracy",
            "Task achievement",
            "Coherence and cohesion",
            "Lexical resource and grammar control",
        ],
        "ielts_general": [
            "Everyday and workplace reading",
            "Task response",
            "Coherence and cohesion",
            "Lexical resource and grammar control",
        ],
        "ielts": [
            "Band-appropriate reading and writing control",
            "Coherence and cohesion",
            "Lexical resource",
            "Grammar range and accuracy",
        ],
        "toefl_ibt": [
            "Academic reading",
            "Evidence-based writing",
            "Integrated language use",
            "Concise source-grounded responses",
        ],
        "dele": [
            "Communicative purpose",
            "Register control",
            "Text comprehension",
            "CEFR-aligned language accuracy",
        ],
    }
    return mapping.get(exam_family, [])


def _context_blob(context: dict) -> str:
    bits: list[str] = []
    for item in (
        context.get("program_title"),
        context.get("program_overview"),
        context.get("unit_title"),
        context.get("unit_overview"),
        context.get("topic_title"),
        context.get("topic_subtopic"),
        context.get("topic_summary"),
        " ".join(context.get("topic_learning_objectives") or []),
        " ".join(context.get("topic_success_criteria") or []),
        " ".join(context.get("topic_student_can_do") or []),
        context.get("exam_display_name"),
        " ".join(context.get("exam_focus_areas") or []),
    ):
        text = _clean_text(item)
        if text:
            bits.append(text)
    return " ".join(bits).casefold()


def _boost(scores: dict[str, float], values: list[str], amount: float) -> None:
    for idx, value in enumerate(values):
        key = _clean_text(value)
        if not key:
            continue
        scores[key] = scores.get(key, 0.0) + max(0.2, amount - idx * 0.15)


def _keyword_hits(blob: str, *patterns: str) -> bool:
    return any(re.search(pattern, blob, flags=re.IGNORECASE) for pattern in patterns)


def _boost_by_keywords(scores: dict[str, float], blob: str, *, product: str, subject_family: str, exam_family: str) -> None:
    if product == "worksheet":
        if _keyword_hits(blob, r"\bskim", r"\bscan"):
            _boost(scores, ["reading_comprehension", "multiple_choice", "true_false"], 5.0)
        if _keyword_hits(blob, r"\bskim", r"\bscan", r"\breading\b", r"\bpassage\b", r"\btext\b", r"\bevidence\b", r"\binfer", r"\bcomprehension\b"):
            _boost(scores, ["reading_comprehension", "multiple_choice", "short_answer", "true_false"], 4.8)
        if _keyword_hits(blob, r"\bgrammar\b", r"\bediting\b", r"\berror\b", r"\brevision\b", r"\bconvention", r"\btense\b", r"\bsentence\b"):
            _boost(scores, ["error_correction", "fill_in_the_blanks", "multiple_choice", "short_answer"], 4.6)
        if _keyword_hits(blob, r"\bvocabulary\b", r"\blexic", r"\bword\b", r"\bcollocation\b", r"\bmeaning\b", r"\bcontext\b"):
            _boost(scores, ["multiple_choice", "matching", "fill_in_the_blanks", "word_search_vocab"], 4.2)
        if _keyword_hits(blob, r"\bwriting\b", r"\bparagraph\b", r"\bresponse\b", r"\bcompose\b"):
            _boost(scores, ["short_answer", "fill_in_the_blanks", "error_correction"], 3.8)
        if subject_family == "math":
            _boost(scores, ["short_answer", "multiple_choice", "matching"], 2.4)
            if _keyword_hits(blob, r"\bgraph\b", r"\btable\b", r"\bdata\b"):
                _boost(scores, ["short_answer", "multiple_choice"], 2.2)
        elif subject_family == "science":
            _boost(scores, ["short_answer", "multiple_choice", "matching", "true_false"], 2.4)
            if _keyword_hits(blob, r"\bclassif", r"\bgroup\b", r"\blabel\b", r"\bdiagram\b", r"\bprocess\b"):
                _boost(scores, ["matching", "short_answer", "true_false"], 2.2)
        elif subject_family == "music":
            _boost(scores, ["matching", "multiple_choice", "short_answer"], 2.3)
    else:
        if _keyword_hits(blob, r"\bskim", r"\bscan"):
            _boost(scores, ["reading_comprehension", "multiple_choice", "true_false"], 5.0)
        if _keyword_hits(blob, r"\bskim", r"\bscan", r"\breading\b", r"\bpassage\b", r"\btext\b", r"\bevidence\b", r"\binfer", r"\bcomprehension\b"):
            _boost(scores, ["reading_comprehension", "multiple_choice", "short_answer", "true_false"], 4.8)
        if _keyword_hits(blob, r"\bgrammar\b", r"\bediting\b", r"\berror\b", r"\brevision\b", r"\bconvention", r"\bsentence\b"):
            _boost(scores, ["multiple_choice", "error_correction", "sentence_transformation", "fill_in_blank"], 4.7)
        if _keyword_hits(blob, r"\bvocabulary\b", r"\bword\b", r"\bmeaning\b", r"\bcontext\b", r"\blexic"):
            _boost(scores, ["vocabulary", "multiple_choice", "reading_comprehension"], 4.4)
        if _keyword_hits(blob, r"\bwriting\b", r"\bparagraph\b", r"\bessay\b", r"\bresponse\b", r"\bcoheren"):
            _boost(scores, ["writing_prompt", "short_answer", "sentence_transformation"], 4.2)
        if subject_family == "math":
            _boost(scores, ["problem_solving", "equation_solving", "show_your_work", "word_problems"], 4.0)
            if _keyword_hits(blob, r"\btable\b", r"\bgraph\b", r"\bdata\b"):
                _boost(scores, ["table_interpretation", "data_analysis"], 3.4)
        elif subject_family == "science":
            _boost(scores, ["data_analysis", "classification", "process_explanation", "hypothesis_and_conclusion"], 4.0)
        elif subject_family == "music":
            _boost(scores, ["theory_questions", "symbol_identification", "terminology", "rhythm_counting"], 4.0)

    if exam_family == "sat_rw":
        if product == "worksheet":
            _boost(scores, ["reading_comprehension", "multiple_choice", "error_correction", "short_answer"], 5.8)
            if _keyword_hits(blob, r"\bskim", r"\bscan", r"\breading\b", r"\bpassage\b", r"\bevidence\b", r"\btext\b"):
                _boost(scores, ["reading_comprehension"], 3.0)
            scores["word_search_vocab"] = scores.get("word_search_vocab", 0.0) - 2.0
        else:
            _boost(scores, ["multiple_choice", "reading_comprehension", "error_correction", "sentence_transformation"], 5.2)
    elif exam_family in {"ielts", "ielts_academic", "ielts_general"}:
        if product == "worksheet":
            _boost(scores, ["reading_comprehension", "short_answer", "multiple_choice"], 4.6)
        else:
            _boost(scores, ["reading_comprehension", "short_answer", "writing_prompt", "multiple_choice"], 4.6)
    elif exam_family == "toefl_ibt":
        if product == "worksheet":
            _boost(scores, ["reading_comprehension", "short_answer", "multiple_choice"], 4.6)
        else:
            _boost(scores, ["reading_comprehension", "multiple_choice", "short_answer", "writing_prompt"], 4.8)
    elif exam_family == "dele":
        if product == "worksheet":
            _boost(scores, ["reading_comprehension", "short_answer", "multiple_choice", "error_correction"], 4.6)
        else:
            _boost(scores, ["reading_comprehension", "multiple_choice", "short_answer", "writing_prompt"], 4.7)


def _sorted_recommendations(scores: dict[str, float], allowed: list[str]) -> list[str]:
    allowed_clean = [_clean_text(item) for item in allowed if _clean_text(item)]
    decorated = []
    for idx, item in enumerate(allowed_clean):
        decorated.append((scores.get(item, 0.0), -idx, item))
    decorated.sort(reverse=True)
    return [item for score, _idx, item in decorated if score > 0]


def get_program_topic_recommendation_profile(context: dict | None) -> dict:
    context = dict(context or {})
    if not context:
        return {
            "worksheet_ranked": [],
            "exam_ranked": [],
            "lesson_purpose_ranked": [],
            "worksheet_reason": "",
            "exam_reason": "",
        }

    blob = _context_blob(context)
    subject_family = _clean_text(context.get("subject_family")) or "general"
    exam_family = _clean_text(context.get("exam_family"))
    worksheet_scores = {item: 0.0 for item in _wb().WORKSHEET_TYPES}
    exam_scores = {item: 0.0 for item in _eb().EXAM_EXERCISE_TYPES}

    _boost(worksheet_scores, [str(x) for x in _ensure_list(context.get("suggested_worksheet_types"))], 6.0)
    _boost(exam_scores, [str(x) for x in _ensure_list(context.get("suggested_exam_types"))], 6.0)
    _boost_by_keywords(worksheet_scores, blob, product="worksheet", subject_family=subject_family, exam_family=exam_family)
    _boost_by_keywords(exam_scores, blob, product="exam", subject_family=subject_family, exam_family=exam_family)

    worksheet_ranked = _sorted_recommendations(worksheet_scores, _wb().WORKSHEET_TYPES)
    exam_ranked = _sorted_recommendations(exam_scores, _eb().EXAM_EXERCISE_TYPES)
    lesson_purpose_ranked = [_clean_text(context.get("lesson_purpose"))] if _clean_text(context.get("lesson_purpose")) else []

    reason_bits: list[str] = []
    if _clean_text(context.get("topic_title")):
        reason_bits.append(_clean_text(context.get("topic_title")))
    if _clean_text(context.get("topic_summary")):
        reason_bits.append(_clean_text(context.get("topic_summary")))
    if _clean_text(context.get("exam_display_name")):
        reason_bits.append(_clean_text(context.get("exam_display_name")))
    reason_text = " | ".join(reason_bits[:3])

    return {
        "worksheet_ranked": worksheet_ranked,
        "exam_ranked": exam_ranked,
        "lesson_purpose_ranked": lesson_purpose_ranked,
        "worksheet_reason": reason_text,
        "exam_reason": reason_text,
    }


def build_program_topic_generation_context(
    program: dict,
    unit: dict,
    topic: dict,
    *,
    subject: str = "",
    custom_subject_name: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
) -> dict:
    program = dict(program or {})
    unit = dict(unit or {})
    topic = dict(topic or {})
    topic_title = _clean_text(topic.get("title") or topic.get("lesson_focus"))
    suggested_worksheet_types = _dedupe_keep_order([str(x) for x in _ensure_list(topic.get("suggested_worksheet_types"))])
    suggested_exam_types = _dedupe_keep_order([str(x) for x in _ensure_list(topic.get("suggested_exam_exercise_types"))])
    exam_family = infer_exam_prep_family(
        subject,
        program=program,
        unit=unit,
        topic=topic,
    )
    return {
        "subject": _clean_text(subject),
        "custom_subject_name": _clean_text(custom_subject_name),
        "learner_stage": _clean_text(learner_stage),
        "level_or_band": _clean_text(level_or_band),
        "program_id": int(program.get("id") or 0),
        "subject_family": _clean_text(program.get("subject_family")) or infer_subject_family(subject, custom_subject_name),
        "program_title": _clean_text(program.get("title")),
        "program_overview": _clean_text(program.get("program_overview")),
        "assessment_strategy": _clean_text(program.get("assessment_strategy")),
        "resource_strategy": _clean_text(program.get("resource_strategy")),
        "unit_id": int(unit.get("unit_id") or 0),
        "unit_number": int(unit.get("unit_number") or 0),
        "unit_title": _clean_text(unit.get("title")),
        "unit_overview": _clean_text(unit.get("overview")),
        "topic_id": int(topic.get("topic_id") or 0),
        "topic_number": int(topic.get("topic_number") or 0),
        "topic_title": topic_title,
        "topic_subtopic": _clean_text(topic.get("subtopic")),
        "topic_summary": _clean_text(topic.get("student_summary") or topic.get("lesson_focus") or topic.get("subtopic")),
        "topic_learning_objectives": _dedupe_keep_order([str(x) for x in _ensure_list(topic.get("learning_objectives"))]),
        "topic_success_criteria": _dedupe_keep_order([str(x) for x in _ensure_list(topic.get("success_criteria"))]),
        "topic_student_can_do": _dedupe_keep_order([str(x) for x in _ensure_list(topic.get("student_can_do"))]),
        "lesson_purpose": _clean_text(topic.get("lesson_purpose")),
        "suggested_worksheet_types": suggested_worksheet_types,
        "suggested_exam_types": suggested_exam_types,
        "program_track": "exam_prep" if exam_family else "general_language",
        "exam_family": exam_family,
        "exam_display_name": _exam_display_name(exam_family),
        "exam_focus_areas": _exam_focus_areas(exam_family),
    }


def merge_program_topic_context_into_profile(profile: dict | None, context: dict | None) -> dict:
    merged = dict(profile or {})
    context = dict(context or {})
    if not context:
        return merged

    program_context = dict(merged.get("program_context") or {})
    topic_title = _clean_text(context.get("topic_title"))
    next_topics = _dedupe_keep_order(
        ([topic_title] if topic_title else [])
        + [str(x) for x in _ensure_list(program_context.get("next_topics"))]
    )
    suggested_worksheet_types = _dedupe_keep_order(
        [str(x) for x in _ensure_list(context.get("suggested_worksheet_types"))]
        + [str(x) for x in _ensure_list(program_context.get("suggested_worksheet_types"))]
    )
    suggested_exam_types = _dedupe_keep_order(
        [str(x) for x in _ensure_list(context.get("suggested_exam_types"))]
        + [str(x) for x in _ensure_list(program_context.get("suggested_exam_types"))]
    )

    program_context.update(
        {
            "current_program_title": _clean_text(context.get("program_title")) or _clean_text(program_context.get("current_program_title")),
            "current_unit_title": _clean_text(context.get("unit_title")),
            "current_topic_title": topic_title,
            "topic_summary": _clean_text(context.get("topic_summary")),
            "topic_learning_objectives": _dedupe_keep_order([str(x) for x in _ensure_list(context.get("topic_learning_objectives"))]),
            "topic_success_criteria": _dedupe_keep_order([str(x) for x in _ensure_list(context.get("topic_success_criteria"))]),
            "topic_student_can_do": _dedupe_keep_order([str(x) for x in _ensure_list(context.get("topic_student_can_do"))]),
            "lesson_purpose": _clean_text(context.get("lesson_purpose")),
            "assessment_strategy": _clean_text(context.get("assessment_strategy")),
            "resource_strategy": _clean_text(context.get("resource_strategy")),
            "program_track": _clean_text(context.get("program_track")),
            "exam_family": _clean_text(context.get("exam_family")),
            "exam_display_name": _clean_text(context.get("exam_display_name")),
            "exam_focus_areas": _dedupe_keep_order([str(x) for x in _ensure_list(context.get("exam_focus_areas"))]),
            "next_topics": next_topics,
            "suggested_worksheet_types": suggested_worksheet_types,
            "suggested_exam_types": suggested_exam_types,
        }
    )
    merged["program_context"] = program_context
    if _clean_text(context.get("learner_stage")) and not _clean_text(merged.get("learner_stage")):
        merged["learner_stage"] = _clean_text(context.get("learner_stage"))
    if _clean_text(context.get("level_or_band")) and not _clean_text(merged.get("level_or_band")):
        merged["level_or_band"] = _clean_text(context.get("level_or_band"))

    summary_bits = []
    if topic_title:
        summary_bits.append(f"Current program topic is {topic_title}")
    if _clean_text(context.get("unit_title")):
        summary_bits.append(f"inside {context['unit_title']}")
    if _clean_text(context.get("exam_display_name")):
        summary_bits.append(f"aligned to {context['exam_display_name']}")
    existing_summary = _clean_text(merged.get("summary"))
    context_summary = " ".join(summary_bits).strip()
    if existing_summary and context_summary:
        merged["summary"] = f"{existing_summary}. {context_summary}"
    elif context_summary:
        merged["summary"] = context_summary
    return merged


def build_program_topic_prompt_block(
    profile: dict | None,
    *,
    product: str,
    selected_formats: list[str] | None = None,
) -> str:
    program = dict((profile or {}).get("program_context") or {})
    current_topic = _clean_text(program.get("current_topic_title"))
    if not current_topic:
        return ""
    recommendation_profile = get_program_topic_recommendation_profile(program)
    normalized_selected = [_clean_text(item) for item in (selected_formats or []) if _clean_text(item)]

    lines = [
        "Program-linked resource brief:",
        f"- Anchor this {product.replace('_', ' ')} to the active program topic: {current_topic}",
    ]
    if _clean_text(program.get("current_unit_title")):
        lines.append(f"- Current unit: {_clean_text(program.get('current_unit_title'))}")
    if _clean_text(program.get("current_program_title")):
        lines.append(f"- Learning program: {_clean_text(program.get('current_program_title'))}")
    if _clean_text(program.get("topic_summary")):
        lines.append(f"- Topic focus: {_clean_text(program.get('topic_summary'))}")
    if program.get("topic_learning_objectives"):
        lines.append(f"- Learning objectives: {', '.join(program['topic_learning_objectives'][:4])}")
    if program.get("topic_success_criteria"):
        lines.append(f"- Success criteria: {', '.join(program['topic_success_criteria'][:4])}")
    if _clean_text(program.get("lesson_purpose")) and product == "lesson plan":
        lines.append(f"- Suggested lesson purpose signal: {_clean_text(program.get('lesson_purpose')).replace('_', ' ')}")
    if program.get("suggested_worksheet_types") and product == "worksheet":
        lines.append(f"- Suggested worksheet types from the program: {', '.join(program['suggested_worksheet_types'][:4])}")
    if program.get("suggested_exam_types") and product == "exam":
        lines.append(f"- Suggested exam exercise types from the program: {', '.join(program['suggested_exam_types'][:5])}")
    if recommendation_profile.get("worksheet_ranked") and product == "worksheet":
        lines.append(f"- Best-fit worksheet formats for this topic: {', '.join(recommendation_profile['worksheet_ranked'][:4])}")
    if recommendation_profile.get("exam_ranked") and product == "exam":
        lines.append(f"- Best-fit exam formats for this topic: {', '.join(recommendation_profile['exam_ranked'][:5])}")
    if _clean_text(program.get("resource_strategy")):
        lines.append(f"- Program resource strategy: {_clean_text(program.get('resource_strategy'))}")
    if _clean_text(program.get("assessment_strategy")):
        lines.append(f"- Program assessment strategy: {_clean_text(program.get('assessment_strategy'))}")

    exam_family = _clean_text(program.get("exam_family"))
    if exam_family:
        exam_name = _clean_text(program.get("exam_display_name")) or exam_family.upper()
        lines.append(f"- This program is exam-prep oriented for {exam_name}.")
        focus_areas = [str(x) for x in _ensure_list(program.get("exam_focus_areas"))]
        if focus_areas:
            lines.append(f"- Priority exam focus areas: {', '.join(focus_areas[:4])}")
        lines.extend(_exam_family_guidance(exam_family, product))

    lines.extend(
        [
            "- The output should feel like a deliberate next step in this program, not a generic stand-alone resource.",
            "- Reuse the program's progression logic, terminology, and skill emphasis when shaping the content.",
        ]
    )
    recommended_for_selection: list[str] = []
    if product == "worksheet":
        recommended_for_selection = [str(x) for x in recommendation_profile.get("worksheet_ranked") or []]
    elif product == "exam":
        recommended_for_selection = [str(x) for x in recommendation_profile.get("exam_ranked") or []]
    elif product == "lesson plan":
        recommended_for_selection = [str(x) for x in recommendation_profile.get("lesson_purpose_ranked") or []]
    if normalized_selected and recommended_for_selection:
        selected_overlap = {item.casefold() for item in normalized_selected} & {
            str(item).casefold() for item in recommended_for_selection[: max(1, min(3, len(recommended_for_selection)))]
        }
        if not selected_overlap:
            lines.extend(
                [
                    f"- The chosen {product.replace('_', ' ')} format is less typical for this specific program topic.",
                    "- Keep it pedagogically coherent and still aligned to the program goals, topic focus, and success criteria.",
                    "- Do not force a generic activity pattern that ignores what this topic is really trying to teach.",
                ]
            )
    return "\n".join(lines)


def _exam_family_guidance(exam_family: str, product: str) -> list[str]:
    if exam_family == "sat_rw":
        shared = [
            "- Use realistic digital SAT Reading and Writing-style language demands rather than generic ESL filler.",
            "- Avoid essay-writing tasks unless the teacher explicitly asks for them.",
        ]
        if product == "exam":
            return shared + [
                "- For exams, prefer short passage or passage-pair based multiple-choice items with four plausible options.",
                "- Keep the task style coherent with SAT domains such as Information and Ideas, Craft and Structure, Expression of Ideas, and Standard English Conventions.",
            ]
        return shared + [
            "- Build practice around close reading, revision/editing decisions, vocabulary in context, rhetorical synthesis, and sentence-boundary or grammar control.",
        ]
    if exam_family in {"ielts", "ielts_academic", "ielts_general"}:
        return [
            "- Keep the resource aligned to band-oriented IELTS performance: clarity, coherence, lexical control, and grammar accuracy.",
            "- Use authentic communicative tasks and reading/writing demands instead of isolated grammar drills unless the topic explicitly targets them.",
            "- Maintain realistic exam-prep tone and functional language.",
        ]
    if exam_family == "toefl_ibt":
        return [
            "- Keep the resource academically oriented and evidence-based.",
            "- Prioritise concise source-grounded reasoning, academic vocabulary, and integrated language use.",
            "- Avoid overly casual contexts that would not feel authentic for TOEFL iBT preparation.",
        ]
    if exam_family == "dele":
        return [
            "- Keep the Spanish authentic, register-aware, and communicative.",
            "- Align the resource to CEFR-appropriate DELE-style comprehension, production, and language-use demands.",
            "- Use realistic Spanish-language situations and avoid translated-from-English phrasing.",
        ]
    return []


def get_active_program_topic_context() -> dict:
    return dict(st.session_state.get(PROGRAM_TOPIC_CONTEXT_STATE_KEY) or {})


def render_program_topic_picker(
    *,
    state_prefix: str,
    subject: str,
    custom_subject_name: str = "",
    learner_stage: str = "",
    level_or_band: str = "",
) -> dict:
    from core.i18n import t
    from helpers.learning_programs import load_learning_program, load_my_learning_programs

    canonical_subject = _clean_text(subject).lower().replace(" ", "_")
    selector_key = f"{state_prefix}_use_program_topic"
    enabled = st.toggle(
        t("program_topic_picker_toggle"),
        key=selector_key,
        help=t("program_topic_picker_toggle_help"),
    )
    if not enabled:
        st.session_state.pop(PROGRAM_TOPIC_CONTEXT_STATE_KEY, None)
        return {}

    programs_df = load_my_learning_programs(limit=200)
    if programs_df is None or programs_df.empty:
        st.info(t("program_topic_picker_no_programs"))
        return {}

    filtered = programs_df.copy()
    if "subject" in filtered.columns:
        filtered = filtered[filtered["subject"].fillna("").astype(str).str.lower() == canonical_subject]
    if canonical_subject == "other" and custom_subject_name and "custom_subject_name" in filtered.columns:
        filtered = filtered[
            filtered["custom_subject_name"].fillna("").astype(str).str.casefold()
            == _clean_text(custom_subject_name).casefold()
        ]
    if learner_stage and "learner_stage" in filtered.columns:
        stage_filtered = filtered[filtered["learner_stage"].fillna("").astype(str) == learner_stage]
        if not stage_filtered.empty:
            filtered = stage_filtered

    if filtered.empty:
        st.info(t("program_topic_picker_no_matches"))
        return {}

    program_options = [int(item) for item in filtered["id"].dropna().astype(int).tolist()]
    active_context = get_active_program_topic_context()
    active_program_id = int(active_context.get("program_id") or 0)
    program_key = f"{state_prefix}_program_id"
    previous_program_key = f"_{state_prefix}_previous_program_id"
    if program_key not in st.session_state and active_program_id in program_options:
        st.session_state[program_key] = active_program_id
    if int(st.session_state.get(program_key) or 0) not in program_options and program_options:
        st.session_state[program_key] = program_options[0]
    selected_program_id = st.selectbox(
        t("program_topic_picker_program"),
        program_options,
        format_func=lambda pid: _clean_text(
            filtered.loc[filtered["id"].astype(int) == int(pid), "title"].iloc[0]
        ),
        key=program_key,
    )
    program = load_learning_program(int(selected_program_id)) or {}
    units = program.get("units") or []
    topic_records: list[tuple[str, str, dict, dict]] = []
    for unit in units:
        for topic in unit.get("topics") or []:
            label = (
                f"{_clean_text(unit.get('title'))} · "
                f"{_clean_text(topic.get('title') or topic.get('lesson_focus'))}"
            )
            token = (
                f"{int(unit.get('unit_number') or 0)}::"
                f"{int(topic.get('topic_number') or 0)}::"
                f"{int(topic.get('topic_id') or 0)}::{label}"
            )
            topic_records.append((token, label, unit, topic))
    if not topic_records:
        st.info(t("program_topic_picker_no_topics"))
        return {}

    topic_key = f"{state_prefix}_topic_token"
    previous_program_id = int(st.session_state.get(previous_program_key) or 0)
    if previous_program_id and previous_program_id != int(selected_program_id):
        st.session_state.pop(topic_key, None)
    active_topic_token = ""
    active_program_matches = int(selected_program_id) > 0 and int(active_context.get("program_id") or 0) == int(selected_program_id)
    if active_program_matches:
        for token, _label, unit, topic in topic_records:
            if (
                int(active_context.get("topic_id") or 0) > 0
                and int(topic.get("topic_id") or 0) == int(active_context.get("topic_id") or 0)
            ) or (
                int(unit.get("unit_number") or 0) == int(active_context.get("unit_number") or 0)
                and int(topic.get("topic_number") or 0) == int(active_context.get("topic_number") or 0)
            ):
                active_topic_token = token
                break
    topic_tokens = [item[0] for item in topic_records]
    if topic_key not in st.session_state and active_topic_token:
        st.session_state[topic_key] = active_topic_token
    if st.session_state.get(topic_key) not in topic_tokens and topic_tokens:
        st.session_state[topic_key] = topic_tokens[0]
    selected_topic_token = st.selectbox(
        t("program_topic_picker_topic"),
        topic_tokens,
        format_func=lambda token: next((label for rec_token, label, _unit, _topic in topic_records if rec_token == token), ""),
        key=topic_key,
    )
    st.session_state[previous_program_key] = int(selected_program_id)
    selected_match = next((item for item in topic_records if item[0] == selected_topic_token), None)
    if not selected_match:
        return {}
    _, _label, unit, topic = selected_match
    context = build_program_topic_generation_context(
        program,
        unit,
        topic,
        subject=program.get("subject") or subject,
        custom_subject_name=program.get("custom_subject_name") or custom_subject_name,
        learner_stage=program.get("learner_stage") or learner_stage,
        level_or_band=program.get("level_or_band") or level_or_band,
    )
    st.session_state[PROGRAM_TOPIC_CONTEXT_STATE_KEY] = context
    if _clean_text(context.get("exam_display_name")):
        st.caption(
            t(
                "program_topic_picker_exam_context",
                exam_name=_clean_text(context.get("exam_display_name")),
            )
        )
    elif _clean_text(context.get("program_title")):
        st.caption(
            t(
                "program_topic_picker_program_context",
                program_title=_clean_text(context.get("program_title")),
            )
        )
    return context


def apply_program_topic_form_defaults(
    context: dict | None,
    *,
    stage_key: str,
    level_key: str,
    topic_key: str,
    purpose_key: str = "",
    worksheet_type_key: str = "",
    exam_types_key: str = "",
) -> None:
    context = dict(context or {})
    if not context:
        return
    recommendation_profile = get_program_topic_recommendation_profile(context)
    signature = _context_signature(context)
    learner_stage = _clean_text(context.get("learner_stage"))
    level_or_band = _clean_text(context.get("level_or_band"))
    topic_title = _clean_text(context.get("topic_title"))
    if learner_stage:
        st.session_state[stage_key] = learner_stage
    if level_or_band:
        st.session_state[level_key] = level_or_band
    if topic_title:
        st.session_state[topic_key] = topic_title
    lesson_purpose = _clean_text(context.get("lesson_purpose"))
    ranked_purposes = [str(x) for x in _ensure_list(recommendation_profile.get("lesson_purpose_ranked")) if _clean_text(x)]
    if purpose_key and (ranked_purposes or lesson_purpose):
        _apply_recommended_default_once(
            purpose_key,
            ranked_purposes[0] if ranked_purposes else lesson_purpose,
            context_signature=signature,
        )
    ranked_ws = [str(x) for x in _ensure_list(recommendation_profile.get("worksheet_ranked")) if _clean_text(x)]
    if worksheet_type_key and ranked_ws:
        _apply_recommended_default_once(
            worksheet_type_key,
            ranked_ws[0],
            context_signature=signature,
        )
    ranked_exam = [str(x) for x in _ensure_list(recommendation_profile.get("exam_ranked")) if _clean_text(x)]
    if exam_types_key and ranked_exam:
        _apply_recommended_list_default_once(
            exam_types_key,
            ranked_exam[: min(4, len(ranked_exam))],
            context_signature=signature,
        )


def prime_program_topic_smart_tool(tool_flag: str, context: dict) -> None:
    from core.navigation import clear_smart_tool_result_state

    context = dict(context or {})
    preserved_learning_program_state = {
        key: st.session_state.get(key)
        for key in (
            "quick_learning_program_result",
            "quick_learning_program_mode_used",
            "quick_learning_program_warning",
            "quick_learning_program_meta",
            "quick_learning_program_payload",
            "quick_learning_program_pending_unit",
            "quick_learning_program_saved_program_id",
            "quick_learning_program_generate_requested",
            "quick_learning_program_editing_unit",
        )
        if key in st.session_state
    }
    clear_smart_tool_result_state()
    for key, value in preserved_learning_program_state.items():
        st.session_state[key] = value
    st.session_state[PROGRAM_TOPIC_CONTEXT_STATE_KEY] = context
    st.session_state[tool_flag] = True
    if int(context.get("program_id") or 0) > 0:
        st.session_state["_active_learning_program_workspace"] = {
            "program_id": int(context.get("program_id") or 0),
            "page": str(st.session_state.get("page") or "").strip(),
            "source": "program_topic_tool",
        }
    toggle_key_by_flag = {
        "open_quick_plan_expander": "quick_plan_use_program_topic",
        "open_quick_ws_expander": "quick_ws_use_program_topic",
        "open_quick_exam_expander": "quick_exam_use_program_topic",
    }
    state_prefix_by_flag = {
        "open_quick_plan_expander": "quick_plan",
        "open_quick_ws_expander": "quick_ws",
        "open_quick_exam_expander": "quick_exam",
    }
    toggle_key = toggle_key_by_flag.get(tool_flag)
    if toggle_key:
        st.session_state[toggle_key] = True
    state_prefix = state_prefix_by_flag.get(tool_flag, "")
    if state_prefix:
        program_id = int(context.get("program_id") or 0)
        if program_id > 0:
            st.session_state[f"{state_prefix}_program_id"] = program_id
        topic_token = (
            f"{int(context.get('unit_number') or 0)}::"
            f"{int(context.get('topic_number') or 0)}::"
            f"{int(context.get('topic_id') or 0)}::"
            f"{_clean_text(context.get('unit_title'))} · {_clean_text(context.get('topic_title'))}"
        )
        st.session_state[f"{state_prefix}_topic_token"] = topic_token
    st.session_state["_home_smart_tool_dialog"] = {
        "version": _HOME_SMART_TOOL_DIALOG_VERSION,
        "flag": str(tool_flag or "").strip(),
    }

    subject = _clean_text(context.get("subject")).lower().replace(" ", "_")
    custom_subject_name = _clean_text(context.get("custom_subject_name"))
    learner_stage = _clean_text(context.get("learner_stage"))
    level_or_band = _clean_text(context.get("level_or_band"))
    topic = _clean_text(context.get("topic_title"))
    lesson_purpose = _clean_text(context.get("lesson_purpose")) or "practice_skill"

    if tool_flag == "open_quick_plan_expander":
        st.session_state["quick_plan_subject"] = subject if subject else "other"
        st.session_state["quick_plan_other_subject"] = custom_subject_name
        if learner_stage:
            st.session_state["quick_plan_learner_stage"] = learner_stage
        if level_or_band:
            st.session_state["quick_plan_level"] = level_or_band
        st.session_state["quick_plan_purpose"] = lesson_purpose
        st.session_state["quick_plan_topic"] = topic
    elif tool_flag == "open_quick_ws_expander":
        st.session_state["quick_ws_subject"] = subject if subject else "other"
        st.session_state["ws_other_subject"] = custom_subject_name
        if learner_stage:
            st.session_state["ws_stage"] = learner_stage
        if level_or_band:
            st.session_state["ws_level"] = level_or_band
        if context.get("suggested_worksheet_types"):
            st.session_state["ws_type"] = str(context["suggested_worksheet_types"][0])
        st.session_state["ws_topic"] = topic
    elif tool_flag == "open_quick_exam_expander":
        st.session_state["quick_exam_subject"] = subject if subject else "other"
        st.session_state["exam_other_subject"] = custom_subject_name
        if learner_stage:
            st.session_state["exam_stage"] = learner_stage
        if level_or_band:
            st.session_state["exam_level"] = level_or_band
        st.session_state["quick_exam_topic"] = topic
        if context.get("suggested_exam_types"):
            st.session_state["exam_exercise_types"] = context["suggested_exam_types"][:5]
        st.session_state["quick_exam_title"] = topic
