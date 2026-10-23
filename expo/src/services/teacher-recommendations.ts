import { requireSupabase } from '@/lib/supabase';
import type { PublicResource } from '@/services/public-data';
import { getResourceLibrary } from '@/services/resource-library';
import { buildStudentTopicAlignment } from '@/services/student-recommendation-topic-alignment';
import { semanticTextAffinity } from '@/services/student-recommendation-semantic';
import type { TeacherObjectiveRecommendation } from '@/services/teacher-objective-recommendations';

type EventRow = { resource_kind?: string; resource_record_id?: string | number; learning_program_topic_id?: number; event_weight?: number; created_at?: string; recommendation_bucket?: string; recommendation_focus_kind?: string; event_type?: string };
export type RecommendationNeed = { id: string; subject: string; topic: string; priority: 'high' | 'medium' | 'next'; topicId?: number; title?: string; objective?: string; stage?: string; level?: string; lessonFocus?: string };
export type RecommendationModel = { teacherId: string; weights: Record<string, number>; priors: { kind: Record<string, number>; bucket: Record<string, number>; focus: Record<string, number> }; alignment: ReturnType<typeof buildStudentTopicAlignment> };

const BASE_WEIGHTS: Record<string, number> = {
  bias: -0.2, subject_match: 0.85, stage_match: 0.36, level_match: 0.42, topic_overlap: 0.9, title_match: 0.75, objective_match: 0.55, source_own: 0.18,
  kind_plan: 0.22, kind_worksheet: 0.26, kind_exam: 0.14, kind_video: 0.18, bucket_next_topic: 0.2, bucket_review: 0.26, bucket_pending_gap: 0.18,
  focus_needs_practice: 0.18, focus_reteach: 0.16, focus_reinforce: 0.12, focus_stretch: 0.08, topic_reference_present: 0.16, semantic_affinity: 0.52,
  exact_topic_match: 0.78, exact_topic_support: 0.32, direct_topic_link: 0.64, topic_kind_prior: 0.34, topic_match_ambiguity: -0.26,
  unsupervised_affinity: 0.38, prior_kind_success: 0.24, prior_bucket_success: 0.3, prior_focus_success: 0.22,
};
const EVENT_TARGET: Record<string, number> = { prefill: 0.2, resource_opened: 0.32, resource_assigned: 0.55, assignment_created: 0.74, teacher_marked_done: 0.78, student_started: 0.84, student_completed: 0.92, student_improved: 1 };
const resourcePoolCache = new Map<string, { expires: number; promise: Promise<PublicResource[]> }>();

