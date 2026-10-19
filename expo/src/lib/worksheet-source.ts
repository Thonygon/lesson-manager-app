type WorksheetText = { instructions?: unknown; questions?: unknown; source_text?: unknown; reading_passage?: unknown };

const sourceReference = /\b(?:first|second|third|last|previous|following)\s+(?:paragraph|passage|text|article)\b|\b(?:paragraph|passage|text|article)\s+(?:above|below|provided|given)\b|(?:primer|segundo|tercer|último)\s+p[aá]rrafo|(?:texto|pasaje|artículo)\s+(?:anterior|siguiente|de arriba|proporcionado)|(?:ilk|ikinci|son)\s+paragraf|(?:yukarıdaki|aşağıdaki)\s+(?:metin|paragraf)/i;
const readTextInstruction = /\b(?:read the following (?:text|passage)|lee el siguiente texto|lea el siguiente texto|aşağıdaki metni oku)\b/i;

export function worksheetReferencesSource(document: WorksheetText): boolean {
  const questions = Array.isArray(document.questions) ? document.questions : [];
  return readTextInstruction.test(String(document.instructions || '')) || questions.some((question) => sourceReference.test(typeof question === 'string' ? question : JSON.stringify(question)));
}

export function worksheetHasSource(document: WorksheetText): boolean {
  return [document.source_text, document.reading_passage].some((value) => typeof value === 'string' && Boolean(value.trim()));
}
