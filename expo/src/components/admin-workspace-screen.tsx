/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell, type AppNotification } from '@/components/app-shell';
import { AdminBars as Bars, AdminTrend } from '@/components/admin-charts';
import { AdminExplorerPanel } from '@/components/admin-explorer-panel';
import { AdminIntelligencePanel } from '@/components/admin-intelligence-panel';
import { AdminAccountPanel, AdminPlanPanel, AdminStaffPanel } from '@/components/admin-management-panels';
import { AdminUserEditor } from '@/components/admin-user-editor';
import { AdminGeographyPanel } from '@/components/admin-geography-panel';
import { PrivilegedRecordList } from '@/components/privileged-record-list';
import { Button, EmptyState, LoadingState, Panel, TabRail } from '@/components/ui';
import { dateLabel, groupCount, KpiGrid, SectionHeading, WarningBox } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { usePrivilegedAccess } from '@/providers/privileged-access-provider';
import { type AdminAiSnapshot, invalidateAdminAiSnapshot, loadAdminAiSnapshot } from '@/services/admin-ai';
import { type AdminEic, invalidateAdminEic, loadAdminEic } from '@/services/admin-eic';
import { type AdminWorkspaceData, loadAdminWorkspace } from '@/services/privileged-workspaces';
import { colors } from '@/theme';
import { LEGAL_PUBLICATION } from '@/lib/legal-publication.generated';

