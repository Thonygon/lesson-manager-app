import { Link, router, type Href, usePathname } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import type { PropsWithChildren } from 'react';
import { Image, Modal, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PreferenceSwitcher } from '@/components/preference-switcher';
import { colors } from '@/theme';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { usePrivilegedAccess } from '@/providers/privileged-access-provider';
import { useNotifications } from '@/providers/notifications-provider';

const NAV = [
  { href: '/dashboard', icon: '⌂', labelKey: 'nav.home', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/student-home', icon: '⌂', labelKey: 'nav.home', roles: ['student'] },
  { href: '/students', icon: '◉', labelKey: 'nav.students', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/lessons', icon: '◷', labelKey: 'nav.lessons', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/payments', icon: '◫', labelKey: 'nav.payments', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/calendar', icon: '□', labelKey: 'nav.calendar', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/resources', icon: '◇', labelKey: 'nav.resources', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/smart-tools', icon: '✦', labelKey: 'nav.smartTools', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/analytics', icon: '↗', labelKey: 'nav.analytics', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/branding', icon: '✎', labelKey: 'branding.title', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/community', icon: '◎', labelKey: 'nav.community', roles: ['teacher', 'school_admin', 'admin'] },
  { href: '/student-practice', icon: '✦', labelKey: 'nav.practice', roles: ['student'] },
  { href: '/student-study-plan', icon: '▤', labelKey: 'nav.studyPlan', roles: ['student'] },
  { href: '/student-assignments', icon: '▣', labelKey: 'nav.assignments', roles: ['student'] },
  { href: '/student-find-teacher', icon: '⌕', labelKey: 'nav.findTeacher', roles: ['student'] },
] as const;

const PRIVILEGED_NAV = [
  { href: '/admin', icon: '⚙', labelKey: 'admin.area.administration', kind: 'admin' },
  { href: '/admin-operations', icon: '◈', labelKey: 'admin.area.operations', kind: 'admin' },
  { href: '/admin-business', icon: '↗', labelKey: 'admin.area.business', kind: 'admin' },
  { href: '/developer-workspace', icon: '⌘', labelKey: 'nav.developer', kind: 'developer' },
] as const;

let desktopNavigationCollapsed = false;

export type AppNotification = { key: string; icon: string; title: string; body?: string; href: Href };

export function AppShell({ title, eyebrow, notifications, scrollToTopToken, children }: PropsWithChildren<{ title: string; eyebrow?: string; notifications?: AppNotification[]; scrollToTopToken?: number }>) {
  const contentScrollRef = useRef<ScrollView>(null);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(() => desktopNavigationCollapsed);
  const { width } = useWindowDimensions();
  const { t } = useAppPreferences();
  const pathname = usePathname();
  const { profile, user } = useAuth();
  const access = usePrivilegedAccess();
  const inbox = useNotifications();
  const { publishPaymentAlerts } = inbox;
  useEffect(() => { if (notifications) publishPaymentAlerts(notifications); }, [notifications, publishPaymentAlerts]);
  useEffect(() => {
    if (!scrollToTopToken) return;
    const frame = requestAnimationFrame(() => contentScrollRef.current?.scrollTo({ y: 0, animated: true }));
    return () => cancelAnimationFrame(frame);
  }, [scrollToTopToken]);
  const compact = width < 960; const phone = width < 560;
  const role = profile?.last_active_mode ?? profile?.primary_role ?? profile?.role ?? 'student';
  const navigationRole = pathname.startsWith('/admin') && access.isAdmin ? 'admin'
    : pathname === '/developer-workspace' && access.canUseDeveloperWorkspace ? 'developer'
    : role;
  const identityName = profile?.display_name || profile?.username || user?.email || t('nav.profile');
  const identityInitial = String(identityName).slice(0, 1).toUpperCase();
  const visibleNav = navigationRole === 'admin' || navigationRole === 'developer' ? [] : NAV.filter((item) => (item.roles as readonly string[]).includes(navigationRole));
  const privilegedNav = PRIVILEGED_NAV.filter((item) => item.kind === navigationRole && (item.kind === 'admin' ? access.isAdmin : access.canUseDeveloperWorkspace));
  const allNav = [...visibleNav, ...privilegedNav];
  const showSidebar = compact ? mobileNavigationOpen : !desktopCollapsed;
  const toggleNavigation = () => {
    if (compact) setMobileNavigationOpen((open) => !open);
    else setDesktopCollapsed((collapsed) => { desktopNavigationCollapsed = !collapsed; return !collapsed; });
  };
  const headerActions = <View style={[styles.headerActions, compact && styles.headerActionsCompact]}>
    <Pressable accessibilityRole="button" accessibilityLabel={`${t('dashboard.notifications')}: ${inbox.unread.length}`} accessibilityState={{ expanded: inboxOpen }} onPress={() => { setInboxOpen(true); void inbox.refresh(true); }} style={styles.bell}><Text style={styles.bellIcon}>🔔</Text>{inbox.unread.length ? <View style={styles.badge}><Text style={styles.badgeText}>{inbox.unread.length > 99 ? '99+' : inbox.unread.length}</Text></View> : null}</Pressable>
    {compact ? <Pressable accessibilityRole="link" accessibilityLabel={`${t('nav.profile')}: ${identityName}`} accessibilityState={{ selected: pathname === '/profile' }} onPress={() => router.push('/profile')} style={({ pressed }) => [styles.compactIdentity, phone && styles.compactIdentityPhone, pathname === '/profile' && styles.identityButtonActive, pressed && styles.identityButtonPressed]}>{profile?.avatar_url ? <Image source={{ uri: profile.avatar_url }} style={styles.identityAvatar} /> : <View style={styles.identityFallback}><Text style={styles.identityInitial}>{identityInitial}</Text></View>}<Text numberOfLines={1} style={styles.compactIdentityName}>{identityName}</Text></Pressable> : null}
  </View>;

  return (
    <SafeAreaView style={styles.safe}>
      {compact ? <View style={styles.mobileBar}>
        <Pressable accessibilityRole="button" accessibilityLabel={t('nav.openMenu')} accessibilityState={{ expanded: mobileNavigationOpen }} onPress={toggleNavigation} style={[styles.menuButton, phone && styles.menuButtonPhone]}><Text style={styles.menuIcon}>☰</Text></Pressable>
        <Link href={navigationRole === 'admin' ? '/admin' : navigationRole === 'developer' ? '/developer-workspace' : role === 'student' ? '/student-home' : '/dashboard'} accessibilityLabel="Classio home"><Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={[styles.mobileLogo, phone && styles.mobileLogoPhone]} /></Link>
        {headerActions}
      </View> : null}
      <View style={[styles.layout, compact && styles.layoutCompact]}>
        {compact && mobileNavigationOpen ? <Pressable accessibilityRole="button" accessibilityLabel={t('common.close')} onPress={() => setMobileNavigationOpen(false)} style={styles.drawerBackdrop} /> : null}
        {showSidebar ? <View style={[styles.sidebar, compact && styles.sidebarDrawer]}>
          <View style={styles.sidebarHeader}><Link href={navigationRole === 'admin' ? '/admin' : navigationRole === 'developer' ? '/developer-workspace' : role === 'student' ? '/student-home' : '/dashboard'} accessibilityLabel="Classio home">
            <Image source={require('../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.logo} />
          </Link><Pressable accessibilityRole="button" accessibilityLabel={compact ? t('common.close') : t('nav.hideMenu')} onPress={toggleNavigation} style={styles.menuButton}><Text style={styles.menuIcon}>{compact ? '×' : '‹'}</Text></Pressable></View>
          <ScrollView style={styles.navScroll} contentContainerStyle={styles.nav}>
            {allNav.map((item) => {
              const active = pathname === item.href || (item.href === '/students' && pathname.startsWith('/student-delete'));
              return (
                <Link key={item.href} href={item.href as Href} onPress={() => { if (compact) setMobileNavigationOpen(false); }} style={[styles.navItem, active && styles.navItemActive]}>
                  <View style={styles.navInner}><Text style={[styles.navIcon, active && styles.navTextActive]}>{item.icon}</Text><Text style={[styles.navText, active && styles.navTextActive]}>{t(item.labelKey)}</Text></View>
                </Link>
              );
            })}
          </ScrollView>
          <View style={styles.sidebarFooter}>
            <PreferenceSwitcher compact={compact} sidebar />
            {!compact ? <View style={styles.identity}><Pressable accessibilityRole="link" accessibilityLabel={`${t('nav.profile')}: ${identityName}`} accessibilityState={{ selected: pathname === '/profile' }} onPress={() => router.push('/profile')} style={({ pressed }) => [styles.identityButton, pathname === '/profile' && styles.identityButtonActive, pressed && styles.identityButtonPressed]}>
              <View style={styles.identityRow}>{profile?.avatar_url ? <Image source={{ uri: profile.avatar_url }} style={styles.identityAvatar} /> : <View style={styles.identityFallback}><Text style={styles.identityInitial}>{identityInitial}</Text></View>}<View style={styles.identityCopy}><Text numberOfLines={1} style={styles.identityName}>{identityName}</Text><Text style={styles.identityRole}>{navigationRole.replace('_', ' ')}</Text></View></View>
            </Pressable></View> : null}
          </View>
        </View> : null}
        <ScrollView ref={contentScrollRef} style={styles.contentScroll} contentContainerStyle={[styles.content, phone && styles.contentPhone]} keyboardShouldPersistTaps="handled">
          <View style={[styles.pageHeader, phone && styles.pageHeaderPhone]}>
            {!compact && desktopCollapsed ? <Pressable accessibilityRole="button" accessibilityLabel={t('nav.openMenu')} accessibilityState={{ expanded: false }} onPress={toggleNavigation} style={styles.menuButton}><Text style={styles.menuIcon}>☰</Text></Pressable> : null}
            <View style={styles.headingCopy}>{eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}<Text style={styles.title}>{title}</Text></View>
            {!compact ? headerActions : null}
          </View>
          <View style={styles.body}>{children}</View>
        </ScrollView>
      </View>
      <Modal visible={inboxOpen} transparent animationType="fade" onRequestClose={() => setInboxOpen(false)}>
        <View style={styles.modalRoot}>
          <Pressable accessibilityRole="button" accessibilityLabel={t('common.close')} onPress={() => setInboxOpen(false)} style={styles.modalBackdrop} />
          <View style={[styles.inbox, phone && styles.inboxPhone]}>
            <View style={styles.inboxHeader}><Text style={styles.inboxTitle}>{t('dashboard.notifications')}</Text><Pressable accessibilityRole="button" accessibilityLabel={t('common.close')} onPress={() => setInboxOpen(false)} style={styles.inboxClose}><Text style={styles.inboxCloseText}>×</Text></Pressable></View>
            <ScrollView style={styles.inboxScroll} contentContainerStyle={styles.inboxList}>
              {inbox.error ? <Text style={styles.inboxError}>{inbox.error}</Text> : null}
              {inbox.loading && !inbox.items.length ? <Text style={styles.inboxEmpty}>{t('common.loading')}</Text> : null}
              {inbox.items.length ? inbox.items.map((item) => {
                const isUnread = inbox.unread.some((unread) => unread.key === item.key);
                const itemTitle = item.titleText || t(item.titleKey, item.titleParams);
                return <View key={item.key} style={[styles.inboxItem, isUnread && styles.inboxItemUnread]}><Pressable accessibilityRole="button" accessibilityLabel={itemTitle} onPress={() => { void inbox.markRead(item.key); setInboxOpen(false); router.push(item.href); }} style={styles.inboxItemLink}><Text style={styles.inboxIcon}>{item.icon}</Text><View style={styles.inboxCopy}><Text style={styles.inboxItemTitle}>{itemTitle}</Text>{item.detail ? <Text style={styles.inboxBody}>{item.detail}</Text> : null}</View>{isUnread ? <View style={styles.unreadDot} /> : null}</Pressable><Pressable accessibilityRole="button" accessibilityLabel={t(isUnread ? 'notifications.markRead' : 'notifications.markUnread')} onPress={() => void (isUnread ? inbox.markRead(item.key) : inbox.markUnread(item.key))} style={styles.inboxReadAction}><Text style={styles.inboxReadActionText}>{t(isUnread ? 'notifications.markRead' : 'notifications.markUnread')}</Text></Pressable><Text style={styles.inboxArrow}>→</Text></View>;
              }) : !inbox.loading ? <Text style={styles.inboxEmpty}>{t('dashboard.noNotifications')}</Text> : null}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: 'transparent' },
  layout: { flex: 1, flexDirection: 'row' },
  layoutCompact: { flexDirection: 'column' },
  sidebar: { width: 238, padding: 22, backgroundColor: colors.surface, borderRightWidth: 1, borderRightColor: colors.line },
  sidebarDrawer: { position: 'absolute', top: 0, bottom: 0, left: 0, width: 280, maxWidth: '85%', zIndex: 2 },
  drawerBackdrop: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, zIndex: 1, backgroundColor: 'rgba(0, 0, 0, 0.45)' },
  mobileBar: { minHeight: 58, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 8, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.line },
  mobileLogo: { width: 106, height: 40 },
  mobileLogoPhone: { width: 88, height: 36 },
  sidebarHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 },
  menuButton: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center' },
  menuButtonPhone: { width: 34 },
  menuIcon: { color: colors.primary, fontSize: 25, lineHeight: 30, fontWeight: '600' },
  logo: { width: 132, height: 48 },
  navScroll: { flex: 1 },
  nav: { gap: 7 },
  navItem: { paddingVertical: 11, paddingHorizontal: 12, borderRadius: 10 },
  navItemActive: { backgroundColor: colors.primarySoft },
  navInner: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  navIcon: { color: colors.subtle, width: 16, fontSize: 14, textAlign: 'center' },
  navText: { color: colors.muted, fontSize: 14, fontWeight: '600' },
  navTextActive: { color: colors.primary },
  sidebarFooter: { marginTop: 'auto', paddingTop: 14, borderTopWidth: 1, borderTopColor: colors.line, gap: 10 },
  identity: { paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line },
  identityButton: { paddingVertical: 10, paddingHorizontal: 9, marginHorizontal: -9, borderRadius: 12 },
  identityButtonActive: { backgroundColor: colors.primarySoft },
  identityButtonPressed: { opacity: 0.72 },
  compactIdentity: { maxWidth: 190, minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 8, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  compactIdentityPhone: { maxWidth: 125, minWidth: 0, flexShrink: 1, paddingHorizontal: 5, gap: 5 },
  compactIdentityName: { color: colors.ink, fontSize: 12, fontWeight: '700', maxWidth: 130, minWidth: 0, flexShrink: 1 },
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
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerActionsCompact: { marginLeft: 'auto', minWidth: 0, flexShrink: 1, gap: 4 },
  headingCopy: { flex: 1 },
  eyebrow: { color: colors.primary, fontSize: 11, fontWeight: '800', letterSpacing: 1.2, marginBottom: 7 },
  title: { color: colors.ink, fontSize: 34, lineHeight: 41, fontWeight: '800', letterSpacing: -0.8 },
  inboxItemLink: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  bell: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' }, bellIcon: { color: colors.ink, fontSize: 18 }, badge: { position: 'absolute', top: -3, right: -3, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: colors.danger, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3 }, badgeText: { color: colors.inverse, fontSize: 8, fontWeight: '900' }, inbox: { width: 420, maxWidth: '100%', maxHeight: '85%', borderWidth: 1, borderColor: colors.line, borderRadius: 18, backgroundColor: colors.surface, padding: 16, gap: 7 }, inboxTitle: { color: colors.ink, fontSize: 17, fontWeight: '900', marginBottom: 3 }, inboxItem: { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, backgroundColor: colors.surfaceSoft, padding: 12 }, inboxIcon: { fontSize: 20 }, inboxCopy: { flex: 1 }, inboxItemTitle: { color: colors.ink, fontSize: 13, fontWeight: '800' }, inboxBody: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: 3 }, inboxReadAction: { paddingVertical: 7, paddingHorizontal: 4 }, inboxReadActionText: { color: colors.primary, fontSize: 10, fontWeight: '800' }, inboxArrow: { color: colors.primary, fontSize: 17, fontWeight: '900' }, inboxEmpty: { color: colors.success, fontSize: 13, fontWeight: '700' },
  body: { marginTop: 26 },
  modalRoot: { flex: 1, alignItems: 'flex-end', justifyContent: 'flex-start', paddingTop: 24, paddingHorizontal: 20 },
  modalBackdrop: { position: 'absolute', inset: 0, backgroundColor: 'rgba(4, 12, 27, 0.62)' },
  inboxPhone: { width: '100%', maxHeight: '85%' },
  inboxHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  inboxClose: { minWidth: 36, minHeight: 36, alignItems: 'center', justifyContent: 'center' },
  inboxCloseText: { color: colors.muted, fontSize: 28, lineHeight: 30 },
  inboxScroll: { maxHeight: 550 },
  inboxList: { gap: 8, paddingBottom: 5 },
  inboxItemUnread: { borderWidth: 1, borderColor: colors.primary },
  unreadDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.primary },
  inboxError: { color: colors.danger, fontSize: 11 },
});
