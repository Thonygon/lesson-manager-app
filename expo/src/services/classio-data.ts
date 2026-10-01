import { requireSupabase } from '@/lib/supabase';

export type DashboardCounts = {
  students: number;
  lessons: number;
  assignments: number;
  resources: number;
};

export type ClassioRecord = Record<string, unknown>;

export type DashboardOverview = DashboardCounts & {
  recentLessons: ClassioRecord[];
  openAssignments: ClassioRecord[];
  recentPayments: ClassioRecord[];
  schedules: ClassioRecord[];
};

export type ListDefinition = {
  table: string;
  select: string;
  orderBy: string;
  ascending?: boolean;
};

const LISTS: Record<'students' | 'lessons' | 'assignments' | 'resources' | 'payments' | 'schedules', ListDefinition> = {
  students: { table: 'students', select: 'id,student,email,phone,zoom_link,notes,color,address,native_language,student_source,linked_at,linked_student_user_id,teacher_student_link_id', orderBy: 'student' },
  lessons: { table: 'classes', select: 'id,student,lesson_date,number_of_lesson,modality,subject,subject_custom,note', orderBy: 'lesson_date', ascending: false },
  assignments: { table: 'teacher_assignments', select: 'id,teacher_id,student_id,link_id,assignment_type,source_type,source_record_id,title,topic,subject_key,subject_label,status,due_at,score_pct,total_questions,correct_count,teacher_note,assigned_at,opened_at,viewed_at,submitted_at,graded_at,completed_at,created_at,updated_at,learning_program_assignment_id,learning_program_topic_id', orderBy: 'created_at', ascending: false },
  resources: { table: 'lesson_plans', select: 'id,title,subject_display,topic,status,created_at', orderBy: 'created_at', ascending: false },
  payments: { table: 'payments', select: 'id,student,number_of_lesson,payment_date,paid_amount,currency,modality,subject,subject_custom,package_start_date,package_expiry_date,lesson_adjustment_units,package_normalized,normalized_note,normalized_at', orderBy: 'payment_date', ascending: false },
  schedules: { table: 'schedules', select: 'id,student,weekday,time,duration_minutes,active,timezone,start_date,end_date', orderBy: 'weekday' },
};

export type ListKey = keyof typeof LISTS;

async function exactCount(table: string): Promise<number> {
  const { count, error } = await requireSupabase().from(table).select('*', { count: 'exact', head: true });
  if (error) throw error;
  return count ?? 0;
}

export async function getDashboardCounts(): Promise<DashboardCounts> {
  const [students, lessons, assignments, resources] = await Promise.all([
    exactCount('students'),
    exactCount('classes'),
    exactCount('teacher_assignments'),
    exactCount('lesson_plans'),
  ]);
  return { students, lessons, assignments, resources };
}

async function dashboardList(table: string, select: string, orderBy: string, limit: number, ascending = false) {
  const { data, error } = await requireSupabase().from(table).select(select).order(orderBy, { ascending }).limit(limit);
  if (error) throw error;
  return (data ?? []) as unknown as ClassioRecord[];
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const [students, recentLessons, assignments, resources, recentPayments, schedules] = await Promise.all([
    dashboardList('students', 'id,student', 'student', 1000, true),
    dashboardList('classes', 'id,student,lesson_date,modality,subject,note', 'lesson_date', 8),
    dashboardList('teacher_assignments', 'id,title,subject_label,status,due_at,score_pct,created_at', 'created_at', 100),
    dashboardList('lesson_plans', 'id,title', 'created_at', 1000),
    dashboardList('payments', 'id,student,payment_date,paid_amount,currency,modality,subject', 'payment_date', 5),
    dashboardList('schedules', 'id,student,weekday,time,duration_minutes,active,timezone,start_date,end_date', 'weekday', 100, true),
  ]);
  const openAssignments = assignments
    .filter((record) => !['completed', 'graded', 'archived'].includes(String(record.status ?? '').toLowerCase()))
    .slice(0, 5);
  return {
    students: students.length,
    lessons: recentLessons.length,
    assignments: assignments.length,
    resources: resources.length,
    recentLessons: recentLessons.slice(0, 5),
    openAssignments,
    recentPayments,
    schedules: schedules.filter((record) => record.active !== false).slice(0, 6),
  };
}

