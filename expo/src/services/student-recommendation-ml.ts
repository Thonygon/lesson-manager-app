import { canonicalSubjectKey } from '@/lib/subjects';
import type { StudentWorkspace } from '@/services/student-data';
import type { ClassioRecord } from '@/services/classio-data';
import { buildStudentProgramSignals, studentTopicTokens } from '@/services/student-recommendation-programs';
import { buildStudentTopicAlignment } from '@/services/student-recommendation-topic-alignment';

type Features = Record<string, number>;
type Sample = { features: Features; target: number; diagnosticTarget?: number; timestamp?: string };
type StudentModel = { weights: Features; sampleCount: number; blendWeight: number };
const modelCache = new WeakMap<StudentWorkspace, Partial<Record<'live' | 'history', StudentModel>>>();

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const sigmoid = (value: number) => 1 / (1 + Math.exp(-value));
const number = (value: unknown) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; };
const text = (value: unknown) => String(value ?? '').trim();
const key = (value: unknown) => text(value).toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '');
const overlap = (left: Set<string>, right: Set<string>) => left.size && right.size ? clamp([...left].filter((token) => right.has(token)).length / 3) : 0;

type MlHistorySignals = { subjects: Set<string>; subjectLevels: Record<string, string>; topicTokens: Set<string>; activeTopicIds: Set<number>; sessions: ClassioRecord[]; assignments: ClassioRecord[] };

/** Streamlit's report profile is built from 180-day practice and assignment history. */
export function buildStudentMlHistorySignals(workspace: StudentWorkspace, clock = Date.now()): MlHistorySignals {
  const cutoff = clock - 180 * 86400000;
  const recent = (value: unknown) => { const stamp = Date.parse(text(value)); return Number.isFinite(stamp) && stamp >= cutoff; };
  const sessions = (workspace.sessions ?? []).filter((row) => recent(row.created_at))
    .sort((a, b) => text(b.created_at).localeCompare(text(a.created_at))).slice(0, 800);
  const assignments = (workspace.mlHistoryAssignments ?? workspace.assignments ?? []).filter((row) => key(row.status) !== 'archived' && recent(row.updated_at))
    .sort((a, b) => text(b.updated_at).localeCompare(text(a.updated_at))).slice(0, 800);
  const subjects = new Set<string>();
  const topicTokens = new Set<string>();
  const activeTopicIds = new Set<number>();
  const levels = new Map<string, Map<string, number>>();
  for (const row of sessions) {
    const subject = canonicalSubjectKey(row.subject);
    if (subject) subjects.add(subject);
    const level = text(row.level);
    if (subject && level) {
      const counts = levels.get(subject) ?? new Map<string, number>();
      counts.set(level, (counts.get(level) ?? 0) + 1);
      levels.set(subject, counts);
    }
    for (const token of studentTopicTokens(row.topic)) topicTokens.add(token);
  }
  for (const row of assignments) {
    const subject = canonicalSubjectKey(row.subject_key);
    if (subject) subjects.add(subject);
    for (const token of studentTopicTokens(row.topic)) topicTokens.add(token);
    const topicId = number(row.learning_program_topic_id);
    if (topicId > 0) activeTopicIds.add(topicId);
  }
  const subjectLevels: Record<string, string> = {};
  for (const [subject, counts] of levels) {
    const mostCommon = [...counts].sort((a, b) => b[1] - a[1])[0];
    if (mostCommon) subjectLevels[subject] = mostCommon[0];
  }
  return { subjects, subjectLevels, topicTokens, activeTopicIds, sessions, assignments };
}

export const BASE_STUDENT_ML_WEIGHTS: Features = {
  bias: -0.12, subject_in_program: 0.7, level_fit: 0.45, stage_fit: 0.28,
  next_topic_overlap: 0.72, review_topic_overlap: 0.82, pending_topic_overlap: 0.46,
  program_subject_fit: 0.4, program_type_fit: 0.26, topic_need: 0.84,
  subject_need: 0.52, exercise_need: 0.36, completion_fit: 0.28,
  format_fit: 0.24, semantic_affinity: 0.44, explicit_topic_match: 0.82,
  explicit_topic_support: 0.28, direct_topic_link: 0.54, topic_kind_prior: 0.34,
  topic_match_ambiguity: -0.22, topic_success_penalty: -0.18,
};

