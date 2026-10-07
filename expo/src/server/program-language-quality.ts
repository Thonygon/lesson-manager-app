// Mirrors _program_language_quality_issues in streamlit/helpers/learning_programs.py.
type Document = Record<string, unknown>;
const markers: Record<string, string[]> = {
  en: [' the ', ' and ', ' for ', ' with ', ' learners ', ' through ', ' skills ', ' practice '],
  es: [' de ', ' y ', ' para ', ' con ', ' los ', ' las ', ' una ', ' un ', ' que ', ' del ', ' habilidades '],
  tr: [' ve ', ' için ', ' ile ', ' bir ', ' öğrenc', ' beceri', ' ders', ' çünkü ', ' olarak '],
};
const clean = (value: unknown): string => typeof value === 'string' ? value.trim() : '';
const rows = (value: unknown): Document[] => Array.isArray(value) ? value.filter((item): item is Document => !!item && typeof item === 'object' && !Array.isArray(item)) : [];
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];

export function looksWrongProgramLanguage(text: string, language: string): boolean {
  const normalized = ` ${clean(text).toLowerCase()} `;
  if (normalized.length < 48 || !['es', 'tr'].includes(clean(language).toLowerCase())) return false;
  const target = clean(language).toLowerCase();
  const englishHits = markers.en.filter((marker) => normalized.includes(marker)).length;
  const targetHits = markers[target].filter((marker) => normalized.includes(marker)).length;
  return englishHits >= 3 && englishHits >= targetHits + 2;
}

export function programLanguageIssues(document: Document, programLanguage: string, studentLanguage: string, unitOnly = false): string[] {
  const teacher: unknown[] = unitOnly ? [] : [document.title, document.program_overview, document.teacher_rationale, document.scope_and_sequence_rationale, document.entry_profile, document.exit_profile, document.prerequisite_summary, document.assessment_strategy, document.resource_strategy, document.non_classio_support_strategy];
  const student: unknown[] = unitOnly ? [] : [document.student_summary];
  const units = unitOnly ? [document] : rows(document.units);
  for (const unit of units) {
    teacher.push(unit.title, unit.overview, ...list(unit.unit_objectives), ...list(unit.delivery_notes));
    for (const topic of rows(unit.topics)) {
      teacher.push(topic.title, topic.subtopic, topic.lesson_focus, ...list(topic.learning_objectives), ...list(topic.success_criteria), ...list(topic.student_can_do), ...list(topic.delivery_notes), topic.homework_idea, topic.teacher_notes);
      student.push(topic.student_summary);
    }
  }
  const issues: string[] = [];
  if (looksWrongProgramLanguage(teacher.map(clean).filter(Boolean).join(' '), programLanguage)) issues.push(`teacher-facing program fields are not in requested ${programLanguage}`);
  if (looksWrongProgramLanguage(student.map(clean).filter(Boolean).join(' '), studentLanguage)) issues.push(`student-facing summaries are not in requested ${studentLanguage}`);
  return issues;
}
