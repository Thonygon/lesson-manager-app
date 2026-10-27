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
  contentCounts: Record<string, number | null>;
  platformCounts: Record<string, number | null>;
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
  aiCases: WorkspaceResult;
  aiApprovals: WorkspaceResult;
  aiApprovalEvents: WorkspaceResult;
  fallbackEvents: WorkspaceResult;
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

type AdminSection = 'accounts' | 'staff' | 'payments' | 'explorer' | 'audit' | 'platform' | 'resourcesA' | 'resourcesB';
type AdminSectionResult = Partial<AdminWorkspaceData>;
const adminSectionCache = new Map<AdminSection, { value: AdminSectionResult; expires: number; userId: string }>();
const adminSectionPending = new Map<string, Promise<AdminSectionResult>>();

export function invalidateAdminWorkspace() { adminSectionCache.clear(); }

function sectionsForAdminTab(tab: string): AdminSection[] {
  if (tab === 'overview') return ['accounts', 'platform', 'resourcesA', 'resourcesB'];
  if (tab === 'business') return ['accounts', 'platform', 'resourcesA', 'resourcesB'];
  if (tab === 'operations') return ['accounts', 'staff'];
  if (tab === 'subscriptions') return ['accounts', 'staff', 'payments'];
  if (tab === 'explorer') return ['accounts', 'explorer'];
  if (tab === 'pricing') return ['accounts'];
  if (tab === 'audit') return ['audit'];
  return [];
}

export async function loadAdminWorkspace(tab: string, force = false): Promise<AdminWorkspaceData> {
  const client = requireSupabase();
  const { data: session } = await client.auth.getSession();
  if (!session.session) throw new Error('Admin access requires an authenticated account.');
  const userId = session.session.user.id;
  if (force) invalidateAdminWorkspace();
  const sections = sectionsForAdminTab(tab);
  const results = await Promise.all(sections.map(async (section) => {
    const cached = adminSectionCache.get(section);
    if (cached?.userId === userId && cached.expires > Date.now()) return [section, cached.value] as const;
    const key = `${userId}:${section}`;
    let pending = adminSectionPending.get(key);
    if (!pending) {
      pending = (async () => {
        const response = await fetch(`/api/admin-workspace?section=${section}`, { headers: { Authorization: `Bearer ${session.session!.access_token}` }, cache: 'no-store' });
        const result = await response.json().catch(() => ({})) as AdminSectionResult & { error?: string };
        if (response.status === 429) throw new Error('admin.rateLimited');
        if (!response.ok) throw new Error(`${section}: ${result.error || 'Admin data could not be loaded.'}`);
        adminSectionCache.set(section, { value: result, expires: Date.now() + 60_000, userId });
        return result;
      })();
      adminSectionPending.set(key, pending);
      void pending.finally(() => { if (adminSectionPending.get(key) === pending) adminSectionPending.delete(key); }).catch(() => {});
    }
    return [section, await pending] as const;
  }));
  const sectionData = Object.fromEntries(results) as Partial<Record<AdminSection, AdminSectionResult>>;
  const accounts = sectionData.accounts ?? {}, platform = sectionData.platform ?? {};
  const empty = { rows: [] };
  const platformCounts = { ...(platform.platformCounts ?? {}) };
  if (accounts.profiles?.rows.length != null && accounts.profiles.rows.length < 500 && platformCounts.profiles == null) platformCounts.profiles = accounts.profiles.rows.length;
  if (accounts.subscriptions?.rows.length != null && accounts.subscriptions.rows.length < 500 && platformCounts.subscriptions == null) platformCounts.subscriptions = accounts.subscriptions.rows.length;
  return {
    profiles: accounts.profiles ?? empty, subscriptions: accounts.subscriptions ?? empty, plans: accounts.plans ?? empty,
    paymentEvents: sectionData.payments?.paymentEvents ?? sectionData.audit?.paymentEvents ?? empty,
    overrides: sectionData.audit?.overrides ?? empty,
    staffRoles: sectionData.staff?.staffRoles ?? empty,
    explorerMoves: sectionData.explorer?.explorerMoves ?? empty,
    contentCounts: { ...sectionData.resourcesA?.contentCounts, ...sectionData.resourcesB?.contentCounts }, platformCounts,
    warnings: results.flatMap(([, result]) => result.warnings ?? []).filter((warning) => !(warning.startsWith('user_subscriptions:') && platformCounts.subscriptions != null) && !(warning.startsWith('profiles:') && platformCounts.profiles != null)),
  };
}

