/** Streamlit practice_engine._normalize_answer, including typographic punctuation and Unicode marks. */
export function normalizePracticeAnswer(value: unknown): string {
  return String(value ?? '').trim().replace(/[’‘]/g, "'").replace(/[“”]/g, '"').replace(/[—–]/g, '-')
    .normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}_\s'/-]/gu, ' ').replace(/\s+/g, ' ').trim();
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
