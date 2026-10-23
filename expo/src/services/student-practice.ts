import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';
import { extractResourceImageUrl, type PublicResource } from '@/services/public-data';
import { invalidateStudentRecommendationFeedback } from '@/services/student-data';
import { aggregatePracticeProgress, practiceSessionScorePct } from '@/services/student-practice-progress';
import { canonicalChoice, canonicalTrueFalse, choiceIndex, normalizePracticeAnswer } from '@/services/student-practice-answer-normalization';

export type WordSearchPlacement = { word: string; coords: [number, number][] };
export type PracticeQuestion = { prompt: string; options: string[]; answer: string; exerciseIndex: number; questionIndex: number; exerciseType: string; sectionTitle: string; instructions: string; sourceText: string; visualSupportUrl?: string; vocabularyBank?: string[]; grid?: string[][]; words?: string[]; placements?: WordSearchPlacement[] };
export type PracticeMaterial = { title: string; sourceType: 'worksheet' | 'exam'; sourceId: string; assignmentId?: string; teacherId?: string; learningProgramAssignmentId?: number; subject: string; topic: string; stage: string; level: string; raw: Record<string, unknown>; questions: PracticeQuestion[] };
export type PracticeResult = { sessionId: string; total: number; correct: number; score: number; xp: number; bestStreak: number };
export type VideoPracticeInput = { id: string; assignmentId?: string; teacherId?: string; title: string; subject: string; topic: string; stage: string; level: string; url: string };

