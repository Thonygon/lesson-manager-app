import { requireSupabase } from '@/lib/supabase';
import { normalizeTeachingLanguages } from '@/lib/teaching-languages';

export type TeacherPublicProfile = {
  public_id?: string;
  professional_name: string;
  headline: string;
  biography: string;
  subjects: string[];
  teaching_stages: string[];
  teaching_languages: string[];
  modalities: string[];
  country: string;
  city: string;
  education: string;
  avatar_url: string;
  contact_email: string;
  contact_phone: string;
  show_community_email: boolean;
  show_community_phone: boolean;
  show_web_email: boolean;
  show_web_phone: boolean;
  published_web: boolean;
};

export async function getMyTeacherPublicProfile(): Promise<TeacherPublicProfile | null> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Session required');
  const { data, error } = await client.from('classio_teacher_public_profiles').select('*').eq('teacher_id', auth.user.id).maybeSingle();
  if (error) throw error;
  return data ? { ...(data as TeacherPublicProfile), teaching_languages: normalizeTeachingLanguages(data.teaching_languages) } : null;
}

export async function saveMyTeacherPublicProfile(profile: TeacherPublicProfile): Promise<string> {
  const { data, error } = await requireSupabase().rpc('classio_save_teacher_public_profile', { p_profile: { ...profile, teaching_languages: normalizeTeachingLanguages(profile.teaching_languages) } });
  if (error) throw error;
  return String(data);
}

export async function resolvePublicTeacher(publicId: string): Promise<string | null> {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(publicId)) return null;
  const { data, error } = await requireSupabase().rpc('classio_resolve_teacher_public_id', { p_public_id: publicId });
  if (error) throw error;
  return data ? String(data) : null;
}

export async function getCommunityTeacherContacts(teacherIds: string[]): Promise<Record<string, { email: string; phone: string }>> {
  if (!teacherIds.length) return {};
  const result: Record<string, { email: string; phone: string }> = {};
  for (let index = 0; index < teacherIds.length; index += 100) {
    const { data, error } = await requireSupabase().rpc('classio_community_teacher_contacts', { p_teacher_ids: teacherIds.slice(index, index + 100) });
    if (error) throw error;
    for (const item of Array.isArray(data) ? data : []) result[String(item.teacher_id)] = { email: String(item.email || ''), phone: String(item.phone || '') };
  }
  return result;
}
