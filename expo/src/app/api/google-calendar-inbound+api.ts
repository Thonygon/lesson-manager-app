import { authorizedUser, serverClient } from '@/server/google-calendar';
import { getGoogleCalendarEvents, importGoogleCalendarEvents, listGoogleCalendars, listHiddenGoogleCalendarEvents, selectGoogleCalendars, setGoogleEventHidden, setGoogleEventStudent } from '@/server/google-calendar-inbound';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
const message = (error: unknown) => error instanceof Error ? error.message : 'Google Calendar is unavailable.';
async function teacherUser(request: Request) {
  const uid = await authorizedUser(request);
  const { data, error } = await serverClient().from('profiles').select('role,primary_role,can_teach').eq('user_id', uid).maybeSingle();
  if (error) throw error;
  if (data?.can_teach !== true && !['teacher', 'tutor', 'admin'].includes(String(data?.primary_role || data?.role || '')))
    throw new Error('A teacher account is required for this calendar.');
  return uid;
}

export async function GET(request: Request) {
  try {
    const uid = await teacherUser(request);
    const url = new URL(request.url);
    if (url.searchParams.get('mode') === 'calendars') return json({ calendars: await listGoogleCalendars(uid) });
    if (url.searchParams.get('mode') === 'hidden') return json(await listHiddenGoogleCalendarEvents(uid, Number(url.searchParams.get('page') || '1')));
    const start = url.searchParams.get('start') || '';
    const end = url.searchParams.get('end') || '';
    return json(await getGoogleCalendarEvents(uid, start, end));
  } catch (error) {
    return json({ error: message(error) }, /Sign in|expired/.test(message(error)) ? 401 : /teacher account/.test(message(error)) ? 403 : /range|calendar|student|Reconnect|Choose/.test(message(error)) ? 400 : 502);
  }
}

export async function POST(request: Request) {
  try {
    const uid = await teacherUser(request);
    const body = await request.json() as { action?: string; calendarIds?: unknown; calendarId?: unknown; eventId?: unknown; studentId?: unknown; items?: unknown };
    if (body.action === 'selectCalendars') {
      if (!Array.isArray(body.calendarIds) || body.calendarIds.some((id) => typeof id !== 'string')) return json({ error: 'Choose valid calendars.' }, 400);
      return json({ calendars: await selectGoogleCalendars(uid, body.calendarIds as string[]) });
    }
    if (body.action === 'link' || body.action === 'unlink') {
      const calendarId = typeof body.calendarId === 'string' ? body.calendarId.trim() : '';
      const eventId = typeof body.eventId === 'string' ? body.eventId.trim() : '';
      if (!calendarId || !eventId || calendarId.length > 320 || eventId.length > 320) return json({ error: 'Choose a valid Google event.' }, 400);
      const studentId = body.action === 'unlink' ? null : Number(body.studentId);
      await setGoogleEventStudent(uid, calendarId, eventId, studentId);
      return json({ linked: studentId !== null });
    }
    if (body.action === 'hide' || body.action === 'show') {
      const calendarId = typeof body.calendarId === 'string' ? body.calendarId.trim() : '';
      const eventId = typeof body.eventId === 'string' ? body.eventId.trim() : '';
      if (!calendarId || !eventId || calendarId.length > 320 || eventId.length > 320) return json({ error: 'Choose a valid Google event.' }, 400);
      await setGoogleEventHidden(uid, calendarId, eventId, body.action === 'hide');
      return json({ hidden: body.action === 'hide' });
    }
    if (body.action === 'importMany') {
      if (!Array.isArray(body.items) || body.items.some((item) => !item || typeof item !== 'object' || typeof item.calendarId !== 'string' || typeof item.eventId !== 'string' || typeof item.studentId !== 'number'))
        return json({ error: 'Choose valid Google events and students.' }, 400);
      return json({ imported: await importGoogleCalendarEvents(uid, body.items as { calendarId: string; eventId: string; studentId: number }[]) });
    }
    return json({ error: 'Unknown Google Calendar action.' }, 400);
  } catch (error) {
    return json({ error: message(error) }, /Sign in|expired/.test(message(error)) ? 401 : /teacher account/.test(message(error)) ? 403 : /student|event|calendar|Choose|Reconnect|timed/.test(message(error)) ? 400 : 502);
  }
}
