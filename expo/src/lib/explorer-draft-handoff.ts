import AsyncStorage from '@react-native-async-storage/async-storage';

import type { SmartToolInput, SmartToolKind } from '@/services/smart-tools';

const KEY = 'classio.explorerDraft.v1';
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
const MAX_BYTES = 250_000;
const KINDS: SmartToolKind[] = ['plan', 'worksheet', 'exam', 'program'];

export type ExplorerDraft = {
  kind: SmartToolKind;
  input: SmartToolInput;
  document?: Record<string, unknown>;
  createdAt: number;
};

export function parseExplorerDraft(raw: string | null, now = Date.now()): ExplorerDraft | null {
  if (!raw || raw.length > MAX_BYTES) return null;
  try {
    const draft = JSON.parse(raw) as ExplorerDraft;
    if (!draft || !KINDS.includes(draft.kind) || draft.input?.kind !== draft.kind ||
      typeof draft.input.subject !== 'string' || typeof draft.input.stage !== 'string' ||
      typeof draft.input.level !== 'string' || typeof draft.input.topic !== 'string' ||
      typeof draft.input.notes !== 'string' || typeof draft.input.duration !== 'string' ||
      typeof draft.input.language !== 'string' || !Number.isFinite(draft.createdAt) ||
      draft.createdAt > now || now - draft.createdAt > MAX_AGE_MS ||
      (draft.document !== undefined && (!draft.document || typeof draft.document !== 'object' || Array.isArray(draft.document)))) return null;
    return draft;
  } catch { return null; }
}

export async function saveExplorerDraft(input: SmartToolInput, document?: Record<string, unknown>) {
  const raw = JSON.stringify({ kind: input.kind, input, ...(document ? { document } : {}), createdAt: Date.now() });
  if (!parseExplorerDraft(raw)) throw new Error('Explorer draft is too large or invalid.');
  await AsyncStorage.setItem(KEY, raw);
}

export async function getExplorerDraft() {
  const raw = await AsyncStorage.getItem(KEY);
  const draft = parseExplorerDraft(raw);
  if (raw && !draft) await AsyncStorage.removeItem(KEY);
  return draft;
}

export async function clearExplorerDraft() { await AsyncStorage.removeItem(KEY); }
