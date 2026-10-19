import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { ResourceFilters } from '@/components/resource-filters';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { EmptyState, Pagination, TabRail } from '@/components/ui';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { useAppPreferences } from '@/providers/app-preferences';
import type { PublicResource, PublicResourceKind } from '@/services/public-data';
import { getResourceLibrary, getResourcePreviewImages } from '@/services/resource-library';
import { colors } from '@/theme';

const ACTIONS = [
  { href: '/students', icon: '👩‍🎓', title: 'nav.students', body: 'home.actionStudents', accent: colors.success, tint: colors.successSoft },
  { href: '/lessons', icon: '📝', title: 'nav.lessons', body: 'home.actionLessons', accent: colors.orange, tint: colors.orangeSoft },
  { href: '/payments', icon: '💳', title: 'nav.payments', body: 'home.actionPayments', accent: colors.danger, tint: colors.dangerSoft },
  { href: '/calendar', icon: '📅', title: 'nav.calendar', body: 'home.actionCalendar', accent: colors.primary, tint: colors.primarySoft },
  { href: '/analytics', icon: '📈', title: 'nav.analytics', body: 'home.actionAnalytics', accent: colors.violet, tint: colors.violetSoft },
  { href: '/smart-tools', icon: '🤖', title: 'nav.smartTools', body: 'home.actionSmart', accent: colors.warning, tint: colors.warningSoft },
  { href: '/resources', icon: '🌐', title: 'nav.resources', body: 'home.actionResources', accent: colors.pink, tint: colors.pinkSoft },
  { href: '/community', icon: '🤝', title: 'nav.community', body: 'home.resourcesBody', accent: colors.violet, tint: colors.violetSoft },
] as const;
const KINDS: Record<PublicResourceKind, { icon: string; label: string }> = { program: { icon: '📚', label: 'smart.program' }, plan: { icon: '📝', label: 'smart.plan' }, worksheet: { icon: '📋', label: 'smart.worksheet' }, exam: { icon: '🧪', label: 'smart.exam' }, video: { icon: '🎬', label: 'home.videos' } };
const norm = (value: unknown) => String(value ?? '').trim().toLocaleLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' ');

