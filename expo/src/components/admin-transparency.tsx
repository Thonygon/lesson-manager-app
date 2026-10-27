import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Disclosure, Field, HelpIcon, SelectField } from '@/components/ui';
import { requireSupabase } from '@/lib/supabase';
import { useAppPreferences } from '@/providers/app-preferences';
import { invalidateAdminAiSnapshot, type AdminAiSnapshot } from '@/services/admin-ai';
import { colors } from '@/theme';

type System = { id: string; status: string; copy: { name: string; limitation: string }; row: Record<string, unknown> };
const value = (item: unknown) => item === null || item === undefined || item === '' ? '' : String(item);
const object = (item: unknown): Record<string, unknown> => item && typeof item === 'object' && !Array.isArray(item) ? item as Record<string, unknown> : {};

export function AdminModelCards({ systems, snapshot, onRefresh }: { systems: System[]; snapshot: AdminAiSnapshot | null; onRefresh: () => void }) {
  const { t } = useAppPreferences();
  const [componentId, setComponentId] = useState('');
  const [versionInput, setVersionInput] = useState('');
  const [reviewStatus, setReviewStatus] = useState('reviewed');
  const [reviewReason, setReviewReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ message: string; tone: 'success' | 'error' } | null>(null);
  const missing = t('transparency.notRecorded');
  const field = (label: string, content: unknown) => `${t(label)}: ${value(content) || missing}`;
  const versionFor = (system: System) => {
    const exposure = (snapshot?.recommendationDecisions || []).find((row) => row.model_component_id === system.id);
    const run = (snapshot?.validatedRuns || []).find((row) => row.run_id === system.row.validated_run_id || row.experiment_id === system.id);
    return value(exposure?.model_version || run?.code_version || run?.run_id);
  };
  const submitReview = async () => {
    if (!componentId || !versionInput.trim() || reviewReason.trim().length < 8) { setFeedback({ tone: 'error', message: t('transparency.reviewRequired') }); return; }
    setBusy(true); setFeedback(null);
    try {
      const { data, error } = await requireSupabase().rpc('classio_review_model_card', { p_component_id: componentId, p_model_version: versionInput.trim(), p_status: reviewStatus, p_reason: reviewReason.trim() });
      if (error || data !== true) throw error || new Error(t('transparency.reviewFailed'));
      invalidateAdminAiSnapshot(); onRefresh(); setFeedback({ tone: 'success', message: t('transparency.reviewSaved') }); setReviewReason('');
    } catch (error) { setFeedback({ tone: 'error', message: error instanceof Error ? error.message : t('transparency.reviewFailed') }); }
    finally { setBusy(false); }
  };
  return <Disclosure title={t('transparency.modelCards')} summary={t('transparency.modelCardsScope')}>
    <View style={styles.list}>{systems.map((system) => {
      const run = (snapshot?.validatedRuns || []).find((row) => row.run_id === system.row.validated_run_id || row.experiment_id === system.id);
      const model = (snapshot?.modelResults || []).find((row) => row.run_id === run?.run_id && (!run?.human_review_recommended_model_name || row.model_name === run.human_review_recommended_model_name));
      const exposure = (snapshot?.recommendationDecisions || []).find((row) => row.model_component_id === system.id);
      const review = (snapshot?.modelReviews || []).find((row) => row.component_id === system.id && row.model_version === versionFor(system));
      const parameters = object(model?.parameters_json);
      const holdout = object(model?.holdout_metrics_json);
      const segments = object(holdout.by_segment || holdout.segments);
      const segmentSummary = Object.keys(segments).length ? Object.entries(segments).slice(0, 8).map(([key, metrics]) => `${key}: ${JSON.stringify(metrics)}`).join('; ') : missing;
      const version = value(exposure?.model_version || run?.code_version || run?.run_id) || missing;
      const window = run?.source_start_at && run?.source_end_at ? `${value(run.source_start_at)} – ${value(run.source_end_at)}` : missing;
      const details = [field('transparency.version', version), field('transparency.dataWindow', window), field('transparency.segmentMetrics', segmentSummary),
        field('transparency.threshold', parameters.threshold || holdout.threshold), field('transparency.owner', review?.reviewed_by || run?.human_reviewed_by),
        field('transparency.reviewedAt', review?.reviewed_at || run?.human_reviewed_at), field('transparency.retirement', review?.status === 'retired' ? t('transparency.reviewStatus.retired') : review?.status === 'reviewed' ? t('transparency.notRetired') : missing),
        field('transparency.reviewReason', review?.review_reason),
        `${t('admin.systemLimitation')}: ${system.copy.limitation}`].join('\n\n');
      return <View key={system.id} style={styles.row}><View style={styles.copy}><Text style={styles.rowTitle}>{system.copy.name}</Text><Text style={styles.meta}>{version} · {system.status}</Text></View><HelpIcon title={`${t('transparency.modelCard')}: ${system.copy.name}`}>{details}</HelpIcon></View>;
    })}</View>
    {systems.length ? <Disclosure title={t('transparency.recordReview')} summary={t('transparency.reviewScope')}><View style={styles.reviewForm}>
      <SelectField label={t('transparency.modelCard')} value={componentId} onChange={(next) => { setComponentId(next); setVersionInput(versionFor(systems.find((item) => item.id === next) || systems[0])); }} options={systems.map((system) => ({ value: system.id, label: system.copy.name }))} />
      <Field accessibilityLabel={t('transparency.version')} placeholder={t('transparency.version')} value={versionInput} onChangeText={setVersionInput} />
      <SelectField label={t('transparency.retirement')} value={reviewStatus} onChange={setReviewStatus} options={['reviewed', 'retired'].map((status) => ({ value: status, label: t(`transparency.reviewStatus.${status}`) }))} />
      <Field accessibilityLabel={t('transparency.reviewReason')} placeholder={t('transparency.reviewReason')} value={reviewReason} onChangeText={setReviewReason} />
      <Button disabled={busy} onPress={() => void submitReview()}>{t('transparency.saveReview')}</Button>
      <ActionFeedback message={feedback?.message} tone={feedback?.tone || 'error'} onDismiss={(shown) => setFeedback((current) => current?.message === shown ? null : current)} />
    </View></Disclosure> : null}
    {(snapshot?.runtimeApprovals || []).length ? <View style={styles.list}><Text style={styles.subtitle}>{t('transparency.generativeModels')}</Text>{snapshot!.runtimeApprovals.map((approval, index) => {
      const name = `${value(approval.provider)} · ${value(approval.model)}`;
      const details = [field('transparency.version', approval.prompt_version), field('admin.systemSurface', approval.surface),
        field('transparency.dataWindow', t('transparency.notApplicable')), field('transparency.segmentMetrics', missing),
        field('transparency.threshold', t('transparency.notApplicable')), field('transparency.owner', approval.reviewed_by),
        field('transparency.reviewedAt', approval.reviewed_at), field('transparency.retirement', approval.status)].join('\n\n');
      return <View key={`${name}:${approval.prompt_version}:${index}`} style={styles.row}><View style={styles.copy}><Text style={styles.rowTitle}>{name}</Text><Text style={styles.meta}>{value(approval.surface)} · {value(approval.status)}</Text></View><HelpIcon title={`${t('transparency.modelCard')}: ${name}`}>{details}</HelpIcon></View>;
    })}</View> : null}
  </Disclosure>;
}