export async function loadTeacherRecommendationResourcePool(): Promise<PublicResource[]> {
  const { data, error } = await requireSupabase().auth.getUser(); const userId = data.user?.id;
  if (error || !userId) throw error ?? new Error('Your session has expired.');
  const cached = resourcePoolCache.get(userId);
  if (cached && cached.expires > Date.now()) return cached.promise;
  const promise = Promise.allSettled([getResourceLibrary('mine'), getResourceLibrary('community')]).then(([mine, community]) => {
    if (mine.status === 'rejected' && community.status === 'rejected') throw mine.reason;
    const resources = [...(mine.status === 'fulfilled' ? mine.value.resources : []), ...(community.status === 'fulfilled' ? community.value.resources : [])];
    return [...new Map(resources.map((resource) => [`${resource.kind}:${resource.id}`, resource])).values()];
  }).catch((reason) => { resourcePoolCache.delete(userId); throw reason; });
  resourcePoolCache.set(userId, { expires: Date.now() + 60000, promise });
  return promise;
}
const normalize = (value: unknown) => String(value || '').trim().toLocaleLowerCase().replace(/[_-]+/g, ' ').replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ');
const key = (value: unknown) => normalize(value).replaceAll(' ', '_');
const sigmoid = (value: number) => 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, value))));
const tokens = (...values: unknown[]) => new Set(normalize(values.join(' ')).split(' ').filter((item) => item.length > 2));
const overlap = (left: Set<string>, right: Set<string>, scale = 3) => left.size && right.size ? Math.min(1, [...left].filter((item) => right.has(item)).length / scale) : 0;
const subject = (value: unknown) => { const normalized = normalize(value).replaceAll(' ', '_'); return ({ inglés: 'english', ingles: 'english', english: 'english', español: 'spanish', espanol: 'spanish', spanish: 'spanish', matemáticas: 'mathematics', matematicas: 'mathematics', math: 'mathematics', maths: 'mathematics', mathematics: 'mathematics', ciencias: 'science', science: 'science' } as Record<string, string>)[normalized] || normalized; };
const containsFolded = (value: unknown, needle: unknown) => Boolean(String(needle || '').trim()) && String(value || '').trim().toLocaleLowerCase().includes(String(needle || '').trim().toLocaleLowerCase());
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
  const { data, error } = await client.from('learning_program_recommendation_events').select('resource_kind,resource_record_id,learning_program_topic_id,event_weight,created_at,recommendation_bucket,recommendation_focus_kind,event_type').eq('teacher_id', userData.user.id).gte('created_at', cutoff).order('created_at', { ascending: false }).limit(1500);
  const rows = (error ? [] : data ?? []) as EventRow[];
  if (!rows.length) return { teacherId: userData.user.id, weights: { ...BASE_WEIGHTS }, priors: { kind: {}, bucket: {}, focus: {} }, alignment: buildStudentTopicAlignment() };
  const [assignmentResult, referenceEventResult, videoResult] = await Promise.all([
    client.from('teacher_assignments').select('assignment_type,source_record_id,learning_program_topic_id,score_pct,status,updated_at').eq('teacher_id', userData.user.id).not('source_record_id', 'is', null).not('learning_program_topic_id', 'is', null).neq('status', 'archived').gte('updated_at', cutoff).order('updated_at', { ascending: false }).limit(1200),
    client.from('learning_program_recommendation_events').select('resource_kind,resource_record_id,learning_program_topic_id,event_type,event_weight,created_at').eq('teacher_id', userData.user.id).not('resource_record_id', 'is', null).not('learning_program_topic_id', 'is', null).gte('created_at', cutoff).order('created_at', { ascending: false }).limit(1200),
    client.from('learning_program_topic_videos').select('topic_id,video_id,created_at').eq('teacher_id', userData.user.id).order('created_at', { ascending: false }).limit(2000),
  ]);
  // Streamlit treats unavailable reference tables as empty evidence, while retaining recommendation events.
  const alignment = buildStudentTopicAlignment(assignmentResult.error ? [] : assignmentResult.data ?? [], referenceEventResult.error ? [] : referenceEventResult.data ?? [], videoResult.error ? [] : videoResult.data ?? []);
  const samples = rows.map((row) => { const kind = key(row.resource_kind); const bucket = key(row.recommendation_bucket); const focus = key(row.recommendation_focus_kind); const topicId = Number(row.learning_program_topic_id) || 0; const topic = topicId > 0 ? alignment(kind, row.resource_record_id, [topicId]) : null; return { features: { [`kind_${kind}`]: kind ? 1 : 0, [`bucket_${bucket}`]: bucket ? 1 : 0, [`focus_${focus}`]: focus ? 1 : 0, topic_reference_present: topicId > 0 ? 1 : 0, exact_topic_match: topic?.explicitTopicMatch || 0, exact_topic_support: topic?.explicitTopicSupport || 0, direct_topic_link: topic?.directTopicLink || 0, topic_kind_prior: topic?.topicKindPrior || 0, topic_match_ambiguity: topic?.topicMatchAmbiguity || 0 }, target: EVENT_TARGET[key(row.event_type)] ?? 0.1 }; });
  const grouped = (field: keyof EventRow) => Object.fromEntries([...new Set(rows.map((row) => key(row[field])).filter(Boolean))].map((value) => [value, average(rows.filter((row) => key(row[field]) === value).map((row) => EVENT_TARGET[key(row.event_type)] ?? 0.1))]));
  return { teacherId: userData.user.id, weights: fit(samples), priors: { kind: grouped('resource_kind'), bucket: grouped('recommendation_bucket'), focus: grouped('recommendation_focus_kind') }, alignment };
}

function needContext(need: RecommendationNeed) {
  return need.priority === 'next' ? { bucket: 'next_topic', focus: 'stretch' } : need.priority === 'high' ? { bucket: 'review', focus: 'needs_practice' } : { bucket: 'pending_gap', focus: 'reinforce' };
}

