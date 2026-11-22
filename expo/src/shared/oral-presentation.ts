import catalog from './oral-exercises.json';

export type OralFamily = keyof typeof catalog.families;
export type OralCriterion = { id: string; label: string; max_score: number };
export type OralDocument = {
  title: string; subject: string; topic: string; objective: string; exercise_type: string;
  student_instructions: string; stimulus: string; expected_response: string;
  max_duration_seconds: number; success_criteria: string[]; rubric: OralCriterion[];
  teacher_notes: string; plan_language: string; student_material_language: string;
};
const RUBRIC: Record<OralFamily, string[]> = {
  language: ['Task achievement', 'Fluency', 'Accuracy', 'Vocabulary', 'Intelligibility'],
  mathematics: ['Reasoning', 'Conceptual accuracy', 'Mathematical communication', 'Clarity'],
  science: ['Scientific accuracy', 'Evidence', 'Reasoning', 'Clarity'],
  music: ['Performance accuracy', 'Interpretation', 'Musical understanding'],
  study_skills: ['Reflection', 'Strategy', 'Justification', 'Application'],
  general: ['Task achievement', 'Evidence', 'Organization', 'Clarity'],
};
export function oralFamily(subject: string): OralFamily {
  const key = subject.trim().toLowerCase().replaceAll('_', ' ');
  if (['english', 'spanish', 'turkish', 'language', 'languages', 'inglés', 'español', 'türkçe'].includes(key)) return 'language';
  if (['mathematics', 'math', 'matemáticas', 'matematik'].includes(key)) return 'mathematics';
  if (['science', 'ciencias', 'fen bilimleri'].includes(key)) return 'science';
  if (['music', 'música', 'müzik'].includes(key)) return 'music';
  if (['study skills', 'study strategies', 'habilidades de estudio', 'çalışma becerileri'].includes(key)) return 'study_skills';
  return 'general';
}
export function oralExercises(family: OralFamily) { return catalog.families[family] as string[]; }
export function oralExerciseLabel(id: string, language: 'en' | 'es' | 'tr' = 'en') {
  const labels = catalog.labels as Record<string, string[]>;
  return labels[id]?.[{ en: 0, es: 1, tr: 2 }[language]] || id.replaceAll('_', ' ');
}
export function defaultOralRubric(family: OralFamily): OralCriterion[] {
  return RUBRIC[family].map((label) => ({ id: label.toLowerCase().replaceAll(' ', '_'), label, max_score: 4 }));
}
const STIMULUS_REQUIRED = new Set(['read_aloud', 'read_and_answer', 'picture_description', 'story_retelling', 'oral_summary', 'solve_and_explain', 'mathematical_error_analysis', 'compare_solution_methods', 'claim_evidence_reasoning', 'explain_experiment', 'present_hypothesis', 'aural_response', 'historical_argument', 'project_defense']);
export function oralTemplateAvailable(exerciseType: string): boolean { return !STIMULUS_REQUIRED.has(exerciseType); }
export function oralTemplate(input: { subject: string; topic: string; objective: string; exerciseType: string; maxDurationSeconds: number; instructions?: string; planLanguage: string; studentLanguage: string }): OralDocument {
  const family = oralFamily(input.subject);
  if (!oralExercises(family).includes(input.exerciseType)) throw new Error('Choose an oral exercise for the selected subject.');
  if (!oralTemplateAvailable(input.exerciseType)) throw new Error('This exercise needs AI-generated supporting content.');
  if (!input.topic.trim() || !input.objective.trim()) throw new Error('A topic and learning objective are required.');
  const label = oralExerciseLabel(input.exerciseType, input.studentLanguage === 'es' ? 'es' : input.studentLanguage === 'tr' ? 'tr' : 'en');
  const studentInstructions = input.studentLanguage === 'es' ? `Graba una respuesta oral sobre ${input.topic}. ${input.instructions || 'Explica tu idea y da al menos un ejemplo.'}` : input.studentLanguage === 'tr' ? `${input.topic} hakkında sözlü bir yanıt kaydet. ${input.instructions || 'Düşünceni açıkla ve en az bir örnek ver.'}` : `Record a spoken response about ${input.topic}. ${input.instructions || 'Explain your idea and give at least one example.'}`;
  return { title: `${label}: ${input.topic}`, subject: input.subject, topic: input.topic, objective: input.objective, exercise_type: input.exerciseType, student_instructions: studentInstructions, stimulus: '', expected_response: input.studentLanguage === 'es' ? 'Respuesta oral con explicación y ejemplo.' : input.studentLanguage === 'tr' ? 'Açıklama ve örnek içeren sözlü yanıt.' : 'A spoken explanation with an example.', max_duration_seconds: input.maxDurationSeconds, success_criteria: defaultOralRubric(family).map((criterion) => criterion.label), rubric: defaultOralRubric(family), teacher_notes: '', plan_language: input.planLanguage, student_material_language: input.studentLanguage };
}
export function oralDocumentIssues(value: Record<string, unknown>, family: OralFamily, selectedType: string): string[] {
  const issues: string[] = [];
  const required = ['title', 'subject', 'topic', 'objective', 'student_instructions', 'expected_response'];
  for (const field of required) if (typeof value[field] !== 'string' || !(value[field] as string).trim()) issues.push(`${field} is required`);
  if (value.exercise_type !== selectedType || !oralExercises(family).includes(selectedType)) issues.push('Exercise type does not match the selected family');
  if (STIMULUS_REQUIRED.has(selectedType) && (typeof value.stimulus !== 'string' || !value.stimulus.trim())) issues.push('Supporting content is required for this exercise');
  if (!Number.isSafeInteger(value.max_duration_seconds) || Number(value.max_duration_seconds) < 30 || Number(value.max_duration_seconds) > 600) issues.push('Recording duration must be 30–600 seconds');
  if (!Array.isArray(value.success_criteria) || !value.success_criteria.length || value.success_criteria.some((item: unknown) => typeof item !== 'string' || !item.trim())) issues.push('Success criteria are required');
  const rubric = value.rubric;
  if (!Array.isArray(rubric) || rubric.length < 2 || rubric.length > 8 || rubric.some((criterion: unknown) => !criterion || typeof criterion !== 'object' || typeof (criterion as OralCriterion).label !== 'string' || !(criterion as OralCriterion).label.trim() || !Number.isInteger((criterion as OralCriterion).max_score) || (criterion as OralCriterion).max_score < 1 || (criterion as OralCriterion).max_score > 20)) issues.push('Rubric needs 2–8 valid criteria');
  if (Array.isArray(rubric) && rubric.some((criterion: unknown) => !criterion || typeof criterion !== 'object' || !/^[a-z][a-z0-9_]{1,49}$/.test(String((criterion as OralCriterion).id || '')))) issues.push('Rubric criteria need stable IDs');
  if (Array.isArray(rubric) && new Set(rubric.map((criterion: OralCriterion) => criterion.id)).size !== rubric.length) issues.push('Rubric criterion IDs must be unique');
  return issues;
}
