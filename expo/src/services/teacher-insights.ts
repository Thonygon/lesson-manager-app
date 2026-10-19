import { Platform } from 'react-native';
import { canonicalSubjectLabel } from '@/lib/subjects';

import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';
import { readTeacherHistory } from '@/services/teacher-history-pagination';
import { ANALYTICS_CURRENCIES } from '@/services/teacher-currency';

export type InsightPeriod = 'all' | 'year' | 'month' | 'week';
export type TeacherDataset = {
  students: ClassioRecord[];
  lessons: ClassioRecord[];
  payments: ClassioRecord[];
  schedules: ClassioRecord[];
  assignments: ClassioRecord[];
  reviewRequests: ClassioRecord[];
  practiceRequests: ClassioRecord[];
  yearGoal: number;
  goalCurrency: string;
};

export type PackageInsight = {
  student: string;
  currency: string;
  phone: string;
  email: string;
  subject: string;
  modality: string;
  purchased: number;
  delivered: number;
  remaining: number;
  paymentDate: string;
  startDate: string;
  expiryDate: string;
  estimatedFinishDate: string;
  status: 'active' | 'finishing_soon' | 'due_now' | 'overused';
  dashboardStatus: 'active' | 'almost_finished' | 'finished' | 'mismatch' | 'dropout';
};

function isoDate(value: unknown) { return String(value || '').slice(0, 10); }
function localDateKey(date: Date) { const year = date.getFullYear(); const month = String(date.getMonth() + 1).padStart(2, '0'); const day = String(date.getDate()).padStart(2, '0'); return `${year}-${month}-${day}`; }
function timestamp(value: unknown) { const parsed = new Date(String(value || '')); return Number.isNaN(parsed.valueOf()) ? 0 : parsed.valueOf(); }
function isFreeLesson(row: ClassioRecord) { const note = String(row.note || '').toUpperCase(); return ['[FREE]', '[DEMO]', '[DONT COUNT]', "[DON'T COUNT]"].some((tag) => note.includes(tag)); }
function addDays(date: Date, days: number) { const next = new Date(date); next.setDate(next.getDate() + days); return next; }

export async function getTeacherDataset(): Promise<TeacherDataset> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const uid = userData.user.id; const year = new Date().getFullYear();
  const [students, lessons, payments, schedules, assignments, reviewRequests, practiceRequests, goal, goalCurrency] = await Promise.all([
    client.from('students').select('id,student,email,phone,zoom_link,address,color,native_language,linked_student_user_id').eq('user_id', uid).order('student').limit(1000),
    readTeacherHistory(client, uid, 'classes', 'id,student,lesson_date,number_of_lesson,modality,subject,subject_custom,note', 'lesson_date'),
    readTeacherHistory(client, uid, 'payments', 'id,student,number_of_lesson,payment_date,paid_amount,currency,modality,subject,subject_custom,package_start_date,package_expiry_date,lesson_adjustment_units,package_normalized', 'payment_date'),
    client.from('schedules').select('id,student,weekday,time,duration_minutes,active,timezone,start_date,end_date').eq('user_id', uid).order('weekday').limit(1000),
    client.from('teacher_assignments').select('id,title,student_id,status,due_at,score_pct,subject_label,assignment_type,learning_program_topic_id,submitted_at,graded_at,created_at').eq('teacher_id', uid).order('created_at', { ascending: false }).limit(2000),
    client.from('teacher_review_requests').select('id,student_id,assignment_id,status,subject_key,subject_label,requested_at,reviewed_at').eq('teacher_id', uid).order('requested_at', { ascending: false }).limit(2000),
    client.from('learning_program_progress').select('id,assignment_id,topic_id,updated_at,program_assignment:learning_program_assignments!inner(student_user_id,student_name,teacher_id)').eq('program_assignment.teacher_id', uid).eq('teacher_done', true).eq('student_done', true).order('updated_at', { ascending: false }).limit(500),
    client.from('app_settings').select('value').eq('user_id', uid).eq('key', `year_goal_${year}_personal`).limit(1),
    client.from('app_settings').select('value').eq('user_id', uid).eq('key', `year_goal_${year}_personal_currency`).limit(1),
  ]);
  const error = students.error ?? schedules.error ?? assignments.error ?? reviewRequests.error ?? practiceRequests.error ?? goal.error ?? goalCurrency.error;
  if (error) throw error;
  return {
    students: (students.data ?? []) as unknown as ClassioRecord[], lessons: lessons as ClassioRecord[], payments: payments as ClassioRecord[], schedules: (schedules.data ?? []) as unknown as ClassioRecord[], assignments: (assignments.data ?? []) as unknown as ClassioRecord[], reviewRequests: (reviewRequests.data ?? []) as unknown as ClassioRecord[], practiceRequests: (practiceRequests.data ?? []).map((row) => { const assignment = Array.isArray(row.program_assignment) ? row.program_assignment[0] : row.program_assignment; return { ...row, student_id: assignment?.student_user_id, student_name: assignment?.student_name }; }) as ClassioRecord[],
    yearGoal: Number(goal.data?.[0]?.value || 0),
    goalCurrency: ANALYTICS_CURRENCIES[Number(goalCurrency.data?.[0]?.value) || 0] || 'TRY',
  };
}

