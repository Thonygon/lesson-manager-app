/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Redirect, router, type Href } from 'expo-router';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell, type AppNotification } from '@/components/app-shell';
import { Button, EmptyState, LoadingState, Panel, Pagination, TabRail } from '@/components/ui';
import { ResourceFilters } from '@/components/resource-filters';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import type { PublicResource, PublicResourceKind } from '@/services/public-data';
import { getResourceLibrary, getResourcePreviewImages } from '@/services/resource-library';
import { buildPackageInsights, completeTeacherOnboarding, getTeacherDataset, type TeacherDataset } from '@/services/teacher-insights';
import { colors } from '@/theme';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';

const ACTIONS = [
  { href: '/dashboard', icon: '📊', title: 'nav.dashboard', body: 'home.actionDashboard', accent: colors.primary, tint: colors.primarySoft },
  { href: '/students', icon: '👩‍🎓', title: 'nav.students', body: 'home.actionStudents', accent: colors.success, tint: colors.successSoft },
  { href: '/lessons', icon: '📝', title: 'nav.lessons', body: 'home.actionLessons', accent: colors.orange, tint: colors.orangeSoft },
  { href: '/payments', icon: '💳', title: 'nav.payments', body: 'home.actionPayments', accent: colors.danger, tint: colors.dangerSoft },
  { href: '/calendar', icon: '📅', title: 'nav.calendar', body: 'home.actionCalendar', accent: colors.primary, tint: colors.primarySoft },
  { href: '/analytics', icon: '📈', title: 'nav.analytics', body: 'home.actionAnalytics', accent: colors.violet, tint: colors.violetSoft },
  { href: '/smart-tools', icon: '🤖', title: 'nav.smartTools', body: 'home.actionSmart', accent: colors.warning, tint: colors.warningSoft },
  { href: '/resources', icon: '🌐', title: 'nav.resources', body: 'home.actionResources', accent: colors.pink, tint: colors.pinkSoft },
] as const;
const normalizeFacet = (value: unknown) => String(value ?? '').trim().toLocaleLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ');
const KIND_META: Record<PublicResourceKind, { icon: string; labelKey: string }> = { program: { icon: '📚', labelKey: 'smart.program' }, plan: { icon: '📝', labelKey: 'smart.plan' }, worksheet: { icon: '📋', labelKey: 'smart.worksheet' }, exam: { icon: '🧪', labelKey: 'smart.exam' }, video: { icon: '🎬', labelKey: 'home.videos' } };

export default function HomeRoute() {
  const { profile } = useAuth(); const role = profile?.last_active_mode ?? profile?.primary_role ?? profile?.role;
  return role === 'student' ? <Redirect href="/student-home" /> : <TeacherHomeScreen />;
}

