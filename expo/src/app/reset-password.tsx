import * as Linking from 'expo-linking';
import { router } from 'expo-router';
import Head from 'expo-router/head';
import { useEffect, useState } from 'react';
import { Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ActionFeedback, Button, Field, LoadingState, Panel } from '@/components/ui';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { parsePasswordRecoveryLink } from '@/lib/password-recovery-link';
import { supabase } from '@/lib/supabase';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

export default function ResetPasswordScreen() {
  const { t } = useAppPreferences();
  const { configured, loading, user, recoverySession, updatePassword } = useAuth();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [linkPending, setLinkPending] = useState(Platform.OS !== 'web');
  const [linkError, setLinkError] = useState('');
  const [nativeRecoverySession, setNativeRecoverySession] = useState(false);
  const [message, setMessage] = useState('');
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    if (Platform.OS === 'web') return;
    let active = true;
    const handle = async (url: string | null) => {
      if (!active) return;
      const result = parsePasswordRecoveryLink(url || '');
      if (result.kind === 'error') setLinkError(t('auth.resetInvalid'));
      else if (result.kind === 'session') {
        if (!supabase) setLinkError(t('auth.resetInvalid'));
        else {
          const { error } = await supabase.auth.setSession({ access_token: result.accessToken, refresh_token: result.refreshToken });
          if (active && error) setLinkError(t('auth.resetInvalid'));
          else if (active) setNativeRecoverySession(true);
        }
      }
      if (active) setLinkPending(false);
    };
    void Linking.getInitialURL().then(handle).catch(() => { if (active) { setLinkError(t('auth.resetInvalid')); setLinkPending(false); } });
    const subscription = Linking.addEventListener('url', ({ url }) => { void handle(url); });
    return () => { active = false; subscription.remove(); };
  }, [t]);

  const save = async () => {
    if (password.length < 8) return setMessage(t('auth.resetLength'));
    if (password !== confirm) return setMessage(t('auth.resetMismatch'));
    setBusy(true); setMessage('');
    const error = await updatePassword(password);
    setBusy(false);
    if (error) setMessage(error);
    else { setCompleted(true); setPassword(''); setConfirm(''); }
  };

  return <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled"><SafeAreaView style={styles.safe}>
    <Head><title>{t('auth.resetTitle')} | Classio</title></Head>
    <View style={styles.topbar}><Text style={styles.brand}>Classio</Text><PreferenceSwitcher /></View>
    <Panel style={styles.card}>
      <Text style={styles.title}>{t('auth.resetTitle')}</Text>
      {completed ? <><Text style={styles.body}>{t('auth.resetDone')}</Text><Button onPress={() => router.replace('/sign-in')}>{t('auth.backToSignIn')}</Button></>
        : loading || linkPending ? <LoadingState />
        : !configured || linkError || !user || !(recoverySession || nativeRecoverySession) ? <><Text style={styles.body}>{linkError || t('auth.resetInvalid')}</Text><Button onPress={() => router.replace('/sign-in')}>{t('auth.backToSignIn')}</Button></>
        : <>
          <Text style={styles.body}>{t('auth.resetNewIntro')}</Text>
          <Text style={styles.label}>{t('auth.newPassword')}</Text>
          <Field accessibilityLabel={t('auth.newPassword')} autoCapitalize="none" autoComplete="new-password" secureTextEntry value={password} onChangeText={setPassword} />
          <Text style={styles.label}>{t('auth.confirmPassword')}</Text>
          <Field accessibilityLabel={t('auth.confirmPassword')} autoCapitalize="none" autoComplete="new-password" secureTextEntry value={confirm} onChangeText={setConfirm} />
          <Button disabled={busy || !password || !confirm} onPress={() => void save()}>{busy ? t('auth.wait') : t('auth.saveNewPassword')}</Button>
          <ActionFeedback message={message} tone="error" onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} />
        </>}
    </Panel>
  </SafeAreaView></ScrollView>;
}

const styles = StyleSheet.create({
  page: { flexGrow: 1, backgroundColor: 'transparent' }, safe: { flex: 1, width: '100%', maxWidth: 640, alignSelf: 'center', paddingHorizontal: 24 },
  topbar: { minHeight: 82, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, brand: { color: colors.primary, fontSize: 25, fontWeight: '900' },
  card: { gap: 14, marginTop: 72, padding: 28 }, title: { color: colors.ink, fontSize: 26, fontWeight: '900' }, body: { color: colors.muted, fontSize: 14, lineHeight: 22 },
  label: { color: colors.ink, fontSize: 12, fontWeight: '800' },
});
