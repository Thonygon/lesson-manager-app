export const ANALYTICS_CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP', 'ARS', 'BRL', 'MXN', 'JPY', 'CAD', 'AUD', 'CHF', 'COP', 'CLP', 'INR', 'KRW', 'SEK', 'NOK', 'DKK', 'PLN', 'CNY'] as const;
export const INFLATION_COUNTRIES: Record<string, string> = {
  Argentina: 'ARG', Australia: 'AUS', Brazil: 'BRA', Canada: 'CAN', Chile: 'CHL', China: 'CHN', Colombia: 'COL', Denmark: 'DNK', France: 'FRA', Germany: 'DEU', India: 'IND', Italy: 'ITA', Japan: 'JPN', Mexico: 'MEX', Netherlands: 'NLD', Norway: 'NOR', Poland: 'POL', 'South Korea': 'KOR', Spain: 'ESP', Sweden: 'SWE', Switzerland: 'CHE', Turkey: 'TUR', 'United Kingdom': 'GBR', 'United States': 'USA',
};

const cache = new Map<string, { fetchedAt: number; rates: Record<string, number> }>();
const TTL_MS = 60 * 60 * 1000;
const cpiCache = new Map<string, { fetchedAt: number; values: Record<number, number> }>();

async function fetchWithTimeout(url: string, signal?: AbortSignal): Promise<Response> {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', onAbort, { once: true });
  const timeout = setTimeout(() => controller.abort(), 10000);
  try { return await fetch(url, { signal: controller.signal }); }
  finally { clearTimeout(timeout); signal?.removeEventListener('abort', onAbort); }
}

/** Same one-hour exchange-rate source and conversion rule as Streamlit helpers/currency.py. */
export async function getAnalyticsExchangeRate(base: string, display: string, signal?: AbortSignal): Promise<number> {
  if (base === display) return 1;
  if (!ANALYTICS_CURRENCIES.includes(base as typeof ANALYTICS_CURRENCIES[number]) || !ANALYTICS_CURRENCIES.includes(display as typeof ANALYTICS_CURRENCIES[number])) throw new Error('Unsupported currency.');
  let entry = cache.get(base);
  if (!entry || Date.now() - entry.fetchedAt >= TTL_MS) {
    const response = await fetchWithTimeout(`https://open.er-api.com/v6/latest/${base}`, signal);
    if (!response.ok) throw new Error('Exchange rates are unavailable.');
    const payload = await response.json() as { result?: string; rates?: Record<string, unknown> };
    if (payload.result !== 'success' || !payload.rates || typeof payload.rates !== 'object') throw new Error('Exchange rates are unavailable.');
    const rates: Record<string, number> = {};
    for (const [code, value] of Object.entries(payload.rates)) if (typeof value === 'number' && Number.isFinite(value) && value > 0) rates[code] = value;
    entry = { fetchedAt: Date.now(), rates };
    cache.set(base, entry);
  }
  const rate = entry.rates[display];
  if (!Number.isFinite(rate) || rate <= 0) throw new Error(`No exchange rate is available for ${display}.`);
  return rate;
}

/** Port of Streamlit's World Bank CPI lookup, cached for one day. */
export async function getAnalyticsCpi(country: string, signal?: AbortSignal): Promise<Record<number, number>> {
  const code = INFLATION_COUNTRIES[country];
  if (!code) throw new Error('Unsupported inflation country.');
  let entry = cpiCache.get(code);
  if (!entry || Date.now() - entry.fetchedAt >= 86400000) {
    const response = await fetchWithTimeout(`https://api.worldbank.org/v2/country/${code}/indicator/FP.CPI.TOTL?date=2000:${new Date().getFullYear()}&format=json&per_page=100`, signal);
    if (!response.ok) throw new Error('Inflation data are unavailable.');
    const payload = await response.json() as unknown;
    const observations = Array.isArray(payload) && Array.isArray(payload[1]) ? payload[1] as { date?: unknown; value?: unknown }[] : [];
    const values: Record<number, number> = {};
    for (const row of observations) {
      const year = Number(row.date); const value = Number(row.value);
      if (Number.isInteger(year) && year >= 2000 && Number.isFinite(value) && value > 0 && row.value != null) values[year] = value;
    }
    if (!Object.keys(values).length) throw new Error('Inflation data are unavailable.');
    entry = { fetchedAt: Date.now(), values }; cpiCache.set(code, entry);
  }
  return entry.values;
}

export function inflateAnalyticsAmount(amount: number, fromYear: number, toYear: number, cpi: Record<number, number>): number {
  const from = cpi[fromYear]; const to = cpi[toYear];
  return fromYear === toYear || !from || !to ? amount : amount * to / from;
}
