import { authorizeQualityFeedback, feedbackJson, insertRow, readRows, upsertRow } from '../../server/quality-feedback-api';

const uuid = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value) ? value : '';
const reasons = new Set(['content', 'level', 'format', 'other']);
const resourceTables: Record<string, string> = { plan: 'lesson_plans', worksheet: 'worksheets', exam: 'quick_exams', program: 'learning_programs' };
const operationFeatures: Record<string, string[]> = { plan: ['generate_plan', 'quick_lesson_ai'], worksheet: ['generate_worksheet', 'quick_worksheet_ai'], exam: ['generate_exam', 'quick_exam_ai'], program: ['generate_program'] };

export async function GET(request: Request) {
  try {
    const auth = await authorizeQualityFeedback(request);
    if ('error' in auth) return auth.error;
    const url = new URL(request.url);
    const resourceType = url.searchParams.get('resourceType') || '';
    const resourceId = url.searchParams.get('resourceId') || '';
    if (!resourceTables[resourceType] || !/^\d{1,18}$/.test(resourceId)) return feedbackJson({ eligible: false });
    const resources = await readRows(auth.base, auth.serverKey, resourceTables[resourceType], { id: `eq.${resourceId}`, user_id: `eq.${auth.userId}` }, resourceType === 'exam' ? 'id,created_at,updated_at' : 'id,created_at,updated_at,source_type');
    if (!resources[0]) return feedbackJson({ eligible: false });
    const links = await readRows(auth.base, auth.serverKey, 'classio_generation_resources', { resource_type: `eq.${resourceType}`, resource_id: `eq.${resourceId}`, actor_user_id: `eq.${auth.userId}` }, 'generation_id,edited_at');
    let link = links[0];
    if (!link) {
      // Older AI documents predate explicit resource binding. Recover only a
      // unique operation close to creation, and never revive a known edit.
      const resource = resources[0];
      const created = Date.parse(String(resource.created_at || ''));
      const updated = Date.parse(String(resource.updated_at || ''));
      const sourceIsAi = resourceType === 'exam' || String(resource.source_type || '') === 'ai';
      if (sourceIsAi && Number.isFinite(created) && Number.isFinite(updated) && Math.abs(updated - created) <= 60000) {
        const features = operationFeatures[resourceType];
        const candidates = await readRows(auth.base, auth.serverKey, 'classio_ai_operations', { actor_user_id: `eq.${auth.userId}`, status: 'eq.success', feature_name: `in.(${features.join(',')})`, finished_at: `gte.${new Date(created - 300000).toISOString()}`, order: 'finished_at.desc' }, 'operation_id,finished_at', 10);
        const nearby = candidates.filter((row) => created >= Date.parse(String(row.finished_at || '')) - 10000 && created <= Date.parse(String(row.finished_at || '')) + 300000);
        if (nearby.length === 1) {
          const previous = await readRows(auth.base, auth.serverKey, 'classio_generation_resources', { generation_id: `eq.${nearby[0].operation_id}` }, 'generation_id');
          if (!previous.length) {
            await upsertRow(auth.base, auth.serverKey, 'classio_generation_resources', 'generation_id', { generation_id: nearby[0].operation_id, actor_user_id: auth.userId, resource_type: resourceType, resource_id: resourceId });
            link = { generation_id: nearby[0].operation_id, edited_at: null };
          }
        }
      }
    }
    if (!link && ['plan', 'worksheet', 'exam'].includes(resourceType)) {
      const resource = resources[0];
      const created = Date.parse(String(resource.created_at || ''));
      const updated = Date.parse(String(resource.updated_at || ''));
      if ((resourceType === 'exam' || resource.source_type === 'ai') && Number.isFinite(created) && Number.isFinite(updated) && Math.abs(updated - created) <= 60000) {
        const answers = await readRows(auth.base, auth.serverKey, 'classio_legacy_generation_intent_feedback', { actor_user_id: `eq.${auth.userId}`, resource_type: `eq.${resourceType}`, resource_id: `eq.${resourceId}` }, 'satisfied,reason');
        return feedbackJson({ eligible: true, generationId: `legacy:${resourceType}:${resourceId}`, satisfied: answers[0]?.satisfied ?? null, reason: answers[0]?.reason ?? null });
      }
    }
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
    const rawGenerationId = String(body.generationId || '');
    const generationId = uuid(rawGenerationId);
    const legacy = /^legacy:(plan|worksheet|exam):([1-9]\d{0,17})$/.exec(rawGenerationId);
    const action = String(body.action || 'answer');
    if ((!generationId && !legacy) || !['answer', 'bind'].includes(action) || (action === 'answer' && (typeof body.satisfied !== 'boolean' || (body.reason && !reasons.has(String(body.reason))) || !['generation_preview', 'resource_page'].includes(String(body.surface))))) return feedbackJson({ error: 'Choose a valid answer.' }, 400);
    if (legacy) {
      if (action !== 'answer' || body.surface !== 'resource_page') return feedbackJson({ error: 'Choose a valid resource answer.' }, 400);
      const [, resourceType, resourceId] = legacy;
      const resources = await readRows(auth.base, auth.serverKey, resourceTables[resourceType], { id: `eq.${resourceId}`, user_id: `eq.${auth.userId}` }, resourceType === 'exam' ? 'id,created_at,updated_at' : 'id,created_at,updated_at,source_type');
      const resource = resources[0];
      if (!resource || (resourceType !== 'exam' && resource.source_type !== 'ai')) return feedbackJson({ error: 'This AI resource is unavailable.' }, 404);
      const created = Date.parse(String(resource.created_at || ''));
      const updated = Date.parse(String(resource.updated_at || ''));
      if (!Number.isFinite(created) || !Number.isFinite(updated) || Math.abs(updated - created) > 60000) return feedbackJson({ error: 'This resource has been edited.' }, 409);
      const links = await readRows(auth.base, auth.serverKey, 'classio_generation_resources', { resource_type: `eq.${resourceType}`, resource_id: `eq.${resourceId}`, actor_user_id: `eq.${auth.userId}` }, 'generation_id,edited_at');
      if (links.length) return feedbackJson({ error: 'This resource has a generation record.' }, 409);
      const now = new Date().toISOString();
      const answer = { actor_user_id: auth.userId, resource_type: resourceType, resource_id: resourceId, feedback_surface: 'resource_page', satisfied: body.satisfied, reason: body.satisfied ? null : reasons.has(String(body.reason)) ? body.reason : null, answered_at: now, updated_at: now };
      await upsertRow(auth.base, auth.serverKey, 'classio_legacy_generation_intent_feedback', 'actor_user_id,resource_type,resource_id', answer);
      await insertRow(auth.base, auth.serverKey, 'classio_legacy_generation_intent_events', { actor_user_id: auth.userId, resource_type: resourceType, resource_id: resourceId, feedback_surface: 'resource_page', satisfied: answer.satisfied, reason: answer.reason });
      return feedbackJson({ saved: true });
    }
    const operations = await readRows(auth.base, auth.serverKey, 'classio_ai_operations', { operation_id: `eq.${generationId}`, actor_user_id: `eq.${auth.userId}`, status: 'eq.success' }, 'operation_id,actor_user_id,source,feature_name,modality,started_at,finished_at');
    const operation = operations[0];
    if (!operation || operation.modality !== 'text' || !['expo', 'streamlit'].includes(String(operation.source)) || !['generate_plan', 'generate_worksheet', 'generate_exam', 'generate_program', 'quick_lesson_ai', 'quick_worksheet_ai', 'quick_exam_ai'].includes(String(operation.feature_name))) return feedbackJson({ error: 'This generation is unavailable.' }, 404);
    if (action === 'bind') {
      const resourceType = String(body.resourceType || '');
      const resourceId = String(body.resourceId || '');
      if (!resourceTables[resourceType] || !/^\d{1,18}$/.test(resourceId)) return feedbackJson({ error: 'Choose a valid resource.' }, 400);
      const expected = operationFeatures[resourceType];
      if (!expected.includes(String(operation.feature_name))) return feedbackJson({ error: 'This generation does not match the resource.' }, 409);
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
      generation_id: generationId, operation_id: generationId, actor_user_id: auth.userId, source: operation.source, feature_name: operation.feature_name,
      generation_mode: 'ai', prompt_version: operation.source === 'expo' ? 'expo-generate-v1' : 'streamlit-beta-v1', model_name: String(attempts[0]?.model_reported || attempts[0]?.model_requested || '').slice(0, 160),
      resource_type: links[0].resource_type || prior[0]?.resource_type || '', resource_id: links[0].resource_id || prior[0]?.resource_id || '', shown_at: prior[0]?.shown_at || now,
      feedback_surface: body.surface, satisfied: body.satisfied, reason: body.satisfied ? null : reasons.has(String(body.reason)) ? body.reason : null, answered_at: now, updated_at: now,
    });
    await insertRow(auth.base, auth.serverKey, 'classio_generation_intent_feedback_events', { generation_id: generationId, actor_user_id: auth.userId, feedback_surface: body.surface, satisfied: body.satisfied, reason: body.satisfied ? null : reasons.has(String(body.reason)) ? body.reason : null });
    return feedbackJson({ saved: true });
  } catch (error) { console.error('Generation feedback failed', error instanceof Error ? error.message : 'unknown'); return feedbackJson({ error: 'Feedback could not be saved.' }, 503); }
}
