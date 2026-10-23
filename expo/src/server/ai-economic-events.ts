type Source = 'expo';
export type AiModality = 'text' | 'image';
export type AiEconomicContext = { base: string; serverKey: string; actorUserId?: string | null; source: Source };
export type ProviderUsage = {
  input_tokens: number | null;
  output_tokens: number | null;
  cached_input_tokens: number | null;
  reasoning_tokens: number | null;
  usage_observed: boolean;
  usage_json: Record<string, unknown>;
};
export type AttemptResult = Partial<ProviderUsage> & {
  status: 'success' | 'failed';
  modelReported?: string;
  httpStatus?: number;
  providerRequestId?: string;
  imageCount?: number;
  imageSizeRequested?: string;
  imageResolution?: string;
  errorKind?: string;
};

const count = (value: unknown): number | null => Number.isSafeInteger(value) && Number(value) >= 0 ? Number(value) : null;
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
function numericUsage(value: unknown, depth = 0): Record<string, unknown> {
  if (depth > 2) return {};
  const safe: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(object(value)).slice(0, 30)) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,60}$/.test(key)) continue;
    const number = count(item);
    if (number !== null) { safe[key] = number; continue; }
    const nested = numericUsage(item, depth + 1);
    if (Object.keys(nested).length) safe[key] = nested;
  }
  return safe;
}

/** Keep provider-reported counters; absent counters remain null, never zero. */
export function extractProviderUsage(provider: 'openrouter' | 'gemini' | 'openai', payload: unknown): ProviderUsage {
  const root = object(payload);
  const raw = provider === 'gemini' ? object(root.usageMetadata) : object(root.usage);
  const promptDetails = object(raw.prompt_tokens_details);
  const completionDetails = object(raw.completion_tokens_details);
  return {
    input_tokens: count(provider === 'gemini' ? raw.promptTokenCount : raw.prompt_tokens),
    output_tokens: count(provider === 'gemini' ? raw.candidatesTokenCount : raw.completion_tokens),
    cached_input_tokens: count(provider === 'gemini' ? raw.cachedContentTokenCount : promptDetails.cached_tokens),
    reasoning_tokens: count(provider === 'gemini' ? raw.thoughtsTokenCount : completionDetails.reasoning_tokens),
    usage_observed: Object.keys(raw).length > 0,
    usage_json: numericUsage(raw),
  };
}