const searchText = (value: unknown) => String(value || '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
const searchFields: Record<string, string[]> = {
  plan: ['title', 'topic', 'lesson_purpose', 'subject', 'learner_stage', 'level_or_band', 'author_name'],
  worksheet: ['title', 'topic', 'worksheet_type', 'subject', 'learner_stage', 'level_or_band', 'author_name'],
  exam: ['title', 'topic', 'subject', 'learner_stage', 'level', 'exam_length', 'author_name'],
  video: ['title', 'topic', 'description', 'subject', 'learner_stage', 'level_or_band', 'author_name'],
};
const levelDistance = (left: string, right: string) => {
  const a = searchText(left); const b = searchText(right);
  if (!a || !b) return null;
  if (a === b) return 0;
  for (const order of [['a1', 'a2', 'b1', 'b2', 'c1', 'c2'], ['beginner_band', 'intermediate_band', 'advanced_band']]) {
    if (order.includes(a) && order.includes(b)) return Math.abs(order.indexOf(a) - order.indexOf(b));
  }
  return null;
};
function teacherResourceBucket(resource: PublicResource, need: RecommendationNeed, features: Record<string, number>) {
  if (features.subject_match < 1) return null;
  if (need.stage && resource.stage && searchText(need.stage) !== searchText(resource.stage)) return null;
  const distance = levelDistance(need.level || '', resource.level);
  const direct = features.direct_topic_link;
  const exact = features.exact_topic_match;
  const semantic = features.semantic_affinity;
  const veryStrong = direct >= 1 || exact >= 0.74 || features.topic_overlap >= 0.55 || semantic >= 0.8 || features.title_match >= 1 || features.objective_match >= 1;
  const strong = veryStrong || exact >= 0.48 || features.exact_topic_support >= 0.32 || features.topic_overlap >= 0.3 || semantic >= 0.64 || features.unsupervised_affinity >= 0.66;
  const moderate = strong || features.topic_kind_prior >= 0.34 || semantic >= 0.52 || features.unsupervised_affinity >= 0.54 || features.topic_overlap >= 0.18;
  if (features.topic_match_ambiguity >= 0.8 && direct < 1 && exact < 0.45 && semantic < 0.7) return null;
  if (!moderate) return null;
  if (veryStrong && (distance === 0 || direct >= 1 || exact >= 0.86)) return 'very_close';
  if (strong && (distance === null || distance <= 1)) return 'close';
  return 'related';
}
function teacherFocusBonus(focus: string, kind: string) {
  if (focus === 'needs_practice') return kind === 'worksheet' ? 1.9 : kind === 'video' ? 1.1 : 0.3;
  if (focus === 'reteach') return kind === 'video' ? 2.1 : kind === 'plan' ? 1.7 : 0.3;
  if (focus === 'stretch') return kind === 'plan' ? 1.8 : kind === 'exam' ? 1.1 : 0.2;
  if (focus === 'reinforce') return kind === 'worksheet' || kind === 'plan' ? 1.3 : kind === 'video' ? 0.9 : 0.3;
  return 0;
}

export function rankTeacherResources(resources: PublicResource[], need: RecommendationNeed, model: RecommendationModel, affinityScores?: Map<string, number>, excluded?: Set<string>, studentId = '') {
  const context = needContext(need); const queryTokens = tokens(need.title || need.topic, need.objective);
  const query = searchText([need.title || need.topic, need.objective].filter(Boolean).join(' '));
  const candidates = resources.filter((resource) => !excluded?.has(teacherFeedbackKey(studentId, need, resource))).map((resource) => {
    const kind = key(resource.kind); const resourceTokens = tokens(resource.title, resource.topic);
    const topicId = Number(need.topicId) || 0; const topicFeatures = topicId > 0 ? model.alignment?.(kind, resource.id, [topicId]) : null;
    const raw = resource.raw; const exerciseTypes = Array.isArray(raw.exercise_types) ? raw.exercise_types : [];
    const features: Record<string, number> = {
      subject_match: subject(resource.subject) === subject(need.subject) ? 1 : 0,
      stage_match: key(resource.stage) && key(resource.stage) === key(need.stage) ? 1 : 0,
      level_match: key(resource.level) && key(resource.level) === key(need.level) ? 1 : 0,
      title_match: containsFolded(resource.title, need.title || need.topic) ? 1 : 0,
      objective_match: containsFolded(resource.title, need.objective) ? 1 : 0,
      topic_overlap: overlap(resourceTokens, queryTokens),
      semantic_affinity: semanticTextAffinity(
        [resource.title, resource.topic, raw.description, raw.worksheet_type, raw.lesson_purpose, raw.exam_length, exerciseTypes.join(' ')],
        [need.title || need.topic, need.topic, need.objective, need.lessonFocus, context.bucket, context.focus, '', '', '', '', '', ''],
      ),
      // Python returns zero when its validated fitted representation is unavailable.
      // A lexical overlap is not the trained unsupervised model.
      unsupervised_affinity: affinityScores?.get(`${need.id}:${resource.kind}:${resource.id}`) || 0,
      source_own: String(resource.raw.user_id || '') === model.teacherId ? 1 : 0,
      [`kind_${kind}`]: 1, [`bucket_${context.bucket}`]: 1, [`focus_${context.focus}`]: 1, prior_kind_success: model.priors.kind[kind] || 0, prior_bucket_success: model.priors.bucket[context.bucket] || 0, prior_focus_success: model.priors.focus[context.focus] || 0,
      topic_reference_present: topicId > 0 ? 1 : 0, exact_topic_match: topicFeatures?.explicitTopicMatch || 0, exact_topic_support: topicFeatures?.explicitTopicSupport || 0, direct_topic_link: topicFeatures?.directTopicLink || 0, topic_kind_prior: topicFeatures?.topicKindPrior || 0, topic_match_ambiguity: topicFeatures?.topicMatchAmbiguity || 0,
    };
    const score = sigmoid(Object.entries({ bias: 1, ...features }).reduce((sum, [name, value]) => sum + (model.weights[name] || 0) * value, 0));
    const blob = searchText((searchFields[kind] || []).map((field) => raw[field]).join(' '));
    if (!query || !blob) return null;
    const title = searchText(need.title || need.topic); const objective = searchText(need.objective);
    let displayScore = (title && blob.includes(title) ? 8 : 0) + (objective && blob.includes(objective) ? 5 : 0);
    for (const token of query.split(/\W+/).filter((item) => item.length >= 3)) if (blob.includes(token)) displayScore += 1.4;
    if (searchText(need.subject) && searchText(need.subject) === searchText(raw.subject)) displayScore += 3;
    if (searchText(need.stage) && searchText(need.stage) === searchText(resource.stage)) displayScore += 1.5;
    if (searchText(need.level) && searchText(need.level) === searchText(resource.level)) displayScore += 1.5;
    displayScore += teacherFocusBonus(context.focus, kind) + 5.4 * score + (features.source_own ? 0.8 : 0);
    return { resource, score, displayScore, bucket: teacherResourceBucket(resource, need, features) };
  }).filter((item): item is NonNullable<typeof item> => Boolean(item && item.resource.kind !== 'program' && item.bucket));
  // Python presents only candidates in the strongest available affinity bucket.
  const bucketPriority = { very_close: 0, close: 1, related: 2 } as const;
  const best = Math.min(...candidates.map((item) => bucketPriority[item.bucket as keyof typeof bucketPriority]));
  const order = ['plan', 'video', 'worksheet', 'exam'];
  const winning = candidates.filter((item) => bucketPriority[item.bucket as keyof typeof bucketPriority] === best)
    .sort((a, b) => Number(b.resource.raw.user_id === model.teacherId) - Number(a.resource.raw.user_id === model.teacherId) || b.displayScore - a.displayScore);
  return order.flatMap((kind) => winning.filter((item) => item.resource.kind === kind).slice(0, 3));
}

export function teacherFeedbackKey(studentId: string, need: RecommendationNeed, resource: Pick<PublicResource, 'kind' | 'id'>) {
  return [studentId, need.topicId ? `topic:${need.topicId}` : `need:${need.id}`, resource.kind, resource.id].join(':');
}

export async function loadTeacherRelevanceFeedback(studentId: string): Promise<Set<string>> {
  const client = requireSupabase(); const { data, error } = await client.auth.getSession(); if (error || !data.session) throw error ?? new Error('Your session has expired.');
  const response = await fetch(`/api/teacher-relevance-feedback?studentId=${encodeURIComponent(studentId)}`, { headers: { Authorization: `Bearer ${data.session.access_token}` }, cache: 'no-store' });
  if (!response.ok) throw new Error('Teacher feedback could not be loaded.');
  const payload = await response.json() as { rows?: { context_key?: string }[] };
  return new Set((payload.rows || []).map((row) => String(row.context_key || '')).filter(Boolean));
}

export async function saveTeacherRelevanceFeedback(exposureId: string, action: 'reject' | 'undo', reason?: 'wrong_topic' | 'student_unfit') {
  const client = requireSupabase(); const { data, error } = await client.auth.getSession(); if (error || !data.session) throw error ?? new Error('Your session has expired.');
  const response = await fetch('/api/teacher-relevance-feedback', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify({ exposureId, action, reason }), cache: 'no-store' });
  const payload = await response.json().catch(() => ({})) as { error?: string; contextKey?: string };
  if (!response.ok) throw new Error(payload.error || 'Teacher feedback could not be saved.');
  return payload;
}

