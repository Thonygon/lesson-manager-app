import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';

export const PROFILE_COLUMNS = 'user_id,email,display_name,username,avatar_url,date_of_birth,sex,phone_number,role,primary_role,can_teach,can_study,last_active_mode,preferred_ui_language,timezone,country,preferred_currency,default_lesson_duration,primary_subjects,custom_subjects,teaching_stages,teaching_languages,education_level,show_community_profile,show_community_contact,onboarding_completed';

export async function getProfileWorkspace() {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data, error } = await client.from('profiles').select(PROFILE_COLUMNS).eq('user_id', userData.user.id).maybeSingle();
  if (error) throw error;
  return (data || { user_id: userData.user.id, email: userData.user.email || '' }) as ClassioRecord;
}

export async function saveProfileWorkspace(payload: ClassioRecord) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('profiles').upsert({ ...payload, user_id: userData.user.id, onboarding_completed: true }, { onConflict: 'user_id' });
  if (error) throw error;
}

export async function uploadProfileAvatar(file: Blob & { name?: string; type?: string }) {
  if (!file.type?.startsWith('image/')) throw new Error('Choose a PNG, JPG, JPEG, or WebP image.');
  if (!file.size) throw new Error('The selected image is empty.');
  if (file.size > 5 * 1024 * 1024) throw new Error('The profile image must be smaller than 5 MB.');
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const extension = (file.name?.split('.').pop() || file.type.split('/').pop() || 'jpg').replace(/[^a-z0-9]/gi, '').toLowerCase();
  const path = `${userData.user.id}/${crypto.randomUUID()}.${extension || 'jpg'}`;
  const { error } = await client.storage.from('avatars').upload(path, file, { contentType: file.type || 'image/jpeg', upsert: true });
  if (error) throw error;
  return client.storage.from('avatars').getPublicUrl(path).data.publicUrl;
}

export async function deleteCurrentUserData() {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const uid = userData.user.id;
  const tables = ['student_schedule_freezes', 'teacher_review_requests', 'teacher_assignments', 'teacher_student_subjects', 'teacher_student_links', 'practice_progress', 'classes', 'payments', 'students', 'schedules', 'calendar_overrides', 'pricing_items', 'app_settings', 'lesson_plans', 'learning_programs', 'ai_usage_logs', 'user_activity_log', 'professional_profiles', 'worksheets'];
  for (const table of tables) await client.from(table).delete().eq('user_id', uid);
  const { error } = await client.from('profiles').update({ account_status: 'deleted', deleted_at: new Date().toISOString(), display_name: null, avatar_url: null, phone_number: null, show_community_profile: false, show_community_contact: false, onboarding_completed: false, login_count: 0, active_student_count: 0 }).eq('user_id', uid);
  if (error) throw error;
}
