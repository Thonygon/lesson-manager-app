import { requireSupabase } from '@/lib/supabase';

export type DataRow = Record<string, unknown>;

export type WorkspaceResult = {
  rows: DataRow[];
  warning?: string;
};

export type AdminWorkspaceData = {
  profiles: WorkspaceResult;
  subscriptions: WorkspaceResult;
  plans: WorkspaceResult;
  paymentEvents: WorkspaceResult;
  overrides: WorkspaceResult;
  staffRoles: WorkspaceResult;
  explorerMoves: WorkspaceResult;
  contentCounts: Record<string, number>;
  warnings: string[];
};

export type DeveloperWorkspaceData = {
  experiments: WorkspaceResult;
  runs: WorkspaceResult;
  models: WorkspaceResult;
  artifacts: WorkspaceResult;
  jobs: WorkspaceResult;
  audit: WorkspaceResult;
  diagnostics: WorkspaceResult;
  recommendationEvents: WorkspaceResult;
  warnings: string[];
};

function message(reason: unknown) {
  if (reason && typeof reason === 'object' && 'message' in reason && String(reason.message || '').trim()) return String(reason.message);
  return String(reason || '').trim() || 'Unavailable under the current database access policy.';
}

async function readRows(
  table: string,
  columns = '*',
  options: { order?: string; ascending?: boolean; limit?: number } = {},
): Promise<WorkspaceResult> {
  try {
    const client = requireSupabase();
    let query = client.from(table).select(columns);
    if (options.order) query = query.order(options.order, { ascending: options.ascending ?? false });
    const { data, error } = await query.limit(options.limit ?? 500);
    if (error) throw error;
    return { rows: (data ?? []) as unknown as DataRow[] };
  } catch (reason) {
    return { rows: [], warning: `${table}: ${message(reason)}` };
  }
}

async function countRows(table: string) {
  try {
    const { count, error } = await requireSupabase().from(table).select('*', { count: 'exact', head: true });
    if (error) throw error;
    return { count: count ?? 0, warning: '' };
  } catch (reason) {
    return { count: 0, warning: `${table}: ${message(reason)}` };
  }
}

function warnings(results: WorkspaceResult[], more: string[] = []) {
  return [...results.map((result) => result.warning).filter((item): item is string => Boolean(item)), ...more.filter(Boolean)];
}

export async function loadAdminWorkspace(): Promise<AdminWorkspaceData> {
  const client = requireSupabase();
  const { data: auth } = await client.auth.getUser();
  if (!auth.user) throw new Error('Admin access requires an authenticated account.');
  const { data: profile, error: profileError } = await client.from('profiles').select('role').eq('user_id', auth.user.id).maybeSingle();
  if (profileError || profile?.role !== 'admin') throw new Error('Admin access is required for this workspace.');

  const [profiles, subscriptions, plans, paymentEvents, overrides, staffRoles, explorerMoves, ...counts] = await Promise.all([
    readRows('profiles', 'user_id,email,display_name,role,primary_role,current_plan,subscription_status,created_at,account_status,login_count,last_active_mode,active_student_count,can_teach,can_study', { order: 'created_at', limit: 500 }),
    readRows('user_subscriptions', 'user_id,plan_id,subscription_status,provider_customer_id,manual_override,updated_at', { order: 'updated_at', limit: 500 }),
    readRows('plans', '*', { order: 'id', ascending: true, limit: 100 }),
    readRows('payment_events', 'id,provider,event_type,processed,created_at', { order: 'created_at', limit: 100 }),
    readRows('admin_overrides', 'id,user_id,override_type,reason,created_by,expires_at,created_at', { order: 'created_at', limit: 100 }),
    readRows('user_staff_roles', 'id,user_id,role_key,is_active,assigned_by,assigned_at,revoked_at,assignment_reason', { order: 'assigned_at', limit: 250 }),
    readRows('explorer_moves', 'id,resource_type,tool_key,title,subject,topic,learner_stage,level_or_band,language,status,published_table,published_record_id,created_at,updated_at', { order: 'created_at', limit: 250 }),
    ...['worksheets', 'quick_exams', 'lesson_plans', 'videos', 'learning_programs'].map(countRows),
  ]);
  const names = ['worksheets', 'exams', 'lessonPlans', 'videos', 'learningPrograms'];
  const contentCounts = Object.fromEntries(names.map((name, index) => [name, counts[index].count]));
  return {
    profiles, subscriptions, plans, paymentEvents, overrides, staffRoles, explorerMoves, contentCounts,
    warnings: warnings([profiles, subscriptions, plans, paymentEvents, overrides, staffRoles, explorerMoves], counts.map((item) => item.warning)),
  };
}

export async function loadDeveloperWorkspace(): Promise<DeveloperWorkspaceData> {
  const client = requireSupabase();
  const { data: auth } = await client.auth.getUser();
  if (!auth.user) throw new Error('Developer access requires an authenticated account.');
  const { data: roles, error: rolesError } = await client.from('user_staff_roles').select('role_key').eq('user_id', auth.user.id).eq('is_active', true);
  if (rolesError) throw rolesError;
  const allowed = (roles ?? []).some((row) => row.role_key === 'developer' || row.role_key === 'data_scientist');
  if (!allowed) throw new Error('Developer or data scientist access is required for this workspace.');

  const [experiments, runs, models, artifacts, jobs, audit, diagnostics, recommendationEvents] = await Promise.all([
    readRows('ml_experiments', '*', { order: 'updated_at', limit: 250 }),
    readRows('ml_experiment_runs', '*', { order: 'created_at', limit: 500 }),
    readRows('ml_run_models', '*', { order: 'created_at', limit: 500 }),
    readRows('ml_run_artifacts', '*', { order: 'created_at', limit: 500 }),
    readRows('system_jobs', '*', { order: 'created_at', limit: 500 }),
    readRows('privileged_action_audit_log', '*', { order: 'created_at', limit: 500 }),
    readRows('application_diagnostic_events', '*', { order: 'last_seen_at', limit: 500 }),
    readRows('learning_program_recommendation_events', '*', { order: 'created_at', limit: 1000 }),
  ]);
  const all = [experiments, runs, models, artifacts, jobs, audit, diagnostics, recommendationEvents];
  return { experiments, runs, models, artifacts, jobs, audit, diagnostics, recommendationEvents, warnings: warnings(all) };
}
