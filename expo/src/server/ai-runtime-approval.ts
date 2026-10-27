import type { AiProviderConfig } from './ai-provider-chain';

export const EXPO_TEXT_PROMPT_VERSION = 'expo-generate-v1';
export const EXPO_IMAGE_PROMPT_VERSION = 'expo-cover-v1';

/** Fail closed when the approval registry is unavailable or a model was retired. */
export async function approvedAiProviders(
  providers: AiProviderConfig[], surface: 'expo_text' | 'expo_image', promptVersion: string,
  base: string, serverKey: string, fetcher: typeof fetch = fetch,
): Promise<AiProviderConfig[]> {
  if (!providers.length) return [];
  if (!base || !serverKey) throw new Error('AI approval registry is unavailable.');
  const url = new URL(`${base.replace(/\/$/, '')}/rest/v1/classio_ai_runtime_approvals`);
  url.searchParams.set('select', 'provider,model');
  url.searchParams.set('surface', `eq.${surface}`);
  url.searchParams.set('prompt_version', `eq.${promptVersion}`);
  url.searchParams.set('status', 'eq.approved');
  const response = await fetcher(url, { headers: { apikey: serverKey, Authorization: `Bearer ${serverKey}` } });
  if (!response.ok) throw new Error('AI approval registry is unavailable.');
  const rows = await response.json() as { provider?: string; model?: string }[];
  if (!Array.isArray(rows)) throw new Error('AI approval registry returned invalid data.');
  const allowed = new Set(rows.map((row) => `${row.provider}:${row.model}`));
  return providers.filter((item) => allowed.has(`${item.provider}:${item.model}`));
}
