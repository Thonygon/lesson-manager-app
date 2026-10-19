import { createClient } from '@supabase/supabase-js';

const respond = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
const roles = new Set(['teacher', 'student', 'admin']);
const statuses = new Set(['free', 'active', 'trialing', 'past_due', 'canceled', 'cancelled', 'expired']);

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return respond({ error: 'Sign in to manage access.' }, 401);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return respond({ error: 'Admin access management is not configured.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return respond({ error: 'Your session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: actor, error: actorError } = await server.from('profiles').select('role').eq('user_id', identity.user.id).maybeSingle();
    if (actorError) throw actorError;
    if (actor?.role !== 'admin') return respond({ error: 'Admin access is required.' }, 403);
    const input = await request.json().catch(() => null) as Record<string, unknown> | null;
    const targetId = String(input?.userId || '').trim();
    const role = String(input?.role || '').trim().toLowerCase();
    const planId = String(input?.planId || '').trim();
    const status = String(input?.subscriptionStatus || '').trim().toLowerCase();
    const canTeach = input?.canTeach;
    if (!targetId || targetId.length > 100 || !roles.has(role) || !planId || planId.length > 80 || !statuses.has(status) || typeof canTeach !== 'boolean') return respond({ error: 'Choose valid account access settings.' }, 400);
    if (targetId === identity.user.id && role !== 'admin') return respond({ error: 'An admin cannot remove their own admin access here.' }, 400);
    const [{ data: target, error: targetError }, { data: plan, error: planError }] = await Promise.all([
      server.from('profiles').select('user_id').eq('user_id', targetId).maybeSingle(),
      server.from('plans').select('id,active').eq('id', planId).maybeSingle(),
    ]);
    if (targetError || planError) throw targetError || planError;
    if (!target || !plan || plan.active === false) return respond({ error: 'The account or plan is unavailable.' }, 404);
    const now = new Date().toISOString();
    const { error: subscriptionError } = await server.from('user_subscriptions').upsert({ user_id: targetId, plan_id: planId, subscription_status: status, manual_override: true, updated_at: now }, { onConflict: 'user_id' });
    if (subscriptionError) throw subscriptionError;
    const { error: profileError } = await server.from('profiles').update({ role, primary_role: canTeach ? 'teacher' : 'student', can_teach: canTeach, current_plan: planId, subscription_status: status }).eq('user_id', targetId);
    if (profileError) throw profileError;
    await server.from('admin_overrides').insert({ user_id: targetId, override_type: 'expo_access_assignment', reason: `role=${role}; can_teach=${canTeach}; plan=${planId}; status=${status}`, created_by: identity.user.id, created_at: now });
    return respond({ ok: true });
  } catch (error) {
    console.error('Admin access assignment failed', error);
    return respond({ error: 'Access settings could not be saved.' }, 502);
  }
}
