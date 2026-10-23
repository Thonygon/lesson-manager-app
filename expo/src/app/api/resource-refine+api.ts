import { configuredAiProviders, requestAiProvider } from '../../server/ai-provider-chain';
import { worksheetHasSource, worksheetReferencesSource } from '../../lib/worksheet-source';
import { beginAiOperation, beginProviderAttempt, finishAiOperation, finishProviderAttempt, type AiEconomicContext } from '../../server/ai-economic-events';

type Kind = 'plan' | 'worksheet' | 'exam';
const TABLE: Record<Kind, { table: string; column: string }> = { plan: { table: 'lesson_plans', column: 'plan_json' }, worksheet: { table: 'worksheets', column: 'worksheet_json' }, exam: { table: 'quick_exams', column: 'exam_data' } };
const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });
function parseObject(value: string): Record<string, unknown> { const cleaned = value.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, ''); const start = cleaned.indexOf('{'); const end = cleaned.lastIndexOf('}'); const parsed = JSON.parse(cleaned.slice(start, end + 1)); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Classio returned an invalid resource.'); return parsed as Record<string, unknown>; }
function preserveVisuals(original: unknown, revised: unknown): unknown { if (Array.isArray(original) && Array.isArray(revised)) return revised.map((value, index) => preserveVisuals(original[index], value)); if (!original || !revised || typeof original !== 'object' || typeof revised !== 'object' || Array.isArray(original) || Array.isArray(revised)) return revised; const output = { ...(revised as Record<string, unknown>) }; for (const [key, value] of Object.entries(original as Record<string, unknown>)) { if (/image|visual|thumbnail|base64|watermark/i.test(key)) output[key] = value; else if (key in output) output[key] = preserveVisuals(value, output[key]); } return output; }

