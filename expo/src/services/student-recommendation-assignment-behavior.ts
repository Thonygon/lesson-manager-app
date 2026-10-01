import type { ClassioRecord } from '@/services/classio-data';
import { studentTopicTokens } from '@/services/student-recommendation-programs';

const kindMap: Record<string, string> = { lesson_plan_topic: 'plan', worksheet: 'worksheet', exam: 'exam' };
const text = (value: unknown) => String(value || '').trim();

export function buildStudentAssignmentBehavior(assignments: ClassioRecord[]) {
  const kindSuccess: Record<string, number> = {};
  const kindCompletion: Record<string, number> = {};
  const topicSuccess: Record<string, number> = {};
  const recentTeacherTopics = new Set<string>();
  const kindScores = new Map<string, { count: number; total: number }>();
  const kindCompletions = new Map<string, { assigned: number; completed: number }>();
  const topicScores = new Map<string, { count: number; total: number }>();
  for (const row of assignments) {
    const kind = kindMap[text(row.assignment_type)];
    if (!kind) continue;
    const topic = text(row.topic || row.title);
    const status = text(row.status).toLocaleLowerCase();
    const rawScore = row.score_pct;
    const score = rawScore === null || rawScore === undefined || rawScore === '' ? null : Number(rawScore);
    const validScore = score !== null && Number.isFinite(score);
    if (topic && ['started', 'submitted', 'graded', 'completed'].includes(status)) {
      for (const token of studentTopicTokens(topic)) recentTeacherTopics.add(token);
    }
    const stats = kindScores.get(kind) || { count: 0, total: 0 };
    const completion = kindCompletions.get(kind) || { assigned: 0, completed: 0 };
    completion.assigned += 1;
    if (['graded', 'completed'].includes(status)) completion.completed += 1;
    if (validScore) { stats.count += 1; stats.total += score; }
    kindScores.set(kind, stats);
    kindCompletions.set(kind, completion);
    if (topic) {
      const key = topic.toLocaleLowerCase();
      const topicStats = topicScores.get(key) || { count: 0, total: 0 };
      if (validScore) { topicStats.count += 1; topicStats.total += score; }
      topicScores.set(key, topicStats);
    }
  }
  for (const [kind, stats] of kindScores) kindSuccess[kind] = stats.count ? stats.total / stats.count / 100 : 0;
  for (const [kind, stats] of kindCompletions) kindCompletion[kind] = stats.assigned ? stats.completed / stats.assigned : 0;
  for (const [topic, stats] of topicScores) topicSuccess[topic] = stats.count ? stats.total / stats.count / 100 : 0;
  return { kindSuccess, kindCompletion, topicSuccess, recentTeacherTopics };
}
