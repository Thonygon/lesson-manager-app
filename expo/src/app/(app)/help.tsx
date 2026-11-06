import { createElement, useEffect, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { ActionFeedback, Button, Disclosure, Field, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { checkedHelpScreenshot, myHelpTickets, submitHelpTicket, type HelpKind, type HelpScreenshot, type HelpTicket, type PrivacyScope } from '@/services/help-center';
import { colors } from '@/theme';

const GUIDES = ['start', 'connections', 'lessons', 'payments', 'resources', 'generation', 'reviews', 'rights'] as const;
const KINDS: HelpKind[] = ['bug', 'privacy_rights', 'security_incident', 'idea', 'accessibility', 'other'];
const PRIVACY_SCOPES: PrivacyScope[] = ['access', 'rectification', 'erasure', 'restriction', 'portability', 'objection', 'other'];

function decodeBase64(value: string): Uint8Array {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  const bytes = new Uint8Array(Math.floor(value.length * 3 / 4));
  let buffer = 0; let bits = 0; let length = 0;
  for (const character of value) {
    if (character === '=') break;
    const digit = alphabet.indexOf(character);
    if (digit < 0) continue;
    buffer = (buffer << 6) | digit; bits += 6;
    if (bits >= 8) { bits -= 8; bytes[length++] = (buffer >> bits) & 255; }
  }
  return bytes.slice(0, length);
}

export default function HelpScreen() {
  const { t } = useAppPreferences();
  const params = useLocalSearchParams<{ from?: string; ticket?: string }>();
  const [kind, setKind] = useState<HelpKind>('bug');
  const [privacyScope, setPrivacyScope] = useState<PrivacyScope | ''>('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [pagePath, setPagePath] = useState(typeof params.from === 'string' && params.from.startsWith('/') ? params.from : '/help');
  const [image, setImage] = useState<HelpScreenshot | null>(null);
  const [tickets, setTickets] = useState<HelpTicket[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [tone, setTone] = useState<'success' | 'error'>('error');
  const [submittedNumber, setSubmittedNumber] = useState<number | null>(null);
  const focusedTicket = tickets.find((ticket) => ticket.id === params.ticket);

  useEffect(() => {
    let active = true;
    void myHelpTickets(params.ticket).then((rows) => { if (active) setTickets(rows); }).catch(() => {});
    return () => { active = false; };
  }, [params.ticket]);
  const chooseFile = async (file: HelpScreenshot) => {
    try { await checkedHelpScreenshot(file); setImage(file); setMessage(''); }
    catch { setImage(null); setTone('error'); setMessage(t('help.invalidImage')); }
  };
  const pickNative = async () => {
    const picker = await import('expo-image-picker');
    const result = await picker.launchImageLibraryAsync({ mediaTypes: ['images'], base64: true, quality: 1 });
    const asset = result.assets?.[0];
    if (!asset?.base64) return;
    const bytes = decodeBase64(asset.base64);
    await chooseFile({ name: asset.fileName || 'screenshot.jpg', type: asset.mimeType || 'image/jpeg', size: bytes.length, data: bytes });
  };
  const submit = async () => {
    if (busy) return;
    if (title.trim().length < 5 || description.trim().length < 15) { setTone('error'); setMessage(t('help.invalidDescription')); return; }
    setBusy(true); setMessage(''); setSubmittedNumber(null);
    try {
      const result = await submitHelpTicket({ kind, privacyScope: privacyScope || null, title, description, pagePath, screenshot: image });
      setSubmittedNumber(result.number); setTitle(''); setDescription(''); setImage(null); setPrivacyScope('');
      setTone(result.screenshotUploaded ? 'success' : 'error');
      setMessage(t(result.screenshotUploaded ? 'help.sent' : 'help.sentWithoutImage'));
      setTickets(await myHelpTickets(params.ticket));
    } catch (reason) {
      const key = reason instanceof Error && reason.message.startsWith('help.') ? reason.message : 'help.submitFailed';
      setTone('error'); setMessage(t(key));
    } finally { setBusy(false); }
  };
  return <AppShell title={t('help.title')} eyebrow={t('help.eyebrow')}>
    <View style={styles.stack}>
      {focusedTicket ? <Panel style={styles.panel}><Text accessibilityRole="header" style={styles.heading}>{t('help.selectedReport')} · #{focusedTicket.ticket_number}</Text><Text style={styles.ticketTitle}>{focusedTicket.title}</Text><Text style={styles.body}>{t(`help.status.${focusedTicket.status}`)}</Text>{focusedTicket.response ? <Text style={styles.response}>{focusedTicket.response}</Text> : null}</Panel> : null}
      <Panel style={styles.panel}><Text style={styles.heading}>{t('help.guides')}</Text><Text style={styles.body}>{t('help.guidesIntro')}</Text>
        {GUIDES.map((key) => <Disclosure key={key} title={t(`help.guide.${key}.title`)}><Text style={styles.body}>{t(`help.guide.${key}.body`)}</Text></Disclosure>)}
      </Panel>
      <Panel style={styles.panel}><Text style={styles.heading}>{t('help.contact')}</Text><Text style={styles.body}>{t('help.contactBody')}</Text><Pressable accessibilityRole="link" onPress={() => void Linking.openURL('mailto:info@masterclassio.com')}><Text style={styles.link}>info@masterclassio.com</Text></Pressable></Panel>
      <Panel style={styles.panel}><Text style={styles.heading}>{t('help.reportTitle')}</Text><Text style={styles.body}>{t('help.reportIntro')}</Text>
        <SelectField label={t('help.kind')} value={kind} onChange={(value) => { setKind(value as HelpKind); setPrivacyScope(''); }} options={KINDS.map((value) => ({ value, label: t(`help.kind.${value}`) }))} />
        {kind === 'privacy_rights' ? <><SelectField label={t('help.privacyScope')} value={privacyScope} placeholder={t('help.privacyScopeRequired')} onChange={(value) => setPrivacyScope(value as PrivacyScope)} options={PRIVACY_SCOPES.map((value) => ({ value, label: t(`help.scope.${value}`) }))} /><Text style={styles.body}>{t('help.privacyCaution')}</Text></> : null}
        {kind === 'security_incident' ? <Text style={styles.body}>{t('help.securityCaution')}</Text> : null}
        <View><Text style={styles.label}>{t('help.subject')}</Text><Field accessibilityLabel={t('help.subject')} value={title} maxLength={120} onChangeText={setTitle} placeholder={t('help.subjectPlaceholder')} /></View>
        <View><Text style={styles.label}>{t('help.description')}</Text><Field accessibilityLabel={t('help.description')} value={description} maxLength={4000} multiline numberOfLines={6} onChangeText={setDescription} placeholder={t('help.descriptionPlaceholder')} style={styles.description} /></View>
        <View><Text style={styles.label}>{t('help.page')}</Text><Field accessibilityLabel={t('help.page')} value={pagePath} maxLength={300} onChangeText={setPagePath} placeholder="/resources" /></View>
        <View style={styles.upload}><Text style={styles.label}>{t('help.screenshot')}</Text><Text style={styles.body}>{t('help.screenshotPrivacy')}</Text>
          {Platform.OS === 'web' ? createElement('input', { type: 'file', accept: 'image/png,image/jpeg', 'aria-label': t('help.screenshot'), onChange: (event: { target: { files?: FileList; value: string } }) => { const file = event.target.files?.[0]; if (file) void chooseFile(file); event.target.value = ''; }, style: { color: colors.ink, maxWidth: '100%' } }) : <Button secondary onPress={() => void pickNative()}>{t('help.chooseImage')}</Button>}
          {image ? <View style={styles.imageSelected}><Text style={styles.body}>{image.name}</Text><Button secondary onPress={() => setImage(null)}>{t('help.removeImage')}</Button></View> : null}
        </View>
        <Button disabled={busy} onPress={() => void submit()}>{busy ? t('common.saving') : t('help.send')}</Button>
        <ActionFeedback message={message} tone={tone} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} />
        {submittedNumber ? <Text accessibilityRole="alert" style={styles.confirmation}>{t('help.ticketNumber', { number: submittedNumber })}</Text> : null}
      </Panel>
      <Panel style={styles.panel}><Text style={styles.heading}>{t('help.myReports')}</Text>
        {tickets.length ? tickets.map((ticket) => <View key={ticket.id} style={styles.ticket}><Text style={styles.ticketTitle}>#{ticket.ticket_number} · {ticket.title}</Text><Text style={styles.body}>{t(`help.status.${ticket.status}`)} · {new Date(ticket.created_at).toLocaleDateString()}</Text>{ticket.response ? <Text style={styles.response}>{ticket.response}</Text> : null}</View>) : <Text style={styles.body}>{t('help.noReports')}</Text>}
      </Panel>
    </View>
  </AppShell>;
}

const styles = StyleSheet.create({
  stack: { gap: 18 }, panel: { gap: 14 }, heading: { color: colors.ink, fontSize: 20, fontWeight: '900' },
  body: { color: colors.muted, fontSize: 14, lineHeight: 21 }, label: { color: colors.ink, fontSize: 13, fontWeight: '700', marginBottom: 5 },
  description: { minHeight: 120, textAlignVertical: 'top' }, link: { color: colors.primary, fontWeight: '800', textDecorationLine: 'underline' },
  upload: { gap: 8 }, imageSelected: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 12 },
  ticket: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 12, gap: 4 }, ticketTitle: { color: colors.ink, fontWeight: '800' },
  response: { color: colors.ink, backgroundColor: colors.surfaceSoft, padding: 10, borderRadius: 8 }, confirmation: { color: colors.success, fontWeight: '900' },
});