type DeveloperSection = keyof Omit<DeveloperWorkspaceData, 'warnings'>;
const developerSpecs: Record<DeveloperSection, { table: string; order: string; limit: number }> = {
  experiments: { table: 'ml_experiments', order: 'updated_at', limit: 250 },
  runs: { table: 'ml_experiment_runs', order: 'created_at', limit: 500 },
  models: { table: 'ml_run_models', order: 'created_at', limit: 500 },
  artifacts: { table: 'ml_run_artifacts', order: 'created_at', limit: 500 },
  jobs: { table: 'system_jobs', order: 'created_at', limit: 500 },
  audit: { table: 'privileged_action_audit_log', order: 'created_at', limit: 500 },
  diagnostics: { table: 'application_diagnostic_events', order: 'last_seen_at', limit: 500 },
  aiCases: { table: 'classio_ai_supervision_cases', order: 'last_seen_at', limit: 200 },
  aiApprovals: { table: 'classio_ai_runtime_approvals', order: 'reviewed_at', limit: 100 },
  aiApprovalEvents: { table: 'classio_ai_runtime_approval_events', order: 'created_at', limit: 100 },
  fallbackEvents: { table: 'classio_ai_fallback_events', order: 'created_at', limit: 200 },
  recommendationEvents: { table: 'learning_program_recommendation_events', order: 'created_at', limit: 500 },
};
const developerCache = new Map<string, { value: WorkspaceResult; expires: number }>();
const developerPending = new Map<string, Promise<WorkspaceResult>>();
export function invalidateDeveloperWorkspace() { developerCache.clear(); }
function developerSections(tab: string): DeveloperSection[] {
  if (tab === 'overview') return ['experiments', 'runs', 'jobs'];
  if (tab === 'lab') return ['experiments', 'runs', 'jobs', 'aiApprovals', 'aiApprovalEvents'];
  if (tab === 'evidence') return ['experiments', 'runs', 'models', 'artifacts'];
  if (tab === 'telemetry') return ['diagnostics', 'aiCases', 'fallbackEvents', 'recommendationEvents'];
  if (tab === 'jobs') return ['jobs'];
  return ['audit'];
}

export async function loadDeveloperWorkspace(tab: string): Promise<DeveloperWorkspaceData> {
  const client = requireSupabase();
  const { data: auth } = await client.auth.getUser();
  if (!auth.user) throw new Error('Developer access requires an authenticated account.');
  const { data: roles, error: rolesError } = await client.from('user_staff_roles').select('role_key').eq('user_id', auth.user.id).eq('is_active', true);
  if (rolesError) throw rolesError;
  const allowed = (roles ?? []).some((row) => row.role_key === 'developer' || row.role_key === 'data_scientist');
  if (!allowed) throw new Error('Developer or data scientist access is required for this workspace.');

  const selected = developerSections(tab);
  const result = await Promise.all(selected.map(async (section) => {
    const key = `${auth.user!.id}:${section}`;
    const cached = developerCache.get(key);
    if (cached && cached.expires > Date.now()) return [section, cached.value] as const;
    let pending = developerPending.get(key);
    if (!pending) {
      const spec = developerSpecs[section];
      pending = readRows(spec.table, '*', { order: spec.order, limit: spec.limit }).then((value) => {
        developerCache.set(key, { value, expires: Date.now() + 60_000 });
        return value;
      });
      developerPending.set(key, pending);
      void pending.finally(() => { if (developerPending.get(key) === pending) developerPending.delete(key); }).catch(() => {});
    }
    return [section, await pending] as const;
  }));
  const bySection = Object.fromEntries(result) as Partial<Record<DeveloperSection, WorkspaceResult>>;
  const empty = { rows: [] };
  return {
    experiments: bySection.experiments ?? empty, runs: bySection.runs ?? empty,
    models: bySection.models ?? empty, artifacts: bySection.artifacts ?? empty,
    jobs: bySection.jobs ?? empty, audit: bySection.audit ?? empty,
    diagnostics: bySection.diagnostics ?? empty, aiCases: bySection.aiCases ?? empty, aiApprovals: bySection.aiApprovals ?? empty, aiApprovalEvents: bySection.aiApprovalEvents ?? empty, fallbackEvents: bySection.fallbackEvents ?? empty, recommendationEvents: bySection.recommendationEvents ?? empty,
    warnings: warnings(result.map(([, value]) => value)),
  };
}

export async function updateAiSupervisionCase(id: number, status: 'triaged' | 'mitigating' | 'resolved', resolutionCode: string | null = null) {
  const client = requireSupabase();
  const { data: user } = await client.auth.getUser();
  if (!user.user) throw new Error('Developer access requires an authenticated account.');
  const { data, error } = await client.rpc('classio_update_ai_supervision_case', {
    p_id: id, p_status: status, p_owner_user_id: user.user.id,
    p_due_at: status === 'resolved' ? null : new Date(Date.now() + 7 * 86400000).toISOString(),
    p_resolution_code: status === 'resolved' ? resolutionCode : null,
  });
  if (error) throw error;
  if (!data) throw new Error('AI case was not found.');
  invalidateDeveloperWorkspace();
}

export async function reviewAiRuntime(surface: string, provider: string, model: string, version: string, status: 'approved' | 'retired', reason: string) {
  const client = requireSupabase();
  const { data, error } = await client.rpc('classio_review_ai_runtime', {
    p_surface: surface, p_provider: provider, p_model: model.trim(),
    p_prompt_version: version, p_status: status, p_reason: reason.trim(),
  });
  if (error) throw error;
  if (!data) throw new Error('AI runtime could not be reviewed.');
  invalidateDeveloperWorkspace();
}

export async function reportAiSupervisionCase(reason: string, severity: string, resourceType: string, resourceId: string) {
  const client = requireSupabase();
  const { data, error } = await client.rpc('classio_report_ai_supervision_case', {
    p_reason: reason, p_severity: severity, p_resource_type: resourceType.trim(),
    p_resource_id: resourceId.trim(), p_operation_id: null,
  });
  if (error) throw error;
  if (!data) throw new Error('AI case could not be created.');
  invalidateDeveloperWorkspace();
}
