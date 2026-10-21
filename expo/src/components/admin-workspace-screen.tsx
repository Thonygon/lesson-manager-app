/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell, type AppNotification } from '@/components/app-shell';
import { AdminBars as Bars, AdminTrend } from '@/components/admin-charts';
import { AdminExplorerPanel } from '@/components/admin-explorer-panel';
import { AdminIntelligencePanel } from '@/components/admin-intelligence-panel';
import { AdminAccountPanel, AdminPlanPanel, AdminStaffPanel } from '@/components/admin-management-panels';
import { AdminUserEditor } from '@/components/admin-user-editor';
import { PrivilegedRecordList } from '@/components/privileged-record-list';
import { ActionFeedback, Button, EmptyState, Field, LoadingState, Panel, SelectField, TabRail } from '@/components/ui';
import { dateLabel, groupCount, KpiGrid, RecordList, SectionHeading, WarningBox } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { usePrivilegedAccess } from '@/providers/privileged-access-provider';
import { type AdminAiSnapshot, invalidateAdminAiSnapshot, loadAdminAiSnapshot } from '@/services/admin-ai';
import { type AdminEic, invalidateAdminEic, loadAdminEic } from '@/services/admin-eic';
import { type AdminWorkspaceData, loadAdminWorkspace } from '@/services/privileged-workspaces';
import { colors } from '@/theme';
import { localizeAdminError } from '@/lib/admin-error-copy';
import { requireSupabase } from '@/lib/supabase';

type AdminTab = 'overview' | 'operations' | 'pricing' | 'subscriptions' | 'ai' | 'explorer' | 'business' | 'audit';
type OperationsTab = 'accounts' | 'users' | 'staff';
export type AdminArea = 'administration' | 'operations' | 'business';
const AREA_TABS: Record<AdminArea, AdminTab[]> = {
  administration: ['overview', 'operations', 'subscriptions'],
  operations: ['ai', 'explorer', 'audit'],
  business: ['business', 'pricing'],
};
const AREA_PATHS: Record<AdminArea, '/admin' | '/admin-operations' | '/admin-business'> = {
  administration: '/admin', operations: '/admin-operations', business: '/admin-business',
};
const tabArea = (tab: AdminTab): AdminArea => tab === 'overview' || tab === 'operations' || tab === 'subscriptions' ? 'administration' : tab === 'ai' || tab === 'explorer' || tab === 'audit' ? 'operations' : 'business';
function valueLabel(t: (key: string) => string, value: unknown) {
  if (value == null || value === '') return '—';
  if (typeof value === 'boolean') return t(`admin.value.${value ? 'yes' : 'no'}`);
  const raw = String(value);
  const key = `admin.value.${raw.toLocaleLowerCase()}`;
  const translated = t(key);
  return translated === key ? raw : translated;
}
function countLabels(t: (key: string) => string, rows: [string, number][]): [string, number][] { return rows.map(([label, count]) => [valueLabel(t, label === 'Unspecified' ? 'unspecified' : label), count]); }
const metricValue = (value: number | null | undefined) => value == null ? '—' : value;

