"""Copy the lesson-plan export labels from the read-only Python locale catalogs."""

import json
from pathlib import Path

from translations_en import EN
from translations_es import ES
from translations_tr import TR

keys = ["lesson_overview", "lesson_flow", "teacher_notes", "lesson_materials", "lesson_objective", "success_criteria", "warm_up", "main_activity", "guided_practice", "freer_task", "wrap_up", "core_examples", "practice_questions", "teacher_moves", "extension_task", "optional_homework", "target_vocabulary", "language_frames", "pre_task_questions", "reading_passage", "listening_script", "gist_questions", "detail_questions", "worked_example", "independent_practice", "common_error_alert", "concept_explanation", "real_life_application", "strategy_steps", "performance_goal", "materials_needed", "timing_guide", "expected_output", "differentiation", "assessment_check", "student_checklist", "key_concept", "guided_problem_set", "independent_problem_set", "challenge_problem", "answer_key", "phenomenon_prompt", "prediction_task", "observation_task", "evidence_questions", "misconception_alert", "technical_focus", "practice_pattern", "teacher_model", "strategy_name", "model_scenario", "student_action_plan", "post_task"]
catalog = {language: {key: dictionary[key] for key in keys if key in dictionary} for language, dictionary in [("en", EN), ("es", ES), ("tr", TR)]}
target = Path(__file__).resolve().parents[1] / "src/services/source-document-labels.json"
target.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n")
