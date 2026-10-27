export async function recordAiFallback(
  base: string, serverKey: string, featureName: string,
  effectiveMode: 'template' | 'heuristic' | 'unavailable', reason: string,
  fetcher: typeof fetch = fetch,
) {
  if (!base || !serverKey) return false;
  try {
    const response = await fetcher(`${base.replace(/\/$/, '')}/rest/v1/classio_ai_fallback_events`, {
      method: 'POST', headers: { apikey: serverKey, Authorization: `Bearer ${serverKey}`, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
      body: JSON.stringify({ source: 'expo', feature_name: featureName, requested_mode: 'ai', effective_mode: effectiveMode, reason }),
    });
    return response.ok;
  } catch { return false; }
}
