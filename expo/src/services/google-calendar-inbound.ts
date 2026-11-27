import { hostingApiUrl } from '@/lib/hosting-api-url';
import { requireSupabase } from '@/lib/supabase';
import type { GoogleCalendarEvent, GoogleCalendarItem, HiddenGoogleCalendarEvent } from '@/server/google-calendar-inbound';

async function request(path: string, body?: Record<string, unknown>) {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error ?? new Error('Sign in to use Google Calendar.');
  const response = await fetch(hostingApiUrl(path as `/${string}`), {
    method: body ? 'POST' : 'GET', headers: { Authorization: `Bearer ${data.session.access_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}), cache: 'no-store',
  });
  const result = await response.json() as Record<string, unknown>;
  if (!response.ok) throw new Error(String(result.error || 'Google Calendar is unavailable.'));
  return result;
}

export async function googleCalendarConnected() {
  const result = await request('/api/google-calendar');
  return Boolean(result.connected);
}

export async function getGoogleCalendarChoices(): Promise<GoogleCalendarItem[]> {
  const result = await request('/api/google-calendar-inbound?mode=calendars');
  return (result.calendars || []) as GoogleCalendarItem[];
}

export async function saveGoogleCalendarChoices(calendarIds: string[]): Promise<GoogleCalendarItem[]> {
  const result = await request('/api/google-calendar-inbound', { action: 'selectCalendars', calendarIds });
  return (result.calendars || []) as GoogleCalendarItem[];
}

export async function getGoogleCalendarRange(start: string, end: string): Promise<{ events: GoogleCalendarEvent[]; warning: string }> {
  const result = await request(`/api/google-calendar-inbound?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
  return { events: (result.events || []) as GoogleCalendarEvent[], warning: String(result.warning || '') };
}

export async function getHiddenGoogleCalendarEvents(page: number): Promise<{ events: HiddenGoogleCalendarEvent[]; total: number }> {
  const result = await request(`/api/google-calendar-inbound?mode=hidden&page=${encodeURIComponent(String(page))}`);
  return { events: (result.events || []) as HiddenGoogleCalendarEvent[], total: Number(result.total || 0) };
}

export async function setGoogleCalendarEventHidden(calendarId: string, eventId: string, hidden: boolean) {
  await request('/api/google-calendar-inbound', { action: hidden ? 'hide' : 'show', calendarId, eventId });
}

export async function linkGoogleCalendarEvent(calendarId: string, eventId: string, studentId: number | null) {
  await request('/api/google-calendar-inbound', { action: studentId ? 'link' : 'unlink', calendarId, eventId, ...(studentId ? { studentId } : {}) });
}

export async function importGoogleCalendarEvents(items: { calendarId: string; eventId: string; studentId: number }[]) {
  const result = await request('/api/google-calendar-inbound', { action: 'importMany', items });
  return Number(result.imported || 0);
}
