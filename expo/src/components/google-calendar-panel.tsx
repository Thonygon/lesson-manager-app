import { useEffect, useState } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';
import * as Linking from 'expo-linking';

import { ActionFeedback, Button, Panel } from '@/components/ui';
import { requireSupabase } from '@/lib/supabase';
import { colors } from '@/theme';
import { useAppPreferences } from '@/providers/app-preferences';

type Status = { configured: boolean; connected: boolean };
async function calendarRequest(action?: 'connect' | 'sync' | 'disconnect') {
  const { data, error } = await requireSupabase().auth.getSession();
  if (error || !data.session) throw error ?? new Error('Sign in to use Google Calendar.');
  const response = await fetch('/api/google-calendar', { method: action ? 'POST' : 'GET', headers: { Authorization: `Bearer ${data.session.access_token}`, ...(action ? { 'Content-Type': 'application/json' } : {}) }, ...(action ? { body: JSON.stringify({ action }) } : {}), cache: 'no-store' });
  const result = await response.json() as Status & { error?: string; url?: string; synced?: number; removed?: number };
  if (!response.ok) throw new Error(result.error || 'Google Calendar is unavailable.');
  return result;
}

export function GoogleCalendarPanel({ callbackStatus }: { callbackStatus?: string }) {
  const { t } = useAppPreferences();
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [messageTone, setMessageTone] = useState<'success' | 'error'>(callbackStatus === 'connected' ? 'success' : 'error');
  const [message, setMessage] = useState(callbackStatus === 'connected' ? t('calendar.googleCallbackConnected') : callbackStatus === 'failed' ? t('calendar.googleCallbackFailed') : callbackStatus === 'denied' ? t('calendar.googleCallbackDenied') : '');
  useEffect(() => { void calendarRequest().then(setStatus).catch((error) => { setMessageTone('error'); setMessage(error instanceof Error ? error.message : 'Google Calendar status is unavailable.'); }); }, []);
  const action = async (name: 'connect' | 'sync' | 'disconnect') => {
    setBusy(true); setMessage('');
    try {
      const result = await calendarRequest(name);
      if (name === 'connect' && result.url) {
        if (Platform.OS === 'web' && typeof window !== 'undefined') window.location.assign(result.url);
        else await Linking.openURL(result.url);
        return;
      }
      if (name === 'sync') { setMessageTone('success'); setMessage(t('calendar.googleSyncResult', { synced: result.synced || 0, removed: result.removed || 0 })); }
      if (name === 'disconnect') { setMessageTone('success'); setMessage(t('calendar.googleDisconnectResult')); }
      setStatus(await calendarRequest());
    } catch (error) { setMessageTone('error'); setMessage(error instanceof Error ? error.message : 'Google Calendar is unavailable.'); }
    finally { setBusy(false); }
  };
  return <Panel style={styles.panel}>
    <View style={styles.copy}>
      <Text style={styles.title}>Google Calendar</Text>
      <Text style={styles.description}>{t('calendar.googleDescription')}</Text>
      <Text style={styles.status}>{!status ? t('calendar.googleChecking') : !status.configured ? t('calendar.googleNeedsSetup') : status.connected ? `● ${t('calendar.googleConnected')}` : t('calendar.googleDisconnected')}</Text>

    </View>
    <View style={styles.actions}>
      {status?.configured && !status.connected ? <Button disabled={busy} onPress={() => void action('connect')}>{t('calendar.googleConnect')}</Button> : null}
      {status?.connected ? <><Button disabled={busy} onPress={() => void action('sync')}>{busy ? t('calendar.googleSyncing') : t('calendar.googleSync')}</Button><Button secondary disabled={busy} onPress={() => void action('disconnect')}>{t('calendar.googleDisconnect')}</Button></> : null}
    </View><ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} />
  </Panel>;
}

const styles = StyleSheet.create({ panel: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, alignItems: 'center', marginTop: 18 }, copy: { flex: 1, minWidth: 220 }, title: { color: colors.ink, fontSize: 17, fontWeight: '900' }, description: { color: colors.muted, fontSize: 12, lineHeight: 19, marginTop: 5 }, status: { color: colors.primary, fontSize: 11, fontWeight: '800', marginTop: 10 }, message: { color: colors.subtle, fontSize: 11, marginTop: 6 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 } });
