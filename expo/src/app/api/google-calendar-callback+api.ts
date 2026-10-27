import { finishConnection } from '@/server/google-calendar';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const destination = new URL('/calendar', 'https://app.masterclassio.com');
  const code = url.searchParams.get('code'); const state = url.searchParams.get('state');
  if (!code || !state || url.searchParams.has('error')) {
    destination.searchParams.set('googleCalendar', 'denied');
    return Response.redirect(destination, 303);
  }
  try {
    await finishConnection(code, state);
    destination.searchParams.set('googleCalendar', 'connected');
  } catch (error) {
    console.error('Google Calendar authorization failed', error);
    destination.searchParams.set('googleCalendar', 'failed');
  }
  return Response.redirect(destination, 303);
}
