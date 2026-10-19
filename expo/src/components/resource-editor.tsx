import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Disclosure, Field, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

type PathPart = string | number;
type EditableField = { path: PathPart[]; kind: 'scalar' | 'list'; value: string; original: unknown };

const SKIP_KEYS = new Set(['visual_support', 'visual_supports', '_visual_support_status', 'cover_image', 'avatar_url', 'image_url', 'image', 'text_blocks', 'text_kind', 'worksheet_type']);
const ROOT_SKIP_KEYS = new Set(['id', 'user_id', 'title', 'subject', 'learner_stage', 'level_or_band', 'plan_language', 'student_material_language', 'source_type']);
const isScalar = (value: unknown) => value === null || ['string', 'number', 'boolean'].includes(typeof value);

const WORKSHEET_FIELDS: Record<string, string[]> = {
  short_answer: ['questions', 'source_text', 'text_title'],
  reading_comprehension: ['questions', 'reading_passage', 'text_title'],
  true_false: ['true_false_statements', 'source_text', 'text_title'],
  matching: ['matching_pairs', 'left_items', 'right_items'],
  multiple_choice: ['multiple_choice_items'],
  fill_in_the_blanks: ['questions', 'vocabulary_bank'],
  error_correction: ['questions', 'source_text'],
  word_search_vocab: ['vocabulary_bank', 'wordsearch_grid', 'grid'],
};
const WORKSHEET_COMMON = new Set(['instructions', 'answer_key', 'teacher_notes', 'sections']);
const EXAM_SECTION_FIELDS = new Set(['title', 'instructions', 'source_text', 'text_title', 'vocabulary_bank']);
const EXAM_QUESTION_FIELDS = new Set(['stem', 'text', 'question', 'sentence', 'prompt', 'original', 'left', 'right', 'options', 'explanation', 'marking_guide']);

// Exams have a fixed assessment schema. Never expose its identifiers, type,
// generated media, scoring metadata, or arbitrary nested JSON as editable text.
function collectExamFields(document: Record<string, unknown>): EditableField[] {
  const exam = document.exam_data && typeof document.exam_data === 'object' && !Array.isArray(document.exam_data) ? document.exam_data as Record<string, unknown> : {};
  const key = document.answer_key && typeof document.answer_key === 'object' && !Array.isArray(document.answer_key) ? document.answer_key as Record<string, unknown> : {};
  const result: EditableField[] = [];
  const add = (value: unknown, path: PathPart[]) => { if (value !== undefined && (isScalar(value) || Array.isArray(value))) result.push(...collectFields(value, path)); };
  add(exam.instructions, ['exam_data', 'instructions']);
  const sections = Array.isArray(exam.sections) ? exam.sections : [];
  sections.forEach((rawSection, index) => {
    if (!rawSection || typeof rawSection !== 'object' || Array.isArray(rawSection)) return;
    const section = rawSection as Record<string, unknown>;
    EXAM_SECTION_FIELDS.forEach((field) => { if (field !== 'vocabulary_bank' || Array.isArray(section[field])) add(section[field], ['exam_data', 'sections', index, field]); });
    const questions = Array.isArray(section.questions) ? section.questions : [];
    questions.forEach((rawQuestion, questionIndex) => {
      const base: PathPart[] = ['exam_data', 'sections', index, 'questions', questionIndex];
      if (isScalar(rawQuestion)) { add(rawQuestion, base); return; }
      if (!rawQuestion || typeof rawQuestion !== 'object' || Array.isArray(rawQuestion)) return;
      const question = rawQuestion as Record<string, unknown>;
      EXAM_QUESTION_FIELDS.forEach((field) => {
        const value = question[field];
        if (field === 'options' && (!Array.isArray(value) || !value.every(isScalar))) return;
        if (isScalar(value) || (field === 'options' && Array.isArray(value))) add(value, [...base, field]);
      });
    });
  });
  const keySections = Array.isArray(key.sections) ? key.sections : [];
  keySections.forEach((rawSection, index) => {
    if (!rawSection || typeof rawSection !== 'object' || Array.isArray(rawSection)) return;
    const answers = (rawSection as Record<string, unknown>).answers;
    if (Array.isArray(answers) && answers.every(isScalar)) add(answers, ['answer_key', 'sections', index, 'answers']);
  });
  return result;
}

