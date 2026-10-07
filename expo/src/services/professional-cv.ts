import { requireSupabase } from '@/lib/supabase';
import sourceCountries from './cv-countries.json';

export const CV_COUNTRIES: string[] = sourceCountries;
export function validCvPhone(value: string): boolean {
  const phone = value.trim();
  return !phone || (/^[\d+()]+$/.test(phone) && phone.replace(/\D/g, '').length >= 6);
}
export function profileCvDefaults(profile: Record<string, unknown>): Partial<TemplateCvInput> {
  const list = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && !!item.trim()).join(', ') : '';
  const country = String(profile.country || '').trim();
  const role = String(profile.primary_role || profile.role || 'teacher');
  return { fullName: String(profile.display_name || '').trim(), email: String(profile.email || '').trim(), phone: String(profile.phone_number || '').replace(/[^\d+()]/g, ''), location: CV_COUNTRIES.includes(country) ? country : '', role: role === 'tutor' ? 'tutor' : 'teacher', subjects: list(profile.primary_subjects), teachingStages: list(profile.teaching_stages), teachingLanguages: list(profile.teaching_languages) };
}

export type CvLocale = 'en' | 'es' | 'tr';
export type TemplateCvInput = {
  fullName: string; email: string; phone: string; location: string; role: 'teacher' | 'tutor';
  subjects: string; teachingStages: string; teachingLanguages: string;
  summary: string; education: string; certifications: string; experience: string; skills: string;
  availability: string; rate: string;
};

const splitComma = (value: string) => value.replaceAll('\n', ',').split(',').map((item) => item.trim()).filter(Boolean);
const splitLines = (value: string) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
const defaultSummary: Record<CvLocale, (input: TemplateCvInput, subjects: string[], stages: string[]) => string> = {
  en: (input, subjects, stages) => `${input.role === 'tutor' ? 'Tutor' : 'Teacher'} of ${subjects.join(', ')} working with ${stages.join(', ')} learners.`,
  es: (input, subjects, stages) => `${input.role === 'tutor' ? 'Tutoría' : 'Docencia'} de ${subjects.join(', ')} para estudiantes de ${stages.join(', ')}.`,
  tr: (input, subjects, stages) => `${stages.join(', ')} düzeyindeki öğrencilere ${subjects.join(', ')} öğreten ${input.role === 'tutor' ? 'özel öğretmen' : 'öğretmen'}.`,
};

export function buildTemplateCv(input: TemplateCvInput, locale: CvLocale): Record<string, unknown> {
  const subjects = splitComma(input.subjects);
  const stages = splitComma(input.teachingStages);
  const languages = splitComma(input.teachingLanguages);
  if (!input.fullName.trim() || !input.location.trim() || !subjects.length || !stages.length || !languages.length) {
    throw new Error('Name, location, subjects, teaching stages, and teaching languages are required.');
  }
  if (!CV_COUNTRIES.includes(input.location.trim())) throw new Error('Choose a valid country.');
  if (!validCvPhone(input.phone)) throw new Error('Enter a phone number with at least six digits, using only digits, +, ( and ).');
  return {
    title: `CV – ${input.fullName.trim()}`,
    full_name: input.fullName.trim(), email: input.email.trim(), phone: input.phone.trim(), location: input.location.trim(),
    date_of_birth: '', sex: '', role: input.role, subjects,
    professional_summary: input.summary.trim() || defaultSummary[locale](input, subjects, stages),
    teaching_stages: stages, teaching_languages: languages,
    education: splitLines(input.education), certifications: splitComma(input.certifications),
    experience: splitLines(input.experience), skills: splitComma(input.skills),
    availability: input.availability.trim(), rate: input.rate.trim(), source_type: 'template', avatar_url: '',
  };
}

export async function saveTemplateCv(document: Record<string, unknown>): Promise<void> {
  const client = requireSupabase();
  const { data, error: authError } = await client.auth.getUser();
  if (authError || !data.user) throw authError ?? new Error('Your session has expired.');
  const { data: profile, error: profileError } = await client.from('profiles').select('role,primary_role,can_teach').eq('user_id', data.user.id).maybeSingle();
  if (profileError || !profile) throw profileError ?? new Error('Teaching access could not be verified.');
  if (profile.can_teach === false || (profile.can_teach == null && !['teacher', 'tutor'].includes(String(profile.primary_role || profile.role || '')))) {
    throw new Error('Teacher access is required.');
  }
  const { error } = await client.from('professional_profiles').insert({
    user_id: data.user.id, doc_type: 'cv', title: String(document.title || 'CV'), source_type: 'template',
    cv_json: document, ai_prompt: '', status: 'active', created_at: new Date().toISOString(),
  });
  if (error) throw error;
}
