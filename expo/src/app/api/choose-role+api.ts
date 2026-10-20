import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to choose a workspace.' }, 401);
  const input = await request.json().catch(() => null) as { mode?: string; language?: string } | null;
  const mode = input?.mode, language = input?.language;
  if (mode !== 'teacher' && mode !== 'student') return json({ error: 'Choose teacher or student.' }, 400);
  if (!['en', 'es', 'tr'].includes(language || '')) return json({ error: 'Choose a supported language.' }, 400);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'Role selection is not configured.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: profile, error: profileError } = await server.from('profiles').select('role,login_count,onboarding_completed').eq('user_id', identity.user.id).maybeSingle();
    if (profileError) throw profileError;
    if (profile?.role === 'admin' || profile?.role === 'school_admin' || Number(profile?.login_count ?? 0) > 0 || profile?.onboarding_completed === true) return json({ error: 'This account has already selected a workspace.' }, 409);
    const { error: saveError } = await server.from('profiles').upsert({
      user_id: identity.user.id,
      email: identity.user.email || null,
      role: mode,
      primary_role: mode,
      can_teach: mode === 'teacher',
      can_study: mode === 'student',
      last_active_mode: mode,
      preferred_ui_language: language,
      login_count: 1,
    }, { onConflict: 'user_id' });
    if (saveError) throw saveError;
    return json({ ok: true });
  } catch (error) {
    console.error('Initial role selection failed', error);
    return json({ error: 'Your choice could not be saved.' }, 500);
  }
}
