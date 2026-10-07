// Source: summarize_previous_program_context in streamlit/helpers/learning_programs.py.
type Row = Record<string, unknown>;
const row = (value: unknown): Row => value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {};
const rows = (value: unknown): Row[] => Array.isArray(value) ? value.map(row).filter((item) => Object.keys(item).length > 0) : [];
const value = (item: unknown): string => typeof item === 'string' ? item.trim() : '';
const list = (item: unknown): string[] => Array.isArray(item) ? item.map(value).filter(Boolean) : [];

export function summarizePreviousProgram(program: Row): Row {
  const units = rows(program.units);
  const topicTitles = units.flatMap((unit) => rows(unit.topics).map((topic) => value(topic.title)).filter(Boolean));
  const finalUnit = units.find((unit) => Number(unit.unit_number) === units.length);
  return {
    title: value(program.title), subject: value(program.subject), subject_display: value(program.subject_display), learner_stage: value(program.learner_stage), level_or_band: value(program.level_or_band),
    entry_profile: value(program.entry_profile), exit_profile: value(program.exit_profile), scope_and_sequence_rationale: value(program.scope_and_sequence_rationale),
    core_progression_priorities: list(program.core_progression_priorities), best_practice_frameworks: list(program.best_practice_frameworks),
    units_count: units.length, topics_count: topicTitles.length, topics_already_covered: topicTitles.slice(0, 120),
    final_topics: finalUnit ? rows(finalUnit.topics).map((topic) => value(topic.title)).filter(Boolean).slice(0, 25) : [], teacher_rationale: value(program.teacher_rationale),
  };
}

export function previousProgramFromStorage(stored: Row): Row {
  const data = row(stored.program_data);
  return { ...data, title: value(data.title) || value(stored.title), subject: value(stored.subject), subject_display: value(stored.custom_subject_name) || value(stored.subject).replaceAll('_', ' '), learner_stage: value(stored.learner_stage), level_or_band: value(stored.level_or_band) };
}

// Streamlit updates the normalized unit/topic rows as well as program_data. For
// older programs the latter can lag behind the rows the teacher last edited.
export function mergePreviousProgramRows(program: Row, unitRows: unknown, topicRows: unknown): Row {
  const units = rows(program.units);
  const savedUnits = rows(unitRows);
  const savedTopics = rows(topicRows);
  if (!savedUnits.length && !savedTopics.length) return program;
  const number = (item: Row, key: string) => Number(item[key]) || 0;
  const unitNumbers = new Set([...units.map((unit) => number(unit, 'unit_number')), ...savedUnits.map((unit) => number(unit, 'unit_number')), ...savedTopics.map((topic) => number(topic, 'unit_number'))].filter((n) => n > 0));
  const mergedUnits = [...unitNumbers].sort((a, b) => a - b).map((unitNumber) => {
    const original = units.find((unit) => number(unit, 'unit_number') === unitNumber) || {};
    const saved = savedUnits.find((unit) => number(unit, 'unit_number') === unitNumber) || {};
    const baseTopics = rows(original.topics).map((topic, index) => ({ ...topic, topic_number: number(topic, 'topic_number') || index + 1 }));
    const matchingTopics = savedTopics.filter((topic) => number(topic, 'unit_number') === unitNumber);
    const topicNumbers = new Set([...baseTopics.map((topic) => number(topic, 'topic_number')), ...matchingTopics.map((topic) => number(topic, 'topic_number'))].filter((n) => n > 0));
    const topics = [...topicNumbers].sort((a, b) => a - b).map((topicNumber) => ({
      ...(baseTopics.find((topic) => number(topic, 'topic_number') === topicNumber) || {}),
      ...(matchingTopics.find((topic) => number(topic, 'topic_number') === topicNumber) || {}),
    }));
    return { ...original, ...saved, unit_number: unitNumber, topics };
  });
  return { ...program, units: mergedUnits };
}

export function previousProgramComplete(program: Row): boolean {
  const units = rows(program.units);
  return units.length > 0 && units.every((unit) => { const topics = rows(unit.topics); return topics.length > 0 && topics.every((topic) => list(topic.learning_objectives).length > 0 || list(topic.success_criteria).length > 0 || list(topic.student_can_do).length > 0 || list(topic.suggested_worksheet_types).length > 0 || list(topic.suggested_exam_exercise_types).length > 0 || !!value(topic.homework_idea) || !!value(topic.teacher_notes)); });
}
