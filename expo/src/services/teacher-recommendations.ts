import { requireSupabase } from '@/lib/supabase';
import type { PublicResource } from '@/services/public-data';

type EventRow = { resource_kind?: string; recommendation_bucket?: string; recommendation_focus_kind?: string; event_type?: string };
export type RecommendationNeed = { id: string; subject: string; topic: string; priority: 'high' | 'medium' | 'next' };
export type RecommendationModel = { teacherId: string; weights: Record<string, number>; priors: { kind: Record<string, number>; bucket: Record<string, number>; focus: Record<string, number> } };

const BASE_WEIGHTS: Record<string, number> = {
  bias: -0.2, subject_match: 0.85, stage_match: 0.36, level_match: 0.42, topic_overlap: 0.9, title_match: 0.75, objective_match: 0.55, source_own: 0.18,
  kind_plan: 0.22, kind_worksheet: 0.26, kind_exam: 0.14, kind_video: 0.18, bucket_next_topic: 0.2, bucket_review: 0.26, bucket_pending_gap: 0.18,
  focus_needs_practice: 0.18, focus_reteach: 0.16, focus_reinforce: 0.12, focus_stretch: 0.08, topic_reference_present: 0.16, semantic_affinity: 0.52,
  unsupervised_affinity: 0.38, prior_kind_success: 0.24, prior_bucket_success: 0.3, prior_focus_success: 0.22,
};
const EVENT_TARGET: Record<string, number> = { prefill: 0.2, resource_opened: 0.32, resource_assigned: 0.55, assignment_created: 0.74, teacher_marked_done: 0.78, student_started: 0.84, student_completed: 0.92, student_improved: 1 };
const normalize = (value: unknown) => String(value || '').trim().toLocaleLowerCase().replace(/[_-]+/g, ' ').replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ');
const key = (value: unknown) => normalize(value).replaceAll(' ', '_');
const sigmoid = (value: number) => 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, value))));
const tokens = (...values: unknown[]) => new Set(normalize(values.join(' ')).split(' ').filter((item) => item.length > 2));
const overlap = (left: Set<string>, right: Set<string>, scale = 3) => left.size && right.size ? Math.min(1, [...left].filter((item) => right.has(item)).length / scale) : 0;
function average(values: number[]) { return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0; }

function fit(samples: { features: Record<string, number>; target: number }[]) {
  if (!samples.length) return { ...BASE_WEIGHTS };
  const names = new Set(['bias', ...Object.keys(BASE_WEIGHTS), ...samples.flatMap((sample) => Object.keys(sample.features))]);
  const weights = Object.fromEntries([...names].map((name) => [name, BASE_WEIGHTS[name] || 0]));
  for (let step = 0; step < 140; step += 1) {
    const gradients: Record<string, number> = Object.fromEntries([...names].map((name) => [name, 0]));
    samples.forEach(({ features, target }) => {
      const row: Record<string, number> = { bias: 1, ...features }; const prediction = sigmoid([...names].reduce((sum, name) => sum + (weights[name] || 0) * (row[name] || 0), 0));
      names.forEach((name) => { gradients[name] += (prediction - Math.max(0, Math.min(1, target))) * (row[name] || 0); });
    });
    names.forEach((name) => { const penalty = name === 'bias' ? 0 : 0.01 * weights[name]; weights[name] -= 0.16 * (gradients[name] / samples.length + penalty); });
  }
  return weights;
}

