import { authorizeQualityFeedback, feedbackJson, insertRow, readRows, upsertRow } from '../../server/quality-feedback-api';

const tables: Record<string, string> = { plan: 'lesson_plans', worksheet: 'worksheets', exam: 'quick_exams', video: 'videos' };
const reasons = new Set(['wrong_topic', 'student_unfit']);
const clean = (value: unknown, max = 240) => String(value ?? '').trim().slice(0, max);

export async function GET(request: Request) {
  try {
    const auth = await authorizeQualityFeedback(request);
    if ('error' in auth) return auth.error;
    const studentId = clean(new URL(request.url).searchParams.get('studentId'), 80);
    if (!studentId) return feedbackJson({ error: 'Choose a student.' }, 400);
    const rows = await readRows(auth.base, auth.serverKey, 'classio_teacher_relevance_feedback', { teacher_id: `eq.${auth.userId}`, student_id: `eq.${studentId}`, active: 'eq.true', order: 'updated_at.desc' }, 'context_key,resource_type,resource_id,topic_id,recommendation_id,reason,resource_updated_at', 1000);
    return feedbackJson({ rows });
  } catch (error) { console.error('Teacher relevance feedback read failed', error instanceof Error ? error.message : 'unknown'); return feedbackJson({ error: 'Feedback could not be loaded.' }, 503); }
}

export async function POST(request: Request) {
  try {
    const auth = await authorizeQualityFeedback(request);
    if ('error' in auth) return auth.error;
    const raw = await request.text();
    if (raw.length > 1500) return feedbackJson({ error: 'Feedback is too large.' }, 413);
    let body: { exposureId?: unknown; action?: unknown; reason?: unknown };
    try { body = JSON.parse(raw); } catch { return feedbackJson({ error: 'Choose a valid feedback action.' }, 400); }
    const exposureId = clean(body.exposureId, 500);
    const action = clean(body.action, 20);
    const reason = clean(body.reason, 30);
    if (!exposureId || !['reject', 'undo'].includes(action) || (action === 'reject' && !reasons.has(reason))) return feedbackJson({ error: 'Choose a valid feedback action.' }, 400);
    const exposures = await readRows(auth.base, auth.serverKey, 'resource_exposures', { exposure_id: `eq.${exposureId}`, teacher_id: `eq.${auth.userId}`, viewer_user_id: `eq.${auth.userId}`, exposure_type: 'eq.teacher_resource_recommendation' }, 'exposure_id,teacher_id,student_id,resource_id,resource_type,learning_program_topic_id,context_json');
    const exposure = exposures[0];
    if (!exposure || !tables[String(exposure.resource_type)]) return feedbackJson({ error: 'This recommendation is unavailable.' }, 404);
    const context = exposure.context_json && typeof exposure.context_json === 'object' ? exposure.context_json as Record<string, unknown> : {};
    const recommendationId = clean(context.recommendation_id, 160);
    const topicId = Number(exposure.learning_program_topic_id) || 0;
    const studentId = clean(exposure.student_id, 80);
    const resourceType = String(exposure.resource_type);
    const resourceId = clean(exposure.resource_id, 80);
    const contextKey = [studentId, topicId ? `topic:${topicId}` : `need:${recommendationId}`, resourceType, resourceId].join(':');
    if (contextKey.length > 500) return feedbackJson({ error: 'This recommendation cannot be reviewed.' }, 400);
    const prior = await readRows(auth.base, auth.serverKey, 'classio_teacher_relevance_feedback', { teacher_id: `eq.${auth.userId}`, context_key: `eq.${contextKey}` }, 'id,active,reason,resource_updated_at');
    if (action === 'undo' && !prior[0]?.active) return feedbackJson({ saved: true, active: false });
    const resources = await readRows(auth.base, auth.serverKey, tables[resourceType], { id: `eq.${resourceId}` }, 'id,user_id,is_public,status,updated_at');
    const resource = resources[0];
    if (!resource || String(resource.status || 'active') === 'archived' || (resource.is_public !== true && String(resource.user_id) !== auth.userId)) return feedbackJson({ error: 'This resource is no longer available.' }, 404);
    const now = new Date().toISOString();
    const feedback = await upsertRow(auth.base, auth.serverKey, 'classio_teacher_relevance_feedback', 'teacher_id,context_key', {
      teacher_id: auth.userId, student_id: studentId, context_key: contextKey, exposure_id: exposureId, resource_type: resourceType, resource_id: resourceId,
      resource_is_public: resource.is_public === true, resource_updated_at: resource.updated_at || prior[0]?.resource_updated_at || null,
      topic_id: topicId || null, recommendation_id: recommendationId, reason: action === 'reject' ? reason : null,
      active: action === 'reject', created_at: prior[0] ? undefined : now, updated_at: now,
    });
    await insertRow(auth.base, auth.serverKey, 'classio_teacher_relevance_feedback_events', { feedback_id: feedback.id, exposure_id: exposureId, teacher_id: auth.userId, action: action === 'reject' ? 'rejected' : 'undone', reason: action === 'reject' ? reason : null });
    return feedbackJson({ saved: true, active: action === 'reject', contextKey });
  } catch (error) { console.error('Teacher relevance feedback failed', error instanceof Error ? error.message : 'unknown'); return feedbackJson({ error: 'Feedback could not be saved.' }, 503); }
}
