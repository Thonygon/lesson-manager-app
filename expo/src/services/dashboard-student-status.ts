import { requireSupabase } from '@/lib/supabase';

// app_settings.value is numeric. Store one flag per student for both screens.
const KEY_PREFIX = 'teacher_student_inactive_';

async function identity() {
  const client = requireSupabase();
  const { data, error } = await client.auth.getUser();
  if (error || !data.user) throw error ?? new Error('Your session has expired.');
  return { client, uid: data.user.id };
}

function settingKey(student: string) { return `${KEY_PREFIX}${encodeURIComponent(student.trim())}`; }

export async function getInactiveDashboardStudents(): Promise<string[]> {
  const { client, uid } = await identity();
  const { data, error } = await client.from('app_settings').select('key,value').eq('user_id', uid).like('key', `${KEY_PREFIX}%`);
  if (error) throw error;
  return (data || []).filter((row) => Number(row.value) === 1).flatMap((row) => {
    try { return [decodeURIComponent(String(row.key).slice(KEY_PREFIX.length))]; }
    catch { return []; }
  });
}

export async function setTeacherStudentActive(student: string, active: boolean): Promise<string[]> {
  const name = student.trim();
  if (!name) throw new Error('Choose a student first.');
  const { client, uid } = await identity();
  const { error } = await client.from('app_settings').upsert({ user_id: uid, key: settingKey(name), value: active ? 0 : 1 }, { onConflict: 'user_id,key' });
  if (error) throw error;
  return getInactiveDashboardStudents();
}

export async function renameTeacherStudentActivity(oldName: string, newName: string): Promise<string[]> {
  const current = await getInactiveDashboardStudents();
  if (!current.includes(oldName.trim()) || oldName.trim() === newName.trim()) return current;
  const { client, uid } = await identity();
  const { error } = await client.from('app_settings').upsert([
    { user_id: uid, key: settingKey(oldName), value: 0 },
    { user_id: uid, key: settingKey(newName), value: 1 },
  ], { onConflict: 'user_id,key' });
  if (error) throw error;
  return getInactiveDashboardStudents();
}
