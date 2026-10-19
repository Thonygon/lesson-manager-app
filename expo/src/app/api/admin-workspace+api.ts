import { createClient, type SupabaseClient } from '@supabase/supabase-js';

type Row = Record<string, unknown>;
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });

async function rows(client: SupabaseClient, table: string, columns: string, order: string, limit: number, ascending = false) {
  const { data, error } = await client.from(table).select(columns).order(order, { ascending }).limit(limit);
  if (error) throw new Error(`${table}: ${error.message}`);
  return { rows: (data ?? []) as unknown as Row[] };
}

async function count(client: SupabaseClient, table: string) {
  const { count: total, error } = await client.from(table).select('*', { count: 'exact', head: true });
  if (error) throw new Error(`${table}: ${error.message}`);
  return total ?? 0;
}

export async function GET(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to manage Classio.' }, 401);
  const section = new URL(request.url).searchParams.get('section');
  if (!['accounts', 'platform', 'resourcesA', 'resourcesB', 'operations'].includes(section || '')) return json({ error: 'Choose an admin data section.' }, 400);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'Admin data access is not configured.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: actor, error: actorError } = await server.from('profiles').select('role').eq('user_id', identity.user.id).maybeSingle();
    if (actorError) throw actorError;
    if (actor?.role !== 'admin') return json({ error: 'Admin access is required.' }, 403);

    if (section === 'accounts') {
      const [profiles, subscriptions, plans] = await Promise.all([
        rows(server, 'profiles', 'user_id,email,display_name,role,primary_role,current_plan,subscription_status,created_at,account_status,admin_notes,login_count,last_active_mode,active_student_count,can_teach,can_study', 'created_at', 1000),
        rows(server, 'user_subscriptions', 'user_id,plan_id,subscription_status,provider_customer_id,manual_override,updated_at', 'updated_at', 1000),
        rows(server, 'plans', '*', 'id', 100, true),
      ]);
      return json({ profiles, subscriptions, plans, warnings: profiles.rows.length === 1000 ? ['profiles: showing the latest 1,000 accounts; total count is shown separately.'] : [] });
    }
    if (section === 'platform') {
      const [profiles, subscriptions, paymentEvents] = await Promise.all(['profiles', 'user_subscriptions', 'payment_events'].map((table) => count(server, table)));
      return json({ platformCounts: { profiles, subscriptions, paymentEvents } });
    }
    if (section === 'resourcesA') {
      const [worksheets, exams, lessonPlans] = await Promise.all(['worksheets', 'quick_exams', 'lesson_plans'].map((table) => count(server, table)));
      return json({ contentCounts: { worksheets, exams, lessonPlans } });
    }
    if (section === 'resourcesB') {
      const [videos, learningPrograms] = await Promise.all(['videos', 'learning_programs'].map((table) => count(server, table)));
      return json({ contentCounts: { videos, learningPrograms } });
    }
    const [paymentEvents, overrides, staffRoles, explorerMoves] = await Promise.all([
      rows(server, 'payment_events', 'id,provider,event_type,processed,created_at', 'created_at', 100),
      rows(server, 'admin_overrides', 'id,user_id,override_type,reason,created_by,expires_at,created_at', 'created_at', 100),
      rows(server, 'user_staff_roles', 'id,user_id,role_key,is_active,assigned_by,assigned_at,revoked_at,assignment_reason', 'assigned_at', 250),
      rows(server, 'explorer_moves', 'id,resource_type,tool_key,title,subject,topic,learner_stage,level_or_band,language,status,published_table,published_record_id,created_at,updated_at', 'created_at', 500),
    ]);
    return json({ paymentEvents, overrides, staffRoles, explorerMoves });
  } catch (error) {
    console.error('Admin workspace load failed', { section, error });
    return json({ error: error instanceof Error ? error.message : 'Admin data could not be loaded.' }, 500);
  }
}
