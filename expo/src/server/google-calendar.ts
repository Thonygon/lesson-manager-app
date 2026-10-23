import { createHash, createHmac, timingSafeEqual } from 'node:crypto';
import { createClient } from '@supabase/supabase-js';

const googleScope = 'https://www.googleapis.com/auth/calendar.events';
const appUrl = 'https://classio.expo.app';
type Tokens = { token?: string; refresh_token?: string; expires_at?: number };
type FreezeRow = { student: string | null; start_date: string | null; end_date: string | null };

function config() {
  const clientId = process.env.GOOGLE_CAL_CLIENT_ID || '';
  const clientSecret = process.env.GOOGLE_CAL_CLIENT_SECRET || '';
  const stateSecret = process.env.GOOGLE_CAL_STATE_SECRET || '';
  const redirectUri = process.env.GOOGLE_CAL_REDIRECT_URI || `${appUrl}/api/google-calendar-callback`;
  return { clientId, clientSecret, stateSecret, redirectUri, configured: Boolean(clientId && clientSecret && stateSecret) };
}

function serverClient() {
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const key = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !key) throw new Error('The calendar service is not configured.');
  return createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

export async function authorizedUser(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) throw new Error('Sign in to connect Google Calendar.');
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const key = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  if (!url || !key) throw new Error('The calendar service is not configured.');
  const client = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user) throw new Error('Your Classio session has expired.');
  return data.user.id;
}

function sign(payload: string, secret: string) { return createHmac('sha256', secret).update(payload).digest('base64url'); }
export function connectionUrl(uid: string) {
  const cfg = config();
  if (!cfg.configured) throw new Error('Google Calendar needs OAuth credentials on the Expo server.');
  const payload = Buffer.from(JSON.stringify({ uid, expires: Date.now() + 10 * 60_000 })).toString('base64url');
  const state = `${payload}.${sign(payload, cfg.stateSecret)}`;
  const query = new URLSearchParams({ client_id: cfg.clientId, redirect_uri: cfg.redirectUri, response_type: 'code', scope: googleScope, access_type: 'offline', prompt: 'consent', state });
  return `https://accounts.google.com/o/oauth2/v2/auth?${query}`;
}

function stateUser(state: string) {
  const cfg = config();
  const [payload, signature] = state.split('.');
  const expected = payload && cfg.configured ? sign(payload, cfg.stateSecret) : '';
  if (!cfg.configured || !payload || !signature || signature.length !== expected.length || !timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) throw new Error('The Google authorization request has expired.');
  const value = JSON.parse(Buffer.from(payload, 'base64url').toString()) as { uid?: string; expires?: number };
  if (!value.uid || !value.expires || value.expires < Date.now()) throw new Error('The Google authorization request has expired.');
  return value.uid;
}

async function tokenRequest(body: URLSearchParams) {
  const response = await fetch('https://oauth2.googleapis.com/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body, signal: AbortSignal.timeout(15000) });
  const data = await response.json() as Record<string, unknown>;
  if (!response.ok || !data.access_token) throw new Error(String(data.error_description || data.error || 'Google authorization failed.'));
  return data;
}

async function saveTokens(uid: string, tokens: Tokens | null) {
  const { error } = await serverClient().from('profiles').update({ gcal_tokens: tokens ? JSON.stringify(tokens) : null }).eq('user_id', uid);
  if (error) throw error;
}

async function loadTokens(uid: string): Promise<Tokens | null> {
  const { data, error } = await serverClient().from('profiles').select('gcal_tokens').eq('user_id', uid).limit(1).maybeSingle();
  if (error) throw error;
  const value = data?.gcal_tokens;
  if (!value) return null;
  return typeof value === 'string' ? JSON.parse(value) as Tokens : value as Tokens;
}

export function googleConfigured() { return config().configured; }
export async function googleConnected(uid: string) { return Boolean((await loadTokens(uid))?.refresh_token); }
export async function disconnectGoogle(uid: string) { await saveTokens(uid, null); }

export async function finishConnection(code: string, state: string) {
  const uid = stateUser(state); const cfg = config();
  const data = await tokenRequest(new URLSearchParams({ code, client_id: cfg.clientId, client_secret: cfg.clientSecret, redirect_uri: cfg.redirectUri, grant_type: 'authorization_code' }));
  if (!data.refresh_token) throw new Error('Google did not return an offline access token. Reconnect and grant access.');
  await saveTokens(uid, { token: String(data.access_token), refresh_token: String(data.refresh_token), expires_at: Date.now() + Number(data.expires_in || 3600) * 1000 });
}

async function accessToken(uid: string) {
  const stored = await loadTokens(uid); if (!stored?.refresh_token) throw new Error('Connect Google Calendar first.');
  if (stored.token && stored.expires_at && stored.expires_at > Date.now() + 60_000) return stored.token;
  const cfg = config();
  const data = await tokenRequest(new URLSearchParams({ refresh_token: stored.refresh_token, client_id: cfg.clientId, client_secret: cfg.clientSecret, grant_type: 'refresh_token' }));
  const updated = { ...stored, token: String(data.access_token), expires_at: Date.now() + Number(data.expires_in || 3600) * 1000 };
  await saveTokens(uid, updated); return updated.token;
}

function eventId(uid: string, kind: 's' | 'o', id: unknown) { return `c${uid.replace(/-/g, '')}${kind}${Number(id).toString(16)}`; }
function googleTime(date: string, time: string, minutes: number) {
  const start = new Date(`${date}T${time}:00Z`);
  const end = new Date(start.getTime() + minutes * 60_000);
  return { start: `${date}T${time}:00`, end: end.toISOString().slice(0, 19) };
}
function dateInTimezone(date: Date, timezone: string) {
  try {
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date);
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  } catch { return date.toISOString().slice(0, 10); }
}

