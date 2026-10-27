import AsyncStorage from '@react-native-async-storage/async-storage';
import type { PublicResourceKind } from '@/services/public-data';

const KEY = 'classio.publicResourceHandoff.v1';
const MAX_AGE = 24 * 60 * 60 * 1000;
const KINDS: PublicResourceKind[] = ['program', 'plan', 'worksheet', 'exam', 'video'];

export type PublicResourceHandoff = { kind: PublicResourceKind; id: string; title: string; createdAt: number };

export function parsePublicResourceHandoff(raw: string | null, now = Date.now()): PublicResourceHandoff | null {
  if (!raw || raw.length > 1000) return null;
  try {
    const value = JSON.parse(raw) as PublicResourceHandoff;
    return value && KINDS.includes(value.kind) && /^[0-9]{1,80}$/.test(value.id) &&
      typeof value.title === 'string' && value.title.length <= 200 && Number.isFinite(value.createdAt) &&
      value.createdAt <= now && now - value.createdAt < MAX_AGE ? value : null;
  } catch { return null; }
}

export async function savePublicResourceHandoff(value: Omit<PublicResourceHandoff, 'createdAt'>) {
  const raw = JSON.stringify({ ...value, createdAt: Date.now() });
  if (!parsePublicResourceHandoff(raw)) throw new Error('Invalid resource handoff');
  await AsyncStorage.setItem(KEY, raw);
}

export async function getPublicResourceHandoff() {
  const raw = await AsyncStorage.getItem(KEY);
  const value = parsePublicResourceHandoff(raw);
  if (raw && !value) await AsyncStorage.removeItem(KEY);
  return value;
}

export async function clearPublicResourceHandoff() { await AsyncStorage.removeItem(KEY); }