export async function getRecords(key: ListKey): Promise<ClassioRecord[]> {
  const definition = LISTS[key];
  const { data, error } = await requireSupabase()
    .from(definition.table)
    .select(definition.select)
    .order(definition.orderBy, { ascending: definition.ascending ?? true })
    .limit(1000);
  if (error) throw error;
  return (data ?? []) as unknown as ClassioRecord[];
}

export type AssignmentWorkspace = {
  assignments: ClassioRecord[];
  attempts: ClassioRecord[];
  reviewRequests: ClassioRecord[];
  studentNames: Record<string, string>;
};

export async function getAssignmentWorkspace(): Promise<AssignmentWorkspace> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const teacherId = userData.user.id;
  const [assignmentResult, attemptResult, reviewResult, studentResult] = await Promise.all([
    client.from('teacher_assignments').select(LISTS.assignments.select).eq('teacher_id', teacherId).neq('status', 'archived').order('created_at', { ascending: false }).limit(1000),
    client.from('teacher_assignment_attempts').select('id,assignment_id,student_id,attempt_number,status,score_pct,total_questions,correct_count,teacher_feedback,started_at,submitted_at,graded_at,completed_at,created_at').eq('teacher_id', teacherId).order('created_at', { ascending: false }).limit(2000),
    client.from('teacher_review_requests').select('id,student_id,assignment_id,practice_session_id,subject_key,subject_label,source_type,source_id,title,status,request_note,teacher_feedback,override_score_pct,requested_at,reviewed_at,created_at').eq('teacher_id', teacherId).order('requested_at', { ascending: false }).limit(1000),
    client.from('students').select('student,linked_student_user_id').eq('user_id', teacherId).not('linked_student_user_id', 'is', null).limit(1000),
  ]);
  const error = assignmentResult.error ?? attemptResult.error ?? reviewResult.error ?? studentResult.error;
  if (error) throw error;
  const studentNames = Object.fromEntries((studentResult.data ?? []).flatMap((row) => row.linked_student_user_id ? [[String(row.linked_student_user_id), String(row.student || 'Student')]] : []));
  return {
    assignments: (assignmentResult.data ?? []) as unknown as ClassioRecord[],
    attempts: (attemptResult.data ?? []) as unknown as ClassioRecord[],
    reviewRequests: (reviewResult.data ?? []) as unknown as ClassioRecord[],
    studentNames,
  };
}

export async function getAssignmentDetail(id: string | number): Promise<ClassioRecord> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data, error } = await client.from('teacher_assignments').select('id,teacher_id,student_id,assignment_type,source_type,source_record_id,title,topic,subject_key,subject_label,teacher_note,content_snapshot,status,score_pct,total_questions,correct_count,due_at,assigned_at,opened_at,viewed_at,submitted_at,graded_at,completed_at,created_at,updated_at,learning_program_assignment_id,learning_program_topic_id').eq('id', id).eq('teacher_id', userData.user.id).single();
  if (error) throw error;
  return data as unknown as ClassioRecord;
}

export type TeacherReviewDetail = {
  review: ClassioRecord;
  session: ClassioRecord;
  answers: ClassioRecord[];
};

export async function getTeacherReviewDetail(reviewId: string | number): Promise<TeacherReviewDetail> {
  const { data, error } = await requireSupabase().rpc('classio_teacher_review_detail', { p_review_id: reviewId });
  if (error) throw error;
  const payload = (data ?? {}) as unknown as TeacherReviewDetail;
  return { review: payload.review ?? {}, session: payload.session ?? {}, answers: Array.isArray(payload.answers) ? payload.answers : [] };
}

export async function submitTeacherReview(input: { reviewId: string | number; overrides: Record<string, 'keep' | 'correct' | 'incorrect'>; feedback: string }) {
  const { data, error } = await requireSupabase().rpc('classio_submit_teacher_review', {
    p_review_id: input.reviewId,
    p_overrides: input.overrides,
    p_teacher_feedback: input.feedback.trim(),
  });
  if (error) throw error;
  return (data ?? {}) as unknown as ClassioRecord;
}

export async function addStudent(input: { name: string; email?: string; phone?: string }) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const payload = {
    user_id: userData.user.id,
    student: input.name.trim(),
    email: input.email?.trim() || null,
    phone: input.phone?.trim() || null,
    student_source: 'manual',
  };
  const { error } = await client.from('students').insert(payload);
  if (error) throw error;
}

