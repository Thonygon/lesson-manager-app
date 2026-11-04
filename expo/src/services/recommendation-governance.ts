import approvals from '@/config/recommendation-governance.json';

type Family = 'teacher_resources' | 'student_resources';
type Decision = { family?: string; policy_version?: string; model_version?: string; evidence_sha256?: string; eligible_for_human_approval?: boolean; review_record_valid?: boolean; action?: string };

// Bundled release decisions are code-reviewed. No approval means a heuristic beta ranking.
export function learnedRecommendationApproved(family: Family, modelVersion = 'expo-port-v1'): boolean {
  const decision = (approvals as Record<Family, Decision | null>)[family];
  return Boolean(decision && decision.family === family && decision.policy_version === '2026-10-30.1'
    && decision.model_version === modelVersion && /^[a-f0-9]{64}$/.test(String(decision.evidence_sha256 || ''))
    && decision.eligible_for_human_approval === true && decision.review_record_valid === true && decision.action === 'promote');
}
