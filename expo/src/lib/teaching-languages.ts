const ALIASES: Record<string, string> = {
  en: 'en', eng: 'en', english: 'en', inglés: 'en', ingles: 'en', i̇ngilizce: 'en',
  es: 'es', spa: 'es', spanish: 'es', español: 'es', espanol: 'es', i̇spanyolca: 'es',
  tr: 'tr', tur: 'tr', turkish: 'tr', türkçe: 'tr', turkce: 'tr',
};

export function canonicalTeachingLanguage(value: unknown): string {
  const original = String(value ?? '').trim();
  return ALIASES[original.toLocaleLowerCase()] || original.toLocaleLowerCase();
}

export function normalizeTeachingLanguages(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map(canonicalTeachingLanguage).filter(Boolean))];
}

export function teachingLanguageLabel(value: string, locale: string): string {
  const code = canonicalTeachingLanguage(value);
  let name: string | undefined;
  try { name = new Intl.DisplayNames([locale], { type: 'language' }).of(code); }
  catch { /* Preserve legacy free-text values while the database is normalized. */ }
  const label = name && name !== code ? name : value.replaceAll('_', ' ');
  return label.charAt(0).toLocaleUpperCase(locale) + label.slice(1);
}
