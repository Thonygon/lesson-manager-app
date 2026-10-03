// Sources: streamlit/helpers/answer_key_utils.py and quick_exam_builder.py:repair_exam_answer_key.
type RecordValue = Record<string, unknown>;
const asRecord = (value: unknown): RecordValue => value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
const asList = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const cleanText = (value: unknown) => String(value ?? '').replace(/[“”]/g, '"').replace(/[‘’]/g, "'").replace(/[—–]/g, '-').replace(/\s+/g, ' ').trim();
const cleanItem = (value: unknown) => cleanText(value).replace(/^(?:[\[({]+\s*)?(?:['"]+\s*)?(?:\(?\d+\)?|[A-Za-z])[.)\-:]\s*/, '').replace(/^[\[({]+\s*/, '').replace(/\s*[\])}]+$/, '').replace(/^['"]+|['"]+$/g, '').replace(/[,;]+$/, '').trim();

function parseSequence(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value;
  const source = String(value ?? '').trim();
  if (!source.startsWith('[') || !source.endsWith(']')) return null;
  try { const parsed = JSON.parse(source); if (Array.isArray(parsed)) return parsed; } catch { /* Python list syntax below. */ }
  const inner = source.slice(1, -1).trim();
  if (!inner) return [];
  const quoted = [...inner.matchAll(/(['"])((?:\\.|(?!\1)[^\\])*)\1\s*(?:,|$)/g)].map((match) => match[2].replace(/\\(['"\\])/g, '$1'));
  return quoted.length && quoted.join('').length ? quoted : null;
}

export function splitAnswerKeyItems(raw: unknown, expectedCount?: number): string[] {
  const sequence = parseSequence(raw);
  let items: string[];
  if (sequence) items = sequence.map(cleanItem).filter(Boolean);
  else {
    const source = String(raw ?? '').replace(/[“”]/g, '"').replace(/[‘’]/g, "'").replace(/[—–]/g, '-').trim();
    if (!source) items = [];
    else {
      const numbered = [...source.matchAll(/(?:^|[\s\[({,;])['"]?\s*((?:\(?\d+\)?|[A-Za-z])[.)\-:])\s*(.*?)(?=(?:[\s\])},;]+['"]?\s*(?:\(?\d+\)?|[A-Za-z])[.)\-:]\s)|$)/gs)].map((match) => cleanItem(match[2])).filter(Boolean);
      if (numbered.length >= 2 || (expectedCount && numbered.length >= expectedCount)) items = numbered;
      else {
        let candidate = source.startsWith('[') && source.endsWith(']') ? source.slice(1, -1).trim() : source;
        candidate = candidate.replace(/['"]\s*[,;]\s*['"]/g, '\n').replace(/\s*;\s*(?=(?:\(?\d+\)?|[A-Za-z])[.)\-:]\s)/g, '\n');
        if (expectedCount && expectedCount > 1 && !candidate.includes('\n')) candidate = candidate.replace(/\s+(?=(?:\(?\d+\)?|[A-Za-z])[.)\-:]\s)/g, '\n');
        let parts = candidate.split(/\n+/).filter((part) => part.trim());
        if (parts.length === 1 && candidate.includes(';')) parts = candidate.split(/\s*;\s*/).filter((part) => part.trim());
        if (parts.length === 1 && expectedCount && expectedCount > 1) parts = parts[0].split(/(?<=[.!?])\s+/).filter((part) => part.trim());
        items = parts.map(cleanItem).filter(Boolean);
      }
    }
  }
  if (expectedCount !== undefined) return [...items.slice(0, expectedCount), ...Array(Math.max(0, expectedCount - items.length)).fill('')];
  return items;
}

export function worksheetAnswerCount(document: RecordValue): number {
  const kind = String(document.worksheet_type || '');
  if (kind === 'multiple_choice') return asList(document.multiple_choice_items).length;
  if (kind === 'matching') return asList(document.matching_pairs).length || asList(document.left_items).length;
  if (kind === 'true_false') return asList(document.true_false_statements).length || asList(document.questions).length;
  if (['fill_in_the_blanks', 'short_answer', 'reading_comprehension', 'error_correction'].includes(kind)) return asList(document.questions).length;
  return 0;
}

export function normalizeWorksheetAnswerKey(document: RecordValue): RecordValue {
  const count = worksheetAnswerCount(document);
  if (!count) return document;
  return { ...document, answer_key: splitAnswerKeyItems(document.answer_key, count).filter(Boolean).join('\n') };
}

function answerValue(value: unknown): unknown {
  return typeof value === 'string' ? cleanItem(value) : value;
}

function canonicalMatchingAnswer(value: unknown, choices: string[]): unknown {
  const entry = asRecord(value);
  const candidate = Object.keys(entry).length === 1 ? Object.values(entry)[0] : value;
  const marker = cleanText(candidate).replace(/^option\s+/i, '');
  const index = /^[A-Za-z]$/.test(marker) ? marker.toUpperCase().charCodeAt(0) - 65 : /^\d+$/.test(marker) ? Number(marker) - 1 : -1;
  return index >= 0 && index < choices.length && choices[index] ? choices[index] : value;
}

export function repairExamAnswerKey(document: RecordValue): RecordValue {
  const sections = asList(document.sections).map(asRecord);
  const existing = asList(asRecord(document.answer_key).sections).map(asRecord);
  const repaired = sections.map((section, index) => {
    const questions = asList(section.questions).map(asRecord);
    const supplied = asList(existing[index]?.answers).length ? asList(existing[index]?.answers) : asList(section.answers);
    const answers = supplied.flatMap((value) => {
      if (typeof value === 'string') { const cleaned = cleanItem(value); return cleaned ? [cleaned] : []; }
      return value && typeof value === 'object' && !Array.isArray(value) ? [answerValue(value)] : [];
    });
    if (String(section.type || '') === 'multiple_choice' && answers.length < questions.length) {
      for (let questionIndex = answers.length; questionIndex < questions.length; questionIndex += 1) {
        const question = questions[questionIndex];
        answers.push(answerValue(question.answer || question.correct_answer || question.correct || ''));
      }
    }
    const choices = questions.map((question) => cleanText(question.right));
    const canonical = String(section.type || '') === 'matching' ? answers.map((answer) => canonicalMatchingAnswer(answer, choices)) : answers;
    return { title: cleanText(existing[index]?.title || section.title), answers: canonical };
  });
  return { ...document, sections: sections.map((section, index) => ({ ...section, answers: repaired[index].answers })), answer_key: { ...asRecord(document.answer_key), sections: repaired } };
}
