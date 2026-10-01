import { canonicalSubjectKey } from '@/lib/subjects';
import type { ClassioRecord } from '@/services/classio-data';

type NumericMap = Record<string, number>;

export type StudentNeedProfile = {
  primarySubjects: string[];
  subjectNeed: NumericMap;
  subjectAttempts: NumericMap;
  topicNeed: NumericMap;
  exerciseNeed: NumericMap;
  subjectLevel: Record<string, string>;
  subjectStage: Record<string, string>;
  defaultStage: string;
  overallAccuracy: NumericMap;
  weights: number[];
};

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const sigmoid = (value: number) => 1 / (1 + Math.exp(-value));
const number = (value: unknown) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; };
const text = (value: unknown) => String(value || '').trim();

function daysSince(value: unknown, now: number) {
  if (!value) return 999;
  const timestamp = Date.parse(String(value));
  return Number.isFinite(timestamp) ? Math.max(0, (now - timestamp) / 86400000) : 999;
}

function features(row: ClassioRecord, now: number) {
  const accuracy = number(row.accuracy_pct) / 100;
  const attempted = number(row.total_attempted);
  return [1, clamp(1 - accuracy), clamp(Math.min(attempted, 12) / 12), clamp(Math.min(daysSince(row.last_practiced, now), 30) / 30)];
}

export function fitStudentNeedWeights(progress: ClassioRecord[], now = Date.now()) {
  if (!progress.length) return [-0.1, 2.2, 0.7, 0.9];
  const rows = progress.map((row) => features(row, now));
  const targets = progress.map((row) => {
    const accuracy = number(row.accuracy_pct);
    const attempted = number(row.total_attempted);
    return accuracy < 78 || (accuracy < 88 && attempted <= 2) ? 1 : 0;
  });
  const weights = [0, 1.4, 0.4, 0.5];
  for (let epoch = 0; epoch < 120; epoch += 1) {
    const gradients = [0, 0, 0, 0];
    rows.forEach((row, index) => {
      const error = sigmoid(row.reduce((sum, value, featureIndex) => sum + weights[featureIndex] * value, 0)) - targets[index];
      row.forEach((value, featureIndex) => { gradients[featureIndex] += error * value; });
    });
    weights.forEach((weight, index) => { weights[index] = weight - 0.35 * gradients[index] / rows.length; });
  }
  return weights;
}

export function buildStudentNeedProfile(progress: ClassioRecord[], primarySubjects: string[] = [], defaultStage = '', now = Date.now()): StudentNeedProfile {
  const profile: StudentNeedProfile = {
    primarySubjects: primarySubjects.map(canonicalSubjectKey),
    subjectNeed: {}, subjectAttempts: {}, topicNeed: {}, exerciseNeed: {},
    subjectLevel: {}, subjectStage: {}, defaultStage,
    overallAccuracy: {}, weights: fitStudentNeedWeights(progress, now),
  };
  const levelVotes = new Map<string, Map<string, number>>();
  const stageVotes = new Map<string, Map<string, number>>();
  const accuracyTotals = new Map<string, { correct: number; attempted: number }>();
  for (const row of progress) {
    const subject = canonicalSubjectKey(row.subject);
    const topic = text(row.topic).toLocaleLowerCase();
    const exercise = text(row.exercise_type);
    const level = text(row.level);
    const stage = text(row.learner_stage);
    const accuracy = number(row.accuracy_pct) / 100;
    const attempted = number(row.total_attempted);
    const vector = features(row, now);
    const strength = sigmoid(vector.reduce((sum, value, index) => sum + profile.weights[index] * value, 0));
    profile.subjectNeed[subject] = Math.max(strength, profile.subjectNeed[subject] || 0);
    if (topic) profile.topicNeed[topic] = Math.max(strength, profile.topicNeed[topic] || 0);
    if (exercise) profile.exerciseNeed[exercise] = Math.max(strength, profile.exerciseNeed[exercise] || 0);
    profile.subjectAttempts[subject] = (profile.subjectAttempts[subject] || 0) + attempted;
    const total = accuracyTotals.get(subject) || { correct: 0, attempted: 0 };
    total.correct += attempted * accuracy;
    total.attempted += attempted;
    accuracyTotals.set(subject, total);
    if (level) { const votes = levelVotes.get(subject) || new Map<string, number>(); votes.set(level, (votes.get(level) || 0) + attempted); levelVotes.set(subject, votes); }
    if (stage) { const votes = stageVotes.get(subject) || new Map<string, number>(); votes.set(stage, (votes.get(stage) || 0) + attempted); stageVotes.set(subject, votes); }
  }
  for (const [subject, votes] of levelVotes) profile.subjectLevel[subject] = [...votes].sort((a, b) => b[1] - a[1])[0]?.[0] || '';
  for (const [subject, votes] of stageVotes) profile.subjectStage[subject] = [...votes].sort((a, b) => b[1] - a[1])[0]?.[0] || '';
  for (const [subject, total] of accuracyTotals) profile.overallAccuracy[subject] = total.attempted ? total.correct / total.attempted : 0;
  return profile;
}