export async function setTeacherYearGoal(value: number, currency: string) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const year = new Date().getFullYear();
  const currencyIndex = ANALYTICS_CURRENCIES.findIndex((item) => item === currency);
  if (currencyIndex < 0) throw new Error('Unsupported goal currency.');
  const { error } = await client.from('app_settings').upsert([
    { user_id: userData.user.id, key: `year_goal_${year}_personal`, value: String(value) },
    { user_id: userData.user.id, key: `year_goal_${year}_personal_currency`, value: currencyIndex },
  ], { onConflict: 'user_id,key' });
  if (error) throw error;
}

export async function completeTeacherOnboarding() {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('profiles').update({ onboarding_completed: true }).eq('user_id', userData.user.id);
  if (error) throw error;
}

export function periodStart(period: InsightPeriod, now = new Date()) {
  if (period === 'all') return null;
  if (period === 'year') return new Date(now.getFullYear(), 0, 1);
  if (period === 'month') return new Date(now.getFullYear(), now.getMonth(), 1);
  const start = new Date(now); const day = (start.getDay() + 6) % 7; start.setHours(0, 0, 0, 0); start.setDate(start.getDate() - day); return start;
}

export function withinPeriod(rows: ClassioRecord[], key: string, period: InsightPeriod) {
  const start = periodStart(period); return start ? rows.filter((row) => timestamp(row[key]) >= start.valueOf()) : rows;
}

