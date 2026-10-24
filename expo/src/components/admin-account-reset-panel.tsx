import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Disclosure, Field, SelectField } from '@/components/ui';
import { adminResetCopy } from '@/lib/admin-reset-copy';
import { useAppPreferences } from '@/providers/app-preferences';
import { executeAdminAccountReset, previewAdminAccountReset, type ResetOptions, type ResetPreview, type ResetScope } from '@/services/admin-account-reset';
import { colors } from '@/theme';

const scopes: ResetScope[] = ['student', 'teacher', 'full'];

export function AdminAccountResetPanel({ userId, initialNotes, reload }: { userId: string; initialNotes: string; reload: () => Promise<void> }) {
  const { language, t } = useAppPreferences();
  const copy = adminResetCopy[language];
  const label = (key: string) => String(copy[key as keyof typeof copy] || key.replaceAll('_', ' '));
  const [scope, setScope] = useState<ResetScope>('student');
  const [archiveShared, setArchiveShared] = useState(true);
  const [removeLinks, setRemoveLinks] = useState(true);
  const [notes, setNotes] = useState(initialNotes);
  const [preview, setPreview] = useState<ResetPreview | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [phrase, setPhrase] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [tone, setTone] = useState<'success' | 'error'>('error');
  const expectedPhrase = `RESTART ${scope.toUpperCase()}`;
  const options: ResetOptions = { user_id: userId, scope, archive_shared_resources: archiveShared, remove_relationships: removeLinks, notes };
  const invalidate = () => { setPreview(null); setConfirm(false); setPhrase(''); setMessage(''); };
  const loadPreview = async () => {
    setBusy(true); setMessage('');
    try { setPreview(await previewAdminAccountReset(options)); }
    catch (error) { setPreview(null); setTone('error'); setMessage(error instanceof Error ? error.message : t('admin.actionFailed')); }
    finally { setBusy(false); }
  };
  const execute = async () => {
    if (!preview || !confirm || phrase.trim().toUpperCase() !== expectedPhrase) return;
    setBusy(true); setMessage('');
    try {
      const result = await executeAdminAccountReset({ ...options, confirm: true, confirmation_phrase: phrase });
      await reload();
      setTone(result.audited ? 'success' : 'error'); setMessage(`${label(`admin_restart_account_success_${scope}`)} ${label('admin_restart_account_done_counts').replace('{count}', String(Object.values(result.counters).reduce((sum, count) => sum + Number(count || 0), 0)))}${result.audited ? '' : ` ${t('admin.auditWriteFailed')}`}`);
      setPreview(null); setConfirm(false); setPhrase('');
    } catch (error) { setTone('error'); setMessage(error instanceof Error ? error.message : t('admin.actionFailed')); }
    finally { setBusy(false); }
  };
  return <Disclosure title={label('admin_restart_account_title')} summary={label('admin_restart_account_caption')}>
    <View style={styles.stack}>
      <SelectField label={label('admin_restart_scope_label')} value={scope} options={scopes.map((value) => ({ value, label: label(`admin_restart_scope_${value}`) }))} onChange={(value) => { setScope(value as ResetScope); invalidate(); }} />
      {scope !== 'student' ? <SelectField label={label('admin_restart_archive_shared_label')} value={archiveShared ? 'yes' : 'no'} options={[{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }]} onChange={(value) => { setArchiveShared(value === 'yes'); invalidate(); }} /> : null}
      <SelectField label={label('admin_restart_remove_relationships_label')} value={removeLinks ? 'yes' : 'no'} options={[{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }]} onChange={(value) => { setRemoveLinks(value === 'yes'); invalidate(); }} />
      <Text style={styles.label}>{label('admin_restart_account_notes_label')}</Text><Field accessibilityLabel={label('admin_restart_account_notes_label')} value={notes} onChangeText={(value) => { setNotes(value); invalidate(); }} multiline numberOfLines={3} />
      <Button secondary disabled={busy} onPress={() => void loadPreview()}>{busy ? t('common.loading') : label('admin_restart_preview_title')}</Button>
      {preview ? <View style={styles.preview}><Text style={styles.title}>{label('admin_restart_preview_title')}</Text><Text style={styles.help}>{label('admin_restart_preview_caption')}</Text><View style={styles.summary}>{(['delete', 'archive', 'reset'] as const).map((action) => <View key={action} style={styles.stat}><Text style={styles.statValue}>{preview.summary[action]}</Text><Text style={styles.statLabel}>{label(`admin_reset_summary_${action}`)}</Text></View>)}</View>{preview.rows.length ? preview.rows.map((row, index) => <View key={`${row.label_key}-${index}`} style={styles.row}><View style={styles.rowCopy}><Text style={styles.rowTitle}>{label(row.label_key)}</Text>{row.note_key ? <Text style={styles.help}>{label(row.note_key)}</Text> : null}</View><Text style={styles.rowCount}>{row.count} · {label(`admin_reset_action_${row.action}`)}</Text></View>) : <Text style={styles.help}>{label('admin_restart_preview_empty')}</Text>}</View> : null}
      {preview ? <><SelectField label={label('admin_restart_account_confirm_label')} value={confirm ? 'yes' : 'no'} options={[{ value: 'no', label: t('admin.value.no') }, { value: 'yes', label: t('admin.value.yes') }]} onChange={(value) => setConfirm(value === 'yes')} /><Text style={styles.label}>{label('admin_restart_account_phrase_label').replace('{phrase}', expectedPhrase)}</Text><Field accessibilityLabel={label('admin_restart_account_phrase_label').replace('{phrase}', expectedPhrase)} value={phrase} onChangeText={setPhrase} autoCapitalize="characters" /><Button secondary disabled={busy || !confirm || phrase.trim().toUpperCase() !== expectedPhrase} onPress={() => void execute()}>{label('admin_restart_account_button')}</Button></> : null}
      <ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={tone} />
    </View>
  </Disclosure>;
}

const styles = StyleSheet.create({ stack: { gap: 12, paddingTop: 8 }, label: { color: colors.muted, fontSize: 11, fontWeight: '800' }, title: { color: colors.ink, fontWeight: '900', fontSize: 16 }, help: { color: colors.muted, fontSize: 11, lineHeight: 17 }, preview: { gap: 10, borderWidth: 1, borderColor: colors.line, borderRadius: 14, padding: 14 }, summary: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 }, stat: { minWidth: 90, flexGrow: 1, backgroundColor: colors.surfaceSoft, padding: 12, borderRadius: 10 }, statValue: { color: colors.ink, fontSize: 20, fontWeight: '900' }, statLabel: { color: colors.muted, fontSize: 11 }, row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, paddingVertical: 7, borderTopWidth: 1, borderTopColor: colors.line }, rowCopy: { flex: 1 }, rowTitle: { color: colors.ink, fontSize: 12, fontWeight: '800' }, rowCount: { color: colors.primary, fontSize: 11, fontWeight: '800' } });
