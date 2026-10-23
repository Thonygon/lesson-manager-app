import { redactDirectIdentifiers } from '../../server/ai-privacy-redaction';
import { fetchBoundedAiJson } from '../../server/bounded-ai-request';
import { beginAiOperation, beginProviderAttempt, extractProviderUsage, finishAiOperation, finishProviderAttempt, type AiEconomicContext } from '../../server/ai-economic-events';

const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });

export async function POST(request: Request) {
  try {
    const token = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
    const base = (process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '').replace(/\/$/, '');
    const anon = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
    const key = process.env.GEMINI_API_KEY || '';
    if (!token) return json({ error: 'Sign in to generate an image.' }, 401);
    if (!base || !anon || !key) return json({ error: 'Image generation is not configured.' }, 503);
    const body = await request.json() as { id?: string; kind?: 'plan' | 'worksheet' | 'exam' };
    const planId = String(body.id ?? '').trim();
    if (!planId || planId.length > 100 || !/^[a-zA-Z0-9-]+$/.test(planId)) return json({ error: 'Invalid lesson plan.' }, 400);
    const kind = body.kind === 'worksheet' || body.kind === 'exam' ? body.kind : 'plan';
    const table = kind === 'worksheet' ? 'worksheets' : kind === 'exam' ? 'quick_exams' : 'lesson_plans';
    const payloadColumn = kind === 'worksheet' ? 'worksheet_json' : kind === 'exam' ? 'exam_data' : 'plan_json';
    const levelColumn = kind === 'exam' ? 'level' : 'level_or_band';
    const headers = { apikey: anon, Authorization: `Bearer ${token}`, Accept: 'application/json' };
    const auth = await fetch(`${base}/auth/v1/user`, { headers, cache: 'no-store' });
    if (!auth.ok) return json({ error: 'Your session has expired.' }, 401);
    const user = await auth.json() as { id?: string };
    if (!user.id) return json({ error: 'Your session has expired.' }, 401);
    const url = new URL(`${base}/rest/v1/${table}`);
    url.searchParams.set('select', `id,user_id,title,subject,topic,learner_stage,${levelColumn},${payloadColumn}`);
    url.searchParams.set('id', `eq.${planId}`);
    url.searchParams.set('user_id', `eq.${user.id}`);
    url.searchParams.set('limit', '1');
    const lookup = await fetch(url, { headers, cache: 'no-store' });
    if (!lookup.ok) return json({ error: 'This lesson plan could not be loaded.' }, 503);
    const rows = await lookup.json() as Record<string, unknown>[];
    const row = rows[0];
    if (!row) return json({ error: 'Only the owner can generate an image.' }, 403);
    const plan = row[payloadColumn] && typeof row[payloadColumn] === 'object' ? row[payloadColumn] as Record<string, unknown> : {};
    const prompt = `Asset type: Classio ${kind === 'worksheet' ? 'worksheet' : kind === 'exam' ? 'exam' : 'lesson plan'} gallery cover image. Title/context: ${String(row.title || plan.title || '').slice(0, 200)}. Subject: ${String(row.subject || '').slice(0, 80)}. Topic: ${String(row.topic || '').slice(0, 120)}. Learner stage: ${String(row.learner_stage || '').slice(0, 80)}. Level/band: ${String(row[levelColumn] || '').slice(0, 40)}. Wide 16:9 modern educational illustration, one clear age-appropriate teaching scene, polished resource-library cover. Absolutely no text, letters, numbers, captions, logos, labels, or watermarks.`;
    const model = process.env.GEMINI_IMAGE_MODEL || 'gemini-3.1-flash-image-preview';
    const economicContext: AiEconomicContext = { base, serverKey: process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '', actorUserId: user.id, source: 'expo' };
    if (!economicContext.serverKey) return json({ error: 'AI usage recording is not configured.' }, 503);
    let operationId = '';
    let attemptId = '';
    try {
      operationId = await beginAiOperation(economicContext, `cover_${kind}`, 'image');
      attemptId = await beginProviderAttempt(economicContext, operationId, 1, 'gemini', model, 'image');
      const response = await fetchBoundedAiJson(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key }, body: JSON.stringify({ contents: [{ parts: [{ text: redactDirectIdentifiers(prompt) }] }] }) }, { timeoutMs: 45000, maxResponseBytes: 12 * 1024 * 1024 });
      if (!response.ok) {
        await finishProviderAttempt(economicContext, attemptId, { status: 'failed', httpStatus: response.status, providerRequestId: response.requestId, errorKind: 'provider_http' }); attemptId = '';
        await finishAiOperation(economicContext, operationId, 'failed', 'provider_http'); operationId = '';
        return json({ error: 'Classio could not generate the image right now.' }, 503);
      }
      const result = response.body as { candidates?: { content?: { parts?: { inlineData?: { mimeType?: string; data?: string } }[] } }[] };
      const image = result.candidates?.flatMap((candidate) => candidate.content?.parts || []).find((part) => part.inlineData?.data)?.inlineData;
      const usage = extractProviderUsage('gemini', response.body);
      if (!image?.data || image.data.length > 10 * 1024 * 1024 || !/^image\/(png|jpeg|webp)$/.test(image.mimeType || 'image/png')) {
        await finishProviderAttempt(economicContext, attemptId, { status: 'failed', modelReported: model, httpStatus: response.status, providerRequestId: response.requestId, ...usage, imageSizeRequested: '16:9', errorKind: 'invalid_image' }); attemptId = '';
        await finishAiOperation(economicContext, operationId, 'failed', 'invalid_image'); operationId = '';
        return json({ error: 'The image provider returned no usable image.' }, 503);
      }
      await finishProviderAttempt(economicContext, attemptId, { status: 'success', modelReported: model, httpStatus: response.status, providerRequestId: response.requestId, ...usage, imageCount: 1, imageSizeRequested: '16:9' }); attemptId = '';
      await finishAiOperation(economicContext, operationId, 'success'); operationId = '';
      return json({ cover_image: { generator: 'classio_ai_resource_cover_v1', image_data_url: `data:${image.mimeType || 'image/png'};base64,${image.data}`, resource_type: kind === 'worksheet' ? 'Worksheet' : kind === 'exam' ? 'Exam' : 'Lesson plan' } });
    } catch (error) {
      console.error('Image provider request failed', error instanceof Error ? error.message : 'unknown error');
      if (attemptId) await finishProviderAttempt(economicContext, attemptId, { status: 'failed', errorKind: 'transport_or_telemetry' }).catch((failure) => console.error('AI image attempt finalization failed', failure));
      if (operationId) await finishAiOperation(economicContext, operationId, 'failed', 'transport_or_telemetry').catch((failure) => console.error('AI image operation finalization failed', failure));
      return json({ error: 'Classio could not generate the image right now.' }, 503);
    }
  } catch { return json({ error: 'Classio could not generate the image.' }, 500); }
}
