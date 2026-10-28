import type { PublicResource } from '@/services/public-data';
import type { StudentWorkspace } from '@/services/student-data';
import { canonicalSubjectKey } from '@/lib/subjects';
import { scoreStudentRecommendationCandidates } from '@/services/student-recommendation-ranking';
import { buildStudentRecommendationEligibility } from '@/services/student-recommendation-safety';
import { semanticTextAffinity } from '@/services/student-recommendation-semantic';

export type MissionTask = { title: string; detail?: string };

const missionWords = (value: string) => new Set(value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().split(/[^\p{L}\p{N}]+/u).filter((word) => word.length >= 3 && !['the', 'and', 'for', 'with', 'your', 'topic', 'tema', 'unit', 'unidad', 'lesson', 'clase', 'de', 'del', 'las', 'los', 'para', 'con'].includes(word)));

export function missionTopicFit(task: MissionTask, resource: PublicResource): number {
  const title = task.title.replace(/^(?:topic|tema|unit|unidad)\s*\d+\s*[:.\-–]?\s*/i, '').trim();
  const desired = missionWords(title);
  const actual = missionWords(`${resource.topic} ${resource.title}`);
  if (!desired.size || !actual.size) return 0;
  const shared = [...desired].filter((word) => actual.has(word)).length;
  const overlap = shared / desired.size;
  const semantic = semanticTextAffinity([title], [resource.topic || resource.title]);
  return Math.max(overlap, semantic);
}

export function smartPlanMissionResources(resources: PublicResource[], subject: string, task: MissionTask, goal: string, workspace: StudentWorkspace | null = null): PublicResource[] {
  const eligible = workspace ? buildStudentRecommendationEligibility(workspace) : () => true;
  const rank = (kind: 'worksheet' | 'exam') => {
    // A mission must match its own topic. The general learner ranker only
    // orders candidates after this gate; it cannot introduce a different topic.
    const candidates = resources.filter((item) => item.kind === kind && canonicalSubjectKey(item.subject) === canonicalSubjectKey(subject) && eligible(item) && missionTopicFit(task, item) >= 0.55)
      .sort((left, right) => missionTopicFit(task, right) - missionTopicFit(task, left)).slice(0, 8);
    if (!workspace || !candidates.length) return candidates.slice(0, 3);
    const scored = scoreStudentRecommendationCandidates(candidates, workspace);
    return (scored.length ? scored.map((row) => row.resource) : candidates).slice(0, 3);
  };
  const worksheets = rank('worksheet');
  const exams = rank('exam');
  return [...worksheets, ...exams];
}

export function passedMissionResourceIds(workspace: StudentWorkspace | null, minimumScore = 70): Set<string> {
  const passed = new Set<string>();
  const assignments = new Map((workspace?.assignments ?? []).map((row) => [String(row.id || ''), row]));
  for (const session of workspace?.sessions ?? []) {
    const kind = String(session.source_type || '');
    const id = String(session.source_id || '');
    if (!['worksheet', 'exam'].includes(kind) || !id || String(session.status || '').toLocaleLowerCase() !== 'completed' || Number(session.score_pct || 0) < minimumScore) continue;
    passed.add(`${kind}:${id}`);
    const assignment = assignments.get(id);
    if (assignment && String(assignment.assignment_type || '') === kind && assignment.source_record_id) passed.add(`${kind}:${assignment.source_record_id}`);
  }
  return passed;
}

export function smartPlanMissionComplete(missions: PublicResource[], passed: Set<string>): boolean {
  if (!missions.length) return false;
  const kinds = new Set(missions.map((item) => item.kind));
  return [...kinds].every((kind) => missions.some((item) => item.kind === kind && passed.has(`${item.kind}:${item.id}`)));
}
