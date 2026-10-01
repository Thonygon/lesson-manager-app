import type { PublicResource } from '@/services/public-data';

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const normalized = (values: unknown[]) => values.map((value) => String(value || '')).join(' ').trim().replace(/\s+/g, ' ');
const tokens = (value: string) => new Set(value.toLocaleLowerCase().split(/[^\p{L}\p{N}]+/u).filter((token) => token.length >= 3));

// Matches difflib.SequenceMatcher's matching-block ratio for ordinary short text.
function sequenceRatio(left: string, right: string) {
  const a = Array.from(left);
  const b = Array.from(right);
  if (!a.length && !b.length) return 1;
  const matching = (alo: number, ahi: number, blo: number, bhi: number): number => {
    let bestA = alo; let bestB = blo; let bestSize = 0;
    let previous = new Map<number, number>();
    for (let i = alo; i < ahi; i += 1) {
      const current = new Map<number, number>();
      for (let j = blo; j < bhi; j += 1) {
        if (a[i] !== b[j]) continue;
        const size = (previous.get(j - 1) || 0) + 1;
        current.set(j, size);
        if (size > bestSize) { bestA = i - size + 1; bestB = j - size + 1; bestSize = size; }
      }
      previous = current;
    }
    if (!bestSize) return 0;
    return bestSize + matching(alo, bestA, blo, bestB) + matching(bestA + bestSize, ahi, bestB + bestSize, bhi);
  };
  return 2 * matching(0, a.length, 0, b.length) / (a.length + b.length);
}

export function semanticTextAffinity(leftValues: unknown[], rightValues: unknown[]) {
  const left = normalized(leftValues);
  const right = normalized(rightValues);
  if (!left || !right) return 0;
  const foldedLeft = left.toLocaleLowerCase();
  const foldedRight = right.toLocaleLowerCase();
  if (foldedLeft === foldedRight) return 1;
  const leftTokens = tokens(left);
  const rightTokens = tokens(right);
  const intersection = [...leftTokens].filter((token) => rightTokens.has(token)).length;
  const overlap = clamp(intersection / Math.max(3, Math.min(leftTokens.size, rightTokens.size, 8)));
  const containment = foldedLeft.includes(foldedRight) || foldedRight.includes(foldedLeft) ? 0.82 : 0;
  return clamp(Math.max(overlap, containment, sequenceRatio(foldedLeft, foldedRight) * 0.86));
}

export function resourceSemanticAffinity(resource: PublicResource, nextTopicTitles: string[], nextTopicTokens: string[], weakTopics: string[]) {
  const raw = resource.raw;
  const exerciseTypes = Array.isArray(raw.exercise_types) ? raw.exercise_types : [];
  return semanticTextAffinity(
    [resource.title, resource.topic, raw.description, raw.worksheet_type, raw.lesson_purpose, raw.exam_length, exerciseTypes.join(' ')],
    [resource.topic, resource.topic, nextTopicTitles.join(' '), '', '', '', '', '', '', nextTopicTokens.join(' '), weakTopics.join(' ')],
  );
}
