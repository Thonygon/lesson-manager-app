import type { PackageInsight, TeacherDataset } from '@/services/teacher-insights';

export type AnalyticsForecast = PackageInsight & {
  isActive: boolean;
  unitsPerDay: number;
  daysToFinish: number;
  reminderDate: string;
  dueNow: boolean;
};
export type AnnualRenewalProjection = { ytd: number; expectedFuture: number; projected: number; counted: number; missingBaseline: number };

const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const parseDay = (value: unknown) => { const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || '')); return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null; };
const addDays = (date: Date, days: number) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
const halfEven = (value: number) => { const floor = Math.floor(value); const fraction = value - floor; return fraction === 0.5 ? floor + (floor % 2) : Math.round(value); };
const isFree = (note: unknown) => ['[FREE]', '[DEMO]', '[DONT COUNT]', "[DON'T COUNT]"].some((tag) => String(note || '').toUpperCase().includes(tag));
const median = (values: number[]) => { const sorted = [...values].sort((a, b) => a - b); const middle = Math.floor(sorted.length / 2); return sorted.length ? sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2 : 0; };

/** Port of the burn-rate and expiry rules in Streamlit helpers/forecast.py. */
export function buildAnalyticsForecast(data: TeacherDataset, packages: PackageInsight[], bufferDays = 0, now = new Date()): AnalyticsForecast[] {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const lookback = addDays(today, -56);
  const activeCutoff = addDays(today, -183);
  const recentUnits = new Map<string, number>();
  const lastLesson = new Map<string, Date>();
  for (const lesson of data.lessons) {
    const student = String(lesson.student || '').trim();
    const day = parseDay(lesson.lesson_date);
    if (!student || !day) continue;
    if (!lastLesson.has(student) || day > lastLesson.get(student)!) lastLesson.set(student, day);
    if (day >= lookback) recentUnits.set(student, (recentUnits.get(student) || 0) + (isFree(lesson.note) ? 0 : Math.trunc(Number(lesson.number_of_lesson) || 0)));
  }
  const globalMedian = median([...recentUnits.values()].map((units) => units / 56));
  return packages.flatMap((row) => {
    const lastPayment = parseDay(row.paymentDate);
    const recentLesson = lastLesson.get(row.student);
    const isActive = Boolean((recentLesson && recentLesson >= activeCutoff) || (lastPayment && lastPayment >= activeCutoff));
    if (row.remaining <= 0 && !(recentLesson && recentLesson >= activeCutoff) && !(lastPayment && lastPayment >= activeCutoff)) return [];
    const personalRate = (recentUnits.get(row.student) || 0) / 56;
    const rawRate = personalRate > 0 ? personalRate : globalMedian > 0 ? globalMedian : 0.1;
    const unitsPerDay = Math.round(rawRate * 100) / 100;
    const daysToFinish = Math.round(Math.min(3650, Math.max(0, row.remaining / rawRate)) * 10) / 10;
    const estimated = row.remaining <= 0 ? today : addDays(today, halfEven(Math.min(3650, Math.max(0, row.remaining / rawRate))));
    const expiry = parseDay(row.expiryDate);
    const finish = expiry && expiry < estimated ? expiry : estimated;
    const reminder = addDays(finish, -Math.max(0, Math.trunc(bufferDays)));
    return [{ ...row, isActive, estimatedFinishDate: dateKey(finish), unitsPerDay, daysToFinish, reminderDate: dateKey(reminder), dueNow: reminder <= today }];
  }).sort((a, b) => a.reminderDate.localeCompare(b.reminderDate) || a.remaining - b.remaining || a.student.localeCompare(b.student));
}

/** Mirrors the student-based YTD plus simulated renewals in app_page_analytics.py. */
export function buildAnnualRenewalProjection(data: TeacherDataset, forecast: AnalyticsForecast[], currency: string, now = new Date()): AnnualRenewalProjection {
  const year = now.getFullYear();
  const payments = data.payments.filter((row) => String(row.currency || 'TRY') === currency);
  const ytd = payments.filter((row) => parseDay(row.payment_date)?.getFullYear() === year).reduce((sum, row) => sum + (Number(row.paid_amount) || 0), 0);
  const byStudent = new Map<string, typeof payments>();
  for (const payment of payments) {
    const student = String(payment.student || '').trim();
    if (student && parseDay(payment.payment_date)) byStudent.set(student, [...(byStudent.get(student) || []), payment]);
  }
  const yearEnd = new Date(year, 11, 31);
  let expectedFuture = 0; let counted = 0; let missingBaseline = 0;
  for (const row of forecast) {
    if (row.currency !== currency || !row.isActive) continue;
    const history = [...(byStudent.get(row.student) || [])].sort((a, b) => String(a.payment_date).localeCompare(String(b.payment_date)) || Number(a.id || 0) - Number(b.id || 0));
    const baseline = median(history.slice(-3).map((payment) => Number(payment.paid_amount) || 0));
    if (baseline <= 0) { missingBaseline += 1; continue; }
    const finish = parseDay(row.estimatedFinishDate);
    if (!finish) continue;
    // Dashboard Lessons_Paid_Total is the most recent package's raw unit count.
    const typicalUnits = Math.max(10, Number(history.at(-1)?.number_of_lesson) || row.remaining || 0);
    const cycleDays = Math.max(7, halfEven(typicalUnits / Math.max(0.01, row.unitsPerDay || 0.1)));
    for (let next = finish; next <= yearEnd; next = addDays(next, cycleDays)) expectedFuture += baseline;
    counted += 1;
  }
  return { ytd, expectedFuture, projected: ytd + expectedFuture, counted, missingBaseline };
}
