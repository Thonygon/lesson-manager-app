// Checks the source builders' minimum usable content before a generated resource can be saved.
import { splitAnswerKeyItems, worksheetAnswerCount } from './answer-key';
import { examLengthRule } from '../lib/exam-generation-rules';
type Document = Record<string, unknown>;
const entries = (value: unknown): Document[] => Array.isArray(value) ? value.filter((item): item is Document => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const text = (value: unknown): string => typeof value === 'string' ? value.trim() : '';
const usable = (value: unknown): boolean => Boolean(text(value));

export function worksheetQualityIssues(document: Document): string[] {
  const issues: string[] = [];
  const kind = text(document.worksheet_type);
  const questions = list(document.questions);
  const pairs = entries(document.matching_pairs);
  const count = worksheetAnswerCount(document);
  if (kind === 'reading_comprehension' && !usable(document.reading_passage)) issues.push('reading_comprehension requires a reading_passage');
  if (kind === 'true_false' && !usable(document.source_text)) issues.push('true_false requires source_text');
  if (kind === 'error_correction' && questions.length < 3) issues.push('error_correction needs at least 3 valid incorrect sentences');
  if (kind === 'matching') {
    if (pairs.length < 4 || pairs.some((pair) => !usable(pair.left) || !usable(pair.right))) issues.push('matching needs at least 4 valid pairs');
    if (new Set(pairs.map((pair) => text(pair.right).toLowerCase())).size <= 1) issues.push('matching right side needs varied options');
  }
  if (kind === 'multiple_choice' && entries(document.multiple_choice_items).some((item) => !usable(item.stem) || list(item.options).length < 3 || !usable(item.answer))) issues.push('multiple_choice needs complete items and answers');
  if (kind !== 'word_search_vocab' && splitAnswerKeyItems(document.answer_key, count).some((answer) => !answer)) issues.push('answer_key needs one answer per item');
  return issues;
}

export function examQualityIssues(document: Document, length: string): string[] {
  const issues: string[] = [];
  const { questionsMin, questionsMax } = examLengthRule(length);
  const range = [questionsMin, questionsMax];
  entries(document.sections).forEach((section, index) => {
    const label = `section ${index + 1}`;
    const questions = list(section.questions);
    const kind = text(section.type);
    if (questions.length < range[0] || questions.length > range[1]) issues.push(`${label} needs ${range[0]}-${range[1]} questions`);
    if (kind === 'reading_comprehension' && !usable(section.source_text)) issues.push(`${label} reading_comprehension needs source_text`);
    if (kind === 'table_interpretation') {
      const table = section.table_data && typeof section.table_data === 'object' ? section.table_data as Document : {};
      if (list(table.columns).length < 2 || list(table.rows).length < 2) issues.push(`${label} table_interpretation needs at least 2 columns and 2 rows`);
    }
    if (kind === 'matching' && (questions.length < 4 || questions.some((item) => !item || typeof item !== 'object' || !usable((item as Document).left) || !usable((item as Document).right)))) issues.push(`${label} matching needs at least 4 valid pairs`);
    if (kind === 'error_correction' && questions.length < 3) issues.push(`${label} error_correction needs at least 3 valid items`);
  });
  return issues;
}

export function programQualityIssues(document: Document, requestedUnits: number, requestedLessons: number): string[] {
  const issues: string[] = [];
  const units = entries(document.units);
  if (units.length !== requestedUnits) issues.push(`program needs ${requestedUnits} units`);
  units.forEach((unit, index) => {
    if (!usable(unit.title)) issues.push(`unit ${index + 1} needs a title`);
    const topics = entries(unit.topics);
    if (topics.length !== requestedLessons) issues.push(`unit ${index + 1} needs ${requestedLessons} topics`);
    if (topics.some((topic) => !usable(topic.title) || !usable(topic.student_summary))) issues.push(`unit ${index + 1} has an incomplete topic`);
  });
  return issues;
}
