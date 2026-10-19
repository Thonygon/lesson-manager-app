import { localizeAdminError } from '@/lib/admin-error-copy';
import type { AppLanguage } from '@/providers/app-preferences';
import { requireSupabase } from '@/lib/supabase';

export type AdminAiSnapshot = {
  contentCounts: Record<string, number | null>;
  countMethod: 'planned';
  experiments: Record<string, unknown>[];
  recentRuns: Record<string, unknown>[];
  recentJobs: Record<string, unknown>[];
  validatedRuns: Record<string, unknown>[];
  warnings: string[];
  generatedAt: string;
};

export async function loadAdminAiSnapshot(language: AppLanguage = 'en'): Promise<AdminAiSnapshot> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error || new Error('Sign in to view AI intelligence.');
  const response = await fetch('/api/admin-ai', { headers: { Authorization: `Bearer ${data.session.access_token}` }, cache: 'no-store' });
  const payload = await response.json() as AdminAiSnapshot & { error?: string };
  if (!response.ok) throw new Error(localizeAdminError(payload.error || 'AI intelligence could not be loaded.', language));
  return payload;
}
