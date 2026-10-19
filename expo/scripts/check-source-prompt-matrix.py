"""Compare a local matrix of Expo and Python generation prompts without live AI calls."""

import difflib
import json
import subprocess
import tempfile
from pathlib import Path

from helpers.lesson_planner import _build_ai_prompts, _subject_specific_core_keys
from helpers.quick_exam_builder import _build_exam_prompts
from helpers.worksheet_builder import _build_worksheet_prompts

ROOT = Path(__file__).resolve().parents[2]
EXPO = ROOT / "expo"
SECTIONS = ["title", "objective", "recommended_level", "plan_language", "student_material_language", "success_criteria", "warm_up", "main_activity", "core_examples", "guided_practice", "practice_questions", "freer_task", "wrap_up", "teacher_moves", "extension_task", "homework", "reading_passage", "listening_script", "core_material"]


def cases():
    output = []
    for subject, stage, level in [("spanish", "adult_stage", "A2"), ("mathematics", "upper_primary", "intermediate_band"), ("science", "lower_secondary", "intermediate_band"), ("music", "adult_stage", "beginner_band")]:
        common = {"subject": subject, "topic": "Fractions" if subject == "mathematics" else "Practice topic", "learner_stage": stage, "level_or_band": level, "plan_language": "en", "student_material_language": "es", "student_profile": {}}
        source = {"subject": subject, "topic": common["topic"], "learner_stage": stage, "level_or_band": level, "lesson_purpose": "practice_skill", "plan_language": "en", "student_material_language": "es", "required_sections": SECTIONS, "core_material_required_keys": _subject_specific_core_keys(subject), "student_profile": {}}
        target = {"subject": subject, "topic": common["topic"], "learnerStage": stage, "levelOrBand": level, "lessonPurpose": "practice_skill", "planLanguage": "en", "studentMaterialLanguage": "es"}
        system, user = _build_ai_prompts(source)
        output.append((f"plan/{subject}", "plan", target, system, user))
    for worksheet_type in ("fill_in_the_blanks", "multiple_choice", "matching", "short_answer", "true_false", "reading_comprehension", "error_correction", "word_search_vocab"):
        source = {"subject": "spanish", "topic": "Past tense", "learner_stage": "adult_stage", "level_or_band": "B2", "worksheet_type": worksheet_type, "plan_language": "en", "student_material_language": "es", "student_profile": {}}
        target = {"subject": "spanish", "topic": "Past tense", "learnerStage": "adult_stage", "levelOrBand": "B2", "worksheetType": worksheet_type, "planLanguage": "en", "studentMaterialLanguage": "es"}
        system, user = _build_worksheet_prompts(source)
        output.append((f"worksheet/{worksheet_type}", "worksheet", target, system, user))
    for subject, group, types in [("spanish", "language", ["short_answer", "reading_comprehension", "writing_prompt"]), ("mathematics", "math", ["problem_solving", "equation_solving", "show_your_work"]), ("science", "science", ["data_analysis", "classification", "process_explanation"]), ("music", "music", ["theory_questions", "rhythm_counting", "terminology"])]:
        source = {"subject": subject, "subject_group": group, "topic": "Practice topic", "exam_title": "Practice exam", "learner_stage": "adult_stage", "level_or_band": "B2", "exam_length": "short", "exercise_types": types, "instructions": "", "plan_language": "en", "student_material_language": "es", "student_profile": {}}
        target = {"subject": subject, "topic": "Practice topic", "examTitle": "Practice exam", "learnerStage": "adult_stage", "levelOrBand": "B2", "examLength": "short", "exerciseTypes": types, "instructions": "", "planLanguage": "en", "studentMaterialLanguage": "es"}
        system, user = _build_exam_prompts(source)
        output.append((f"exam/{subject}", "exam", target, system, user))
    return output


with tempfile.TemporaryDirectory(prefix="classio-prompt-matrix-") as output:
    subprocess.run(["npx", "tsc", "--ignoreConfig", "src/server/lesson-plan-prompt.ts", "src/server/worksheet-prompt.ts", "src/server/exam-prompt.ts", "src/server/source-system-prompts.ts", "--resolveJsonModule", "--esModuleInterop", "--module", "commonjs", "--target", "ES2022", "--skipLibCheck", "--outDir", output], cwd=EXPO, check=True)
    matrix = cases()
    script = """
const root = process.argv[1];
const items = JSON.parse(process.argv[2]);
const builders = {
  plan: require(root + '/lesson-plan-prompt.js').buildLessonPlanUserPrompt,
  worksheet: require(root + '/worksheet-prompt.js').buildWorksheetUserPrompt,
  exam: require(root + '/exam-prompt.js').buildExamUserPrompt,
};
const systemPrompt = require(root + '/source-system-prompts.js').sourceSystemPrompt;
process.stdout.write(JSON.stringify(items.map(([kind, input]) => ({system: systemPrompt(kind), user: builders[kind](input)}))));
"""
    result = subprocess.run(["node", "-e", script, output, json.dumps([(kind, target) for _, kind, target, _, _ in matrix])], cwd=EXPO, check=True, capture_output=True, text=True)
    actual = json.loads(result.stdout)
    failures = []
    for (name, _, _, expected_system, expected_user), received in zip(matrix, actual):
        for part, expected in (("system", expected_system), ("user", expected_user)):
            if expected != received[part]:
                difference = "".join(difflib.unified_diff(expected.splitlines(keepends=True), received[part].splitlines(keepends=True), fromfile=f"python/{name}/{part}", tofile=f"expo/{name}/{part}"))
                failures.append(difference[:3000])
    if failures:
        raise SystemExit("Prompt parity failed:\n" + "\n".join(failures[:3]))
    print(f"{len(matrix)} plan, worksheet, and exam system/user prompt fixtures match Python byte-for-byte.")
