import { accessToken, serverClient } from '@/server/google-calendar';

export type GoogleCalendarItem = { id: string; summary: string; primary: boolean; accessRole: string; selected: boolean };
export type GoogleCalendarEvent = {
  calendarId: string; id: string; title: string; startAt: string; endAt: string; allDay: boolean;
  dateKey: string; status: string; htmlLink: string; studentId: number | null; student: string; etag: string;
};
export type HiddenGoogleCalendarEvent = GoogleCalendarEvent & { hiddenAt: string; calendarName: string };
type GoogleEventRecord = {
  id?: string; summary?: string; status?: string; updated?: string; etag?: string; htmlLink?: string;
  start?: { date?: string; dateTime?: string }; end?: { date?: string; dateTime?: string };
  recurringEventId?: string; originalStartTime?: { date?: string; dateTime?: string };
  extendedProperties?: { private?: { classio_owner?: string } };
};
type EventRow = {
  calendar_id: string; event_id: string; title: string; start_at: string | null; end_at: string | null;
  all_day: boolean; date_key: string; status: string; html_link: string; etag: string;
};

const googleBase = 'https://www.googleapis.com/calendar/v3';
const MAX_CALENDARS = 10;
const MAX_PAGES = 12;
const PAGE_SIZE = 250;

async function googleGet(token: string, path: string) {
  const response = await fetch(`${googleBase}${path}`, {
    headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(15000), cache: 'no-store',
  });
  if (!response.ok) {
    if (response.status === 403) throw new Error('Reconnect Google Calendar to grant calendar-list access.');
    throw new Error(`Google Calendar returned ${response.status}.`);
  }
  return response.json() as Promise<Record<string, unknown>>;
}

async function allCalendars(uid: string) {
  const token = await accessToken(uid);
  const rows: { id?: string; summary?: string; primary?: boolean; accessRole?: string }[] = [];
  let pageToken = '';
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const query = new URLSearchParams({ maxResults: String(PAGE_SIZE), ...(pageToken ? { pageToken } : {}) });
    const result = await googleGet(token, `/users/me/calendarList?${query}`);
    rows.push(...(Array.isArray(result.items) ? result.items as typeof rows : []));
    pageToken = String(result.nextPageToken || '');
    if (!pageToken) return rows.filter((row) => row.id && ['reader', 'writer', 'owner', 'writerWithoutPrivateAccess'].includes(row.accessRole || ''));
  }
  throw new Error('Google returned too many calendars to list safely.');
}

export async function listGoogleCalendars(uid: string): Promise<GoogleCalendarItem[]> {
  const [calendars, selected] = await Promise.all([
    allCalendars(uid), serverClient().from('classio_google_calendar_sources').select('calendar_id,enabled').eq('user_id', uid),
  ]);
  if (selected.error) throw selected.error;
  const selectedIds = new Set((selected.data || []).filter((row) => row.enabled).map((row) => String(row.calendar_id)));
  const hasPreference = Boolean(selected.data?.length);
  return calendars.map((row) => ({
    id: String(row.id), summary: String(row.summary || row.id).slice(0, 160), primary: Boolean(row.primary),
    accessRole: String(row.accessRole || ''), selected: hasPreference ? selectedIds.has(String(row.id)) : Boolean(row.primary),
  }));
}

export async function selectGoogleCalendars(uid: string, requestedIds: string[]) {
  const ids = [...new Set(requestedIds.map((id) => id.trim()))];
  if (!ids.length || ids.length > MAX_CALENDARS) throw new Error('Choose between one and ten calendars.');
  const available = await allCalendars(uid);
  const byId = new Map(available.map((row) => [String(row.id), row]));
  if (ids.some((id) => !byId.has(id))) throw new Error('A selected calendar is unavailable to this account.');
  const db = serverClient();
  const { error: disableError } = await db.from('classio_google_calendar_sources').update({ enabled: false }).eq('user_id', uid);
  if (disableError) throw disableError;
  const { error } = await db.from('classio_google_calendar_sources').upsert(ids.map((id) => ({
    user_id: uid, calendar_id: id, display_name: String(byId.get(id)?.summary || id).slice(0, 160), enabled: true,
  })), { onConflict: 'user_id,calendar_id' });
  if (error) throw error;
  return listGoogleCalendars(uid);
}

