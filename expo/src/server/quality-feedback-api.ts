export const feedbackJson = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });

export async function authorizeQualityFeedback(request: Request): Promise<{ base: string; serverKey: string; userId: string } | { error: Response }> {
  const base = (process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '').replace(/\/$/, '');
  const anonKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  const token = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
  if (!base || !anonKey || !serverKey) return { error: feedbackJson({ error: 'Quality feedback is unavailable.' }, 503) };
  if (!token) return { error: feedbackJson({ error: 'Sign in to give feedback.' }, 401) };
  const response = await fetch(`${base}/auth/v1/user`, { headers: { apikey: anonKey, Authorization: `Bearer ${token}` }, cache: 'no-store' });
  if (!response.ok) return { error: feedbackJson({ error: 'Your Classio session has expired.' }, 401) };
  const user = await response.json() as { id?: string };
  if (!user.id) return { error: feedbackJson({ error: 'Your Classio session has expired.' }, 401) };
  return { base, serverKey, userId: user.id };
}

export function adminHeaders(serverKey: string, preference?: string): HeadersInit {
  return { apikey: serverKey, Authorization: `Bearer ${serverKey}`, Accept: 'application/json', 'Content-Type': 'application/json', ...(preference ? { Prefer: preference } : {}) };
}

export async function readRows(base: string, serverKey: string, table: string, filters: Record<string, string>, select: string, limit = 1): Promise<Record<string, unknown>[]> {
  const url = new URL(`${base}/rest/v1/${table}`);
  url.searchParams.set('select', select);
  Object.entries(filters).forEach(([name, value]) => url.searchParams.set(name, value));
  url.searchParams.set('limit', String(limit));
  const response = await fetch(url, { headers: adminHeaders(serverKey), cache: 'no-store' });
  if (!response.ok) throw new Error(`${table} read failed: ${response.status}`);
  return await response.json() as Record<string, unknown>[];
}

export async function upsertRow(base: string, serverKey: string, table: string, conflict: string, value: Record<string, unknown>): Promise<Record<string, unknown>> {
  const url = new URL(`${base}/rest/v1/${table}`);
  url.searchParams.set('on_conflict', conflict);
  const response = await fetch(url, { method: 'POST', headers: adminHeaders(serverKey, 'resolution=merge-duplicates,return=representation'), body: JSON.stringify(value), cache: 'no-store' });
  if (!response.ok) throw new Error(`${table} write failed: ${response.status}`);
  const rows = await response.json() as Record<string, unknown>[];
  if (rows.length !== 1) throw new Error(`${table} write was not confirmed`);
  return rows[0];
}

export async function insertRow(base: string, serverKey: string, table: string, value: Record<string, unknown>): Promise<void> {
  const response = await fetch(`${base}/rest/v1/${table}`, { method: 'POST', headers: adminHeaders(serverKey), body: JSON.stringify(value), cache: 'no-store' });
  if (!response.ok) throw new Error(`${table} write failed: ${response.status}`);
}
