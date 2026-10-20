import { createClient } from '@supabase/supabase-js';

const respond = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
const roles = new Set(['teacher', 'student', 'school_admin', 'admin']);
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
    const canStudy = input?.canStudy;
    const accountStatus = String(input?.accountStatus || 'active').trim();
    const activeMode = String(input?.activeMode || (canTeach ? 'teacher' : 'student')).trim();
    const notes = String(input?.notes || '').trim().slice(0, 1000);
    if (!targetId || targetId.length > 100 || !roles.has(role) || !planId || planId.length > 80 || !statuses.has(status) || typeof canTeach !== 'boolean' || typeof canStudy !== 'boolean' || !['active', 'suspended'].includes(accountStatus) || !['teacher', 'student', 'admin', 'developer_workspace'].includes(activeMode)) return respond({ error: 'Choose valid account access settings.' }, 400);
    if (targetId === identity.user.id && role !== 'admin') return respond({ error: 'An admin cannot remove their own admin access here.' }, 400);
    if (targetId === identity.user.id && accountStatus !== 'active') return respond({ error: 'An admin cannot suspend their own account here.' }, 400);
    if ((activeMode === 'teacher' && !canTeach) || (activeMode === 'student' && !canStudy) || (activeMode === 'admin' && role !== 'admin')) return respond({ error: 'The default workspace must be enabled for this account.' }, 400);
    if (activeMode === 'developer_workspace' && role !== 'admin') {
      const { data: staff, error: staffError } = await server.from('user_staff_roles').select('id').eq('user_id', targetId).eq('is_active', true).in('role_key', ['developer', 'data_scientist']).limit(1);
      if (staffError) throw staffError;
      if (!staff?.length) return respond({ error: 'Developer workspace requires an active staff role.' }, 400);
    }
    const [{ data: target, error: targetError }, { data: plan, error: planError }] = await Promise.all([
      server.from('profiles').select('user_id').eq('user_id', targetId).maybeSingle(),
      server.from('plans').select('id,active').eq('id', planId).maybeSingle(),
    ]);
    if (targetError || planError) throw targetError || planError;
    if (!target || !plan || plan.active === false) return respond({ error: 'The account or plan is unavailable.' }, 404);
    const now = new Date().toISOString();
    const { error: subscriptionError } = await server.from('user_subscriptions').upsert({ user_id: targetId, plan_id: planId, subscription_status: status, manual_override: true, updated_at: now }, { onConflict: 'user_id' });
    if (subscriptionError) throw subscriptionError;
    const { error: profileError } = await server.from('profiles').update({ role, primary_role: canTeach ? 'teacher' : 'student', can_teach: canTeach, can_study: canStudy, last_active_mode: activeMode, account_status: accountStatus, admin_notes: notes, current_plan: planId, subscription_status: status }).eq('user_id', targetId);
    if (profileError) throw profileError;
    const { error: auditError } = await server.from('admin_overrides').insert({ user_id: targetId, override_type: 'role_access', reason: `role=${role}; can_teach=${canTeach}; can_study=${canStudy}; mode=${activeMode}; account=${accountStatus}; plan=${planId}; status=${status}. ${notes}`, created_by: identity.user.id, created_at: now });
    if (auditError) console.error('Admin access audit write failed', auditError);
    return respond({ ok: true, audited: !auditError });
  } catch (error) {
    console.error('Admin access assignment failed', error);
    return respond({ error: 'Access settings could not be saved.' }, 502);
  }
}
