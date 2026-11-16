import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Field, Panel } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import type { ClassioRecord } from '@/services/classio-data';
import { getMyTeacherPublicProfile, saveMyTeacherPublicProfile, type TeacherPublicProfile } from '@/services/teacher-public-profile';
import { privacyNoticeUrl } from '@/lib/privacy-notices';
import { colors } from '@/theme';

function values(value: unknown): string[] { return Array.isArray(value) ? value.map(String).filter(Boolean) : []; }
function contactEmail(value: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()); }
function contactPhone(value: string) { return /^\+?\d{6,15}$/.test(value.trim()); }
function readable(value: string) { return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function Toggle({ checked, label, onPress }: { checked: boolean; label: string; onPress: () => void }) {
  return <Pressable accessibilityRole="checkbox" accessibilityState={{ checked }} onPress={onPress} style={styles.toggle}>
    <Text style={styles.check}>{checked ? '☑' : '☐'}</Text><Text style={styles.toggleText}>{label}</Text>
  </Pressable>;
}

export function TeacherPublicProfileEditor({ account, communityVisible }: { account: ClassioRecord; communityVisible: boolean }) {
  const { t, language } = useAppPreferences();
  const [card, setCard] = useState<TeacherPublicProfile | null>(null);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [message, setMessage] = useState('');
  const [tone, setTone] = useState<'error' | 'success'>('success');
  const [publicId, setPublicId] = useState('');
  useEffect(() => {
    let active = true;
    void getMyTeacherPublicProfile().then((saved) => {
      if (!active) return;
      setCard(saved || {
        professional_name: String(account.display_name || account.username || ''), headline: '', biography: '',
        subjects: [...new Set([...values(account.primary_subjects).filter((value) => value !== 'other'), ...values(account.custom_subjects)])],
        teaching_stages: values(account.teaching_stages), teaching_languages: values(account.teaching_languages),
        modalities: ['online'], country: String(account.country || ''), city: '', education: String(account.education_level || ''),
        avatar_url: String(account.avatar_url || ''), contact_email: String(account.email || ''), contact_phone: String(account.phone_number || ''),
        show_community_email: Boolean(account.show_community_contact && account.email), show_community_phone: false, show_web_email: false, show_web_phone: false, published_web: false,
      });
      setPublicId(saved?.public_id || '');
      setReady(true);
    }).catch(() => { if (active) { setMessage(t('education.loadFailed')); setTone('error'); setReady(true); } });
    return () => { active = false; };
  }, [account, t]);
  const change = <K extends keyof TeacherPublicProfile>(key: K, value: TeacherPublicProfile[K]) => setCard((current) => current ? { ...current, [key]: value } : current);
  const choices = (key: 'subjects' | 'teaching_stages' | 'teaching_languages', available: string[]) => {
    if (!card) return null;
    return <View style={styles.choices}>{[...new Set([...available, ...card[key]])].map((value) => <Toggle key={value} checked={card[key].includes(value)} label={readable(value)} onPress={() => change(key, card[key].includes(value) ? card[key].filter((item) => item !== value) : [...card[key], value])} />)}</View>;
  };
  const save = async () => {
    if (!card) return;
    if (card.professional_name.trim().length < 2) { setTone('error'); setMessage(t('education.nameRequired')); return; }
    if (((card.show_web_email || card.show_community_email) && !contactEmail(card.contact_email)) ||
        ((card.show_web_phone || card.show_community_phone) && !contactPhone(card.contact_phone))) {
      setTone('error'); setMessage(t('education.contactRequired')); return;
    }
    if (card.published_web && !communityVisible) { setTone('error'); setMessage(t('education.communityFirst')); return; }
    if (card.published_web && (!card.subjects.length || !card.teaching_stages.length)) { setTone('error'); setMessage(t('education.scopeRequired')); return; }
    if (card.published_web && !acknowledged) { setTone('error'); setMessage(t('education.notice')); return; }
    setSaving(true); setMessage('');
    try {
      const id = await saveMyTeacherPublicProfile(card);
      setPublicId(id); setAcknowledged(false); setTone('success'); setMessage(t('education.saved'));
    } catch (reason) {
      setTone('error'); setMessage(reason instanceof Error ? reason.message : t('education.saveFailed'));
    } finally { setSaving(false); }
  };
  return <Panel style={styles.panel}>
    <Text accessibilityRole="header" style={styles.title}>{t('education.title')}</Text>
    <Text style={styles.help}>{t('education.intro')}</Text>
    {!ready || !card ? <Text style={styles.help}>{t('common.loading')}</Text> : <>
      <Text style={styles.label}>{t('education.name')}</Text><Field value={card.professional_name} maxLength={100} onChangeText={(value) => change('professional_name', value)} />
      <Text style={styles.label}>{t('education.headline')}</Text><Field value={card.headline} maxLength={160} onChangeText={(value) => change('headline', value)} />
      <Text style={styles.label}>{t('education.bio')}</Text><Field value={card.biography} multiline numberOfLines={5} maxLength={1500} onChangeText={(value) => change('biography', value)} />
      <Text style={styles.help}>{t('education.subjectsHelp')}</Text>
      <Text style={styles.label}>{t('education.subjects')}</Text>{choices('subjects', [...values(account.primary_subjects).filter((value) => value !== 'other'), ...values(account.custom_subjects)])}
      <Text style={styles.label}>{t('education.stages')}</Text>{choices('teaching_stages', values(account.teaching_stages))}
      <Text style={styles.label}>{t('education.languages')}</Text>{choices('teaching_languages', values(account.teaching_languages))}
      <View style={styles.fields}><View style={styles.field}><Text style={styles.label}>{t('education.city')}</Text><Field value={card.city} maxLength={80} onChangeText={(value) => change('city', value)} /></View><View style={styles.field}><Text style={styles.label}>{t('education.country')}</Text><Field value={card.country} maxLength={80} onChangeText={(value) => change('country', value)} /></View></View>
      <Text style={styles.label}>{t('education.email')}</Text><Field value={card.contact_email} autoCapitalize="none" keyboardType="email-address" maxLength={254} onChangeText={(value) => change('contact_email', value)} />
      <Text style={styles.label}>{t('education.phone')}</Text><Field value={card.contact_phone} keyboardType="phone-pad" placeholder="+905551234567" maxLength={16} onChangeText={(value) => change('contact_phone', value.replace(/(?!^)\+/g, '').replace(/[^\d+]/g, ''))} />
      <Toggle checked={card.modalities.includes('online')} label={t('education.online')} onPress={() => change('modalities', card.modalities.includes('online') ? card.modalities.filter((value) => value !== 'online') : [...card.modalities, 'online'])} />
      <Toggle checked={card.modalities.includes('in_person')} label={t('education.inPerson')} onPress={() => change('modalities', card.modalities.includes('in_person') ? card.modalities.filter((value) => value !== 'in_person') : [...card.modalities, 'in_person'])} />
      <View style={styles.rule} />
      <Toggle checked={card.show_community_email} label={t('education.communityEmail')} onPress={() => change('show_community_email', !card.show_community_email)} />
      <Toggle checked={card.show_community_phone} label={t('education.communityPhone')} onPress={() => change('show_community_phone', !card.show_community_phone)} />
      <Toggle checked={card.show_web_email} label={t('education.webEmail')} onPress={() => change('show_web_email', !card.show_web_email)} />
      <Toggle checked={card.show_web_phone} label={t('education.webPhone')} onPress={() => change('show_web_phone', !card.show_web_phone)} />
      <Text style={styles.warning}>{t('education.publicWarning')}</Text>
      <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacyNoticeUrl(language, 'app'))}><Text style={styles.link}>{t('education.readPrivacy')} ↗</Text></Pressable>
      <Toggle checked={card.published_web} label={t('education.publish')} onPress={() => { change('published_web', !card.published_web); setAcknowledged(false); }} />
      {card.published_web ? <Toggle checked={acknowledged} label={t('education.notice')} onPress={() => setAcknowledged((value) => !value)} /> : null}
      <View style={styles.preview}><Text style={styles.label}>{t('education.preview')}</Text><Text style={styles.previewName}>{card.professional_name}</Text><Text style={styles.help}>{card.headline}</Text><Text style={styles.help}>{card.biography}</Text><Text style={styles.help}>{[card.subjects.join(', '), card.city, card.country].filter(Boolean).join(' · ')}</Text>{card.show_web_email ? <Text style={styles.help}>{card.contact_email}</Text> : null}{card.show_web_phone ? <Text style={styles.help}>{card.contact_phone}</Text> : null}<Text style={styles.help}>{t('education.contactViaClassio')}</Text></View>
      <Button disabled={saving} onPress={() => void save()}>{saving ? t('common.saving') : t('education.save')}</Button>
      {publicId && card.published_web ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(`https://masterclassio.com/education/teacher/?id=${encodeURIComponent(publicId)}`)}><Text style={styles.link}>{t('education.publicId')} ↗</Text></Pressable> : null}
    </>}
    <ActionFeedback message={message} tone={tone} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} />
  </Panel>;
}

const styles = StyleSheet.create({
  panel: { gap: 8 }, title: { color: colors.ink, fontSize: 17, fontWeight: '900' }, help: { color: colors.muted, fontSize: 11, lineHeight: 18 }, label: { color: colors.ink, fontSize: 11, fontWeight: '800', marginTop: 5 },
  fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, field: { flex: 1, minWidth: 140 }, toggle: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingVertical: 6 }, check: { color: colors.primary, fontSize: 20 }, toggleText: { color: colors.ink, fontSize: 11, lineHeight: 18, flex: 1 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 }, warning: { color: colors.muted, fontSize: 11, lineHeight: 18 }, rule: { height: 1, backgroundColor: colors.line, marginVertical: 4 }, preview: { borderWidth: 1, borderColor: colors.line, borderRadius: 12, padding: 12, gap: 6 }, previewName: { color: colors.ink, fontSize: 17, fontWeight: '900' }, link: { color: colors.primary, fontSize: 11, fontWeight: '800' },
});
