import { createClient, type SupabaseClient } from '@supabase/supabase-js';

type Row = Record<string, unknown>;
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });

async function rows(client: SupabaseClient, table: string, columns: string, order: string, limit: number, ascending = false): Promise<{ rows: Row[]; warning?: string }> {
  const { data, error } = await client.from(table).select(columns).order(order, { ascending }).limit(limit);
  return error ? { rows: [] as Row[], warning: `${table}: ${error.message || 'Unable to read rows.'}` } : { rows: (data ?? []) as unknown as Row[] };
}

async function count(client: SupabaseClient, table: string, filter?: { column: string; value: string | boolean }): Promise<{ count: number | null; warning?: string }> {
  let query = client.from(table).select('*', { count: 'exact', head: true });
  if (filter) query = query.eq(filter.column, filter.value);
  const { count: total, error } = await query;
  if (table === 'classio_ai_reconciliation_cases' && ['42P01', 'PGRST205'].includes(error?.code || '')) return { count: null };
  return error ? { count: null, warning: `${table}: ${error.message || 'Unable to count rows.'}` } : { count: total ?? 0 };
}

export async function GET(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to manage Classio.' }, 401);
  const section = new URL(request.url).searchParams.get('section');
  if (!['accounts', 'staff', 'payments', 'explorer', 'audit', 'platform', 'resourcesA', 'resourcesB'].includes(section || '')) return json({ error: 'Choose an admin data section.' }, 400);
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
      const [profiles, subscriptions, plans, authUsers] = await Promise.all([
        rows(server, 'profiles', 'user_id,email,display_name,role,primary_role,current_plan,subscription_status,created_at,account_status,admin_notes,login_count,last_active_mode,active_student_count,can_teach,can_study', 'created_at', 500),
        rows(server, 'user_subscriptions', 'user_id,plan_id,subscription_status,provider_customer_id,manual_override,updated_at', 'updated_at', 500),
        rows(server, 'plans', '*', 'id', 100, true),
        server.auth.admin.listUsers({ page: 1, perPage: 500 }).catch(() => null),
      ]);
      const lastSignIn = new Map((authUsers?.data?.users || []).map((user) => [user.id, user.last_sign_in_at || null]));
      const profilesWithActivity = { ...profiles, rows: profiles.rows.map((row) => ({ ...row, last_used_at: lastSignIn.get(String(row.user_id)) || null })) };
      return json({ profiles: profilesWithActivity, subscriptions, plans, warnings: [profiles.warning, subscriptions.warning, plans.warning, authUsers?.error ? `auth.users: ${authUsers.error.message}` : '', profiles.rows.length === 500 ? 'profiles: showing the latest 500 accounts; total count is shown separately.' : '', subscriptions.rows.length === 500 ? 'user_subscriptions: showing the latest 500 subscriptions.' : ''].filter(Boolean) });
    }
    if (section === 'platform') {
      const [profiles, subscriptions, paymentEvents, aiUsage, aiOperations, providerAttempts, pendingAiOperations, attemptsMissingUsage, reconciliationCases, pdfExportEvents, wordExportEvents, failedExportEvents, pendingExportEvents] = await Promise.all([
        ...['profiles', 'user_subscriptions', 'payment_events', 'ai_usage_logs', 'classio_ai_operations', 'classio_provider_attempts'].map((table) => count(server, table)),
        count(server, 'classio_ai_operations', { column: 'status', value: 'started' }),
        count(server, 'classio_provider_attempts', { column: 'usage_observed', value: false }),
        count(server, 'classio_ai_reconciliation_cases', { column: 'review_state', value: 'unknown' }),
        count(server, 'classio_document_export_events', { column: 'format', value: 'pdf' }),
        count(server, 'classio_document_export_events', { column: 'format', value: 'docx' }),
        count(server, 'classio_document_export_events', { column: 'status', value: 'failed' }),
        count(server, 'classio_document_export_events', { column: 'status', value: 'started' }),
      ]);
      const resourceLinkCoverage = await rows(server, 'classio_ai_resource_link_coverage', 'feature_name,successful_operations,linked_resources,unlinked_operations,latest_finished_at', 'feature_name', 3, true);
      const [programGenerationLinks, programSkeletonLinks, coverGenerationLinks] = await Promise.all([
        count(server, 'classio_program_generation_operations'),
        server.from('classio_program_generation_operations').select('*', { count: 'exact', head: true }).is('unit_number', null),
        count(server, 'classio_cover_generation_resources'),
      ]);
      const programSkeletonCount = programSkeletonLinks.error ? null : programSkeletonLinks.count ?? 0;
      const linkTotals = resourceLinkCoverage.warning ? null : resourceLinkCoverage.rows.reduce<{ successfulOperations: number; linkedResources: number; unlinkedOperations: number }>((totals, row) => ({
        successfulOperations: totals.successfulOperations + Number(row.successful_operations || 0),
        linkedResources: totals.linkedResources + Number(row.linked_resources || 0),
        unlinkedOperations: totals.unlinkedOperations + Number(row.unlinked_operations || 0),
      }), { successfulOperations: 0, linkedResources: 0, unlinkedOperations: 0 });
      return json({ platformCounts: { profiles: profiles.count, subscriptions: subscriptions.count, paymentEvents: paymentEvents.count, aiUsage: aiUsage.count, aiOperations: aiOperations.count, providerAttempts: providerAttempts.count, pendingAiOperations: pendingAiOperations.count, attemptsMissingUsage: attemptsMissingUsage.count, reconciliationCases: reconciliationCases.count, linkedAiResources: linkTotals?.linkedResources ?? null, linkedImageCovers: coverGenerationLinks.count, unlinkedAiOperations: linkTotals?.unlinkedOperations ?? null, linkEligibleAiOperations: linkTotals?.successfulOperations ?? null, programSkeletonLinks: programSkeletonCount, programUnitLinks: programGenerationLinks.count == null || programSkeletonCount == null ? null : programGenerationLinks.count - programSkeletonCount, pdfExportEvents: pdfExportEvents.count, wordExportEvents: wordExportEvents.count, failedExportEvents: failedExportEvents.count, pendingExportEvents: pendingExportEvents.count }, warnings: [profiles.warning, subscriptions.warning, paymentEvents.warning, aiUsage.warning, aiOperations.warning, providerAttempts.warning, pendingAiOperations.warning, attemptsMissingUsage.warning, reconciliationCases.warning, resourceLinkCoverage.warning, programGenerationLinks.warning, coverGenerationLinks.warning, programSkeletonLinks.error ? `classio_program_generation_operations: ${programSkeletonLinks.error.message}` : '', pdfExportEvents.warning, wordExportEvents.warning, failedExportEvents.warning, pendingExportEvents.warning].filter(Boolean) });
    }
    if (section === 'resourcesA') {
      const [worksheets, exams, lessonPlans] = await Promise.all(['worksheets', 'quick_exams', 'lesson_plans'].map((table) => count(server, table)));
      return json({ contentCounts: { worksheets: worksheets.count, exams: exams.count, lessonPlans: lessonPlans.count }, warnings: [worksheets.warning, exams.warning, lessonPlans.warning].filter(Boolean) });
    }
    if (section === 'resourcesB') {
      const [videos, learningPrograms] = await Promise.all(['videos', 'learning_programs'].map((table) => count(server, table)));
      return json({ contentCounts: { videos: videos.count, learningPrograms: learningPrograms.count }, warnings: [videos.warning, learningPrograms.warning].filter(Boolean) });
    }
    if (section === 'staff') {
      const staffRoles = await rows(server, 'user_staff_roles', 'id,user_id,role_key,is_active,assigned_by,assigned_at,revoked_by,revoked_at,assignment_reason', 'assigned_at', 250);
      return json({ staffRoles, warnings: [staffRoles.warning].filter(Boolean) });
    }
    if (section === 'explorer') {
      const explorerMoves = await rows(server, 'explorer_moves', 'id,resource_type,tool_key,title,subject,topic,preview_text,anonymous_session_id,learner_stage,level_or_band,language,status,published_table,published_record_id,created_at,updated_at', 'created_at', 500);
      return json({ explorerMoves, warnings: [explorerMoves.warning].filter(Boolean) });
    }
    const paymentEvents = await rows(server, 'payment_events', 'id,provider,event_type,processed,created_at', 'created_at', 100);
    if (section === 'payments') return json({ paymentEvents, warnings: [paymentEvents.warning].filter(Boolean) });
    const overrides = await rows(server, 'admin_overrides', 'id,user_id,override_type,reason,created_by,expires_at,created_at', 'created_at', 100);
    return json({ paymentEvents, overrides, warnings: [paymentEvents.warning, overrides.warning].filter(Boolean) });
  } catch (error) {
    console.error('Admin workspace load failed', { section, error });
    return json({ error: error instanceof Error ? error.message : 'Admin data could not be loaded.' }, 500);
  }
}