async function googleRequest(token: string, method: string, path: string, body?: unknown) {
  return fetch(`https://www.googleapis.com/calendar/v3/calendars/primary/events${path}`, { method, headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000) });
}

export async function syncGoogleCalendar(uid: string) {
  const token = await accessToken(uid); const db = serverClient();
  const [schedules, overrides, freezes, students] = await Promise.all([
    db.from('schedules').select('id,student,weekday,time,duration_minutes,active,timezone,start_date,end_date').eq('user_id', uid).limit(1000),
    db.from('calendar_overrides').select('id,student,original_date,new_datetime,duration_minutes,status,note,gcal_event_id').eq('user_id', uid).limit(2000),
    db.from('student_schedule_freezes').select('student,start_date,end_date,active').eq('user_id', uid).eq('active', true).limit(500),
    db.from('students').select('student,email,zoom_link,address').eq('user_id', uid).limit(1000),
  ]);
  if (schedules.error || overrides.error || freezes.error) throw schedules.error || overrides.error || freezes.error;
  const studentInfo = new Map((students.data || []).map((row) => [String(row.student), row]));
  const existing = new Map<string, string>(); let pageToken = '';
  do {
    const query = new URLSearchParams({ privateExtendedProperty: `classio_owner=${uid}`, maxResults: '250', ...(pageToken ? { pageToken } : {}) });
    const response = await googleRequest(token, 'GET', `?${query}`);
    if (!response.ok) throw new Error(`Google Calendar returned ${response.status} while checking synced lessons.`);
    const result = await response.json() as { items?: { id?: string; extendedProperties?: { private?: { classio_hash?: string } } }[]; nextPageToken?: string };
    for (const item of result.items || []) if (item.id) existing.set(item.id, item.extendedProperties?.private?.classio_hash || '');
    pageToken = result.nextPageToken || '';
  } while (pageToken);
  const desired = new Set<string>(); let synced = 0;
  const upsert = async (id: string, body: Record<string, unknown>, legacyId = false) => {
    desired.add(id);
    const hash = createHash('sha256').update(JSON.stringify(body)).digest('hex');
    if (existing.get(id) === hash) return;
    const event = { ...body, id, extendedProperties: { private: { classio_owner: uid, classio_hash: hash } } };
    let response = await googleRequest(token, existing.has(id) || legacyId ? 'PUT' : 'POST', existing.has(id) || legacyId ? `/${encodeURIComponent(id)}?sendUpdates=all` : '?sendUpdates=all', event);
    if (response.status === 404 && legacyId) response = await googleRequest(token, 'POST', '?sendUpdates=all', event);
    if (!response.ok) throw new Error(`Google Calendar returned ${response.status} while syncing a lesson.`);
    synced += 1;
  };
  const details = (student: string, note = '') => { const info = studentInfo.get(student); return { summary: `Classio: ${student}`, description: [note, info?.zoom_link ? `Lesson link: ${info.zoom_link}` : '', info?.address ? `Address: ${info.address}` : ''].filter(Boolean).join('\n'), ...(info?.address ? { location: info.address } : {}), ...(info?.email ? { attendees: [{ email: info.email, displayName: student }] } : {}) }; };
  for (const row of schedules.data || []) {
    if (row.active === false || !row.start_date || !row.time) continue;
    const days = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']; const day = days[Number(row.weekday)]; if (!day) continue;
    const student = String(row.student || 'Student'); const first = new Date(`${String(row.start_date).slice(0, 10)}T12:00:00Z`);
    const offset = (Number(row.weekday) - ((first.getUTCDay() + 6) % 7) + 7) % 7;
    first.setUTCDate(first.getUTCDate() + offset);
    const firstDate = first.toISOString().slice(0, 10);
    if (row.end_date && firstDate > String(row.end_date).slice(0, 10)) continue;
    const time = googleTime(firstDate, String(row.time).slice(0, 5), Number(row.duration_minutes || 60));
    const matchingFreezes: FreezeRow[] = ((freezes.data || []) as FreezeRow[]).filter((freeze) => String(freeze.student) === student);
    const openFreeze = matchingFreezes.filter((freeze) => !freeze.end_date && freeze.start_date).map((freeze) => String(freeze.start_date).slice(0, 10)).sort()[0];
    const effectiveEnd = [row.end_date ? String(row.end_date).slice(0, 10) : '', openFreeze ? new Date(new Date(`${openFreeze}T12:00:00Z`).getTime() - 86_400_000).toISOString().slice(0, 10) : ''].filter(Boolean).sort()[0] || '';
    if (effectiveEnd && firstDate > effectiveEnd) continue;
    const recurrence = `RRULE:FREQ=WEEKLY;BYDAY=${day}${effectiveEnd ? `;UNTIL=${effectiveEnd.replace(/-/g, '')}T235959Z` : ''}`;
    const exclusions = new Set<string>();
    for (const override of overrides.data || []) if (String(override.student) === student && override.original_date) exclusions.add(String(override.original_date).slice(0, 10));
    for (const freeze of matchingFreezes) if (freeze.start_date && freeze.end_date) {
      const cursor = new Date(`${String(freeze.start_date).slice(0, 10)}T12:00:00Z`);
      const end = String(freeze.end_date).slice(0, 10);
      for (let count = 0; count < 730 && cursor.toISOString().slice(0, 10) <= end; count++, cursor.setUTCDate(cursor.getUTCDate() + 1)) if ((cursor.getUTCDay() + 6) % 7 === Number(row.weekday)) exclusions.add(cursor.toISOString().slice(0, 10));
    }
    const exdates = [...exclusions].filter((date) => date >= firstDate && (!effectiveEnd || date <= effectiveEnd) && (new Date(`${date}T12:00:00Z`).getUTCDay() + 6) % 7 === Number(row.weekday)).map((date) => `EXDATE;TZID=${row.timezone || 'UTC'}:${date.replace(/-/g, '')}T${String(row.time).slice(0, 5).replace(':', '')}00`);
    await upsert(eventId(uid, 's', row.id), { ...details(student), start: { dateTime: time.start, timeZone: row.timezone || 'UTC' }, end: { dateTime: time.end, timeZone: row.timezone || 'UTC' }, recurrence: [recurrence, ...exdates] });
  }
  for (const row of overrides.data || []) {
    const legacyId = String(row.gcal_event_id || '');
    if (row.status === 'cancelled' && legacyId) {
      const deletion = await googleRequest(token, 'DELETE', `/${encodeURIComponent(legacyId)}`);
      if (!deletion.ok && deletion.status !== 404) throw new Error(`Google Calendar returned ${deletion.status} while removing a cancelled lesson.`);
    }
    if (row.status !== 'scheduled' || !row.new_datetime) continue;
    const student = String(row.student || 'Student'); const start = new Date(String(row.new_datetime)); if (Number.isNaN(start.valueOf())) continue;
    const timezone = String((schedules.data || []).find((schedule) => String(schedule.student) === student)?.timezone || 'UTC');
    const date = dateInTimezone(start, timezone);
    if (((freezes.data || []) as FreezeRow[]).some((freeze) => String(freeze.student) === student && freeze.start_date && String(freeze.start_date).slice(0, 10) <= date && (!freeze.end_date || String(freeze.end_date).slice(0, 10) >= date))) continue;
    const end = new Date(start.getTime() + Number(row.duration_minutes || 60) * 60_000);
    await upsert(legacyId || eventId(uid, 'o', row.id), { ...details(student, String(row.note || '')), start: { dateTime: start.toISOString() }, end: { dateTime: end.toISOString() } }, Boolean(legacyId));
  }
  // Remove only events previously created by this integration. Other Google events remain untouched.
  let removed = 0;
  for (const id of existing.keys()) if (!desired.has(id)) {
    const deletion = await googleRequest(token, 'DELETE', `/${encodeURIComponent(id)}`);
    if (!deletion.ok && deletion.status !== 404) throw new Error(`Google Calendar returned ${deletion.status} while removing a cancelled lesson.`);
    removed += 1;
  }
  return { synced, removed };
}
