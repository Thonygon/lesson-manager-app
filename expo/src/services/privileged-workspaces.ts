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
  platformCounts: Record<string, number>;
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

function warnings(results: WorkspaceResult[], more: string[] = []) {
  return [...results.map((result) => result.warning).filter((item): item is string => Boolean(item)), ...more.filter(Boolean)];
}

export async function loadAdminWorkspace(): Promise<AdminWorkspaceData> {
  const client = requireSupabase();
  const { data: session } = await client.auth.getSession();
  if (!session.session) throw new Error('Admin access requires an authenticated account.');
  const sections = ['accounts', 'platform', 'resourcesA', 'resourcesB', 'operations'];
  const results = await Promise.all(sections.map(async (section) => {
    const response = await fetch(`/api/admin-workspace?section=${section}`, { headers: { Authorization: `Bearer ${session.session!.access_token}` }, cache: 'no-store' });
    const result = await response.json().catch(() => ({})) as Partial<AdminWorkspaceData> & { error?: string };
    if (!response.ok) throw new Error(`${section}: ${result.error || 'Admin data could not be loaded.'}`);
    return result;
  }));
  const [accounts, platform, resourcesA, resourcesB, operations] = results;
  if (!accounts.profiles || !accounts.subscriptions || !accounts.plans || !platform.platformCounts || !resourcesA.contentCounts || !resourcesB.contentCounts || !operations.paymentEvents || !operations.overrides || !operations.staffRoles || !operations.explorerMoves) throw new Error('Admin data is incomplete. Refresh and try again.');
  return {
    profiles: accounts.profiles, subscriptions: accounts.subscriptions, plans: accounts.plans,
    paymentEvents: operations.paymentEvents, overrides: operations.overrides, staffRoles: operations.staffRoles, explorerMoves: operations.explorerMoves,
    contentCounts: { ...resourcesA.contentCounts, ...resourcesB.contentCounts }, platformCounts: platform.platformCounts,
    warnings: accounts.warnings || [],
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