export async function addLesson(input: {
  student: string;
  lessonDate: string;
  units: number;
  modality: 'Online' | 'Offline';
  subject: string;
  customSubject?: string;
  note?: string;
}) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('classes').insert({
    user_id: userData.user.id,
    student: input.student.trim(),
    lesson_date: input.lessonDate,
    number_of_lesson: input.units,
    modality: input.modality,
    subject: input.subject === 'Other' ? 'Other' : input.subject,
    subject_custom: input.subject === 'Other' ? input.customSubject?.trim() || null : null,
    note: input.note?.trim() || '',
  });
  if (error) throw error;
  await recalculatePackageDates(input.student);
}

export async function updateLesson(id: string | number, input: { student: string; lessonDate: string; units: number; modality: 'Online' | 'Offline'; subject: string; customSubject?: string; note?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data: previous } = await client.from('classes').select('student').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
  const { error } = await client.from('classes').update({ student: input.student.trim(), lesson_date: input.lessonDate, number_of_lesson: input.units, modality: input.modality, subject: input.subject === 'Other' ? 'Other' : input.subject, subject_custom: input.subject === 'Other' ? input.customSubject?.trim() || null : null, note: input.note?.trim() || '' }).eq('id', id).eq('user_id', userData.user.id);
  if (error) throw error;
  await Promise.all(Array.from(new Set([String(previous?.student || '').trim(), input.student.trim()].filter(Boolean))).map(recalculatePackageDates));
}

export async function deleteLesson(id: string | number) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data: previous } = await client.from('classes').select('student').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
  const { error } = await client.from('classes').delete().eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
  if (previous?.student) await recalculatePackageDates(String(previous.student));
}

export async function addPayment(input: {
  student: string;
  lessonUnits: number;
  paymentDate: string;
  paidAmount: number;
  currency: string;
  modality: 'Online' | 'Offline';
  subject: string;
  customSubject?: string;
  packageStartDate?: string;
}) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('payments').insert({
    user_id: userData.user.id,
    student: input.student.trim(),
    number_of_lesson: input.lessonUnits,
    payment_date: input.paymentDate,
    paid_amount: input.paidAmount,
    currency: input.currency,
    modality: input.modality,
    subject: input.subject === 'Other' ? 'Other' : input.subject,
    subject_custom: input.subject === 'Other' ? input.customSubject?.trim() || null : null,
    package_start_date: input.packageStartDate || input.paymentDate,
    package_expiry_date: null,
    lesson_adjustment_units: 0,
    package_normalized: false,
    normalized_note: '',
    normalized_at: null,
  });
  if (error) throw error;
  await recalculatePackageDates(input.student);
}

export async function updatePayment(id: string | number, input: { student: string; lessonUnits: number; paymentDate: string; paidAmount: number; currency: string; modality: 'Online' | 'Offline'; subject: string; customSubject?: string; packageStartDate?: string; packageExpiryDate?: string; adjustmentUnits?: number; normalized?: boolean; normalizedNote?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data: previous } = await client.from('payments').select('student').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
  const normalized = Boolean(input.normalized || input.normalizedNote?.trim());
  const { error } = await client.from('payments').update({ student: input.student.trim(), number_of_lesson: input.lessonUnits, payment_date: input.paymentDate, paid_amount: input.paidAmount, currency: input.currency, modality: input.modality, subject: input.subject === 'Other' ? 'Other' : input.subject, subject_custom: input.subject === 'Other' ? input.customSubject?.trim() || null : null, package_start_date: input.packageStartDate || input.paymentDate, package_expiry_date: input.packageExpiryDate || null, lesson_adjustment_units: input.adjustmentUnits || 0, package_normalized: normalized, normalized_note: input.normalizedNote?.trim() || '', normalized_at: normalized ? new Date().toISOString() : null }).eq('id', id).eq('user_id', userData.user.id);
  if (error) throw error;
  await Promise.all(Array.from(new Set([String(previous?.student || '').trim(), input.student.trim()].filter(Boolean))).map(recalculatePackageDates));
}

