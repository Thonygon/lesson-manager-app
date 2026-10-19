import { canonicalSubjectKey } from '@/lib/subjects';
import type { PublicResource } from '@/services/public-data';

type PlanTask = { title: string; detail?: string };

const GOAL_WEIGHTS: Record<string, Partial<Record<PublicResource['kind'], number>>> = {
  exam_preparation: { exam: 1.8, worksheet: 0.85, video: 0.25 }, review_mistakes: { worksheet: 1.35, exam: 0.95, video: 0.35 },
  improve_reading: { worksheet: 1.2, exam: 0.8, video: 0.45 }, improve_vocabulary: { worksheet: 1.15, video: 0.8, exam: 0.55 },
  improve_grammar: { worksheet: 1.2, exam: 0.7, video: 0.25 }, improve_speaking: { video: 1.45, worksheet: 0.7, exam: 0.2 },
  problem_solving: { worksheet: 1.25, exam: 0.9, video: 0.25 }, equation_confidence: { worksheet: 1.2, exam: 0.8, video: 0.2 },
  concept_understanding: { video: 1, worksheet: 1, exam: 0.45 }, general_practice: { worksheet: 1, exam: 0.8, video: 0.6 },
  homework_support: { worksheet: 1.1, exam: 0.8, video: 0.55 },
};

const STOP_WORDS = new Set(['the', 'and', 'for', 'with', 'from', 'your', 'about', 'para', 'con', 'del', 'las', 'los', 'una', 'de', 'en', 'la', 'el']);

function tokens(value: unknown): Set<string> {
  return new Set(String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
    .split(/[^\p{L}\p{N}]+/u).filter((word) => word.length >= 3 && !STOP_WORDS.has(word)));
}

function topicScore(task: PlanTask, resource: PublicResource): number {
  const request = tokens(`${task.title} ${task.detail ?? ''}`);
  const candidate = tokens(`${resource.topic} ${resource.title} ${resource.description}`);
  if (!request.size || !candidate.size) return 0;
  const shared = [...request].filter((word) => candidate.has(word)).length;
  if (!shared) return 0;
  const overlap = shared / request.size;
  const topic = String(resource.topic || '').trim().toLocaleLowerCase();
  const title = String(task.title || '').trim().toLocaleLowerCase();
  return overlap + (topic && title && (topic === title || topic.includes(title) || title.includes(topic)) ? 1 : 0);
}

export function selectSmartPlanResources(resources: PublicResource[], subject: string, tasks: PlanTask[], limit = 6, goal = 'general_practice'): PublicResource[] {
  if (!tasks.length || !subject.trim()) return [];
  const requestedSubject = canonicalSubjectKey(subject);
  const candidates = resources.flatMap((resource, index) => {
    if (!['worksheet', 'exam', 'video'].includes(resource.kind)) return [];
    if (canonicalSubjectKey(resource.subject) !== requestedSubject) return [];
    const taskScores = tasks.map((task) => topicScore(task, resource));
    const strongest = Math.max(...taskScores);
    const score = strongest + (GOAL_WEIGHTS[goal]?.[resource.kind] ?? 0.55) / 10;
    return strongest > 0 ? [{ resource, score, index, taskIndex: taskScores.indexOf(strongest) }] : [];
  }).sort((a, b) => b.score - a.score || a.index - b.index);
  const selected: typeof candidates = [];
  const seenResources = new Set<string>();
  const coveredTasks = new Set<number>();
  for (const item of candidates) {
    if (selected.length >= Math.min(limit, 3)) break;
    const key = `${item.resource.kind}:${item.resource.id}`;
    if (seenResources.has(key) || coveredTasks.has(item.taskIndex)) continue;
    selected.push(item); seenResources.add(key); coveredTasks.add(item.taskIndex);
  }
  for (const item of candidates) {
    if (selected.length >= limit) break;
    const key = `${item.resource.kind}:${item.resource.id}`;
    if (seenResources.has(key)) continue;
    selected.push(item); seenResources.add(key);
  }
  return selected.map(({ resource }) => resource);
}