function TeacherHomeScreen() {
  const { profile, refreshProfile, user } = useAuth(); const { t } = useAppPreferences();
  const [dataset, setDataset] = useState<TeacherDataset | null>(null); const [mine, setMine] = useState<PublicResource[]>([]); const [community, setCommunity] = useState<PublicResource[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [welcomeDismissed, setWelcomeDismissed] = useState(false); const [kind, setKind] = useState<PublicResourceKind>('program'); const [query, setQuery] = useState(''); const [subject, setSubject] = useState(''); const [stage, setStage] = useState(''); const [level, setLevel] = useState(''); const [page, setPage] = useState(1);
  const hydratedImages = useRef(new Set<string>());
  const load = useCallback(async () => { setLoading(true); setError(''); try { const [teacherData, ownLibrary, sharedLibrary] = await Promise.all([getTeacherDataset(), getResourceLibrary('mine'), getResourceLibrary('community')]); setDataset(teacherData); setMine(ownLibrary.resources); setCommunity(sharedLibrary.resources); } catch (reason) { setError(reason instanceof Error ? reason.message : t('home.loadFailed')); } finally { setLoading(false); } }, [t]);
  useEffect(() => { void load(); }, [load]);
  const notifications = useMemo<AppNotification[]>(() => {
    if (!dataset) return [];
    const alerts: AppNotification[] = [];
    const reviews = dataset.reviewRequests.filter((row) => String(row.status) === 'requested');
    const packages = buildPackageInsights(dataset);
    const overused = packages.filter((row) => row.status === 'overused').length;
    const renewals = packages.filter((row) => row.status === 'finishing_soon' || row.status === 'due_now').length;
    if (reviews.length) alerts.push({ key: 'reviews', icon: '📋', title: t('dashboard.reviewNotification', { count: reviews.length }), body: t('dashboard.reviewNotificationBody'), href: { pathname: '/students', params: { section: 'progress', learningTab: 'reviews', student: String(reviews[0].student_id || '') } } as Href });
    if (overused) alerts.push({ key: 'overused', icon: '⚠️', title: t('dashboard.overusedNotification', { count: overused }), body: t('dashboard.packageNotificationBody'), href: '/payments' });
    if (renewals) alerts.push({ key: 'renewals', icon: '💳', title: t('dashboard.renewalNotification', { count: renewals }), body: t('dashboard.packageNotificationBody'), href: '/payments' });
    return alerts;
  }, [dataset, t]);
  const name = profile?.display_name || profile?.username || user?.email?.split('@')[0] || t('home.teacher');
  const steps = useMemo(() => [{ key: 'student', icon: '👤', label: t('home.stepStudent'), done: Boolean(dataset?.students.length), href: '/students' }, { key: 'plan', icon: '📚', label: t('home.stepPlan'), done: mine.some((item) => item.kind === 'plan'), href: '/smart-tools?tool=plan' }, { key: 'worksheet', icon: '🧩', label: t('home.stepWorksheet'), done: mine.some((item) => item.kind === 'worksheet'), href: '/smart-tools?tool=worksheet' }], [dataset?.students.length, mine, t]);
  const completed = steps.filter((step) => step.done).length; const progress = Math.round(completed / steps.length * 100); const showWelcome = !profile?.onboarding_completed && !welcomeDismissed;
  const dismissWelcome = async () => { setWelcomeDismissed(true); if (completed === steps.length) { await completeTeacherOnboarding(); await refreshProfile(); } };
  const kindResources = community.filter((item) => item.kind === kind);
  const facetOptions = (facet: 'subject' | 'stage' | 'level') => Array.from(new Map(kindResources.map((item) => item[facet]).filter(Boolean).map((value) => [facet === 'subject' ? canonicalSubjectKey(value) : normalizeFacet(value), facet === 'subject' ? canonicalSubjectLabel(value, t) : String(value)])).values()).sort((a, b) => a.localeCompare(b));
  const filteredResources = kindResources.filter((item) => (!subject || canonicalSubjectKey(item.subject) === canonicalSubjectKey(subject)) && (!stage || normalizeFacet(item.stage) === normalizeFacet(stage)) && (!level || normalizeFacet(item.level) === normalizeFacet(level)) && (!query.trim() || normalizeFacet([item.title, item.description, item.topic, item.subject, canonicalSubjectLabel(item.subject, t), item.stage, item.level, item.author].join(' ')).includes(normalizeFacet(query))));
  const totalPages = Math.max(1, Math.ceil(filteredResources.length / 6));
  const visibleResources = filteredResources.slice((Math.min(page, totalPages) - 1) * 6, Math.min(page, totalPages) * 6);
  const changeKind = (next: PublicResourceKind) => { setKind(next); setSubject(''); setStage(''); setLevel(''); setPage(1); };
  const clearFilters = () => { setQuery(''); setSubject(''); setStage(''); setLevel(''); setPage(1); };
  const hasFilters = Boolean(query.trim() || subject || stage || level);
  useEffect(() => {
    if (kind === 'video') return;
    const missing = visibleResources.filter((item) => !item.imageUrl && !hydratedImages.current.has(`${item.kind}:${item.id}`));
    if (!missing.length) return;
    missing.forEach((item) => hydratedImages.current.add(`${item.kind}:${item.id}`));
    void getResourcePreviewImages(kind, missing.map((item) => item.id)).then((images) => {
      if (!Object.keys(images).length) return;
      setCommunity((current) => current.map((item) => item.kind === kind && images[item.id] ? { ...item, imageUrl: images[item.id] } : item));
    });
  }, [kind, visibleResources]);

  if (loading) return <AppShell title={t('nav.home')} eyebrow={t('home.eyebrow')}><LoadingState /></AppShell>;
  if (error || !dataset) return <AppShell title={t('nav.home')} eyebrow={t('home.eyebrow')}><EmptyState title={t('home.loadFailed')} body={error} action={<Button onPress={() => void load()}>{t('common.refresh')}</Button>} /></AppShell>;
  return <AppShell title={t('home.welcome', { name })} eyebrow={t('home.eyebrow')} notifications={notifications}>
    {showWelcome ? <Panel style={styles.welcome}><Text style={styles.welcomeIcon}>🤖</Text><View style={styles.welcomeCopy}><Text style={styles.welcomeTitle}>{t('home.setupTitle')}</Text><Text style={styles.welcomeBody}>{t('home.setupBody')}</Text><View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${progress}%` }]} /></View><Text style={styles.progressText}>{progress}% · {completed}/{steps.length}</Text><View style={styles.steps}>{steps.map((step) => <Pressable key={step.key} onPress={() => router.push(step.href as never)} style={[styles.step, step.done && styles.stepDone]}><Text style={styles.stepIcon}>{step.done ? '✓' : step.icon}</Text><Text style={styles.stepLabel}>{step.label}</Text></Pressable>)}</View></View><Button secondary onPress={() => void dismissWelcome()}>{completed === steps.length ? t('home.finishSetup') : t('home.skip')}</Button></Panel> : null}
    <View style={styles.sectionHeader}><View><Text style={styles.sectionTitle}>{t('home.menuTitle')}</Text><Text style={styles.sectionBody}>{t('home.menuBody')}</Text></View></View>
    <View style={styles.actionGrid}>{ACTIONS.map((action) => <Pressable key={action.href} accessibilityRole="button" accessibilityLabel={t(action.title)} onPress={() => router.push(action.href)} style={({ pressed }) => [styles.actionCard, { backgroundColor: action.tint, borderColor: action.accent }, pressed && styles.cardPressed]}><View pointerEvents="none" style={styles.actionWash} /><View pointerEvents="none" style={[styles.actionGlow, { backgroundColor: action.tint }]} /><View pointerEvents="none" style={[styles.actionBar, { backgroundColor: action.accent }]} /><View style={[styles.actionIcon, { backgroundColor: action.tint, borderColor: action.accent }]}><Text style={styles.actionEmoji}>{action.icon}</Text></View><Text style={styles.actionTitle}>{t(action.title)}</Text><Text style={styles.actionBody}>{t(action.body)}</Text></Pressable>)}</View>
    <View style={styles.resourceHeader}><View><Text style={styles.sectionTitle}>{t('home.resourcesTitle')}</Text><Text style={styles.sectionBody}>{t('home.resourcesBody')}</Text></View></View>
    <TabRail accessibilityLabel={t('home.resourcesTitle')} items={(Object.keys(KIND_META) as PublicResourceKind[]).map((key) => ({ value: key, label: `${KIND_META[key].icon} ${t(KIND_META[key].labelKey)}` }))} value={kind} onChange={changeKind} />
    <ResourceFilters query={query} onQueryChange={(value) => { setQuery(value); setPage(1); }} count={filteredResources.length} facets={(['subject', 'stage', 'level'] as const).map((facet) => ({ key: facet, label: t(`resources.${facet}`), value: { subject, stage, level }[facet], allValue: '', allLabel: t(`resources.all${facet[0].toUpperCase()}${facet.slice(1)}s`), options: facetOptions(facet).map((value) => ({ value, label: value.replaceAll('_', ' ') })), onChange: (value: string) => { ({ subject: setSubject, stage: setStage, level: setLevel }[facet])(value); setPage(1); } }))} />
    {!visibleResources.length && hasFilters ? <View style={styles.clearRow}><Button secondary onPress={clearFilters}>{t('home.clearFilters')}</Button></View> : null}
    {visibleResources.length ? <View style={styles.resourceGrid}>{visibleResources.map((item) => <ResourceShowcaseCard key={`${item.kind}-${item.id}`} item={item} onPress={() => router.push({ pathname: '/resources', params: { scope: 'community', kind: item.kind, resourceId: String(item.id) } })} />)}</View> : <EmptyState title={t('home.noResources')} body={t('home.noResourcesBody')} />}
    {filteredResources.length > 6 ? <Pagination page={Math.min(page, totalPages)} totalPages={totalPages} totalItems={filteredResources.length} onPageChange={setPage} /> : null}
  </AppShell>;
}

const styles = StyleSheet.create({
  cardPressed: { opacity: 0.75, transform: [{ scale: 0.99 }] }, clearRow: { alignItems: 'flex-start', marginTop: 12 },
  welcome: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, alignItems: 'center', backgroundColor: colors.primarySoft, borderColor: colors.lineStrong, marginBottom: 24 }, welcomeIcon: { fontSize: 34 }, welcomeCopy: { flex: 1, minWidth: 260 }, welcomeTitle: { color: colors.ink, fontSize: 21, fontWeight: '900' }, welcomeBody: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 5 }, progressTrack: { height: 8, borderRadius: 99, overflow: 'hidden', backgroundColor: colors.line, marginTop: 14 }, progressFill: { height: '100%', backgroundColor: colors.success }, progressText: { color: colors.muted, fontSize: 9, fontWeight: '800', marginTop: 5 }, steps: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginTop: 11 }, step: { flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: 999, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surface, paddingHorizontal: 10, paddingVertical: 7 }, stepDone: { backgroundColor: colors.successSoft, borderColor: colors.success }, stepIcon: { color: colors.success, fontSize: 11, fontWeight: '900' }, stepLabel: { color: colors.ink, fontSize: 9, fontWeight: '800' }, sectionHeader: { marginBottom: 13 }, sectionTitle: { color: colors.ink, fontSize: 20, fontWeight: '900' }, sectionBody: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 4 }, actionGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 11 }, actionCard: { flexGrow: 1, flexBasis: 240, minWidth: 225, maxWidth: 350, minHeight: 150, borderRadius: 20, borderWidth: 1, overflow: 'hidden', padding: 18, alignItems: 'flex-start' }, actionWash: { position: 'absolute', inset: 0, backgroundColor: colors.surface, opacity: 0.82 }, actionGlow: { position: 'absolute', top: -62, right: -32, width: 170, height: 125, borderRadius: 999, opacity: 0.9 }, actionBar: { position: 'absolute', left: 18, right: 18, top: 0, height: 4, borderBottomLeftRadius: 999, borderBottomRightRadius: 999, opacity: 0.75 }, actionIcon: { width: 46, height: 46, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center' }, actionEmoji: { fontSize: 23 }, actionTitle: { color: colors.ink, fontSize: 16, fontWeight: '900', marginTop: 12, textAlign: 'left' }, actionBody: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: 5, textAlign: 'left' }, actionOpen: { fontSize: 10, fontWeight: '900', marginTop: 'auto', paddingTop: 10 }, resourceHeader: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 32, marginBottom: 10 }, kindRow: { gap: 7, paddingVertical: 7 }, choice: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 8 }, choiceActive: { backgroundColor: colors.primary, borderColor: colors.primary }, choiceText: { color: colors.muted, fontSize: 10, fontWeight: '800' }, choiceTextActive: { color: colors.inverse }, resourceGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 8 }, resourceCard: { flexGrow: 1, flexBasis: 320, minWidth: 280, maxWidth: 530, flexDirection: 'row', minHeight: 132, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 16, overflow: 'hidden' }, resourceVisual: { width: 132, minHeight: 132, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceSoft }, resourceImage: { width: '100%', height: '100%' }, resourceIcon: { fontSize: 34 }, resourceCopy: { flex: 1, padding: 14 }, resourceTitle: { color: colors.ink, fontSize: 14, lineHeight: 18, fontWeight: '900' }, resourceBody: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 5 }, resourceMeta: { color: colors.primary, fontSize: 8, fontWeight: '800', textTransform: 'capitalize', marginTop: 'auto', paddingTop: 8 },
});
