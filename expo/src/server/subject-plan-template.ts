import snapshots from './source-subject-plan-templates.json';
import { displayTopic } from './general-plan-template';

type TemplateIndex = Record<string, Record<string, Record<string, Record<string, Record<string, Record<string, number>>>>>>;
const index = snapshots.index as unknown as TemplateIndex;

export function subjectPlanTemplate(input: { subject: string; topic: string; stage: string; level: string; purpose: string; planLanguage: string }): Record<string, unknown> | null {
  const subject = input.subject.trim().toLowerCase().replaceAll(' ', '_');
  const language = ['en', 'es', 'tr'].includes(input.planLanguage) ? input.planLanguage : 'en';
  const variants = index[subject]?.[language]?.[input.stage]?.[input.level]?.[input.purpose];
  if (!variants) return null;
  const topic = input.topic.trim();
  const bankTopic = topic.toLowerCase();
  const source = snapshots.templates[variants[bankTopic] ?? variants.default];
  if (!source) return null;
  const capitalized = displayTopic(topic);
  const replace = (value: unknown): unknown => {
    if (typeof value === 'string') return value.replaceAll('Zztopicmarker', capitalized).replaceAll('zztopicmarker', topic);
    if (Array.isArray(value)) return value.map(replace);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, replace(child)]));
    return value;
  };
  return replace(source) as Record<string, unknown>;
}
