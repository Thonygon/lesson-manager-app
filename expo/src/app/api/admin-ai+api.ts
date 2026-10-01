import { createClient } from '@supabase/supabase-js';

const noStore = { 'Cache-Control': 'private, no-store', Vary: 'Authorization' };
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: noStore });

export async function GET(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to view AI intelligence.' }, 401);

  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publishableKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publishableKey) return json({ error: 'The protected platform-data service is not configured.' }, 503);

  try {
    const publicClient = createClient(url, publishableKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your Classio session has expired.' }, 401);
    if (!serverKey) return json({ error: 'The protected platform-data service is not configured.' }, 503);

    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: profile, error: profileError } = await server.from('profiles').select('role').eq('user_id', identity.user.id).limit(1).maybeSingle();
    if (profileError) throw profileError;
    if (profile?.role !== 'admin') return json({ error: 'Admin access is required.' }, 403);

    // Planned counts avoid loading platform-wide rows into the server or browser.
    const contentTables = ['worksheets', 'quick_exams', 'lesson_plans', 'videos', 'learning_programs'] as const;
    const [counts, experiments, runs, jobs] = await Promise.all([
      Promise.all(contentTables.map(async (table) => {
        const { count, error } = await server.from(table).select('id', { count: 'planned', head: true });
        return { table, count: count ?? null, error: error?.message || '' };
      })),
      server.from('ml_experiments').select('experiment_id,name,is_active,updated_at').order('updated_at', { ascending: false }).limit(20),
      server.from('ml_experiment_runs').select('run_id,experiment_id,run_status,integrity_status,created_at').order('created_at', { ascending: false }).limit(24),
      server.from('system_jobs').select('job_id,job_type,status,created_at').order('created_at', { ascending: false }).limit(24),
    ]);
    const errors = [
      ...counts.filter((row) => row.error).map((row) => `${row.table}: ${row.error}`),
      experiments.error?.message, runs.error?.message, jobs.error?.message,
    ].filter(Boolean);
    return json({
      contentCounts: Object.fromEntries(counts.map((row) => [row.table, row.count])),
      countMethod: 'planned',
      experiments: experiments.data || [],
      recentRuns: runs.data || [],
      recentJobs: jobs.data || [],
      warnings: errors,
      generatedAt: new Date().toISOString(),
    });
  } catch (reason) {
    console.error('Admin AI snapshot failed', reason);
    return json({ error: 'AI intelligence could not be loaded.' }, 502);
  }
}
