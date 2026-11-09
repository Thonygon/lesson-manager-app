import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
const uuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

export async function GET(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to manage Classio.' }, 401);
  const base = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!base || !publicKey || !serverKey) return json({ error: 'Admin data access is not configured.' }, 503);
  try {
    const identityClient = createClient(base, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: authError } = await identityClient.auth.getUser(token);
    if (authError || !identity.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(base, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: actor, error: actorError } = await server.from('profiles').select('role').eq('user_id', identity.user.id).maybeSingle();
    if (actorError) throw actorError;
    if (actor?.role !== 'admin') return json({ error: 'Admin access is required.' }, 403);
    const input = new URL(request.url).searchParams;
    if (input.get('view') === 'geography') {
      const start = new Date(); start.setUTCDate(start.getUTCDate() - 29);
      const fromDay = start.toISOString().slice(0, 10);
      const { data, error } = await server.from('classio_app_country_daily').select('visit_day,country_code,sessions').gte('visit_day', fromDay).order('visit_day', { ascending: false }).limit(6000);
      if (error) throw error;
      const countries = new Map<string, number>();
      for (const row of data || []) countries.set(row.country_code, (countries.get(row.country_code) || 0) + Number(row.sessions || 0));
      return json({ period: 'last_30_days', asOf: new Date().toISOString(), countries: [...countries].map(([code, sessions]) => ({ code, sessions })).sort((a, b) => b.sessions - a.sessions) });
    }
    const userId = input.get('userId') || '';
    if (userId) {
      if (!uuid(userId)) return json({ error: 'Choose a valid account.' }, 400);
      const [profile, subscription, staffRoles, summary, operations, exports] = await Promise.all([
        server.from('profiles').select('user_id,display_name,email,role,primary_role,can_teach,can_study,last_active_mode,account_status,current_plan,subscription_status,admin_notes,login_count,active_student_count,created_at').eq('user_id', userId).maybeSingle(),
        server.from('user_subscriptions').select('plan_id,subscription_status,manual_override').eq('user_id', userId).maybeSingle(),
        server.from('user_staff_roles').select('role_key,is_active').eq('user_id', userId),
        server.rpc('classio_admin_consumption_summary', { p_user_id: userId }),
        server.from('classio_ai_operations').select('operation_id,feature_name,modality,status,source,started_at,finished_at,error_kind,quota_eligible,quota_policy_version').eq('actor_user_id', userId).order('started_at', { ascending: false }).limit(25),
        server.from('classio_document_export_events').select('event_id,format,document_kind,variant,status,started_at,error_kind').eq('actor_user_id', userId).order('started_at', { ascending: false }).limit(15),
      ]);
      if (profile.error || subscription.error || staffRoles.error || summary.error || operations.error || exports.error) throw profile.error || subscription.error || staffRoles.error || summary.error || operations.error || exports.error;
      if (!profile.data) return json({ error: 'Account not found.' }, 404);
      const ids = (operations.data || []).map((row) => row.operation_id);
      const charges = ids.length ? await server.from('classio_smart_tool_quota_charges').select('operation_id').in('operation_id', ids) : { data: [], error: null };
      if (charges.error) throw charges.error;
      const charged = new Set((charges.data || []).map((row) => row.operation_id));
      return json({ account: profile.data, subscription: subscription.data, staffRoles: staffRoles.data || [], summary: summary.data, operations: (operations.data || []).map((row) => ({ ...row, charged: charged.has(row.operation_id) })), exports: exports.data || [] });
    }
    const query = (input.get('q') || '').trim();
    if (query.length < 2 || query.length > 100) return json({ accounts: [] });
    const { data, error } = await server.rpc('classio_admin_search_accounts', { p_query: query });
    if (error) throw error;
    return json({ accounts: data || [] });
  } catch (error) {
    console.error('Admin consumption lookup failed', error instanceof Error ? error.message : 'unknown');
    return json({ error: 'Account usage could not be loaded.' }, 503);
  }
}
