export type TranslationLookup = (key: string, params?: Record<string, string | number>) => string;

const SUBJECT_ALIASES: Record<string, string> = {
  english: 'english', ingles: 'english', ingilizce: 'english',
  spanish: 'spanish', espanol: 'spanish', ispanyolca: 'spanish',
  mathematics: 'mathematics', matematica: 'mathematics', matematicas: 'mathematics', matematik: 'mathematics', math: 'mathematics', maths: 'mathematics',
  science: 'science', ciencias: 'science', ciencia: 'science', fen: 'science', fen_bilimleri: 'science',
  music: 'music', musica: 'music', muzik: 'music',
  study_skills: 'study_skills', study_skill: 'study_skills', tecnicas_de_estudio: 'study_skills', calisma_becerileri: 'study_skills',
  turkish: 'turkish', turco: 'turkish', turkce: 'turkish',
  other: 'other', otro: 'other', otra: 'other', otra_materia: 'other', diger: 'other',
  general: 'general', unspecified: 'general',
};

const SUBJECT_TRANSLATION_KEYS: Record<string, string> = {
  english: 'smart.option.english', spanish: 'smart.option.spanish', mathematics: 'smart.option.mathematics',
  science: 'smart.option.science', music: 'smart.option.music', study_skills: 'smart.option.study_skills',
  turkish: 'smart.option.turkish', other: 'smart.option.other', general: 'dashboard.general',
};

function token(value: unknown) {
  return String(value ?? '').trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
    .replace(/[^a-z0-9ı]+/g, '_').replace(/^_+|_+$/g, '').replaceAll('ı', 'i');
}

export function canonicalSubjectKey(value: unknown) {
  const normalized = token(value);
  return SUBJECT_ALIASES[normalized] || normalized || 'general';
}

export function canonicalSubjectLabel(value: unknown, t?: TranslationLookup) {
  const key = canonicalSubjectKey(value);
  const translationKey = SUBJECT_TRANSLATION_KEYS[key];
  if (t && translationKey) return t(translationKey);
  const defaults: Record<string, string> = { english: 'English', spanish: 'Spanish', mathematics: 'Mathematics', science: 'Science', music: 'Music', study_skills: 'Study skills', turkish: 'Turkish', other: 'Other', general: 'General' };
  if (defaults[key]) return defaults[key];
  return key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function subjectFromRecord(record: Record<string, unknown>) {
  const raw = record.subject === 'Other' || record.subject === 'other'
    ? record.subject_custom || record.custom_subject_name || record.subject_display || record.subject
    : record.subject_label || record.subject_display || record.custom_subject_name || record.subject_key || record.subject;
  return canonicalSubjectKey(raw);
}