export function AdminWorkspaceScreen({ area }: { area: AdminArea }) {
  const { t, language } = useAppPreferences();
  const privileged = usePrivilegedAccess();
  const router = useRouter();
  const params = useLocalSearchParams<{ tab?: string }>();
  const [data, setData] = useState<AdminWorkspaceData | null>(null);
  const [loadedTab, setLoadedTab] = useState<AdminTab | null>(null);
  const [aiSnapshot, setAiSnapshot] = useState<AdminAiSnapshot | null>(null);
  const [eic, setEic] = useState<AdminEic | null>(null);
  const [eicLanguage, setEicLanguage] = useState('');
  const [aiError, setAiError] = useState('');
  const [error, setError] = useState('');
  const loadSequence = useRef(0);
  const [tab, setTab] = useState<AdminTab>(() => AREA_TABS[area].includes(params.tab as AdminTab) ? params.tab as AdminTab : AREA_TABS[area][0]);
  const [operationsTab, setOperationsTab] = useState<OperationsTab>('accounts');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [planFilter, setPlanFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [accessUser, setAccessUser] = useState('');
  const [accessRole, setAccessRole] = useState('teacher');
  const [accessPlan, setAccessPlan] = useState('free');
  const [accessStatus, setAccessStatus] = useState('active');
  const [accessCanTeach, setAccessCanTeach] = useState(true);
  const [accessCanStudy, setAccessCanStudy] = useState(false);
  const [accessAccountStatus, setAccessAccountStatus] = useState('active');
  const [accessMode, setAccessMode] = useState('teacher');
  const [accessNotes, setAccessNotes] = useState('');
  const [accessBusy, setAccessBusy] = useState(false);
  const [accessMessage, setAccessMessage] = useState('');
  const [accessTone, setAccessTone] = useState<'success' | 'error'>('error');
  const [accessConfirmed, setAccessConfirmed] = useState(false);
  const load = useCallback(async (force = false) => {
    const sequence = ++loadSequence.current;
    setError('');
    try { const next = await loadAdminWorkspace(tab, force); if (sequence === loadSequence.current) { setData(next); setLoadedTab(tab); } } catch (reason) { if (sequence === loadSequence.current) { const message = reason instanceof Error ? reason.message : ''; setError(message === 'admin.rateLimited' ? t('admin.rateLimited') : message || t('admin.loadFailed')); } }
  }, [t, tab]);
  const refresh = useCallback(() => load(true), [load]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!params.tab) return; if (AREA_TABS[area].includes(params.tab as AdminTab)) setTab(params.tab as AdminTab); else if (['overview', 'operations', 'pricing', 'subscriptions', 'ai', 'explorer', 'business', 'audit'].includes(params.tab)) router.replace({ pathname: AREA_PATHS[tabArea(params.tab as AdminTab)], params: { tab: params.tab } } as Href); }, [area, params.tab, router]);
  useEffect(() => {
    if (tab !== 'ai' || aiSnapshot) return;
    let active = true;
    void loadAdminAiSnapshot(language).then((snapshot) => { if (active) { setAiSnapshot(snapshot); setAiError(''); } })
      .catch((reason) => { if (active) setAiError(reason instanceof Error ? reason.message : t('admin.loadFailed')); });
    return () => { active = false; };
  }, [tab, aiSnapshot, t, language]);
  useEffect(() => {
    if (tab !== 'ai' || (eic && eicLanguage === language)) return;
    let active = true;
    void loadAdminEic(language).then((result) => { if (active) { setEic(result); setEicLanguage(language); } }).catch(() => {});
    return () => { active = false; };
  }, [tab, eic, eicLanguage, language]);
  useEffect(() => { setPage(1); }, [search, tab, operationsTab]);

  const profiles = useMemo(() => data?.profiles.rows ?? [], [data?.profiles.rows]);
  const subscriptions = data?.subscriptions.rows ?? [];
  const chooseAccessUser = (value: string) => {
    setAccessUser(value); setAccessMessage(''); setAccessConfirmed(false);
    const profile = profiles.find((row) => String(row.user_id) === value);
    const subscription = subscriptions.find((row) => String(row.user_id) === value);
    setAccessRole(String(profile?.role || 'teacher'));
    setAccessCanTeach(profile?.can_teach === true || (profile?.can_teach == null && ['teacher', 'tutor'].includes(String(profile?.primary_role || profile?.role))));
    setAccessCanStudy(profile?.can_study === true || String(profile?.role) === 'student');
    setAccessAccountStatus(String(profile?.account_status || 'active'));
    setAccessMode(String(profile?.last_active_mode || (profile?.can_teach ? 'teacher' : 'student')));
    setAccessNotes(String(profile?.admin_notes || ''));
    setAccessPlan(String(subscription?.plan_id || profile?.current_plan || 'free'));
    const subscriptionStatus = String(subscription?.subscription_status || profile?.subscription_status || 'active');
    setAccessStatus(subscriptionStatus === 'cancelled' ? 'canceled' : subscriptionStatus);
  };
  const saveAccess = async () => {
    if (!accessUser || accessBusy || !accessConfirmed) return;
    setAccessBusy(true); setAccessMessage('');
    try {
      const { data: session } = await requireSupabase().auth.getSession();
      if (!session.session) throw new Error(t('admin.accessDenied'));
      const response = await fetch('/api/admin-access', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.session.access_token}` }, body: JSON.stringify({ userId: accessUser, role: accessRole, canTeach: accessCanTeach, canStudy: accessCanStudy, accountStatus: accessAccountStatus, activeMode: accessMode, notes: accessNotes, planId: accessPlan, subscriptionStatus: accessStatus }) });
      const result = await response.json().catch(() => ({})) as { error?: string; audited?: boolean };
      if (!response.ok) throw new Error(result.error ? localizeAdminError(result.error, language) : t('admin.accessSaveFailed'));
      if (result.audited === false) throw new Error(t('admin.auditWriteFailed'));
      await refresh(); setAccessTone('success'); setAccessMessage(t('admin.accessSaved')); setAccessConfirmed(false);
    } catch (reason) { setAccessTone('error'); setAccessMessage(reason instanceof Error ? reason.message : t('admin.accessSaveFailed')); }
    finally { setAccessBusy(false); }
  };
  const [renderedAt] = useState(() => Date.now());
  const searchableProfiles = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return profiles.filter((row) => (roleFilter === 'all' || row.role === roleFilter) && (statusFilter === 'all' || row.account_status === statusFilter) && (planFilter === 'all' || row.current_plan === planFilter) && (!needle || [row.email, row.display_name, row.role, row.current_plan, row.account_status].some((value) => String(value ?? '').toLocaleLowerCase().includes(needle))));
  }, [profiles, search, roleFilter, statusFilter, planFilter]);
  const thirtyDaysAgo = renderedAt - 30 * 86400000;
  const paid = profiles.filter((row) => !['', 'free', 'beta_lifetime', 'null', 'undefined'].includes(String(row.current_plan ?? '').toLowerCase()) && ['active', 'trialing', 'past_due'].includes(String(row.subscription_status ?? '').toLowerCase()));
  const newUsers = profiles.filter((row) => new Date(String(row.created_at ?? '')).getTime() >= thirtyDaysAgo);
  const suspended = profiles.filter((row) => row.account_status === 'suspended');
  const pendingMoves = data?.explorerMoves.rows.filter((row) => row.status === 'pending').length ?? 0;
  const adminNotifications: AppNotification[] = [];
  if (pendingMoves) adminNotifications.push({ key: 'explorer', icon: '🧭', title: t('admin.explorerPending') + ` · ${pendingMoves}`, href: '/admin-operations?tab=explorer' as Href });
  if (data?.warnings.length) adminNotifications.push({ key: 'partial', icon: '⚠️', title: t('admin.partialData'), href: '/admin-operations?tab=audit' as Href });

  if ((!data || loadedTab !== tab) && !error) return <AppShell title={t(`admin.area.${area}`)} eyebrow={t('admin.eyebrow')}><LoadingState /></AppShell>;
  if (error) return <AppShell title={t(`admin.area.${area}`)} eyebrow={t('admin.eyebrow')}><EmptyState title={/admin access|sign in|session has expired/i.test(error) ? t('admin.accessDenied') : t('admin.loadFailed')} body={error} /><Button onPress={() => void refresh()}>{t('common.refresh')}</Button></AppShell>;
  if (!data) return null;
  const contentBars = ([[t('resources.worksheets'), data.contentCounts.worksheets], [t('resources.exams'), data.contentCounts.exams], [t('resources.lessonPlans'), data.contentCounts.lessonPlans], [t('resources.videos'), data.contentCounts.videos], [t('resources.programs'), data.contentCounts.learningPrograms]] as [string, number | null][]).filter((row): row is [string, number] => row[1] !== null && row[1] !== undefined);

  const tabs = [
    ['overview', t('admin.tab.overview')], ['operations', t('admin.tab.operations')], ['pricing', t('admin.tab.pricing')], ['subscriptions', t('admin.tab.subscriptions')],
    ['ai', t('admin.tab.ai')], ['explorer', t('admin.tab.explorer')], ['business', t('admin.tab.business')], ['audit', t('admin.tab.audit')],
  ].filter(([value]) => AREA_TABS[area].includes(value as AdminTab)).map(([value, label]) => ({ value: value as AdminTab, label }));

  return <AppShell title={t(`admin.area.${area}`)} eyebrow={t('admin.eyebrow')} notifications={adminNotifications}>
    <View style={styles.stack}>
      <TabRail items={tabs} value={tab} onChange={setTab} accessibilityLabel={t('admin.title')} />
      {tab === 'overview' ? <>
        {profiles.length >= 500 ? <Text style={styles.note}>{t('admin.sampleNote')}</Text> : null}
        <KpiGrid items={[
          { label: t('admin.totalUsers'), value: metricValue(data.platformCounts.profiles) }, { label: t('admin.paidUsers'), value: paid.length },
          { label: t('admin.new30'), value: newUsers.length }, { label: t('admin.suspended'), value: suspended.length },
        ]} />
        <Panel><SectionHeading title={t('admin.contentVolume')} body={t('admin.contentVolumeHelp')} /><View style={styles.topGap}><KpiGrid items={[
          { label: t('resources.worksheets'), value: metricValue(data.contentCounts.worksheets) }, { label: t('resources.exams'), value: metricValue(data.contentCounts.exams) },
          { label: t('resources.lessonPlans'), value: metricValue(data.contentCounts.lessonPlans) }, { label: t('resources.videos'), value: metricValue(data.contentCounts.videos) },
          { label: t('resources.programs'), value: metricValue(data.contentCounts.learningPrograms) },
        ]} /></View></Panel>
        <Panel><SectionHeading title={t('admin.planMix')} /><View style={styles.topGap}><Bars rows={countLabels(t, groupCount(profiles, 'current_plan'))} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel>
        <PrivilegedRecordList filterKey="role" filterLabel={t('admin.role')} rows={profiles} title={t('admin.recentAccounts')} emptyTitle={t('admin.noAccounts')} emptyBody={t('admin.noAccountsBody')} describe={(row) => ({ title: String(row.display_name || row.email || row.user_id), summary: `${valueLabel(t, row.role)} · ${valueLabel(t, row.current_plan || 'free')} · ${dateLabel(row.created_at)}` })} fields={profileFields(t)} />
      </> : null}

      {tab === 'operations' ? <>
        <TabRail items={[{ value: 'accounts', label: t('admin.operations.accounts') }, { value: 'users', label: t('admin.operations.users') }, { value: 'staff', label: t('admin.operations.staff') }]} value={operationsTab} onChange={setOperationsTab} />
        {operationsTab === 'accounts' ? <AdminAccountPanel profiles={profiles} plans={data.plans.rows} reload={refresh} /> : null}
        {operationsTab === 'staff' ? <AdminStaffPanel profiles={profiles} assignments={data.staffRoles.rows} reload={refresh} /> : null}
        {operationsTab === 'accounts' ? <View style={styles.filterRow}><View style={styles.filterSearch}><Field value={search} onChangeText={(value) => { setSearch(value); setPage(1); }} placeholder={t('admin.searchUsers')} accessibilityLabel={t('admin.searchUsers')} /></View><View style={styles.filter}><SelectField label={t('admin.role')} value={roleFilter} options={[{ value: 'all', label: t('admin.allRoles') }, ...['teacher', 'student', 'school_admin', 'admin'].map((value) => ({ value, label: valueLabel(t, value) }))]} onChange={(value) => { setRoleFilter(value); setPage(1); }} /></View><View style={styles.filter}><SelectField label={t('admin.accountStatus')} value={statusFilter} options={[{ value: 'all', label: t('admin.allStatuses') }, ...['active', 'suspended'].map((value) => ({ value, label: valueLabel(t, value) }))]} onChange={(value) => { setStatusFilter(value); setPage(1); }} /></View><View style={styles.filter}><SelectField label={t('admin.plan')} value={planFilter} options={[{ value: 'all', label: t('admin.allPlans') }, ...data.plans.rows.map((row) => ({ value: String(row.id), label: String(row.name || row.id) }))]} onChange={(value) => { setPlanFilter(value); setPage(1); }} /></View></View> : null}
        {operationsTab === 'accounts' ? <Panel><SectionHeading title={t('admin.accountOperations')} body={t('admin.protectedMutationHelp')} /><View style={styles.topGap}><KpiGrid items={[{ label: t('admin.active'), value: profiles.length - suspended.length }, { label: t('admin.suspended'), value: suspended.length }, { label: t('admin.staffMembers'), value: data.staffRoles.rows.filter((row) => row.is_active).length }]}/></View></Panel> : null}
        {operationsTab === 'accounts' ? <RecordList pageSize={18} rows={searchableProfiles} page={page} onPageChange={setPage} emptyTitle={t('admin.noAccounts')} emptyBody={t('admin.noAccountsBody')} describe={(row) => ({ title: String(row.display_name || row.email || row.user_id), summary: `${valueLabel(t, row.role)} · ${valueLabel(t, row.account_status || 'active')}` })} fields={profileFields(t)} /> : null}
        {operationsTab === 'users' ? <AdminUserEditor profiles={searchableProfiles} plans={data.plans.rows} staffRoles={data.staffRoles.rows} reload={refresh} /> : null}
        {operationsTab === 'staff' ? <PrivilegedRecordList filterKey="role_key" filterLabel={t('admin.role')} rows={data.staffRoles.rows} emptyTitle={t('admin.noStaff')} emptyBody={t('admin.noStaffBody')} describe={(row) => ({ title: String(row.role_key || row.user_id), summary: `${valueLabel(t, row.is_active ? 'active' : 'inactive')} · ${dateLabel(row.assigned_at)}` })} fields={[{ key: 'user_id', label: t('admin.userId') }, { key: 'role_key', label: t('admin.role'), format: (value) => valueLabel(t, value) }, { key: 'is_active', label: t('admin.status'), format: (value) => valueLabel(t, value ? 'active' : 'inactive') }, { key: 'assigned_by', label: t('admin.assignedBy') }, { key: 'assigned_at', label: t('admin.assignedAt'), format: dateLabel }, { key: 'assignment_reason', label: t('admin.reason') }]} /> : null}
      </> : null}

      {tab === 'pricing' ? <><SectionHeading title={t('admin.pricingTitle')} body={t('admin.protectedMutationHelp')} /><AdminPlanPanel plans={data.plans.rows} reload={refresh} /><PrivilegedRecordList filterKey="billing_interval" filterLabel={t('admin.billingInterval')} rows={data.plans.rows} emptyTitle={t('admin.noPlans')} emptyBody={t('admin.noPlansBody')} describe={(row) => ({ title: String(row.name || row.id), summary: `${row.price == null ? t('admin.customPrice') : `USD ${(Number(row.price) / 100).toFixed(2)}`} · ${valueLabel(t, row.active === false ? 'inactive' : 'active')}` })} fields={[{ key: 'id', label: t('admin.planId') }, { key: 'billing_interval', label: t('admin.billingInterval'), format: (value) => t(`admin.interval.${value}`) }, { key: 'active', label: t('admin.status'), format: (value) => valueLabel(t, value ? 'active' : 'inactive') }]} /></> : null}
      {tab === 'subscriptions' ? <><Panel><SectionHeading title={t('admin.manageAccess')} body={t('admin.manageAccessHelp')} /><View style={styles.topGap}><SelectField label={t('admin.account')} value={accessUser} options={[{ value: '', label: t('admin.chooseAccount') }, ...profiles.map((row) => ({ value: String(row.user_id), label: String(row.email || row.display_name || row.user_id) }))]} onChange={chooseAccessUser} />{accessUser ? <><SelectField label={t('admin.role')} value={accessRole} options={['teacher', 'student', 'school_admin', 'admin'].map((value) => ({ value, label: valueLabel(t, value) }))} onChange={(value) => { setAccessRole(value); if (accessMode === 'admin' && value !== 'admin') setAccessMode(accessCanTeach ? 'teacher' : 'student'); }} /><SelectField label={t('admin.teachingAccess')} value={accessCanTeach ? 'yes' : 'no'} options={[{ value: 'yes', label: t('resources.yes') }, { value: 'no', label: t('resources.no') }]} onChange={(value) => { const enabled = value === 'yes'; setAccessCanTeach(enabled); if (!enabled && accessMode === 'teacher') { if (accessCanStudy) setAccessMode('student'); else if (accessRole === 'admin') setAccessMode('admin'); else { setAccessCanStudy(true); setAccessMode('student'); } } }} /><SelectField label={t('admin.studyAccess')} value={accessCanStudy ? 'yes' : 'no'} options={[{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }]} onChange={(value) => { const enabled = value === 'yes'; setAccessCanStudy(enabled); if (!enabled && accessMode === 'student') { if (accessCanTeach) setAccessMode('teacher'); else if (accessRole === 'admin') setAccessMode('admin'); else { setAccessCanTeach(true); setAccessMode('teacher'); } } }} /><SelectField label={t('admin.defaultMode')} value={accessMode} options={[...(accessCanTeach ? ['teacher'] : []), ...(accessCanStudy ? ['student'] : []), ...(accessRole === 'admin' ? ['admin'] : []), ...(accessMode === 'developer_workspace' || data.staffRoles.rows.some((row) => row.user_id === accessUser && row.is_active) ? ['developer_workspace'] : [])].map((value) => ({ value, label: valueLabel(t, value) }))} onChange={setAccessMode} /><SelectField label={t('admin.accountStatus')} value={accessAccountStatus} options={['active', 'suspended'].map((value) => ({ value, label: valueLabel(t, value) }))} onChange={setAccessAccountStatus} /><Field value={accessNotes} onChangeText={setAccessNotes} placeholder={t('admin.notes')} accessibilityLabel={t('admin.notes')} /><SelectField label={t('admin.plan')} value={accessPlan} options={data.plans.rows.filter((row) => row.active !== false).map((row) => ({ value: String(row.id), label: String(row.name || row.id) }))} onChange={setAccessPlan} /><SelectField label={t('admin.subscriptionStatus')} value={accessStatus} options={['free', 'active', 'trialing', 'past_due', 'canceled', 'expired'].map((value) => ({ value, label: valueLabel(t, value) }))} onChange={setAccessStatus} /><Pressable accessibilityRole="checkbox" accessibilityState={{ checked: accessConfirmed }} onPress={() => setAccessConfirmed(!accessConfirmed)} style={styles.confirmRow}><Text style={styles.confirmMark}>{accessConfirmed ? '☑' : '☐'}</Text><Text style={styles.confirmText}>{t('admin.confirmAccess')}</Text></Pressable><Button disabled={accessBusy || !accessConfirmed} onPress={() => void saveAccess()}>{accessBusy ? t('common.saving') : t('admin.saveAccess')}</Button><ActionFeedback message={accessMessage} tone={accessTone} /></> : null}</View></Panel><KpiGrid items={countLabels(t, groupCount(subscriptions, 'subscription_status')).map(([label, value]) => ({ label, value }))} /><PrivilegedRecordList filterKey="subscription_status" filterLabel={t('admin.subscriptionStatus')} rows={subscriptions} emptyTitle={t('admin.noSubscriptions')} emptyBody={t('admin.noSubscriptionsBody')} describe={(row) => ({ title: String(row.user_id), summary: `${valueLabel(t, row.plan_id || 'free')} · ${valueLabel(t, row.subscription_status || 'free')}` })} fields={[{ key: 'plan_id', label: t('admin.plan'), format: (value) => valueLabel(t, value) }, { key: 'subscription_status', label: t('admin.status'), format: (value) => valueLabel(t, value) }, { key: 'provider_customer_id', label: t('admin.providerCustomer') }, { key: 'manual_override', label: t('admin.manualOverride'), format: (value) => valueLabel(t, value) }, { key: 'updated_at', label: t('common.updated'), format: dateLabel }]} /><PrivilegedRecordList filterKey="event_type" filterLabel={t('admin.eventType')} rows={data.paymentEvents.rows} title={t('admin.recentPaymentEvents')} emptyTitle={t('admin.noPaymentEvents')} emptyBody={t('admin.noPaymentEventsBody')} describe={(row) => ({ title: valueLabel(t, row.event_type || row.provider || row.id), summary: `${String(row.provider || 'Classio')} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'provider', label: t('admin.provider') }, { key: 'processed', label: t('admin.processed'), format: (value) => valueLabel(t, value) }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /></> : null}
      {tab === 'ai' ? <AdminIntelligencePanel snapshot={aiSnapshot} eic={eic} error={aiError} contentCounts={data.contentCounts} moves={data.explorerMoves.rows} canOpenDeveloper={privileged.canUseDeveloperWorkspace} onOpenDeveloper={() => router.push('/developer-workspace')} onRefresh={() => { invalidateAdminAiSnapshot(); invalidateAdminEic(); setAiSnapshot(null); setEic(null); void refresh(); }} /> : null}
      {tab === 'explorer' ? <AdminExplorerPanel moves={data.explorerMoves.rows} profiles={profiles} reload={refresh} /> : null}
      {tab === 'business' ? <><KpiGrid items={[{ label: t('admin.totalUsers'), value: metricValue(data.platformCounts.profiles) }, { label: t('admin.subscriptions'), value: metricValue(data.platformCounts.subscriptions) }, { label: t('admin.paymentEvents'), value: metricValue(data.platformCounts.paymentEvents) }, { label: t('admin.aiUsageEvents'), value: metricValue(data.platformCounts.aiUsage) }]} />{profiles.length >= 500 ? <Text style={styles.note}>{t('admin.sampleNote')}</Text> : null}<Panel><SectionHeading title={t('admin.signupTrend')} /><View style={styles.topGap}><AdminTrend rows={signupMonths(profiles)} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel><View style={styles.twoCols}><Panel style={styles.flexPanel}><SectionHeading title={t('admin.planMix')} /><View style={styles.topGap}><Bars rows={countLabels(t, groupCount(profiles, 'current_plan'))} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel><Panel style={styles.flexPanel}><SectionHeading title={t('admin.statusMix')} /><View style={styles.topGap}><Bars rows={countLabels(t, groupCount(subscriptions, 'subscription_status'))} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel></View><Panel><SectionHeading title={t('admin.contentVolume')} /><View style={styles.topGap}><Bars rows={contentBars} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel></> : null}
      {tab === 'audit' ? <><SectionHeading title={t('admin.auditTitle')} body={t('admin.auditBody')} /><Panel><SectionHeading title={t('admin.overrideActivity')} /><Bars rows={countLabels(t, groupCount(data.overrides.rows, 'override_type'))} emptyTitle={t('admin.noAudit')} emptyBody={t('admin.noAuditBody')} /></Panel><PrivilegedRecordList filterKey="override_type" filterLabel={t('admin.action')} rows={data.overrides.rows} title={t('admin.overrideHistory')} emptyTitle={t('admin.noAudit')} emptyBody={t('admin.noAuditBody')} describe={(row) => ({ title: valueLabel(t, row.override_type || row.id), summary: `${row.user_id || '—'} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'user_id', label: t('admin.userId') }, { key: 'reason', label: t('admin.reason') }, { key: 'created_by', label: t('admin.actor') }, { key: 'expires_at', label: t('admin.expiresAt'), format: dateLabel }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /><PrivilegedRecordList filterKey="event_type" filterLabel={t('admin.eventType')} rows={data.paymentEvents.rows} title={t('admin.recentPaymentEvents')} emptyTitle={t('admin.noPaymentEvents')} emptyBody={t('admin.noPaymentEventsBody')} describe={(row) => ({ title: valueLabel(t, row.event_type || row.provider || row.id), summary: `${String(row.provider || 'Classio')} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'provider', label: t('admin.provider') }, { key: 'event_type', label: t('admin.eventType'), format: (value) => valueLabel(t, value) }, { key: 'processed', label: t('admin.processed'), format: (value) => valueLabel(t, value) }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /></> : null}
      <WarningBox warnings={data.warnings} title={t('admin.partialData')} />
    </View>
  </AppShell>;
}

function profileFields(t: (key: string, values?: Record<string, string | number>) => string) { const format = (value: unknown) => valueLabel(t, value); return [{ key: 'email', label: t('common.email') }, { key: 'user_id', label: t('admin.userId') }, { key: 'role', label: t('admin.role'), format }, { key: 'primary_role', label: t('admin.primaryRole'), format }, { key: 'current_plan', label: t('admin.plan'), format }, { key: 'subscription_status', label: t('admin.subscriptionStatus'), format }, { key: 'account_status', label: t('admin.accountStatus'), format }, { key: 'last_active_mode', label: t('admin.lastMode'), format }, { key: 'login_count', label: t('admin.logins') }, { key: 'active_student_count', label: t('admin.activeStudents') }, { key: 'last_used_at', label: t('admin.lastLogin'), format: dateLabel }, { key: 'created_at', label: t('common.created'), format: dateLabel }]; }
function signupMonths(rows: Record<string, unknown>[]): [string, number][] { const grouped = new Map<string, number>(); rows.forEach((row) => { const date = new Date(String(row.created_at ?? '')); if (!Number.isNaN(date.getTime())) { const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; grouped.set(key, (grouped.get(key) ?? 0) + 1); } }); return Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0])).slice(-12); }

const styles = StyleSheet.create({ filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, filterSearch: { flexGrow: 2, flexBasis: 230, minWidth: 190 }, filter: { flexGrow: 1, flexBasis: 160, minWidth: 150 }, stack: { gap: 18 }, topGap: { marginTop: 16 }, twoCols: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, flexPanel: { flexGrow: 1, flexBasis: 320 }, note: { color: colors.muted, fontSize: 14, lineHeight: 21 }, confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 10 }, confirmMark: { color: colors.primary, fontSize: 20 }, confirmText: { color: colors.ink, fontSize: 12, flexShrink: 1 } });
