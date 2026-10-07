// Match the columns populated by Streamlit's _flatten_program_rows.
type RecordValue = Record<string, unknown>;
const string = (value: unknown) => typeof value === 'string' ? value.trim() : '';
const list = (value: unknown) => Array.isArray(value) ? value.map(string).filter(Boolean) : [];
const positiveInt = (value: unknown, fallback: number) => {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : fallback;
};

export function programUnitRow(unit: RecordValue, index: number) {
  const unitNumber = index + 1;
  const topics = Array.isArray(unit.topics) ? unit.topics : [];
  return {
    unit_number: unitNumber,
    title: string(unit.title) || `Unit ${unitNumber}`,
    overview: string(unit.overview) || string(unit.unit_summary),
    unit_objectives: list(unit.unit_objectives).length ? list(unit.unit_objectives) : list(unit.learning_objectives),
    recommended_lesson_purposes: list(unit.recommended_lesson_purposes),
    recommended_worksheet_types: list(unit.recommended_worksheet_types),
    recommended_exam_exercise_types: list(unit.recommended_exam_exercise_types),
    estimated_lessons: positiveInt(unit.estimated_lessons, topics.length || 1),
  };
}

export function programTopicRow(topic: RecordValue, index: number, unitNumber: number) {
  return {
    unit_number: unitNumber,
    topic_number: index + 1,
    title: string(topic.title) || string(topic.topic) || `Topic ${index + 1}`,
    subtopic: string(topic.subtopic),
    lesson_focus: string(topic.lesson_focus) || string(topic.topic) || string(topic.title),
    lesson_purpose: string(topic.lesson_purpose) || 'introduce_concept',
    learning_objectives: list(topic.learning_objectives).length ? list(topic.learning_objectives) : list(topic.objectives),
    success_criteria: list(topic.success_criteria),
    student_can_do: list(topic.student_can_do),
    suggested_worksheet_types: list(topic.suggested_worksheet_types),
    suggested_exam_exercise_types: list(topic.suggested_exam_exercise_types),
    homework_idea: string(topic.homework_idea),
    teacher_notes: string(topic.teacher_notes),
    student_summary: string(topic.student_summary),
    estimated_lessons: positiveInt(topic.estimated_lessons, 1),
  };
}
