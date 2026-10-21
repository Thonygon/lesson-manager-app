/** Try free-capable providers before paid fallbacks. */
export type AiProvider = 'openrouter' | 'gemini' | 'openai';
export type AiProviderConfig = { provider: AiProvider; key: string; model: string };
type ProviderEnvironment = Partial<Record<'OPENROUTER_API_KEY' | 'GEMINI_API_KEY' | 'OPENAI_API_KEY' | 'AI_MODEL' | 'OPENROUTER_MODEL' | 'GEMINI_MODEL', string>>;

export function configuredAiProviders(env: ProviderEnvironment): AiProviderConfig[] {
  const openRouterModel = env.OPENROUTER_MODEL?.trim() || '';
  const freeOpenRouterModel = openRouterModel === 'openrouter/free' || openRouterModel.endsWith(':free') ? openRouterModel : 'openrouter/free';
  return ([
    { provider: 'openrouter', key: env.OPENROUTER_API_KEY?.trim() || '', model: freeOpenRouterModel },
    { provider: 'gemini', key: env.GEMINI_API_KEY?.trim() || '', model: env.GEMINI_MODEL?.trim() || 'gemini-2.5-flash' },
    { provider: 'openai', key: env.OPENAI_API_KEY?.trim() || '', model: env.AI_MODEL?.trim() || 'gpt-4o-mini' },
  ] as AiProviderConfig[]).filter((item) => Boolean(item.key));
}

export async function requestAiProvider(
  provider: AiProviderConfig, systemPrompt: string, userPrompt: string, fetcher: typeof fetch = fetch,
): Promise<{ content: string; model: string }> {
  const commonHeaders = { 'Content-Type': 'application/json' };
  const response = provider.provider === 'gemini'
    ? await fetcher(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(provider.model)}:generateContent`, {
      method: 'POST', headers: { ...commonHeaders, 'x-goog-api-key': provider.key },
      body: JSON.stringify({ systemInstruction: { parts: [{ text: systemPrompt }] }, contents: [{ role: 'user', parts: [{ text: userPrompt }] }], generationConfig: { temperature: 0.35, responseMimeType: 'application/json' } }),
    })
    : await fetcher(provider.provider === 'openrouter' ? 'https://openrouter.ai/api/v1/chat/completions' : 'https://api.openai.com/v1/chat/completions', {
      method: 'POST', headers: { ...commonHeaders, Authorization: `Bearer ${provider.key}`, ...(provider.provider === 'openrouter' ? { 'HTTP-Referer': 'https://classio.expo.app', 'X-Title': 'Classio' } : {}) },
      body: JSON.stringify({ model: provider.model, messages: [{ role: 'system', content: systemPrompt }, { role: 'user', content: userPrompt }], temperature: 0.35, response_format: { type: 'json_object' } }),
    });
  if (!response.ok) throw new Error(`${provider.provider} returned HTTP ${response.status}.`);
  const result = await response.json() as Record<string, unknown>;
  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  const firstCandidate = candidates[0] && typeof candidates[0] === 'object' ? candidates[0] as Record<string, unknown> : {};
  const content = firstCandidate.content && typeof firstCandidate.content === 'object' ? firstCandidate.content as Record<string, unknown> : {};
  const parts = Array.isArray(content.parts) ? content.parts : [];
  const geminiText = parts.map((part) => part && typeof part === 'object' ? String((part as Record<string, unknown>).text || '') : '').join('');
  const choices = Array.isArray(result.choices) ? result.choices : [];
  const firstChoice = choices[0] && typeof choices[0] === 'object' ? choices[0] as Record<string, unknown> : {};
  const message = firstChoice.message && typeof firstChoice.message === 'object' ? firstChoice.message as Record<string, unknown> : {};
  const responseText = provider.provider === 'gemini' ? geminiText : String(message.content || '');
  if (!responseText.trim()) throw new Error(`${provider.provider} returned an empty document.`);
  return { content: responseText, model: String(result.model || provider.model) };
}
