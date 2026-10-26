/* eslint-disable react-hooks/exhaustive-deps, react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { router, useIsFocused } from 'expo-router';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { AppShell } from '@/components/app-shell';
import { Button, EmptyState, LoadingState } from '@/components/ui';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import { useHomeIntro } from '@/providers/home-intro-provider';
import { getPublicResourcePreviewImages, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import { getStudentWorkspace, type StudentWorkspace } from '@/services/student-data';
import { getStudentPublicPracticeResources } from '@/services/student-resource-access';
import { logStudentRecommendation, logStudentRecommendationOpen } from '@/services/student-practice';
import { recommendationExcludedIds } from '@/services/student-recommendation-exclusions';
import { buildStudentRecommendationEligibility } from '@/services/student-recommendation-safety';
import { selectScoredStudentRecommendations } from '@/services/student-recommendation-selection';
import { scoreStudentRecommendationCandidates } from '@/services/student-recommendation-ranking';
import { colors } from '@/theme';

const CARDS = [{ href: '/student-practice', icon: '🧠', title: 'student.practice', body: 'student.practiceBody', color: colors.primary, tint: colors.primarySoft }, { href: '/student-study-plan', icon: '📚', title: 'student.studyPlan', body: 'student.studyPlanBody', color: colors.success, tint: colors.successSoft }, { href: '/student-assignments', icon: '🗂️', title: 'student.assignments', body: 'student.assignmentsBody', color: colors.orange, tint: colors.orangeSoft }, { href: '/student-find-teacher', icon: '🔍', title: 'student.findTeacher', body: 'student.findTeacherBody', color: colors.violet, tint: colors.violetSoft }] as const;

function withinHomeDeadline<T>(request: Promise<T>, message: string): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  return Promise.race([
    request,
    new Promise<T>((_, reject) => { timeout = setTimeout(() => reject(new Error(message)), 18000); }),
  ]).finally(() => clearTimeout(timeout));
}

export default function StudentHomeScreen() {
  const { markReady } = useHomeIntro();
  const { width } = useWindowDimensions();
  const phone = width < 560;
  const isFocused = useIsFocused();
  const { profile } = useAuth(); const { t } = useAppPreferences(); const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null); const [resources, setResources] = useState<PublicResource[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [now] = useState(() => Date.now());
  useEffect(() => { markReady('/student-home', !loading); }, [loading, markReady]);
  const hydratedImages = useRef(new Set<string>());
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const message = t('student.loadFailed');
    const [student, publicResources] = await Promise.allSettled([
      withinHomeDeadline(getStudentWorkspace('home'), message),
      withinHomeDeadline(getStudentPublicPracticeResources(), message),
    ]);
    if (student.status === 'fulfilled') setWorkspace(student.value);
    if (publicResources.status === 'fulfilled') setResources(publicResources.value);
    if (student.status === 'rejected') setError(student.reason instanceof Error ? student.reason.message : message);
    else if (publicResources.status === 'rejected') setError(publicResources.reason instanceof Error ? publicResources.reason.message : message);
    setLoading(false);
  }, [t]);
  useEffect(() => { if (isFocused) void load(); }, [isFocused, load]);
  const recommendations = useMemo(() => {
    const excluded = recommendationExcludedIds(workspace);
    const eligible = buildStudentRecommendationEligibility(workspace);
    const ranked = scoreStudentRecommendationCandidates(resources.filter((row) => ['worksheet', 'exam', 'video'].includes(row.kind) && !excluded.has(`${row.kind}:${row.id}`) && eligible(row)), workspace);
    return selectScoredStudentRecommendations(ranked, workspace, 6).slice(0, 6);
  }, [resources, workspace]);
  const recommendationReason = (item: (typeof recommendations)[number]) => item.recommendationReason
    ? t(item.recommendationReason.key, item.recommendationReason.params) : t('student.matchesLearning');
  const visibleRecommendations = recommendations;
  useEffect(() => { if (!loading && !error && visibleRecommendations.length) void logStudentRecommendation(visibleRecommendations, 'student_home').catch((reason) => console.warn('Student recommendation exposure failed', reason)); }, [loading, error, visibleRecommendations.map((row) => `${row.kind}:${row.id}:${row.learningProgramAssignmentId || 0}:${row.learningProgramTopicId || 0}`).join('|')]);
  useEffect(() => {
    const groups = new Map<PublicResourceKind, PublicResource[]>();
    recommendations.filter((item) => item.kind !== 'video' && !item.imageUrl && !hydratedImages.current.has(`${item.kind}:${item.id}`)).forEach((item) => {
      hydratedImages.current.add(`${item.kind}:${item.id}`);
      groups.set(item.kind, [...(groups.get(item.kind) ?? []), item]);
    });
    groups.forEach((items, resourceKind) => {
      void getPublicResourcePreviewImages(resourceKind, items.map((item) => item.id)).then((images) => {
        if (!Object.keys(images).length) return;
        setResources((current) => current.map((item) => images[item.id] ? { ...item, imageUrl: images[item.id] } : item));
      });
    });
  }, [recommendations]);
  const urgent = (workspace?.assignments ?? []).find((row) => !['submitted', 'graded', 'completed', 'cancelled'].includes(String(row.status)) && row.due_at && new Date(String(row.due_at)).getTime() <= now + 3 * 86400000) || (workspace?.assignments ?? []).find((row) => String(row.status) === 'assigned');
  const drafts = (workspace?.sessions ?? []).filter((row) => String(row.status) === 'in_progress' && ['worksheet', 'exam'].includes(String(row.source_type))).slice(0, 3);
  const firstName = String(profile?.display_name || profile?.username || t('student.learner')).split(' ')[0];
  const openRecommendation = (item: PublicResource) => {
    void logStudentRecommendationOpen(item, 'student_home').catch((reason) => console.warn('Student recommendation open failed', reason));
    router.push({ pathname: '/student-practice', params: { kind: item.kind, resourceId: item.id, returnTo: 'student-home' } });
  };
  const openUrgent = () => {
    if (!urgent) return;
    const assignmentId = String(urgent.id);
    const assignmentType = String(urgent.assignment_type);
    if (assignmentType === 'lesson_plan_topic') {
      router.push({ pathname: '/student-lesson-topic' as never, params: { assignmentId } });
      return;
    }
    router.push({ pathname: '/student-practice', params: { kind: assignmentType, assignmentId, returnTo: 'student-assignments' } });
  };
  return <AppShell title={t('student.welcome', { name: firstName })} eyebrow={t('student.commandCenter')}><Text style={styles.intro}>{t('student.welcomeBody')}</Text><View style={[styles.cardGrid, phone && styles.cardGridPhone]}>{CARDS.map((card) => <Pressable key={card.href} accessibilityRole="button" accessibilityLabel={t(card.title)} onPress={() => router.push(card.href)} style={({ pressed }) => [styles.navCard, phone && styles.navCardPhone, { backgroundColor: card.tint, borderColor: card.color }, pressed && styles.cardPressed]}><View pointerEvents="none" style={styles.navWash} /><View pointerEvents="none" style={[styles.navGlow, phone && styles.navGlowPhone, { backgroundColor: card.tint }]} /><View pointerEvents="none" style={[styles.navBar, { backgroundColor: card.color }]} /><View style={[styles.navIconShell, phone && styles.navIconShellPhone, { backgroundColor: card.tint, borderColor: card.color }]}><Text style={[styles.navIcon, phone && styles.navIconPhone]}>{card.icon}</Text></View><Text numberOfLines={2} style={[styles.navTitle, phone && styles.navTitlePhone]}>{t(card.title)}</Text>{!phone ? <Text style={styles.navBody}>{t(card.body)}</Text> : null}</Pressable>)}</View>{urgent ? <Pressable onPress={openUrgent} style={styles.urgent}><View style={styles.urgentCopy}><Text style={styles.urgentKicker}>{t('student.reviewNow')}</Text><Text style={styles.urgentTitle}>{String(urgent.title || t('student.assignment'))}</Text><Text style={styles.urgentBody}>{[urgent.subject_label || urgent.subject_key, urgent.topic, urgent.due_at ? new Date(String(urgent.due_at)).toLocaleDateString() : ''].filter(Boolean).join(' · ')}</Text></View><Text style={styles.urgentArrow}>→</Text></Pressable> : null}{drafts.length ? <View style={styles.draftTray}><Text style={styles.sectionTitle}>{t("student.continuePractice")}</Text><Text style={styles.sectionBody}>{t("student.continuePracticeBody")}</Text><View style={styles.draftGrid}>{drafts.map((draft) => <Pressable key={String(draft.id)} onPress={() => router.push({ pathname: "/student-practice", params: { draftSessionId: String(draft.id), returnTo: "student-home" } })} style={styles.draftCard}><Text style={styles.draftKind}>{String(draft.source_type)}</Text><Text style={styles.draftTitle}>{String(draft.title || t("student.practice"))}</Text><Text style={styles.draftMeta}>{[draft.subject, draft.topic].filter(Boolean).join(" · ")}</Text><Text style={styles.draftAction}>▶ {t("student.resumePractice")}</Text></Pressable>)}</View></View> : null}{loading ? <LoadingState /> : error ? <EmptyState title={t('student.loadFailed')} body={error} action={<Button onPress={() => void load()}>{t('common.refresh')}</Button>} /> : <><View style={styles.sectionTop}><View><Text style={styles.sectionTitle}>{t('student.recommended')}</Text><Text style={styles.sectionBody}>{t('student.recommendedBody')}</Text></View></View>{visibleRecommendations.length ? <View style={styles.resourceGrid}>{visibleRecommendations.map((item) => <ResourceShowcaseCard key={`${item.kind}-${item.id}-${item.learningProgramAssignmentId || 0}-${item.learningProgramTopicId || 0}`} item={item} onPress={() => openRecommendation(item)} eyebrow={t('student.forYou')} description={recommendationReason(item)} />)}</View> : <EmptyState title={t('student.noRecommendations')} body={t('student.noRecommendationsBody')} action={<Button secondary onPress={() => router.push('/student-practice')}>{t('student.seePractice')}</Button>} />}</>}</AppShell>;
}
const styles = StyleSheet.create({ draftTray: { marginBottom: 22 }, draftGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 12 }, draftCard: { flexGrow: 1, flexBasis: 270, minWidth: 240, maxWidth: 530, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 16, padding: 15 }, draftKind: { color: colors.primary, fontSize: 9, fontWeight: "900", textTransform: "uppercase" }, draftTitle: { color: colors.ink, fontSize: 15, fontWeight: "900", marginTop: 5 }, draftMeta: { color: colors.muted, fontSize: 11, marginTop: 5 }, draftAction: { color: colors.primary, fontSize: 11, fontWeight: "900", marginTop: 12 }, cardPressed: { opacity: 0.75, transform: [{ scale: 0.99 }] }, intro: { color: colors.muted, fontSize: 16, lineHeight: 24, maxWidth: 680, marginBottom: 20 }, urgent: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 14, minWidth: 0, backgroundColor: colors.orangeSoft, borderWidth: 1, borderColor: colors.orange, borderRadius: 17, padding: 17, marginBottom: 16 }, urgentCopy: { flex: 1, minWidth: 0 }, urgentKicker: { color: colors.orange, fontSize: 9, fontWeight: '900', textTransform: 'uppercase' }, urgentTitle: { color: colors.ink, fontSize: 17, fontWeight: '900', marginTop: 4, flexShrink: 1, flexWrap: 'wrap' }, urgentBody: { color: colors.muted, fontSize: 10, marginTop: 4, flexShrink: 1, flexWrap: 'wrap' }, urgentArrow: { color: colors.orange, fontSize: 24, fontWeight: '900', flexShrink: 0 }, notifications: { marginBottom: 18 }, notificationList: { gap: 8 }, notification: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 13 }, notificationIcon: { fontSize: 20 }, notificationText: { flex: 1, color: colors.ink, fontSize: 12, lineHeight: 18, fontWeight: '700' }, notificationArrow: { color: colors.primary, fontSize: 17, fontWeight: '900' }, notificationClear: { color: colors.success, fontSize: 12, fontWeight: '800' }, cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 26 }, cardGridPhone: { gap: 10, marginBottom: 16 }, navCard: { flex: 1, minWidth: 210, minHeight: 168, borderWidth: 1, borderRadius: 20, overflow: 'hidden', padding: 18, alignItems: 'flex-start' }, navCardPhone: { flexBasis: '47%', minWidth: 0, minHeight: 0, aspectRatio: 1, padding: 14, borderRadius: 18 }, navWash: { position: 'absolute', inset: 0, backgroundColor: colors.surface, opacity: 0.82 }, navGlow: { position: 'absolute', top: -70, right: -35, width: 180, height: 145, borderRadius: 999, opacity: 0.92 }, navGlowPhone: { top: -50, right: -45, width: 130, height: 115 }, navBar: { position: 'absolute', left: 18, right: 18, top: 0, height: 4, borderBottomLeftRadius: 999, borderBottomRightRadius: 999, opacity: 0.75 }, navIconShell: { width: 48, height: 48, borderRadius: 15, borderWidth: 1, alignItems: 'center', justifyContent: 'center' }, navIconShellPhone: { width: 42, height: 42, borderRadius: 13 }, navIcon: { fontSize: 24 }, navIconPhone: { fontSize: 21 }, navTitle: { color: colors.ink, fontSize: 17, fontWeight: '900', marginTop: 12, textAlign: 'left' }, navTitlePhone: { fontSize: 14, lineHeight: 18, marginTop: 10 }, navBody: { color: colors.muted, fontSize: 11, lineHeight: 17, textAlign: 'center', marginTop: 7 }, open: { fontSize: 10, fontWeight: '900', marginTop: 'auto', paddingTop: 10 }, sectionTop: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }, sectionTitle: { color: colors.ink, fontSize: 19, fontWeight: '900' }, sectionBody: { color: colors.muted, fontSize: 11, marginTop: 4 }, resourceGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, resourceCard: { flexGrow: 1, flexBasis: 280, minWidth: 250, maxWidth: 360, borderRadius: 16, overflow: 'hidden', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line }, image: { width: '100%', height: 150 }, imageFallback: { height: 150, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primarySoft }, fallbackIcon: { fontSize: 34 }, resourceCopy: { padding: 14 }, kind: { color: colors.primary, fontSize: 8, fontWeight: '900', textTransform: 'uppercase' }, resourceTitle: { color: colors.ink, fontSize: 14, lineHeight: 19, fontWeight: '900', marginTop: 5 }, resourceMeta: { color: colors.muted, fontSize: 9, marginTop: 7, textTransform: 'capitalize' }, resourceReason: { color: colors.violet, fontSize: 10, marginTop: 7 } });