function collectFields(value: unknown, path: PathPart[] = [], worksheetType?: string): EditableField[] {
  if (path.length && (SKIP_KEYS.has(String(path[path.length - 1])) || (path.length === 1 && ROOT_SKIP_KEYS.has(String(path[0]))))) return [];
  if (path.length === 1 && worksheetType && WORKSHEET_FIELDS[worksheetType] && !WORKSHEET_COMMON.has(String(path[0])) && !WORKSHEET_FIELDS[worksheetType].includes(String(path[0])) && !(path[0] === 'vocabulary_bank' && Array.isArray(value) && value.length)) return [];
  if (path.length === 1 && worksheetType && WORKSHEET_COMMON.has(String(path[0])) && String(path[0]) !== 'instructions' && String(path[0]) !== 'answer_key' && (value === '' || (Array.isArray(value) && !value.length))) return [];
  if (Array.isArray(value)) {
    if (value.every(isScalar)) return [{ path, kind: 'list', value: value.filter((item) => String(item ?? '').trim()).map(String).join('\n'), original: value }];
    return value.flatMap((item, index) => collectFields(item, [...path, index], worksheetType));
  }
  if (value && typeof value === 'object') return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => collectFields(child, [...path, key], worksheetType));
  return path.length ? [{ path, kind: 'scalar', value: value === null || value === undefined ? '' : String(value), original: value }] : [];
}

function setAtPath(root: Record<string, unknown>, field: EditableField, raw: string) {
  let parent: any = root;
  field.path.slice(0, -1).forEach((part) => { parent = parent[part]; });
  const key = field.path[field.path.length - 1];
  let value: unknown = raw;
  if (field.kind === 'list') value = raw.split('\n').map((line) => line.trim()).filter(Boolean);
  else if (typeof field.original === 'boolean') value = ['1', 'true', 'yes', 'on'].includes(raw.trim().toLocaleLowerCase());
  else if (typeof field.original === 'number') value = Number.isFinite(Number(raw)) ? Number(raw) : field.original;
  else if (field.original === null && !raw.trim()) value = null;
  parent[key] = value;
}

function pathLabel(path: PathPart[]) {
  return path.map((part) => typeof part === 'number' ? String(part + 1) : part.replaceAll('_', ' ')).join(' › ');
}

function localizedPathLabel(path: PathPart[], t: (key: string) => string) {
  return path.map((part) => {
    if (typeof part === 'number') return String(part + 1);
    const key = `resources.term.${part}`;
    const translated = t(key);
    return translated === key ? part.replaceAll('_', ' ') : translated;
  }).join(' › ');
}

