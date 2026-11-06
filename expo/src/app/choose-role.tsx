import { Redirect, router } from 'expo-router';
import Head from 'expo-router/head';
import { useRef, useState } from 'react';
import { Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionFeedback, Button, LoadingState, Panel } from '@/components/ui';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { requiresRoleSelection } from '@/lib/route-access';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { chooseInitialWorkspaceRole } from '@/services/profile';
import { colors } from '@/theme';
import { legalAgreementUrl, privacyNoticeUrl } from '@/lib/privacy-notices';
import { LEGAL_PUBLICATION } from '@/lib/legal-publication.generated';

export default function ChooseRoleScreen() {
  const { configured, loading, user, profile, error: authError, refreshProfile, signOut } = useAuth();
  const { t, language } = useAppPreferences();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [termsChecked, setTermsChecked] = useState(false);
  const [teacherChecked, setTeacherChecked] = useState(false);
  const [selectedMode, setSelectedMode] = useState<'teacher' | 'student' | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const selectMode = (mode: 'teacher' | 'student') => {
    if (busy) return;
    setSelectedMode(mode);
    setTermsChecked(false);
    setTeacherChecked(false);
    setError('');
  };

  const choose = async (mode: 'teacher' | 'student') => {
    if (busy || selectedMode !== mode) return;
    if (!termsChecked || (mode === 'teacher' && !teacherChecked)) { setError(t('legal.acceptRequired')); return; }
    setBusy(true); setError('');
    try {
      await chooseInitialWorkspaceRole(mode, language);
      await refreshProfile();
      router.replace(mode === 'student' ? '/student-home' : '/dashboard');
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : '';
      setError(message === 'legal.acceptRequired' ? t(message) : message || t('auth.chooseRoleFailed'));
    } finally {
      setBusy(false);
    }
  };

  const leave = async () => {
    if (busy) return;
    setBusy(true); setError('');
    try { await signOut(); router.replace('/sign-in'); }
    catch (reason) { setError(reason instanceof Error ? reason.message : t('account.signOutFailed')); }
    finally { setBusy(false); }
  };

  if (loading) return <LoadingState />;
  if (!configured || !user) return <Redirect href="/sign-in" />;
  if (authError) return <View style={styles.errorWrap}><ActionFeedback message={authError} tone="error" /></View>;
  if (!requiresRoleSelection(profile)) return <Redirect href="/home" />;

  return <ScrollView ref={scrollRef} contentContainerStyle={styles.page}>
    <SafeAreaView style={styles.safe}>
      <Head><title>{t('auth.chooseRoleTitle')} | Classio</title></Head>
      <View style={styles.topbar}><Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.logo} /><PreferenceSwitcher onLanguageChange={() => { setTermsChecked(false); setTeacherChecked(false); setError(''); }} /></View>
      <View style={styles.intro}><Text style={styles.eyebrow}>{t('auth.chooseRoleTitle')}</Text><Text style={styles.title}>{t('auth.chooseRoleHeading')}</Text><Text style={styles.subtitle}>{t('auth.chooseRoleSubtitle')}</Text></View>
      <View style={styles.cards}>
        <Pressable accessibilityRole="button" accessibilityLabel={t('auth.teacherRole')} accessibilityState={{ selected: selectedMode === 'teacher' }} disabled={busy} onPress={() => selectMode('teacher')} style={({ pressed }) => [styles.card, styles.teacherCard, selectedMode === 'teacher' && styles.selectedCard, (pressed || busy) && styles.pressed]}>
          <Text style={styles.icon}>👩‍🏫</Text><Text style={styles.cardTitle}>{t('auth.teacherRole')}</Text><Text style={styles.cardBody}>{t('auth.teacherRoleBody')}</Text><Text style={styles.teacherAction}>{t('auth.selectRole')} →</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={t('auth.studentRole')} accessibilityState={{ selected: selectedMode === 'student' }} disabled={busy} onPress={() => selectMode('student')} style={({ pressed }) => [styles.card, styles.studentCard, selectedMode === 'student' && styles.selectedCard, (pressed || busy) && styles.pressed]}>
          <Text style={styles.icon}>🎓</Text><Text style={styles.cardTitle}>{t('auth.studentRole')}</Text><Text style={styles.cardBody}>{t('auth.studentRoleBody')}</Text><Text style={styles.studentAction}>{t('auth.selectRole')} →</Text>
        </Pressable>
      </View>
      {selectedMode ? <View onLayout={() => scrollRef.current?.scrollToEnd({ animated: true })}><Panel style={styles.legalPanel}>
        <Text accessibilityRole="header" style={styles.legalHeading}>{t(selectedMode === 'teacher' ? 'legal.educatorHeading' : 'legal.studentHeading')}</Text>
        <Text style={styles.legalIntro}>{t(selectedMode === 'teacher' ? 'legal.educatorIntro' : 'legal.studentIntro')}</Text>
        <Text style={styles.legalVersion}>{t('legal.version')}: {LEGAL_PUBLICATION.version}</Text>
        <View style={styles.legalLinks}>
          <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(legalAgreementUrl(language, 'terms'))}><Text style={styles.legalLink}>{t('legal.terms')} ↗</Text></Pressable>
          {selectedMode === 'teacher' ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(legalAgreementUrl(language, 'teacher-data'))}><Text style={styles.legalLink}>{t('legal.teacherData')} ↗</Text></Pressable> : null}
          <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacyNoticeUrl(language, selectedMode === 'student' ? 'students' : 'app'))}><Text style={styles.legalLink}>{t(selectedMode === 'student' ? 'legal.studentNotice' : 'legal.privacyNotice')} ↗</Text></Pressable>
        </View>
        <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: termsChecked }} onPress={() => setTermsChecked((value) => !value)} style={styles.legalCheck}><Text style={styles.legalCheckIcon}>{termsChecked ? '☑' : '□'}</Text><Text style={styles.legalCheckText}>{t('legal.acceptTerms')}</Text></Pressable>
        {selectedMode === 'teacher' ? <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: teacherChecked }} onPress={() => setTeacherChecked((value) => !value)} style={styles.legalCheck}><Text style={styles.legalCheckIcon}>{teacherChecked ? '☑' : '□'}</Text><Text style={styles.legalCheckText}>{t('legal.acceptTeacherData')}</Text></Pressable> : null}
        <Button disabled={busy || !termsChecked || (selectedMode === 'teacher' && !teacherChecked)} onPress={() => void choose(selectedMode)}>{busy ? t('auth.wait') : t('legal.acceptContinue')}</Button>
      </Panel></View> : null}
      {busy ? <Text style={styles.busy}>{t('auth.wait')}</Text> : null}
      {error ? <Panel style={styles.feedback}><ActionFeedback message={error} onDismiss={(shown) => setError((current) => current === shown ? '' : current)} tone="error" /></Panel> : null}
      <Text style={styles.hint}>{t('auth.chooseRoleHint')}</Text>
      <View style={styles.signOut}><Button secondary disabled={busy} onPress={() => void leave()}>{t('account.signOut')}</Button></View>
    </SafeAreaView>
  </ScrollView>;
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, minHeight: '100%', paddingHorizontal: 24, backgroundColor: 'transparent' },
  safe: { width: '100%', maxWidth: 900, alignSelf: 'center', paddingBottom: 48 },
  topbar: { minHeight: 86, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 16 },
  logo: { width: 150, height: 52 },
  intro: { alignItems: 'center', marginTop: 42, gap: 12 },
  eyebrow: { color: colors.primary, fontSize: 11, fontWeight: '900', letterSpacing: 1.4, textTransform: 'uppercase' },
  title: { color: colors.ink, fontSize: 36, lineHeight: 42, fontWeight: '900', textAlign: 'center' },
  subtitle: { color: colors.muted, fontSize: 15, lineHeight: 23, textAlign: 'center', maxWidth: 620 },
  cards: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 18, marginTop: 36 },
  card: { flexGrow: 1, flexBasis: 300, maxWidth: 390, minHeight: 250, borderRadius: 24, borderWidth: 1, padding: 28, alignItems: 'center', justifyContent: 'center', gap: 12, backgroundColor: colors.surface, shadowColor: colors.shadow, shadowOpacity: 0.08, shadowRadius: 18, shadowOffset: { width: 0, height: 9 } },
  teacherCard: { borderColor: colors.primary },
  studentCard: { borderColor: colors.success },
  pressed: { opacity: 0.65 }, selectedCard: { borderWidth: 3 },
  icon: { fontSize: 36 },
  cardTitle: { color: colors.ink, fontSize: 22, fontWeight: '900' },
  cardBody: { color: colors.muted, fontSize: 14, lineHeight: 21, textAlign: 'center', maxWidth: 290 },
  teacherAction: { color: colors.primary, fontSize: 13, fontWeight: '900', marginTop: 7 },
  studentAction: { color: colors.success, fontSize: 13, fontWeight: '900', marginTop: 7 },
  hint: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 28 },
  busy: { color: colors.primary, textAlign: 'center', marginTop: 16 },
  feedback: { marginTop: 20 },
  legalPanel: { marginTop: 26, padding: 18, gap: 10 }, legalHeading: { color: colors.ink, fontSize: 19, fontWeight: '800' }, legalIntro: { color: colors.muted, fontSize: 14, lineHeight: 21 }, legalVersion: { color: colors.subtle, fontSize: 12 }, legalLinks: { flexDirection: 'row', flexWrap: 'wrap', gap: 16 }, legalLink: { color: colors.primary, fontWeight: '800', paddingVertical: 6 }, legalCheck: { flexDirection: 'row', gap: 10, paddingVertical: 6, alignItems: 'flex-start' }, legalCheckIcon: { color: colors.primary, fontSize: 22, lineHeight: 24 }, legalCheckText: { flex: 1, color: colors.ink, fontSize: 13, lineHeight: 20 }, signOut: { alignItems: 'center', marginTop: 18 },
  errorWrap: { margin: 24 },
});
