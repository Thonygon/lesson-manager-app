// Source: streamlit/helpers/learning_programs.py:_STAGE_STRUCTURE_RULES and _ENGINE_STRUCTURE_OVERRIDES.
type StructureRule = { unitsDefault: number; unitsMin: number; unitsMax: number; lessonsDefault: number; lessonsMin: number; lessonsMax: number };
const rules: Record<string, StructureRule> = {
  early_primary: { unitsDefault: 8, unitsMin: 6, unitsMax: 8, lessonsDefault: 4, lessonsMin: 3, lessonsMax: 5 },
  upper_primary: { unitsDefault: 10, unitsMin: 8, unitsMax: 11, lessonsDefault: 4, lessonsMin: 3, lessonsMax: 5 },
  lower_secondary: { unitsDefault: 10, unitsMin: 8, unitsMax: 11, lessonsDefault: 4, lessonsMin: 3, lessonsMax: 6 },
  upper_secondary: { unitsDefault: 11, unitsMin: 9, unitsMax: 12, lessonsDefault: 4, lessonsMin: 3, lessonsMax: 6 },
  adult_stage: { unitsDefault: 10, unitsMin: 8, unitsMax: 12, lessonsDefault: 4, lessonsMin: 3, lessonsMax: 6 },
};
export function programStructureRule(subject: string, stage: string): StructureRule {
  const family = subject.toLowerCase().replaceAll(' ', '_');
  const base = rules[stage] || rules.upper_primary;
  if (stage === 'adult_stage' && ['english', 'spanish', 'language'].includes(family)) return { ...base, unitsDefault: 11, lessonsMax: 5 };
  if (stage === 'adult_stage' && family === 'study_skills') return { unitsDefault: 8, unitsMin: 6, unitsMax: 10, lessonsDefault: 3, lessonsMin: 2, lessonsMax: 4 };
  return base;
}
export function clampProgramStructure(subject: string, stage: string, requestedUnits?: number, requestedLessons?: number) {
  const rule = programStructureRule(subject, stage);
  const clamp = (value: number | undefined, fallback: number, min: number, max: number) => Number.isFinite(value) ? Math.max(min, Math.min(max, Math.round(value!))) : fallback;
  return { units: clamp(requestedUnits, rule.unitsDefault, rule.unitsMin, rule.unitsMax), lessonsPerUnit: clamp(requestedLessons, rule.lessonsDefault, rule.lessonsMin, rule.lessonsMax), rule };
}
