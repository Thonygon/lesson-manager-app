import { localizeAdminError } from '@/lib/admin-error-copy';
import type { AppLanguage } from '@/providers/app-preferences';
import { requireSupabase } from '@/lib/supabase';

export async function performAdminAction(input: Record<string, unknown>, language: AppLanguage = 'en'): Promise<void> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error ?? new Error('Your Classio session has expired.');
  const response = await fetch('/api/admin-actions', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify(input) });
  const result = await response.json().catch(() => ({})) as { error?: string; audited?: boolean };
  if (!response.ok) throw new Error(localizeAdminError(result.error || 'The admin action could not be completed.', language));
  if (result.audited === false) throw new Error(localizeAdminError('The change was saved, but the audit record could not be written. Check the audit log before continuing.', language));
}
export async function loadAdminExplorerMove(id: string, language: AppLanguage = 'en'): Promise<Record<string, unknown>> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error ?? new Error('Your Classio session has expired.');
  const response = await fetch(`/api/admin-explorer-move?id=${encodeURIComponent(id)}`, { headers: { Authorization: `Bearer ${data.session.access_token}` } });
  const result = await response.json().catch(() => ({})) as { error?: string; move?: Record<string, unknown> };
  if (!response.ok || !result.move) throw new Error(localizeAdminError(result.error || 'The Explorer preview could not be loaded.', language));
  return result.move;
}