function record(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, unknown>;
  if (typeof value === 'string' && value.trim().startsWith('{')) { try { const parsed = JSON.parse(value); return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {}; } catch { return {}; } }
  return {};
}
function list(value: unknown): unknown[] { return Array.isArray(value) ? value : []; }
function text(value: unknown) { return typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''; }
const normalized = normalizePracticeAnswer;
function strictCorrection(value: unknown) { return text(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[’‘]/g, "'").replace(/[“”]/g, '"').replace(/[—–]/g, '-').replace(/\s+/g, ' ').replace(/\s+([,;:.!?])/g, '$1').replace(/[.!?]+$/g, '').trim(); }
const STOP_WORDS = new Set(['a','an','the','is','are','was','were','be','been','being','it','its','to','of','in','on','at','for','and','or','but','by','as','with','from','that','this','also','very','than','not','no','do','does','did','has','have','had','will','can','could','would','should','may','might']);
function answerWords(value: unknown) { return new Set((normalized(value).match(/[a-z0-9]+/g) ?? []).filter((word) => !STOP_WORDS.has(word))); }
export function evaluateWritingPrompt(student: string, expected: string) {
  const studentNorm = normalized(student);
  if (!studentNorm) return { isCorrect: false, score: 0, feedbackKeys: ['writing_feedback_missing_response'] };
  const expectedWords = answerWords(expected);
  const studentWords = new Set((studentNorm.match(/[a-z0-9]+/g) ?? []).filter((word) => expectedWords.has(word)));
  const overlap = expectedWords.size ? studentWords.size / expectedWords.size : 0;
  const words = (student.match(/[\p{L}\p{N}_]+/gu) ?? []).length;
  const sentences = student.split(/[.!?]+/).filter((part) => part.trim()).length;
  const content = overlap >= 0.75 ? 0.6 : overlap >= 0.5 ? 0.45 : overlap >= 0.3 ? 0.3 : overlap > 0 ? 0.15 : 0;
  const development = words >= 45 || sentences >= 3 ? 0.25 : words >= 25 || sentences >= 2 ? 0.15 : words >= 10 ? 0.05 : 0;
  const structure = sentences >= 3 ? 0.15 : sentences >= 2 ? 0.1 : words >= 12 ? 0.05 : 0;
  const score = Math.round(Math.min(1, content + development + structure) * 100) / 100;
  return { isCorrect: score >= 0.6, score, feedbackKeys: [
    overlap >= 0.6 ? 'writing_feedback_content_strong' : overlap >= 0.3 ? 'writing_feedback_content_partial' : 'writing_feedback_content_missing',
    words >= 25 ? 'writing_feedback_length_good' : words >= 10 ? 'writing_feedback_length_ok' : 'writing_feedback_length_short',
    sentences >= 2 ? 'writing_feedback_structure_good' : 'writing_feedback_structure_needs',
  ] };
}
function displayAnswer(value: unknown) { if (Array.isArray(value)) return value.map(text).filter(Boolean).join(', '); const row = record(value); if (Object.keys(row).length) return text(row.text || row.answer || row.value || row.right || value); return text(value); }
function matchingReference(value: unknown, count: number) { return choiceIndex(displayAnswer(value), count); }
function stableShuffle(values: string[], seed: string) { const result = [...new Set(values.filter(Boolean))]; let state = [...seed].reduce((hash, char) => ((hash << 5) - hash + char.charCodeAt(0)) | 0, 2166136261); const random = () => { state = Math.imul(state ^ (state >>> 15), 1 | state); state ^= state + Math.imul(state ^ (state >>> 7), 61 | state); return ((state ^ (state >>> 14)) >>> 0) / 4294967296; }; for (let index = result.length - 1; index > 0; index -= 1) { const swap = Math.floor(random() * (index + 1)); [result[index], result[swap]] = [result[swap], result[index]]; } return result; }
function normalizeWords(value: unknown) { const values = Array.isArray(value) ? value : text(value).split(','); return [...new Set(values.map((word) => text(word).replace(/^[\s\[\]"'\\]+|[\s\[\]"'\\]+$/g, '').replace(/\s+/g, '').toUpperCase()).filter(Boolean))]; }
function wordSearchWords(value: unknown): string[] {
  if (Array.isArray(value)) return [...new Set(value.flatMap((item) => wordSearchWords(item)))];
  if (value && typeof value === 'object') {
    const row = record(value);
    return wordSearchWords(row.found_words || row.found || row.words || []);
  }
  const raw = text(value);
  if (!raw) return [];
  if (raw.startsWith('[') || raw.startsWith('{') || raw.startsWith('"')) {
    try { const parsed = JSON.parse(raw); if (parsed !== raw) return wordSearchWords(parsed); } catch { /* fall through to legacy comma/newline parsing */ }
  }
  return normalizeWords(raw.split(/[,;|\n]/));
}
function firstNonEmptyList(...values: unknown[]) { return values.map(list).find((items) => items.length) ?? []; }
function generateWordSearch(input: string[], seed: string) {
  const words = normalizeWords(input).filter((word) => word.length <= 15).slice(0, 12); const size = Math.max(10, Math.min(15, Math.max(...words.map((word) => word.length), 8) + 2)); let state = [...seed].reduce((hash, char) => Math.imul(hash ^ char.charCodeAt(0), 16777619), 2166136261) >>> 0; const random = () => ((state = (Math.imul(state, 1664525) + 1013904223) >>> 0) / 4294967296); const grid = Array.from({ length: size }, () => Array.from({ length: size }, () => '')); const directions = [[0,1],[1,0],[1,1],[1,-1],[0,-1],[-1,0],[-1,-1],[-1,1]]; const placements: WordSearchPlacement[] = [];
  for (const word of words) { let placed = false; for (let attempt = 0; attempt < 220 && !placed; attempt += 1) { const [dr, dc] = directions[Math.floor(random() * directions.length)]; const row = Math.floor(random() * size); const col = Math.floor(random() * size); const endRow = row + dr * (word.length - 1); const endCol = col + dc * (word.length - 1); if (endRow < 0 || endRow >= size || endCol < 0 || endCol >= size) continue; const coords = [...word].map((_, index) => [row + dr * index, col + dc * index] as [number, number]); if (coords.some(([r, c], index) => grid[r][c] && grid[r][c] !== word[index])) continue; coords.forEach(([r, c], index) => { grid[r][c] = word[index]; }); placements.push({ word, coords }); placed = true; } }
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'; grid.forEach((row) => row.forEach((letter, col) => { if (!letter) row[col] = alphabet[Math.floor(random() * alphabet.length)]; })); return { grid, words: placements.map((item) => item.word), placements };
}
function answerItems(value: unknown, count: number) {
  if (Array.isArray(value)) return value.map((item) => Array.isArray(item) ? JSON.stringify(item.map(displayAnswer).filter(Boolean)) : displayAnswer(item));
  const raw = text(value); if (!raw) return [];
  const indexed = [...raw.matchAll(/(?:^|\s|,)\d+[.):\-]\s*([^,;|\n]+?)(?=\s+\d+[.):\-]|[,;|\n]|$)/g)].map((match) => match[1].trim());
  if (count > 1 && indexed.length === count) return indexed;
  const tokens = raw.trim().split(/\s+/);
  if (count > 1 && tokens.length === count && tokens.every((item) => /^(?:[A-D]|[FVT]|true|false|verdader[oa]|fals[oa])$/i.test(item))) return tokens;
  const lines = raw.split(/\n|;|\||,(?=\s*(?:\d+|[A-Za-z])[.):\-])/).map((item) => item.replace(/^\s*(?:answer\s*)?[A-Za-z0-9]+[.)\-:]\s*/i, '').trim()).filter(Boolean);
  if (lines.length >= count) return lines;
  return raw.split(/\s*,\s*/).map((item) => item.trim()).filter(Boolean);
}
function promptFor(kind: string, value: unknown) {
  const row = record(value);
  if (kind === 'multiple_choice') return text(row.stem || row.text || value);
  if (kind === 'matching') return text(row.left || row.text || value);
  if (kind === 'vocabulary') return [row.word, row.task || row.text].map(text).filter(Boolean).join(': ');
  if (kind === 'sentence_transformation') return [row.original, row.prompt].map(text).filter(Boolean).join(' · ');
  return text(row.text || row.question || row.prompt || row.task || value);
}
function optionsFor(kind: string, value: unknown) {
  const row = record(value);
  if (kind === 'true_false') return ['True', 'False'];
  return list(row.options || row.choices).map(displayAnswer).filter(Boolean);
}
function addSection(target: PracticeQuestion[], section: Record<string, unknown>, sectionIndex: number, fallbackAnswers?: unknown) {
  const kind = text(section.type || section.worksheet_type || 'short_answer').replace('fill_in_the_blanks', 'fill_in_blank');
  const questions = firstNonEmptyList(section.questions, section.true_false_statements, section.items);
  // The edited answer key is authoritative. Generated sections and inline
  // question answers can retain older copies after a teacher corrects a key.
  const fallback = answerItems(fallbackAnswers, questions.length);
  const answers = fallback.length === questions.length ? fallback : answerItems(section.answer_key ?? section.answers, questions.length);
  if (kind === 'word_search_vocab') {
    const first = record(questions[0]); const answerWords = wordSearchWords(answers[0] || first.words || section.vocabulary_bank); const rawGrid = firstNonEmptyList(first.grid, section.grid, section.word_search_grid); const storedGrid = rawGrid.map((row) => list(row).map((letter) => text(letter).toUpperCase())); const storedPlacements = firstNonEmptyList(first.placements, section.placements).map((value) => { const item = record(value); return { word: text(item.word).replace(/\s+/g, '').toUpperCase(), coords: list(item.coords).map((coord) => list(coord).map(Number).slice(0, 2) as [number, number]) }; }).filter((item) => item.word && item.coords.length); const generated = storedGrid.length && answerWords.length && storedPlacements.length ? { grid: storedGrid, words: answerWords, placements: storedPlacements } : generateWordSearch(answerWords, `${sectionIndex}:${answerWords.join('|')}`); target.push({ prompt: text(section.instructions || section.title), options: [], answer: JSON.stringify(generated.words), exerciseIndex: sectionIndex, questionIndex: 0, exerciseType: kind, sectionTitle: text(section.title), instructions: text(section.instructions), sourceText: text(section.source_text), visualSupportUrl: extractResourceImageUrl(section.visual_support), vocabularyBank: generated.words, ...generated }); return;
  }
  const rightChoices = questions.map((question) => text(record(question).right)).filter(Boolean); const matchingOptions = kind === 'matching' ? stableShuffle(rightChoices, `${sectionIndex}:${questions.map((question) => promptFor(kind, question)).join('|')}`) : [];
  questions.forEach((question, questionIndex) => { const inlineAnswer = record(question).answer ?? record(question).correct_answer ?? record(question).correct ?? record(question).value; const itemOptions = optionsFor(kind, question); let answer = displayAnswer(answers[questionIndex] || inlineAnswer); if (kind === 'matching') { const reference = matchingReference(answer, rightChoices.length); answer = reference >= 0 ? rightChoices[reference] : displayAnswer(record(question).right) || answer; } else if (['multiple_choice', 'vocabulary'].includes(kind) && itemOptions.length) { const reference = matchingReference(answer, itemOptions.length); if (reference >= 0) answer = itemOptions[reference]; } target.push({ prompt: promptFor(kind, question), options: matchingOptions.length ? matchingOptions : itemOptions, answer, exerciseIndex: sectionIndex, questionIndex, exerciseType: kind, sectionTitle: text(section.title), instructions: text(section.instructions), sourceText: text(section.source_text || section.reading_passage), visualSupportUrl: extractResourceImageUrl(section.visual_support), vocabularyBank: list(section.vocabulary_bank).map(text).filter(Boolean) }); });
}
function worksheetQuestions(ws: Record<string, unknown>) {
  const result: PracticeQuestion[] = []; const kind = text(ws.worksheet_type);
  if (kind === 'multiple_choice') {
    const items = list(ws.multiple_choice_items); const inline = items.map((item) => record(item).answer ?? record(item).correct_answer); const key = answerItems(ws.answer_key, items.length); addSection(result, { type: kind, title: ws.title, questions: items, answers: key.length === items.length ? key : inline, instructions: ws.instructions, visual_support: list(ws.visual_supports)[0] }, 0); return result;
  }
  if (kind === 'matching') {
    const pairs = list(ws.matching_pairs).length ? list(ws.matching_pairs) : list(ws.left_items).map((left, index) => ({ left, right: list(ws.right_items)[index] })); addSection(result, { type: kind, title: ws.title, questions: pairs, answers: pairs.map((item) => record(item).right), instructions: ws.instructions, visual_support: list(ws.visual_supports)[0] }, 0); return result;
  }
  if (kind === 'word_search_vocab') {
    const vocabulary = wordSearchWords(ws.vocabulary_bank); const first = record(list(ws.questions)[0]); const rawGrid = firstNonEmptyList(ws.grid, ws.word_search_grid, first.grid); const storedGrid = rawGrid.map((row) => list(row).map((letter) => text(letter).toUpperCase())); const storedPlacements = firstNonEmptyList(ws.placements, first.placements).map((value) => { const item = record(value); return { word: text(item.word).replace(/\s+/g, '').toUpperCase(), coords: list(item.coords).map((coord) => list(coord).map(Number).slice(0, 2) as [number, number]) }; }).filter((item) => item.word && item.coords.length); const generated = storedGrid.length && vocabulary.length && storedPlacements.length ? { grid: storedGrid, words: vocabulary, placements: storedPlacements } : generateWordSearch(vocabulary, vocabulary.join('|'));
    result.push({ prompt: text(ws.instructions || ws.title), options: [], answer: JSON.stringify(generated.words), exerciseIndex: 0, questionIndex: 0, exerciseType: kind, sectionTitle: text(ws.title), instructions: text(ws.instructions), sourceText: '', visualSupportUrl: extractResourceImageUrl(list(ws.visual_supports)[0]), vocabularyBank: generated.words, ...generated }); return result;
  }
  const questions = firstNonEmptyList(ws.questions, ws.true_false_statements, ws.items);
  addSection(result, { ...ws, type: kind, title: ws.title, questions, source_text: ws.source_text || ws.reading_passage, visual_support: list(ws.visual_supports)[0] }, 0, ws.answer_key);
  return result;
}
function examQuestions(exam: Record<string, unknown>, answerKey: Record<string, unknown>) {
  const result: PracticeQuestion[] = []; const keys = list(answerKey.sections);
  list(exam.sections).forEach((value, index) => addSection(result, record(value), index, record(keys[index]).answers)); return result;
}
export function materialFromAssignment(row: ClassioRecord): PracticeMaterial | null {
  const kind = text(row.assignment_type); if (kind !== 'worksheet' && kind !== 'exam') return null;
  const snapshot = record(row.content_snapshot); const payload = kind === 'worksheet' ? record(snapshot.worksheet || snapshot.worksheet_json) : record(snapshot.exam_data || snapshot.exam_json); const key = record(snapshot.answer_key);
  const questions = kind === 'worksheet' ? worksheetQuestions(payload) : examQuestions(payload, key);
  return { title: text(row.title || payload.title), sourceType: kind, sourceId: text(row.source_record_id || row.id), assignmentId: text(row.id), teacherId: text(row.teacher_id), learningProgramAssignmentId: Number(row.learning_program_assignment_id) || undefined, subject: text(row.subject_key || row.subject_label), topic: text(row.topic), stage: text(record(snapshot.meta).learner_stage), level: text(record(snapshot.meta).level_or_band), raw: payload, questions };
}
export function materialFromPublic(resource: PublicResource): PracticeMaterial | null {
  if (resource.kind !== 'worksheet' && resource.kind !== 'exam') return null; const raw = resource.raw;
  const payload = resource.kind === 'worksheet' ? record(raw.worksheet_json || raw.worksheet || raw) : record(raw.exam_data || raw.exam_json || raw); const key = record(raw.answer_key);
  const questions = resource.kind === 'worksheet' ? worksheetQuestions(payload) : examQuestions(payload, key);
  return { title: resource.title, sourceType: resource.kind, sourceId: resource.id, subject: resource.subject, topic: resource.topic, stage: resource.stage, level: resource.level, raw: payload, questions };
}
export function materialFromSession(row: ClassioRecord): PracticeMaterial | null { const data = record(row.exercise_data); const sourceType = text(row.source_type || data.source_type); if (sourceType !== 'worksheet' && sourceType !== 'exam') return null; const questions: PracticeQuestion[] = []; list(data.exercises).forEach((section, index) => addSection(questions, record(section), index)); if (!questions.length) return null; return { title: text(row.title || data.title), sourceType, sourceId: text(data.source_id || row.source_id || row.id), assignmentId: text(data.assignment_id) || undefined, learningProgramAssignmentId: Number(data.learning_program_assignment_id) || undefined, subject: text(row.subject), topic: text(row.topic), stage: text(row.learner_stage), level: text(row.level), raw: data, questions }; }
export async function loadPracticeReview(row: ClassioRecord) {
  const repairedCount = await repairVisiblePracticeHistory([String(row.id)]);
  if (repairedCount) {
    const refreshed = await requireSupabase().from('practice_sessions').select('id,source_type,source_id,title,subject,topic,learner_stage,level,exercise_data,total_questions,correct_count,score_pct,xp_earned,best_streak,status').eq('id', row.id).maybeSingle();
    if (!refreshed.error && refreshed.data) row = refreshed.data as ClassioRecord;
  }
  const material = materialFromSession(row); if (!material) throw new Error('This practice session can no longer be opened.');
  const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id; if (!uid) throw new Error('Your session has expired.');
  const { data, error } = await client.from('practice_answers').select('exercise_idx,question_idx,student_answer').eq('session_id', Number(row.id)).eq('user_id', uid); if (error) throw error;
  const answerMap = new Map((data ?? []).map((answer) => [`${answer.exercise_idx}:${answer.question_idx}`, text(answer.student_answer)]));
  const answers = Object.fromEntries(material.questions.map((question, index) => [String(index), answerMap.get(`${question.exerciseIndex}:${question.questionIndex}`) || '']));
  const stored = { sessionId: text(row.id), total: Number(row.total_questions || 0), correct: Number(row.correct_count || 0), score: Number(row.score_pct || 0), xp: Number(row.xp_earned || 0), bestStreak: Number(row.best_streak || 0) } satisfies PracticeResult;
  // Early Expo sessions stored some word-search answer shapes as 0%. Regrade from
  // the saved found-word set when opening History and repair only an improved score.
  const includesWordSearch = material.questions.some((question) => question.exerciseType === 'word_search_vocab');
  const regraded = includesWordSearch ? gradePractice(material, answers) : null;
  if (regraded && regraded.total > 0 && regraded.score > stored.score) {
    const repaired = { sessionId: stored.sessionId, total: regraded.total, correct: regraded.correct, score: regraded.score, xp: Math.max(stored.xp, regraded.xp), bestStreak: Math.max(stored.bestStreak, regraded.bestStreak) } satisfies PracticeResult;
    const { error: repairError } = await client.from('practice_sessions').update({ total_questions: repaired.total, correct_count: repaired.correct, score_pct: repaired.score, xp_earned: repaired.xp, best_streak: repaired.bestStreak }).eq('id', Number(row.id)).eq('user_id', uid);
    if (!repairError) return { material, answers, result: repaired };
  }
  return { material, answers, result: stored };
}

export async function repairVisiblePracticeHistory(sessionIds: string[]): Promise<number> {
  const ids = sessionIds.map(Number).filter((id) => Number.isSafeInteger(id) && id > 0).slice(0, 18);
  if (!ids.length) return 0;
  const { data } = await requireSupabase().auth.getSession();
  if (!data.session?.access_token) return 0;
  const response = await fetch('/api/practice-regrade', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify({ kind: 'history', sessionIds: ids }) });
  if (!response.ok) return 0;
  const result = await response.json() as { repaired?: number };
  return Number(result.repaired || 0);
}
export function gradePractice(material: PracticeMaterial, answers: Record<string, string>) {
  let correct = 0; let streak = 0; let bestStreak = 0;
  const rows = material.questions.map((question, index) => { const studentAnswer = text(answers[String(index)]); let student = normalized(studentAnswer); let expected = normalized(question.answer); let correctCount = 0; let totalCount = 1; if (question.exerciseType === 'true_false') { student = canonicalTrueFalse(studentAnswer); expected = canonicalTrueFalse(question.answer); } else if (question.exerciseType === 'multiple_choice') { student = canonicalChoice(studentAnswer, question.options); expected = canonicalChoice(question.answer, question.options); } let isCorrect = Boolean(student) && student === expected; if (question.exerciseType === 'error_correction') isCorrect = Boolean(strictCorrection(studentAnswer)) && strictCorrection(studentAnswer) === strictCorrection(question.answer); if (!['multiple_choice','true_false','matching','error_correction'].includes(question.exerciseType) && !isCorrect && student && expected) { if (student.includes(expected) || expected.includes(student)) isCorrect = true; else { const expectedWords = answerWords(question.answer); const studentWords = answerWords(studentAnswer); const overlap = [...expectedWords].filter((word) => studentWords.has(word)).length; isCorrect = expectedWords.size > 0 && overlap / expectedWords.size >= 0.55; } } if (question.exerciseType === 'word_search_vocab') { const placedWords = wordSearchWords(question.placements?.map((placement) => placement.word) ?? []); const expectedWords = new Set(placedWords.length ? placedWords : wordSearchWords(question.words?.length ? question.words : question.vocabularyBank?.length ? question.vocabularyBank : question.answer)); const foundSet = new Set(wordSearchWords(studentAnswer)); correctCount = [...expectedWords].filter((word) => foundSet.has(word)).length; totalCount = expectedWords.size; isCorrect = totalCount > 0 && correctCount === totalCount; } else if (isCorrect) correctCount = 1; const writingFeedback = question.exerciseType === 'writing_prompt' ? evaluateWritingPrompt(studentAnswer, question.answer) : null; if (writingFeedback) { isCorrect = writingFeedback.isCorrect; correctCount = isCorrect ? 1 : 0; } correct += correctCount; if (correctCount) { streak += correctCount; bestStreak = Math.max(bestStreak, streak); } else streak = 0; return { ...question, studentAnswer, isCorrect, correctCount, totalCount, writingFeedback }; });
  const total = rows.reduce((sum, row) => sum + row.totalCount, 0); const score = practiceSessionScorePct(correct, total); const xp = correct * 5 + total + (correct === total && total > 0 ? 15 : 0) + (bestStreak > 2 ? (bestStreak - 2) * 2 : 0); return { rows, total, correct, score, bestStreak, xp };
}

export function practiceAnswerProgress(graded: ReturnType<typeof gradePractice>, answers: Record<string, string>) {
  const answered = graded.rows.reduce((sum, row, index) => sum + (row.exerciseType === 'word_search_vocab' ? row.correctCount : Number(Boolean(answers[String(index)]?.trim()))), 0);
  const ready = graded.rows.every((row, index) => row.exerciseType === 'word_search_vocab' ? row.correctCount > 0 : Boolean(answers[String(index)]?.trim()));
  return { answered, total: graded.total, ready };
}

export const PRACTICE_RANKS = [{ threshold: 0, key: 'newcomer', emoji: '🌱' }, { threshold: 200, key: 'learner', emoji: '📖' }, { threshold: 1000, key: 'rising_star', emoji: '⭐' }, { threshold: 3000, key: 'achiever', emoji: '🏅' }, { threshold: 8000, key: 'expert', emoji: '🏆' }, { threshold: 16000, key: 'master', emoji: '👑' }, { threshold: 30000, key: 'legend', emoji: '🔥' }] as const;
export function practiceRank(totalXp: number) { let index = 0; PRACTICE_RANKS.forEach((rank, rankIndex) => { if (totalXp >= rank.threshold) index = rankIndex; }); const rank = PRACTICE_RANKS[index]; const next = PRACTICE_RANKS[index + 1]; return { ...rank, next, into: totalXp - rank.threshold, span: next ? next.threshold - rank.threshold : 0, pct: next ? Math.min(100, Math.round((totalXp - rank.threshold) / (next.threshold - rank.threshold) * 100)) : 100 }; }
export function exerciseDataForMaterial(material: PracticeMaterial, draftAnswers?: Record<string, string>) { return { title: material.title, source_type: material.sourceType, source_id: material.sourceId, assignment_id: material.assignmentId ? Number(material.assignmentId) : undefined, learning_program_assignment_id: material.learningProgramAssignmentId, draft_answers: draftAnswers, exercises: material.questions.reduce<Record<string, unknown>[]>((groups, question) => { const key = question.exerciseIndex; if (!groups[key]) groups[key] = { type: question.exerciseType, title: question.sectionTitle, instructions: question.instructions, source_text: question.sourceText, visual_support: question.visualSupportUrl ? { image_url: question.visualSupportUrl } : undefined, vocabulary_bank: question.vocabularyBank, questions: [], answers: [] }; (groups[key].questions as unknown[]).push(question.exerciseType === 'word_search_vocab' ? { text: question.prompt, grid: question.grid, words: question.words, placements: question.placements } : { text: question.prompt, options: question.options }); (groups[key].answers as unknown[]).push(question.exerciseType === 'word_search_vocab' ? question.words : question.answer); return groups; }, []) }; }
export async function savePracticeDraft(material: PracticeMaterial, answers: Record<string, string>, sessionId?: string) {
  const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id;
  if (!uid) throw new Error('Your session has expired.');
  const now = new Date().toISOString();
  const payload = { source_type: material.sourceType, source_id: material.assignmentId || material.sourceId, title: material.title, subject: material.subject, topic: material.topic, learner_stage: material.stage, level: material.level, exercise_data: exerciseDataForMaterial(material, answers), total_questions: material.questions.length, correct_count: 0, score_pct: 0, xp_earned: 0, best_streak: 0, status: 'in_progress', completed_at: null };
  let savedId = sessionId;
  if (savedId) {
    const { data: updated, error } = await client.from('practice_sessions').update(payload).eq('id', Number(savedId)).eq('user_id', uid).eq('status', 'in_progress').select('id').maybeSingle();
    if (error) throw error;
    if (!updated) {
      const { data: existing, error: readError } = await client.from('practice_sessions').select('status').eq('id', Number(savedId)).eq('user_id', uid).maybeSingle();
      if (readError || existing?.status !== 'completed') throw readError ?? new Error('Practice draft is unavailable.');
      return savedId;
    }
  } else {
    const { data, error } = await client.from('practice_sessions').insert({ ...payload, user_id: uid, started_at: now, created_at: now }).select('id').single();
    if (error) throw error;
    savedId = String(data.id);
  }
  // Streamlit keeps draft answers both in the session snapshot and as per-question rows.
  // A single bounded delete/insert pair replaces the previous answer batch.
  const answerRows = gradePractice(material, answers).rows.map((row) => ({ session_id: Number(savedId), user_id: uid, exercise_idx: row.exerciseIndex, question_idx: row.questionIndex, exercise_type: row.exerciseType, student_answer: row.studentAnswer, correct_answer: row.answer, is_correct: row.isCorrect, answered_at: now }));
  if (answerRows.length) {
    const cleared = await client.from('practice_answers').delete().eq('session_id', Number(savedId)).eq('user_id', uid);
    if (cleared.error) console.warn('Practice draft answer replacement unavailable', cleared.error);
    else {
      const inserted = await client.from('practice_answers').insert(answerRows);
      if (inserted.error) console.warn('Practice draft answers unavailable', inserted.error);
    }
  }
  return savedId;
}
export async function savePractice(material: PracticeMaterial, answers: Record<string, string>, draftSessionId?: string): Promise<PracticeResult> {
  const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id; if (!uid) throw new Error('Your session has expired.');
  const graded = gradePractice(material, answers);
  const sessionId = draftSessionId || await savePracticeDraft(material, answers);
  const progressGroups = aggregatePracticeProgress(graded.rows, graded.xp);
  const result = {
    source_type: material.sourceType, source_id: String(material.assignmentId || material.sourceId),
    material_source_id: String(material.sourceId), exercise_data: exerciseDataForMaterial(material),
    total: graded.total, correct: graded.correct, score: graded.score, xp: graded.xp,
    best_streak: graded.bestStreak, graded,
    assignment_id: material.assignmentId || null, teacher_id: material.teacherId || null,
    learning_program_assignment_id: material.learningProgramAssignmentId || null,
    answers: graded.rows.map((row) => ({ exercise_index: row.exerciseIndex, question_index: row.questionIndex, exercise_type: row.exerciseType, student_answer: row.studentAnswer, correct_answer: row.answer, is_correct: row.isCorrect })),
    progress: progressGroups.map((group) => ({ exercise_type: group.exerciseType, attempted: group.attempted, correct: group.correct, xp: group.xp })),
  };
  const { data, error } = await client.rpc('classio_complete_student_practice', { p_session_id: Number(sessionId), p_result: result });
  if (error || !data) throw error ?? new Error('Practice completion was not confirmed.');
  return { sessionId: String(data), total: graded.total, correct: graded.correct, score: graded.score, xp: graded.xp, bestStreak: graded.bestStreak };
}
export async function requestTeacherReview(material: PracticeMaterial, sessionId: string, note: string, selectedTeacherId?: string) {
  const teacherId = material.teacherId || selectedTeacherId; if (!teacherId) throw new Error('Choose a connected teacher for this review.'); const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id; if (!uid) throw new Error('Your session has expired.');
  if (material.assignmentId) { const { error } = await client.rpc('classio_request_teacher_revision', { p_assignment_id: Number(material.assignmentId), p_practice_session_id: Number(sessionId) }); if (!error) return; }
  const now = new Date().toISOString();
  const fallback = await client.from('teacher_review_requests').upsert({ teacher_id: teacherId, student_id: uid, subject_key: material.subject, subject_label: material.subject, practice_session_id: Number(sessionId), assignment_id: material.assignmentId ? Number(material.assignmentId) : null, source_type: material.sourceType, source_id: material.sourceId, title: material.title, status: 'requested', request_note: note.trim(), requested_at: now, updated_at: now }, { onConflict: 'teacher_id,practice_session_id' }); if (fallback.error) throw fallback.error;
}
export async function recordVideoWatch(video: VideoPracticeInput) {
  const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id; if (!uid) throw new Error('Your session has expired.'); const now = new Date().toISOString(); const xp = 6; const sourceId = video.assignmentId || video.id; const session = await client.from('practice_sessions').insert({ user_id: uid, source_type: 'video', source_id: sourceId, title: video.title, subject: video.subject, topic: video.topic, learner_stage: video.stage, level: video.level, exercise_data: { source_type: 'video', source_id: video.id, title: video.title, subject: video.subject, topic: video.topic, level: video.level, watch_url: video.url, engagement_type: 'video_watch' }, total_questions: 1, correct_count: 0, score_pct: 0, xp_earned: xp, best_streak: 1, status: 'completed', started_at: now, completed_at: now, created_at: now }).select('id').single(); if (session.error) throw session.error;
  const scopeKey = video.assignmentId ? `assignment:${video.assignmentId}` : 'independent'; const current = await client.from('practice_progress').select('id,total_attempted,total_correct,total_xp,best_streak').eq('user_id', uid).eq('scope_key', scopeKey).eq('source_type', 'video').eq('subject', video.subject).eq('topic', video.topic).eq('exercise_type', 'video_watch').eq('level', video.level).maybeSingle(); const progressPayload = { user_id: uid, scope_key: scopeKey, source_type: 'video', teacher_id: video.teacherId || null, assignment_id: video.assignmentId ? Number(video.assignmentId) : null, subject: video.subject, topic: video.topic, exercise_type: 'video_watch', level: video.level, total_attempted: Number(current.data?.total_attempted || 0) + 1, total_correct: Number(current.data?.total_correct || 0), accuracy_pct: 0, total_xp: Number(current.data?.total_xp || 0) + xp, best_streak: Math.max(1, Number(current.data?.best_streak || 0)), last_practiced: now }; const progress = current.data?.id ? await client.from('practice_progress').update(progressPayload).eq('id', current.data.id) : await client.from('practice_progress').insert({ ...progressPayload, created_at: now }); if (progress.error) throw progress.error;
  if (video.assignmentId && video.teacherId) { const attempts = await client.from('teacher_assignment_attempts').select('id').eq('assignment_id', Number(video.assignmentId)).eq('student_id', uid); const attempt = await client.from('teacher_assignment_attempts').insert({ assignment_id: Number(video.assignmentId), teacher_id: video.teacherId, student_id: uid, practice_session_id: session.data.id, attempt_number: (attempts.data?.length || 0) + 1, status: 'completed', score_pct: 100, total_questions: 1, correct_count: 1, submission_payload: { source_type: 'video', source_id: video.id, title: video.title, watch_event: 'student_video_watch' }, started_at: now, submitted_at: now, graded_at: now, completed_at: now, created_at: now, updated_at: now }); if (attempt.error) throw attempt.error; const assignment = await client.from('teacher_assignments').update({ status: 'completed', score_pct: 100, total_questions: 1, correct_count: 1, opened_at: now, submitted_at: now, graded_at: now, completed_at: now, updated_at: now }).eq('id', Number(video.assignmentId)).eq('student_id', uid); if (assignment.error) throw assignment.error; }
  return String(session.data.id);
}
type ScopedRecommendation = PublicResource & { learningProgramAssignmentId?: number; learningProgramTopicId?: number; programId?: number; mlScore?: number; mlBlendWeight?: number; recommendationScore?: number };

async function logRecommendationActivity(resources: ScopedRecommendation[], surface: string, activityType: 'student_recommendation_impression' | 'student_recommendation_open') {
  const validResources = resources.filter((resource) => Number.isSafeInteger(Number(resource.id)) && Number(resource.id) > 0).slice(0, 12);
  if (!validResources.length) return;
  const { data } = await requireSupabase().auth.getSession();
  const token = data.session?.access_token;
  if (!token) return;
  const response = await fetch('/api/student-recommendation-feedback', {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ events: validResources.map((resource) => ({ activityType, surface, resourceKind: resource.kind, resourceId: Number(resource.id), title: resource.title, subject: resource.subject, topic: resource.topic, level: resource.level, assignedResource: false, programId: resource.programId, learningProgramAssignmentId: resource.learningProgramAssignmentId, learningProgramTopicId: resource.learningProgramTopicId, score: resource.recommendationScore, mlScore: resource.mlScore, mlBlendWeight: resource.mlBlendWeight })) }),
  });
  if (!response.ok) throw new Error('Recommendation activity could not be recorded.');
}

