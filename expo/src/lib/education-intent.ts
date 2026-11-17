const KEY = 'classio-education-connection-intent';
const MAX_AGE_MS = 30 * 60 * 1000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type EducationIntent = { publicId: string; subject: string; savedAt: number };

export function educationIntentFromParams(publicId: unknown, subject: unknown = ''): EducationIntent | null {
  if (typeof publicId !== 'string' || !UUID.test(publicId)) return null;
  return { publicId, subject: typeof subject === 'string' ? subject.slice(0, 80) : '', savedAt: Date.now() };
}

export function rememberEducationIntent(publicId: unknown, subject: unknown = ''): EducationIntent | null {
  if (typeof window === 'undefined') return null;
  const intent = educationIntentFromParams(publicId, subject);
  if (!intent) return null;
  window.sessionStorage.setItem(KEY, JSON.stringify(intent));
  return intent;
}

export function currentEducationIntent(): EducationIntent | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    if (!raw) return null;
    const item = JSON.parse(raw) as EducationIntent;
    if (!UUID.test(item.publicId) || !Number.isFinite(item.savedAt) || Date.now() - item.savedAt > MAX_AGE_MS) {
      window.sessionStorage.removeItem(KEY); return null;
    }
    return item;
  } catch { window.sessionStorage.removeItem(KEY); return null; }
}

export function educationIntentDestination(): string | null {
  const intent = currentEducationIntent();
  if (!intent) return null;
  const query = new URLSearchParams({ publicId: intent.publicId });
  if (intent.subject) query.set('subject', intent.subject);
  return `/education-connect?${query}`;
}

export function clearEducationIntent() {
  if (typeof window !== 'undefined') window.sessionStorage.removeItem(KEY);
}
