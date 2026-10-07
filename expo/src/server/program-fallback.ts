import translations from './program-fallback-text.json';
import { programGuidance } from './program-guidance';

type Context = { subject: string; subjectKey: string; stage: string; level: string; units: number; lessonsPerUnit: number; planLanguage: string };
type Row = Record<string, unknown>;
const purposes = ['introduce_concept', 'practice_skill', 'review_topic', 'diagnose_difficulty', 'discussion_exploration'];
const worksheets = ['fill_in_the_blanks', 'multiple_choice', 'matching', 'short_answer', 'true_false', 'reading_comprehension', 'error_correction', 'word_search_vocab'];
const exams = ['multiple_choice', 'true_false', 'matching', 'fill_in_blank', 'short_answer', 'reading_comprehension', 'vocabulary', 'sentence_transformation', 'error_correction', 'writing_prompt', 'problem_solving', 'equation_solving', 'show_your_work', 'table_interpretation', 'word_problems', 'data_analysis', 'classification', 'process_explanation', 'hypothesis_and_conclusion', 'diagram_questions', 'theory_questions', 'symbol_identification', 'rhythm_counting', 'terminology', 'composer_period_matching'];
const labels: Record<string, Record<string, string>> = {
  en: { early_primary: 'Early Primary', upper_primary: 'Upper Primary', lower_secondary: 'Lower Secondary', upper_secondary: 'Upper Secondary', adult_stage: 'Adult', beginner_band: 'Beginner', intermediate_band: 'Intermediate', advanced_band: 'Advanced' },
  es: { early_primary: 'Primaria inicial', upper_primary: 'Primaria alta', lower_secondary: 'Secundaria baja', upper_secondary: 'Secundaria alta', adult_stage: 'Adultos', beginner_band: 'Principiante', intermediate_band: 'Intermedio', advanced_band: 'Avanzado' },
  tr: { early_primary: 'İlkokul başlangıç', upper_primary: 'İlkokul üst', lower_secondary: 'Ortaokul alt', upper_secondary: 'Ortaokul üst', adult_stage: 'Yetişkin', beginner_band: 'Başlangıç', intermediate_band: 'Orta', advanced_band: 'İleri' },
};

