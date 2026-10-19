import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AdminBars } from '@/components/admin-charts';
import { Button, Disclosure, Field, LoadingState, Panel, SelectField, TabRail } from '@/components/ui';
import { dateLabel, groupCount, KpiGrid, RecordList, SectionHeading, WarningBox } from '@/components/workspace-ui';
import { ADMIN_INTELLIGENCE_CATALOG } from '@/data/admin-intelligence-catalog';
import { useAppPreferences } from '@/providers/app-preferences';
import type { AdminAiSnapshot } from '@/services/admin-ai';
import { colors } from '@/theme';

type Tab = 'overview' | 'systems' | 'evidence' | 'health';
const status = (value: unknown) => String(value ?? '').trim().toLowerCase();

export function AdminIntelligencePanel({ snapshot, error, contentCounts, moves, canOpenDeveloper, onOpenDeveloper, onRefresh }: {
  snapshot: AdminAiSnapshot | null;
  error: string;
  contentCounts: Record<string, number>;
  moves: Record<string, unknown>[];
  canOpenDeveloper: boolean;
  onOpenDeveloper: () => void;
  onRefresh: () => void;
}) {
  const { t, language } = useAppPreferences();
  const [tab, setTab] = useState<Tab>('overview'), [search, setSearch] = useState(''), [systemStatus, setSystemStatus] = useState('all');
  const systems = useMemo(() => ADMIN_INTELLIGENCE_CATALOG.filter((item) => {
    const copy = item.translations[language];
    return (systemStatus === 'all' || item.operational_status === systemStatus) && (!search.trim() || [copy.name, copy.business_question, item.component_id].some((value) => value.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())));
  }), [language, search, systemStatus]);
  const validated = snapshot?.validatedRuns ?? [];
  const failedJobs = snapshot?.recentJobs.filter((row) => ['FAILED', 'STALE'].includes(String(row.status))) ?? [];
  const runningJobs = snapshot?.recentJobs.filter((row) => ['QUEUED', 'RUNNING'].includes(String(row.status))) ?? [];
  const contentTotal = Object.values(snapshot?.contentCounts ?? contentCounts).reduce<number>((sum, value) => sum + Number(value || 0), 0);
  const translatedStatus = (value: unknown) => { const key = `admin.value.${status(value)}`; return t(key) === key ? String(value || '—') : t(key); };
  return <View style={styles.stack}>
    <View style={styles.header}><View style={styles.headerText}><SectionHeading title={t('admin.aiTitle')} body={t('admin.aiBody')} /></View><Button secondary onPress={onRefresh}>{t('admin.refresh')}</Button></View>
    <TabRail accessibilityLabel={t('admin.aiTitle')} value={tab} onChange={setTab} items={(['overview', 'systems', 'evidence', 'health'] as const).map((value) => ({ value, label: t(`admin.intelligenceTab.${value}`) }))} />
    {tab === 'overview' ? <>
      <KpiGrid items={[{ label: t('admin.contentTotal'), value: contentTotal }, { label: t('admin.systemCount'), value: ADMIN_INTELLIGENCE_CATALOG.length }, { label: t('admin.explorerPending'), value: moves.filter((row) => row.status === 'pending').length }, { label: t('admin.validatedRuns'), value: validated.length }, { label: t('admin.failedJobs'), value: failedJobs.length }]} />
      {snapshot ? <><View style={styles.twoCols}><Panel style={styles.flexPanel}><SectionHeading title={t('admin.runStatus')} /><AdminBars rows={groupCount(snapshot.recentRuns, 'run_status').map(([label, count]) => [translatedStatus(label), count])} emptyTitle={t('developer.noRuns')} emptyBody={t('developer.noRunsBody')} /></Panel><Panel style={styles.flexPanel}><SectionHeading title={t('admin.jobStatus')} /><AdminBars rows={groupCount(snapshot.recentJobs, 'status').map(([label, count]) => [translatedStatus(label), count])} emptyTitle={t('admin.noJobs')} emptyBody={t('admin.noJobsBody')} /></Panel></View><Panel><SectionHeading title={t('admin.intelligenceReadiness')} body={validated.length ? t('admin.intelligenceEvidencePresent') : t('admin.intelligenceEvidenceMissing')} /><View style={styles.topGap}><Text style={styles.note}>{runningJobs.length ? t('admin.intelligenceJobsActive', { count: runningJobs.length }) : t('admin.intelligenceNoActiveJobs')}</Text></View></Panel></> : null}
    </> : null}
    {tab === 'systems' ? <><View style={styles.filters}><View style={styles.filterSearch}><Field accessibilityLabel={t('admin.searchSystems')} value={search} onChangeText={setSearch} placeholder={t('admin.searchSystems')} /></View><View style={styles.filter}><SelectField label={t('admin.systemStatus')} value={systemStatus} options={[{ value: 'all', label: t('admin.allStatuses') }, ...['live', 'production', 'offline_evaluation'].map((value) => ({ value, label: translatedStatus(value) }))]} onChange={setSystemStatus} /></View></View><Text style={styles.note}>{t('admin.resultCount', { count: systems.length })}</Text>{systems.map((item) => { const copy = item.translations[language]; return <Disclosure key={item.component_id} title={copy.name} summary={`${translatedStatus(item.operational_status)} · ${translatedStatus(item.component_type)}`}><View style={styles.systemContent}><Text style={styles.systemQuestion}>{copy.business_question}</Text><Text style={styles.note}>{copy.production_use}</Text><Text style={styles.systemLabel}>{t('admin.systemDecision')}</Text><Text style={styles.note}>{copy.decision_supported}</Text><Text style={styles.systemLabel}>{t('admin.systemSurface')}</Text><Text style={styles.note}>{copy.product_surface}</Text><Text style={styles.systemLabel}>{t('admin.systemLimitation')}</Text><Text style={styles.note}>{copy.limitation}</Text><Text style={styles.systemLabel}>{t('admin.systemEvidence')}</Text><Text style={styles.note}>{translatedStatus(item.evidence_maturity)} · {translatedStatus(item.data_maturity)}</Text></View></Disclosure>; })}</> : null}
    {tab === 'evidence' && snapshot ? <><RecordList rows={validated} page={1} pageSize={10} onPageChange={() => {}} title={t('admin.validatedRuns')} emptyTitle={t('admin.noValidatedRuns')} emptyBody={t('admin.noValidatedRunsBody')} describe={(row) => ({ title: String(row.experiment_id || row.run_id), summary: `${translatedStatus(row.run_status)} · ${translatedStatus(row.integrity_status)}` })} fields={[{ key: 'run_id', label: t('admin.runId') }, { key: 'evidence_verdict', label: t('admin.evidence'), format: translatedStatus }, { key: 'operational_use', label: t('admin.operationalUse'), format: translatedStatus }, { key: 'primary_metric_leader', label: t('admin.modelLeader') }, { key: 'source_row_count', label: t('admin.sourceRows') }, { key: 'completed_at', label: t('common.updated'), format: dateLabel }]} /><RecordList rows={snapshot.experiments} page={1} pageSize={20} onPageChange={() => {}} title={t('developer.catalog')} emptyTitle={t('developer.noExperiments')} emptyBody={t('developer.noExperimentsBody')} describe={(row) => ({ title: String(row.name || row.experiment_id), summary: String(row.experiment_id || '—') })} fields={[{ key: 'experiment_id', label: t('admin.experimentId') }, { key: 'updated_at', label: t('common.updated'), format: dateLabel }]} /><RecordList rows={snapshot.recentRuns} page={1} pageSize={24} onPageChange={() => {}} title={t('admin.recentMlRuns')} emptyTitle={t('developer.noRuns')} emptyBody={t('developer.noRunsBody')} describe={(row) => ({ title: String(row.run_id || '—'), summary: `${row.experiment_id || '—'} · ${translatedStatus(row.run_status)}` })} fields={[{ key: 'integrity_status', label: t('developer.status'), format: translatedStatus }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /></> : null}
    {tab === 'health' && snapshot ? <><KpiGrid items={[{ label: t('admin.activeJobs'), value: runningJobs.length }, { label: t('admin.failedJobs'), value: failedJobs.length }, { label: t('admin.partialData'), value: snapshot.warnings.length }]} /><RecordList rows={snapshot.recentJobs} page={1} pageSize={24} onPageChange={() => {}} title={t('admin.recentJobs')} emptyTitle={t('admin.noJobs')} emptyBody={t('admin.noJobsBody')} describe={(row) => ({ title: String(row.job_type || row.job_id), summary: `${translatedStatus(row.status)} · ${Number(row.progress_pct || 0).toFixed(0)}%` })} fields={[{ key: 'job_id', label: t('admin.jobId') }, { key: 'current_stage', label: t('admin.stage') }, { key: 'error_code', label: t('admin.errorCode') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /><WarningBox warnings={snapshot.warnings} title={t('admin.partialData')} /></> : null}
    {error ? <Panel><Text style={styles.note}>{error}</Text></Panel> : !snapshot ? <LoadingState /> : null}
    <Panel><Text style={styles.note}>{t('admin.developerLinkHelp')}</Text>{canOpenDeveloper ? <View style={styles.topGap}><Button onPress={onOpenDeveloper}>{t('admin.openDeveloperWorkspace')}</Button></View> : null}</Panel>
  </View>;
}

const styles = StyleSheet.create({ stack: { gap: 17 }, header: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 12, alignItems: 'center' }, headerText: { flex: 1, minWidth: 220 }, twoCols: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, flexPanel: { flexGrow: 1, flexBasis: 320 }, topGap: { marginTop: 12 }, note: { color: colors.muted, fontSize: 12, lineHeight: 18 }, filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, filterSearch: { flexGrow: 2, flexBasis: 260 }, filter: { flexGrow: 1, flexBasis: 180 }, systemContent: { gap: 8 }, systemQuestion: { color: colors.ink, fontSize: 14, fontWeight: '900', lineHeight: 20 }, systemLabel: { color: colors.primary, fontSize: 10, fontWeight: '900', textTransform: 'uppercase', marginTop: 5 } });