export function inboundDateRange(start: string, end: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) throw new Error('Choose a valid calendar range.');
  const first = new Date(`${start}T00:00:00Z`); const last = new Date(`${end}T00:00:00Z`);
  if (Number.isNaN(first.valueOf()) || Number.isNaN(last.valueOf()) || first.toISOString().slice(0, 10) !== start || last.toISOString().slice(0, 10) !== end || last < first || last.getTime() - first.getTime() > 62 * 86_400_000)
    throw new Error('Choose a calendar range of 63 days or less.');
  return { first: first.toISOString(), lastExclusive: new Date(last.getTime() + 86_400_000).toISOString() };
}

export function eventOverlapsLocalRange(row: Pick<EventRow, 'start_at' | 'end_at' | 'all_day' | 'date_key'>, start: string, end: string, timezone: string) {
  if (row.all_day) {
    const last = row.end_at ? new Date(Date.parse(row.end_at) - 1).toISOString().slice(0, 10) : row.date_key;
    return row.date_key <= end && last >= start;
  }
  if (!row.start_at || !row.end_at) return false;
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' });
  const localDate = (value: Date) => {
    const parts = Object.fromEntries(formatter.formatToParts(value).map((part) => [part.type, part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  return localDate(new Date(row.start_at)) <= end && localDate(new Date(Date.parse(row.end_at) - 1)) >= start;
}

async function selectedSources(uid: string) {
  const db = serverClient();
  const { data, error } = await db.from('classio_google_calendar_sources').select('calendar_id').eq('user_id', uid).eq('enabled', true).limit(MAX_CALENDARS);
  if (error) throw error;
  if (data?.length) return data.map((row) => String(row.calendar_id));
  const primary = (await allCalendars(uid)).find((row) => row.primary);
  if (!primary?.id) return [];
  const { error: insertError } = await db.from('classio_google_calendar_sources').upsert({ user_id: uid, calendar_id: primary.id, display_name: String(primary.summary || primary.id).slice(0, 160), enabled: true }, { onConflict: 'user_id,calendar_id' });
  if (insertError) throw insertError;
  return [primary.id];
}

async function hiddenEventKeys(uid: string, calendarIds: string[]) {
  const keys = new Set<string>();
  const db = serverClient();
  for (let offset = 0; ; offset += 1000) {
    const { data, error } = await db.from('classio_google_calendar_hidden_events')
      .select('calendar_id,event_id').eq('user_id', uid).in('calendar_id', calendarIds)
      .order('calendar_id').order('event_id').range(offset, offset + 999);
    if (error) throw error;
    for (const row of data || []) keys.add(`${row.calendar_id}\0${row.event_id}`);
    if ((data || []).length < 1000) break;
  }
  return keys;
}

export async function listHiddenGoogleCalendarEvents(uid: string, page: number): Promise<{ events: HiddenGoogleCalendarEvent[]; total: number }> {
  if (!Number.isSafeInteger(page) || page < 1 || page > 10000) throw new Error('Choose a valid hidden-events page.');
  const ids = await selectedSources(uid);
  if (!ids.length) return { events: [], total: 0 };
  const db = serverClient();
  const { data, count, error } = await db.from('classio_google_calendar_hidden_events')
    .select('calendar_id,event_id,hidden_at,event:classio_google_calendar_events!inner(title,start_at,end_at,all_day,date_key,status,html_link,etag)', { count: 'exact' })
    .eq('user_id', uid).in('calendar_id', ids).neq('event.status', 'cancelled')
    .order('hidden_at', { ascending: false }).range((page - 1) * 20, page * 20 - 1);
  if (error) throw error;
  const { data: sources, error: sourceError } = await db.from('classio_google_calendar_sources')
    .select('calendar_id,display_name').eq('user_id', uid).in('calendar_id', ids);
  if (sourceError) throw sourceError;
  const sourceNames = new Map((sources || []).map((row) => [String(row.calendar_id), String(row.display_name || row.calendar_id)]));
  const events = (data || []).map((row) => {
    const event = row.event as unknown as EventRow;
    return {
      calendarId: String(row.calendar_id), id: String(row.event_id), title: event.title,
      startAt: event.start_at || '', endAt: event.end_at || '', allDay: event.all_day,
      dateKey: event.date_key, status: event.status, htmlLink: event.html_link,
      studentId: null, student: '', etag: event.etag,
      hiddenAt: String(row.hidden_at), calendarName: sourceNames.get(String(row.calendar_id)) || String(row.calendar_id),
    };
  });
  return { events, total: count || 0 };
}

export async function setGoogleEventHidden(uid: string, calendarId: string, eventId: string, hidden: boolean) {
  const db = serverClient();
  if (hidden) {
    const { data: event, error: eventError } = await db.from('classio_google_calendar_events')
      .select('event_id,status').eq('user_id', uid).eq('calendar_id', calendarId).eq('event_id', eventId).maybeSingle();
    if (eventError) throw eventError;
    if (!event || event.status === 'cancelled') throw new Error('Refresh this Google event before hiding it.');
    const { error } = await db.from('classio_google_calendar_hidden_events')
      .upsert({ user_id: uid, calendar_id: calendarId, event_id: eventId }, { onConflict: 'user_id,calendar_id,event_id', ignoreDuplicates: true });
    if (error) throw error;
  } else {
    const { error } = await db.from('classio_google_calendar_hidden_events').delete()
      .eq('user_id', uid).eq('calendar_id', calendarId).eq('event_id', eventId);
    if (error) throw error;
  }
}

function eventRow(uid: string, calendarId: string, event: GoogleEventRecord, refreshedAt: string) {
  const allDay = Boolean(event.start?.date);
  const start = event.start?.dateTime || (event.start?.date ? `${event.start.date}T00:00:00Z` : null);
  const end = event.end?.dateTime || (event.end?.date ? `${event.end.date}T00:00:00Z` : null);
  if (!event.id || !start || !end || Number.isNaN(Date.parse(start)) || Number.isNaN(Date.parse(end)) || Date.parse(end) <= Date.parse(start)) return null;
  return {
    user_id: uid, calendar_id: calendarId, event_id: event.id,
    title: String(event.summary || '(Untitled)').slice(0, 300), start_at: new Date(start).toISOString(), end_at: new Date(end).toISOString(),
    all_day: allDay, date_key: event.start?.date || '', status: event.status === 'tentative' ? 'tentative' : event.status === 'cancelled' ? 'cancelled' : 'confirmed',
    google_updated_at: event.updated || null, etag: String(event.etag || '').slice(0, 240), html_link: String(event.htmlLink || '').slice(0, 1200),
    recurring_event_id: String(event.recurringEventId || '').slice(0, 320), original_start_time: String(event.originalStartTime?.dateTime || event.originalStartTime?.date || '').slice(0, 80),
    refreshed_at: refreshedAt,
  };
}

async function refreshCalendarRange(uid: string, token: string, calendarId: string, first: string, lastExclusive: string) {
  const rows: ReturnType<typeof eventRow>[] = [];
  let pageToken = '';
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const query = new URLSearchParams({ singleEvents: 'true', timeMin: first, timeMax: lastExclusive, maxResults: String(PAGE_SIZE), ...(pageToken ? { pageToken } : {}) });
    const response = await googleGet(token, `/calendars/${encodeURIComponent(calendarId)}/events?${query}`);
    const events = Array.isArray(response.items) ? response.items as GoogleEventRecord[] : [];
    for (const event of events) {
      if (event.extendedProperties?.private?.classio_owner === uid) continue;
      const row = eventRow(uid, calendarId, event, new Date().toISOString());
      if (row) rows.push(row);
    }
    pageToken = String(response.nextPageToken || '');
    if (!pageToken) break;
    if (page === MAX_PAGES - 1) throw new Error('Google returned too many events for this range. Choose a shorter view.');
  }
  const db = serverClient();
  const refreshedAt = new Date().toISOString();
  for (let index = 0; index < rows.length; index += 100) {
    const { error } = await db.from('classio_google_calendar_events').upsert(rows.slice(index, index + 100).map((row) => ({
      ...row, refreshed_at: refreshedAt,
    })), { onConflict: 'user_id,calendar_id,event_id' });
    if (error) throw error;
  }
  const { error: staleError } = await db.from('classio_google_calendar_events').update({ status: 'cancelled' })
    .eq('user_id', uid).eq('calendar_id', calendarId).lt('start_at', lastExclusive).gt('end_at', first).lt('refreshed_at', refreshedAt);
  if (staleError) throw staleError;
  const { error: sourceError } = await db.from('classio_google_calendar_sources').update({ last_sync_at: refreshedAt }).eq('user_id', uid).eq('calendar_id', calendarId);
  if (sourceError) throw sourceError;
}

export async function getGoogleCalendarEvents(uid: string, start: string, end: string, timezone = 'UTC'): Promise<{ events: GoogleCalendarEvent[]; warning: string }> {
  const range = inboundDateRange(start, end);
  try { new Intl.DateTimeFormat('en-US', { timeZone: timezone }); } catch { throw new Error('Choose a valid calendar timezone.'); }
  const ids = await selectedSources(uid);
  if (!ids.length) return { events: [], warning: '' };
  let warning = '';
  // A one-day margin covers the UTC offsets on either side of the requested
  // local dates, including daylight-saving transitions.
  const paddedFirst = new Date(Date.parse(range.first) - 86_400_000).toISOString();
  const paddedEnd = new Date(Date.parse(range.lastExclusive) + 86_400_000).toISOString();
  try {
    const token = await accessToken(uid);
    for (const id of ids) await refreshCalendarRange(uid, token, id, paddedFirst, paddedEnd);
  } catch (error) {
    warning = error instanceof Error ? error.message : 'Google Calendar could not refresh.';
  }
  const db = serverClient();
  const { data, error } = await db.from('classio_google_calendar_events')
    .select('calendar_id,event_id,title,start_at,end_at,all_day,date_key,status,html_link,etag')
    .eq('user_id', uid).in('calendar_id', ids).neq('status', 'cancelled')
    .lt('start_at', paddedEnd).gt('end_at', paddedFirst).order('start_at').limit(1500);
  if (error) throw error;
  const rows = ((data || []) as EventRow[]).filter((row) => eventOverlapsLocalRange(row, start, end, timezone));
  if ((data || []).length === 1500) warning = [warning, 'This view contains too many Google events. Choose a shorter range.'].filter(Boolean).join(' ');
  const hiddenKeys = await hiddenEventKeys(uid, ids);
  const { data: imports, error: importError } = await db.from('classio_google_calendar_imports')
    .select('calendar_id,event_id,student_id').eq('user_id', uid).in('calendar_id', ids).limit(5000);
  if (importError) throw importError;
  const importMap = new Map((imports || []).map((row) => [`${row.calendar_id}\0${row.event_id}`, Number(row.student_id)]));
  const studentIds = [...new Set([...importMap.values()])];
  const { data: students, error: studentError } = studentIds.length
    ? await db.from('students').select('id,student').eq('user_id', uid).in('id', studentIds).limit(1500)
    : { data: [], error: null };
  if (studentError) throw studentError;
  const names = new Map((students || []).map((row) => [Number(row.id), String(row.student || '')]));
  return { warning, events: rows.filter((row) => !hiddenKeys.has(`${row.calendar_id}\0${row.event_id}`)).map((row) => ({
    calendarId: row.calendar_id, id: row.event_id, title: row.title, startAt: row.start_at || '', endAt: row.end_at || '',
    allDay: row.all_day, dateKey: row.date_key, status: row.status, htmlLink: row.html_link,
    studentId: importMap.get(`${row.calendar_id}\0${row.event_id}`) || null,
    student: names.get(importMap.get(`${row.calendar_id}\0${row.event_id}`) || 0) || '', etag: row.etag,
  })) };
}

export async function setGoogleEventStudent(uid: string, calendarId: string, eventId: string, studentId: number | null) {
  const db = serverClient();
  const { data: event, error: eventError } = await db.from('classio_google_calendar_events')
    .select('event_id,start_at,end_at,all_day,status').eq('user_id', uid).eq('calendar_id', calendarId).eq('event_id', eventId).maybeSingle();
  if (eventError) throw eventError;
  if (!event) throw new Error('Refresh this Google event before linking it.');
  if (studentId !== null) {
    if (!Number.isSafeInteger(studentId) || studentId <= 0) throw new Error('Choose a valid student.');
    if (event.all_day || !event.start_at || !event.end_at || event.status === 'cancelled') throw new Error('Only active timed events can become lessons.');
    const { data: hidden, error: hiddenError } = await db.from('classio_google_calendar_hidden_events')
      .select('event_id').eq('user_id', uid).eq('calendar_id', calendarId).eq('event_id', eventId).maybeSingle();
    if (hiddenError) throw hiddenError;
    if (hidden) throw new Error('Show this Google event in Classio before importing it.');
    const { data: student, error } = await db.from('students').select('id').eq('user_id', uid).eq('id', studentId).maybeSingle();
    if (error) throw error;
    if (!student) throw new Error('This student is not in your roster.');
  }
  const { error } = studentId
    ? await db.from('classio_google_calendar_imports').upsert({ user_id: uid, calendar_id: calendarId, event_id: eventId, student_id: studentId }, { onConflict: 'user_id,calendar_id,event_id' })
    : await db.from('classio_google_calendar_imports').delete().eq('user_id', uid).eq('calendar_id', calendarId).eq('event_id', eventId);
  if (error) throw error;
}

export async function importGoogleCalendarEvents(uid: string, items: { calendarId: string; eventId: string; studentId: number }[]) {
  if (!items.length || items.length > 100) throw new Error('Choose between one and 100 events.');
  const unique = new Map<string, (typeof items)[number]>();
  for (const item of items) {
    if (!item.calendarId || !item.eventId || item.calendarId.length > 320 || item.eventId.length > 320 || !Number.isSafeInteger(item.studentId) || item.studentId <= 0)
      throw new Error('Choose valid events and students.');
    unique.set(`${item.calendarId}\0${item.eventId}`, item);
  }
  if (unique.size !== items.length) throw new Error('The import contains a duplicate Google event.');
  const db = serverClient();
  const studentIds = [...new Set(items.map((item) => item.studentId))];
  const { data: students, error: studentsError } = await db.from('students').select('id').eq('user_id', uid).in('id', studentIds).limit(100);
  if (studentsError) throw studentsError;
  if ((students || []).length !== studentIds.length) throw new Error('An imported student is not in your roster.');
  for (const calendarId of [...new Set(items.map((item) => item.calendarId))]) {
    const eventIds = items.filter((item) => item.calendarId === calendarId).map((item) => item.eventId);
    const { data, error } = await db.from('classio_google_calendar_events')
      .select('event_id,start_at,end_at,all_day,status').eq('user_id', uid).eq('calendar_id', calendarId).in('event_id', eventIds).limit(100);
    if (error) throw error;
    if ((data || []).length !== eventIds.length || (data || []).some((row) => row.all_day || !row.start_at || !row.end_at || row.status === 'cancelled'))
      throw new Error('Refresh the selected Google events before importing.');
    const { data: hidden, error: hiddenError } = await db.from('classio_google_calendar_hidden_events')
      .select('event_id').eq('user_id', uid).eq('calendar_id', calendarId).in('event_id', eventIds);
    if (hiddenError) throw hiddenError;
    if (hidden?.length) throw new Error('Show hidden Google events in Classio before importing them.');
  }
  const { error } = await db.from('classio_google_calendar_imports').upsert(items.map((item) => ({
    user_id: uid, calendar_id: item.calendarId, event_id: item.eventId, student_id: item.studentId,
  })), { onConflict: 'user_id,calendar_id,event_id' });
  if (error) throw error;
  return items.length;
}