export async function deletePayment(id: string | number) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data: previous } = await client.from('payments').select('student').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
  const { error } = await client.from('payments').delete().eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
  if (previous?.student) await recalculatePackageDates(String(previous.student));
}

export type PricingItem = {
  id?: string | number;
  modality: 'online' | 'offline';
  kind: 'hourly' | 'package';
  hours: number | null;
  price: number;
  currency: string;
  active: boolean;
  sort_order: number;
};

export async function getPricingItems(): Promise<PricingItem[]> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data, error } = await client
    .from('pricing_items')
    .select('id,modality,kind,hours,price,currency,active,sort_order')
    .eq('user_id', userData.user.id)
    .eq('active', true)
    .order('sort_order')
    .order('hours');
  if (error) throw error;
  return (data ?? []).map((row) => ({
    id: row.id,
    modality: String(row.modality).toLowerCase() === 'offline' ? 'offline' : 'online',
    kind: String(row.kind).toLowerCase() === 'package' ? 'package' : 'hourly',
    hours: row.hours == null ? null : Number(row.hours),
    price: Number(row.price || 0),
    currency: String(row.currency || 'TRY'),
    active: row.active !== false,
    sort_order: Number(row.sort_order || 0),
  }));
}

export async function savePricingItem(item: PricingItem): Promise<void> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const payload = {
    user_id: userData.user.id,
    modality: item.modality,
    kind: item.kind,
    hours: item.kind === 'package' ? item.hours : null,
    price: Math.max(0, Math.round(item.price)),
    currency: item.currency,
    active: true,
    sort_order: item.kind === 'package' ? Math.max(1, Math.round(item.hours || 1)) : 0,
  };
  const query = item.id == null
    ? client.from('pricing_items').insert(payload)
    : client.from('pricing_items').update(payload).eq('id', item.id).eq('user_id', userData.user.id);
  const { error } = await query;
  if (error) throw error;
}

export async function deletePricingItem(id: string | number): Promise<void> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('pricing_items').delete().eq('id', id).eq('user_id', userData.user.id);
  if (error) throw error;
}

function dateOnly(value: unknown) { return value ? String(value).slice(0, 10) : ''; }
function countableLessonUnits(row: ClassioRecord) {
  const note = String(row.note || '').toUpperCase();
  return ['[FREE]', '[DEMO]', '[DONT COUNT]', "[DON'T COUNT]"].some((token) => note.includes(token)) ? 0 : Math.max(0, Number(row.number_of_lesson || 0));
}

export async function recalculatePackageDates(student: string) {
  const name = student.trim(); if (!name) return { updated: 0, mismatches: 0 };
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const uid = userData.user.id;
  const [paymentResult, lessonResult] = await Promise.all([
    client.from('payments').select('id,number_of_lesson,payment_date,package_start_date,package_expiry_date,lesson_adjustment_units').eq('user_id', uid).eq('student', name).order('payment_date').order('id'),
    client.from('classes').select('id,lesson_date,number_of_lesson,note').eq('user_id', uid).eq('student', name).order('lesson_date').order('id'),
  ]);
  if (paymentResult.error || lessonResult.error) throw paymentResult.error ?? lessonResult.error;
  const packages = (paymentResult.data ?? []) as unknown as ClassioRecord[];
  const lessons = (lessonResult.data ?? []) as unknown as ClassioRecord[];
  let updated = 0; let mismatches = 0;
  for (let index = 0; index < packages.length; index += 1) {
    const payment = packages[index]; const start = dateOnly(payment.package_start_date || payment.payment_date); const nextStart = dateOnly(packages[index + 1]?.package_start_date || packages[index + 1]?.payment_date);
    const purchased = Math.max(0, Number(payment.number_of_lesson || 0) + Number(payment.lesson_adjustment_units || 0));
    let used = 0; let expiry = '';
    if (start && purchased > 0) for (const lesson of lessons) { const date = dateOnly(lesson.lesson_date); if (!date || date < start || (nextStart && date >= nextStart)) continue; used += countableLessonUnits(lesson); if (!expiry && used >= purchased) expiry = date; }
    if (used > purchased) mismatches += 1;
    const updates: ClassioRecord = {}; if (!payment.package_start_date && start) updates.package_start_date = start; if (dateOnly(payment.package_expiry_date) !== expiry) updates.package_expiry_date = expiry || null;
    if (Object.keys(updates).length) { const { error } = await client.from('payments').update(updates).eq('id', payment.id).eq('user_id', uid); if (error) throw error; updated += 1; }
  }
  return { updated, mismatches };
}

