"""Snapshot deterministic Python profile guidance for the Expo server prompt builder.

Run from the repository root with
``PYTHONPATH=streamlit .venv/bin/python3 expo/scripts/build-generation-guidance.py``.
The source remains read-only; the project virtualenv is needed for full guidance.
"""

import json
from pathlib import Path

from helpers.generation_guidance import build_generation_profile_guidance
from helpers.worksheet_builder import _worksheet_profile_guidance, _worksheet_type_rules, WORKSHEET_TYPES
from helpers.quick_exam_builder import (
    EXAM_EXERCISE_TYPES,
    _exam_profile_guidance,
    _section_type_rules,
    _subject_group_guidance,
    _group_alignment_rules,
    _exam_quality_guardrails,
    _exercise_title,
)

SUBJECTS = ["english", "spanish", "mathematics", "science", "music", "study_skills", "other"]
STAGES = ["early_primary", "upper_primary", "lower_secondary", "upper_secondary", "adult_stage"]
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "beginner_band", "intermediate_band", "advanced_band"]
PRODUCTS = ["lesson_plan", "worksheet", "exam"]

guidance = {
    f"{subject}|{stage}|{level}|{product}": build_generation_profile_guidance(subject, stage, level, product=product)
    for subject in SUBJECTS
    for stage in STAGES
    for level in LEVELS
    for product in PRODUCTS
}
target = Path(__file__).resolve().parents[1] / "src/server/source-generation-guidance.json"
target.write_text(json.dumps(guidance, ensure_ascii=False, separators=(",", ":")) + "\n")

worksheet_profiles = {
    f"{subject}|{stage}|{level}": _worksheet_profile_guidance({
        "subject": subject,
        "learner_stage": stage,
        "level_or_band": level,
    })
    for subject in SUBJECTS
    for stage in STAGES
    for level in LEVELS
}
(target.parent / "source-worksheet-profile-guidance.json").write_text(
    json.dumps(worksheet_profiles, ensure_ascii=False, separators=(",", ":")) + "\n"
)
(target.parent / "source-worksheet-type-rules.json").write_text(
    json.dumps({kind: _worksheet_type_rules(kind) for kind in WORKSHEET_TYPES}, ensure_ascii=False, separators=(",", ":")) + "\n"
)

exam_groups = ["language", "math", "science", "music", "general", "other"]
exam_data = {
    "profiles": {
        f"{subject}|{stage}|{level}": _exam_profile_guidance({
            "subject": subject, "learner_stage": stage, "level_or_band": level,
        })
        for subject in SUBJECTS for stage in STAGES for level in LEVELS
    },
    "type_rules": {
        f"{kind}|{group}": _section_type_rules(kind, subject_group=group)
        for kind in EXAM_EXERCISE_TYPES for group in exam_groups
    },
    "group_guidance": {group: _subject_group_guidance(group) for group in exam_groups},
    "alignment": {group: _group_alignment_rules(group) for group in exam_groups},
    "labels": {kind: _exercise_title(kind) for kind in EXAM_EXERCISE_TYPES},
    "quality_guardrails": _exam_quality_guardrails(),
}
(target.parent / "source-exam-guidance.json").write_text(
    json.dumps(exam_data, ensure_ascii=False, separators=(",", ":")) + "\n"
)