export function programFallback(context: Context): Row {
  const locale = context.planLanguage in translations ? context.planLanguage as keyof typeof translations : 'en';
  const messages: Record<string, string> = translations[locale];
  const translate = (key: string, args: Record<string, string | number> = {}) => (messages[key] || translations.en[key as keyof typeof translations.en] || key).replace(/\{(\w+)\}/g, (_, name: string) => String(args[name] ?? `{${name}}`));
  const subject = context.subject.replaceAll('_', ' ');
  const stage = labels[locale][context.stage] || context.stage.replaceAll('_', ' ');
  const level = labels[locale][context.level] || context.level;
  const guidance = programGuidance(context.subjectKey, context.stage, context.level, context.subjectKey === 'other' ? context.subject : '');
  const progression = guidance.subject_progression_profile;
  const activities = guidance.recommended_non_classio_activities;
  const preferredWorksheets = guidance.subject_family === 'math' ? ['short_answer', 'matching', 'multiple_choice', 'true_false', ...worksheets] : guidance.subject_family === 'language' ? ['reading_comprehension', 'fill_in_the_blanks', 'matching', 'multiple_choice', 'short_answer', ...worksheets] : worksheets;
  const worksheetTypes = [...new Set(preferredWorksheets)].slice(0, 3);
  const examTypes = exams.slice(0, 3);
  const units = Array.from({ length: context.units }, (_, unitIndex) => {
    const number = unitIndex + 1;
    return { unit_number: number, title: translate('learning_program_fallback_unit_title', { number }), overview: translate('learning_program_fallback_unit_overview', { subject, stage, level }), unit_objectives: [translate('learning_program_fallback_unit_objective', { unit: number })], recommended_lesson_purposes: purposes.slice(0, 3), recommended_worksheet_types: worksheetTypes, recommended_exam_exercise_types: examTypes, recommended_non_classio_activities: activities.slice(0, 3), delivery_notes: [translate('learning_program_fallback_unit_delivery_note')], estimated_lessons: context.lessonsPerUnit, topics: Array.from({ length: context.lessonsPerUnit }, (_, topicIndex) => { const topicNumber = topicIndex + 1; return { topic_number: topicNumber, title: `${translate('learning_program_fallback_unit_title', { number })} · ${translate('learning_program_fallback_topic_title', { number: topicNumber })}`, subtopic: '', lesson_focus: translate('learning_program_fallback_topic_focus', { subject, number: topicNumber }), lesson_purpose: purposes[topicIndex % purposes.length], learning_objectives: [translate('learning_program_fallback_topic_objective', { unit: number, topic: topicNumber })], success_criteria: [translate('learning_program_fallback_success_criteria')], student_can_do: [translate('learning_program_fallback_student_can_do')], suggested_worksheet_types: worksheetTypes, suggested_exam_exercise_types: examTypes, suggested_non_classio_activities: activities.slice(0, 2), delivery_notes: [translate('learning_program_fallback_topic_delivery_note')], homework_idea: '', teacher_notes: progression.sequence_expectations[0] || '', student_summary: translate('learning_program_fallback_topic_focus', { subject, number: topicNumber }), estimated_lessons: 1 }; }) };
  });
  return { title: translate('learning_program_title_format', { subject, stage, level }), program_overview: translate('learning_program_fallback_overview', { subject, stage, level }), teacher_rationale: translate('learning_program_default_teacher_rationale'), scope_and_sequence_rationale: progression.sequence_expectations[0] || '', core_progression_priorities: progression.focus_strands.slice(0, 5), entry_profile: translate('learning_program_default_entry_profile'), exit_profile: translate('learning_program_default_exit_profile'), prerequisite_summary: translate('learning_program_default_prerequisite_summary'), student_summary: translate('learning_program_default_student_summary', { subject }), assessment_strategy: translate('learning_program_default_assessment_strategy'), resource_strategy: translate('learning_program_default_resource_strategy'), subject_family: guidance.subject_family, delivery_design_notes: [translate('learning_program_default_delivery_note_one'), translate('learning_program_default_delivery_note_two')], non_classio_support_strategy: translate('learning_program_default_non_classio_strategy'), best_practice_frameworks: [...new Set([...guidance.best_practice_frameworks, ...progression.global_priorities.slice(0, 2)])], units };
}

export function fallbackProgramUnit(skeleton: Row, fallback: Row, index: number): Row {
  const original = Array.isArray(skeleton.units) ? skeleton.units[index] as Row : {};
  const generated = Array.isArray(fallback.units) ? fallback.units[index] as Row : {};
  const topics = Array.isArray(original.topics) ? original.topics as Row[] : [];
  const replacements = Array.isArray(generated.topics) ? generated.topics as Row[] : [];
  return { ...generated, ...original, unit_objectives: generated.unit_objectives, recommended_lesson_purposes: generated.recommended_lesson_purposes, recommended_worksheet_types: generated.recommended_worksheet_types, recommended_exam_exercise_types: generated.recommended_exam_exercise_types, recommended_non_classio_activities: generated.recommended_non_classio_activities, delivery_notes: generated.delivery_notes, estimated_lessons: generated.estimated_lessons, topics: topics.map((topic, topicIndex) => ({ ...(replacements[topicIndex] || {}), ...topic, learning_objectives: replacements[topicIndex]?.learning_objectives, success_criteria: replacements[topicIndex]?.success_criteria, student_can_do: replacements[topicIndex]?.student_can_do, suggested_worksheet_types: replacements[topicIndex]?.suggested_worksheet_types, suggested_exam_exercise_types: replacements[topicIndex]?.suggested_exam_exercise_types, suggested_non_classio_activities: replacements[topicIndex]?.suggested_non_classio_activities, delivery_notes: replacements[topicIndex]?.delivery_notes, teacher_notes: replacements[topicIndex]?.teacher_notes })) };
}
