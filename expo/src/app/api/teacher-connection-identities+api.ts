import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
type Identity = { name: string; email: string; phone: string };

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to view teacher connection requests.' }, 401);
  const input = await request.json().catch(() => null) as { linkIds?: unknown } | null;
  const ids = Array.isArray(input?.linkIds) ? input.linkIds : [];
  if (!ids.length || ids.length > 1000 || ids.some((id) => !Number.isSafeInteger(Number(id)) || Number(id) <= 0)) return json({ error: 'Choose valid teacher connection requests.' }, 400);
  const linkIds = [...new Set(ids.map(Number))];
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'The protected connection service is unavailable.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: auth, error: authError } = await publicClient.auth.getUser(token);
    if (authError || !auth.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: links, error: linkError } = await server.from('teacher_student_links').select('id,student_id').eq('teacher_id', auth.user.id).in('id', linkIds);
    if (linkError) throw linkError;
    if (links?.length !== linkIds.length) return json({ error: 'A teacher connection is unavailable.' }, 403);
    const studentIds = [...new Set(links.map((link) => String(link.student_id)))];
    const { data: profiles, error: profileError } = await server.from('profiles').select('user_id,display_name,username,email,phone_number').in('user_id', studentIds);
    if (profileError) throw profileError;
    const profileById = new Map((profiles ?? []).map((profile) => [String(profile.user_id), profile]));
    const identities: Record<string, Identity> = {};
    for (const link of links) {
      const profile = profileById.get(String(link.student_id));
      // A pending request with an incomplete profile still has a verified Auth email.
      // Resolve it only for the teacher who owns this exact request.
      let authEmail = '';
      let authName = '';
      if (!profile?.email || (!profile?.display_name && !profile?.username)) {
        const { data: studentAuth, error: studentError } = await server.auth.admin.getUserById(String(link.student_id));
        if (studentError) throw studentError;
        authEmail = String(studentAuth.user?.email || '');
        authName = String(studentAuth.user?.user_metadata?.full_name || studentAuth.user?.user_metadata?.name || '');
      }
      const email = String(profile?.email || authEmail).trim();
      const name = String(profile?.display_name || profile?.username || authName || email.split('@')[0] || '').trim();
      if (!name && !email) return json({ error: 'A student profile is unavailable. Try again later.' }, 503);
      identities[String(link.id)] = { name, email, phone: String(profile?.phone_number || '').trim() };
    }
    return json({ identities });
  } catch (error) {
    console.error('Teacher connection identity lookup failed', error);
    return json({ error: 'Student connection details could not be loaded.' }, 502);
  }
}
