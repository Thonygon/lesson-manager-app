/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell, type AppNotification } from '@/components/app-shell';
import { ActionFeedback, Button, EmptyState, Field, LoadingState, Panel, SelectField, TabRail } from '@/components/ui';
import { Bars, dateLabel, groupCount, KpiGrid, RecordList, SectionHeading, WarningBox } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { type DeveloperWorkspaceData, loadDeveloperWorkspace } from '@/services/privileged-workspaces';
import { checkPythonModelAuthentication, getPythonAffinityModel, pythonModelApiUrl } from '@/services/python-models';
import { colors } from '@/theme';

type DeveloperTab = 'overview' | 'lab' | 'evidence' | 'telemetry' | 'jobs' | 'audit';

export default function DeveloperWorkspaceScreen() {
  const { t } = useAppPreferences();
  const params = useLocalSearchParams<{ tab?: string }>();
  const [data, setData] = useState<DeveloperWorkspaceData | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<DeveloperTab>(() => (['overview', 'lab', 'evidence', 'telemetry', 'jobs', 'audit'].includes(String(params.tab)) ? params.tab as DeveloperTab : 'overview'));
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [experimentId, setExperimentId] = useState('');
  const [pythonCheckBusy, setPythonCheckBusy] = useState(false);
  const [pythonCheckResult, setPythonCheckResult] = useState<{ message: string; tone: 'success' | 'error' } | null>(null);
  const checkPythonConnection = async () => {
    setPythonCheckBusy(true); setPythonCheckResult(null);
    try {
      await checkPythonModelAuthentication();
      try {
        const model = await getPythonAffinityModel();
        setPythonCheckResult({ tone: 'success', message: t('developer.pythonModelReady', { run: model.run_id }) });
      } catch {
        setPythonCheckResult({ tone: 'error', message: t('developer.pythonAuthOnly') });
      }
    } catch {
      setPythonCheckResult({ tone: 'error', message: t('developer.pythonAuthFailed') });
    } finally { setPythonCheckBusy(false); }
  };
  const load = useCallback(async () => {
    setError('');
    try { setData(await loadDeveloperWorkspace()); } catch (reason) { setError(reason instanceof Error ? reason.message : t('developer.loadFailed')); }
  }, [t]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (params.tab && ['overview', 'lab', 'evidence', 'telemetry', 'jobs', 'audit'].includes(params.tab)) setTab(params.tab as DeveloperTab); }, [params.tab]);
  useEffect(() => { setPage(1); }, [search, tab, experimentId]);

  const experiments = data?.experiments.rows ?? [];
  const runs = data?.runs.rows ?? [];
  const experimentOptions = experiments.map((row) => ({ value: String(row.experiment_id), label: String(row.name || row.experiment_id), detail: String(row.business_question || '') }));
  useEffect(() => { if (!experimentId && experimentOptions.length) setExperimentId(experimentOptions[0].value); }, [experimentId, experimentOptions]);
  const selectedRuns = experimentId ? runs.filter((row) => row.experiment_id === experimentId) : runs;
  const selectedExperiment = experiments.find((row) => row.experiment_id === experimentId);
  const needle = search.trim().toLocaleLowerCase();
  const filteredJobs = useMemo(() => (data?.jobs.rows ?? []).filter((row) => !needle || [row.job_id, row.job_type, row.status, row.current_stage, row.error_message].some((value) => String(value ?? '').toLocaleLowerCase().includes(needle))), [data?.jobs.rows, needle]);
  const filteredAudit = useMemo(() => (data?.audit.rows ?? []).filter((row) => !needle || [row.action_type, row.entity_type, row.entity_id, row.reason, row.actor_user_id].some((value) => String(value ?? '').toLocaleLowerCase().includes(needle))), [data?.audit.rows, needle]);

  const unresolvedCount = data?.diagnostics.rows.filter((row) => !row.resolved_at && row.status !== 'resolved').length ?? 0;
  const failedJobs = data?.jobs.rows.filter((row) => ['FAILED', 'ERROR'].includes(String(row.status).toUpperCase())).length ?? 0;
  const developerNotifications: AppNotification[] = [];
  if (unresolvedCount) developerNotifications.push({ key: 'diagnostics', icon: '🩺', title: `${t('developer.unresolved')} · ${unresolvedCount}`, href: '/developer-workspace?tab=telemetry' });
  if (failedJobs) developerNotifications.push({ key: 'jobs', icon: '⚠️', title: `${t('developer.failure')} · ${failedJobs}`, href: '/developer-workspace?tab=jobs' });

  if (!data && !error) return <AppShell title={t('developer.title')} eyebrow={t('developer.eyebrow')}><LoadingState /></AppShell>;
  if (error) return <AppShell title={t('developer.title')} eyebrow={t('developer.eyebrow')}><EmptyState title={t('developer.accessDenied')} body={error} /></AppShell>;
  if (!data) return null;

  const tabs = [
    ['overview', t('developer.tab.overview')], ['lab', t('developer.tab.lab')], ['evidence', t('developer.tab.evidence')],
    ['telemetry', t('developer.tab.telemetry')], ['jobs', t('developer.tab.jobs')], ['audit', t('developer.tab.audit')],
  ].map(([value, label]) => ({ value: value as DeveloperTab, label }));

  return <AppShell title={t('developer.title')} eyebrow={t('developer.eyebrow')} notifications={developerNotifications}>
    <View style={styles.stack}>
      <TabRail items={tabs} value={tab} onChange={setTab} accessibilityLabel={t('developer.title')} />
      {tab === 'overview' ? <>
        <View style={styles.quickGrid}>{([['lab', '🧪', t('developer.tab.lab')], ['evidence', '📈', t('developer.tab.evidence')], ['telemetry', '📡', t('developer.tab.telemetry')], ['jobs', '⚙️', t('developer.tab.jobs')]] as const).map(([target, icon, label]) => <Pressable key={target} accessibilityRole="button" accessibilityLabel={label} onPress={() => setTab(target)} style={({ pressed }) => [styles.quickCard, pressed && styles.quickPressed]}><Text style={styles.quickIcon}>{icon}</Text><Text style={styles.quickLabel}>{label}</Text><Text style={styles.quickArrow}>→</Text></Pressable>)}</View>
        <KpiGrid items={[
          { label: t('developer.experiments'), value: experiments.length }, { label: t('developer.runs'), value: runs.length },
          { label: t('developer.validatedRuns'), value: runs.filter((row) => String(row.run_status).startsWith('VALIDATED')).length },
          { label: t('developer.activeJobs'), value: data.jobs.rows.filter((row) => ['QUEUED', 'RUNNING'].includes(String(row.status))).length },
        ]} />
        <View style={styles.twoCols}><Panel style={styles.flexPanel}><SectionHeading title={t('developer.runStatus')} /><View style={styles.topGap}><Bars rows={groupCount(runs, 'run_status')} emptyTitle={t('developer.noRuns')} emptyBody={t('developer.noRunsBody')} /></View></Panel><Panel style={styles.flexPanel}><SectionHeading title={t('developer.jobStatus')} /><View style={styles.topGap}><Bars rows={groupCount(data.jobs.rows, 'status')} emptyTitle={t('developer.noJobs')} emptyBody={t('developer.noJobsBody')} /></View></Panel></View>
        <RecordList rows={experiments} page={page} pageSize={8} onPageChange={setPage} title={t('developer.catalog')} emptyTitle={t('developer.noExperiments')} emptyBody={t('developer.noExperimentsBody')} describe={(row) => ({ title: String(row.name || row.experiment_id), summary: `${row.experiment_id || '—'} · v${row.experiment_version || '—'}` })} fields={experimentFields(t)} />
      </> : null}

      {tab === 'lab' ? <>
        <SectionHeading title={t('developer.labTitle')} body={t('developer.labBody')} />
        <Panel><SectionHeading title={t('developer.pythonConnection')} body={pythonModelApiUrl()} /><View style={styles.topGap}><Button disabled={pythonCheckBusy} onPress={() => void checkPythonConnection()}>{pythonCheckBusy ? t('common.loading') : t('developer.pythonCheck')}</Button><ActionFeedback message={pythonCheckResult?.message} tone={pythonCheckResult?.tone || 'error'} /></View></Panel>
        <SelectField label={t('developer.selectExperiment')} value={experimentId} options={experimentOptions} placeholder={t('developer.selectExperiment')} onChange={setExperimentId} />
        {selectedExperiment ? <Panel><Text style={styles.question}>{String(selectedExperiment.business_question || selectedExperiment.name)}</Text><View style={styles.meta}><Text style={styles.metaText}>{t('developer.target')}: {String(selectedExperiment.target_version || '—')}</Text><Text style={styles.metaText}>{t('developer.unit')}: {String(selectedExperiment.unit_of_analysis || '—')}</Text><Text style={styles.metaText}>{t('developer.primaryMetric')}: {String(selectedExperiment.primary_metric || '—')}</Text></View></Panel> : null}
        <KpiGrid items={[
          { label: t('developer.runs'), value: selectedRuns.length }, { label: t('developer.eligible'), value: selectedRuns.filter((row) => ['ELIGIBLE', 'QUEUED', 'RUNNING', 'COMPLETED_PENDING_VALIDATION'].includes(String(row.run_status))).length },
          { label: t('developer.students'), value: latestNumber(selectedRuns, 'students_represented') }, { label: t('developer.resources'), value: latestNumber(selectedRuns, 'resources_represented') },
          { label: t('developer.includedRows'), value: latestNumber(selectedRuns, 'included_row_count') }, { label: t('developer.censoredRows'), value: latestNumber(selectedRuns, 'right_censored_count') },
        ]} />
        <Panel><SectionHeading title={t('developer.launchGuard')} body={t('developer.launchGuardBody')} /></Panel>
        <RecordList rows={selectedRuns} page={page} onPageChange={setPage} emptyTitle={t('developer.noRuns')} emptyBody={t('developer.noRunsBody')} describe={runDescription} fields={runFields(t)} />
      </> : null}

      {tab === 'evidence' ? <>
        <SectionHeading title={t('developer.evidenceTitle')} body={t('developer.evidenceBody')} />
        <SelectField label={t('developer.selectExperiment')} value={experimentId} options={experimentOptions} placeholder={t('developer.selectExperiment')} onChange={setExperimentId} />
        <RecordList rows={selectedRuns} page={page} pageSize={8} onPageChange={setPage} title={t('developer.runs')} emptyTitle={t('developer.noRuns')} emptyBody={t('developer.noRunsBody')} describe={runDescription} fields={runFields(t)} />
        <RecordList rows={data.models.rows.filter((row) => !selectedRuns.length || selectedRuns.some((run) => run.run_id === row.run_id))} page={page} pageSize={8} onPageChange={setPage} title={t('developer.models')} emptyTitle={t('developer.noModels')} emptyBody={t('developer.noModelsBody')} describe={(row) => ({ title: String(row.model_name || row.id), summary: `${row.execution_status || '—'} · ${row.run_id || '—'}` })} fields={[{ key: 'run_id', label: t('developer.runId') }, { key: 'execution_status', label: t('developer.status') }, { key: 'holdout_metrics_json', label: t('developer.holdoutMetrics') }, { key: 'confidence_intervals_json', label: t('developer.confidenceIntervals') }, { key: 'parameters_json', label: t('developer.parameters') }, { key: 'failure_message', label: t('developer.failure') }]} />
        <RecordList rows={data.artifacts.rows.filter((row) => !selectedRuns.length || selectedRuns.some((run) => run.run_id === row.run_id))} page={page} pageSize={8} onPageChange={setPage} title={t('developer.artifacts')} emptyTitle={t('developer.noArtifacts')} emptyBody={t('developer.noArtifactsBody')} describe={(row) => ({ title: String(row.artifact_type || row.id), summary: `${row.run_id || '—'} · ${row.content_type || '—'}` })} fields={[{ key: 'storage_bucket', label: t('developer.bucket') }, { key: 'storage_path', label: t('developer.path') }, { key: 'checksum', label: t('developer.checksum') }, { key: 'size_bytes', label: t('developer.size') }, { key: 'contains_sensitive_data', label: t('developer.sensitive') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} />
      </> : null}

      {tab === 'telemetry' ? <>
        <SectionHeading title={t('developer.telemetryTitle')} body={t('developer.telemetryBody')} />
        <KpiGrid items={[
          { label: t('developer.recommendationEvents'), value: data.recommendationEvents.rows.length },
          { label: t('developer.diagnosticGroups'), value: data.diagnostics.rows.length },
          { label: t('developer.unresolved'), value: data.diagnostics.rows.filter((row) => !row.resolved_at && row.status !== 'resolved').length },
          { label: t('developer.surfaces'), value: new Set(data.recommendationEvents.rows.map((row) => String(row.surface || row.source || 'unknown'))).size },
        ]} />
        <View style={styles.twoCols}><Panel style={styles.flexPanel}><SectionHeading title={t('developer.eventsByType')} /><View style={styles.topGap}><Bars rows={groupFirst(data.recommendationEvents.rows, ['event_type', 'action', 'event_name'])} emptyTitle={t('common.noResults')} emptyBody={t('developer.noTelemetry')} /></View></Panel><Panel style={styles.flexPanel}><SectionHeading title={t('developer.diagnosticsByStatus')} /><View style={styles.topGap}><Bars rows={groupFirst(data.diagnostics.rows, ['status', 'severity', 'event_type'])} emptyTitle={t('common.noResults')} emptyBody={t('developer.noDiagnostics')} /></View></Panel></View>
        <RecordList rows={data.diagnostics.rows} page={page} onPageChange={setPage} emptyTitle={t('developer.noDiagnostics')} emptyBody={t('developer.noDiagnosticsBody')} describe={(row) => ({ title: String(row.event_type || row.fingerprint || row.id), summary: `${row.severity || row.status || '—'} · ${dateLabel(row.last_seen_at || row.created_at)}` })} fields={Object.keys(data.diagnostics.rows[0] ?? {}).slice(0, 12).map((key) => ({ key, label: key.replaceAll('_', ' '), ...(key.endsWith('_at') ? { format: dateLabel } : {}) }))} />
      </> : null}

      {tab === 'jobs' ? <><SectionHeading title={t('developer.jobsTitle')} body={t('developer.jobsBody')} /><Field value={search} onChangeText={setSearch} placeholder={t('developer.searchJobs')} accessibilityLabel={t('developer.searchJobs')} /><RecordList rows={filteredJobs} page={page} onPageChange={setPage} emptyTitle={t('developer.noJobs')} emptyBody={t('developer.noJobsBody')} describe={(row) => ({ title: String(row.job_id || row.id), summary: `${row.job_type || '—'} · ${row.status || '—'} · ${Number(row.progress_pct || 0)}%` })} fields={[{ key: 'job_version', label: t('developer.version') }, { key: 'status', label: t('developer.status') }, { key: 'priority', label: t('developer.priority') }, { key: 'current_stage', label: t('developer.stage') }, { key: 'requested_by_role', label: t('developer.requestedBy') }, { key: 'requested_at', label: t('developer.requestedAt'), format: dateLabel }, { key: 'heartbeat_at', label: t('developer.heartbeat'), format: dateLabel }, { key: 'error_message', label: t('developer.failure') }]} /></> : null}
      {tab === 'audit' ? <><SectionHeading title={t('developer.auditTitle')} body={t('developer.auditBody')} /><Field value={search} onChangeText={setSearch} placeholder={t('developer.searchAudit')} accessibilityLabel={t('developer.searchAudit')} /><RecordList rows={filteredAudit} page={page} onPageChange={setPage} emptyTitle={t('developer.noAudit')} emptyBody={t('developer.noAuditBody')} describe={(row) => ({ title: String(row.action_type || row.id), summary: `${row.entity_type || '—'} · ${row.entity_id || '—'} · ${dateLabel(row.created_at)}` })} fields={[{ key: 'actor_user_id', label: t('developer.actor') }, { key: 'actor_roles', label: t('developer.roles') }, { key: 'entity_type', label: t('developer.entity') }, { key: 'entity_id', label: t('developer.entityId') }, { key: 'reason', label: t('developer.reason') }, { key: 'before_json', label: t('developer.before') }, { key: 'after_json', label: t('developer.after') }, { key: 'created_at', label: t('common.created'), format: dateLabel }]} /></> : null}
      <WarningBox warnings={data.warnings} title={t('developer.partialData')} />
    </View>
  </AppShell>;
}

function latestNumber(rows: Record<string, unknown>[], field: string) { return Number(rows[0]?.[field] || 0).toLocaleString(); }
function runDescription(row: Record<string, unknown>) { return { title: String(row.run_id || row.id), summary: `${row.run_status || '—'} · ${row.integrity_status || '—'} · ${dateLabel(row.created_at)}` }; }
function experimentFields(t: (key: string) => string) { return [{ key: 'business_question', label: t('developer.businessQuestion') }, { key: 'target_version', label: t('developer.target') }, { key: 'unit_of_analysis', label: t('developer.unit') }, { key: 'primary_metric', label: t('developer.primaryMetric') }, { key: 'is_active', label: t('developer.active') }, { key: 'definition_json', label: t('developer.definition') }]; }
function runFields(t: (key: string) => string) { return [{ key: 'experiment_version', label: t('developer.version') }, { key: 'environment', label: t('developer.environment') }, { key: 'code_version', label: t('developer.codeVersion') }, { key: 'dataset_fingerprint', label: t('developer.dataset') }, { key: 'source_row_count', label: t('developer.sourceRows') }, { key: 'included_row_count', label: t('developer.includedRows') }, { key: 'primary_metric_leader', label: t('developer.metricLeader') }, { key: 'overall_model_selection', label: t('developer.modelSelection') }, { key: 'maturity_verdict', label: t('developer.maturity') }, { key: 'evidence_verdict', label: t('developer.evidenceVerdict') }, { key: 'validation_notes', label: t('developer.validationNotes') }, { key: 'failure_message', label: t('developer.failure') }]; }
function groupFirst(rows: Record<string, unknown>[], fields: string[]): [string, number][] { const field = fields.find((candidate) => rows.some((row) => row[candidate])); return field ? groupCount(rows, field) : []; }

const styles = StyleSheet.create({ quickGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, quickCard: { flexGrow: 1, flexBasis: 180, minWidth: 160, flexDirection: 'row', alignItems: 'center', gap: 10, padding: 15, borderWidth: 1, borderColor: colors.line, borderRadius: 16, backgroundColor: colors.surface }, quickPressed: { opacity: 0.7 }, quickIcon: { fontSize: 20 }, quickLabel: { flex: 1, color: colors.ink, fontSize: 12, fontWeight: '800' }, quickArrow: { color: colors.primary, fontSize: 16, fontWeight: '900' }, stack: { gap: 18 }, topGap: { marginTop: 16 }, twoCols: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, flexPanel: { flexGrow: 1, flexBasis: 320 }, question: { color: colors.ink, fontSize: 18, lineHeight: 26, fontWeight: '800' }, meta: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 14 }, metaText: { color: colors.muted, fontSize: 12, fontWeight: '700' } });
