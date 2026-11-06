import { LEGAL_PUBLICATION } from '@/lib/legal-publication.generated';
import { requiredLegalDocuments } from '@/lib/legal-acceptance';
import { requireSupabase } from '@/lib/supabase';

export async function acceptCurrentLegalDocuments(mode: 'teacher' | 'student', language: 'en' | 'es' | 'tr') {
  const documents = requiredLegalDocuments(mode, language);
  const terms = documents.find((item) => item.slug === 'terms');
  const teacherData = documents.find((item) => item.slug === 'teacher-data');
  if (!terms) throw new Error('The published terms are unavailable.');
  const { data, error } = await requireSupabase().rpc('classio_accept_legal_documents', {
    p_mode: mode,
    p_language: language,
    p_version: LEGAL_PUBLICATION.version,
    p_terms_sha256: terms.sha256,
    p_teacher_data_sha256: teacherData?.sha256 ?? null,
  });
  if (error) throw error;
  if (data !== true) throw new Error('Legal acceptance was not confirmed.');
}
