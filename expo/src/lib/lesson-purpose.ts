export const LESSON_PURPOSES = ['Introduce concept', 'Practice skill', 'Review topic', 'Diagnose difficulty', 'Discussion and exploration'] as const;

const keys: Record<string, string> = {
  introduce_concept: 'introduce_concept',
  practice_skill: 'practice_skill',
  review_topic: 'review_topic',
  diagnose_difficulty: 'diagnose_difficulty',
  discussion_and_exploration: 'discussion_exploration',
  discussion_exploration: 'discussion_exploration',
};

export function lessonPurposeKey(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, '_');
  return keys[normalized] || normalized;
}

export function lessonPurposeOption(value: string): string {
  return LESSON_PURPOSES.find((option) => lessonPurposeKey(option) === lessonPurposeKey(value)) || value;
}

export function lessonPurposeLabel(value: string, translate: (key: string) => string): string {
  const key = `resources.term.${lessonPurposeKey(value)}`;
  const label = translate(key);
  return label === key ? value.replaceAll('_', ' ') : label;
}
