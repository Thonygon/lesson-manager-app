export function educationLabel(value: unknown, t: (key: string) => string) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const key = `profile.${raw}`;
  const translated = t(key);
  return translated === key ? raw.replaceAll('_', ' ') : translated;
}
