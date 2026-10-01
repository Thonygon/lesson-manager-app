import { requireSupabase } from '@/lib/supabase';

export type ProfessionalResource = {
  id: string;
  docType: 'cv' | 'cover_letter';
  title: string;
  sourceType: string;
  content: string;
  cv: Record<string, unknown>;
  targetEmployer: string;
  status: string;
  createdAt: string;
};

export async function getProfessionalResources(archived = false): Promise<ProfessionalResource[]> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data, error } = await client.from('professional_profiles').select('id,doc_type,title,source_type,content,cv_json,target_employer,status,created_at').eq('user_id', userData.user.id).eq('status', archived ? 'archived' : 'active').order('created_at', { ascending: false }).limit(1000);
  if (error) throw error;
  return (data ?? []).map((row) => ({
    id: String(row.id), docType: row.doc_type === 'cover_letter' ? 'cover_letter' : 'cv', title: String(row.title || (row.doc_type === 'cover_letter' ? 'Cover letter' : 'CV')), sourceType: String(row.source_type || ''), content: String(row.content || ''), cv: typeof row.cv_json === 'object' && row.cv_json ? row.cv_json as Record<string, unknown> : {}, targetEmployer: String(row.target_employer || ''), status: String(row.status || 'active'), createdAt: String(row.created_at || ''),
  }));
}

export async function setProfessionalResourceStatus(id: string, status: 'active' | 'archived'): Promise<void> {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('professional_profiles').update({ status }).eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}

export async function deleteProfessionalResource(id: string): Promise<void> {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from('professional_profiles').delete().eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}
