import { Platform } from 'react-native';
import { requireSupabase } from '@/lib/supabase';
import { hostingApiUrl } from '@/lib/hosting-api-url';

const nativeVisits = new Map<string, string>();
const sentUsers = new Set<string>();

/** Count at most one visit per signed-in browser tab or native app process. */
export async function recordAppVisit(): Promise<void> {
  const { data } = await requireSupabase().auth.getSession();
  if (!data.session) return;
  const userId = data.session.user.id;
  if (sentUsers.has(userId)) return;
  let eventId = nativeVisits.get(userId) || '';
  if (Platform.OS === 'web' && typeof sessionStorage !== 'undefined') {
    const key = `classio.appVisitId.${userId}`;
    eventId = sessionStorage.getItem(key) || '';
    if (!eventId) { eventId = crypto.randomUUID(); sessionStorage.setItem(key, eventId); }
  } else if (!eventId) { eventId = crypto.randomUUID(); nativeVisits.set(userId, eventId); }
  const response = await fetch(hostingApiUrl('/api/app-visit'), { method: 'POST', headers: { Authorization: `Bearer ${data.session.access_token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ eventId }), cache: 'no-store' });
  if (response.ok) sentUsers.add(userId);
}
