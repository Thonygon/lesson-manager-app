/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell, type AppNotification } from '@/components/app-shell';
import { EmptyState, Field, LoadingState, Panel, TabRail } from '@/components/ui';
import { Bars, dateLabel, groupCount, KpiGrid, RecordList, SectionHeading, WarningBox } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { type AdminAiSnapshot, loadAdminAiSnapshot } from '@/services/admin-ai';
import { type AdminWorkspaceData, loadAdminWorkspace } from '@/services/privileged-workspaces';
import { colors } from '@/theme';

type AdminTab = 'overview' | 'operations' | 'pricing' | 'subscriptions' | 'ai' | 'explorer' | 'business' | 'audit';
type OperationsTab = 'accounts' | 'users' | 'staff';

export default function AdminScreen() {
  const { t } = useAppPreferences();
  const params = useLocalSearchParams<{ tab?: string }>();
  const [data, setData] = useState<AdminWorkspaceData | null>(null);
  const [aiSnapshot, setAiSnapshot] = useState<AdminAiSnapshot | null>(null);
  const [aiError, setAiError] = useState('');
  const [error, setError] = useState('');
  const [tab, setTab] = useState<AdminTab>(() => (['overview', 'operations', 'pricing', 'subscriptions', 'ai', 'explorer', 'business', 'audit'].includes(String(params.tab)) ? params.tab as AdminTab : 'overview'));
  const [operationsTab, setOperationsTab] = useState<OperationsTab>('accounts');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [aiExperimentPage, setAiExperimentPage] = useState(1);
  const [aiRunPage, setAiRunPage] = useState(1);
  const load = useCallback(async () => {
    setError('');
    try { setData(await loadAdminWorkspace()); } catch (reason) { setError(reason instanceof Error ? reason.message : t('admin.loadFailed')); }
  }, [t]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (params.tab && ['overview', 'operations', 'pricing', 'subscriptions', 'ai', 'explorer', 'business', 'audit'].includes(params.tab)) setTab(params.tab as AdminTab); }, [params.tab]);
  useEffect(() => {
    if (tab !== 'ai' || aiSnapshot) return;
    let active = true;
    void loadAdminAiSnapshot().then((snapshot) => { if (active) { setAiSnapshot(snapshot); setAiError(''); } })
      .catch((reason) => { if (active) setAiError(reason instanceof Error ? reason.message : t('admin.loadFailed')); });
    return () => { active = false; };
  }, [tab, aiSnapshot, t]);
  useEffect(() => { setPage(1); }, [search, tab, operationsTab]);

  const profiles = useMemo(() => data?.profiles.rows ?? [], [data?.profiles.rows]);
  const subscriptions = data?.subscriptions.rows ?? [];
  const [renderedAt] = useState(() => Date.now());
  const searchableProfiles = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    if (!needle) return profiles;
    return profiles.filter((row) => [row.email, row.display_name, row.role, row.current_plan, row.account_status].some((value) => String(value ?? '').toLocaleLowerCase().includes(needle)));
  }, [profiles, search]);
  const thirtyDaysAgo = renderedAt - 30 * 86400000;
  const paid = profiles.filter((row) => !['', 'free', 'null', 'undefined'].includes(String(row.current_plan ?? '').toLowerCase()));
  const newUsers = profiles.filter((row) => new Date(String(row.created_at ?? '')).getTime() >= thirtyDaysAgo);
  const suspended = profiles.filter((row) => row.account_status === 'suspended');
  const pendingMoves = data?.explorerMoves.rows.filter((row) => row.status === 'pending').length ?? 0;
  const adminNotifications: AppNotification[] = [];
  if (pendingMoves) adminNotifications.push({ key: 'explorer', icon: '🧭', title: t('admin.explorerPending') + ` · ${pendingMoves}`, href: '/admin?tab=explorer' });
  if (data?.warnings.length) adminNotifications.push({ key: 'partial', icon: '⚠️', title: t('admin.partialData'), href: '/admin?tab=audit' });

  if (!data && !error) return <AppShell title={t('admin.title')} eyebrow={t('admin.eyebrow')}><LoadingState /></AppShell>;
  if (error) return <AppShell title={t('admin.title')} eyebrow={t('admin.eyebrow')}><EmptyState title={t('admin.accessDenied')} body={error} /></AppShell>;
  if (!data) return null;

  const tabs = [
    ['overview', t('admin.tab.overview')], ['operations', t('admin.tab.operations')], ['pricing', t('admin.tab.pricing')], ['subscriptions', t('admin.tab.subscriptions')],
    ['ai', t('admin.tab.ai')], ['explorer', t('admin.tab.explorer')], ['business', t('admin.tab.business')], ['audit', t('admin.tab.audit')],
  ].map(([value, label]) => ({ value: value as AdminTab, label }));

  return <AppShell title={t('admin.title')} eyebrow={t('admin.eyebrow')} notifications={adminNotifications}>
    <View style={styles.stack}>
      <TabRail items={tabs} value={tab} onChange={setTab} accessibilityLabel={t('admin.title')} />
      {tab === 'overview' ? <>
        <View style={styles.quickGrid}>{([['operations', '👥', t('admin.tab.operations')], ['subscriptions', '💳', t('admin.tab.subscriptions')], ['ai', '✨', t('admin.tab.ai')], ['audit', '🛡️', t('admin.tab.audit')]] as const).map(([target, icon, label]) => <Pressable key={target} accessibilityRole="button" accessibilityLabel={label} onPress={() => setTab(target)} style={({ pressed }) => [styles.quickCard, pressed && styles.quickPressed]}><Text style={styles.quickIcon}>{icon}</Text><Text style={styles.quickLabel}>{label}</Text><Text style={styles.quickArrow}>→</Text></Pressable>)}</View>
        <KpiGrid items={[
          { label: t('admin.totalUsers'), value: profiles.length }, { label: t('admin.paidUsers'), value: paid.length },
          { label: t('admin.new30'), value: newUsers.length }, { label: t('admin.suspended'), value: suspended.length },
        ]} />
        <Panel><SectionHeading title={t('admin.contentVolume')} body={t('admin.contentVolumeHelp')} /><View style={styles.topGap}><KpiGrid items={[
          { label: t('resources.worksheets'), value: data.contentCounts.worksheets }, { label: t('resources.exams'), value: data.contentCounts.exams },
          { label: t('resources.lessonPlans'), value: data.contentCounts.lessonPlans }, { label: t('resources.videos'), value: data.contentCounts.videos },
          { label: t('resources.programs'), value: data.contentCounts.learningPrograms },
        ]} /></View></Panel>
        <Panel><SectionHeading title={t('admin.planMix')} /><View style={styles.topGap}><Bars rows={groupCount(profiles, 'current_plan')} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel>
        <RecordList rows={profiles.slice(0, 25)} page={page} pageSize={8} onPageChange={setPage} title={t('admin.recentAccounts')} emptyTitle={t('admin.noAccounts')} emptyBody={t('admin.noAccountsBody')} describe={(row) => ({ title: String(row.display_name || row.email || row.user_id), summary: `${row.role || '—'} · ${row.current_plan || 'free'} · ${dateLabel(row.created_at)}` })} fields={profileFields(t)} />
      </> : null}

      {tab === 'operations' ? <>
        <TabRail items={[{ value: 'accounts', label: t('admin.operations.accounts') }, { value: 'users', label: t('admin.operations.users') }, { value: 'staff', label: t('admin.operations.staff') }]} value={operationsTab} onChange={setOperationsTab} />
        {operationsTab !== 'staff' ? <Field value={search} onChangeText={setSearch} placeholder={t('admin.searchUsers')} accessibilityLabel={t('admin.searchUsers')} /> : null}
        {operationsTab === 'accounts' ? <Panel><SectionHeading title={t('admin.accountOperations')} body={t('admin.protectedMutationHelp')} /><View style={styles.topGap}><KpiGrid items={[{ label: t('admin.active'), value: profiles.length - suspended.length }, { label: t('admin.suspended'), value: suspended.length }, { label: t('admin.staffMembers'), value: data.staffRoles.rows.filter((row) => row.is_active).length }]}/></View></Panel> : null}
        {operationsTab === 'users' || operationsTab === 'accounts' ? <RecordList rows={searchableProfiles} page={page} onPageChange={setPage} emptyTitle={t('admin.noAccounts')} emptyBody={t('admin.noAccountsBody')} describe={(row) => ({ title: String(row.display_name || row.email || row.user_id), summary: `${row.role || '—'} · ${row.account_status || 'active'}` })} fields={profileFields(t)} /> : null}
        {operationsTab === 'staff' ? <RecordList rows={data.staffRoles.rows} page={page} onPageChange={setPage} emptyTitle={t('admin.noStaff')} emptyBody={t('admin.noStaffBody')} describe={(row) => ({ title: String(row.role_key || row.user_id), summary: `${row.is_active ? t('admin.active') : t('admin.inactive')} · ${dateLabel(row.assigned_at)}` })} fields={[{ key: 'user_id', label: t('admin.userId') }, { key: 'role_key', label: t('admin.role') }, { key: 'is_active', label: t('admin.status') }, { key: 'assigned_by', label: t('admin.assignedBy') }, { key: 'assigned_at', label: t('admin.assignedAt'), format: dateLabel }, { key: 'assignment_reason', label: t('admin.reason') }]} /> : null}
      </> : null}

      {tab === 'pricing' ? <><SectionHeading title={t('admin.pricingTitle')} body={t('admin.protectedMutationHelp')} /><RecordList rows={data.plans.rows} page={page} onPageChange={setPage} emptyTitle={t('admin.noPlans')} emptyBody={t('admin.noPlansBody')} describe={(row) => ({ title: String(row.name || row.id), summary: `${row.currency || ''} ${row.price_monthly ?? row.monthly_price ?? '—'}` })} fields={Object.keys(data.plans.rows[0] ?? {}).slice(0, 12).map((key) => ({ key, label: key.replaceAll('_', ' ') }))} /></> : null}
      {tab === 'subscriptions' ? <><KpiGrid items={groupCount(subscriptions, 'subscription_status').map(([label, value]) => ({ label, value }))} /><RecordList rows={subscriptions} page={page} onPageChange={setPage} emptyTitle={t('admin.noSubscriptions')} emptyBody={t('admin.noSubscriptionsBody')} describe={(row) => ({ title: String(row.user_id), summary: `${row.plan_id || 'free'} · ${row.subscription_status || 'free'}` })} fields={[{ key: 'plan_id', label: t('admin.plan') }, { key: 'subscription_status', label: t('admin.status') }, { key: 'provider_customer_id', label: t('admin.providerCustomer') }, { key: 'manual_override', label: t('admin.manualOverride') }, { key: 'updated_at', label: t('common.updated'), format: dateLabel }]} /></> : null}
      {tab === 'ai' ? <><SectionHeading title={t('admin.aiTitle')} body={t('admin.aiBody')} />
        <KpiGrid items={[{ label: t('admin.contentTotal'), value: Object.values(aiSnapshot?.contentCounts ?? data.contentCounts).reduce<number>((sum, value) => sum + Number(value || 0), 0) }, { label: t('admin.explorerPending'), value: data.explorerMoves.rows.filter((row) => row.status === 'pending').length }, { label: t('admin.published'), value: data.explorerMoves.rows.filter((row) => row.status === 'published').length }]} />
        {aiSnapshot ? <>
          <Panel><SectionHeading title={t('admin.protectedEvidence')} body={t('admin.estimatedCounts')} /><View style={styles.topGap}><KpiGrid items={[{ label: t('resources.worksheets'), value: aiSnapshot.contentCounts.worksheets ?? '—' }, { label: t('resources.exams'), value: aiSnapshot.contentCounts.quick_exams ?? '—' }, { label: t('resources.lessonPlans'), value: aiSnapshot.contentCounts.lesson_plans ?? '—' }, { label: t('resources.videos'), value: aiSnapshot.contentCounts.videos ?? '—' }, { label: t('resources.programs'), value: aiSnapshot.contentCounts.learning_programs ?? '—' }]} /></View></Panel>
          <RecordList rows={aiSnapshot.experiments} page={aiExperimentPage} onPageChange={setAiExperimentPage} title={t('developer.catalog')} emptyTitle={t('developer.noExperiments')} emptyBody={t('developer.noExperimentsBody')} describe={(row) => ({ title: String(row.name || row.experiment_id), summary: `${row.experiment_id || '—'} · ${row.is_active ? t('admin.active') : t('admin.inactive')}` })} fields={[{ key: 'experiment_id', label: t('admin.experimentId') }, { key: 'updated_at', label: t('common.updated'), format: dateLabel }]} />
          <RecordList rows={aiSnapshot.recentRuns} page={aiRunPage} onPageChange={setAiRunPage} title={t('admin.recentMlRuns')} emptyTitle={t('developer.noRuns')} emptyBody={t('developer.noRunsBody')} describe={(row) => ({ title: String(row.run_id || '—'), summary: `${row.experiment_id || '—'} · ${row.run_status || '—'}` })} fields={[{ key: 'integrity_status', label: t('developer.status') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} />
          <WarningBox warnings={aiSnapshot.warnings} title={t('admin.partialData')} />
        </> : aiError ? <Panel><Text style={styles.note}>{aiError}</Text></Panel> : <LoadingState />}
        <Panel><Text style={styles.note}>{t('admin.developerLinkHelp')}</Text></Panel>
      </> : null}
      {tab === 'explorer' ? <RecordList rows={data.explorerMoves.rows} page={page} onPageChange={setPage} emptyTitle={t('admin.noExplorer')} emptyBody={t('admin.noExplorerBody')} describe={(row) => ({ title: String(row.title || row.tool_key || row.id), summary: `${row.resource_type || '—'} · ${row.status || 'pending'} · ${row.subject || '—'}` })} fields={[{ key: 'tool_key', label: t('admin.tool') }, { key: 'resource_type', label: t('admin.resourceType') }, { key: 'topic', label: t('resources.topic') }, { key: 'learner_stage', label: t('resources.stage') }, { key: 'language', label: t('common.language') }, { key: 'status', label: t('admin.status') }, { key: 'published_table', label: t('admin.destination') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /> : null}
      {tab === 'business' ? <><KpiGrid items={[{ label: t('admin.totalUsers'), value: profiles.length }, { label: t('admin.subscriptions'), value: subscriptions.length }, { label: t('admin.paymentEvents'), value: data.paymentEvents.rows.length }]} /><Panel><SectionHeading title={t('admin.signupTrend')} /><View style={styles.topGap}><Bars rows={signupMonths(profiles)} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel><View style={styles.twoCols}><Panel style={styles.flexPanel}><SectionHeading title={t('admin.planMix')} /><View style={styles.topGap}><Bars rows={groupCount(profiles, 'current_plan')} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel><Panel style={styles.flexPanel}><SectionHeading title={t('admin.statusMix')} /><View style={styles.topGap}><Bars rows={groupCount(subscriptions, 'subscription_status')} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel></View></> : null}
      {tab === 'audit' ? <><SectionHeading title={t('admin.auditTitle')} body={t('admin.auditBody')} /><RecordList rows={[...data.overrides.rows, ...data.paymentEvents.rows].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))} page={page} onPageChange={setPage} emptyTitle={t('admin.noAudit')} emptyBody={t('admin.noAuditBody')} describe={(row) => ({ title: String(row.override_type || row.event_type || row.id), summary: `${row.provider || row.user_id || 'Classio'} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'user_id', label: t('admin.userId') }, { key: 'reason', label: t('admin.reason') }, { key: 'provider', label: t('admin.provider') }, { key: 'processed', label: t('admin.processed') }, { key: 'created_by', label: t('admin.actor') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /></> : null}
      <WarningBox warnings={data.warnings} title={t('admin.partialData')} />
    </View>
  </AppShell>;
}

function profileFields(t: (key: string, values?: Record<string, string | number>) => string) { return [{ key: 'email', label: t('common.email') }, { key: 'user_id', label: t('admin.userId') }, { key: 'role', label: t('admin.role') }, { key: 'primary_role', label: t('admin.primaryRole') }, { key: 'current_plan', label: t('admin.plan') }, { key: 'subscription_status', label: t('admin.subscriptionStatus') }, { key: 'account_status', label: t('admin.accountStatus') }, { key: 'last_active_mode', label: t('admin.lastMode') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]; }
function signupMonths(rows: Record<string, unknown>[]): [string, number][] { const grouped = new Map<string, number>(); rows.forEach((row) => { const date = new Date(String(row.created_at ?? '')); if (!Number.isNaN(date.getTime())) { const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; grouped.set(key, (grouped.get(key) ?? 0) + 1); } }); return Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0])).slice(-12); }

const styles = StyleSheet.create({ quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, quickCard: { flexGrow: 1, flexBasis: 180, minWidth: 160, flexDirection: 'row', alignItems: 'center', gap: 10, padding: 15, borderWidth: 1, borderColor: colors.line, borderRadius: 16, backgroundColor: colors.surface }, quickPressed: { opacity: 0.7 }, quickIcon: { fontSize: 20 }, quickLabel: { flex: 1, color: colors.ink, fontSize: 12, fontWeight: '800' }, quickArrow: { color: colors.primary, fontSize: 16, fontWeight: '900' }, stack: { gap: 18 }, topGap: { marginTop: 16 }, twoCols: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, flexPanel: { flexGrow: 1, flexBasis: 320 }, note: { color: colors.muted, fontSize: 14, lineHeight: 21 } });
