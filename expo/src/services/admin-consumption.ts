import { requireSupabase } from '@/lib/supabase';

export type ConsumptionPeriod = { label: 'month' | 'year' | 'all'; delivered_resources: number; quota_used: number; ai_operations: number; failed_operations: number; refinements: number; program_unit_events: number; image_events: number; provider_attempts: number; pdf_handoffs: number; word_handoffs: number; failed_exports: number };
export type ConsumptionDetail = { account: Record<string, unknown>; subscription: Record<string, unknown> | null; staffRoles: Record<string, unknown>[]; summary: { as_of: string; timezone: string; periods: ConsumptionPeriod[] }; operations: Record<string, unknown>[]; exports: Record<string, unknown>[] };

async function request(path: string): Promise<Record<string, unknown>> {
  const { data } = await requireSupabase().auth.getSession();
  if (!data.session) throw new Error('Admin session expired.');
  const response = await fetch(path, { headers: { Authorization: `Bearer ${data.session.access_token}` }, cache: 'no-store' });
  const result = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error(String(result.error || 'Account usage could not be loaded.'));
  return result;
}

export async function searchAdminAccounts(query: string): Promise<Record<string, unknown>[]> {
  if (query.trim().length < 2) return [];
  const result = await request(`/api/admin-consumption?q=${encodeURIComponent(query.trim())}`);
  return Array.isArray(result.accounts) ? result.accounts as Record<string, unknown>[] : [];
}

export async function getAdminConsumption(userId: string): Promise<ConsumptionDetail> {
  return await request(`/api/admin-consumption?userId=${encodeURIComponent(userId)}`) as ConsumptionDetail;
}

export type CountryVisits = { code: string; sessions: number };
export async function getAdminGeography(): Promise<{ asOf: string; countries: CountryVisits[] }> {
  return await request('/api/admin-consumption?view=geography') as { asOf: string; countries: CountryVisits[] };
}