export function AdminDecisionTrail({ snapshot }: { snapshot: AdminAiSnapshot | null }) {
  const { t } = useAppPreferences();
  const recommendations = (snapshot?.recommendationDecisions || []).slice(0, 20);
  const generations = (snapshot?.generationDecisions || []).slice(0, 10);
  const format = (item: unknown) => value(item) || t('transparency.notRecorded');
  return <Disclosure title={t('transparency.decisionTrail')} summary={t('transparency.decisionTrailHelp')}><View style={styles.heading}><Text style={styles.title}>{t('transparency.decisionTrail')}</Text><HelpIcon title={t('transparency.decisionTrail')}>{t('transparency.decisionTrailHelp')}</HelpIcon></View>
    <View style={styles.list}>{recommendations.map((row) => <Disclosure key={value(row.id)} title={`${format(row.resource)} · ${format(row.surface)}`} summary={`${format(row.model_component_id)} · ${format(row.shown_at)}`}>
      <Text style={styles.body}>{`${t('transparency.version')}: ${format(row.model_version)} · ${t('transparency.position')}: ${format(row.position)} · ${t('transparency.score')}: ${format(row.final_score)}`}</Text>
      <Text style={styles.body}>{`${t('transparency.candidates')}: ${Array.isArray(row.displayed_candidates) && row.displayed_candidates.length ? row.displayed_candidates.join(', ') : format(null)}`}</Text>
      <Text style={styles.body}>{`${t('transparency.explanationCodes')}: ${Array.isArray(row.reason_codes) && row.reason_codes.length ? row.reason_codes.join(', ') : format(null)}`}</Text>
      <Text style={styles.body}>{`${t('transparency.feedback')}: ${JSON.stringify(row.feedback || [])} · ${t('transparency.actions')}: ${JSON.stringify(row.events || [])}`}</Text>
      <Text style={styles.meta}>{t('transparency.decisionId')}: {format(row.id)}</Text>
    </Disclosure>)}
    {generations.map((row) => <Disclosure key={value(row.id)} title={`${t('transparency.generation')}: ${format(row.feature_name)}`} summary={`${format(row.surface)} · ${format(row.status)} · ${format(row.shown_at)}`}>
      <Text style={styles.body}>{`${t('transparency.version')}: ${format(row.prompt_version)} · ${t('transparency.modelCard')}: ${format(row.model_name)}`}</Text>
      <Text style={styles.body}>{`${t('transparency.providerAttempts')}: ${JSON.stringify(row.attempts || [])}`}</Text>
      <Text style={styles.body}>{`${t('transparency.feedback')}: ${JSON.stringify(row.feedback || {})}`}</Text>
      <Text style={styles.meta}>{t('transparency.decisionId')}: {format(row.id)} · {format(row.resource)}</Text>
    </Disclosure>)}
    {!recommendations.length && !generations.length ? <Text style={styles.body}>{t('transparency.noDecisions')}</Text> : null}</View>
  </Disclosure>;
}

const styles = StyleSheet.create({ title: { color: colors.ink, fontSize: 17, fontWeight: '900' }, subtitle: { color: colors.ink, fontSize: 13, fontWeight: '800' }, heading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 }, body: { color: colors.muted, fontSize: 12, lineHeight: 19, marginTop: 7 }, list: { gap: 8, marginTop: 13 }, reviewForm: { gap: 10 }, row: { flexDirection: 'row', alignItems: 'center', gap: 12, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 9 }, copy: { flex: 1 }, rowTitle: { color: colors.ink, fontSize: 12, fontWeight: '800' }, meta: { color: colors.muted, fontSize: 10, marginTop: 4 } });
