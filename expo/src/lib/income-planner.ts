// Planning assumptions kept in parity with streamlit/helpers/goal_explorer.py.
export const TEACHING_WEEKS = 44;
export const YOUTH_TEACHING_WEEKS = 36;
export const LESSONS_PER_STUDENT_WEEK = 1.5;
export const RATE_RANGES_USD = {
  English: { Online: [25, 40, 80], 'In person': [30, 50, 90] },
  Spanish: { Online: [25, 40, 80], 'In person': [30, 50, 90] },
  Mathematics: { Online: [30, 50, 100], 'In person': [35, 55, 110] },
  Science: { Online: [30, 50, 100], 'In person': [35, 55, 110] },
  Music: { Online: [25, 45, 90], 'In person': [30, 50, 100] },
  'Study skills': { Online: [20, 35, 70], 'In person': [25, 40, 80] },
} as const;
export type IncomeSubject = keyof typeof RATE_RANGES_USD;
export type IncomeModality = 'Online' | 'In person';
export type IncomeAudience = 'Kids' | 'Teens' | 'Adults';
export type IncomeEducation = 'Student' | 'Bachelor’s' | 'Master’s' | 'Doctorate';
export const CURRENCY_FACTORS = { USD: 1, EUR: .92, GBP: .79, TRY: 38, ARS: 1060, BRL: 5.1, MXN: 17.2, JPY: 155, CAD: 1.37, AUD: 1.55, CHF: .88, COP: 3950, CLP: 950, INR: 83.5, KRW: 1340, SEK: 10.8, NOK: 10.9, DKK: 6.9, PLN: 4, CNY: 7.25 } as const;
export type IncomeCurrency = keyof typeof CURRENCY_FACTORS;
const audienceFactor: Record<IncomeAudience, number> = { Kids: .75, Teens: .85, Adults: 1 };
const educationFactor: Record<IncomeEducation, number> = { Student: .7, 'Bachelor’s': .9, 'Master’s': 1, Doctorate: 1.15 };

export function convertPlanningAmount(amount: number, from: IncomeCurrency, to: IncomeCurrency) {
  if (!Number.isFinite(amount) || amount < 0) return 0;
  return Math.round(amount * CURRENCY_FACTORS[to] / CURRENCY_FACTORS[from]);
}

export function recommendedRange(subject: IncomeSubject, modalities: IncomeModality[], audiences: IncomeAudience[], education: IncomeEducation, currency: IncomeCurrency): [number, number, number] {
  const combinations = modalities.flatMap((modality) => audiences.map((audience) =>
    RATE_RANGES_USD[subject][modality].map((base) => base * audienceFactor[audience] * educationFactor[education] * CURRENCY_FACTORS[currency])));
  if (!combinations.length) return [0, 0, 0];
  return [
    Math.max(1, Math.round(Math.min(...combinations.map((row) => row[0])))),
    Math.max(1, Math.round(combinations.reduce((sum, row) => sum + row[1], 0) / combinations.length)),
    Math.max(1, Math.round(Math.max(...combinations.map((row) => row[2])))),
  ];
}

export function buildIncomePlan(goal: number, hourlyRate: number, audiences: IncomeAudience[]) {
  if (!Number.isFinite(goal) || !Number.isFinite(hourlyRate) || goal <= 0 || hourlyRate <= 0 || !audiences.length) return null;
  const effectiveWeeks = audiences.reduce((sum, audience) => sum + (audience === 'Adults' ? TEACHING_WEEKS : YOUTH_TEACHING_WEEKS), 0) / audiences.length;
  const annualHours = Math.ceil(goal / hourlyRate);
  const weeklyHours = Math.ceil(goal / (hourlyRate * effectiveWeeks));
  const studentsNeeded = Math.ceil(weeklyHours / LESSONS_PER_STUDENT_WEEK);
  const status = weeklyHours <= 24 ? 'comfortable' : weeklyHours <= 31 ? 'focused' : weeklyHours <= 42 ? 'ambitious' : 'overloaded';
  return { annualHours, weeklyHours, studentsNeeded, effectiveWeeks, status } as const;
}
