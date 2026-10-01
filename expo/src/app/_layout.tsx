import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { AuthProvider } from '@/providers/auth-provider';
import { AppPreferencesProvider, useAppPreferences } from '@/providers/app-preferences';
import { PrivilegedAccessProvider } from '@/providers/privileged-access-provider';
import { LiveBackground } from '@/components/live-background';

function AppFrame() {
  const { resolvedTheme } = useAppPreferences();
  return <><LiveBackground /><Stack screenOptions={{ headerShown: false, title: 'Classio', contentStyle: { backgroundColor: 'transparent' } }} /><StatusBar style={resolvedTheme === 'dark' ? 'light' : 'dark'} /></>;
}

export default function RootLayout() {
  return (
    <AppPreferencesProvider><AuthProvider><PrivilegedAccessProvider><AppFrame /></PrivilegedAccessProvider></AuthProvider></AppPreferencesProvider>
  );
}
