from __future__ import annotations


_STAGE_AGE_GUIDANCE = {
    "early_primary": "Learners are typically around ages 6 to 8. Keep tone, examples, and task load very concrete and highly scaffolded.",
    "upper_primary": "Learners are typically around ages 9 to 11. Keep materials motivating, concrete, and clearly structured while building independence.",
    "lower_secondary": "Learners are typically around ages 12 to 14. Keep the tone respectful, adolescent, and age-appropriate rather than childish or adult-only.",
    "upper_secondary": "Learners are typically around ages 15 to 18. Keep the work academically stronger, more independent, and aligned to teenage or pre-adult contexts.",
    "adult_stage": "Learners are adults. Keep contexts practical, respectful, and directly useful.",
}


def _learning_programs():
    import helpers.learning_programs as learning_programs

    return learning_programs


def infer_subject_family(subject: str, custom_subject_name: str = "") -> str:
    try:
        return _learning_programs().get_subject_family(subject, custom_subject_name)
    except Exception:
        return "general"


def get_subject_progression_profile(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    custom_subject_name: str = "",
) -> dict:
    try:
        return _learning_programs().get_subject_progression_profile(
            subject,
            learner_stage,
            level_or_band,
            custom_subject_name,
        )
    except Exception:
        family = infer_subject_family(subject, custom_subject_name)
        return {
            "subject": subject,
            "subject_family": family,
            "global_priorities": [],
            "focus_strands": [],
            "sequence_expectations": [],
            "subject_specific_notes": [],
        }


def _level_expectation_lines(subject_family: str, learner_stage: str, level_or_band: str) -> list[str]:
    family = str(subject_family or "general").strip().lower()
    stage = str(learner_stage or "").strip().lower()
    level = str(level_or_band or "").strip()
    lines: list[str] = []

    if family == "language":
        if level == "A1":
            lines.extend([
                "Use very simple, high-frequency language, but keep the situations and names suitable for the learner stage.",
                "Prefer short coherent texts, literal questions, scaffolded speaking, and sentence-to-short-paragraph writing.",
            ])
        elif level == "A2":
            lines.extend([
                "Use clear everyday language with short connected texts, supported inference, and simple opinion or reaction tasks.",
                "Stretch beyond isolated sentences, but keep the texts and outputs manageable.",
            ])
        elif level in {"B1", "B2"}:
            lines.extend([
                "Use more independent explanation, comparison, justification, and extended reading or listening.",
                "Balance fluency and accuracy so tasks feel communicative rather than mechanical.",
            ])
        elif level in {"C1", "C2"}:
            lines.extend([
                "Use sophisticated language demand while keeping contexts age-appropriate for the learner stage.",
                "Expect synthesis, interpretation, and precise expression without defaulting to adult workplace contexts.",
            ])

        if stage == "lower_secondary":
            lines.append("For lower-secondary language learning, avoid primary-style stories, babyish contexts, and adult workplace themes.")

    elif family == "math":
        if level == "beginner_band":
            lines.extend([
                "Prioritize prerequisite repair, concrete representations, and worked examples before abstraction.",
                "Use shorter prompts and explicit scaffolds so confidence can rebuild without lowering the age appropriateness.",
            ])
        elif level == "intermediate_band":
            lines.extend([
                "Focus on core curriculum understanding, accurate method choice, and connected reasoning.",
                "Blend procedural fluency with explanation and application.",
            ])
        elif level == "advanced_band":
            lines.extend([
                "Use richer reasoning, justification, and transfer tasks, but keep the sequence teachable and coherent.",
                "Stretch learners without jumping past the conceptual foundations they still need.",
            ])

    elif family == "science":
        if level == "beginner_band":
            lines.extend([
                "Start with observable phenomena, clear vocabulary, and scaffolded explanation before formal abstraction.",
                "Use practical evidence talk and concrete examples to stabilize understanding.",
            ])
        elif level == "intermediate_band":
            lines.extend([
                "Blend concept understanding, evidence use, and explanation in balanced proportions.",
                "Use practical work or scenarios to connect ideas to formal scientific models.",
            ])
        elif level == "advanced_band":
            lines.extend([
                "Increase demand through data interpretation, model-based explanation, and stronger reasoning.",
                "Keep advanced tasks anchored in conceptual coherence, not just harder terminology.",
            ])

    elif family == "music":
        if level == "beginner_band":
            lines.extend([
                "Consolidate rhythm, notation, listening, and performance confidence through short repeated cycles.",
                "Keep theory tightly connected to hearing and doing.",
            ])
        elif level == "intermediate_band":
            lines.extend([
                "Balance theory, aural work, technique, and performance so the work feels musical, not fragmented.",
                "Use practice cycles that connect notation, listening, and performance.",
            ])
        elif level == "advanced_band":
            lines.extend([
                "Increase independence through interpretation, stylistic awareness, and more demanding theory or repertoire work.",
                "Use critique and reflection to deepen musicianship, not just accuracy.",
            ])

    elif family == "study_skills":
        if level == "beginner_band":
            lines.extend([
                "Start with visible routines, organization, and task initiation before expecting independent strategy choice.",
                "Use real school tasks and concrete rehearsal rather than abstract advice.",
            ])
        elif level == "intermediate_band":
            lines.extend([
                "Build planning, memory strategies, revision, and time management through authentic school demands.",
                "Move from teacher-led structure toward guided independence.",
            ])
        elif level == "advanced_band":
            lines.extend([
                "Use more independent planning, revision systems, and metacognitive evaluation.",
                "Expect students to compare, choose, and adapt strategies for different academic demands.",
            ])

    else:
        if level == "beginner_band":
            lines.extend([
                "Prioritize foundations, confidence, and scaffolded practice before heavier abstraction.",
                "Keep tasks structured, clear, and visibly successful.",
            ])
        elif level == "intermediate_band":
            lines.extend([
                "Balance understanding, application, communication, and retrieval in a coherent sequence.",
                "Keep examples and outputs age-appropriate and purposeful.",
            ])
        elif level == "advanced_band":
            lines.extend([
                "Use more analysis, synthesis, critique, and independent application.",
                "Stretch learners while keeping the sequence teachable and age-appropriate.",
            ])

    return lines


