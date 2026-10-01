"""Compare default Expo AI user prompts byte-for-byte with Streamlit.

Run from the repository root with
``PYTHONPATH=streamlit .venv/bin/python3 expo/scripts/check-source-prompts.py``.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from helpers.lesson_planner import _build_ai_prompts, _subject_specific_core_keys
from helpers.worksheet_builder import _build_worksheet_prompts
from helpers.quick_exam_builder import _build_exam_prompts

ROOT = Path(__file__).resolve().parents[2]
EXPO = ROOT / "expo"


def source_prompts():
    plan = {"subject": "spanish", "topic": "Past tense", "learner_stage": "adult_stage", "level_or_band": "A2", "lesson_purpose": "practice_skill", "plan_language": "en", "student_material_language": "es", "required_sections": ["title", "objective", "recommended_level", "plan_language", "student_material_language", "success_criteria", "warm_up", "main_activity", "core_examples", "guided_practice", "practice_questions", "freer_task", "wrap_up", "teacher_moves", "extension_task", "homework", "reading_passage", "listening_script", "core_material"], "core_material_required_keys": _subject_specific_core_keys("spanish"), "student_profile": {}}
    worksheet = {"subject": "spanish", "topic": "Past tense", "learner_stage": "adult_stage", "level_or_band": "A2", "worksheet_type": "multiple_choice", "plan_language": "en", "student_material_language": "es", "student_profile": {}}
    exam = {"subject": "spanish", "subject_group": "language", "topic": "Past tense", "exam_title": "Past tense exam", "learner_stage": "adult_stage", "level_or_band": "A2", "exam_length": "short", "exercise_types": ["multiple_choice", "reading_comprehension", "writing_prompt"], "instructions": "", "plan_language": "en", "student_material_language": "es", "student_profile": {}}
    return {"plan": _build_ai_prompts(plan)[1], "worksheet": _build_worksheet_prompts(worksheet)[1], "exam": _build_exam_prompts(exam)[1]}


with tempfile.TemporaryDirectory(prefix="classio-prompt-parity-") as output:
    subprocess.run([
        "npx", "tsc", "--ignoreConfig", "src/server/lesson-plan-prompt.ts", "src/server/worksheet-prompt.ts", "src/server/exam-prompt.ts",
        "--resolveJsonModule", "--esModuleInterop", "--module", "commonjs", "--target", "ES2022", "--skipLibCheck", "--outDir", output,
    ], cwd=EXPO, check=True)
    script = """
const root = process.argv[1];
const plan = require(root + '/lesson-plan-prompt.js').buildLessonPlanUserPrompt({subject:'spanish',topic:'Past tense',learnerStage:'adult_stage',levelOrBand:'A2',lessonPurpose:'practice_skill',planLanguage:'en',studentMaterialLanguage:'es'});
const worksheet = require(root + '/worksheet-prompt.js').buildWorksheetUserPrompt({subject:'spanish',topic:'Past tense',learnerStage:'adult_stage',levelOrBand:'A2',worksheetType:'multiple_choice',planLanguage:'en',studentMaterialLanguage:'es'});
const exam = require(root + '/exam-prompt.js').buildExamUserPrompt({subject:'spanish',topic:'Past tense',examTitle:'Past tense exam',learnerStage:'adult_stage',levelOrBand:'A2',examLength:'short',exerciseTypes:['multiple_choice','reading_comprehension','writing_prompt'],planLanguage:'en',studentMaterialLanguage:'es',instructions:''});
process.stdout.write(JSON.stringify({plan,worksheet,exam}));
"""
    result = subprocess.run(["node", "-e", script, output], cwd=EXPO, check=True, capture_output=True, text=True)
    expo_prompts = json.loads(result.stdout)
    for kind, expected in source_prompts().items():
        if expo_prompts[kind] != expected:
            raise SystemExit(f"{kind} default user prompt differs from Python")
    print("Plan, worksheet, and exam default user prompts match Python byte-for-byte.")
