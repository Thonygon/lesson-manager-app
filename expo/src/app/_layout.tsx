import { router, Stack, usePathname, type Href } from 'expo-router';
import { useEffect, useLayoutEffect, useRef } from 'react';
import { Platform } from 'react-native';
import Head from 'expo-router/head';
import { StatusBar } from 'expo-status-bar';

import { AuthProvider, useAuth } from '@/providers/auth-provider';
import { privilegedDeepLinkToRestore } from '@/lib/route-access';
import { AppPreferencesProvider, useAppPreferences } from '@/providers/app-preferences';
import { PrivilegedAccessProvider, usePrivilegedAccess } from '@/providers/privileged-access-provider';
import { LiveBackground } from '@/components/live-background';
import { StorageNotice } from '@/components/storage-notice';
import { IntroConstellation } from '@/components/intro-constellation';
import { publicCopy } from '@/lib/public-copy';
import { HomeIntroProvider, useHomeIntro } from '@/providers/home-intro-provider';
import { introOverlayCss } from '@/theme';

// Capture a privileged deep link before Expo Router initializes its web stack.
// On a cold load the nested stack can briefly select another route while the
// persisted session is restored. Never use this hint to grant access.
const initialWebHref = typeof window !== 'undefined' && /^\/(?:admin(?:-[a-z-]+)?|developer-workspace)(?:\/|$)/.test(window.location.pathname)
  ? `${window.location.pathname}${window.location.search}${window.location.hash}` : '';

function AppFrame() {
  const { resolvedTheme, language } = useAppPreferences();
  const { user, profile, loading } = useAuth();
  const access = usePrivilegedAccess();
  const initialRouteRecovery = useRef<{ state: 'pending'; path: string; timer: ReturnType<typeof setTimeout> } | { state: 'done' | 'abandoned' } | null>(null);
  const homeIntro = useHomeIntro();
  const pathname = usePathname();
  const enteringHome = pathname === '/home' || pathname === '/dashboard' || pathname === '/student-home';
  const showHomeIntro = enteringHome || (pathname === '/sign-in' && homeIntro.requested);
  useEffect(() => {
    if (Platform.OS !== 'web' || !initialWebHref) return;
    const recovery = initialRouteRecovery.current;
    if (recovery?.state === 'pending' && pathname !== recovery.path) {
      clearTimeout(recovery.timer);
      initialRouteRecovery.current = { state: 'abandoned' };
      return;
    }
    if (recovery || loading || access.loading || !user || !profile) return;
    // Arm only once after access is known. Any subsequent navigation cancels
    // the restore instead of starting a fresh 500 ms window on that page.
    const pathAtSchedule = pathname;
    const timer = setTimeout(() => {
      if (initialRouteRecovery.current?.state !== 'pending') return;
      if (window.location.pathname !== pathAtSchedule) {
        initialRouteRecovery.current = { state: 'abandoned' };
        return;
      }
      initialRouteRecovery.current = { state: 'done' };
      const target = privilegedDeepLinkToRestore(initialWebHref, window.location.pathname, profile, access);
      if (target) router.replace(target as Href);
    }, 500);
    initialRouteRecovery.current = { state: 'pending', path: pathAtSchedule, timer };
  }, [access, loading, pathname, profile, user]);
  useEffect(() => () => {
    if (initialRouteRecovery.current?.state === 'pending') clearTimeout(initialRouteRecovery.current.timer);
  }, []);
  useLayoutEffect(() => {
    if (Platform.OS === 'web' && !showHomeIntro && pathname !== '/' && !loading) document.getElementById('classio-boot-overlay')?.remove();
  }, [loading, pathname, showHomeIntro]);
  return <>
    <Head><style>{introOverlayCss}</style></Head>
    <LiveBackground />
    <Stack screenOptions={{ headerShown: false, title: 'Classio', contentStyle: { backgroundColor: 'transparent' } }} />
    <StorageNotice />
    {showHomeIntro ? <IntroConstellation sessionKey="classio-home-intro-seen-v2" ready={!loading && !!user && homeIntro.readyRoute === pathname} tagline={publicCopy(language).introTagline} theme={resolvedTheme} /> : null}
    <StatusBar style={resolvedTheme === 'dark' ? 'light' : 'dark'} />
  </>;
}

export default function RootLayout() {
  return (
    <AppPreferencesProvider><AuthProvider><PrivilegedAccessProvider><HomeIntroProvider><AppFrame /></HomeIntroProvider></PrivilegedAccessProvider></AuthProvider></AppPreferencesProvider>
  );
}
