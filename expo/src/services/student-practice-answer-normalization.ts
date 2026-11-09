/** Streamlit practice_engine._normalize_answer, including typographic punctuation and Unicode marks. */
export function normalizePracticeAnswer(value: unknown): string {
  return String(value ?? '').trim().replace(/[’‘]/g, "'").replace(/[“”]/g, '"').replace(/[—–]/g, '-')
    .normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}_\s'/-]/gu, ' ').replace(/\s+/g, ' ').trim();
}

const NEGATIONS = new Set(['no', 'not', 'never', 'nunca', 'jamas', 'sin', 'without', 'degil', 'yok']);
const CONFLICTS = new Set(['pero', 'but', 'however', 'instead', 'aunque', 'except', 'fakat', 'ama']);
const NUMBER_WORDS = new Set(['cero', 'uno', 'una', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez', 'once', 'doce', 'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']);

/** A complete model phrase can appear inside a fuller student sentence.
 * This deliberately does not guess that word overlap or a short fragment is equivalent. */
export function matchesExpandedModelAnswer(student: unknown, model: unknown, prompt?: unknown): boolean {
  const answer = normalizePracticeAnswer(student);
  const expected = normalizePracticeAnswer(model);
  const modelWords = expected.split(' ').filter(Boolean);
  const answerWords = answer.split(' ').filter(Boolean);
  if (modelWords.length < 3 || expected.length < 12) return false;
  const negations = (words: string[]) => [...new Set(words.filter((word) => NEGATIONS.has(word)))].sort().join('|');
  if (negations(answerWords) !== negations(modelWords)) return false;
  const phraseStart = (whole: string[], part: string[]) => whole.findIndex((_, index) => part.every((word, offset) => whole[index + offset] === word));
  const fullModelStart = answerWords.length > modelWords.length && answerWords.length <= modelWords.length + 12 ? phraseStart(answerWords, modelWords) : -1;
  if (fullModelStart >= 0) {
    const extra = [...answerWords.slice(0, fullModelStart), ...answerWords.slice(fullModelStart + modelWords.length)];
    const modelNumbers = new Set(modelWords.filter((word) => NUMBER_WORDS.has(word) || /^\d+$/.test(word)));
    return !extra.some((word) => CONFLICTS.has(word) || ((NUMBER_WORDS.has(word) || /^\d+$/.test(word)) && !modelNumbers.has(word)));
  }
  // A shorter sentence is safe only when the omitted model context is already
  // in the question. A fragment like "Elena se levanta" still cannot pass.
  if (answerWords.length < 4 || answerWords.length < Math.ceil(modelWords.length * 0.5)) return false;
  const answerStart = phraseStart(modelWords, answerWords);
  if (answerStart < 0) return false;
  const omitted = [...modelWords.slice(0, answerStart), ...modelWords.slice(answerStart + answerWords.length)];
  const questionWords = new Set(normalizePracticeAnswer(prompt).split(' '));
  return omitted.length > 0 && omitted.every((word) => questionWords.has(word)) && !omitted.some((word) => NEGATIONS.has(word) || NUMBER_WORDS.has(word) || /^\d+$/.test(word));
}

export function canonicalTrueFalse(value: unknown): string {
  const answer = normalizePracticeAnswer(value).replace(/^(?:answer|respuesta|cevap)\s*[:.-]?\s*/, '');
  if (['true', 't', 'v', 'yes', 'si', 'verdadero', 'verdadera', 'dogru', 'evet'].includes(answer)) return 'true';
  if (['false', 'f', 'no', 'falso', 'falsa', 'yanlis', 'yanlıs', 'hayir', 'hayır'].includes(answer)) return 'false';
  return answer;
}

export function choiceIndex(value: unknown, optionCount: number): number {
  const answer = normalizePracticeAnswer(value);
  const marker = answer.match(/^(?:(?:option|opcion|opcao|secenek|choice|answer)\s*)?([a-z]|\d+)(?:[).:-].*)?$/);
  if (!marker) return -1;
  const index = /^\d+$/.test(marker[1]) ? Number(marker[1]) - 1 : marker[1].charCodeAt(0) - 97;
  return index >= 0 && index < optionCount ? index : -1;
}

export function canonicalChoice(value: unknown, options: string[]): string {
  const optionText = (item: unknown) => normalizePracticeAnswer(String(item ?? '').replace(/^\s*(?:option\s*)?[A-Z][).:-]\s*/i, ''));
  const index = choiceIndex(value, options.length);
  if (index >= 0) return optionText(options[index]);
  return optionText(value);
}
