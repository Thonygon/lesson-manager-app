import { Redirect, router, Stack, usePathname, type Href } from 'expo-router';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { LoadingState } from '@/components/ui';
import { useAuth } from '@/providers/auth-provider';
import { authorizedDestination, requiresRoleSelection } from '@/lib/route-access';
import { usePrivilegedAccess } from '@/providers/privileged-access-provider';
import { NotificationsProvider } from '@/providers/notifications-provider';

export default function ProtectedLayout() {
  const { configured, loading, user, profile } = useAuth();
  const pathname = usePathname();
  const access = usePrivilegedAccess();
  const destination = !loading && user && requiresRoleSelection(profile) ? '/choose-role' : authorizedDestination(pathname, profile, access);
  useEffect(() => {
    if (!destination) return;
    if (destination === '/choose-role') { router.replace(destination as Href); return; }
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      if (window.location.pathname !== destination) window.location.replace(destination);
      return;
    }
    router.replace(destination);
  }, [destination]);
  if (loading || (access.loading && (pathname.startsWith('/admin') || pathname.startsWith('/developer-workspace')))) return <LoadingState />;
  if (!configured || !user) return <Redirect href="/sign-in" />;
  if (destination) return <LoadingState />;
  return <NotificationsProvider><Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: 'transparent' } }} /></NotificationsProvider>;
}
