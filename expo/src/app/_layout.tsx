import { Stack, usePathname } from 'expo-router';
import { useLayoutEffect } from 'react';
import { Platform } from 'react-native';
import Head from 'expo-router/head';
import { StatusBar } from 'expo-status-bar';

import { AuthProvider, useAuth } from '@/providers/auth-provider';
import { AppPreferencesProvider, useAppPreferences } from '@/providers/app-preferences';
import { PrivilegedAccessProvider } from '@/providers/privileged-access-provider';
import { LiveBackground } from '@/components/live-background';
import { IntroConstellation } from '@/components/intro-constellation';
import { publicCopy } from '@/lib/public-copy';
import { HomeIntroProvider, useHomeIntro } from '@/providers/home-intro-provider';
import { introOverlayCss } from '@/theme';

function AppFrame() {
  const { resolvedTheme, language } = useAppPreferences();
  const { user, loading } = useAuth();
  const homeIntro = useHomeIntro();
  const pathname = usePathname();
  const enteringHome = pathname === '/home' || pathname === '/dashboard' || pathname === '/student-home';
  const showHomeIntro = enteringHome || (pathname === '/sign-in' && homeIntro.requested);
  useLayoutEffect(() => {
    if (Platform.OS === 'web' && !showHomeIntro && pathname !== '/' && !loading) document.getElementById('classio-boot-overlay')?.remove();
  }, [loading, pathname, showHomeIntro]);
  return <>
    <Head><style>{introOverlayCss}</style></Head>
    <LiveBackground />
    <Stack screenOptions={{ headerShown: false, title: 'Classio', contentStyle: { backgroundColor: 'transparent' } }} />
    {showHomeIntro ? <IntroConstellation sessionKey="classio-home-intro-seen-v2" ready={!loading && !!user && homeIntro.readyRoute === pathname} tagline={publicCopy(language).introTagline} theme={resolvedTheme} /> : null}
    <StatusBar style={resolvedTheme === 'dark' ? 'light' : 'dark'} />
  </>;
}

export default function RootLayout() {
  return (
    <AppPreferencesProvider><AuthProvider><PrivilegedAccessProvider><HomeIntroProvider><AppFrame /></HomeIntroProvider></PrivilegedAccessProvider></AuthProvider></AppPreferencesProvider>
  );
}