export async function recordTeacherRecommendationExposures(need: RecommendationNeed, ranked: { resource: PublicResource; score: number }[], studentId: string): Promise<Map<string, string>> {
  if (!ranked.length) return new Map(); const client = requireSupabase(); const { data: userData } = await client.auth.getUser(); const teacherId = userData.user?.id; if (!teacherId) return new Map();
  const shownAt = new Date().toISOString(); const context = needContext(need); const cycle = `${teacherId}:${studentId}:${need.id}:${shownAt.slice(0, 16)}`;
  const rows = ranked.map(({ resource, score }, index) => { const exposureId = `${cycle}:${resource.kind}:${resource.id}`; return { exposure_id: exposureId, idempotency_key: exposureId, teacher_id: teacherId, student_id: studentId || null, viewer_user_id: teacherId, resource_id: resource.id, resource_type: resource.kind, exposure_type: 'teacher_resource_recommendation', surface: 'student_learning_recommendations', position: index + 1, recommendation_bucket: context.bucket, recommendation_focus_kind: context.focus, learning_program_topic_id: need.topicId || null, shown_at: shownAt, model_component_id: 'teacher_recommendation_resource_ranker', model_version: 'expo-port-v1', learned_score: score, final_score: score, context_json: { subject: resource.subject, topic: resource.topic, recommendation_id: need.id } }; });
  const { error } = await client.from('resource_exposures').upsert(rows, { onConflict: 'idempotency_key', ignoreDuplicates: true });
  if (error) throw error;
  return new Map(rows.map((row) => [`${need.id}:${row.resource_type}:${row.resource_id}`, row.exposure_id]));
}

