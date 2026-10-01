import guidance from './source-generation-guidance.json';

// Keep the payload and user message aligned with
// streamlit/helpers/lesson_planner.py:generate_ai_lesson_plan/_build_ai_prompts.
const REQUIRED_SECTIONS = ['title', 'objective', 'recommended_level', 'plan_language', 'student_material_language', 'success_criteria', 'warm_up', 'main_activity', 'core_examples', 'guided_practice', 'practice_questions', 'freer_task', 'wrap_up', 'teacher_moves', 'extension_task', 'homework', 'reading_passage', 'listening_script', 'core_material'];
const COMMON_CORE = ['materials_needed', 'timing_guide', 'expected_output', 'differentiation'];
const SPECIFIC_CORE: Record<string, string[]> = {
  language: ['target_vocabulary', 'language_frames', 'pre_task_questions', 'gist_questions', 'detail_questions', 'post_task', 'assessment_check', 'student_checklist'],
  math: ['key_concept', 'worked_example', 'guided_problem_set', 'independent_problem_set', 'challenge_problem', 'answer_key', 'common_error_alert', 'assessment_check'],
  science: ['phenomenon_prompt', 'prediction_task', 'concept_explanation', 'observation_task', 'real_life_application', 'evidence_questions', 'misconception_alert', 'assessment_check'],
  music: ['technical_focus', 'practice_pattern', 'teacher_model', 'performance_goal', 'student_checklist'],
  study_skills: ['strategy_name', 'strategy_steps', 'model_scenario', 'student_action_plan', 'student_checklist'],
  general: ['assessment_check'],
};

export type LessonPlanPromptInput = { subject: string; topic: string; learnerStage: string; levelOrBand: string; lessonPurpose: string; planLanguage: string; studentMaterialLanguage: string; studentProfile?: Record<string, unknown>; programContextBlock?: string; studentProfileBlock?: string };

export function buildLessonPlanUserPrompt(input: LessonPlanPromptInput) {
  const subject = input.subject.trim().toLowerCase().replaceAll(' ', '_');
  const engine = ['english', 'spanish'].includes(subject) ? 'language' : subject === 'mathematics' ? 'math' : SPECIFIC_CORE[subject] ? subject : 'general';
  const payload = {
    subject: input.subject,
    topic: input.topic,
    learner_stage: input.learnerStage,
    level_or_band: input.levelOrBand,
    lesson_purpose: input.lessonPurpose,
    plan_language: input.planLanguage,
    student_material_language: input.studentMaterialLanguage,
    required_sections: REQUIRED_SECTIONS,
    core_material_required_keys: [...COMMON_CORE, ...SPECIFIC_CORE[engine]],
    student_profile: input.studentProfile || {},
  };
  const profileGuidance = (guidance as Record<string, string>)[`${subject}|${input.learnerStage}|${input.levelOrBand}|lesson_plan`] || '';
  const studentProfileBlock = input.studentProfileBlock || '';
  const programContextBlock = input.programContextBlock || '';
  return `
Create one complete lesson plan as JSON.

Planner input:
${JSON.stringify(payload, null, 2)}

Rules:
- Return JSON only.
- Include all required_sections.
- Use empty string "" or empty list [] if a section is not needed.
- success_criteria must be a list of strings.
- warm_up, main_activity, core_examples, guided_practice, practice_questions, freer_task, wrap_up, teacher_moves must be lists of strings.
- extension_task and homework must be strings.
- core_material must be an object with subject-appropriate keys.
- Student-facing text must stay in the requested student_material_language.
- Do not mix scripts or inject stray characters from unrelated languages into student-facing content.
- If the lesson is reading-focused, include a reading_passage.
- If the lesson is listening-focused, include a listening_script.
- The JSON must match the planner structure exactly.

Profile quality guidance:
${profileGuidance}

${studentProfileBlock}

${programContextBlock}
`;
}
