import { Redirect, router } from 'expo-router';
import Head from 'expo-router/head';
import { useCallback, useEffect, useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Field, Panel } from '@/components/ui';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { GoogleSignIn } from '@/components/google-sign-in';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

export default function SignInScreen() {
  const { width } = useWindowDimensions();
  const [webWidth, setWebWidth] = useState<number | null>(null);
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const update = () => setWebWidth(window.innerWidth);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);
  const compact = (Platform.OS === 'web' ? webWidth ?? width : width) < 850;
  const { t } = useAppPreferences();
  const { configured, loading, user, signIn, signInWithMagicLink, signInWithGoogle, signInWithGoogleIdToken, signUp } = useAuth();
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true); setMessage(null);
    const error = mode === 'sign-in' ? await signIn(email, password) : await signUp(email, password);
    setSubmitting(false);
    if (error) setMessage(error);
    else if (mode === 'sign-up') setMessage(t('auth.confirmEmail'));
    else router.replace('/home');
  };

  const sendMagicLink = async () => {
    setSubmitting(true); setMessage(null);
    const error = await signInWithMagicLink(email);
    setSubmitting(false);
    setMessage(error || t('auth.magicSent'));
  };

  const openGoogle = async () => {
    setSubmitting(true); setMessage(null);
    const error = await signInWithGoogle();
    if (error) setMessage(error);
    setSubmitting(false);
  };

  const acceptGoogleCredential = useCallback(async (token: string, nonce: string) => {
    setSubmitting(true); setMessage(null);
    const error = await signInWithGoogleIdToken(token, nonce);
    setSubmitting(false);
    if (error) setMessage(error);
    else router.replace('/home');
  }, [signInWithGoogleIdToken]);

  if (!loading && user) return <Redirect href="/home" />;

  return <ScrollView contentContainerStyle={[styles.page, { backgroundColor: 'transparent' }]} keyboardShouldPersistTaps="handled">
    <SafeAreaView style={styles.safe}>
      <Head><title>{mode === 'sign-in' ? t('auth.signIn') : t('auth.createAccount')} | Classio</title></Head>
      <View style={styles.topbar}><Pressable onPress={() => router.push('/')}><Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.logo} /></Pressable><View style={styles.topbarActions}><PreferenceSwitcher /><Pressable onPress={() => router.push('/')} style={styles.back}><Text style={styles.backText}>← {t('auth.explore')}</Text></Pressable></View></View>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[styles.layout, compact && styles.layoutCompact]}>
        {!compact ? <View style={styles.story}>
          <Text style={styles.storyEyebrow}>{t('auth.eyebrow')}</Text><Text style={styles.storyTitle}>{t('auth.storyTitle')}</Text><Text style={styles.storyBody}>{t('auth.storyBody')}</Text>
          <View style={styles.promiseList}>{[['01', t('auth.nextTitle'), t('auth.nextBody')], ['02', t('auth.contextTitle'), t('auth.contextBody')], ['03', t('auth.adminTitle'), t('auth.adminBody')]].map(([number, title, body]) => <View key={number} style={styles.promise}><Text style={styles.promiseNumber}>{number}</Text><View style={styles.promiseCopy}><Text style={styles.promiseTitle}>{title}</Text><Text style={styles.promiseBody}>{body}</Text></View></View>)}</View>
        </View> : null}
        <Panel style={[styles.card, compact && styles.cardCompact]}>
          <View style={styles.modeTabs}><Pressable onPress={() => { setMode('sign-in'); setMessage(null); }} style={[styles.modeTab, mode === 'sign-in' && styles.modeActive]}><Text style={[styles.modeText, mode === 'sign-in' && styles.modeTextActive]}>{t('auth.signIn')}</Text></Pressable><Pressable onPress={() => { setMode('sign-up'); setMessage(null); }} style={[styles.modeTab, mode === 'sign-up' && styles.modeActive]}><Text style={[styles.modeText, mode === 'sign-up' && styles.modeTextActive]}>{t('auth.createAccount')}</Text></Pressable></View>
          <Text style={styles.title}>{mode === 'sign-in' ? t('auth.welcome') : t('auth.start')}</Text><Text style={styles.intro}>{mode === 'sign-in' ? t('auth.signInIntro') : t('auth.signUpIntro')}</Text>
          {!configured ? <View style={styles.configNotice}><Text style={styles.noticeTitle}>Deployment configuration required</Text><Text style={styles.noticeBody}>This environment needs the Supabase URL and public publishable key.</Text></View> : <>
            <View style={styles.fieldGroup}><Text style={styles.label}>{t('auth.email')}</Text><Field accessibilityLabel={t('auth.email')} autoCapitalize="none" autoComplete="email" keyboardType="email-address" placeholder="you@example.com" value={email} onChangeText={setEmail} /></View>
            <View style={styles.fieldGroup}><Text style={styles.label}>{t('auth.password')}</Text><Field accessibilityLabel={t('auth.password')} autoCapitalize="none" autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'} placeholder={mode === 'sign-in' ? t('auth.passwordPlaceholder') : t('auth.newPasswordPlaceholder')} secureTextEntry value={password} onChangeText={setPassword} /></View>
            {message ? <View style={styles.messageBox}><Text style={styles.message}>{message}</Text></View> : null}
            <Button disabled={submitting || !email || !password} onPress={() => void submit()}>{submitting ? t('auth.wait') : mode === 'sign-in' ? t('auth.signInButton') : t('auth.createButton')}</Button>
            {mode === 'sign-in' ? <><View style={styles.or}><View style={styles.orLine} /><Text style={styles.orText}>{t('auth.passwordless')}</Text><View style={styles.orLine} /></View><Button disabled={submitting || !email} secondary onPress={() => void sendMagicLink()}>{t('auth.magicLink')}</Button></> : null}
            <GoogleSignIn disabled={submitting} label={t('auth.googleButton')} onPress={() => void openGoogle()} onCredential={acceptGoogleCredential} onError={setMessage} />
            <Text style={styles.googleBody}>{t('auth.googleHint')}</Text>
          </>}
          <Text style={styles.security}>{t('auth.security')}</Text>
        </Panel>
      </KeyboardAvoidingView>
    </SafeAreaView>
  </ScrollView>;
}