export function ResourceEditor({ document, onApply, defaultOpen = false, recommendedLevels, onDirtyChange, worksheetType, examMode = false }: { document: Record<string, unknown>; onApply: (document: Record<string, unknown>) => void; defaultOpen?: boolean; recommendedLevels?: { value: string; label: string }[]; onDirtyChange?: (dirty: boolean) => void; worksheetType?: string; examMode?: boolean }) {
  const { t, language } = useAppPreferences();
  const examLabel = (path: PathPart[]) => {
    const copy = { en: { section: 'Section', question: 'Question', answers: 'Answer key' }, es: { section: 'Sección', question: 'Pregunta', answers: 'Clave de respuestas' }, tr: { section: 'Bölüm', question: 'Soru', answers: 'Cevap anahtarı' } }[language];
    if (path[0] === 'exam_data' && path[1] === 'instructions') return localizedPathLabel(['instructions'], t);
    const section = typeof path[2] === 'number' ? `${copy.section} ${path[2] + 1}` : copy.section;
    if (path[0] === 'answer_key') return `${section} › ${copy.answers}`;
    if (path[3] === 'questions' && typeof path[4] === 'number') return `${section} › ${copy.question} ${path[4] + 1}${path[5] ? ` › ${localizedPathLabel([path[5]], t)}` : ''}`;
    return `${section} › ${localizedPathLabel(path.slice(3), t)}`;
  };
  const editableDocument = useMemo(() => worksheetType === 'short_answer' && !('source_text' in document) ? { ...document, source_text: '' } : document, [document, worksheetType]);
  const fields = useMemo(() => examMode ? collectExamFields(editableDocument) : collectFields(editableDocument, [], worksheetType), [editableDocument, worksheetType, examMode]);
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((field) => [JSON.stringify(field.path), field.value])));
  const [error, setError] = useState('');
  const apply = () => {
    const invalidNumber = fields.find((field) => typeof field.original === 'number' && (!Number.isFinite(Number(values[JSON.stringify(field.path)] ?? field.value)) || (Number.isInteger(field.original) && !Number.isInteger(Number(values[JSON.stringify(field.path)] ?? field.value)))));
    if (invalidNumber) { setError(`${pathLabel(invalidNumber.path)}: enter a valid number.`); return; }
    const tooLong = fields.find((field) => (values[JSON.stringify(field.path)] ?? field.value).length > 12000);
    if (tooLong) { setError(`${pathLabel(tooLong.path)}: text is too long.`); return; }
    const emptiedList = fields.find((field) => field.kind === 'list' && Array.isArray(field.original) && field.original.length > 0 && !(values[JSON.stringify(field.path)] ?? field.value).trim());
    if (emptiedList) { setError(`${pathLabel(emptiedList.path)}: keep at least one item.`); return; }
    if (examMode) {
      const changedLength = fields.find((field) => field.kind === 'list' && Array.isArray(field.original) && (values[JSON.stringify(field.path)] ?? field.value).split('\n').map((line) => line.trim()).filter(Boolean).length !== field.original.length);
      if (changedLength) { setError(`${pathLabel(changedLength.path)}: keep the same number of items so questions, choices, and answers stay aligned.`); return; }
      const emptyRequired = fields.find((field) => field.path.includes('questions') && !(values[JSON.stringify(field.path)] ?? field.value).trim());
      if (emptyRequired) { setError(`${pathLabel(emptyRequired.path)}: this question field cannot be empty.`); return; }
    }
    const invalidLevel = fields.find((field) => field.path.at(-1) === 'recommended_level' && recommendedLevels?.length && !recommendedLevels.some((option) => option.value === (values[JSON.stringify(field.path)] ?? field.value)));
    if (invalidLevel) { setError(`${pathLabel(invalidLevel.path)}: choose a valid level.`); return; }
    setError('');
    const updated = JSON.parse(JSON.stringify(editableDocument)) as Record<string, unknown>;
    fields.forEach((field) => setAtPath(updated, field, values[JSON.stringify(field.path)] ?? field.value));
    if (examMode) {
      const sections = (updated.exam_data as { sections?: Record<string, unknown>[] } | undefined)?.sections;
      const answerSections = (updated.answer_key as { sections?: { answers?: unknown[] }[] } | undefined)?.sections;
      if (Array.isArray(sections) && Array.isArray(answerSections)) answerSections.forEach((keySection, index) => {
        if (!Array.isArray(keySection.answers) || !sections[index]) return;
        sections[index].answers = [...keySection.answers];
        const questions = sections[index].questions;
        if (Array.isArray(questions)) questions.forEach((question, questionIndex) => {
          if (!question || typeof question !== 'object' || Array.isArray(question) || questionIndex >= keySection.answers!.length) return;
          const row = question as Record<string, unknown>;
          if ('answer' in row) row.answer = keySection.answers![questionIndex];
          if ('correct_answer' in row) row.correct_answer = keySection.answers![questionIndex];
        });
      });
    }
    onApply(updated);
  };
  return <Disclosure title={t('smart.editorTitle')} summary={t('smart.editorHelp')} defaultOpen={defaultOpen} style={styles.editor}>
    <View style={styles.fields}>{fields.map((field) => { const key = JSON.stringify(field.path); const label = examMode ? examLabel(field.path) : localizedPathLabel(field.path, t); const multiline = field.kind === 'list' || ['source_text', 'reading_passage', 'instructions', 'answer_key'].includes(String(field.path.at(-1))) || String(field.original ?? '').length > 80; const change = (value: string) => { const next = { ...values, [key]: value }; setValues(next); onDirtyChange?.(fields.some((entry) => next[JSON.stringify(entry.path)] !== entry.value)); }; return <View key={key} style={styles.field}><Text style={styles.label}>{label}</Text>{field.path.at(-1) === 'recommended_level' && recommendedLevels?.length ? <SelectField label={label} value={values[key] ?? field.value} options={recommendedLevels} onChange={change} /> : typeof field.original === 'boolean' ? <SelectField label={label} value={values[key] ?? field.value} options={[{ value: 'true', label: t('resources.yes') }, { value: 'false', label: t('resources.no') }]} onChange={change} /> : <Field value={values[key] ?? field.value} onChangeText={change} keyboardType={typeof field.original === 'number' ? 'decimal-pad' : 'default'} multiline={multiline} numberOfLines={multiline ? 4 : 1} style={multiline ? styles.multiline : undefined} />}</View>; })}</View>
    {error ? <Text style={styles.error}>{error}</Text> : null}
    <View style={styles.action}><Button onPress={apply}>{t('smart.applyEdits')}</Button></View>
  </Disclosure>;
}

const styles = StyleSheet.create({ editor: { marginTop: 12 }, fields: { gap: 10 }, field: { gap: 5 }, label: { color: colors.muted, fontSize: 10, fontWeight: '800', textTransform: 'capitalize' }, multiline: { minHeight: 92, paddingTop: 12, textAlignVertical: 'top' }, error: { color: colors.danger, fontSize: 12, marginTop: 8 }, action: { alignSelf: 'flex-start', marginTop: 14 } });