export async function updateStudentProfile(id: string, input: {
  email?: string; phone?: string; zoomLink?: string; address?: string; nativeLanguage?: string; notes?: string; color?: string;
}) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('students').update({
    email: input.email?.trim() || '', phone: input.phone?.replace(/[^0-9+]/g, '') || '', zoom_link: input.zoomLink?.trim() || '',
    address: input.address?.trim() || '', native_language: input.nativeLanguage?.trim() || '', notes: input.notes?.trim() || '', color: input.color?.trim() || '#3B82F6',
  }).eq('id', id).eq('user_id', userData.user.id);
  if (error) throw error;
}

export async function deleteStudent(id: string | number) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('students').delete().eq('id', id).eq('user_id', userData.user.id);
  if (error) throw error;
}

export async function renameStudentEverywhere(oldName: string, newName: string) {
  const oldValue = oldName.trim(); const newValue = newName.trim();
  if (!oldValue || !newValue) throw new Error('Enter a student name.');
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data, error } = await client.rpc('classio_rename_student_everywhere', { p_old_name: oldValue, p_new_name: newValue });
  if (error) throw error;
  return data as { renamed?: boolean; name?: string; students?: number; classes?: number; payments?: number; schedules?: number; calendar_overrides?: number } | null;
}

export async function getStudentHistory(student: string): Promise<{ lessons: ClassioRecord[]; payments: ClassioRecord[] }> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const [lessonResult, paymentResult] = await Promise.all([
    client.from('classes').select('id,lesson_date,number_of_lesson,modality,subject,subject_custom,note').eq('user_id', userData.user.id).eq('student', student).order('lesson_date', { ascending: false }).limit(200),
    client.from('payments').select('id,payment_date,number_of_lesson,paid_amount,currency,modality,subject,subject_custom,package_start_date,package_expiry_date,lesson_adjustment_units,package_normalized').eq('user_id', userData.user.id).eq('student', student).order('payment_date', { ascending: false }).limit(100),
  ]);
  if (lessonResult.error || paymentResult.error) throw lessonResult.error ?? paymentResult.error;
  return { lessons: (lessonResult.data ?? []) as unknown as ClassioRecord[], payments: (paymentResult.data ?? []) as unknown as ClassioRecord[] };
}

export async function addSchedule(input: { student: string; weekday: number; time: string; durationMinutes: number; startDate: string; endDate?: string; active: boolean; timezone: string }) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('schedules').insert({ user_id: userData.user.id, student: input.student.trim(), weekday: input.weekday, time: input.time, duration_minutes: input.durationMinutes, active: input.active, timezone: input.timezone, start_date: input.startDate, end_date: input.endDate || null });
  if (error) throw error;
}

export async function updateSchedule(id: string | number, input: { student: string; weekday: number; time: string; durationMinutes: number; startDate: string; endDate?: string; active: boolean; timezone: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.rpc('classio_edit_schedule', { p_schedule_id: Number(id), p_student: input.student.trim(), p_weekday: input.weekday, p_time: input.time, p_duration_minutes: input.durationMinutes, p_active: input.active, p_timezone: input.timezone, p_effective_start_date: input.startDate, p_end_date: input.endDate || null, p_scope: 'entire' }); if (error) throw error;
}

export async function versionScheduleFromDate(id: string | number, input: { student: string; weekday: number; time: string; durationMinutes: number; startDate: string; endDate?: string; active: boolean; timezone: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.rpc('classio_edit_schedule', {
    p_schedule_id: Number(id), p_student: input.student.trim(), p_weekday: input.weekday, p_time: input.time,
    p_duration_minutes: input.durationMinutes, p_active: input.active, p_timezone: input.timezone,
    p_effective_start_date: input.startDate, p_end_date: input.endDate || null, p_scope: 'future',
  });
  if (error) throw error;
}

export async function deleteSchedule(id: string | number) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('schedules').delete().eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}

export async function setActiveMode(mode: 'teacher' | 'student') {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('profiles').update({ last_active_mode: mode }).eq('user_id', userData.user.id);
  if (error) throw error;
}