export async function loadTeacherRecommendationModel(): Promise<RecommendationModel> {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const cutoff = new Date(Date.now() - 180 * 86400000).toISOString();
  const { data } = await client.from('learning_program_recommendation_events').select('resource_kind,recommendation_bucket,recommendation_focus_kind,event_type').eq('teacher_id', userData.user.id).gte('created_at', cutoff).order('created_at', { ascending: false }).limit(1500);
  const rows = (data ?? []) as EventRow[];
  const samples = rows.map((row) => { const kind = key(row.resource_kind); const bucket = key(row.recommendation_bucket); const focus = key(row.recommendation_focus_kind); return { features: { [`kind_${kind}`]: kind ? 1 : 0, [`bucket_${bucket}`]: bucket ? 1 : 0, [`focus_${focus}`]: focus ? 1 : 0 }, target: EVENT_TARGET[key(row.event_type)] ?? 0.1 }; });
  const grouped = (field: keyof EventRow) => Object.fromEntries([...new Set(rows.map((row) => key(row[field])).filter(Boolean))].map((value) => [value, average(rows.filter((row) => key(row[field]) === value).map((row) => EVENT_TARGET[key(row.event_type)] ?? 0.1))]));
  return { teacherId: userData.user.id, weights: fit(samples), priors: { kind: grouped('resource_kind'), bucket: grouped('recommendation_bucket'), focus: grouped('recommendation_focus_kind') } };
}

function needContext(need: RecommendationNeed) {
  return need.priority === 'next' ? { bucket: 'next_topic', focus: 'stretch' } : need.priority === 'high' ? { bucket: 'review', focus: 'needs_practice' } : { bucket: 'pending_gap', focus: 'reinforce' };
}

export function rankTeacherResources(resources: PublicResource[], need: RecommendationNeed, model: RecommendationModel) {
  const context = needContext(need); const queryTokens = tokens(need.topic, need.subject);
  return resources.map((resource) => {
    const kind = key(resource.kind); const resourceTokens = tokens(resource.title, resource.topic, resource.description, resource.subject); const title = normalize(resource.title); const topic = normalize(need.topic);
    const features: Record<string, number> = {
      subject_match: normalize(resource.subject) === normalize(need.subject) ? 1 : 0, title_match: topic && title.includes(topic) ? 1 : 0, topic_overlap: overlap(resourceTokens, queryTokens), semantic_affinity: overlap(resourceTokens, queryTokens, Math.max(2, queryTokens.size)), unsupervised_affinity: overlap(resourceTokens, queryTokens, Math.max(3, resourceTokens.size)), source_own: String(resource.raw.user_id || '') === model.teacherId ? 1 : 0,
      [`kind_${kind}`]: 1, [`bucket_${context.bucket}`]: 1, [`focus_${context.focus}`]: 1, prior_kind_success: model.priors.kind[kind] || 0, prior_bucket_success: model.priors.bucket[context.bucket] || 0, prior_focus_success: model.priors.focus[context.focus] || 0,
    };
    const score = sigmoid(Object.entries({ bias: 1, ...features }).reduce((sum, [name, value]) => sum + (model.weights[name] || 0) * value, 0));
    return { resource, score };
  }).filter((item) => item.resource.kind !== 'program').sort((a, b) => (Number(normalize(b.resource.subject) === normalize(need.subject)) - Number(normalize(a.resource.subject) === normalize(need.subject))) || b.score - a.score).slice(0, 6);
}

export async function recordTeacherRecommendationExposures(need: RecommendationNeed, ranked: { resource: PublicResource; score: number }[], studentId: string) {
  if (!ranked.length) return; const client = requireSupabase(); const { data: userData } = await client.auth.getUser(); const teacherId = userData.user?.id; if (!teacherId) return;
  const shownAt = new Date().toISOString(); const context = needContext(need); const cycle = `${teacherId}:${studentId}:${need.id}:${shownAt.slice(0, 16)}`;
  const rows = ranked.map(({ resource, score }, index) => { const exposureId = `${cycle}:${resource.kind}:${resource.id}`; return { exposure_id: exposureId, idempotency_key: exposureId, teacher_id: teacherId, student_id: studentId || null, viewer_user_id: teacherId, resource_id: resource.id, resource_type: resource.kind, exposure_type: 'teacher_resource_recommendation', surface: 'student_learning_recommendations', position: index + 1, recommendation_bucket: context.bucket, recommendation_focus_kind: context.focus, shown_at: shownAt, model_component_id: 'teacher_recommendation_resource_ranker', model_version: 'expo-port-v1', learned_score: score, final_score: score, context_json: { subject: resource.subject, topic: resource.topic, recommendation_id: need.id } }; });
  await client.from('resource_exposures').upsert(rows, { onConflict: 'idempotency_key', ignoreDuplicates: true });
}
