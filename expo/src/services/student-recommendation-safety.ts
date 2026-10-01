import { canonicalSubjectKey } from '@/lib/subjects';
import type { PublicResource } from '@/services/public-data';
import type { StudentWorkspace } from '@/services/student-data';
import { buildStudentNeedProfile } from '@/services/student-recommendation-need';
import { buildStudentProgramSignals, studentTopicTokens } from '@/services/student-recommendation-programs';
import { buildStudentTopicAlignment } from '@/services/student-recommendation-topic-alignment';

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const BAND_LEVELS = ['beginner_band', 'intermediate_band', 'advanced_band'];
const LEARNER_STAGES = ['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage'];
const STAGE_ALIASES: Record<string, string> = {
  pre_primary: 'early_primary', lower_primary: 'early_primary', primary_lower: 'early_primary',
  primary_upper: 'upper_primary', secondary_lower: 'lower_secondary', middle_school: 'lower_secondary',
  secondary_upper: 'upper_secondary', high_school: 'upper_secondary', adult: 'adult_stage', professional: 'adult_stage',
};

function canonicalLevel(value: unknown) {
  const raw = String(value || '').trim();
  const upper = raw.toUpperCase();
  if (CEFR_LEVELS.includes(upper)) return upper;
  const lower = raw.toLocaleLowerCase();
  const bands: Record<string, string> = {
    beginner: 'beginner_band', elementary: 'beginner_band', intermediate: 'intermediate_band',
    upper_intermediate: 'intermediate_band', advanced: 'advanced_band', proficient: 'advanced_band',
  };
  return bands[lower] || lower;
}

export function canonicalStudentStage(value: unknown) {
  const raw = String(value || '').trim().toLocaleLowerCase().replaceAll(' ', '_');
  return STAGE_ALIASES[raw] || raw;
}

function orderedDistance(target: unknown, resource: unknown, levels: string[], canonicalize: (value: unknown) => string): number | null {
  const targetIndex = levels.indexOf(canonicalize(target));
  const resourceIndex = levels.indexOf(canonicalize(resource));
  return targetIndex >= 0 && resourceIndex >= 0 ? resourceIndex - targetIndex : null;
}

export type StudentRecommendationPolicyProfile = {
  subjectAttempts: Record<string, number>;
  subjectLevel: Record<string, string>;
  subjectStage: Record<string, string>;
  defaultStage: string;
  programSubjects: string[];
  programLevels: Record<string, string>;
  programStages: Record<string, string>;
};

export type StudentRecommendationPolicySignals = {
  accuracy: number;
  topicNeed: number;
  nextTopicOverlap?: number;
  pendingTopicOverlap?: number;
  reviewTopicOverlap?: number;
  directTopicLink?: number;
  explicitTopicMatch?: number;
};

export function evaluateStudentRecommendationPolicy(
  resource: Pick<PublicResource, 'subject' | 'level' | 'stage'>,
  profile: StudentRecommendationPolicyProfile,
  signals: StudentRecommendationPolicySignals,
) {
  const subject = canonicalSubjectKey(resource.subject);
  const targetLevel = profile.subjectLevel[subject] || profile.programLevels[subject] || '';
  const targetStage = profile.subjectStage[subject] || profile.programStages[subject] || profile.defaultStage || '';
  const levelDistance = orderedDistance(targetLevel, resource.level, CEFR_LEVELS, canonicalLevel)
    ?? orderedDistance(targetLevel, resource.level, BAND_LEVELS, canonicalLevel);
  const stageDistance = orderedDistance(targetStage, resource.stage, LEARNER_STAGES, canonicalStudentStage);
  const totalAttempts = Object.values(profile.subjectAttempts).reduce((sum, value) => sum + Number(value || 0), 0);
  const subjectAttempts = Number(profile.subjectAttempts[subject] || 0);
  const hasProgram = profile.programSubjects.length > 0;
  const coldStart = !hasProgram && totalAttempts < 3;
  const result = { allowed: true, coldStart, stretchAllowed: false, stretchCandidate: false, levelDistance, targetLevel, stageDistance, targetStage };

  if (targetStage && stageDistance !== null && Math.abs(stageDistance) >= 2) result.allowed = false;
  else if (coldStart && canonicalLevel(resource.level) && !['A1', 'beginner_band'].includes(canonicalLevel(resource.level))) result.allowed = false;
  else if (hasProgram && !profile.programSubjects.includes(subject)) result.allowed = false;
  else if (hasProgram && targetLevel && levelDistance !== null) {
    if (levelDistance >= 2) result.allowed = false;
    else if (levelDistance > 0) {
      const alignment = Math.max(signals.nextTopicOverlap || 0, signals.pendingTopicOverlap || 0, signals.reviewTopicOverlap || 0, signals.directTopicLink || 0, signals.explicitTopicMatch || 0);
      result.stretchCandidate = true;
      result.stretchAllowed = subjectAttempts >= 5 && signals.accuracy >= 0.82 && signals.topicNeed < 0.35 && alignment >= 0.34;
      result.allowed = result.stretchAllowed;
    }
  }
  return result;
}

