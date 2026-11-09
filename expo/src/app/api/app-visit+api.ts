import { createClient } from '@supabase/supabase-js';
import { appVisitCountry } from '@/server/app-visit-country';

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return new Response(null, { status: 401 });
  const base = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!base || !publicKey || !serverKey) return new Response(null, { status: 503 });
  const country = appVisitCountry(request);
  const eventId = String((await request.json().catch(() => ({})) as { eventId?: unknown }).eventId || '');
  if (!/^[A-Z]{2}$/.test(country) || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(eventId)) return new Response(null, { status: 400 });
  try {
    const identityClient = createClient(base, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: authError } = await identityClient.auth.getUser(token);
    if (authError || !identity.user) return new Response(null, { status: 401 });
    const server = createClient(base, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { error } = await server.rpc('classio_record_app_visit', { p_actor: identity.user.id, p_event: eventId, p_country: country });
    if (error) throw error;
    return new Response(null, { status: 204 });
  } catch (error) {
    console.error('App visit count failed', error instanceof Error ? error.message : 'unknown');
    return new Response(null, { status: 503 });
  }
}
