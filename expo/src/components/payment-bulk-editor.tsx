import { useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { updatePayment, type ClassioRecord } from '@/services/classio-data';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import { ActionFeedback, Button, Field, Pagination, Panel, SelectField } from './ui';

const SUBJECTS = ['English', 'Spanish', 'Mathematics', 'Science', 'Music', 'Study Skills', 'Other'];
type Draft = { paymentDate: string; units: string; amount: string; modality: 'Online' | 'Offline'; subject: string; customSubject: string; startDate: string; expiryDate: string; adjustment: string; normalized: boolean; note: string };
const date = (value: unknown) => String(value || '').slice(0, 10);
const draftFor = (row: ClassioRecord): Draft => ({ paymentDate: date(row.payment_date), units: String(row.number_of_lesson ?? ''), amount: String(row.paid_amount ?? ''), modality: row.modality === 'Offline' ? 'Offline' : 'Online', subject: String(row.subject || 'English'), customSubject: String(row.subject_custom || ''), startDate: date(row.package_start_date || row.payment_date), expiryDate: date(row.package_expiry_date), adjustment: String(row.lesson_adjustment_units ?? 0), normalized: Boolean(row.package_normalized), note: String(row.normalized_note || '') });
const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T12:00:00`));

export function PaymentBulkEditor({ student, records, onSaved }: { student: string; records: ClassioRecord[]; onSaved: () => Promise<unknown> }) {
  const { t } = useAppPreferences();
  const rows = records.filter((row) => String(row.student || '').trim() === student);
  const [changes, setChanges] = useState<Record<string, Draft>>({});
  const pending = useRef(new Map<string, { payload: string; requestId: string }>());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(rows.length / 8));
  const currentPage = Math.min(page, totalPages);
  const visible = rows.slice((currentPage - 1) * 8, currentPage * 8);
  const update = (row: ClassioRecord, patch: Partial<Draft>) => { const id = String(row.id); setChanges((current) => ({ ...current, [id]: { ...(current[id] || draftFor(row)), ...patch } })); setMessage(''); };
  const changedRows = rows.filter((row) => changes[String(row.id)]);

  const apply = async () => {
    for (const row of changedRows) {
      const item = changes[String(row.id)];
      const units = Number(item.units); const amount = Number(item.amount); const adjustment = Number(item.adjustment);
      if (!validDate(item.paymentDate) || !validDate(item.startDate) || (item.expiryDate && !validDate(item.expiryDate))) return setMessage(t('payments.bulkInvalidDate', { id: String(row.id) }));
      if (!Number.isInteger(units) || units < 1 || units > 500 || !Number.isFinite(amount) || amount < 0 || !Number.isInteger(adjustment)) return setMessage(t('payments.bulkInvalidNumbers', { id: String(row.id) }));
      if (item.subject === 'Other' && !item.customSubject.trim()) return setMessage(t('payments.bulkInvalidSubject', { id: String(row.id) }));
    }
    setBusy(true); setMessage('');
    try {
      for (const row of changedRows) {
        const item = changes[String(row.id)];
        const input = { student, lessonUnits: Number(item.units), paymentDate: item.paymentDate, paidAmount: Number(item.amount), currency: String(row.currency || 'TRY'), modality: item.modality, subject: item.subject, customSubject: item.customSubject, packageStartDate: item.startDate, packageExpiryDate: item.expiryDate, adjustmentUnits: Number(item.adjustment), normalized: item.normalized, normalizedNote: item.note };
        const payload = JSON.stringify(input); const key = String(row.id); const previous = pending.current.get(key);
        const requestId = previous?.payload === payload ? previous.requestId : crypto.randomUUID();
        pending.current.set(key, { payload, requestId });
        await updatePayment(key, input, requestId);
      }
      await onSaved(); pending.current.clear(); setChanges({}); setMessageTone('success'); setMessage(t('payments.bulkSaved', { count: changedRows.length }));
    } catch (error) { setMessageTone('error'); setMessage(error instanceof Error ? error.message : t('payments.bulkFailed')); }
    finally { setBusy(false); }
  };

  return <View style={styles.root}>
    <Text style={styles.help}>{t('payments.bulkIntro', { student })}</Text>
    {rows.length === 0 ? <Text style={styles.help}>{t('payments.bulkEmpty')}</Text> : <>
      <ScrollView horizontal showsHorizontalScrollIndicator><View style={styles.table}>
        {visible.map((row) => { const item = changes[String(row.id)] || draftFor(row); return <Panel key={String(row.id)} style={styles.row}>
          <Text style={styles.heading}>{t('payments.bulkPayment', { id: String(row.id) })} · {String(row.currency || 'TRY')}{changes[String(row.id)] ? ` · ${t('payments.bulkEdited')}` : ''}</Text>
          <View style={styles.fields}>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.paymentDate')}</Text><Field value={item.paymentDate} onChangeText={(value) => update(row, { paymentDate: value })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.bulkUnits')}</Text><Field keyboardType="number-pad" value={item.units} onChangeText={(value) => update(row, { units: value })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.amount')}</Text><Field keyboardType="decimal-pad" value={item.amount} onChangeText={(value) => update(row, { amount: value })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('records.modality')}</Text><SelectField label={t('records.modality')} value={item.modality} options={['Online', 'Offline'].map((value) => ({ value, label: value === 'Offline' ? t('records.offline') : t('records.online') }))} onChange={(value) => update(row, { modality: value as Draft['modality'] })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('records.subject')}</Text><SelectField label={t('records.subject')} value={item.subject} options={SUBJECTS.map((value) => ({ value, label: t(`records.subject.${value}`) }))} onChange={(value) => update(row, { subject: value })} /></View>
            {item.subject === 'Other' ? <View style={styles.cell}><Text style={styles.label}>{t('records.customSubject')}</Text><Field value={item.customSubject} onChangeText={(value) => update(row, { customSubject: value })} /></View> : null}
            <View style={styles.cell}><Text style={styles.label}>{t('payments.packageStart')}</Text><Field value={item.startDate} onChangeText={(value) => update(row, { startDate: value })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.bulkExpiry')}</Text><Field value={item.expiryDate} onChangeText={(value) => update(row, { expiryDate: value })} placeholder={t('payments.bulkOptional')} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.unitAdjustment')}</Text><Field keyboardType="number-pad" value={item.adjustment} onChangeText={(value) => update(row, { adjustment: value })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.bulkState')}</Text><SelectField label={t('payments.packageState')} value={item.normalized ? 'Normalized' : 'Standard'} options={['Standard', 'Normalized'].map((value) => ({ value, label: t(value === 'Normalized' ? 'payments.normalized' : 'payments.standard') }))} onChange={(value) => update(row, { normalized: value === 'Normalized' })} /></View>
            <View style={styles.cell}><Text style={styles.label}>{t('payments.bulkNote')}</Text><Field value={item.note} onChangeText={(value) => update(row, { note: value })} /></View>
          </View>
        </Panel>; })}
      </View></ScrollView>
      <View style={styles.actions}><Pagination page={currentPage} totalPages={totalPages} totalItems={rows.length} onPageChange={setPage} disabled={busy} /><Button disabled={busy || changedRows.length === 0} onPress={() => void apply()}>{busy ? t('payments.bulkApplying') : t('payments.bulkApply', { count: changedRows.length })}</Button></View>
    </>}
    <ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} />
  </View>;
}

const styles = StyleSheet.create({ root: { gap: 12 }, help: { color: colors.muted, fontSize: 12 }, table: { gap: 8, minWidth: 740 }, row: { padding: 14, gap: 8 }, heading: { color: colors.ink, fontWeight: '800' }, fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 }, cell: { width: 150, gap: 3 }, label: { color: colors.muted, fontSize: 10, fontWeight: '700' }, actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8 }, message: { color: colors.primary, fontSize: 12, fontWeight: '700' } });
