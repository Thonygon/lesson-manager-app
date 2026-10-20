import { localizeAdminError } from '@/lib/admin-error-copy';
import type { AppLanguage } from '@/providers/app-preferences';
import { requireSupabase } from '@/lib/supabase';

export type AdminAiSnapshot = {
  contentCounts: Record<string, number | null>;
  experiments: Record<string, unknown>[];
  recentRuns: Record<string, unknown>[];
  recentJobs: Record<string, unknown>[];
  validatedRuns: Record<string, unknown>[];
  warnings: string[];
  generatedAt: string;
};

let snapshotCache: { userId: string; value: AdminAiSnapshot; expires: number } | null = null;
let snapshotPending: { userId: string; request: Promise<AdminAiSnapshot> } | null = null;
export function invalidateAdminAiSnapshot() { snapshotCache = null; }

export async function loadAdminAiSnapshot(language: AppLanguage = 'en'): Promise<AdminAiSnapshot> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error || new Error('Sign in to view AI intelligence.');
  const userId = data.session.user.id;
  if (snapshotCache?.userId === userId && snapshotCache.expires > Date.now()) return snapshotCache.value;
  if (snapshotPending?.userId === userId) return snapshotPending.request;
  const request = (async () => {
    const response = await fetch('/api/admin-ai', { headers: { Authorization: `Bearer ${data.session.access_token}` }, cache: 'no-store' });
    const payload = await response.json() as AdminAiSnapshot & { error?: string };
    if (!response.ok) throw new Error(localizeAdminError(payload.error || 'AI intelligence could not be loaded.', language));
    snapshotCache = { userId, value: payload, expires: Date.now() + 60_000 };
    return payload;
  })();
  snapshotPending = { userId, request };
  try { return await request; } finally { if (snapshotPending?.request === request) snapshotPending = null; }
}
