import { canonicalSubjectKey } from '@/lib/subjects';
import type { PublicResource } from '@/services/public-data';
import type { StudentWorkspace } from '@/services/student-data';
import { buildStudentNeedProfile } from '@/services/student-recommendation-need';
import { buildStudentProgramSignals, studentTopicTokens, type ProgramScope } from '@/services/student-recommendation-programs';
import { buildStudentAssignmentSignals, resourceAssignmentKey } from '@/services/student-recommendation-assignments';
import { buildStudentAssignmentBehavior } from '@/services/student-recommendation-assignment-behavior';
import { resourceSemanticAffinity } from '@/services/student-recommendation-semantic';
import { canonicalStudentStage, evaluateStudentRecommendationPolicy } from '@/services/student-recommendation-safety';
import { buildStudentTopicAlignment } from '@/services/student-recommendation-topic-alignment';

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const text = (value: unknown) => String(value || '').trim();
const cefr = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const bands = ['beginner_band', 'intermediate_band', 'advanced_band'];
const aliases: Record<string, string> = { beginner: 'beginner_band', elementary: 'beginner_band', intermediate: 'intermediate_band', upper_intermediate: 'intermediate_band', advanced: 'advanced_band', proficient: 'advanced_band' };
function canonicalLevel(value: unknown) { const raw = text(value); const upper = raw.toUpperCase(); return cefr.includes(upper) ? upper : aliases[raw.toLocaleLowerCase()] || raw.toLocaleLowerCase(); }
function levelSimilarity(target: unknown, resource: unknown) {
  const a = canonicalLevel(target); const b = canonicalLevel(resource);
  if (!a || !b) return 0.55;
  if (a === b) return 1;
  if (cefr.includes(a) && cefr.includes(b)) return ({ 1: 0.82, 2: 0.6 } as Record<number, number>)[Math.abs(cefr.indexOf(a) - cefr.indexOf(b))] || 0.25;
  if (bands.includes(a) && bands.includes(b)) return ({ 1: 0.8, 2: 0.45 } as Record<number, number>)[Math.abs(bands.indexOf(a) - bands.indexOf(b))] || 0.25;
  return 0.4;
}
export function studentRecommendationStageFit(target: unknown, resource: unknown) {
  const targetStage = canonicalStudentStage(target);
  const resourceStage = canonicalStudentStage(resource);
  return targetStage && resourceStage ? (targetStage === resourceStage ? 1 : 0.35) : 0.65;
}
export function studentRecommendationSubjectFocus(subjectNeed: number, inProgram: boolean, subjectAttempts: number, isPrimary: boolean, hasProgram = false) {
  let focus = subjectNeed > 0 ? 1 : isPrimary ? 0.8 : 0.45;
  if (inProgram) focus = Math.max(focus, subjectAttempts < 5 ? 0.96 : 0.92);
  else if (hasProgram) focus = Math.min(focus, 0.2);
  return focus;
}
function overlap(tokens: Set<string>, reference: Set<string>, scale = 3) {
  if (!tokens.size || !reference.size) return 0;
  return clamp([...tokens].filter((token) => reference.has(token)).length / Math.max(scale, 1));
}
/** Streamlit's _scope_adjusted_resource_score, applied only to the matching program scope. */
export function scopeAdjustedStudentRecommendationScore(
  resource: Pick<PublicResource, 'title' | 'topic' | 'level'>,
  baseScore: number,
  scope: ProgramScope,
) {
  const tokens = studentTopicTokens(resource.topic, resource.title);
  const topicFit = Math.max(0, ...scope.topics.filter((topic) => !topic.isComplete)
    .map((topic) => overlap(tokens, topic.tokens)));
  return baseScore + 0.12 * (levelSimilarity(scope.level, resource.level) - 0.55) + 0.10 * topicFit;
}
export function studentStretchRecommendationBoost(stretchAllowed: boolean, levelFit: number, nextTopicOverlap: number) {
  if (!stretchAllowed) return 0;
  return Math.max(levelFit >= 0.8 ? 0.10 : 0, nextTopicOverlap >= 0.34 ? 0.12 : 0);
}
function exerciseType(resource: PublicResource) {
  if (resource.kind === 'video') return 'video';
  if (resource.kind === 'worksheet') return text(resource.raw.worksheet_type);
  const types = resource.raw.exercise_types;
  return Array.isArray(types) ? text(types[0]) : '';
}

export type StudentRecommendationReason = { key: string; params?: Record<string, string> };

type StudentRecommendationReasonInput = {
  kind: PublicResource['kind']; topic: string; subject: string; assignedActive: boolean; assignedUnseen: boolean;
  directTopicLink: number; topicNeed: number; subjectNeed: number; exerciseNeed?: number; exerciseType?: string;
  nextTopicOverlap?: number; reviewTopicOverlap?: number; pendingTopicOverlap?: number;
  programTopicOverlap?: number; recentTeacherOverlap?: number; programTypeFit?: number;
  levelFit?: number; level?: string; stretchBoost?: number; semanticAffinity?: number;
};

