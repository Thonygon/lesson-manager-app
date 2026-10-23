export type AiRequestLimits = { timeoutMs: number; maxResponseBytes: number };

/** Bound both elapsed time and bytes read, including streamed responses without Content-Length. */
export async function fetchBoundedAiJson(
  url: string,
  init: RequestInit,
  limits: AiRequestLimits,
  fetcher: typeof fetch = fetch,
): Promise<{ ok: boolean; status: number; body: Record<string, unknown>; requestId: string }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), limits.timeoutMs);
  try {
    const response = await fetcher(url, { ...init, signal: controller.signal });
    const requestId = response.headers?.get('x-request-id') || response.headers?.get('x-goog-request-id') || '';
    if (!response.ok) return { ok: false, status: response.status, body: {}, requestId };
    const declaredLength = Number(response.headers?.get('content-length'));
    if (Number.isFinite(declaredLength) && declaredLength > limits.maxResponseBytes) throw new Error('AI provider response exceeded the size limit.');
    if (!response.body) throw new Error('AI provider returned an empty response.');
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    try {
      while (true) {
        const next = await reader.read();
        if (next.done) break;
        length += next.value.byteLength;
        if (length > limits.maxResponseBytes) {
          await reader.cancel().catch(() => {});
          throw new Error('AI provider response exceeded the size limit.');
        }
        chunks.push(next.value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('AI provider returned invalid JSON.');
    return { ok: true, status: response.status, body: parsed as Record<string, unknown>, requestId };
  } catch (error) {
    if (controller.signal.aborted) throw new Error('AI provider timed out.');
    throw error;
  } finally { clearTimeout(timeout); }
}
