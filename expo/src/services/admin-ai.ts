import { requireSupabase } from '@/lib/supabase';

export type AdminAiSnapshot = {
  contentCounts: Record<string, number | null>;
  countMethod: 'planned';
  experiments: Record<string, unknown>[];
  recentRuns: Record<string, unknown>[];
  recentJobs: Record<string, unknown>[];
  warnings: string[];
  generatedAt: string;
};

export async function loadAdminAiSnapshot(): Promise<AdminAiSnapshot> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error || new Error('Sign in to view AI intelligence.');
  const response = await fetch('/api/admin-ai', { headers: { Authorization: `Bearer ${data.session.access_token}` }, cache: 'no-store' });
  const payload = await response.json() as AdminAiSnapshot & { error?: string };
  if (!response.ok) throw new Error(payload.error || 'AI intelligence could not be loaded.');
  return payload;
}
