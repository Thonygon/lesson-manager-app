const CONFUSABLES: Record<string, string> = { 'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x', 'і': 'i', 'ӏ': 'l', 'α': 'a', 'ε': 'e', 'ο': 'o', 'ρ': 'p' };
const normalizeToken = (value: string) => value.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase().replace(/[аеорсхіӏαεορ]/gu, (character) => CONFUSABLES[character] || character);
type Token = { value: string; start: number; end: number };
const tokens = (value: string): Token[] => [...value.matchAll(/[\p{L}\p{N}]+/gu)].map((match) => ({ value: normalizeToken(match[0]), start: match.index, end: match.index + match[0].length }));
function oneEditOrLess(left: string, right: string): boolean {
  if (Math.abs(left.length - right.length) > 1) return false;
  let i = 0; let j = 0; let edits = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) { i += 1; j += 1; continue; }
    if (++edits > 1) return false;
    if (left.length >= right.length) i += 1;
    if (left.length <= right.length) j += 1;
  }
  return edits + (left.length - i) + (right.length - j) <= 1;
}
function redactKnownStudentNames(value: string, knownNames: readonly string[]): string {
  const promptTokens = tokens(value);
  const spans: { start: number; end: number }[] = [];
  for (const name of knownNames.slice(0, 5)) {
    const nameTokens = tokens(name.slice(0, 120)).map((token) => token.value).filter((token) => token.length >= 2);
    if (!nameTokens.length) continue;
    for (let i = 0; i < promptTokens.length; i += 1) {
      const window = promptTokens.slice(i, i + nameTokens.length);
      if (window.length === nameTokens.length && oneEditOrLess(window.map((token) => token.value).join(''), nameTokens.join('')) && nameTokens.join('').length >= 6) {
        spans.push({ start: window[0].start, end: window.at(-1)!.end });
      }
      if (nameTokens.some((token) => token.length >= 3 && token === promptTokens[i].value)) spans.push({ start: promptTokens[i].start, end: promptTokens[i].end });
    }
  }
  if (!spans.length) return value;
  spans.sort((a, b) => a.start - b.start || b.end - a.end);
  const merged: { start: number; end: number }[] = [];
  for (const span of spans) {
    const previous = merged.at(-1);
    if (previous && span.start <= previous.end) previous.end = Math.max(previous.end, span.end);
    else merged.push({ ...span });
  }
  for (const span of merged.reverse()) value = `${value.slice(0, span.start)}[student name removed]${value.slice(span.end)}`;
  return value;
}

function validTurkishIdentityNumber(value: string): boolean {
  if (!/^[1-9]\d{10}$/.test(value)) return false;
  const digits = [...value].map(Number);
  const odd = digits[0] + digits[2] + digits[4] + digits[6] + digits[8];
  const even = digits[1] + digits[3] + digits[5] + digits[7];
  return digits[9] === ((odd * 7 - even) % 10 + 10) % 10
    && digits[10] === digits.slice(0, 10).reduce((sum, digit) => sum + digit, 0) % 10;
}

/** Remove recognizable identifiers and selected-student name variants before provider calls. */
export function redactDirectIdentifiers(value: string, knownStudentNames: readonly string[] = []): string {
  return redactKnownStudentNames(value, knownStudentNames)
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '[email removed]')
    .replace(/\b(?:https?:\/\/)?(?:www\.)?wa\.me\/\+?\d{7,15}\b/gi, '[contact removed]')
    .replace(/\b(?:phone|tel(?:ephone|éfono|efon)?|mobile|móvil|contacto|whatsapp|gsm)\s*[:#-]?\s*\+?\d[\d\s().-]{6,}\d\b/gi, '[contact removed]')
    .replace(/(?<!\w)\+\d[\d\s().-]{7,}\d\b/g, '[contact removed]')
    .replace(/\b(?:address|dirección|domicilio|ikamet adresi|adres)\s*:\s*[^\n.;}]{5,120}/gi, '[address removed]')
    .replace(/\b(?:calle|avenida|avda\.?|carrera|street|st\.|avenue|ave\.|road|rd\.|sokak|cadde)\s+[\p{L}\d][\p{L}\d\s,º°#-]{2,60}\d+[\p{L}\d\s,º°#-]{0,25}/giu, '[address removed]')
    .replace(/(["']?(?:student_name|learner_name|student_full_name|student_email|student_phone|student_address)["']?\s*[:=]\s*)["']?[^,"'\n}]+["']?/gi, '$1"[student identifier removed]"')
    .replace(/\b(?:student name|nombre del alumno|nombre de la alumna|nombre del estudiante|öğrenci adı)\s*:\s*[^\n.;}]{2,100}/gi, '[student name removed]')
    .replace(/\b(?:tckn|t\.c\.\s*kimlik(?:\s*(?:no|numarası))?|dni|nie|nif|passport|pasaporte|pasaport|ssn|social security number)\s*([:#-]?)\s*([A-Z0-9-]{6,25})\b/giu,
      (match, delimiter: string, token: string) => delimiter === ':' || delimiter === '#' || /\d/.test(token) ? '[identity number removed]' : match)
    .replace(/\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]){11,30}\b/gi, '[bank account removed]')
    .replace(/(?<!\d)\d{11}(?!\d)/g, (candidate) => validTurkishIdentityNumber(candidate) ? '[identity number removed]' : candidate);
}
