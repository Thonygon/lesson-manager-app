import snapshots from './source-general-plan-templates.json';

type PlanLanguage = 'en' | 'es' | 'tr';
type Purpose = 'introduce_concept' | 'practice_skill' | 'review_topic' | 'diagnose_difficulty' | 'discussion_exploration';

const purposes = new Set<Purpose>(['introduce_concept', 'practice_skill', 'review_topic', 'diagnose_difficulty', 'discussion_exploration']);

export function displayTopic(topic: string): string {
  const clean = topic.trim().replace(/\s+/g, ' ').replace(/\s+([.,!?;:])/g, '$1').replace(/\s*-\s*/g, ' - ').replace(/\s*\/\s*/g, ' / ').replace(/\s+/g, ' ');
  return clean ? clean[0].toUpperCase() + clean.slice(1) : '';
}

export function generalPlanTemplate(input: { topic: string; level: string; purpose: string; planLanguage: string }): Record<string, unknown> {
  const language: PlanLanguage = ['en', 'es', 'tr'].includes(input.planLanguage) ? input.planLanguage as PlanLanguage : 'en';
  const purpose: Purpose = purposes.has(input.purpose as Purpose) ? input.purpose as Purpose : 'introduce_concept';
  const source = snapshots[language][purpose];
  const rawTopic = input.topic.trim();
  const capitalized = displayTopic(rawTopic);
  const replace = (value: unknown): unknown => {
    if (typeof value === 'string') return value.replaceAll('Zztopicmarker', capitalized).replaceAll('zztopicmarker', rawTopic).replaceAll('zzlevelmarker', input.level);
    if (Array.isArray(value)) return value.map(replace);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, replace(child)]));
    return value;
  };
  return replace(source) as Record<string, unknown>;
}
