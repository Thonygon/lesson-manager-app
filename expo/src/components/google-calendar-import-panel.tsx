import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import type { ClassioRecord } from '@/services/classio-data';
import { googleEventMatchesClassioLesson, type CalendarEvent } from '@/services/calendar-workspace';
import { importGoogleCalendarEvents } from '@/services/google-calendar-inbound';
import type { GoogleCalendarEvent } from '@/server/google-calendar-inbound';
import { colors } from '@/theme';

const PAGE_SIZE = 12;
export function GoogleCalendarImportPanel({ events, students, classioEvents, onImported }: { events: GoogleCalendarEvent[]; students: ClassioRecord[]; classioEvents: CalendarEvent[]; onImported: () => void }) {
  const { t, language } = useAppPreferences();
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const pending = useMemo(() => events.filter((event) => !event.studentId && !event.allDay && event.status !== 'cancelled').sort((a, b) => a.startAt.localeCompare(b.startAt)), [events]);
  if (!pending.length) return null;
  const pages = Math.max(1, Math.ceil(pending.length / PAGE_SIZE));
  const visible = pending.slice((Math.min(page, pages) - 1) * PAGE_SIZE, Math.min(page, pages) * PAGE_SIZE);
  const selected = pending.flatMap((event) => {
    const studentId = Number(choices[`${event.calendarId}\0${event.id}`]);
    return Number.isSafeInteger(studentId) && studentId > 0 ? [{ calendarId: event.calendarId, eventId: event.id, studentId }] : [];
  });
  const importSelected = async () => {
    setBusy(true); setMessage('');
    try {
      const count = await importGoogleCalendarEvents(selected.slice(0, 100));
      setChoices({}); setMessage(t('calendar.googleImportedCount', { count })); onImported();
    } catch (error) { setMessage(error instanceof Error ? error.message : t('calendar.googleLinkFailed')); }
    finally { setBusy(false); }
  };
  return <Panel style={styles.panel}>
    <Text style={styles.title}>{t('calendar.googleImportTitle')}</Text>
    <Text style={styles.help}>{t('calendar.googleImportHelp')}</Text>
    {visible.map((event) => {
      const key = `${event.calendarId}\0${event.id}`;
      const chosenStudent = students.find((row) => String(row.id) === choices[key]);
      const possibleDuplicate = chosenStudent && googleEventMatchesClassioLesson(classioEvents, event, String(chosenStudent.student || ''));
      return <View key={key} style={styles.row}><View style={styles.copy}><Text style={styles.eventTitle}>{event.title || t('calendar.googleUntitled')}</Text><Text style={styles.eventDate}>{new Date(event.startAt).toLocaleString(language)}</Text>{possibleDuplicate ? <Text style={styles.duplicate}>{t('calendar.googlePossibleDuplicate')}</Text> : null}</View><View style={styles.select}><SelectField label={t('calendar.googleLinkStudent')} value={choices[key] || ''} options={[{ value: '', label: t('calendar.googleChooseStudent') }, ...students.map((row) => ({ value: String(row.id), label: String(row.student || '') }))]} onChange={(value) => setChoices((current) => ({ ...current, [key]: value }))} /></View></View>;
    })}
    <View style={styles.actions}><Button disabled={busy || !selected.length} onPress={() => void importSelected()}>{t('calendar.googleImportSelected', { count: Math.min(100, selected.length) })}</Button>{page > 1 ? <Button secondary onPress={() => setPage((value) => value - 1)}>{t('common.previous')}</Button> : null}{page < pages ? <Button secondary onPress={() => setPage((value) => value + 1)}>{t('common.next')}</Button> : null}</View>
    {message ? <Text style={styles.message}>{message}</Text> : null}
  </Panel>;
}

const styles = StyleSheet.create({ panel: { gap: 10, marginTop: 18 }, title: { color: colors.ink, fontSize: 16, fontWeight: '900' }, help: { color: colors.muted, fontSize: 11, lineHeight: 17 }, row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 12, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 10 }, copy: { flex: 1, minWidth: 170 }, eventTitle: { color: colors.ink, fontSize: 11, fontWeight: '800' }, eventDate: { color: colors.muted, fontSize: 9, marginTop: 3 }, duplicate: { color: colors.warning, fontSize: 9, fontWeight: '700', marginTop: 4 }, select: { minWidth: 190, flex: 1 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, message: { color: colors.primary, fontSize: 11 } });
