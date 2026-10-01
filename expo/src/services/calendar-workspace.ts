import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';

export type CalendarWorkspace = { schedules: ClassioRecord[]; overrides: ClassioRecord[]; freezes: ClassioRecord[] };
export type CalendarEvent = { key: string; student: string; date: string; time: string; duration: number; source: 'weekly' | 'override'; note: string; scheduleId?: string; overrideId?: string };
function dateKey(date: Date) { const y = date.getFullYear(); const m = String(date.getMonth() + 1).padStart(2, '0'); const d = String(date.getDate()).padStart(2, '0'); return `${y}-${m}-${d}`; }
function parseLocalDate(value: string) { const [y, m, d] = value.split('-').map(Number); return new Date(y, (m || 1) - 1, d || 1); }
function isWithin(date: string, start: unknown, end: unknown) { return (!start || String(start).slice(0, 10) <= date) && (!end || String(end).slice(0, 10) >= date); }

export async function getCalendarWorkspace(): Promise<CalendarWorkspace> {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.'); const uid = userData.user.id;
  const [schedules, overridesWithGoogleId, freezes] = await Promise.all([
    client.from('schedules').select('id,student,weekday,time,duration_minutes,active,timezone,start_date,end_date').eq('user_id', uid).order('weekday').limit(1000),
    client.from('calendar_overrides').select('id,student,original_date,new_datetime,duration_minutes,status,note,gcal_event_id').eq('user_id', uid).order('original_date', { ascending: false }).limit(2000),
    client.from('student_schedule_freezes').select('id,student,start_date,end_date,reason,note,active,created_at').eq('user_id', uid).order('created_at', { ascending: false }).limit(500),
  ]);
  const overrides = overridesWithGoogleId.error
    ? await client.from('calendar_overrides').select('id,student,original_date,new_datetime,duration_minutes,status,note').eq('user_id', uid).order('original_date', { ascending: false }).limit(2000)
    : overridesWithGoogleId;
  const error = schedules.error ?? overrides.error ?? freezes.error; if (error) throw error;
  return { schedules: (schedules.data ?? []) as unknown as ClassioRecord[], overrides: (overrides.data ?? []) as unknown as ClassioRecord[], freezes: (freezes.data ?? []) as unknown as ClassioRecord[] };
}

export function buildCalendarEvents(workspace: CalendarWorkspace, startDate: string, endDate: string): CalendarEvent[] {
  const start = parseLocalDate(startDate); const end = parseLocalDate(endDate); const overrideKeys = new Set(workspace.overrides.map((row) => `${String(row.student)}|${String(row.original_date).slice(0, 10)}`)); const activeFreezes = workspace.freezes.filter((row) => row.active !== false);
  const paused = (student: string, date: string) => activeFreezes.some((row) => String(row.student) === student && isWithin(date, row.start_date, row.end_date)); const events: CalendarEvent[] = [];
  for (let cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) { const date = dateKey(cursor); const weekday = (cursor.getDay() + 6) % 7; for (const row of workspace.schedules) { const student = String(row.student || 'Student'); if (row.active === false || Number(row.weekday) !== weekday || !isWithin(date, row.start_date, row.end_date) || paused(student, date) || overrideKeys.has(`${student}|${date}`)) continue; events.push({ key: `s-${row.id}-${date}`, student, date, time: String(row.time || '').slice(0, 5), duration: Number(row.duration_minutes || 60), source: 'weekly', note: '', scheduleId: String(row.id) }); } }
  for (const row of workspace.overrides) { if (String(row.status || '').toLowerCase() !== 'scheduled' || !row.new_datetime) continue; const parsed = new Date(String(row.new_datetime)); if (Number.isNaN(parsed.valueOf())) continue; const date = dateKey(parsed); const student = String(row.student || 'Student'); if (date < startDate || date > endDate || paused(student, date)) continue; events.push({ key: `o-${row.id}`, student, date, time: parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }), duration: Number(row.duration_minutes || 60), source: 'override', note: String(row.note || ''), overrideId: String(row.id) }); }
  return events.sort((a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time) || a.student.localeCompare(b.student));
}

async function userId() { const { data, error } = await requireSupabase().auth.getUser(); if (error || !data.user) throw error ?? new Error('Your session has expired.'); return data.user.id; }
export async function addCalendarOverride(input: { student: string; originalDate: string; newDateTime?: string; durationMinutes: number; status: 'scheduled' | 'cancelled'; note?: string }) { const client = requireSupabase(); const uid = await userId(); const newDate = input.status === 'scheduled' && input.newDateTime ? new Date(input.newDateTime) : null; if (newDate && Number.isNaN(newDate.valueOf())) throw new Error('Enter a valid date and time.'); const { error } = await client.from('calendar_overrides').insert({ user_id: uid, student: input.student.trim(), original_date: input.originalDate, new_datetime: newDate?.toISOString() || null, duration_minutes: input.durationMinutes, status: input.status, note: input.note?.trim() || '' }); if (error) throw error; }
export async function deleteCalendarOverride(id: string | number) { const client = requireSupabase(); const uid = await userId(); const { error } = await client.from('calendar_overrides').delete().eq('id', id).eq('user_id', uid); if (error) throw error; }
export async function addScheduleFreeze(input: { student: string; startDate: string; endDate?: string; reason?: string; note?: string }) { const client = requireSupabase(); const uid = await userId(); const { error } = await client.from('student_schedule_freezes').insert({ user_id: uid, student: input.student.trim(), start_date: input.startDate, end_date: input.endDate || null, reason: input.reason?.trim() || '', note: input.note?.trim() || '', active: true }); if (error) throw error; }
export async function updateScheduleFreeze(id: string | number, input: { student: string; startDate: string; endDate?: string; reason?: string; note?: string; active: boolean }) { const client = requireSupabase(); const uid = await userId(); const { error } = await client.from('student_schedule_freezes').update({ student: input.student.trim(), start_date: input.startDate, end_date: input.endDate || null, reason: input.reason?.trim() || '', note: input.note?.trim() || '', active: input.active }).eq('id', id).eq('user_id', uid); if (error) throw error; }
export async function resumeScheduleFreeze(id: string | number) { const client = requireSupabase(); const uid = await userId(); const { error } = await client.from('student_schedule_freezes').update({ active: false }).eq('id', id).eq('user_id', uid); if (error) throw error; }
export async function deleteScheduleFreeze(id: string | number) { const client = requireSupabase(); const uid = await userId(); const { error } = await client.from('student_schedule_freezes').delete().eq('id', id).eq('user_id', uid); if (error) throw error; }
