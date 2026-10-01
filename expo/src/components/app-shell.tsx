import { Link, router, type Href, usePathname } from 'expo-router';
import { useState } from 'react';
import type { PropsWithChildren } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PreferenceSwitcher } from '@/components/preference-switcher';
import { colors } from '@/theme';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { usePrivilegedAccess } from '@/providers/privileged-access-provider';

const NAV = [
  { href: '/home', icon: '⌂', labelKey: 'nav.home', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/student-home', icon: '⌂', labelKey: 'nav.home', roles: ['student'] },
  { href: '/dashboard', icon: '▦', labelKey: 'nav.dashboard', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/students', icon: '◉', labelKey: 'nav.students', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/lessons', icon: '◷', labelKey: 'nav.lessons', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/calendar', icon: '□', labelKey: 'nav.calendar', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/resources', icon: '◇', labelKey: 'nav.resources', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/smart-tools', icon: '✦', labelKey: 'nav.smartTools', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/payments', icon: '◫', labelKey: 'nav.payments', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/analytics', icon: '↗', labelKey: 'nav.analytics', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/community', icon: '◎', labelKey: 'nav.community', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/profile', icon: '◉', labelKey: 'nav.profile', roles: ['teacher', 'student', 'school_admin', 'admin'] },
  { href: '/billing', icon: '◇', labelKey: 'nav.billing', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/student-practice', icon: '✦', labelKey: 'nav.practice', roles: ['student'] },
  { href: '/student-study-plan', icon: '▤', labelKey: 'nav.studyPlan', roles: ['student'] },
  { href: '/student-assignments', icon: '▣', labelKey: 'nav.assignments', roles: ['student'] },
  { href: '/student-find-teacher', icon: '⌕', labelKey: 'nav.findTeacher', roles: ['student'] },
  { href: '/account', icon: '○', labelKey: 'nav.account', roles: ['teacher', 'student', 'school_admin', 'admin'] },
] as const;

const PRIVILEGED_NAV = [
  { href: '/admin', icon: '⚙', labelKey: 'nav.admin', kind: 'admin' },
  { href: '/developer-workspace', icon: '⌘', labelKey: 'nav.developer', kind: 'developer' },
] as const;

export type AppNotification = { key: string; icon: string; title: string; body?: string; href: Href };

export function AppShell({ title, eyebrow, notifications, children }: PropsWithChildren<{ title: string; eyebrow?: string; notifications?: AppNotification[] }>) {
  const [inboxOpen, setInboxOpen] = useState(false);
  const { width } = useWindowDimensions();
  const { t } = useAppPreferences();
  const pathname = usePathname();
  const { profile, user } = useAuth();
  const access = usePrivilegedAccess();
  const compact = width < 960; const phone = width < 560;
  const role = profile?.last_active_mode ?? profile?.primary_role ?? profile?.role ?? 'student';
  const visibleNav = NAV.filter((item) => (item.roles as readonly string[]).includes(role));
  const privilegedNav = PRIVILEGED_NAV.filter((item) => item.kind === 'admin' ? access.isAdmin : access.canUseDeveloperWorkspace);
  const allNav = [...visibleNav, ...privilegedNav];

  return (
    <SafeAreaView style={styles.safe}>
      <View style={[styles.layout, compact && styles.layoutCompact]}>
        <View style={[styles.sidebar, compact && styles.sidebarCompact]}>
          <Link href={role === 'student' ? '/student-home' : '/home'} accessibilityLabel="Classio home">
            <Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.logo} />
          </Link>
          <ScrollView horizontal={compact} showsHorizontalScrollIndicator={false} contentContainerStyle={[styles.nav, compact && styles.navCompact]}>
            {allNav.map((item) => {
              const active = pathname === item.href || (item.href === '/students' && pathname.startsWith('/student-delete'));
              return (
                <Link key={item.href} href={item.href as Href} style={[styles.navItem, active && styles.navItemActive]}>
                  <View style={styles.navInner}><Text style={[styles.navIcon, active && styles.navTextActive]}>{item.icon}</Text><Text style={[styles.navText, active && styles.navTextActive]}>{t(item.labelKey)}</Text></View>
                </Link>
              );
            })}
          </ScrollView>
          {!compact && (
            <View style={styles.identity}>
              <View style={styles.identityRow}>{profile?.avatar_url ? <Image source={{ uri: profile.avatar_url }} style={styles.identityAvatar} /> : <View style={styles.identityFallback}><Text style={styles.identityInitial}>{String(profile?.display_name || profile?.username || user?.email || 'U').slice(0, 1).toUpperCase()}</Text></View>}<View style={styles.identityCopy}><Text numberOfLines={1} style={styles.identityName}>{profile?.display_name || profile?.username || user?.email}</Text><Text style={styles.identityRole}>{role.replace('_', ' ')}</Text></View></View>
            </View>
          )}
        </View>
        <ScrollView style={styles.contentScroll} contentContainerStyle={[styles.content, phone && styles.contentPhone]} keyboardShouldPersistTaps="handled">
          <View style={[styles.pageHeader, phone && styles.pageHeaderPhone]}>
            <View style={styles.headingCopy}>{eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}<Text style={styles.title}>{title}</Text></View>
            <View style={styles.headerActions}>
              {notifications ? <Pressable accessibilityRole="button" accessibilityLabel={`${t('dashboard.notifications')}: ${notifications.length}`} accessibilityState={{ expanded: inboxOpen }} onPress={() => setInboxOpen((open) => !open)} style={[styles.bell, inboxOpen && styles.bellActive]}><Text style={styles.bellIcon}>🔔</Text>{notifications.length ? <View style={styles.badge}><Text style={styles.badgeText}>{notifications.length}</Text></View> : null}</Pressable> : null}
              <PreferenceSwitcher compact={phone} />
            </View>
          </View>
          {notifications && inboxOpen ? <View style={styles.inbox}><Text style={styles.inboxTitle}>{t('dashboard.notifications')}</Text>{notifications.length ? notifications.map((item) => <Pressable key={item.key} accessibilityRole="button" accessibilityLabel={item.title} onPress={() => { setInboxOpen(false); router.push(item.href); }} style={styles.inboxItem}><Text style={styles.inboxIcon}>{item.icon}</Text><View style={styles.inboxCopy}><Text style={styles.inboxItemTitle}>{item.title}</Text>{item.body ? <Text style={styles.inboxBody}>{item.body}</Text> : null}</View><Text style={styles.inboxArrow}>→</Text></Pressable>) : <Text style={styles.inboxEmpty}>{t('dashboard.noNotifications')}</Text>}</View> : null}
          <View style={styles.body}>{children}</View>
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: 'transparent' },
  layout: { flex: 1, flexDirection: 'row' },
  layoutCompact: { flexDirection: 'column' },
  sidebar: { width: 238, padding: 22, backgroundColor: colors.surface, borderRightWidth: 1, borderRightColor: colors.line },
  sidebarCompact: { width: '100%', paddingVertical: 10, paddingHorizontal: 16, borderRightWidth: 0, borderBottomWidth: 1, borderBottomColor: colors.line },
  logo: { width: 132, height: 48, marginBottom: 28 },
  nav: { gap: 7 },
  navCompact: { flexDirection: 'row', paddingRight: 12 },
  navItem: { paddingVertical: 11, paddingHorizontal: 12, borderRadius: 10 },
  navItemActive: { backgroundColor: colors.primarySoft },
  navInner: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  navIcon: { color: colors.subtle, width: 16, fontSize: 14, textAlign: 'center' },
  navText: { color: colors.muted, fontSize: 14, fontWeight: '600' },
  navTextActive: { color: colors.primary },
  identity: { marginTop: 'auto', paddingTop: 20, borderTopWidth: 1, borderTopColor: colors.line },
  identityRow: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  identityAvatar: { width: 34, height: 34, borderRadius: 17 },
  identityFallback: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primarySoft },
  identityInitial: { color: colors.primary, fontSize: 12, fontWeight: '900' },
  identityCopy: { flex: 1 },
  identityName: { color: colors.ink, fontSize: 13, fontWeight: '700' },
  identityRole: { color: colors.muted, fontSize: 12, textTransform: 'capitalize', marginTop: 4 },
  contentScroll: { flex: 1 },
  content: { width: '100%', maxWidth: 1120, alignSelf: 'center', paddingHorizontal: 28, paddingTop: 36, paddingBottom: 64 },
  contentPhone: { paddingHorizontal: 14, paddingTop: 22, paddingBottom: 44 },
  pageHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20 },
  pageHeaderPhone: { flexDirection: 'column', gap: 14 },
  headingCopy: { flex: 1 },
  eyebrow: { color: colors.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1.2, marginBottom: 7 },
  title: { color: colors.ink, fontSize: 34, lineHeight: 41, fontWeight: '800', letterSpacing: -0.8 },
  headerActions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 }, bell: { width: 46, height: 46, borderRadius: 14, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }, bellActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, bellIcon: { color: colors.ink, fontSize: 23 }, badge: { position: 'absolute', top: -5, right: -5, minWidth: 20, height: 20, borderRadius: 10, backgroundColor: colors.danger, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 }, badgeText: { color: colors.inverse, fontSize: 10, fontWeight: '900' }, inbox: { borderWidth: 1, borderColor: colors.line, borderRadius: 18, backgroundColor: colors.surface, padding: 16, marginTop: 16, gap: 7 }, inboxTitle: { color: colors.ink, fontSize: 17, fontWeight: '900', marginBottom: 3 }, inboxItem: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, backgroundColor: colors.surfaceSoft, padding: 12 }, inboxIcon: { fontSize: 20 }, inboxCopy: { flex: 1 }, inboxItemTitle: { color: colors.ink, fontSize: 13, fontWeight: '800' }, inboxBody: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: 3 }, inboxArrow: { color: colors.primary, fontSize: 17, fontWeight: '900' }, inboxEmpty: { color: colors.success, fontSize: 13, fontWeight: '700' },
  body: { marginTop: 26 },
});
