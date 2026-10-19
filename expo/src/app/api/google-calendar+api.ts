import { authorizedUser, connectionUrl, disconnectGoogle, googleConfigured, googleConnected, syncGoogleCalendar } from '@/server/google-calendar';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
function errorMessage(error: unknown) { return error instanceof Error ? error.message : 'Google Calendar is unavailable.'; }

export async function GET(request: Request) {
  try {
    const uid = await authorizedUser(request);
    const configured = googleConfigured();
    return json({ configured, connected: configured ? await googleConnected(uid) : false });
  } catch (error) { return json({ error: errorMessage(error) }, 401); }
}

export async function POST(request: Request) {
  try {
    const uid = await authorizedUser(request);
    const body = await request.json() as { action?: string };
    if (body.action === 'connect') return json({ url: connectionUrl(uid) });
    if (body.action === 'disconnect') { await disconnectGoogle(uid); return json({ connected: false }); }
    if (body.action === 'sync') return json(await syncGoogleCalendar(uid));
    return json({ error: 'Unknown calendar action.' }, 400);
  } catch (error) {
    const message = errorMessage(error);
    return json({ error: message }, /expired|Sign in/.test(message) ? 401 : /configured|credentials/.test(message) ? 503 : 502);
  }
}