export async function logStudentRecommendation(resources: ScopedRecommendation[], surface: string) {
  const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id; if (!uid || !resources.length) return;
  const cycle = new Date().toISOString().slice(0, 13); const shownAt = new Date().toISOString();
  const { error } = await client.from('resource_exposures').upsert(resources.map((resource, index) => { const assignmentId = resource.learningProgramAssignmentId || 0; const topicId = resource.learningProgramTopicId || 0; const exposure = `${uid}:${surface}:${cycle}:${assignmentId}:${topicId}:${resource.kind}:${resource.id}`; const learned = Number.isFinite(resource.mlScore) ? resource.mlScore! : 0; const blend = Number.isFinite(resource.mlBlendWeight) ? resource.mlBlendWeight! : 0; const final = Number.isFinite(resource.recommendationScore) ? resource.recommendationScore! : 0; return { exposure_id: exposure, idempotency_key: exposure, student_id: uid, viewer_user_id: uid, resource_id: resource.id, resource_type: resource.kind, exposure_type: 'optional_student_recommendation', surface, position: index + 1, learning_program_assignment_id: assignmentId || null, learning_program_topic_id: topicId || null, shown_at: shownAt, model_component_id: 'student_recommendation_ranker', model_version: 'expo-port-v1', heuristic_score: final - blend * learned, learned_score: learned, final_score: final, context_json: { subject: resource.subject, topic: resource.topic, level: resource.level, assigned_resource: false, ml_blend_weight: blend, program_id: resource.programId || null, learning_program_assignment_id: assignmentId || null, learning_program_topic_id: topicId || null } }; }), { onConflict: 'idempotency_key', ignoreDuplicates: true });
  if (error) throw error;
  await logRecommendationActivity(resources, surface, 'student_recommendation_impression').catch((reason) => console.warn('Recommendation impression activity unavailable', reason));
}

