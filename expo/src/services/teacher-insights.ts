import { Platform } from 'react-native';
import { canonicalSubjectLabel } from '@/lib/subjects';

import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';

export type InsightPeriod = 'all' | 'year' | 'month' | 'week';
export type TeacherDataset = {
  students: ClassioRecord[];
  lessons: ClassioRecord[];
  payments: ClassioRecord[];
  schedules: ClassioRecord[];
  assignments: ClassioRecord[];
  reviewRequests: ClassioRecord[];
  yearGoal: number;
};

export type PackageInsight = {
  student: string;
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
  const [students, lessons, payments, schedules, assignments, reviewRequests, goal] = await Promise.all([
    client.from('students').select('id,student,email,phone,zoom_link,address,color,native_language,linked_student_user_id').eq('user_id', uid).order('student').limit(1000),
    client.from('classes').select('id,student,lesson_date,number_of_lesson,modality,subject,subject_custom,note').eq('user_id', uid).order('lesson_date', { ascending: false }).limit(5000),
    client.from('payments').select('id,student,number_of_lesson,payment_date,paid_amount,currency,modality,subject,subject_custom,package_start_date,package_expiry_date,lesson_adjustment_units,package_normalized').eq('user_id', uid).order('payment_date', { ascending: false }).limit(5000),
    client.from('schedules').select('id,student,weekday,time,duration_minutes,active,timezone,start_date,end_date').eq('user_id', uid).order('weekday').limit(1000),
    client.from('teacher_assignments').select('id,title,student_id,status,due_at,score_pct,subject_label,assignment_type,submitted_at,graded_at,created_at').eq('teacher_id', uid).order('created_at', { ascending: false }).limit(2000),
    client.from('teacher_review_requests').select('id,student_id,assignment_id,status,subject_key,subject_label,requested_at,reviewed_at').eq('teacher_id', uid).order('requested_at', { ascending: false }).limit(2000),
    client.from('app_settings').select('value').eq('user_id', uid).eq('key', `year_goal_${year}_personal`).limit(1),
  ]);
  const error = students.error ?? lessons.error ?? payments.error ?? schedules.error ?? assignments.error ?? reviewRequests.error;
  if (error) throw error;
  return {
    students: (students.data ?? []) as unknown as ClassioRecord[], lessons: (lessons.data ?? []) as unknown as ClassioRecord[], payments: (payments.data ?? []) as unknown as ClassioRecord[], schedules: (schedules.data ?? []) as unknown as ClassioRecord[], assignments: (assignments.data ?? []) as unknown as ClassioRecord[], reviewRequests: (reviewRequests.data ?? []) as unknown as ClassioRecord[],
    yearGoal: Number(goal.data?.[0]?.value || 0),
  };
}

export async function setTeacherYearGoal(value: number) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const year = new Date().getFullYear();
  const { error } = await client.from('app_settings').upsert({ user_id: userData.user.id, key: `year_goal_${year}_personal`, value: String(value) }, { onConflict: 'user_id,key' });
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

export function buildPackageInsights(data: TeacherDataset): PackageInsight[] {
  const studentMeta = new Map(data.students.map((row) => [String(row.student || '').trim(), row])); const today = new Date(); today.setHours(0, 0, 0, 0);
  const grouped = new Map<string, ClassioRecord[]>(); for (const payment of data.payments) { const key = String(payment.student || '').trim(); if (key) grouped.set(key, [...(grouped.get(key) || []), payment]); }
  const result: PackageInsight[] = [];
  for (const [student, payments] of grouped) {
    const sorted = [...payments].sort((a, b) => timestamp(a.package_start_date || a.payment_date) - timestamp(b.package_start_date || b.payment_date) || Number(a.id || 0) - Number(b.id || 0)); const latest = sorted.at(-1); if (!latest) continue;
    const startDate = isoDate(latest.package_start_date || latest.payment_date); const start = timestamp(startDate); const purchased = Number(latest.number_of_lesson || 0) + Number(latest.lesson_adjustment_units || 0);
    const delivered = data.lessons.filter((lesson) => String(lesson.student || '').trim() === student && timestamp(lesson.lesson_date) >= start && !isFreeLesson(lesson)).reduce((sum, lesson) => sum + Number(lesson.number_of_lesson || 0), 0); const remaining = purchased - delivered;
    const recent = data.lessons.filter((lesson) => String(lesson.student || '').trim() === student && timestamp(lesson.lesson_date) >= addDays(today, -56).valueOf() && !isFreeLesson(lesson)); const recentUnits = recent.reduce((sum, lesson) => sum + Number(lesson.number_of_lesson || 0), 0); const unitsPerDay = recentUnits > 0 ? recentUnits / 56 : 0.1; const estimate = addDays(today, Math.max(0, Math.round(remaining / unitsPerDay))); const explicitExpiry = isoDate(latest.package_expiry_date); const estimatedFinishDate = explicitExpiry && timestamp(explicitExpiry) < estimate.valueOf() ? explicitExpiry : estimate.toISOString().slice(0, 10);
    const status: PackageInsight['status'] = remaining < 0 ? 'overused' : remaining <= 0 || timestamp(estimatedFinishDate) <= today.valueOf() ? 'due_now' : remaining <= 3 || timestamp(estimatedFinishDate) <= addDays(today, 21).valueOf() ? 'finishing_soon' : 'active'; const meta = studentMeta.get(student) || {};
    result.push({ student, phone: String(meta.phone || ''), email: String(meta.email || ''), subject: canonicalSubjectLabel(latest.subject === 'Other' ? latest.subject_custom || 'Other' : latest.subject || 'General'), modality: String(latest.modality || ''), purchased, delivered, remaining, paymentDate: isoDate(latest.payment_date), startDate, expiryDate: explicitExpiry, estimatedFinishDate, status });
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
