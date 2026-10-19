// Mirrors streamlit/helpers/quick_exam_builder.py:_LENGTH_SPEC.
export const EXAM_LENGTH_RULES = {
  short: { sections: 3, questionsMin: 4, questionsMax: 5 },
  medium: { sections: 4, questionsMin: 5, questionsMax: 7 },
  long: { sections: 5, questionsMin: 6, questionsMax: 10 },
} as const;

export type ExamLength = keyof typeof EXAM_LENGTH_RULES;

export function examLengthRule(value: unknown) {
  const key = String(value || '').toLowerCase();
  return EXAM_LENGTH_RULES[key === 'short' || key === 'long' ? key : 'medium'];
}