export function buildStudentRecommendationSafety(workspace: StudentWorkspace | null): (resource: PublicResource) => boolean {
  if (!workspace) return () => false;
  const stageVotesBySubject = new Map<string, Map<string, number>>();
  let totalAttempts = 0;
  for (const row of workspace.practiceProgress) {
    const count = Number(row.total_attempted || 0);
    const attempts = Number.isFinite(count) ? Math.max(0, count) : 0;
    totalAttempts += attempts;
    const stage = canonicalStudentStage(row.learner_stage);
    if (!stage || !attempts) continue;
    const subject = canonicalSubjectKey(row.subject);
    const votes = stageVotesBySubject.get(subject) || new Map<string, number>();
    votes.set(stage, (votes.get(stage) || 0) + attempts);
    stageVotesBySubject.set(subject, votes);
  }
  const hasProgram = workspace.programs.some((row) => {
    const program = row.program && typeof row.program === 'object' ? row.program as Record<string, unknown> : {};
    return Boolean(String(program.subject || '').trim());
  });
  const targetStageBySubject = new Map([...stageVotesBySubject].map(([subject, votes]) => [subject, [...votes].sort((a, b) => b[1] - a[1])[0]?.[0] || '']));
  return (resource) => {
    const targetStage = targetStageBySubject.get(canonicalSubjectKey(resource.subject)) || '';
    const resourceStage = canonicalStudentStage(resource.stage);
    const targetIndex = LEARNER_STAGES.indexOf(targetStage);
    const resourceIndex = LEARNER_STAGES.indexOf(resourceStage);
    if (targetIndex >= 0 && resourceIndex >= 0 && Math.abs(resourceIndex - targetIndex) >= 2) return false;
    if (!hasProgram && totalAttempts < 3) {
      const level = canonicalLevel(resource.level);
      if (level && level !== 'A1' && level !== 'beginner_band') return false;
    }
    return true;
  };
}

/** Apply the complete Streamlit eligibility policy to the already loaded student workspace. */
export function buildStudentRecommendationEligibility(workspace: StudentWorkspace | null): (resource: PublicResource) => boolean {
  if (!workspace) return () => false;
  const need = buildStudentNeedProfile(workspace.practiceProgress);
  const programs = buildStudentProgramSignals(workspace);
  const topicAlignment = buildStudentTopicAlignment(workspace.alignmentAssignments ?? workspace.assignments, workspace.recommendationEvents, workspace.topicVideoLinks);
  const priorityTopics = new Set([...programs.nextTopicIds, ...programs.pendingTopicIds, ...programs.reviewTopicIds]);
  const relevantTopics = priorityTopics.size ? priorityTopics : programs.activeTopicIds;
  const profile: StudentRecommendationPolicyProfile = {
    subjectAttempts: need.subjectAttempts, subjectLevel: need.subjectLevel,
    subjectStage: need.subjectStage, defaultStage: need.defaultStage,
    programSubjects: [...programs.subjects], programLevels: programs.subjectLevels,
    programStages: programs.subjectStages,
  };
  const overlap = (tokens: Set<string>, reference: Set<string>) =>
    Math.min(1, [...tokens].filter((token) => reference.has(token)).length / 3);
  return (resource) => {
    const subject = canonicalSubjectKey(resource.subject);
    const topic = String(resource.topic || '').trim().toLocaleLowerCase();
    const tokens = studentTopicTokens(resource.topic, resource.title);
    const alignment = topicAlignment(resource.kind, resource.id, relevantTopics);
    return evaluateStudentRecommendationPolicy(resource, profile, {
      accuracy: need.overallAccuracy[subject] || 0,
      topicNeed: need.topicNeed[topic] || 0,
      nextTopicOverlap: overlap(tokens, programs.nextTopicTokens),
      pendingTopicOverlap: overlap(tokens, programs.pendingTopicTokens),
      reviewTopicOverlap: overlap(tokens, programs.reviewTopicTokens),
      directTopicLink: alignment.directTopicLink, explicitTopicMatch: alignment.explicitTopicMatch,
    }).allowed;
  };
}