export async function POST(request: Request) {
  try {
    const token = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
    const base = (process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '').replace(/\/$/, '');
    const anon = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
    if (!token) return json({ error: 'Sign in to edit teaching resources.' }, 401);
    if (!base || !anon) return json({ error: 'Resource editing is not configured.' }, 503);
    const raw = await request.text(); if (raw.length > 2000) return json({ error: 'Request is too long.' }, 413);
    const body = JSON.parse(raw) as { kind?: Kind; id?: string; prompt?: string };
    if (!body.kind || !Object.hasOwn(TABLE, body.kind) || !Number.isSafeInteger(Number(body.id)) || Number(body.id) < 1 || !body.prompt?.trim() || body.prompt.length > 1200) return json({ error: 'Choose a resource and describe the change.' }, 400);
    const headers = { apikey: anon, Authorization: `Bearer ${token}`, Accept: 'application/json' };
    const auth = await fetch(`${base}/auth/v1/user`, { headers, cache: 'no-store' }); if (!auth.ok) return json({ error: 'Your session has expired.' }, 401);
    const user = await auth.json() as { id?: string }; if (!user.id) return json({ error: 'Your session has expired.' }, 401);
    const definition = TABLE[body.kind]; const url = new URL(`${base}/rest/v1/${definition.table}`); url.searchParams.set('select', `id,user_id,${definition.column}${body.kind === 'exam' ? ',answer_key' : body.kind === 'worksheet' ? ',worksheet_type' : ''}`); url.searchParams.set('id', `eq.${body.id}`); url.searchParams.set('user_id', `eq.${user.id}`); url.searchParams.set('limit', '1');
    const lookup = await fetch(url, { headers, cache: 'no-store' }); if (!lookup.ok) return json({ error: 'This resource could not be loaded.' }, 503);
    const rows = await lookup.json() as Record<string, unknown>[]; const row = rows[0]; if (!row) return json({ error: 'Only the owner can edit this resource.' }, 403);
    const original = body.kind === 'exam' ? { exam_data: row.exam_data, answer_key: row.answer_key } : row[definition.column];
    if (!original || typeof original !== 'object' || Array.isArray(original)) return json({ error: 'This resource has no editable content.' }, 400);
    const serialized = JSON.stringify(original); if (serialized.length > 75000) return json({ error: 'This resource is too large for AI refinement. Use manual editing.' }, 413);
    const providers = configuredAiProviders({ OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY, GEMINI_API_KEY: process.env.GEMINI_API_KEY, OPENAI_API_KEY: process.env.OPENAI_API_KEY, AI_MODEL: process.env.AI_MODEL, OPENROUTER_MODEL: process.env.OPENROUTER_MODEL });
    if (!providers.length) return json({ error: 'Classio AI is not configured on the server.' }, 503);
    const economicContext: AiEconomicContext = { base, serverKey: process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '', actorUserId: user.id, source: 'expo' };
    if (!economicContext.serverKey) return json({ error: 'AI usage recording is not configured.' }, 503);
    const operationId = await beginAiOperation(economicContext, `refine_${body.kind}`, 'text');
    try {
    const worksheet = body.kind === 'worksheet' ? original as Record<string, unknown> : null;
    const worksheetType = String(worksheet?.worksheet_type || row.worksheet_type || '');
    const sourceField = worksheetType === 'reading_comprehension' ? 'reading_passage' : 'source_text';
    const asksForText = /\b(?:text|passage|paragraph|article|reading)\b|texto|pasaje|párrafo|parrafo|lectura|metin|paragraf/i.test(body.prompt);
    const repairMissingSource = worksheet && asksForText && !worksheetHasSource(worksheet) && (worksheetReferencesSource(worksheet) || worksheetType === 'short_answer' || worksheetType === 'reading_comprehension');
    if (repairMissingSource) {
      const context = { title: worksheet.title, subject: worksheet.subject, topic: worksheet.topic, learner_stage: worksheet.learner_stage, level_or_band: worksheet.level_or_band, student_material_language: worksheet.student_material_language, instructions: worksheet.instructions, questions: worksheet.questions, answer_key: worksheet.answer_key };
      const sourceSystem = `You are Classio's worksheet editor. Return ONLY a JSON object with one key, "${sourceField}", containing a complete student-facing source text. Write in the worksheet's student_material_language. Use the existing questions and answer key as constraints: every question must be answerable from the text, and quoted phrases or paragraph references in the questions must appear in the appropriate part of the text. Preserve the intended language skill; for short_answer, support analysis, rewriting, or reasoning rather than simple fact recall. Do not rewrite questions, answers, or metadata. Do not emit markdown.`;
      const sourceInstruction = `Teacher request: ${body.prompt.trim()}\n\nWorksheet context:\n${JSON.stringify(context)}`;
      let sourceError = 'Classio did not generate a usable source text. Please try again.';
      for (const [index, provider] of providers.slice(0, 2).entries()) {
        const attemptId = await beginProviderAttempt(economicContext, operationId, index + 1, provider.provider, provider.model, 'text');
        let response: Awaited<ReturnType<typeof requestAiProvider>> | null = null;
        let sourceText = '';
        try {
          response = await requestAiProvider(provider, sourceSystem, sourceInstruction);
          const candidate = parseObject(response.content);
          sourceText = String(candidate[sourceField] || '').trim();
          if (sourceText.length < 80) throw new Error('Classio did not generate a complete source text. Please try again.');
        } catch (reason) { sourceError = reason instanceof Error ? reason.message : sourceError; }
        await finishProviderAttempt(economicContext, attemptId, { status: sourceText.length >= 80 ? 'success' : 'failed', modelReported: response?.model, providerRequestId: response?.providerRequestId, httpStatus: response?.httpStatus, ...response?.usage, errorKind: sourceText.length >= 80 ? undefined : response ? 'invalid_output' : 'provider_error' });
        if (sourceText.length >= 80 && response) { await finishAiOperation(economicContext, operationId, 'success'); return json({ document: { ...worksheet, [sourceField]: sourceText }, model: response.model }); }
      }
      await finishAiOperation(economicContext, operationId, 'failed', 'provider_failed');
      return json({ error: sourceError }, 503);
    }
    const system = `You are Classio's teaching-resource editor. Return one complete JSON object with the same top-level structure as the supplied resource. Apply only the teacher's requested change. Preserve all unrelated questions, answers, teaching goals, languages, and formatting. Keep answer keys aligned with questions. Do not emit markdown. Do not invent image URLs or image data.`;
    const instruction = `Teacher request: ${body.prompt.trim()}\n\nCurrent ${body.kind} resource JSON:\n${serialized}`;
    let lastError = 'Classio could not refine this resource.';
    for (const [index, provider] of providers.slice(0, 2).entries()) {
      const attemptId = await beginProviderAttempt(economicContext, operationId, index + 1, provider.provider, provider.model, 'text');
      let response: Awaited<ReturnType<typeof requestAiProvider>> | null = null;
      let result: Record<string, unknown> | null = null;
      try {
        response = await requestAiProvider(provider, system, instruction);
        const candidate = parseObject(response.content);
        result = preserveVisuals(original, candidate) as Record<string, unknown>;
        if (body.kind === 'exam' && (!result.exam_data || !result.answer_key)) throw new Error('The revised exam needs both questions and an answer key.');
        if (JSON.stringify(result) === serialized) throw new Error('Classio returned the original resource without applying the requested change. Please try again.');
        if (body.kind === 'worksheet' && worksheetReferencesSource(result) && !worksheetHasSource(result)) throw new Error('Classio did not add the source text referenced by the questions. Please try again.');
      } catch (reason) { result = null; lastError = reason instanceof Error ? reason.message : lastError; }
      await finishProviderAttempt(economicContext, attemptId, { status: result ? 'success' : 'failed', modelReported: response?.model, providerRequestId: response?.providerRequestId, httpStatus: response?.httpStatus, ...response?.usage, errorKind: result ? undefined : response ? 'invalid_output' : 'provider_error' });
      if (result && response) { await finishAiOperation(economicContext, operationId, 'success'); return json({ document: result, model: response.model }); }
    }
    await finishAiOperation(economicContext, operationId, 'failed', 'provider_failed');
    return json({ error: lastError }, 503);
    } catch (error) { await finishAiOperation(economicContext, operationId, 'failed', 'unexpected_error').catch((failure) => console.error('AI economic operation finalization failed', failure)); throw error; }
  } catch { return json({ error: 'Classio could not refine this resource.' }, 500); }
}