export async function logStudentRecommendationOpen(resource: ScopedRecommendation, surface: string) {
  const client = requireSupabase(); const auth = await client.auth.getUser(); const uid = auth.data.user?.id;
  if (!uid || !resource.id) return;
  let lookup = client.from('resource_exposures').select('exposure_id').eq('student_id', uid).eq('surface', surface).eq('resource_type', resource.kind).eq('resource_id', resource.id).eq('exposure_type', 'optional_student_recommendation');
  lookup = resource.learningProgramAssignmentId ? lookup.eq('learning_program_assignment_id', resource.learningProgramAssignmentId) : lookup.is('learning_program_assignment_id', null);
  lookup = resource.learningProgramTopicId ? lookup.eq('learning_program_topic_id', resource.learningProgramTopicId) : lookup.is('learning_program_topic_id', null);
  const latest = await lookup.gte('shown_at', new Date(Date.now() - 60 * 60 * 1000).toISOString()).order('shown_at', { ascending: false }).limit(1).maybeSingle();
  if (latest.error) throw latest.error;
  let exposureId = latest.data?.exposure_id;
  if (!exposureId) {
    await logStudentRecommendation([resource], surface);
    exposureId = `${uid}:${surface}:${new Date().toISOString().slice(0, 13)}:${resource.learningProgramAssignmentId || 0}:${resource.learningProgramTopicId || 0}:${resource.kind}:${resource.id}`;
  }
  const { error } = await client.from('resource_exposure_events').upsert({ exposure_id: exposureId, event_type: 'opened', event_at: new Date().toISOString(), idempotency_key: `${exposureId}:opened`, student_id: uid, viewer_user_id: uid }, { onConflict: 'idempotency_key', ignoreDuplicates: true });
  if (error) throw error;
  await logRecommendationActivity([resource], surface, 'student_recommendation_open').catch((reason) => console.warn('Recommendation open activity unavailable', reason));
  invalidateStudentRecommendationFeedback();
}