export function studentRecommendationReasons(input: StudentRecommendationReasonInput): StudentRecommendationReason[] {
  const reasons: StudentRecommendationReason[] = [];
  if (input.assignedUnseen && input.kind === 'video' && input.topic)
    reasons.push({ key: 'student.materialReason.teacherAssignedReview', params: { topic: input.topic } });
  else if (input.assignedActive) reasons.push({ key: 'student.materialReason.teacherAssigned' });
  if (input.directTopicLink >= 1 && input.topic)
    reasons.push({ key: 'student.materialReason.programTopic', params: { topic: input.topic } });
  if (input.topicNeed >= 0.65 && input.topic)
    reasons.push({ key: 'student.materialReason.revisitTopic', params: { topic: input.topic } });
  else if (input.subjectNeed >= 0.55 && input.subject)
    reasons.push({ key: 'student.materialReason.subjectSupport', params: { subject: input.subject } });
  if ((input.exerciseNeed || 0) >= 0.58 && input.exerciseType)
    reasons.push({ key: 'student.materialReason.exerciseSupport', params: { exercise_type: input.exerciseType.replaceAll('_', ' ') } });
  if ((input.nextTopicOverlap || 0) >= 0.34 && input.topic)
    reasons.push({ key: 'student.materialReason.programTopic', params: { topic: input.topic } });
  else if ((input.reviewTopicOverlap || 0) >= 0.34 && input.topic)
    reasons.push({ key: 'student.materialReason.revisitTopic', params: { topic: input.topic } });
  else if (((input.pendingTopicOverlap || 0) >= 0.34 || (input.programTopicOverlap || 0) >= 0.34) && input.topic)
    reasons.push({ key: 'student.materialReason.programTopic', params: { topic: input.topic } });
  else if ((input.recentTeacherOverlap || 0) >= 0.34 && input.topic)
    reasons.push({ key: 'student.materialReason.subjectSupport', params: { subject: input.subject } });
  else if ((input.programTypeFit || 0) >= 1 && input.exerciseType)
    reasons.push({ key: 'student.materialReason.programStyle' });
  if ((input.levelFit || 0) >= 0.95 && input.level)
    reasons.push({ key: 'student.materialReason.levelFit', params: { level: input.level } });
  else if ((input.stretchBoost || 0) > 0 && input.level)
    reasons.push({ key: 'student.materialReason.levelStretch', params: { level: input.level } });
  if ((input.semanticAffinity || 0) >= 0.68 && input.topic)
    reasons.push({ key: 'student.materialReason.revisitTopic', params: { topic: input.topic } });
  if (!reasons.length) reasons.push({ key: 'student.materialReason.balanced' });
  return reasons.slice(0, 3);
}

export function primaryStudentRecommendationReason(input: StudentRecommendationReasonInput): StudentRecommendationReason {
  return studentRecommendationReasons(input)[0];
}