export function TeacherHomeExtras() {
  const { t } = useAppPreferences();
  const phone = useWindowDimensions().width < 560;
  const [resources, setResources] = useState<PublicResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [kind, setKind] = useState<PublicResourceKind>('program');
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('');
  const [stage, setStage] = useState('');
  const [level, setLevel] = useState('');
  const [page, setPage] = useState(1);
  const hydrated = useRef(new Set<string>());
  useEffect(() => {
    let active = true;
    void getResourceLibrary('community').then((value) => { if (active) setResources(value.resources); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : t('home.loadFailed')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [t]);
  const kindResources = resources.filter((item) => item.kind === kind);
  const options = (facet: 'subject' | 'stage' | 'level') => [...new Map(kindResources.map((item) => item[facet]).filter(Boolean).map((value) => [facet === 'subject' ? canonicalSubjectKey(value) : norm(value), facet === 'subject' ? canonicalSubjectLabel(value, t) : String(value)])).values()].sort((a, b) => a.localeCompare(b));
  const filtered = kindResources.filter((item) => (!subject || canonicalSubjectKey(item.subject) === canonicalSubjectKey(subject)) && (!stage || norm(item.stage) === norm(stage)) && (!level || norm(item.level) === norm(level)) && (!query.trim() || norm([item.title, item.description, item.topic, item.subject, item.stage, item.level, item.author].join(' ')).includes(norm(query))));
  const pages = Math.max(1, Math.ceil(filtered.length / 6));
  const visible = filtered.slice((Math.min(page, pages) - 1) * 6, Math.min(page, pages) * 6);
  useEffect(() => {
    if (kind === 'video') return;
    const missing = visible.filter((item) => !item.imageUrl && !hydrated.current.has(`${item.kind}:${item.id}`));
    if (!missing.length) return;
    missing.forEach((item) => hydrated.current.add(`${item.kind}:${item.id}`));
    void getResourcePreviewImages(kind, missing.map((item) => item.id)).then((images) => {
      if (Object.keys(images).length) setResources((current) => current.map((item) => item.kind === kind && images[item.id] ? { ...item, imageUrl: images[item.id] } : item));
    }).catch(() => {});
  }, [kind, visible]);
  return <>
    <Text style={styles.heading}>{t('dashboard.quickActions')}</Text>
    <View style={[styles.actions, phone && styles.actionsPhone]}>{ACTIONS.map((action) => <Pressable key={action.href} accessibilityRole="button" accessibilityLabel={t(action.title)} onPress={() => router.push(action.href)} style={({ pressed }) => [styles.action, phone && styles.actionPhone, { borderColor: action.accent, backgroundColor: action.tint }, pressed && styles.pressed]}><View pointerEvents="none" style={styles.actionWash} /><View pointerEvents="none" style={[styles.actionGlow, { backgroundColor: action.tint }]} /><View pointerEvents="none" style={[styles.actionBar, { backgroundColor: action.accent }]} /><View style={[styles.actionIcon, { backgroundColor: action.tint, borderColor: action.accent }]}><Text style={styles.actionEmoji}>{action.icon}</Text></View><Text style={[styles.actionTitle, phone && styles.actionTitlePhone]}>{t(action.title)}</Text>{!phone ? <Text style={styles.actionBody}>{t(action.body)}</Text> : null}</Pressable>)}</View>
    <View style={styles.resourceHeading}><Text style={styles.heading}>{t('home.resourcesTitle')}</Text><Text style={styles.caption}>{t('home.resourcesBody')}</Text></View>
    <TabRail accessibilityLabel={t('home.resourcesTitle')} value={kind} onChange={(value) => { setKind(value as PublicResourceKind); setSubject(''); setStage(''); setLevel(''); setPage(1); }} items={(Object.keys(KINDS) as PublicResourceKind[]).map((value) => ({ value, label: `${KINDS[value].icon} ${t(KINDS[value].label)}` }))} />
    <ResourceFilters query={query} onQueryChange={(value) => { setQuery(value); setPage(1); }} count={loading ? undefined : filtered.length} facets={(['subject', 'stage', 'level'] as const).map((facet) => ({ key: facet, label: t(`resources.${facet}`), value: { subject, stage, level }[facet], allValue: '', allLabel: t(`resources.all${facet[0].toUpperCase()}${facet.slice(1)}s`), options: options(facet).map((value) => ({ value, label: value.replaceAll('_', ' ') })), onChange: (value: string) => { ({ subject: setSubject, stage: setStage, level: setLevel }[facet])(value); setPage(1); } }))} />
    {error ? <EmptyState title={t('home.loadFailed')} body={error} /> : loading ? <Text style={styles.caption}>{t('common.loading')}</Text> : visible.length ? <View style={styles.grid}>{visible.map((item) => <ResourceShowcaseCard key={`${item.kind}-${item.id}`} item={item} onPress={() => router.push({ pathname: '/resources', params: { scope: 'community', kind: item.kind, resourceId: String(item.id) } })} />)}</View> : <EmptyState title={t('home.noResources')} body={t('home.noResourcesBody')} />}
    {!loading && !error && filtered.length > 6 ? <Pagination page={Math.min(page, pages)} totalPages={pages} totalItems={filtered.length} onPageChange={setPage} /> : null}
  </>;
}

const styles = StyleSheet.create({
  heading: { color: colors.ink, fontSize: 20, fontWeight: '900', marginTop: 28, marginBottom: 12 },
  caption: { color: colors.muted, fontSize: 12, lineHeight: 18, marginBottom: 12 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 11 },
  actionsPhone: { gap: 10 },
  action: { flexGrow: 1, flexBasis: 235, minWidth: 210, minHeight: 135, borderWidth: 1, borderRadius: 18, padding: 16, overflow: 'hidden' },
  actionPhone: { flexBasis: '47%', minWidth: 0, minHeight: 0, aspectRatio: 1, padding: 13 },
  actionWash: { position: 'absolute', inset: 0, backgroundColor: colors.surface, opacity: 0.82 },
  actionGlow: { position: 'absolute', top: -62, right: -32, width: 170, height: 125, borderRadius: 999, opacity: 0.9 },
  actionBar: { position: 'absolute', left: 16, right: 16, top: 0, height: 4, borderBottomLeftRadius: 999, borderBottomRightRadius: 999, opacity: 0.75 },
  actionIcon: { width: 44, height: 44, borderRadius: 13, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  actionEmoji: { fontSize: 23 },
  actionTitle: { color: colors.ink, fontSize: 17, fontWeight: '900', marginTop: 13 },
  actionTitlePhone: { fontSize: 14, lineHeight: 18 },
  actionBody: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: 6 },
  pressed: { opacity: 0.75 },
  resourceHeading: { marginTop: 4 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 14 },
});
