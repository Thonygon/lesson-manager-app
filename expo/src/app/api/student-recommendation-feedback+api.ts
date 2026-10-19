type ActivityType = 'student_recommendation_impression' | 'student_recommendation_open';
type EventInput = { activityType: ActivityType; surface: string; resourceKind: string; resourceId: number; title?: string; subject?: string; topic?: string; level?: string; exerciseType?: string; assignedResource?: boolean; assignmentId?: number; programId?: number; learningProgramAssignmentId?: number; learningProgramTopicId?: number; score?: number; mlScore?: number; mlBlendWeight?: number; sourceCreatedAt?: string };
type ActivityRow = { activity_type: ActivityType; meta_json: Record<string, unknown>; created_at: string };

const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });
const text = (value: unknown, max = 200) => String(value ?? '').trim().slice(0, max);
const positiveId = (value: unknown) => { const id = Number(value); return Number.isSafeInteger(id) && id > 0 ? id : 0; };
const number = (value: unknown) => { const result = Number(value); return Number.isFinite(result) ? Math.max(-1000, Math.min(1000, result)) : 0; };

async function authorize(request: Request) {
  const base = process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '';
  const anonKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  const token = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
  if (!base || !anonKey || !serverKey) return { error: json({ error: 'Recommendation feedback is not configured.' }, 503) };
  if (!token) return { error: json({ error: 'Sign in to use recommendations.' }, 401) };
  const response = await fetch(`${base.replace(/\/$/, '')}/auth/v1/user`, { headers: { apikey: anonKey, Authorization: `Bearer ${token}` }, cache: 'no-store' });
  if (!response.ok) return { error: json({ error: 'Your Classio session has expired.' }, 401) };
  const user = await response.json() as { id?: string };
  if (!user.id) return { error: json({ error: 'Your Classio session has expired.' }, 401) };
  return { base: base.replace(/\/$/, ''), serverKey, userId: user.id };
}

function headers(key: string) { return { apikey: key, Authorization: `Bearer ${key}`, Accept: 'application/json' }; }
function signature(activity: string, meta: Record<string, unknown>) { return [activity, text(meta.surface), text(meta.resource_kind), positiveId(meta.resource_id), positiveId(meta.learning_program_assignment_id), positiveId(meta.learning_program_topic_id)].join(':'); }
function meta(item: EventInput) {
  return {
    surface: text(item.surface, 80), resource_kind: text(item.resourceKind, 40), resource_id: positiveId(item.resourceId),
    title: text(item.title), subject: text(item.subject, 100), topic: text(item.topic, 200), level: text(item.level, 80), exercise_type: text(item.exerciseType, 80),
    assigned_resource: Boolean(item.assignedResource), assignment_id: positiveId(item.assignmentId) || null, program_id: positiveId(item.programId) || null,
    learning_program_assignment_id: positiveId(item.learningProgramAssignmentId) || null, learning_program_topic_id: positiveId(item.learningProgramTopicId) || null,
    score: number(item.score), ml_score: number(item.mlScore), ml_blend_weight: number(item.mlBlendWeight), source_created_at: text(item.sourceCreatedAt, 80) || null,
  };
}

export async function GET(request: Request) {
  try {
    const auth = await authorize(request); if (auth.error) return auth.error;
    const { base, serverKey, userId } = auth as { base: string; serverKey: string; userId: string };
    const url = new URL(`${base}/rest/v1/user_activity_log`);
    url.searchParams.set('select', 'activity_type,meta_json,created_at'); url.searchParams.set('user_id', `eq.${userId}`); url.searchParams.set('feature_name', 'eq.student_recommendation_feed');
    url.searchParams.set('created_at', `gte.${new Date(Date.now() - 180 * 86400000).toISOString()}`); url.searchParams.set('order', 'created_at.desc'); url.searchParams.set('limit', '800');
    const response = await fetch(url, { headers: headers(serverKey), cache: 'no-store' });
    if (!response.ok) return json({ error: 'Recommendation feedback could not be loaded.' }, 503);
    return json({ rows: await response.json() });
  } catch { return json({ error: 'Recommendation feedback could not be loaded.' }, 503); }
}

export async function POST(request: Request) {
  try {
    const auth = await authorize(request); if (auth.error) return auth.error;
    const { base, serverKey, userId } = auth as { base: string; serverKey: string; userId: string };
    const rawBody = await request.text();
    if (rawBody.length > 24000) return json({ error: 'Too many recommendation events.' }, 413);
    const body = (() => { try { return JSON.parse(rawBody) as { events?: EventInput[] }; } catch { return null; } })();
    const input = body?.events;
    if (!Array.isArray(input) || !input.length || input.length > 12) return json({ error: 'Choose valid recommendation events.' }, 400);
    // One legacy resource with a missing/non-numeric id must not reject every
    // otherwise valid impression in the batch.
    const items = input.filter((item) => item && ['student_recommendation_impression', 'student_recommendation_open'].includes(item.activityType) && positiveId(item.resourceId) && ['plan', 'worksheet', 'exam', 'video', 'program'].includes(text(item.resourceKind)) && text(item.surface, 80));
    if (!items.length) return json({ inserted: 0, skipped: input.length });
    const recent = new URL(`${base}/rest/v1/user_activity_log`);
    recent.searchParams.set('select', 'activity_type,meta_json'); recent.searchParams.set('user_id', `eq.${userId}`); recent.searchParams.set('feature_name', 'eq.student_recommendation_feed');
    recent.searchParams.set('created_at', `gte.${new Date(Date.now() - 60 * 60000).toISOString()}`); recent.searchParams.set('order', 'created_at.desc'); recent.searchParams.set('limit', '500');
    const lookup = await fetch(recent, { headers: headers(serverKey), cache: 'no-store' });
    if (!lookup.ok) return json({ error: 'Recommendation feedback could not be checked.' }, 503);
    const existing = await lookup.json() as ActivityRow[];
    if (existing.length >= 500) return json({ error: 'Recommendation activity limit reached.' }, 429);
    const seen = new Set(existing.map((row) => signature(row.activity_type, row.meta_json || {})));
    const rows = items.flatMap((item) => {
      const metadata = meta(item); const key = signature(item.activityType, metadata);
      if (seen.has(key)) return [];
      seen.add(key);
      return [{ user_id: userId, activity_type: item.activityType, feature_name: 'student_recommendation_feed', meta_json: metadata, created_at: new Date().toISOString() }];
    });
    if (rows.length) {
      const response = await fetch(`${base}/rest/v1/user_activity_log`, { method: 'POST', headers: { ...headers(serverKey), 'Content-Type': 'application/json', Prefer: 'return=minimal' }, body: JSON.stringify(rows) });
      if (!response.ok) return json({ error: 'Recommendation feedback could not be saved.' }, 503);
    }
    return json({ inserted: rows.length, skipped: input.length - items.length });
  } catch { return json({ error: 'Recommendation feedback could not be saved.' }, 503); }
}
