import { canonicalSubjectKey } from '@/lib/subjects';
import type { PublicResource } from '@/services/public-data';
import type { StudentWorkspace } from '@/services/student-data';
import { buildStudentProgramSignals, studentTopicTokens, type ProgramScope } from '@/services/student-recommendation-programs';
import { buildStudentAssignmentSignals, resourceAssignmentKey, type ResourceAssignmentSignal } from '@/services/student-recommendation-assignments';
import { scopeAdjustedStudentRecommendationScore, type StudentRecommendationReason } from '@/services/student-recommendation-ranking';

function scopeFit(row: Pick<PublicResource, 'title' | 'topic'>, scope: ProgramScope) {
  const tokens = studentTopicTokens(row.topic, row.title);
  const topics = scope.topics.filter((topic) => !topic.isComplete);
  return Math.max(0, ...topics.map((topic) => [...tokens].filter((token) => topic.tokens.has(token)).length));
}

export type RecommendationScopeMetadata = {
  learningProgramAssignmentId: number;
  learningProgramTopicId: number;
  programId: number;
  programTeacherId: string;
};

type ScoredResource<T extends PublicResource> = { resource: T; score: number; reasons?: StudentRecommendationReason[]; reason?: StudentRecommendationReason };

/** Streamlit's scoped-row sort, topic/type deduplication, and assignment round robin. */
export function selectScoredStudentRecommendations<T extends PublicResource>(
  candidates: ScoredResource<T>[], workspace: StudentWorkspace | null, limit = 6,
): (T & Partial<RecommendationScopeMetadata> & { recommendationReasons: StudentRecommendationReason[]; recommendationReason?: StudentRecommendationReason })[] {
  if (!workspace) return [];
  const programs = buildStudentProgramSignals(workspace);
  const assignments = buildStudentAssignmentSignals(workspace.assignments);
  type Scoped = { row: T & Partial<RecommendationScopeMetadata> & { recommendationReasons: StudentRecommendationReason[]; recommendationReason?: StudentRecommendationReason }; score: number; scopeKey: string; index: number };
  const scoped: Scoped[] = [];
  candidates.forEach(({ resource, score, reasons, reason }, index) => {
    const subject = canonicalSubjectKey(resource.subject);
    const assignment = assignments.resourceAssignments.get(resourceAssignmentKey(resource.kind, resource.id));
    const scopes = programs.programScopes[subject] || [];
    const matching = assignment?.learningProgramAssignmentId
      ? scopes.filter((scope) => scope.learningProgramAssignmentId === assignment.learningProgramAssignmentId)
      : scopes;
    const resolved = resolveStudentRecommendationScopes(resource, matching, assignment);
    const entries = resolved.length ? resolved : [undefined];
    for (const metadata of entries) {
      const scope = matching.find((item) => item.learningProgramAssignmentId === metadata?.learningProgramAssignmentId);
      const scopedScore = Math.round((scope ? scopeAdjustedStudentRecommendationScore(resource, score, scope) : score) * 10000) / 10000;
      scoped.push({
        row: { ...resource, ...(metadata || {}), recommendationReasons: reasons || (reason ? [reason] : []), recommendationReason: reasons?.[0] || reason },
        score: scopedScore,
        scopeKey: metadata?.learningProgramAssignmentId ? `assignment:${metadata.learningProgramAssignmentId}` : `subject:${subject}`,
        index,
      });
    }
  });
  const compare = (a: Scoped, b: Scoped) => b.score - a.score
    || a.row.topic.toLocaleLowerCase().localeCompare(b.row.topic.toLocaleLowerCase())
    || a.row.title.toLocaleLowerCase().localeCompare(b.row.title.toLocaleLowerCase())
    || a.index - b.index;
  scoped.sort(compare);
  const seen = new Set<string>();
  const deduped = scoped.filter(({ row, scopeKey }) => {
    const sections = row.raw.exam_data && typeof row.raw.exam_data === 'object'
      ? (row.raw.exam_data as Record<string, unknown>).sections : undefined;
    const firstSection = Array.isArray(sections) && sections[0] && typeof sections[0] === 'object'
      ? sections[0] as Record<string, unknown> : {};
    const exercise = row.kind === 'video' ? 'video' : row.kind === 'worksheet'
      ? String(row.raw.worksheet_type || '') : Array.isArray(row.raw.exercise_types) && row.raw.exercise_types.length
        ? String(row.raw.exercise_types[0] || '') : String(firstSection.type || '');
    const key = JSON.stringify([scopeKey, canonicalSubjectKey(row.subject), row.kind, row.topic.toLocaleLowerCase(), exercise.toLocaleLowerCase()]);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const active = [...new Set(Object.values(programs.programScopes).flat().map((scope) => `assignment:${scope.learningProgramAssignmentId}`))].sort();
  const effectiveLimit = Math.max(1, limit, active.length);
  const selected: Scoped[] = [];
  const selectedSet = new Set<Scoped>();
  const buckets = active.map((key) => deduped.filter((item) => item.scopeKey === key));
  const positions = buckets.map(() => 0);
  while (selected.length < effectiveLimit) {
    let added = false;
    buckets.forEach((bucket, index) => {
      if (selected.length >= effectiveLimit || positions[index] >= bucket.length) return;
      const item = bucket[positions[index]++];
      selected.push(item);
      selectedSet.add(item);
      added = true;
    });
    if (!added) break;
  }
  for (const item of deduped) {
    if (selected.length >= effectiveLimit) break;
    if (selectedSet.has(item)) continue;
    selected.push(item);
  }
  return selected.sort(compare).map(({ row }) => row);
}

/** Resolve Streamlit's assignment-first scope and best matching program topic. */
export function resolveStudentRecommendationScopes(
  row: Pick<PublicResource, 'subject' | 'title' | 'topic'>,
  scopes: ProgramScope[],
  assignment?: ResourceAssignmentSignal,
): RecommendationScopeMetadata[] {
  const exactAssignmentId = assignment?.learningProgramAssignmentId || 0;
  const matching = exactAssignmentId > 0
    ? scopes.filter((scope) => scope.learningProgramAssignmentId === exactAssignmentId)
    : scopes;
  if (exactAssignmentId > 0 && !matching.length) return [{
    learningProgramAssignmentId: exactAssignmentId,
    learningProgramTopicId: assignment?.learningProgramTopicId || 0,
    programId: 0, programTeacherId: '',
  }];
  const tokens = studentTopicTokens(row.topic, row.title);
  return matching.map((scope) => {
    const ordered = [...scope.topics].filter((topic) => topic.topicId > 0).sort((a, b) => {
      const aFit = [...tokens].filter((token) => a.tokens.has(token)).length;
      const bFit = [...tokens].filter((token) => b.tokens.has(token)).length;
      return bFit - aFit || Number(a.isComplete) - Number(b.isComplete) || a.position - b.position;
    });
    return {
      learningProgramAssignmentId: scope.learningProgramAssignmentId,
      learningProgramTopicId: assignment?.learningProgramTopicId || ordered[0]?.topicId || 0,
      programId: scope.programId,
      programTeacherId: scope.teacherId,
    };
  });
}

/** Reserve a distinct, ranked resource for each active program assignment. */
export function selectStudentRecommendationSubjects<T extends Pick<PublicResource, 'subject' | 'title' | 'topic' | 'kind' | 'id'>>(
  ranked: T[], workspace: StudentWorkspace | null, limit = 6,
): (T & Partial<RecommendationScopeMetadata>)[] {
  if (!workspace || !ranked.length) return ranked.slice(0, Math.max(1, limit));
  const signals = buildStudentProgramSignals(workspace);
  const assignments = buildStudentAssignmentSignals(workspace.assignments);
  const scopes = Object.entries(signals.programScopes).sort(([left], [right]) => left.localeCompare(right))
    .flatMap(([subject, entries]) => entries.map((scope) => ({ subject, scope })));
  const selected = new Set<T>();
  const selectedScopes = new Map<T, RecommendationScopeMetadata>();
  const repeatedScopes: (T & RecommendationScopeMetadata)[] = [];
  for (const { subject, scope } of scopes) {
    const eligible = ranked.filter((row) => {
      if (canonicalSubjectKey(row.subject) !== subject) return false;
      const assignment = assignments.resourceAssignments.get(resourceAssignmentKey(row.kind, row.id));
      return !assignment?.learningProgramAssignmentId || assignment.learningProgramAssignmentId === scope.learningProgramAssignmentId;
    });
    const candidates = eligible.some((row) => !selected.has(row)) ? eligible.filter((row) => !selected.has(row)) : eligible;
    const first = candidates.reduce<T | undefined>((best, row) => {
      if (!best || scopeFit(row, scope) > scopeFit(best, scope)) return row;
      return best;
    }, undefined);
    if (first) {
      const assignment = assignments.resourceAssignments.get(resourceAssignmentKey(first.kind, first.id));
      const metadata = resolveStudentRecommendationScopes(first, [scope], assignment)[0];
      if (metadata) {
        if (selected.has(first)) repeatedScopes.push({ ...first, ...metadata });
        else { selected.add(first); selectedScopes.set(first, metadata); }
      }
    }
  }
  const effectiveLimit = Math.max(1, limit, scopes.length);
  for (const row of ranked) {
    if (selected.size + repeatedScopes.length >= effectiveLimit) break;
    selected.add(row);
  }
  const primary = ranked.filter((row) => selected.has(row)).map((row) => {
    const subject = canonicalSubjectKey(row.subject);
    const assignment = assignments.resourceAssignments.get(resourceAssignmentKey(row.kind, row.id));
    const scope = selectedScopes.get(row) || resolveStudentRecommendationScopes(row, signals.programScopes[subject] || [], assignment)[0];
    return scope ? { ...row, ...scope } : row;
  });
  return [...primary, ...repeatedScopes].slice(0, effectiveLimit);
}