def build_generation_profile_guidance(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    *,
    product: str,
    custom_subject_name: str = "",
) -> str:
    profile = get_subject_progression_profile(subject, learner_stage, level_or_band, custom_subject_name)
    stage = str(learner_stage or "").strip().lower()
    family = profile.get("subject_family") or infer_subject_family(subject, custom_subject_name)
    lines: list[str] = []

    age_line = _STAGE_AGE_GUIDANCE.get(stage)
    if age_line:
        lines.append(f"- {age_line}")

    for priority in (profile.get("global_priorities") or [])[:3]:
        lines.append(f"- {priority}")

    focus_strands = profile.get("focus_strands") or []
    if focus_strands:
        lines.append(f"- Prioritize these focus strands: {', '.join(focus_strands[:6])}.")

    for expectation in (profile.get("sequence_expectations") or [])[:3]:
        lines.append(f"- {expectation}")

    for note in (profile.get("subject_specific_notes") or [])[:2]:
        lines.append(f"- {note}")

    lines.extend(f"- {line}" for line in _level_expectation_lines(family, learner_stage, level_or_band))

    if str(product or "").strip().lower() == "worksheet":
        lines.append("- Make the worksheet feel polished and secondary-ready, not like filler drill sheets.")
    elif str(product or "").strip().lower() == "exam":
        lines.append("- Make the assessment evidence clear, aligned, and fair for the selected stage and level.")
    elif str(product or "").strip().lower() == "lesson_plan":
        lines.append("- Keep the lesson practical for one Classio lesson while preserving the correct stage and level demand.")

    return "\n".join(lines)


def build_expert_panel_prompt_blurb(product: str) -> str:
    product_key = str(product or "").strip().lower()
    role_map = {
        "worksheet": "premium worksheet design",
        "exam": "high-validity assessment design",
        "lesson_plan": "practical one-to-one lesson design",
        "learning_program": "scope-and-sequence and curriculum architecture",
    }
    role_text = role_map.get(product_key, "production-ready educational design")
    return (
        "You are Classio's expert generation panel: a coordinated team of PhD-level professionals in education, "
        "instructional design, assessment, curriculum planning, differentiation, and subject-specific pedagogy. "
        "Act as if a subject specialist, learner-stage specialist, classroom practitioner, and instructional designer "
        f"are jointly reviewing every decision for {role_text}. "
        "Prioritize production-ready teacher usability, accuracy, alignment, age appropriateness, and polished classroom delivery."
    )
