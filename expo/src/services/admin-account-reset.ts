import { requireSupabase } from '@/lib/supabase';
import { pythonModelApiUrl } from '@/services/python-models';

export type ResetScope = 'student' | 'teacher' | 'full';
export type ResetPreviewRow = { label_key: string; action: 'delete' | 'archive' | 'reset'; count: number; note_key?: string };
export type ResetPreview = { scope: ResetScope; rows: ResetPreviewRow[]; summary: Record<'delete' | 'archive' | 'reset', number> };
export type ResetOptions = { user_id: string; scope: ResetScope; archive_shared_resources: boolean; remove_relationships: boolean; notes: string; confirm?: boolean; confirmation_phrase?: string };

async function requestReset<T>(action: 'preview' | 'execute', options: ResetOptions): Promise<T> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session?.access_token) throw new Error('Your Classio session has expired.');
  const response = await fetch(`${pythonModelApiUrl()}/v1/admin/account-reset/${action}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${data.session.access_token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
  });
  const payload = await response.json().catch(() => ({})) as T & { detail?: string };
  if (!response.ok) throw new Error(payload.detail || `Account reset ${action} is unavailable (${response.status}).`);
  return payload;
}

export const previewAdminAccountReset = (options: ResetOptions) => requestReset<ResetPreview>('preview', options);
export const executeAdminAccountReset = (options: ResetOptions) => requestReset<{ ok: true; audited: boolean; counters: Record<string, number> }>('execute', options);
