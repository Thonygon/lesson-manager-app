import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
export async function GET(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  const id = Number(new URL(request.url).searchParams.get('id'));
  if (!token) return json({ error: 'Sign in to inspect Explorer moves.' }, 401);
  if (!Number.isInteger(id) || id < 1) return json({ error: 'Choose a valid Explorer move.' }, 400);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'Admin Explorer access is not configured.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: actor, error: actorError } = await server.from('profiles').select('role').eq('user_id', identity.user.id).maybeSingle();
    if (actorError) throw actorError;
    if (actor?.role !== 'admin') return json({ error: 'Admin access is required.' }, 403);
    const { data: move, error } = await server.from('explorer_moves').select('id,resource_type,title,meta_json,payload_json,status,admin_notes,updated_at').eq('id', id).maybeSingle();
    if (error) throw error;
    if (!move) return json({ error: 'Explorer move not found.' }, 404);
    return json({ move });
  } catch (error) { console.error('Admin Explorer preview failed', error); return json({ error: 'The Explorer preview could not be loaded.' }, 502); }
}