export async function recordTeacherObjectiveExposures(items: TeacherObjectiveRecommendation[], studentId: string) {
  if (!studentId || !items.length) return;
  const client = requireSupabase(); const { data } = await client.auth.getUser(); const teacherId = data.user?.id; if (!teacherId) return;
  const shownAt = new Date().toISOString(); const cycle = `${teacherId}:${studentId}:teacher-objectives:${shownAt.slice(0, 16)}`;
  const rows = items.map((item, index) => {
    const exposureId = `${cycle}:${item.id}`;
    return { exposure_id: exposureId, idempotency_key: exposureId, teacher_id: teacherId, student_id: studentId, viewer_user_id: teacherId,
      resource_id: item.topicId ? `topic:${item.topicId}` : item.title, resource_type: 'teacher_objective', exposure_type: 'teacher_objective_recommendation',
      surface: 'teacher_student_progress', position: index + 1, recommendation_bucket: item.bucket, recommendation_focus_kind: item.focus,
      learning_program_assignment_id: item.programAssignmentId || null, learning_program_topic_id: item.topicId || null,
      shown_at: shownAt, model_component_id: 'teacher_recommendation_objective_selector', model_version: 'expo-port-v1',
      learned_score: item.score, final_score: item.score, context_json: { program_id: item.programId || null, subject_key: subject(item.subject), title: item.title } };
  });
  await client.from('resource_exposures').upsert(rows, { onConflict: 'idempotency_key', ignoreDuplicates: true });
}

export async function recordTeacherRecommendationAction(item: TeacherObjectiveRecommendation, studentId: string, eventType: 'prefill' | 'resource_opened' | 'resource_assigned' | 'teacher_marked_done', resource?: PublicResource) {
  if (!studentId) return;
  const client = requireSupabase(); const { data } = await client.auth.getUser(); const teacherId = data.user?.id; if (!teacherId) return;
  const now = new Date().toISOString();
  await client.from('learning_program_recommendation_events').insert({ teacher_id: teacherId, student_id: studentId,
    learning_program_assignment_id: item.programAssignmentId || null, learning_program_topic_id: item.topicId || null, program_id: item.programId || null,
    recommendation_bucket: item.bucket, recommendation_focus_kind: item.focus, resource_kind: eventType === 'teacher_marked_done' ? 'lesson' : resource?.kind || (item.tool === 'plan' ? 'lesson_plan' : item.tool),
    resource_record_id: resource ? Number(resource.id) || null : null, event_type: eventType, event_weight: eventType === 'prefill' ? 0.18 : eventType === 'teacher_marked_done' ? 0.42 : eventType === 'resource_assigned' ? 0.55 : 0.32,
    metadata: { title: item.title, ...(eventType === 'teacher_marked_done' && item.resolvedLowScoreSignature ? { resolved_low_score_signature: item.resolvedLowScoreSignature } : {}) }, created_at: now, updated_at: now });
}
