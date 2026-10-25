import { redactDirectIdentifiers } from '../../server/ai-privacy-redaction';
import { fetchBoundedAiJson } from '../../server/bounded-ai-request';
import { beginAiOperation, beginProviderAttempt, extractProviderUsage, finishAiOperation, finishProviderAttempt, type AiEconomicContext } from '../../server/ai-economic-events';

const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });

export async function POST(request: Request) {
  try {
    const token = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
    const base = (process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '').replace(/\/$/, '');
    const anon = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
    const geminiKey = process.env.GEMINI_API_KEY || '';
    const openRouterKey = process.env.OPENROUTER_API_KEY || '';
    if (!token) return json({ error: 'Sign in to generate an image.' }, 401);
    if (!base || !anon || (!geminiKey && !openRouterKey)) return json({ error: 'Image generation is not configured.' }, 503);
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
    const providers = [
      { provider: 'openrouter' as const, key: openRouterKey, model: process.env.OPENROUTER_IMAGE_MODEL || 'google/gemini-3.1-flash-image' },
      { provider: 'gemini' as const, key: geminiKey, model: process.env.GEMINI_IMAGE_MODEL || 'gemini-3.1-flash-image' },
    ].filter((provider) => provider.key);
    const economicContext: AiEconomicContext = { base, serverKey: process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '', actorUserId: user.id, source: 'expo' };
    if (!economicContext.serverKey) return json({ error: 'AI usage recording is not configured.' }, 503);
    let operationId = '';
    let attemptId = '';
    try {
      operationId = await beginAiOperation(economicContext, `cover_${kind}`, 'image');
      let noCredit = true;
      for (const [index, provider] of providers.entries()) {
        attemptId = await beginProviderAttempt(economicContext, operationId, index + 1, provider.provider, provider.model, 'image');
        let finalizingSuccess = false;
        try {
          const safePrompt = redactDirectIdentifiers(prompt);
          const response = provider.provider === 'openrouter'
            ? await fetchBoundedAiJson('https://openrouter.ai/api/v1/images', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${provider.key}`, 'HTTP-Referer': 'https://classio.expo.app', 'X-Title': 'Classio' }, body: JSON.stringify({ model: provider.model, prompt: safePrompt, aspect_ratio: '16:9' }) }, { timeoutMs: 60000, maxResponseBytes: 12 * 1024 * 1024 })
            : await fetchBoundedAiJson(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(provider.model)}:generateContent`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-goog-api-key': provider.key }, body: JSON.stringify({ contents: [{ parts: [{ text: safePrompt }] }], generationConfig: { responseModalities: ['IMAGE'], imageConfig: { aspectRatio: '16:9' } } }) }, { timeoutMs: 60000, maxResponseBytes: 12 * 1024 * 1024 });
          if (!response.ok) {
            noCredit = noCredit && response.status === 402;
            await finishProviderAttempt(economicContext, attemptId, { status: 'failed', httpStatus: response.status, providerRequestId: response.requestId, errorKind: 'provider_http' }); attemptId = '';
            continue;
          }
          const body = response.body as { data?: { b64_json?: string; media_type?: string }[]; candidates?: { content?: { parts?: { inlineData?: { mimeType?: string; data?: string }; inline_data?: { mime_type?: string; data?: string } }[] } }[] };
          const remoteImage = provider.provider === 'openrouter' ? body.data?.[0] : body.candidates?.flatMap((candidate) => candidate.content?.parts || []).find((part) => part.inlineData?.data || part.inline_data?.data);
          const imageData = provider.provider === 'openrouter' ? (remoteImage as { b64_json?: string } | undefined)?.b64_json : (remoteImage as { inlineData?: { data?: string }; inline_data?: { data?: string } } | undefined)?.inlineData?.data || (remoteImage as { inline_data?: { data?: string } } | undefined)?.inline_data?.data;
          const mimeType = provider.provider === 'openrouter' ? (remoteImage as { media_type?: string } | undefined)?.media_type : (remoteImage as { inlineData?: { mimeType?: string }; inline_data?: { mime_type?: string } } | undefined)?.inlineData?.mimeType || (remoteImage as { inline_data?: { mime_type?: string } } | undefined)?.inline_data?.mime_type;
          const usage = extractProviderUsage(provider.provider, response.body);
          if (!imageData || imageData.length > 10 * 1024 * 1024 || !/^image\/(png|jpeg|webp)$/.test(mimeType || 'image/png')) {
            noCredit = false;
            await finishProviderAttempt(economicContext, attemptId, { status: 'failed', modelReported: provider.model, httpStatus: response.status, providerRequestId: response.requestId, ...usage, imageSizeRequested: '16:9', errorKind: 'invalid_image' }); attemptId = '';
            continue;
          }
          await finishProviderAttempt(economicContext, attemptId, { status: 'success', modelReported: provider.model, httpStatus: response.status, providerRequestId: response.requestId, ...usage, imageCount: 1, imageSizeRequested: '16:9' }); attemptId = '';
          // A lost telemetry response must not turn a completed cover into a failed operation.
          finalizingSuccess = true;
          try { await finishAiOperation(economicContext, operationId, 'success'); }
          catch { await finishAiOperation(economicContext, operationId, 'success'); }
          const completedOperationId = operationId; operationId = '';
          return json({ cover_image: { generator: 'classio_ai_resource_cover_v1', operation_id: completedOperationId, image_data_url: `data:${mimeType || 'image/png'};base64,${imageData}`, resource_type: kind === 'worksheet' ? 'Worksheet' : kind === 'exam' ? 'Exam' : 'Lesson plan' } });
        } catch (error) {
          if (finalizingSuccess) {
            console.error('AI image success could not be confirmed', error);
            operationId = '';
            return json({ error: 'The generated image could not be confirmed. Try again later.', code: 'image_finalization_unavailable' }, 503);
          }
          noCredit = false;
          console.error('Image provider request failed', provider.provider, error instanceof Error ? error.message : 'unknown error');
          if (attemptId) { await finishProviderAttempt(economicContext, attemptId, { status: 'failed', errorKind: 'transport_or_telemetry' }).catch(() => {}); attemptId = ''; }
        }
      }
      await finishAiOperation(economicContext, operationId, 'failed', noCredit ? 'provider_credit' : 'provider_failed'); operationId = '';
      return json({ error: noCredit ? 'Image generation is unavailable because the configured providers have no credit.' : 'Classio could not generate the image right now.', code: noCredit ? 'image_provider_credit' : 'image_provider_failed' }, 503);
    } catch (error) {
      console.error('Image provider request failed', error instanceof Error ? error.message : 'unknown error');
      if (attemptId) await finishProviderAttempt(economicContext, attemptId, { status: 'failed', errorKind: 'transport_or_telemetry' }).catch((failure) => console.error('AI image attempt finalization failed', failure));
      if (operationId) await finishAiOperation(economicContext, operationId, 'failed', 'transport_or_telemetry').catch((failure) => console.error('AI image operation finalization failed', failure));
      return json({ error: 'Classio could not generate the image right now.' }, 503);
    }
  } catch { return json({ error: 'Classio could not generate the image.' }, 500); }
}