export function buildPackageInsights(data: Pick<TeacherDataset, 'students' | 'lessons' | 'payments'>): PackageInsight[] {
  const studentMeta = new Map(data.students.map((row) => [String(row.student || '').trim(), row])); const today = new Date(); today.setHours(0, 0, 0, 0);
  const todayKey = localDateKey(today); const activeCutoff = localDateKey(addDays(today, -183)); const expiryCutoff = localDateKey(addDays(today, -365));
  const grouped = new Map<string, ClassioRecord[]>(); for (const payment of data.payments) { const key = String(payment.student || '').trim(); if (key && isoDate(payment.payment_date)) grouped.set(key, [...(grouped.get(key) || []), payment]); }
  const result: PackageInsight[] = [];
  for (const [student, payments] of grouped) {
    const sorted = [...payments].sort((a, b) => isoDate(a.package_start_date || a.payment_date).localeCompare(isoDate(b.package_start_date || b.payment_date)) || isoDate(a.payment_date).localeCompare(isoDate(b.payment_date)) || Number(a.id || 0) - Number(b.id || 0)); const latest = sorted.at(-1); if (!latest) continue;
    const startDate = isoDate(latest.package_start_date || latest.payment_date); const purchased = Math.trunc(Number(latest.number_of_lesson || 0)) + Math.trunc(Number(latest.lesson_adjustment_units || 0));
    const studentLessons = data.lessons.filter((lesson) => String(lesson.student || '').trim() === student && isoDate(lesson.lesson_date));
    const delivered = studentLessons.filter((lesson) => isoDate(lesson.lesson_date) >= startDate && isoDate(lesson.lesson_date) <= todayKey && !isFreeLesson(lesson)).reduce((sum, lesson) => sum + Math.trunc(Number(lesson.number_of_lesson || 0)), 0);
    const rawRemaining = purchased - delivered;
    const lastLesson = studentLessons.reduce((latestDay, lesson) => isoDate(lesson.lesson_date) > latestDay ? isoDate(lesson.lesson_date) : latestDay, '');
    const paymentDate = isoDate(latest.payment_date); const explicitExpiry = isoDate(latest.package_expiry_date);
    const active = lastLesson >= activeCutoff || paymentDate >= activeCutoff;
    const closedByExpiry = !!explicitExpiry && explicitExpiry <= todayKey && rawRemaining <= 0;
    const closedByOldPayment = paymentDate <= expiryCutoff && !active;
    const remaining = closedByOldPayment || !active ? 0 : rawRemaining;
    const dashboardStatus: PackageInsight['dashboardStatus'] = !active && !closedByExpiry ? 'dropout' : rawRemaining < 0 && active && latest.package_normalized !== true ? 'mismatch' : closedByExpiry || closedByOldPayment || remaining <= 0 ? 'finished' : remaining <= 3 ? 'almost_finished' : 'active';
    const recent = data.lessons.filter((lesson) => String(lesson.student || '').trim() === student && timestamp(lesson.lesson_date) >= addDays(today, -56).valueOf() && !isFreeLesson(lesson)); const recentUnits = recent.reduce((sum, lesson) => sum + Number(lesson.number_of_lesson || 0), 0); const unitsPerDay = recentUnits > 0 ? recentUnits / 56 : 0.1; const estimate = addDays(today, Math.max(0, Math.round(remaining / unitsPerDay))); const estimatedFinishDate = explicitExpiry && timestamp(explicitExpiry) < estimate.valueOf() ? explicitExpiry : estimate.toISOString().slice(0, 10);
    const status: PackageInsight['status'] = rawRemaining < 0 && active && latest.package_normalized !== true ? 'overused' : remaining <= 0 || timestamp(estimatedFinishDate) <= today.valueOf() ? 'due_now' : remaining <= 3 || timestamp(estimatedFinishDate) <= addDays(today, 21).valueOf() ? 'finishing_soon' : 'active'; const meta = studentMeta.get(student) || {};
    result.push({ student, currency: String(latest.currency || 'TRY'), phone: String(meta.phone || ''), email: String(meta.email || ''), subject: canonicalSubjectLabel(latest.subject === 'Other' ? latest.subject_custom || 'Other' : latest.subject || 'General'), modality: String(latest.modality || ''), purchased, delivered, remaining, paymentDate, startDate, expiryDate: explicitExpiry, estimatedFinishDate, status, dashboardStatus });
  }
  const order = { overused: 0, due_now: 1, finishing_soon: 2, active: 3 }; return result.sort((a, b) => order[a.status] - order[b.status] || a.remaining - b.remaining || a.student.localeCompare(b.student));
}

export function todaySchedules(data: TeacherDataset, now = new Date()) {
  const weekday = (now.getDay() + 6) % 7; const date = localDateKey(now);
  return data.schedules.filter((row) => row.active !== false && Number(row.weekday) === weekday && (!row.start_date || isoDate(row.start_date) <= date) && (!row.end_date || isoDate(row.end_date) >= date)).sort((a, b) => String(a.time).localeCompare(String(b.time)));
}

export type UpcomingLesson = { date: string; dateTime: Date; schedule: ClassioRecord };

export function nextScheduledLesson(data: TeacherDataset, now = new Date(), searchDays = 60): UpcomingLesson | null {
  const current = new Date(now); const candidates: UpcomingLesson[] = [];
  for (let offset = 0; offset <= searchDays; offset += 1) {
    const date = addDays(current, offset); const dateKey = localDateKey(date); const weekday = (date.getDay() + 6) % 7;
    for (const schedule of data.schedules) {
      if (schedule.active === false || Number(schedule.weekday) !== weekday || (schedule.start_date && isoDate(schedule.start_date) > dateKey) || (schedule.end_date && isoDate(schedule.end_date) < dateKey)) continue;
      const [hour, minute] = String(schedule.time || '00:00').split(':').map(Number); const dateTime = new Date(date); dateTime.setHours(hour || 0, minute || 0, 0, 0);
      if (dateTime.valueOf() >= current.valueOf()) candidates.push({ date: dateKey, dateTime, schedule });
    }
  }
  return candidates.sort((a, b) => a.dateTime.valueOf() - b.dateTime.valueOf())[0] || null;
}

export function whatsappUrl(phone: string, message: string) {
  const normalized = phone.replace(/[^0-9]/g, ''); return `https://wa.me/${normalized}?text=${encodeURIComponent(message)}`;
}

export function downloadCsv(filename: string, rows: (string | number)[][]) {
  const csv = rows.map((row) => row.map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\n');
  if (Platform.OS === 'web' && typeof document !== 'undefined') { const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href); return true; }
  return false;
}