async function write(context: AiEconomicContext, table: string, method: 'POST' | 'PATCH', payload: Record<string, unknown>, id?: { column: string; value: string }) {
  if (!context.base || !context.serverKey) throw new Error('AI economic telemetry is not configured.');
  const url = new URL(`${context.base.replace(/\/$/, '')}/rest/v1/${table}`);
  if (id) url.searchParams.set(id.column, `eq.${id.value}`);
  const response = await fetch(url, {
    method,
    headers: { apikey: context.serverKey, Authorization: `Bearer ${context.serverKey}`, 'Content-Type': 'application/json', Prefer: method === 'PATCH' ? 'return=representation' : 'return=minimal' },
    body: JSON.stringify(payload),
    cache: 'no-store',
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`AI economic telemetry ${table} write failed (${response.status}).`);
  if (method === 'PATCH') {
    const rows: unknown = await response.json();
    if (!Array.isArray(rows) || rows.length !== 1) throw new Error(`AI economic telemetry ${table} update was not confirmed.`);
  }
}

export async function beginAiOperation(context: AiEconomicContext, featureName: string, modality: AiModality): Promise<string> {
  const operationId = crypto.randomUUID();
  await write(context, 'classio_ai_operations', 'POST', { operation_id: operationId, actor_user_id: context.actorUserId || null, source: context.source, feature_name: featureName, modality, status: 'started' });
  return operationId;
}

export async function finishAiOperation(context: AiEconomicContext, operationId: string, status: 'success' | 'failed', errorKind?: string): Promise<void> {
  await write(context, 'classio_ai_operations', 'PATCH', { status, finished_at: new Date().toISOString(), error_kind: errorKind || null }, { column: 'operation_id', value: operationId });
}

export async function beginProviderAttempt(context: AiEconomicContext, operationId: string, attemptNo: number, provider: 'openrouter' | 'gemini' | 'openai', model: string, modality: AiModality): Promise<string> {
  const attemptId = crypto.randomUUID();
  await write(context, 'classio_provider_attempts', 'POST', { attempt_id: attemptId, operation_id: operationId, attempt_no: attemptNo, provider, model_requested: model, modality, status: 'started' });
  return attemptId;
}

/** One Worker subrequest covers plan checks, atomic quota reservation and both start records. */
export async function beginReservedGenerationAttempt(context: AiEconomicContext, profilePlan: string, featureName: string, operationId: string, attemptId: string, attemptNo: number, provider: 'openrouter' | 'gemini' | 'openai', model: string): Promise<{ allowed: boolean; status: number; reason: string }> {
  if (!context.base || !context.serverKey || !context.actorUserId) throw new Error('AI generation reservation is not configured.');
  const response = await fetch(`${context.base.replace(/\/$/, '')}/rest/v1/rpc/classio_begin_ai_generation_attempt`, {
    method: 'POST',
    headers: { apikey: context.serverKey, Authorization: `Bearer ${context.serverKey}`, 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ p_user_id: context.actorUserId, p_profile_plan: profilePlan, p_feature_name: featureName, p_provider: provider, p_model: model, p_operation_id: operationId, p_attempt_id: attemptId, p_attempt_no: attemptNo }),
    cache: 'no-store',
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`AI generation reservation failed (${response.status}).`);
  const result = await response.json() as { allowed?: unknown; status?: unknown; reason?: unknown };
  if (typeof result.allowed !== 'boolean') throw new Error('AI generation reservation was not confirmed.');
  return { allowed: result.allowed, status: Number(result.status) || 200, reason: String(result.reason || '') };
}

export async function finishProviderAttempt(context: AiEconomicContext, attemptId: string, result: AttemptResult): Promise<void> {
  await write(context, 'classio_provider_attempts', 'PATCH', {
    status: result.status,
    finished_at: new Date().toISOString(),
    model_reported: result.modelReported?.slice(0, 160) || null,
    http_status: result.httpStatus || null,
    provider_request_id: result.providerRequestId?.slice(0, 160) || null,
    input_tokens: result.input_tokens ?? null,
    output_tokens: result.output_tokens ?? null,
    cached_input_tokens: result.cached_input_tokens ?? null,
    reasoning_tokens: result.reasoning_tokens ?? null,
    image_count: result.imageCount ?? null,
    image_size_requested: result.imageSizeRequested?.slice(0, 40) || null,
    image_resolution: result.imageResolution?.slice(0, 40) || null,
    usage_observed: result.usage_observed ?? false,
    usage_json: result.usage_json ?? {},
    error_kind: result.errorKind?.slice(0, 80) || null,
  }, { column: 'attempt_id', value: attemptId });
}

/** Complete a generation's attempts, operation and usage log in one Worker subrequest. */
export async function finishGenerationOperation(context: AiEconomicContext, operationId: string, status: 'success' | 'failed', attempts: { attemptId: string; result: AttemptResult }[], errorKind = '', usageMeta: Record<string, unknown> = {}): Promise<void> {
  if (!context.base || !context.serverKey || !operationId) throw new Error('AI generation telemetry is not configured.');
  const response = await fetch(`${context.base.replace(/\/$/, '')}/rest/v1/rpc/classio_finish_ai_generation`, {
    method: 'POST',
    headers: { apikey: context.serverKey, Authorization: `Bearer ${context.serverKey}`, 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      p_operation_id: operationId,
      p_user_id: context.actorUserId || null,
      p_status: status,
      p_error_kind: errorKind || null,
      p_attempts: attempts.map(({ attemptId, result }) => ({
        attempt_id: attemptId,
        status: result.status,
        model_reported: result.modelReported?.slice(0, 160) || null,
        http_status: result.httpStatus || null,
        provider_request_id: result.providerRequestId?.slice(0, 160) || null,
        input_tokens: result.input_tokens ?? null,
        output_tokens: result.output_tokens ?? null,
        cached_input_tokens: result.cached_input_tokens ?? null,
        reasoning_tokens: result.reasoning_tokens ?? null,
        usage_observed: result.usage_observed ?? false,
        usage_json: result.usage_json ?? {},
        error_kind: result.errorKind?.slice(0, 80) || null,
      })),
      p_usage_meta: usageMeta,
    }),
    cache: 'no-store',
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok || await response.json() !== true) throw new Error(`AI generation telemetry finalization failed (${response.status}).`);
}
