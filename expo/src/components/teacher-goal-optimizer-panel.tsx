import { StyleSheet, Text, View } from 'react-native';

import { Panel } from '@/components/ui';
import type { GoalOptimization } from '@/services/teacher-goal-optimizer';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

const money = (value: number, currency: string) => `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
export function TeacherGoalOptimizerPanel({ optimization, currency, rate = 1 }: { optimization: GoalOptimization; currency: string; rate?: number }) {
  const { t } = useAppPreferences();
  const fmt = (value: number) => money(value * rate, currency);
  const actions = [
    optimization.pricePct >= .005 && t('analyticsPage.optimizer.priceAction', { percent: Math.round(optimization.pricePct * 100), impact: fmt(optimization.scenarios.find((row) => row.key === 'price')?.impact || 0) }),
    optimization.newStudents >= .15 && t('analyticsPage.optimizer.growthAction', { count: Math.max(1, Math.ceil(optimization.newStudents)), impact: fmt(optimization.scenarios.find((row) => row.key === 'growth')?.impact || 0) }),
    optimization.extraUnitsWeek >= .15 && t('analyticsPage.optimizer.capacityAction', { units: optimization.extraUnitsWeek.toFixed(1), impact: fmt(optimization.scenarios.find((row) => row.key === 'capacity')?.impact || 0) }),
    optimization.renewalFocus >= .05 && t('analyticsPage.optimizer.renewalAction', { impact: fmt(optimization.scenarios.find((row) => row.key === 'renewal')?.impact || 0) }),
  ].filter(Boolean);
  return <>
    <View style={styles.metrics}>
      <Panel style={styles.metric}><Text style={styles.value}>{fmt(optimization.baselineProjection)}</Text><Text style={styles.label}>{t('analyticsPage.optimizer.current')}</Text></Panel>
      <Panel style={styles.metric}><Text style={styles.value}>{fmt(optimization.optimizedProjection)}</Text><Text style={styles.label}>{t('analyticsPage.optimizer.suggested')}</Text></Panel>
      <Panel style={styles.metric}><Text style={styles.value}>{fmt(optimization.remainingGap)}</Text><Text style={styles.label}>{t('analyticsPage.optimizer.remaining')}</Text></Panel>
      <Panel style={styles.metric}><Text style={styles.value}>{Math.round(optimization.goalProbability * 100)}% → {Math.round(optimization.optimizedProbability * 100)}%</Text><Text style={styles.label}>{t('analyticsPage.optimizer.likelihood')}</Text></Panel>
    </View>
    <View style={styles.columns}>
      <Panel style={styles.section}><Text style={styles.title}>{t('analyticsPage.optimizer.impact')}</Text>{optimization.scenarios.map((scenario) => <View key={scenario.key} style={styles.row}><Text style={styles.body}>{t(`analyticsPage.optimizer.${scenario.key}`)}</Text><Text style={styles.amount}>{fmt(scenario.impact)}</Text></View>)}</Panel>
      <Panel style={styles.section}><Text style={styles.title}>{t('analyticsPage.optimizer.actions')}</Text>{actions.length ? actions.map((action) => <Text key={String(action)} style={styles.body}>• {action}</Text>) : <Text style={styles.body}>{t('analyticsPage.optimizer.protect')}</Text>}</Panel>
      <Panel style={styles.section}><Text style={styles.title}>{t('analyticsPage.optimizer.priority')}</Text>{optimization.actionStudents.length ? optimization.actionStudents.slice(0, 5).map((student) => <Text key={student.student} style={styles.body}>• {student.student} · {fmt(student.value)} · {t('analyticsPage.optimizer.unitsLeft', { units: student.unitsLeft })}{student.reminderDate ? ` · ${t('analyticsPage.remind')} ${student.reminderDate}` : ''}</Text>) : <Text style={styles.body}>{t('analyticsPage.optimizer.noPriority')}</Text>}</Panel>
    </View>
    <Text style={styles.note}>{t('analyticsPage.optimizer.note')}</Text>
  </>;
}

const styles = StyleSheet.create({
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 12 },
  metric: { flex: 1, minWidth: 180, padding: 15 },
  value: { color: colors.ink, fontSize: 19, fontWeight: '900' },
  label: { color: colors.muted, fontSize: 10, marginTop: 5 },
  columns: { flexDirection: 'row', flexWrap: 'wrap', gap: 11, marginTop: 12 },
  section: { flex: 1, minWidth: 260, gap: 8 },
  title: { color: colors.ink, fontSize: 15, fontWeight: '900', marginBottom: 3 },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  body: { color: colors.muted, fontSize: 11, lineHeight: 17, flexShrink: 1 },
  amount: { color: colors.primary, fontSize: 11, fontWeight: '800' },
  note: { color: colors.subtle, fontSize: 9, marginTop: 10, lineHeight: 14 },
});
