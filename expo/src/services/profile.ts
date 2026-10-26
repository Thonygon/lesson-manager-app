import { requireSupabase } from '@/lib/supabase';
import { hostingApiUrl } from '@/lib/hosting-api-url';
import type { ClassioRecord } from '@/services/classio-data';

export const PROFILE_COLUMNS = 'user_id,email,display_name,username,avatar_url,date_of_birth,sex,phone_number,role,primary_role,can_teach,can_study,last_active_mode,preferred_ui_language,timezone,country,preferred_currency,default_lesson_duration,primary_subjects,custom_subjects,teaching_stages,teaching_languages,education_level,show_community_profile,show_community_contact,onboarding_completed';

/** Match Streamlit's additive mode enablement: saving one mode must not revoke the other. */
export function profileModeSaveFields(record: ClassioRecord | null, selectedRole: 'teacher' | 'student') {
  const role = String(record?.role || '').trim();
  const primaryRole = String(record?.primary_role || '').trim();
  const fallbackRole = primaryRole || role;
  return {
    role: role || selectedRole,
    primary_role: primaryRole || selectedRole,
    can_teach: selectedRole === 'teacher' || record?.can_teach === true || (record?.can_teach == null && ['teacher', 'tutor'].includes(fallbackRole)),
    can_study: selectedRole === 'student' || record?.can_study === true || (record?.can_study == null && fallbackRole === 'student'),
    last_active_mode: selectedRole,
  };
}

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

/** Enable teaching alongside studying, matching Streamlit's opt-in action. */
export async function enableTeacherMode() {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('profiles').upsert({ user_id: userData.user.id, can_teach: true, can_study: true }, { onConflict: 'user_id' });
  if (error) throw error;
}

export async function activateProfileWorkspaceMode(mode: 'teacher' | 'student') {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('profiles').upsert({ user_id: userData.user.id, last_active_mode: mode, ...(mode === 'teacher' ? { can_teach: true } : { can_study: true }) }, { onConflict: 'user_id' });
  if (error) throw error;
}

/** Persist the first-login choice before opening either workspace. */
export async function chooseInitialWorkspaceRole(mode: 'teacher' | 'student', language: 'en' | 'es' | 'tr') {
  const client = requireSupabase();
  const { data: session, error: sessionError } = await client.auth.getSession();
  if (sessionError || !session.session) throw sessionError ?? new Error('Your session has expired.');
  const response = await fetch(hostingApiUrl('/api/choose-role'), { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.session.access_token}` }, body: JSON.stringify({ mode, language }) });
  const result = await response.json().catch(() => ({})) as { error?: string };
  if (!response.ok) throw new Error(result.error || 'Your choice could not be saved.');
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
  const { data, error } = await client.rpc('classio_delete_account_data', { p_user_id: userData.user.id });
  if (error) throw error;
  if (data !== true) throw new Error('Account deletion could not be confirmed.');
}
