// Matches Streamlit's _topic_has_generated_details / _program_is_complete.
type Row = Record<string, unknown>;
const rows = (value: unknown): Row[] => Array.isArray(value) ? value.filter((item): item is Row => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
const populated = (value: unknown) => Array.isArray(value) ? value.length > 0 : typeof value === 'string' && value.trim().length > 0;

export function programUnitReady(unit: Row): boolean {
  const topics = rows(unit.topics);
  return topics.length > 0 && topics.every((topic) => ['learning_objectives', 'success_criteria', 'student_can_do', 'suggested_worksheet_types', 'suggested_exam_exercise_types', 'homework_idea', 'teacher_notes'].some((key) => populated(topic[key])));
}

export function programReady(program: Row): boolean {
  const units = rows(program.units);
  return units.length > 0 && units.every(programUnitReady);
}

export function programProgress(program: Row): { ready: number; total: number } {
  const units = rows(program.units);
  return { ready: units.filter(programUnitReady).length, total: units.length };
}
