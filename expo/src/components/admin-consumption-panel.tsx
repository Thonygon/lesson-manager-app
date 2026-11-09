import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { LoadingState, Panel, TabRail } from '@/components/ui';
import { KpiGrid, SectionHeading } from '@/components/workspace-ui';
import { getAdminConsumption, type ConsumptionDetail, type ConsumptionPeriod } from '@/services/admin-consumption';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

export function AdminConsumptionPanel({ userId, plans }: { userId: string; plans: Record<string, unknown>[] }) {
  const { t } = useAppPreferences();
  const [detail, setDetail] = useState<ConsumptionDetail | null>(null);
  const [error, setError] = useState('');
  const [period, setPeriod] = useState<ConsumptionPeriod['label']>('month');
  useEffect(() => {
    let active = true;
    void getAdminConsumption(userId).then((result) => { if (active) setDetail(result); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : t('admin.usageUnavailable')); });
    return () => { active = false; };
  }, [userId, t]);
  if (error) return <Panel><Text style={styles.error}>{error}</Text></Panel>;
  if (!detail) return <Panel><LoadingState /></Panel>;
  const current = detail.summary.periods.find((item) => item.label === period);
  const subscription = detail.subscription;
  const activeSubscription = subscription?.manual_override === true || ['active', 'trialing'].includes(String(subscription?.subscription_status || ''));
  const planId = String(activeSubscription ? subscription?.plan_id || 'free' : detail.account.current_plan || 'free');
  const plan = plans.find((item) => String(item.id) === planId);
  const limits = plan?.limits_json && typeof plan.limits_json === 'object' ? plan.limits_json as Record<string, unknown> : {};
  const quotaLimit = limits.ai_generations == null ? NaN : Number(limits.ai_generations);
  const fallbackLimit = planId === 'teacher_pro' ? 250 : planId === 'school' ? 2000 : planId === 'beta_lifetime' ? 1000 : 10;
  const limitLabel = Number.isSafeInteger(quotaLimit) && quotaLimit >= 0 ? String(quotaLimit) : String(fallbackLimit);
  return <Panel style={styles.panel}>
    <SectionHeading title={t('admin.usageTitle')} body={`${String(detail.account.display_name || detail.account.email || userId)} · ${t('admin.usageAsOf')} ${new Date(detail.summary.as_of).toLocaleString()} · UTC`} />
    <View style={styles.meta}><Text style={styles.metaText}>{t('admin.plan')}: {String(plan?.name || planId)}</Text><Text style={styles.metaText}>{t('admin.subscriptionStatus')}: {t(`admin.value.${String(subscription?.subscription_status || detail.account.subscription_status || 'free')}`)}</Text></View>
    <TabRail items={(['month', 'year', 'all'] as const).map((value) => ({ value, label: t(`admin.usagePeriod.${value}`) }))} value={period} onChange={setPeriod} />
    {current ? <><KpiGrid items={[
      { label: t('admin.usageDelivered'), value: current.delivered_resources },
      { label: t('admin.usageAiEvents'), value: current.ai_operations },
      { label: t('admin.usageAttempts'), value: current.provider_attempts },
      { label: t('admin.usageRefinements'), value: current.refinements },
      { label: t('admin.usageProgramUnits'), value: current.program_unit_events },
      { label: t('admin.usageImages'), value: current.image_events },
      { label: t('admin.usagePdf'), value: current.pdf_handoffs },
      { label: t('admin.usageWord'), value: current.word_handoffs },
      { label: t('admin.usageFailed'), value: current.failed_operations + current.failed_exports },
    ]} />
      <Text style={styles.note}>{period === 'month' ? `${t('admin.usageQuota')}: ${current.quota_used} / ${limitLabel}. ` : ''}{t('admin.usageMethod')}</Text>
      <Text style={styles.subheading}>{t('admin.usageRecent')}</Text>
      {(detail.operations || []).slice(0, 12).map((operation) => <View key={String(operation.operation_id)} style={styles.event}><Text style={styles.eventTitle}>{String(operation.feature_name).replaceAll('_', ' ')} · {t(`admin.value.${String(operation.status)}`)}</Text><Text style={styles.note}>{new Date(String(operation.started_at)).toLocaleString()} · {operation.charged === true ? t('admin.usageCharged') : t('admin.usageEventOnly')}{operation.error_kind ? ` · ${String(operation.error_kind)}` : ''}</Text></View>)}
      {(detail.exports || []).slice(0, 6).map((event) => <View key={String(event.event_id)} style={styles.event}><Text style={styles.eventTitle}>{String(event.format).toUpperCase()} · {String(event.document_kind).replaceAll('_', ' ')}</Text><Text style={styles.note}>{new Date(String(event.started_at)).toLocaleString()} · {String(event.status).replaceAll('_', ' ')}</Text></View>)}
    </> : null}
  </Panel>;
}

const styles = StyleSheet.create({ panel: { gap: 14 }, meta: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, metaText: { color: colors.ink, fontSize: 13, fontWeight: '700' }, subheading: { color: colors.ink, fontSize: 15, fontWeight: '800' }, event: { borderTopWidth: 1, borderColor: colors.line, paddingTop: 8, gap: 3 }, eventTitle: { color: colors.ink, fontSize: 13, fontWeight: '700' }, note: { color: colors.muted, fontSize: 12, lineHeight: 18 }, error: { color: colors.danger, fontSize: 13 } });
