type Kind = 'plan' | 'worksheet' | 'exam' | 'program';
type Row = Record<string, unknown>;
const FEATURES: Record<Exclude<Kind, 'program'>, string> = { plan: 'quick_lesson_ai', worksheet: 'quick_worksheet_ai', exam: 'quick_exam_ai' };
const DEFAULT_LIMITS: Record<string, number> = { free: 10, teacher_pro: 250, school: 2000, beta_lifetime: 1000 };

export type UsageContext = { base: string; serverKey: string; userId: string; kind: Kind; profilePlan?: string };
export type UsageGate = { allowed: boolean; status: number; reason: string; remainingSeconds?: number; used: number; source?: 'counter' | 'logs' };

async function selectRows(context: UsageContext, table: string, select: string, filters: Record<string, string>, limit = 1, order?: string): Promise<Row[]> {
  const url = new URL(`${context.base.replace(/\/$/, '')}/rest/v1/${table}`);
  url.searchParams.set('select', select);
  url.searchParams.set('limit', String(limit));
  if (order) url.searchParams.set('order', order);
  for (const [column, value] of Object.entries(filters)) url.searchParams.set(column, `eq.${value}`);
  const response = await fetch(url, { headers: { apikey: context.serverKey, Authorization: `Bearer ${context.serverKey}`, Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) throw new Error(`AI usage ${table} read failed (${response.status}).`);
  const rows = await response.json();
  return Array.isArray(rows) ? rows : [];
}

async function optionalRows(context: UsageContext, table: string, select: string, filters: Record<string, string>, limit = 1, order?: string): Promise<Row[]> {
  try { return await selectRows(context, table, select, filters, limit, order); }
  catch (error) { console.error(`Optional AI usage ${table} lookup failed`, error); return []; }
}

async function successfulLogCount(context: UsageContext, now: number): Promise<number> {
  const url = new URL(`${context.base.replace(/\/$/, '')}/rest/v1/ai_usage_logs`);
  url.searchParams.set('select', 'id');
  url.searchParams.set('user_id', `eq.${context.userId}`);
  url.searchParams.set('feature_name', `in.(${Object.values(FEATURES).join(',')})`);
  url.searchParams.set('status', 'eq.success');
  const date = new Date(now);
  url.searchParams.set('created_at', `gte.${new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1)).toISOString()}`);
  url.searchParams.set('limit', '0');
  const response = await fetch(url, { headers: { apikey: context.serverKey, Authorization: `Bearer ${context.serverKey}`, Prefer: 'count=exact', Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) throw new Error(`AI usage log count failed (${response.status}).`);
  const range = response.headers.get('content-range');
  const count = Number(range?.split('/')[1]);
  if (!range || !Number.isSafeInteger(count) || count < 0) throw new Error('AI usage log count was unavailable.');
  return count;
}

async function writeRow(context: UsageContext, table: string, payload: Row, upsert = false): Promise<void> {
  const url = `${context.base.replace(/\/$/, '')}/rest/v1/${table}${upsert ? '?on_conflict=user_id' : ''}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { apikey: context.serverKey, Authorization: `Bearer ${context.serverKey}`, 'Content-Type': 'application/json', Prefer: upsert ? 'resolution=merge-duplicates,return=minimal' : 'return=minimal' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`AI usage ${table} write failed (${response.status}).`);
}

export async function checkAiGenerationUsage(context: UsageContext, now = Date.now()): Promise<UsageGate> {
  const [subscription] = await optionalRows(context, 'user_subscriptions', 'plan_id,subscription_status,manual_override,plans(features_json,limits_json,active)', { user_id: context.userId });
  const subscriptionActive = subscription?.manual_override === true || ['active', 'trialing'].includes(String(subscription?.subscription_status || '').toLowerCase());
  const planId = String(subscriptionActive ? subscription.plan_id || 'free' : context.profilePlan || 'free');
  const joinedPlan = subscriptionActive && subscription.plans && typeof subscription.plans === 'object' && !Array.isArray(subscription.plans) ? subscription.plans as Row : null;
  const [fetchedPlan] = joinedPlan ? [] : await optionalRows(context, 'plans', 'features_json,limits_json,active', { id: planId });
  const plan = joinedPlan || fetchedPlan;
  const effectivePlan = plan && plan.active !== false ? plan : null;
  const effectivePlanId = effectivePlan ? planId : 'free';
  const features = effectivePlan?.features_json && typeof effectivePlan.features_json === 'object' ? effectivePlan.features_json as Row : {};
  if (features.ai_tools === false) return { allowed: false, status: 403, reason: 'AI tools are not included in your plan.', used: 0 };
  if (context.kind === 'program') return { allowed: true, status: 200, reason: '', used: 0 }; // Programs have no generation count limit in Streamlit.
  const limits = effectivePlan?.limits_json && typeof effectivePlan.limits_json === 'object' ? effectivePlan.limits_json as Row : {};
  const limitValue = limits.ai_generations;
  const limit = limitValue == null ? DEFAULT_LIMITS[effectivePlanId] ?? null : Number(limitValue);
  let used: number;
  let source: 'counter' | 'logs' = 'counter';
  try {
    const [usage] = await selectRows(context, 'usage_tracking', 'ai_generations', { user_id: context.userId });
    used = Math.max(0, Number(usage?.ai_generations || 0));
  } catch (error) {
    console.error('AI usage counter lookup failed; verifying successful usage logs instead', error);
    used = await successfulLogCount(context, now);
    source = 'logs';
  }
  if (!Number.isFinite(used) || (limit !== null && !Number.isFinite(limit))) throw new Error('Invalid AI usage counter or plan limit.');
  if (limit !== null && used >= limit) return { allowed: false, status: 429, reason: 'Your AI generation limit has been reached.', used };
  return { allowed: true, status: 200, reason: '', used, source };
}

export async function logAiGeneration(context: UsageContext, status: 'requested' | 'success' | 'failed', meta: Row = {}): Promise<void> {
  if (context.kind === 'program') return;
  await writeRow(context, 'ai_usage_logs', { user_id: context.userId, feature_name: FEATURES[context.kind], status, meta_json: meta, created_at: new Date().toISOString() });
}

export async function incrementAiGenerationUsage(context: UsageContext, previousUsed: number): Promise<void> {
  if (context.kind === 'program') return;
  await writeRow(context, 'usage_tracking', { user_id: context.userId, ai_generations: previousUsed + 1 }, true);
}
