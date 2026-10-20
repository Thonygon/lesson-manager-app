import { requireSupabase } from '@/lib/supabase';
import { pythonModelApiUrl } from '@/services/python-models';
import { Platform } from 'react-native';

export type AdminEic = {
  summary: Record<string, unknown>;
  portfolio: Record<string, unknown>[];
  validated_runs: Record<string, unknown>[];
  telemetry: { summary: Record<string, unknown>; by_surface: Record<string, unknown>[] };
  decisions: Record<string, unknown>[];
  trend: Record<string, unknown>;
  business_detail: Record<string, unknown>;
  academic_evidence: Record<string, unknown>;
  reports: Record<string, unknown>[];
};

let eicCache: { key: string; value: AdminEic; expires: number } | null = null;
let eicPending: { key: string; request: Promise<AdminEic> } | null = null;
export function invalidateAdminEic() { eicCache = null; }

export async function loadAdminEic(language: 'en' | 'es' | 'tr'): Promise<AdminEic> {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session?.access_token) throw new Error('Your Classio session has expired.');
  const key = `${data.session.user.id}:${language}`;
  if (eicCache?.key === key && eicCache.expires > Date.now()) return eicCache.value;
  if (eicPending?.key === key) return eicPending.request;
  const request = (async () => {
    const response = await fetch(`${pythonModelApiUrl()}/v1/admin/intelligence?language=${language}`, { headers: { Authorization: `Bearer ${data.session.access_token}` } });
    if (!response.ok) throw new Error(`Educational Intelligence Center unavailable (${response.status}).`);
    const value = await response.json() as AdminEic;
    eicCache = { key, value, expires: Date.now() + 60_000 };
    return value;
  })();
  eicPending = { key, request };
  try { return await request; } finally { if (eicPending?.request === request) eicPending = null; }
}

export async function downloadAdminEicReport(language: 'en' | 'es' | 'tr'): Promise<void> {
  if (Platform.OS !== 'web' || typeof document === 'undefined') throw new Error('Download unavailable on this device.');
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session?.access_token) throw new Error('Your Classio session has expired.');
  const response = await fetch(`${pythonModelApiUrl()}/v1/admin/intelligence/reports/experiment_docx?language=${language}`, { headers: { Authorization: `Bearer ${data.session.access_token}` } });
  if (!response.ok) throw new Error(response.status === 404 ? 'The validated report has not been prepared.' : `Report download failed (${response.status}).`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `classio-validated-evidence-${language}.docx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
