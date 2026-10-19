import { useMemo, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { ActionFeedback, Button, EmptyState, Field, LoadingState, Panel, SelectField } from '@/components/ui';
import { useRecords } from '@/hooks/use-records';
import { useAppPreferences } from '@/providers/app-preferences';
import { deleteStudent, type ClassioRecord } from '@/services/classio-data';
import { setTeacherStudentActive } from '@/services/dashboard-student-status';
import { colors } from '@/theme';

export default function DeleteStudentScreen() {
  const { t } = useAppPreferences(); const { records, loading, error, refresh } = useRecords('students');
  const params = useLocalSearchParams<{ studentId?: string }>();
  const [query, setQuery] = useState(''); const [selectedOverride, setSelected] = useState<ClassioRecord | null>(null); const [confirming, setConfirming] = useState(false); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  const visible = useMemo(() => records.filter((row) => `${row.student || ''} ${row.email || ''}`.toLowerCase().includes(query.trim().toLowerCase())), [query, records]);
  const selected = selectedOverride || (!message && params.studentId ? records.find((row) => String(row.id) === params.studentId) || null : null);
  const remove = async () => { if (!selected || !confirming) return; setBusy(true); setMessage(''); try { const name = String(selected.student || ''); await deleteStudent(String(selected.id)); let statusError = ''; try { await setTeacherStudentActive(name, true); } catch (reason) { statusError = reason instanceof Error ? reason.message : String(reason); } setMessageTone(statusError ? 'error' : 'success'); setMessage(`${t('students.removed', { name })}${statusError ? ` · ${statusError}` : ''}`); setSelected(null); setConfirming(false); await refresh(); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('students.removeFailed')); } finally { setBusy(false); } };

  return <AppShell title={t('students.removeTitle')} eyebrow={t('pages.studentsEyebrow')}>
    <Panel style={styles.warning}><Text style={styles.warningIcon}>⚠️</Text><View style={styles.warningCopy}><Text style={styles.warningTitle}>{t('students.removeWarningTitle')}</Text><Text style={styles.warningBody}>{t('students.removeWarning')}</Text></View></Panel>

    <Field accessibilityLabel={t('students.search')} placeholder={t('students.search')} value={query} onChangeText={setQuery} />
    {loading ? <LoadingState /> : error ? <EmptyState title={t('students.directoryUnavailable')} body={error} /> : !visible.length ? <EmptyState title={t('students.noMatches')} body={t('students.noMatchesBody')} /> : <View style={styles.list}><SelectField label={t('students.chooseStudent')} value={String(selected?.id || '')} placeholder={t('students.chooseStudent')} help={t('students.removeSelectHelp')} options={visible.map((row) => ({ value: String(row.id), label: String(row.student || t('dashboard.studentFallback')), detail: String(row.email || t('students.noEmail')) }))} onChange={(id) => { setSelected(visible.find((row) => String(row.id) === id) || null); setConfirming(false); }} /></View>}
    {selected ? <Panel style={styles.confirm}><Text style={styles.confirmTitle}>{t('students.removeConfirmTitle', { name: String(selected.student || '') })}</Text><Text style={styles.confirmBody}>{t('students.removeConfirmBody')}</Text><Pressable onPress={() => setConfirming((value) => !value)} style={styles.checkRow}><View style={[styles.checkbox, confirming && styles.checkboxActive]}><Text style={styles.checkmark}>{confirming ? '✓' : ''}</Text></View><Text style={styles.checkLabel}>{t('students.removeCheckbox')}</Text></Pressable><Button disabled={!confirming || busy} onPress={() => void remove()}>{busy ? t('common.saving') : t('students.removeAction')}</Button></Panel> : null}<ActionFeedback message={message} tone={messageTone} />
  </AppShell>;
}

const styles = StyleSheet.create({
  warning: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, backgroundColor: colors.warningSoft, borderColor: colors.warning }, warningIcon: { fontSize: 22 }, warningCopy: { flex: 1 }, warningTitle: { color: colors.ink, fontSize: 15, fontWeight: '900' }, warningBody: { color: colors.muted, fontSize: 11, lineHeight: 18, marginTop: 4 }, message: { backgroundColor: colors.primarySoft, borderRadius: 10, padding: 12, marginVertical: 12 }, messageText: { color: colors.primary, fontSize: 11, fontWeight: '800' }, list: { gap: 8, marginTop: 12 }, student: { flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 13, padding: 12 }, studentActive: { borderColor: colors.danger, backgroundColor: colors.dangerSoft }, avatar: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: colors.inverse, fontWeight: '900' }, studentCopy: { flex: 1 }, studentName: { color: colors.ink, fontSize: 13, fontWeight: '900' }, studentMeta: { color: colors.muted, fontSize: 10, marginTop: 3 }, selectMark: { color: colors.danger, fontSize: 18, fontWeight: '900' }, confirm: { marginTop: 16, borderColor: colors.danger }, confirmTitle: { color: colors.ink, fontSize: 17, fontWeight: '900' }, confirmBody: { color: colors.muted, fontSize: 11, lineHeight: 18, marginTop: 5 }, checkRow: { flexDirection: 'row', alignItems: 'center', gap: 9, marginVertical: 15 }, checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 1, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' }, checkboxActive: { backgroundColor: colors.danger, borderColor: colors.danger }, checkmark: { color: colors.inverse, fontWeight: '900' }, checkLabel: { color: colors.ink, fontSize: 11, fontWeight: '700', flex: 1 },
});
