import { authorizeQualityFeedback, feedbackJson, insertRow, readRows, upsertRow } from '../../server/quality-feedback-api';

const uuid = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value : '';
const reasons = new Set(['content', 'level', 'format', 'other']);
const resourceTables: Record<string, string> = { plan: 'lesson_plans', worksheet: 'worksheets', exam: 'quick_exams', program: 'learning_programs' };

export async function GET(request: Request) {
  try {
    const auth = await authorizeQualityFeedback(request);
    if ('error' in auth) return auth.error;
    const url = new URL(request.url);
    const resourceType = url.searchParams.get('resourceType') || '';
    const resourceId = url.searchParams.get('resourceId') || '';
    if (!resourceTables[resourceType] || !/^\d{1,18}$/.test(resourceId)) return feedbackJson({ eligible: false });
    const resources = await readRows(auth.base, auth.serverKey, resourceTables[resourceType], { id: `eq.${resourceId}`, user_id: `eq.${auth.userId}` }, 'id');
    if (!resources[0]) return feedbackJson({ eligible: false });
    const links = await readRows(auth.base, auth.serverKey, 'classio_generation_resources', { resource_type: `eq.${resourceType}`, resource_id: `eq.${resourceId}`, actor_user_id: `eq.${auth.userId}` }, 'generation_id,edited_at');
    const link = links[0];
    if (!link || link.edited_at) return feedbackJson({ eligible: false });
    const answers = await readRows(auth.base, auth.serverKey, 'classio_generation_intent_feedback', { generation_id: `eq.${link.generation_id}`, actor_user_id: `eq.${auth.userId}` }, 'satisfied,reason');
    return feedbackJson({ eligible: true, generationId: link.generation_id, satisfied: answers[0]?.satisfied ?? null, reason: answers[0]?.reason ?? null });
  } catch (error) { console.error('Generation feedback lookup failed', error instanceof Error ? error.message : 'unknown'); return feedbackJson({ error: 'Feedback could not be loaded.' }, 503); }
}

export async function POST(request: Request) {
  try {
    const auth = await authorizeQualityFeedback(request);
    if ('error' in auth) return auth.error;
    const raw = await request.text();
    if (raw.length > 1200) return feedbackJson({ error: 'Feedback is too large.' }, 413);
    let body: { generationId?: unknown; satisfied?: unknown; reason?: unknown; action?: unknown; resourceType?: unknown; resourceId?: unknown; surface?: unknown };
    try { body = JSON.parse(raw); } catch { return feedbackJson({ error: 'Choose a valid answer.' }, 400); }
    const generationId = uuid(body.generationId);
    const action = String(body.action || 'answer');
    if (!generationId || !['answer', 'bind'].includes(action) || (action === 'answer' && (typeof body.satisfied !== 'boolean' || (body.reason && !reasons.has(String(body.reason))) || !['generation_preview', 'resource_page'].includes(String(body.surface))))) return feedbackJson({ error: 'Choose a valid answer.' }, 400);
    const operations = await readRows(auth.base, auth.serverKey, 'classio_ai_operations', { operation_id: `eq.${generationId}`, actor_user_id: `eq.${auth.userId}`, source: 'eq.expo', status: 'eq.success' }, 'operation_id,actor_user_id,feature_name,modality,started_at,finished_at');
    const operation = operations[0];
    if (!operation || operation.modality !== 'text' || !String(operation.feature_name).startsWith('generate_')) return feedbackJson({ error: 'This generation is unavailable.' }, 404);
    if (action === 'bind') {
      const resourceType = String(body.resourceType || '');
      const resourceId = String(body.resourceId || '');
      if (!resourceTables[resourceType] || !/^\d{1,18}$/.test(resourceId)) return feedbackJson({ error: 'Choose a valid resource.' }, 400);
      const resources = await readRows(auth.base, auth.serverKey, resourceTables[resourceType], { id: `eq.${resourceId}`, user_id: `eq.${auth.userId}` }, 'id,created_at');
      if (!resources[0]) return feedbackJson({ error: 'This resource is unavailable.' }, 404);
      const createdAt = Date.parse(String(resources[0].created_at || ''));
      const startedAt = Date.parse(String(operation.started_at || ''));
      if (!Number.isFinite(createdAt) || !Number.isFinite(startedAt) || createdAt < startedAt - 60000 || createdAt > startedAt + 3600000) return feedbackJson({ error: 'This resource does not belong to the generation.' }, 409);
      await upsertRow(auth.base, auth.serverKey, 'classio_generation_resources', 'generation_id', { generation_id: generationId, actor_user_id: auth.userId, resource_type: resourceType, resource_id: resourceId });
      return feedbackJson({ saved: true });
    }
    const links = await readRows(auth.base, auth.serverKey, 'classio_generation_resources', { generation_id: `eq.${generationId}`, actor_user_id: `eq.${auth.userId}` }, 'resource_type,resource_id,edited_at');
    if (!links[0] || links[0].edited_at) return feedbackJson({ error: 'This generation has been edited or is unavailable.' }, 409);
    const attempts = await readRows(auth.base, auth.serverKey, 'classio_provider_attempts', { operation_id: `eq.${generationId}`, status: 'eq.success', order: 'attempt_no.desc' }, 'model_reported,model_requested', 1);
    const prior = await readRows(auth.base, auth.serverKey, 'classio_generation_intent_feedback', { generation_id: `eq.${generationId}`, actor_user_id: `eq.${auth.userId}` }, 'shown_at,resource_type,resource_id');
    const now = new Date().toISOString();
    await upsertRow(auth.base, auth.serverKey, 'classio_generation_intent_feedback', 'generation_id', {
      generation_id: generationId, operation_id: generationId, actor_user_id: auth.userId, source: 'expo', feature_name: operation.feature_name,
      generation_mode: 'ai', prompt_version: 'expo-generate-v1', model_name: String(attempts[0]?.model_reported || attempts[0]?.model_requested || '').slice(0, 160),
      resource_type: links[0].resource_type || prior[0]?.resource_type || '', resource_id: links[0].resource_id || prior[0]?.resource_id || '', shown_at: prior[0]?.shown_at || now,
      feedback_surface: body.surface, satisfied: body.satisfied, reason: body.satisfied ? null : reasons.has(String(body.reason)) ? body.reason : null, answered_at: now, updated_at: now,
    });
    await insertRow(auth.base, auth.serverKey, 'classio_generation_intent_feedback_events', { generation_id: generationId, actor_user_id: auth.userId, feedback_surface: body.surface, satisfied: body.satisfied, reason: body.satisfied ? null : reasons.has(String(body.reason)) ? body.reason : null });
    return feedbackJson({ saved: true });
  } catch (error) { console.error('Generation feedback failed', error instanceof Error ? error.message : 'unknown'); return feedbackJson({ error: 'Feedback could not be saved.' }, 503); }
}