const styles = StyleSheet.create({
  page: { minHeight: '100%', backgroundColor: colors.canvas }, safe: { width: '100%', maxWidth: 1160, alignSelf: 'center', paddingHorizontal: 24, paddingBottom: 38 }, topbar: { minHeight: 76, flexDirection: 'row', flexWrap: 'wrap', gap: 10, alignItems: 'center', justifyContent: 'space-between' }, topbarActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }, logo: { width: 148, height: 52 }, back: { paddingVertical: 10 }, backText: { color: colors.muted, fontSize: 13, fontWeight: '700' },
  layout: { width: '100%', flexDirection: 'row', alignItems: 'center', gap: 70, minHeight: 650, paddingVertical: 36 }, layoutCompact: { flexDirection: 'column', alignItems: 'stretch', gap: 28, paddingTop: 24 }, story: { flex: 1, minWidth: 0 }, storyEyebrow: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1.3, marginBottom: 14 }, storyTitle: { color: colors.ink, fontSize: 48, lineHeight: 54, fontWeight: '900', letterSpacing: -1.7 }, storyBody: { color: colors.muted, fontSize: 17, lineHeight: 27, marginTop: 18, maxWidth: 570 }, promiseList: { marginTop: 34, gap: 18 }, promise: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' }, promiseNumber: { width: 34, height: 34, borderRadius: 17, textAlign: 'center', lineHeight: 34, backgroundColor: colors.primarySoft, color: colors.primary, fontSize: 10, fontWeight: '900' }, promiseCopy: { flex: 1 }, promiseTitle: { color: colors.ink, fontSize: 14, fontWeight: '800' }, promiseBody: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 3 },
  card: { flexGrow: 0, flexShrink: 0, maxWidth: 480, width: '100%', gap: 13, padding: 30, borderRadius: 24, shadowColor: colors.ink, shadowOpacity: 0.08, shadowRadius: 24, shadowOffset: { width: 0, height: 12 } }, cardCompact: { alignSelf: 'center' }, modeTabs: { flexDirection: 'row', backgroundColor: colors.surfaceSoft, borderRadius: 12, padding: 4, marginBottom: 8 }, modeTab: { flex: 1, borderRadius: 9, paddingVertical: 10, alignItems: 'center' }, modeActive: { backgroundColor: colors.surface }, modeText: { color: colors.muted, fontSize: 12, fontWeight: '800' }, modeTextActive: { color: colors.ink }, title: { color: colors.ink, fontSize: 28, fontWeight: '900', textAlign: 'center' }, intro: { color: colors.muted, fontSize: 14, lineHeight: 21, textAlign: 'center', marginBottom: 4 }, fieldGroup: { gap: 6 }, label: { color: colors.ink, fontSize: 11, fontWeight: '800' }, messageBox: { backgroundColor: colors.warningSoft, borderRadius: 10, padding: 11 }, message: { color: colors.warning, fontSize: 12, lineHeight: 18 }, configNotice: { backgroundColor: colors.warningSoft, borderRadius: 12, padding: 15 }, noticeTitle: { color: colors.warning, fontWeight: '800', marginBottom: 5 }, noticeBody: { color: colors.warning, lineHeight: 20 },
  or: { flexDirection: 'row', alignItems: 'center', gap: 9, marginVertical: 2 }, orLine: { height: 1, backgroundColor: colors.line, flex: 1 }, orText: { color: colors.subtle, fontSize: 8, fontWeight: '900', letterSpacing: 0.6 }, googleNotice: { flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: colors.canvas, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.line }, googleIcon: { width: 28, height: 28, borderRadius: 14, textAlign: 'center', lineHeight: 28, color: '#4285F4', backgroundColor: colors.surface, fontWeight: '900' }, googleTitle: { color: colors.ink, fontSize: 11, fontWeight: '800' }, googleBody: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 2 }, security: { color: colors.subtle, fontSize: 10, lineHeight: 15, textAlign: 'center', marginTop: 2 },
});
