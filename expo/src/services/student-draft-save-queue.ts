type Answers = Record<string, string>;
type DraftState = { key: string; sessionId?: string; pending: Promise<string> | null; fingerprint: string };

/** Serializes draft writes so an insert cannot race another insert or final submission. */
export function createStudentDraftSaveQueue<T>(save: (material: T, answers: Answers, sessionId?: string) => Promise<string>) {
  let current: DraftState = { key: '', pending: null, fingerprint: '' };
  return {
    reset(key: string, sessionId?: string, answers?: Answers) {
      current = { key, sessionId, pending: null, fingerprint: answers ? JSON.stringify(answers) : '' };
    },
    key() { return current.key; },
    enqueue(key: string, material: T, answers: Answers): Promise<string> | null {
      const state = current;
      const fingerprint = JSON.stringify(answers);
      if (state.key !== key || state.fingerprint === fingerprint) return null;
      state.fingerprint = fingerprint;
      const prior = state.pending ?? Promise.resolve(state.sessionId || '');
      const pending = prior.catch(() => state.sessionId || '').then((id) => save(material, answers, id || state.sessionId));
      state.pending = pending;
      void pending.then((id) => { state.sessionId = id; }).catch(() => { state.fingerprint = ''; }).finally(() => { if (state.pending === pending) state.pending = null; });
      return pending;
    },
    async flush(): Promise<string | undefined> {
      const state = current;
      return state.pending ? await state.pending : state.sessionId;
    },
  };
}
