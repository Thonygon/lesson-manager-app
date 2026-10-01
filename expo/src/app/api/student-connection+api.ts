import { createClient } from '@supabase/supabase-js';

const headers = { 'Cache-Control': 'private, no-store', Vary: 'Authorization' };
const json = (body: unknown, status = 200) => Response.json(body, { status, headers });

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to manage your teacher connections.' }, 401);
  const body = await request.json().catch(() => null) as { linkId?: unknown } | null;
  const linkId = Number(body?.linkId);
  if (!Number.isSafeInteger(linkId) || linkId <= 0) return json({ error: 'A valid connection is required.' }, 400);

  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'The protected connection service is not configured.' }, 503);

  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your Classio session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: link, error: lookupError } = await server.from('teacher_student_links').select('id,status').eq('id', linkId).eq('student_id', identity.user.id).limit(1).maybeSingle();
    if (lookupError) throw lookupError;
    if (!link) return json({ error: 'This teacher connection is unavailable.' }, 404);
    if (!['pending', 'active', 'archived'].includes(link.status)) return json({ error: 'This teacher connection cannot be ended.' }, 409);
    const now = new Date().toISOString();
    // Repeat the scope update on retries after a partial failure.
    if (link.status !== 'archived') {
      const { error } = await server.from('teacher_student_links').update({ status: 'archived', archived_at: now, updated_at: now }).eq('id', linkId).eq('student_id', identity.user.id);
      if (error) throw error;
    }
    const { error: scopeError } = await server.from('teacher_student_subjects').update({ status: 'archived', deactivated_at: now, updated_at: now }).eq('link_id', linkId).eq('student_id', identity.user.id).eq('status', 'active');
    if (scopeError) throw scopeError;
    return json({ status: 'archived' });
  } catch (reason) {
    console.error('Student connection archive failed', reason);
    return json({ error: 'The teacher connection could not be ended.' }, 502);
  }
}