/** Scores the Streamlit feature terms available in the bounded Expo workspace. */
export function scoreStudentRecommendationCandidates<T extends PublicResource>(resources: T[], workspace: StudentWorkspace | null): { resource: T; score: number; reasons: StudentRecommendationReason[] }[] {
  if (!workspace) return [];
  const need = buildStudentNeedProfile(workspace.practiceProgress);
  const programs = buildStudentProgramSignals(workspace);
  const primarySubjects = new Set((workspace.primarySubjects || []).map(canonicalSubjectKey));
  const assignments = buildStudentAssignmentSignals(workspace.assignments);
  const behavior = buildStudentAssignmentBehavior(workspace.assignments);
  const topicAlignment = buildStudentTopicAlignment(workspace.alignmentAssignments ?? workspace.assignments, workspace.recommendationEvents, workspace.topicVideoLinks);
  const priorityTopics = new Set([...programs.nextTopicIds, ...programs.pendingTopicIds, ...programs.reviewTopicIds]);
  const relevantTopics = priorityTopics.size ? priorityTopics : programs.activeTopicIds;
  const totalAttempts = Object.values(need.subjectAttempts).reduce((total, attempts) => total + attempts, 0);
  const scored = resources.flatMap((resource, index) => {
    const subject = canonicalSubjectKey(resource.subject);
    const topic = text(resource.topic).toLocaleLowerCase();
    const kind = resource.kind;
    const type = exerciseType(resource);
    const subjectNeed = need.subjectNeed[subject] || 0;
    const topicNeed = need.topicNeed[topic] || 0;
    const exerciseNeed = need.exerciseNeed[type] || 0;
    const subjectAttempts = need.subjectAttempts[subject] || 0;
    const targetLevel = need.subjectLevel[subject] || programs.subjectLevels[subject] || '';
    const targetStage = need.subjectStage[subject] || programs.subjectStages[subject] || need.defaultStage;
    const tokens = studentTopicTokens(resource.topic, resource.title);
    const next = overlap(tokens, programs.nextTopicTokens);
    const pending = overlap(tokens, programs.pendingTopicTokens);
    const review = overlap(tokens, programs.reviewTopicTokens);
    const assigned = overlap(tokens, assignments.activeAssignedTopicTokens, 2);
    const unseen = overlap(tokens, assignments.unseenVideoTopicTokens, 2);
    const recent = overlap(tokens, behavior.recentTeacherTopics, 2);
    const inProgram = programs.subjects.has(subject);
    const activeAssignment = assignments.resourceAssignments.get(resourceAssignmentKey(kind, resource.id));
    const alignment = topicAlignment(kind, resource.id, relevantTopics);
    const levelFit = levelSimilarity(targetLevel, resource.level);
    const stageFit = studentRecommendationStageFit(targetStage, resource.stage);
    const subjectFocus = studentRecommendationSubjectFocus(subjectNeed, inProgram, subjectAttempts, primarySubjects.has(subject), programs.subjects.size > 0);
    const topicSupport = Math.max(topicNeed, subjectNeed * 0.55);
    const typeSupport = Math.max(exerciseNeed, subjectNeed * 0.45);
    const programTypeFit = kind === 'worksheet' ? Number(programs.worksheetTypes.has(type)) : kind === 'exam' ? Number(programs.examTypes.has(type)) : 0;
    const programTopicOverlap = overlap(tokens, programs.topicTokens);
    const semanticAffinity = resourceSemanticAffinity(resource, programs.nextTopicTitles, [...programs.nextTopicTokens], Object.keys(need.topicNeed));
    const topicSuccess = behavior.topicSuccess[topic] || 0;
    const policy = evaluateStudentRecommendationPolicy(resource, {
      subjectAttempts: need.subjectAttempts, subjectLevel: need.subjectLevel,
      subjectStage: need.subjectStage, defaultStage: need.defaultStage,
      programSubjects: [...programs.subjects], programLevels: programs.subjectLevels,
      programStages: programs.subjectStages,
    }, {
      accuracy: need.overallAccuracy[subject] || 0, topicNeed,
      nextTopicOverlap: next, pendingTopicOverlap: pending, reviewTopicOverlap: review,
      explicitTopicMatch: alignment.explicitTopicMatch, directTopicLink: alignment.directTopicLink,
    });
    if (!policy.allowed) return [];
    let score = 0.28 * subjectFocus + 0.28 * topicSupport + 0.18 * typeSupport
      + 0.14 * levelFit + 0.08 * stageFit + 0.08 * programTopicOverlap
      + 0.08 * next + 0.06 * review + 0.04 * pending + 0.04 * Number(inProgram)
      + 0.04 * programTypeFit + 0.06 * (behavior.kindSuccess[kind] || 0)
      + 0.04 * (behavior.kindCompletion[kind] || 0) + 0.05 * recent
      + 0.05 * assigned + 0.05 * unseen
      + 0.08 * alignment.explicitTopicMatch + 0.04 * alignment.explicitTopicSupport
      + 0.06 * alignment.directTopicLink
      + 0.04 * alignment.topicKindPrior - 0.04 * alignment.topicMatchAmbiguity
      + 0.05 * semanticAffinity;
    if (topicNeed >= 0.6) score += 0.18;
    else if (review >= 0.34) score += 0.16;
    const stretchBoost = studentStretchRecommendationBoost(policy.stretchAllowed, levelFit, next);
    score += stretchBoost;
    if (activeAssignment && !activeAssignment.isCompleted) score += 0.14 + (assigned >= 0.34 ? 0.08 : 0);
    if (activeAssignment?.isUnseen) score += 0.12 + (kind === 'video' ? 0.08 : 0);
    if (activeAssignment?.isUnseen && kind === 'video' && (
      topicNeed >= 0.45 || review >= 0.34 || recent >= 0.34 || unseen >= 0.34 || alignment.directTopicLink >= 1 || alignment.explicitTopicMatch >= 0.5
    )) score += 0.22;
    if (!programs.subjects.size && totalAttempts < 3 && levelFit < 0.95) score -= 0.04;
    if (topicSuccess >= 0.82 && topicNeed < 0.28) score -= 0.08;
    else if (topicSuccess <= 0.68 && topic) score += 0.08;
    const reasons = studentRecommendationReasons({
      kind, topic: text(resource.topic), subject: text(resource.subject),
      assignedActive: Boolean(activeAssignment && !activeAssignment.isCompleted),
      assignedUnseen: Boolean(activeAssignment?.isUnseen),
      directTopicLink: alignment.directTopicLink, topicNeed, subjectNeed,
      exerciseNeed, exerciseType: type, nextTopicOverlap: next, reviewTopicOverlap: review,
      pendingTopicOverlap: pending, programTopicOverlap, recentTeacherOverlap: recent,
      programTypeFit, levelFit, level: resource.level, stretchBoost, semanticAffinity,
    });
    return [{ resource, score, index, reasons }];
  });
  return scored.sort((a, b) => b.score - a.score || a.index - b.index).map(({ resource, score, reasons }) => ({ resource, score, reasons }));
}

/** Legacy resource-only ranking for callers that do not need scoped candidate scores. */
export function rankStudentRecommendations<T extends PublicResource>(resources: T[], workspace: StudentWorkspace | null): T[] {
  return scoreStudentRecommendationCandidates(resources, workspace).map(({ resource }) => resource);
}
