import { requireSupabase } from '@/lib/supabase';
import { buildCalendarEvents } from '@/services/calendar-workspace';
import type { ClassioRecord } from '@/services/classio-data';

function dateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export async function getTeacherTodayAgenda(teacherId: string, schedules: ClassioRecord[], now = new Date()): Promise<ClassioRecord[]> {
  if (!teacherId) throw new Error('A teacher session is required.');
  const client = requireSupabase();
  const today = dateKey(now);
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const [original, moved, freezes] = await Promise.all([
    client.from('calendar_overrides').select('id,student,original_date,new_datetime,duration_minutes,status,note').eq('user_id', teacherId).eq('original_date', today).limit(200),
    client.from('calendar_overrides').select('id,student,original_date,new_datetime,duration_minutes,status,note').eq('user_id', teacherId).gte('new_datetime', start.toISOString()).lt('new_datetime', end.toISOString()).limit(200),
    client.from('student_schedule_freezes').select('id,student,start_date,end_date,active').eq('user_id', teacherId).eq('active', true).lte('start_date', today).limit(200),
  ]);
  const error = original.error ?? moved.error ?? freezes.error;
  if (error) throw error;
  const overrides = new Map<string, ClassioRecord>();
  for (const row of [...(original.data || []), ...(moved.data || [])]) overrides.set(String(row.id), row as ClassioRecord);
  const events = buildCalendarEvents({
    schedules,
    overrides: [...overrides.values()],
    freezes: (freezes.data || []).filter((row) => !row.end_date || String(row.end_date).slice(0, 10) >= today) as ClassioRecord[],
  }, today, today);
  return events.map((event) => ({ id: event.key, student: event.student, time: event.time, duration_minutes: event.duration, note: event.note, source: event.source }));
}