/** Same sigmoid gradient update, learning rate, and L2 penalty as Python's _fit_linear_model. */
export function fitStudentRecommendationModel(samples: Sample[], baseWeights: Features = BASE_STUDENT_ML_WEIGHTS): Features {
  if (!samples.length) return { ...baseWeights };
  const names = new Set(['bias', ...Object.keys(baseWeights), ...samples.flatMap((sample) => Object.keys(sample.features))]);
  const weights = Object.fromEntries([...names].map((name) => [name, number(baseWeights[name])]));
  for (let step = 0; step < 140; step += 1) {
    const gradients = Object.fromEntries([...names].map((name) => [name, 0]));
    for (const sample of samples) {
      const prediction = scoreStudentRecommendationModel(weights, sample.features);
      const error = prediction - clamp(sample.target);
      for (const name of names) gradients[name] += error * (name === 'bias' ? 1 : number(sample.features[name]));
    }
    for (const name of names) {
      const penalty = name === 'bias' ? 0 : 0.01 * weights[name];
      weights[name] -= 0.16 * (gradients[name] / samples.length + penalty);
    }
  }
  return weights;
}

export function scoreStudentRecommendationModel(weights: Features, features: Features): number {
  return sigmoid(number(weights.bias) + Object.entries(features).reduce((sum, [name, value]) => sum + number(weights[name]) * number(value), 0));
}

/** Python's held-out F1/AUC blend calibration, with the source's low-data fallback. */
export function studentRecommendationBlendWeight(samples: Sample[]): number {
  if (samples.length < 6) return 0.42;
  const ordered = [...samples].sort((a, b) => text(a.timestamp).localeCompare(text(b.timestamp)));
  const split = Math.min(ordered.length - 1, Math.max(4, Math.floor(ordered.length * 0.7)));
  const training = ordered.slice(0, split);
  const evaluation = ordered.slice(split);
  const { semantic_affinity: _unused, ...diagnosticWeights } = BASE_STUDENT_ML_WEIGHTS;
  void _unused;
  const weights = fitStudentRecommendationModel(training.map((sample) => ({ ...sample, target: sample.diagnosticTarget ?? sample.target })), diagnosticWeights);
  const labels = evaluation.map((sample) => Number((sample.diagnosticTarget ?? sample.target) >= 0.62));
  const scores = evaluation.map((sample) => scoreStudentRecommendationModel(weights, sample.features));
  let tp = 0; let fp = 0; let fn = 0;
  labels.forEach((label, index) => { const predicted = Number(scores[index] >= 0.5); if (predicted && label) tp += 1; else if (predicted) fp += 1; else if (label) fn += 1; });
  const precision = tp / Math.max(1, tp + fp);
  const recall = tp / Math.max(1, tp + fn);
  const f1 = precision + recall ? 2 * precision * recall / (precision + recall) : 0;
  const positives = scores.filter((_, index) => labels[index] === 1);
  const negatives = scores.filter((_, index) => labels[index] === 0);
  const auc = positives.length && negatives.length
    ? positives.reduce((sum, positive) => sum + negatives.reduce((wins, negative) => wins + (positive > negative ? 1 : positive === negative ? 0.5 : 0), 0), 0) / (positives.length * negatives.length)
    : 0.5;
  return Math.max(0.35, Math.min(0.72, 0.32 + 0.42 * Math.max(f1, auc - 0.15) + (samples.length >= 12 ? 0.08 : 0)));
}

