import { useState } from 'react';
import { Linking, StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Field, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { helpScreenshotUrl, updateHelpTicket, type HelpStatus, type HelpTicket } from '@/services/help-center';
import { colors } from '@/theme';

const STATUSES: HelpStatus[] = ['open', 'triaged', 'in_progress', 'resolved', 'closed'];

export function DeveloperHelpTickets({ tickets, initialId, onRefresh }: { tickets: HelpTicket[]; initialId?: string; onRefresh: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const [selectedId, setSelectedId] = useState(initialId || '');
  const [status, setStatus] = useState<HelpStatus>(() => tickets.find((ticket) => ticket.id === initialId)?.status || 'open');
  const [response, setResponse] = useState(() => tickets.find((ticket) => ticket.id === initialId)?.response || '');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [tone, setTone] = useState<'success' | 'error'>('error');
  const selected = tickets.find((ticket) => ticket.id === selectedId);
  const chooseTicket = (id: string) => {
    setSelectedId(id);
    const ticket = tickets.find((item) => item.id === id);
    setStatus(ticket?.status || 'open'); setResponse(ticket?.response || '');
    setMessage('');
  };
  const save = async () => {
    if (!selected || busy) return;
    setBusy(true); setMessage('');
    try { await updateHelpTicket(selected.id, status, response); await onRefresh(); setTone('success'); setMessage(t('help.developer.saved')); }
    catch { setTone('error'); setMessage(t('help.developer.saveFailed')); }
    finally { setBusy(false); }
  };
  const showScreenshot = async () => {
    if (!selected) return;
    try { const url = await helpScreenshotUrl(selected); if (!url) throw new Error('Missing screenshot'); await Linking.openURL(url); }
    catch { setTone('error'); setMessage(t('help.developer.imageUnavailable')); }
  };
  const pending = tickets.filter((ticket) => !['resolved', 'closed'].includes(ticket.status)).length;
  const ordered = [...tickets].sort((a, b) => {
    const priority = (ticket: HelpTicket) => !['resolved', 'closed'].includes(ticket.status) && ['privacy_rights', 'security_incident'].includes(ticket.kind) ? 1 : 0;
    return priority(b) - priority(a) || Date.parse(b.created_at) - Date.parse(a.created_at);
  });
  return <Panel style={styles.panel}>
    <Text style={styles.heading}>{t('help.developer.title')} · {pending}</Text>
    <Text style={styles.body}>{t('help.developer.body')}</Text>
    {tickets.length ? <SelectField label={t('help.developer.select')} value={selectedId} onChange={chooseTicket} options={[{ value: '', label: t('help.developer.choose') }, ...ordered.map((ticket) => ({ value: ticket.id, label: `#${ticket.ticket_number} · ${t(`help.kind.${ticket.kind}`)} · ${ticket.title}`, detail: t(`help.status.${ticket.status}`) }))]} /> : <Text style={styles.body}>{t('help.developer.empty')}</Text>}
    {selected ? <View style={styles.detail}>
      <Text style={styles.heading}>#{selected.ticket_number} · {selected.title}</Text>
      <Text style={styles.meta}>{t(`help.kind.${selected.kind}`)} · {new Date(selected.created_at).toLocaleString()} · {selected.page_path}</Text>
      {selected.privacy_scope ? <Text style={styles.meta}>{t('help.privacyScope')}: {t(`help.scope.${selected.privacy_scope}`)}</Text> : null}
      <Text style={styles.body}>{selected.description}</Text>
      {selected.screenshot_mime ? <Button secondary onPress={() => void showScreenshot()}>{t('help.developer.openImage')}</Button> : null}
      <SelectField label={t('help.developer.status')} value={status} onChange={(value) => setStatus(value as HelpStatus)} options={STATUSES.map((value) => ({ value, label: t(`help.status.${value}`) }))} />
      <Text style={styles.label}>{t('help.developer.response')}</Text>
      <Field accessibilityLabel={t('help.developer.response')} multiline numberOfLines={5} maxLength={2000} value={response} onChangeText={setResponse} style={styles.response} />
      <Button disabled={busy} onPress={() => void save()}>{busy ? t('common.saving') : t('common.save')}</Button>
    </View> : null}
    <ActionFeedback message={message} tone={tone} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} />
  </Panel>;
}

const styles = StyleSheet.create({
  panel: { gap: 14 }, detail: { gap: 12, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 15 },
  heading: { color: colors.ink, fontSize: 18, fontWeight: '900' }, body: { color: colors.muted, fontSize: 14, lineHeight: 21 },
  meta: { color: colors.subtle, fontSize: 12 }, label: { color: colors.ink, fontWeight: '700' }, response: { minHeight: 100, textAlignVertical: 'top' },
});
