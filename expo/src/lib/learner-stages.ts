import type { TranslationLookup } from '@/lib/subjects';

const known = new Set(['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage']);
const aliases: Record<string, string> = {
  adult: 'adult_stage', adults: 'adult_stage', adulto: 'adult_stage', adultos: 'adult_stage',
  adult_stage: 'adult_stage', yetiskin: 'adult_stage', yetiskinler: 'adult_stage',
  primary_early: 'early_primary', primary_upper: 'upper_primary',
};

export function canonicalLearnerStageKey(value: unknown) {
  const normalized = String(value ?? '').trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '');
  return aliases[normalized] || normalized;
}

export function learnerStageLabel(value: unknown, t: TranslationLookup) {
  const key = canonicalLearnerStageKey(value);
  if (!key) return '';
  return known.has(key) ? t(`profile.stage.${key}`) : key.replaceAll('_', ' ').replace(/\b\p{L}/gu, (letter) => letter.toLocaleUpperCase());
}