/** Live recommendations use active-program signals; historical comparison fixtures use history-derived signals. */
export function buildStudentRecommendationModel(workspace: StudentWorkspace, now?: number, mode: 'live' | 'history' = 'live'): StudentModel {
  if (now === undefined) {
    const cached = modelCache.get(workspace)?.[mode];
    if (cached) return cached;
  }
  const clock = now ?? Date.now();
  const history = buildStudentMlHistorySignals(workspace, clock);
  const signals = mode === 'live' ? buildStudentProgramSignals(workspace) : history;
  const alignment = buildStudentTopicAlignment(workspace.alignmentAssignments ?? workspace.assignments, workspace.recommendationEvents, workspace.topicVideoLinks, clock);
  const samples: Sample[] = [];
  const diagnosticSamples: Sample[] = [];
  for (const row of history.sessions) {
    const kind = key(row.source_type);
    const subject = canonicalSubjectKey(row.subject);
    const level = key(row.level);
    const sample = { target: 0.3 + 0.7 * number(row.score_pct) / 100, timestamp: text(row.completed_at || row.created_at), features: {
      [`kind_${kind}`]: Number(Boolean(kind)),
      subject_in_program: Number(signals.subjects.has(subject)),
      level_fit: Number(Boolean(level) && level === key(signals.subjectLevels[subject])),
      topic_in_program: overlap(studentTopicTokens(row.topic), signals.topicTokens),
    } };
    samples.push(sample);
    if (['worksheet', 'exam', 'video'].includes(kind)) diagnosticSamples.push(sample);
  }
  for (const row of history.assignments) {
    const kind = key(row.assignment_type);
    if (!['worksheet', 'exam', 'video'].includes(kind)) continue;
    const subject = canonicalSubjectKey(row.subject_key);
    const status = key(row.status);
    const score = number(row.score_pct) / 100;
    const target = ['graded', 'completed'].includes(status) ? 0.4 + 0.6 * score
      : ['started', 'submitted'].includes(status) ? 0.45
        : ['assigned', 'overdue'].includes(status) && kind === 'video' ? 0.3 : 0.2;
    const topicId = number(row.learning_program_topic_id);
    const linked = alignment(kind, row.source_record_id, topicId > 0 ? [topicId] : signals.activeTopicIds);
    const sample = { target, timestamp: text(row.updated_at || row.created_at), features: {
      [`kind_${kind}`]: 1,
      subject_in_program: Number(signals.subjects.has(subject)),
      topic_in_program: overlap(studentTopicTokens(row.topic), signals.topicTokens),
      explicit_topic_match: linked.explicitTopicMatch,
      explicit_topic_support: linked.explicitTopicSupport,
      direct_topic_link: linked.directTopicLink,
      topic_kind_prior: linked.topicKindPrior,
      topic_match_ambiguity: linked.topicMatchAmbiguity,
    } };
    samples.push(sample);
    diagnosticSamples.push(sample);
  }
  for (const row of (workspace.recommendationFeedback ?? []).slice(0, 800)) {
    const activity = key(row.activity_type);
    if (!['student_recommendation_impression', 'student_recommendation_open'].includes(activity)) continue;
    const meta = row.meta_json && typeof row.meta_json === 'object' ? row.meta_json as Record<string, unknown> : {};
    const kind = key(meta.resource_kind);
    if (!kind) continue;
    const subject = canonicalSubjectKey(meta.subject);
    const level = key(meta.level);
    const opened = activity === 'student_recommendation_open';
    const sample = { target: opened ? 0.76 : 0.18, diagnosticTarget: opened ? 0.78 : 0.16, timestamp: text(row.created_at), features: {
      [`kind_${kind}`]: 1,
      subject_in_program: Number(signals.subjects.has(subject)),
      level_fit: Number(Boolean(level) && level === key(signals.subjectLevels[subject])),
      topic_in_program: overlap(studentTopicTokens(meta.topic), signals.topicTokens),
      program_type_fit: Number(Boolean(meta.assigned_resource)),
      completion_fit: number(meta.ml_blend_weight),
      topic_need: number(meta.ml_score),
    } };
    samples.push(sample);
    diagnosticSamples.push(sample);
  }
  const model = { weights: fitStudentRecommendationModel(samples), sampleCount: samples.length, blendWeight: studentRecommendationBlendWeight(diagnosticSamples) };
  if (now === undefined) modelCache.set(workspace, { ...modelCache.get(workspace), [mode]: model });
  return model;
}
