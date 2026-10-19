import type { AnalyticsForecast, AnnualRenewalProjection } from '@/services/teacher-analytics-forecast';
import type { TeacherDataset } from '@/services/teacher-insights';

type ActionStudent = { student: string; value: number; unitsLeft: number; reminderDate: string; finishDate: string; dueNow: boolean };
type Scenario = { key: 'price' | 'growth' | 'capacity' | 'renewal'; impact: number; value: number };
export type GoalOptimization = {
  baselineProjection: number; optimizedProjection: number; gap: number; remainingGap: number;
  goalProbability: number; optimizedProbability: number; pricePct: number; newStudents: number;
  extraUnitsWeek: number; renewalFocus: number; avgPackageValue: number; effectiveRate: number;
  weeksLeft: number; renewalPool: number; riskRate: number; actionStudents: ActionStudent[]; scenarios: Scenario[];
};

const median = (values: number[]) => { const sorted = [...values].sort((a, b) => a - b); const mid = Math.floor(sorted.length / 2); return sorted.length ? sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2 : 0; };
const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const probability = (projection: number, goal: number, risk: number) => goal <= 0 ? 0 : Math.max(0, Math.min(.99, Math.max(0, Math.min(1.25, projection / goal)) * Math.max(.55, 1 - Math.max(0, Math.min(.45, risk)))));

/** Equivalent to Streamlit helpers/goal_optimizer.py for one selected currency. */
export function buildGoalOptimization(data: TeacherDataset, forecast: AnalyticsForecast[], projection: AnnualRenewalProjection, currency: string, goal: number, now = new Date()): GoalOptimization {
  const thirtyDays = dateKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 30));
  const yearEnd = new Date(now.getFullYear(), 11, 31);
  const weeksLeft = Math.max(1, Math.floor((yearEnd.getTime() - new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) / 86400000) / 7);
  const payments = data.payments.filter((row) => String(row.currency || 'TRY') === currency && String(row.student || '').trim());
  const byStudent = new Map<string, typeof payments>();
  for (const payment of payments) {
    const student = String(payment.student).trim();
    byStudent.set(student, [...(byStudent.get(student) || []), payment]);
  }
  const baselines = new Map<string, number>();
  for (const [student, history] of byStudent) {
    const recent = [...history].sort((a, b) => String(a.payment_date || '').localeCompare(String(b.payment_date || ''))).slice(-3);
    const value = median(recent.map((row) => Number(row.paid_amount) || 0));
    if (value > 0) baselines.set(student, value);
  }
  const selectedForecast = forecast.filter((row) => row.currency === currency && row.isActive !== false);
  const actionStudents = selectedForecast.map((row) => {
    const value = baselines.get(row.student) || 0;
    const soon = !!row.estimatedFinishDate && row.estimatedFinishDate <= thirtyDays;
    const priority = value + (row.dueNow ? value * .45 : 0) + (soon ? value * .25 : 0) + (row.remaining <= 2 ? value * .20 : 0);
    return { student: row.student, value, unitsLeft: row.remaining, reminderDate: row.reminderDate || '', finishDate: row.estimatedFinishDate || '', dueNow: row.dueNow, priority };
  }).filter((row) => row.student && row.value > 0).sort((a, b) => b.priority - a.priority || b.value - a.value).slice(0, 6).map(({ priority: _priority, ...row }) => row);
  const expectedFuture = Math.max(0, projection.expectedFuture);
  const avgPackageValue = baselines.size ? median([...baselines.values()]) : expectedFuture / 4;
  const renewalPool = actionStudents.reduce((sum, row) => sum + row.value, 0) || expectedFuture * .18;
  const risky = selectedForecast.filter((row) => row.remaining <= 2).length + selectedForecast.filter((row) => row.dueNow).length;
  const riskRate = Math.min(.42, .08 + risky / Math.max(1, selectedForecast.length) * .20);
  const paid = payments.reduce((sum, row) => sum + (Number(row.paid_amount) || 0), 0);
  const delivered = data.lessons.reduce((sum, row) => sum + (Number(row.number_of_lesson) || 0), 0);
  const effectiveRate = delivered > 0 ? paid / delivered : 0;
  const baselineProjection = Math.max(0, projection.projected);
  const normalizedGoal = Math.max(0, Number(goal) || 0);
  const gap = Math.max(0, normalizedGoal - baselineProjection);
  const factors = [baselineProjection, Math.max(0, avgPackageValue), Math.max(0, effectiveRate * weeksLeft), Math.max(0, renewalPool)];
  const upper = [.18, 8, 10, 1]; const effortWeights = [.10, .45, .30, .18];
  const x = gap > 0 ? [.03, .75, 1, .35] : [0, 0, 0, 0];
  const loss = (values: number[]) => {
    const remaining = Math.max(0, gap - values.reduce((sum, value, i) => sum + value * factors[i], 0));
    const effort = values.reduce((sum, value, i) => sum + effortWeights[i] * (value / Math.max(.0001, upper[i])) ** 2 * Math.max(1, gap) ** 2, 0);
    return remaining ** 2 + effort;
  };
  if (gap > 0) for (let iteration = 0; iteration < 220; iteration += 1) {
    const current = loss(x);
    const gradient = x.map((_, i) => {
      const step = Math.max(.0005, upper[i] * .001);
      const trial = [...x]; trial[i] = Math.min(upper[i], trial[i] + step);
      return (loss(trial) - current) / step;
    });
    for (let i = 0; i < 4; i += 1) x[i] = Math.max(0, Math.min(upper[i], x[i] - .00000008 * gradient[i]));
  }
  const impacts = x.map((value, i) => value * factors[i]);
  const optimizedProjection = baselineProjection + impacts.reduce((sum, value) => sum + value, 0);
  const scenarios = (['price', 'growth', 'capacity', 'renewal'] as const).map((key, i) => ({ key, impact: impacts[i], value: x[i] })).sort((a, b) => b.impact - a.impact);
  return { baselineProjection, optimizedProjection, gap, remainingGap: Math.max(0, normalizedGoal - optimizedProjection), goalProbability: probability(baselineProjection, normalizedGoal, riskRate), optimizedProbability: probability(optimizedProjection, normalizedGoal, Math.max(0, riskRate - x[3] * .18)), pricePct: x[0], newStudents: x[1], extraUnitsWeek: x[2], renewalFocus: x[3], avgPackageValue, effectiveRate, weeksLeft, renewalPool, riskRate, actionStudents, scenarios };
}
