import { Redirect, router } from 'expo-router';
import Head from 'expo-router/head';
import { useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionFeedback, Button, LoadingState, Panel } from '@/components/ui';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { hasCurrentLegalAcceptance, legalModeForProfile } from '@/lib/legal-acceptance';
import { LEGAL_PUBLICATION } from '@/lib/legal-publication.generated';
import { legalAgreementUrl, privacyNoticeUrl } from '@/lib/privacy-notices';
import { requiresRoleSelection } from '@/lib/route-access';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { acceptCurrentLegalDocuments } from '@/services/legal-acceptance';
import { colors } from '@/theme';

export default function AcceptTermsScreen() {
  const { configured, loading, user, profile, legalAcceptances, refreshProfile } = useAuth();
  const { t, language } = useAppPreferences();
  const [termsChecked, setTermsChecked] = useState(false);
  const [teacherChecked, setTeacherChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (loading) return <LoadingState />;
  if (!configured || !user) return <Redirect href="/sign-in" />;
  if (requiresRoleSelection(profile)) return <Redirect href="/choose-role" />;
  if (hasCurrentLegalAcceptance(profile, legalAcceptances)) return <Redirect href="/home" />;
  const mode = legalModeForProfile(profile);
  const accept = async () => {
    if (!termsChecked || (mode === 'teacher' && !teacherChecked) || busy) return;
    setBusy(true); setError('');
    try {
      await acceptCurrentLegalDocuments(mode, language);
      await refreshProfile();
      router.replace('/home');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('legal.acceptFailed'));
    } finally { setBusy(false); }
  };
  return <ScrollView contentContainerStyle={styles.page}><SafeAreaView style={styles.safe}>
    <Head><title>{t('legal.acceptTitle')} | Classio</title></Head>
    <View style={styles.top}><Text style={styles.brand}>Master Classio</Text><PreferenceSwitcher /></View>
    <Panel style={styles.panel}><Text accessibilityRole="header" style={styles.title}>{t('legal.acceptTitle')}</Text>
      <Text style={styles.body}>{t('legal.acceptIntro')}</Text>
      <Text style={styles.version}>{t('legal.version')}: {LEGAL_PUBLICATION.version}</Text>
      <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(legalAgreementUrl(language, 'terms'))}><Text style={styles.link}>{t('legal.terms')} ↗</Text></Pressable>
      {mode === 'teacher' ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(legalAgreementUrl(language, 'teacher-data'))}><Text style={styles.link}>{t('legal.teacherData')} ↗</Text></Pressable> : null}
      <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacyNoticeUrl(language, 'app'))}><Text style={styles.link}>{t('legal.privacyNotice')} ↗</Text></Pressable>
      <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: termsChecked }} onPress={() => setTermsChecked((value) => !value)} style={styles.checkRow}><Text style={styles.check}>{termsChecked ? '☑' : '□'}</Text><Text style={styles.checkLabel}>{t('legal.acceptTerms')}</Text></Pressable>
      {mode === 'teacher' ? <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: teacherChecked }} onPress={() => setTeacherChecked((value) => !value)} style={styles.checkRow}><Text style={styles.check}>{teacherChecked ? '☑' : '□'}</Text><Text style={styles.checkLabel}>{t('legal.acceptTeacherData')}</Text></Pressable> : null}
      <Button disabled={busy || !termsChecked || (mode === 'teacher' && !teacherChecked)} onPress={() => void accept()}>{busy ? t('auth.wait') : t('legal.acceptContinue')}</Button>
      <ActionFeedback message={error} tone="error" onDismiss={(shown) => setError((current) => current === shown ? '' : current)} />
    </Panel>
  </SafeAreaView></ScrollView>;
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, minHeight: '100%', paddingHorizontal: 20 }, safe: { maxWidth: 720, width: '100%', alignSelf: 'center', paddingBottom: 40 },
  top: { minHeight: 90, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 }, brand: { color: colors.primary, fontSize: 22, fontWeight: '900' },
  panel: { gap: 15, padding: 28 }, title: { color: colors.ink, fontSize: 27, fontWeight: '900' }, body: { color: colors.muted, fontSize: 14, lineHeight: 22 },
  version: { color: colors.subtle, fontSize: 12 }, link: { color: colors.primary, fontSize: 14, fontWeight: '800', paddingVertical: 4 },
  checkRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 8 }, check: { color: colors.primary, fontSize: 24, lineHeight: 25 }, checkLabel: { flex: 1, color: colors.ink, fontSize: 14, lineHeight: 22 },
});