type AdminTab = 'overview' | 'operations' | 'pricing' | 'subscriptions' | 'ai' | 'explorer' | 'business' | 'audit';
type OperationsTab = 'accounts' | 'users' | 'staff';
export type AdminArea = 'administration' | 'accounts' | 'operations' | 'business';
const AREA_TABS: Record<AdminArea, AdminTab[]> = {
  administration: ['overview'],
  accounts: ['operations'],
  operations: ['ai', 'explorer', 'audit'],
  business: ['business', 'pricing'],
};
const AREA_PATHS: Record<AdminArea, '/admin' | '/admin-accounts' | '/admin-operations' | '/admin-business'> = {
  administration: '/admin', accounts: '/admin-accounts', operations: '/admin-operations', business: '/admin-business',
};
const tabArea = (tab: AdminTab): AdminArea => tab === 'overview' ? 'administration' : tab === 'operations' || tab === 'subscriptions' ? 'accounts' : tab === 'ai' || tab === 'explorer' || tab === 'audit' ? 'operations' : 'business';
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
  const [operationsTab, setOperationsTab] = useState<OperationsTab>('users');
  const load = useCallback(async (force = false) => {
    const sequence = ++loadSequence.current;
    setError('');
    try { const next = await loadAdminWorkspace(tab, force); if (sequence === loadSequence.current) { setData(next); setLoadedTab(tab); } } catch (reason) { if (sequence === loadSequence.current) { const message = reason instanceof Error ? reason.message : ''; setError(message === 'admin.rateLimited' ? t('admin.rateLimited') : message || t('admin.loadFailed')); } }
  }, [t, tab]);
  const refresh = useCallback(() => load(true), [load]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (!params.tab) return; if (params.tab === 'subscriptions') { router.replace('/admin-accounts'); return; } if (AREA_TABS[area].includes(params.tab as AdminTab)) setTab(params.tab as AdminTab); else if (['overview', 'operations', 'pricing', 'ai', 'explorer', 'business', 'audit'].includes(params.tab)) router.replace({ pathname: AREA_PATHS[tabArea(params.tab as AdminTab)], params: { tab: params.tab } } as Href); }, [area, params.tab, router]);
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

  const profiles = useMemo(() => data?.profiles.rows ?? [], [data?.profiles.rows]);
  const globalMetrics = data?.globalMetrics;
  const pendingMoves = data?.explorerMoves.rows.filter((row) => row.status === 'pending').length ?? 0;
  const adminNotifications: AppNotification[] = [];
  if (pendingMoves) adminNotifications.push({ key: 'explorer', icon: '🧭', title: t('admin.explorerPending') + ` · ${pendingMoves}`, href: '/admin-operations?tab=explorer' as Href });
  if (data?.warnings.length) adminNotifications.push({ key: 'partial', icon: '⚠️', title: t('admin.partialData'), href: '/admin-operations?tab=audit' as Href });

  if ((!data || loadedTab !== tab) && !error) return <AppShell title={t(`admin.area.${area}`)} eyebrow={t('admin.eyebrow')}><LoadingState /></AppShell>;
  if (error) return <AppShell title={t(`admin.area.${area}`)} eyebrow={t('admin.eyebrow')}><EmptyState title={/admin access|sign in|session has expired/i.test(error) ? t('admin.accessDenied') : t('admin.loadFailed')} body={error} /><Button onPress={() => void refresh()}>{t('common.refresh')}</Button></AppShell>;
  if (!data) return null;
  const contentBars = ([[t('resources.worksheets'), data.contentCounts.worksheets], [t('resources.exams'), data.contentCounts.exams], [t('resources.lessonPlans'), data.contentCounts.lessonPlans], [t('resources.videos'), data.contentCounts.videos], [t('resources.programs'), data.contentCounts.learningPrograms]] as [string, number | null][]).filter((row): row is [string, number] => row[1] !== null && row[1] !== undefined);

  const tabs = [
    ['overview', t('admin.tab.overview')], ['operations', t('admin.tab.operations')], ['pricing', t('admin.tab.pricing')],
    ['ai', t('admin.tab.ai')], ['explorer', t('admin.tab.explorer')], ['business', t('admin.tab.business')], ['audit', t('admin.tab.audit')],
  ].filter(([value]) => AREA_TABS[area].includes(value as AdminTab)).map(([value, label]) => ({ value: value as AdminTab, label }));

  return <AppShell title={t(`admin.area.${area}`)} eyebrow={t('admin.eyebrow')} notifications={adminNotifications}>
    <View style={styles.stack}>
      {tabs.length > 1 ? <TabRail items={tabs} value={tab} onChange={setTab} accessibilityLabel={t('admin.title')} /> : null}
      {tab === 'overview' ? <>
        {!globalMetrics ? <Text style={styles.note}>{t('admin.globalMetricsUnavailable')}</Text> : null}
        <KpiGrid items={[
          { label: t('admin.totalUsers'), value: metricValue(data.platformCounts.profiles) }, { label: t('admin.planAccessUsers'), value: metricValue(globalMetrics?.commercial_plan_access) },
          { label: t('admin.new30'), value: metricValue(globalMetrics?.new_30_days) }, { label: t('admin.suspended'), value: metricValue(globalMetrics?.suspended) },
        ]} />
        <Text style={styles.note}>{t('admin.planAccessNotRevenue')}</Text>
        <AdminGeographyPanel />
        <Panel><SectionHeading title={t('admin.contentVolume')} body={t('admin.contentVolumeHelp')} /><View style={styles.topGap}><KpiGrid items={[
          { label: t('resources.worksheets'), value: metricValue(data.contentCounts.worksheets) }, { label: t('resources.exams'), value: metricValue(data.contentCounts.exams) },
          { label: t('resources.lessonPlans'), value: metricValue(data.contentCounts.lessonPlans) }, { label: t('resources.videos'), value: metricValue(data.contentCounts.videos) },
          { label: t('resources.programs'), value: metricValue(data.contentCounts.learningPrograms) },
        ]} /></View></Panel>
        <Panel><SectionHeading title={t('admin.planMix')} /><View style={styles.topGap}>{globalMetrics ? <Bars rows={countLabels(t, globalMetrics.plan_mix)} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /> : <Text style={styles.note}>{t('admin.globalMetricsUnavailable')}</Text>}</View></Panel>
        <Button secondary onPress={() => router.push('/admin-accounts')}>{t('admin.openAccounts')}</Button>
      </> : null}

      {tab === 'operations' ? <>
        <TabRail items={[{ value: 'users', label: t('admin.operations.users') }, { value: 'accounts', label: t('admin.operations.accounts') }, { value: 'staff', label: t('admin.operations.staff') }]} value={operationsTab} onChange={setOperationsTab} />
        {operationsTab === 'accounts' ? <AdminAccountPanel profiles={profiles} plans={data.plans.rows} reload={refresh} /> : null}
        {operationsTab === 'staff' ? <AdminStaffPanel profiles={profiles} admins={data.platformAdmins.rows} assignments={data.staffRoles.rows} reload={refresh} /> : null}
        {operationsTab === 'users' ? <AdminUserEditor profiles={profiles} plans={data.plans.rows} staffRoles={data.staffRoles.rows} reload={refresh} /> : null}
        {operationsTab === 'staff' ? <PrivilegedRecordList filterKey="role_key" filterLabel={t('admin.role')} rows={data.staffRoles.rows} emptyTitle={t('admin.noStaff')} emptyBody={t('admin.noStaffBody')} describe={(row) => ({ title: String(row.role_key || row.user_id), summary: `${valueLabel(t, row.is_active ? 'active' : 'inactive')} · ${dateLabel(row.assigned_at)}` })} fields={[{ key: 'user_id', label: t('admin.userId') }, { key: 'role_key', label: t('admin.role'), format: (value) => valueLabel(t, value) }, { key: 'is_active', label: t('admin.status'), format: (value) => valueLabel(t, value ? 'active' : 'inactive') }, { key: 'assigned_by', label: t('admin.assignedBy') }, { key: 'assigned_at', label: t('admin.assignedAt'), format: dateLabel }, { key: 'assignment_reason', label: t('admin.reason') }]} /> : null}
      </> : null}

      {tab === 'pricing' ? <><SectionHeading title={t('admin.pricingTitle')} body={t('admin.protectedMutationHelp')} /><AdminPlanPanel plans={data.plans.rows} reload={refresh} /><PrivilegedRecordList filterKey="billing_interval" filterLabel={t('admin.billingInterval')} rows={data.plans.rows} emptyTitle={t('admin.noPlans')} emptyBody={t('admin.noPlansBody')} describe={(row) => ({ title: String(row.name || row.id), summary: `${row.price == null ? t('admin.customPrice') : `USD ${(Number(row.price) / 100).toFixed(2)}`} · ${valueLabel(t, row.active === false ? 'inactive' : 'active')}` })} fields={[{ key: 'id', label: t('admin.planId') }, { key: 'billing_interval', label: t('admin.billingInterval'), format: (value) => t(`admin.interval.${value}`) }, { key: 'active', label: t('admin.status'), format: (value) => valueLabel(t, value ? 'active' : 'inactive') }]} /></> : null}
      {tab === 'ai' ? <AdminIntelligencePanel snapshot={aiSnapshot} eic={eic} error={aiError} contentCounts={data.contentCounts} moves={data.explorerMoves.rows} canOpenDeveloper={privileged.canUseDeveloperWorkspace} onOpenDeveloper={() => router.push('/developer-workspace')} onRefresh={() => { invalidateAdminAiSnapshot(); invalidateAdminEic(); setAiSnapshot(null); setEic(null); void refresh(); }} /> : null}
      {tab === 'explorer' ? <AdminExplorerPanel moves={data.explorerMoves.rows} profiles={profiles} reload={refresh} /> : null}
      {tab === 'business' ? <><KpiGrid items={[{ label: t('admin.totalUsers'), value: metricValue(data.platformCounts.profiles) }, { label: t('admin.subscriptions'), value: metricValue(data.platformCounts.subscriptions) }, { label: t('admin.paymentEvents'), value: metricValue(data.platformCounts.paymentEvents) }, { label: t('admin.aiUsageEvents'), value: metricValue(data.platformCounts.aiUsage) }]} />{!globalMetrics ? <Text style={styles.note}>{t('admin.globalMetricsUnavailable')}</Text> : null}<Panel><SectionHeading title={t('admin.signupTrend')} /><View style={styles.topGap}>{globalMetrics ? <AdminTrend rows={globalMetrics.signup_months} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /> : <Text style={styles.note}>{t('admin.globalMetricsUnavailable')}</Text>}</View></Panel><View style={styles.twoCols}><Panel style={styles.flexPanel}><SectionHeading title={t('admin.planMix')} /><View style={styles.topGap}>{globalMetrics ? <Bars rows={countLabels(t, globalMetrics.plan_mix)} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /> : <Text style={styles.note}>{t('admin.globalMetricsUnavailable')}</Text>}</View></Panel><Panel style={styles.flexPanel}><SectionHeading title={t('admin.statusMix')} /><View style={styles.topGap}>{globalMetrics ? <Bars rows={countLabels(t, globalMetrics.status_mix)} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /> : <Text style={styles.note}>{t('admin.globalMetricsUnavailable')}</Text>}</View></Panel></View><Panel><SectionHeading title={t('admin.contentVolume')} /><View style={styles.topGap}><Bars rows={contentBars} emptyTitle={t('common.noResults')} emptyBody={t('admin.noData')} /></View></Panel></> : null}
      {tab === 'business' ? <Panel><SectionHeading title={t('admin.aiEconomicCoverage')} body={t('admin.aiEconomicCoverageHelp')} /><KpiGrid items={[{ label: t('admin.aiOperations'), value: metricValue(data.platformCounts.aiOperations) }, { label: t('admin.providerAttempts'), value: metricValue(data.platformCounts.providerAttempts) }, { label: t('admin.pendingAiOperations'), value: metricValue(data.platformCounts.pendingAiOperations) }, { label: t('admin.reconciliationCases'), value: metricValue(data.platformCounts.reconciliationCases) }, { label: t('admin.attemptsMissingUsage'), value: metricValue(data.platformCounts.attemptsMissingUsage) }, { label: t('admin.linkEligibleAiOperations'), value: metricValue(data.platformCounts.linkEligibleAiOperations) }, { label: t('admin.linkedAiResources'), value: metricValue(data.platformCounts.linkedAiResources) }, { label: t('admin.linkedImageCovers'), value: metricValue(data.platformCounts.linkedImageCovers) }, { label: t('admin.unlinkedAiOperations'), value: metricValue(data.platformCounts.unlinkedAiOperations) }, { label: t('admin.programSkeletonLinks'), value: metricValue(data.platformCounts.programSkeletonLinks) }, { label: t('admin.programUnitLinks'), value: metricValue(data.platformCounts.programUnitLinks) }]} /><Text style={styles.note}>{t('admin.resourceLinkCoverageHelp')}</Text></Panel> : null}
      {tab === 'business' ? <Panel><SectionHeading title={t('admin.exportCoverage')} body={t('admin.exportCoverageHelp')} /><KpiGrid items={[{ label: t('admin.pdfExportEvents'), value: metricValue(data.platformCounts.pdfExportEvents) }, { label: t('admin.wordExportEvents'), value: metricValue(data.platformCounts.wordExportEvents) }, { label: t('admin.failedExportEvents'), value: metricValue(data.platformCounts.failedExportEvents) }, { label: t('admin.pendingExportEvents'), value: metricValue(data.platformCounts.pendingExportEvents) }]} /></Panel> : null}
      {tab === 'audit' ? <><SectionHeading title={t('admin.auditTitle')} body={t('admin.auditBody')} /><Panel><SectionHeading title={t('admin.overrideActivity')} /><Bars rows={countLabels(t, groupCount(data.overrides.rows, 'override_type'))} emptyTitle={t('admin.noAudit')} emptyBody={t('admin.noAuditBody')} /></Panel><PrivilegedRecordList filterKey="override_type" filterLabel={t('admin.action')} rows={data.overrides.rows} title={t('admin.overrideHistory')} emptyTitle={t('admin.noAudit')} emptyBody={t('admin.noAuditBody')} describe={(row) => ({ title: valueLabel(t, row.override_type || row.id), summary: `${row.user_id || '—'} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'user_id', label: t('admin.userId') }, { key: 'reason', label: t('admin.reason') }, { key: 'created_by', label: t('admin.actor') }, { key: 'expires_at', label: t('admin.expiresAt'), format: dateLabel }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /><PrivilegedRecordList filterKey="event_type" filterLabel={t('admin.eventType')} rows={data.paymentEvents.rows} title={t('admin.recentPaymentEvents')} emptyTitle={t('admin.noPaymentEvents')} emptyBody={t('admin.noPaymentEventsBody')} describe={(row) => ({ title: valueLabel(t, row.event_type || row.provider || row.id), summary: `${String(row.provider || 'Classio')} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'provider', label: t('admin.provider') }, { key: 'event_type', label: t('admin.eventType'), format: (value) => valueLabel(t, value) }, { key: 'processed', label: t('admin.processed'), format: (value) => t(value === true ? 'admin.eventProcessed' : 'admin.eventUnprocessed') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /></> : null}
      {tab === 'audit' ? <Panel><SectionHeading title={t('legal.versionedPages')} body={`${LEGAL_PUBLICATION.version} · ${t('legal.effective')}: ${LEGAL_PUBLICATION.effectiveDate} · ${t('legal.publicationApprover')}: ${LEGAL_PUBLICATION.publicationApprover}`} />{LEGAL_PUBLICATION.documents.filter((item) => item.language === language).map((item) => <Pressable key={item.slug} accessibilityRole="link" onPress={() => void Linking.openURL(item.url)} style={{ paddingVertical: 8 }}><Text style={{ color: colors.primary, fontWeight: '700' }}>{t(item.slug === 'terms' ? 'legal.terms' : 'legal.teacherData')} ↗</Text><Text selectable style={styles.note}>SHA-256: {item.sha256}</Text></Pressable>)}</Panel> : null}
      <WarningBox warnings={data.warnings} title={t('admin.partialData')} />
    </View>
  </AppShell>;
}


const styles = StyleSheet.create({ filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, filterSearch: { flexGrow: 2, flexBasis: 230, minWidth: 190 }, filter: { flexGrow: 1, flexBasis: 160, minWidth: 150 }, stack: { gap: 18 }, topGap: { marginTop: 16 }, twoCols: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, flexPanel: { flexGrow: 1, flexBasis: 320 }, note: { color: colors.muted, fontSize: 14, lineHeight: 21 }, confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 10 }, confirmMark: { color: colors.primary, fontSize: 20 }, confirmText: { color: colors.ink, fontSize: 12, flexShrink: 1 } });
