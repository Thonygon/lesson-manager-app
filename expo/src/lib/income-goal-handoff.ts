import AsyncStorage from '@react-native-async-storage/async-storage';

import { CURRENCY_FACTORS, type IncomeCurrency } from '@/lib/income-planner';

const KEY = 'classio.pendingIncomeGoal.v1';
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

type PendingIncomeGoal = { amount: number; currency: IncomeCurrency; year: number; createdAt: number };

export function parsePendingIncomeGoal(raw: string | null, now = Date.now()): PendingIncomeGoal | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as PendingIncomeGoal;
    if (!value || !Number.isFinite(value.amount) || value.amount <= 0 || value.amount > 1e12 || !Object.hasOwn(CURRENCY_FACTORS, value.currency) || value.year !== new Date(now).getFullYear() || !Number.isFinite(value.createdAt) || value.createdAt > now || now - value.createdAt > MAX_AGE_MS) return null;
    return value;
  } catch { return null; }
}

export async function savePendingIncomeGoal(amount: number, currency: IncomeCurrency) {
  if (!Number.isFinite(amount) || amount <= 0 || amount > 1e12 || !Object.hasOwn(CURRENCY_FACTORS, currency)) throw new Error('Invalid income goal.');
  await AsyncStorage.setItem(KEY, JSON.stringify({ amount, currency, year: new Date().getFullYear(), createdAt: Date.now() } satisfies PendingIncomeGoal));
}

export async function getPendingIncomeGoal() {
  const raw = await AsyncStorage.getItem(KEY);
  const value = parsePendingIncomeGoal(raw);
  if (!value && raw) await AsyncStorage.removeItem(KEY);
  return value;
}

export async function clearPendingIncomeGoal() { await AsyncStorage.removeItem(KEY); }
