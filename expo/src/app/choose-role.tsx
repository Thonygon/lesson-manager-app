import { Redirect, router } from 'expo-router';
import Head from 'expo-router/head';
import { useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionFeedback, LoadingState, Panel } from '@/components/ui';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { requiresRoleSelection } from '@/lib/route-access';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { chooseInitialWorkspaceRole } from '@/services/profile';
import { colors } from '@/theme';

export default function ChooseRoleScreen() {
  const { configured, loading, user, profile, error: authError, refreshProfile } = useAuth();
  const { t, language } = useAppPreferences();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const choose = async (mode: 'teacher' | 'student') => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      await chooseInitialWorkspaceRole(mode, language);
      await refreshProfile();
      router.replace(mode === 'student' ? '/student-home' : '/dashboard');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('auth.chooseRoleFailed'));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <LoadingState />;
  if (!configured || !user) return <Redirect href="/sign-in" />;
  if (authError) return <View style={styles.errorWrap}><ActionFeedback message={authError} tone="error" /></View>;
  if (!requiresRoleSelection(profile)) return <Redirect href="/home" />;

  return <ScrollView contentContainerStyle={styles.page}>
    <SafeAreaView style={styles.safe}>
      <Head><title>{t('auth.chooseRoleTitle')} | Classio</title></Head>
      <View style={styles.topbar}><Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.logo} /><PreferenceSwitcher /></View>
      <View style={styles.intro}><Text style={styles.eyebrow}>{t('auth.chooseRoleTitle')}</Text><Text style={styles.title}>{t('auth.chooseRoleHeading')}</Text><Text style={styles.subtitle}>{t('auth.chooseRoleSubtitle')}</Text></View>
      <View style={styles.cards}>
        <Pressable accessibilityRole="button" accessibilityLabel={t('auth.teacherRole')} disabled={busy} onPress={() => void choose('teacher')} style={({ pressed }) => [styles.card, styles.teacherCard, (pressed || busy) && styles.pressed]}>
          <Text style={styles.icon}>👩‍🏫</Text><Text style={styles.cardTitle}>{t('auth.teacherRole')}</Text><Text style={styles.cardBody}>{t('auth.teacherRoleBody')}</Text><Text style={styles.teacherAction}>{t('auth.chooseRoleContinue')} →</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={t('auth.studentRole')} disabled={busy} onPress={() => void choose('student')} style={({ pressed }) => [styles.card, styles.studentCard, (pressed || busy) && styles.pressed]}>
          <Text style={styles.icon}>🎓</Text><Text style={styles.cardTitle}>{t('auth.studentRole')}</Text><Text style={styles.cardBody}>{t('auth.studentRoleBody')}</Text><Text style={styles.studentAction}>{t('auth.chooseRoleContinue')} →</Text>
        </Pressable>
      </View>
      {busy ? <Text style={styles.busy}>{t('auth.wait')}</Text> : null}
      {error ? <Panel style={styles.feedback}><ActionFeedback message={error} tone="error" /></Panel> : null}
      <Text style={styles.hint}>{t('auth.chooseRoleHint')}</Text>
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
  pressed: { opacity: 0.65 },
  icon: { fontSize: 36 },
  cardTitle: { color: colors.ink, fontSize: 22, fontWeight: '900' },
  cardBody: { color: colors.muted, fontSize: 14, lineHeight: 21, textAlign: 'center', maxWidth: 290 },
  teacherAction: { color: colors.primary, fontSize: 13, fontWeight: '900', marginTop: 7 },
  studentAction: { color: colors.success, fontSize: 13, fontWeight: '900', marginTop: 7 },
  hint: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 28 },
  busy: { color: colors.primary, textAlign: 'center', marginTop: 16 },
  feedback: { marginTop: 20 },
  errorWrap: { margin: 24 },
});
