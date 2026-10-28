/* eslint-disable react-hooks/set-state-in-effect */
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { BackLink } from '@/components/back-link';
import { AppShell } from '@/components/app-shell';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { Button, EmptyState, HelpIcon, LoadingState, Panel } from '@/components/ui';
import { canonicalSubjectKey } from '@/lib/subjects';
import { useAppPreferences } from '@/providers/app-preferences';
import type { ClassioRecord } from '@/services/classio-data';
import { getPublicResourcePreviewImages, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import { getStudentAssignmentForPractice, getStudentWorkspace, type StudentWorkspace } from '@/services/student-data';
import { logStudentRecommendation, logStudentRecommendationOpen } from '@/services/student-practice';
import { scoreStudentRecommendationCandidates } from '@/services/student-recommendation-ranking';
import { buildStudentRecommendationEligibility } from '@/services/student-recommendation-safety';
import { recommendationExcludedIds } from '@/services/student-recommendation-exclusions';
import { semanticTextAffinity } from '@/services/student-recommendation-semantic';
import { getStudentPublicPracticeResources } from '@/services/student-resource-access';
import { colors } from '@/theme';

const text = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value).trim() : '';

export default function StudentLessonTopicScreen() {
  const { t } = useAppPreferences();
  const { assignmentId, returnTo } = useLocalSearchParams<{ assignmentId?: string; returnTo?: string }>();
  const [assignment, setAssignment] = useState<ClassioRecord | null>(null);
  const [resources, setResources] = useState<PublicResource[]>([]);
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [resourcesError, setResourcesError] = useState('');
  const hydratedImages = useRef(new Set<string>());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    if (!assignmentId) { setError(t('student.practiceUnavailable')); setLoading(false); return; }
    setLoading(true); setError('');
    try {
      const row = await getStudentAssignmentForPractice(assignmentId);
      if (text(row.assignment_type) !== 'lesson_plan_topic') throw new Error(t('student.practiceUnavailable'));
      setAssignment(row);
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('student.loadFailed')); }
    finally { setLoading(false); }
  }, [assignmentId, t]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    let active = true;
    setResourcesLoading(true);
    setResourcesError('');
    void Promise.all([getStudentPublicPracticeResources(), getStudentWorkspace('home')])
      .then(([rows, value]) => { if (active) { setResources(rows); setWorkspace(value); } })
      .catch((reason) => { if (active) setResourcesError(reason instanceof Error ? reason.message : t('student.loadFailed')); })
      .finally(() => { if (active) setResourcesLoading(false); });
    return () => { active = false; };
  }, [t]);
  const recommendations = useMemo(() => {
    if (!assignment) return [];
    const subject = canonicalSubjectKey(assignment.subject_key || assignment.subject_label);
    const topic = text(assignment.topic || assignment.title);
    const excluded = recommendationExcludedIds(workspace);
    const assignedKeys = new Set((workspace?.assignments ?? []).filter((row) => row.source_record_id).map((row) => `${text(row.assignment_type)}:${text(row.source_record_id)}`));
    const related = resources.flatMap((resource) => {
      if (excluded.has(`${resource.kind}:${resource.id}`) || assignedKeys.has(`${resource.kind}:${resource.id}`)) return [];
      if (!['worksheet', 'exam', 'video'].includes(resource.kind) || canonicalSubjectKey(resource.subject) !== subject) return [];
      const affinity = semanticTextAffinity([resource.topic, resource.title, resource.description], [topic, text(assignment.title)]);
      return affinity >= 0.32 ? [{ resource, affinity }] : [];
    });
    const eligible = workspace ? buildStudentRecommendationEligibility(workspace) : () => true;
    const eligibleMatches = related.filter(({ resource }) => eligible(resource));
    const candidates = eligibleMatches.length ? eligibleMatches : related;
    const ranked = workspace ? scoreStudentRecommendationCandidates(candidates.map(({ resource }) => resource), workspace) : [];
    const scores = new Map(ranked.map(({ resource, score }) => [`${resource.kind}:${resource.id}`, score]));
    return candidates.filter(({ resource }) => !ranked.length || scores.has(`${resource.kind}:${resource.id}`))
      .sort((left, right) => (scores.get(`${right.resource.kind}:${right.resource.id}`) || 0) + right.affinity * 0.45
        - (scores.get(`${left.resource.kind}:${left.resource.id}`) || 0) - left.affinity * 0.45)
      .slice(0, 6).map(({ resource }) => resource);
  }, [assignment, resources, workspace]);
  useEffect(() => {
    if (resourcesLoading || !assignment || !recommendations.length) return;
    const topicId = Number(assignment.learning_program_topic_id) || undefined;
    void logStudentRecommendation(recommendations.map((resource) => ({ ...resource, learningProgramTopicId: topicId, recommendationReasonCodes: ['subject_match', 'topic_match'] })), 'student_lesson_topic').catch((reason) => console.warn('Lesson topic recommendation exposure failed', reason));
  }, [resourcesLoading, assignment, recommendations]);
  const assignedResources = useMemo(() => {
    if (!assignment || !workspace) return [];
    const subject = canonicalSubjectKey(assignment.subject_key || assignment.subject_label);
    const topic = text(assignment.topic || assignment.title);
    const matches = workspace.assignments.filter((row) => {
      const kind = text(row.assignment_type);
      if (!['worksheet', 'exam', 'video'].includes(kind) || canonicalSubjectKey(row.subject_key || row.subject_label) !== subject) return false;
      const direct = assignment.learning_program_topic_id && text(row.learning_program_topic_id) === text(assignment.learning_program_topic_id);
      return Boolean(direct || semanticTextAffinity([row.topic, row.title], [topic, assignment.title]) >= 0.5);
    });
    const seen = new Set<string>();
    return matches.filter((row) => { const key = `${text(row.assignment_type)}:${text(row.source_record_id || row.id)}`; if (seen.has(key)) return false; seen.add(key); return true; });
  }, [assignment, workspace]);
  useEffect(() => {
    const groups = new Map<PublicResourceKind, PublicResource[]>();
    recommendations.filter((resource) => resource.kind !== 'video' && !resource.imageUrl).forEach((resource) => {
      const key = `${resource.kind}:${resource.id}`;
      if (hydratedImages.current.has(key)) return;
      hydratedImages.current.add(key);
      groups.set(resource.kind, [...(groups.get(resource.kind) || []), resource]);
    });
    groups.forEach((items, kind) => {
      void getPublicResourcePreviewImages(kind, items.map((item) => item.id)).then((images) => {
        if (Object.keys(images).length) setResources((current) => current.map((resource) => images[resource.id] ? { ...resource, imageUrl: images[resource.id] } : resource));
      }).catch((reason) => console.warn('Assigned topic preview images unavailable', reason));
    });
  }, [recommendations]);
  const due = assignment?.due_at ? new Date(text(assignment.due_at)).toLocaleDateString() : '';
  return <AppShell title={t('student.smartPlan.assignedTopics')} eyebrow={t('student.learningSpace')}>
    <BackLink label={t(returnTo === 'student-study-plan' ? 'student.backToSmartPlan' : 'student.lessonTopic.backHome')} onPress={() => router.replace(returnTo === 'student-study-plan' ? '/student-study-plan' : '/student-home')} />
    {loading ? <LoadingState /> : error ? <EmptyState title={t('student.loadFailed')} body={error} action={<Button onPress={() => void load()}>{t('common.refresh')}</Button>} /> : assignment ? <Panel style={styles.card}>
      <Text style={styles.kicker}>📒 {t('student.smartPlan.lessonTopic')}</Text>
      <Text style={styles.title}>{text(assignment.title || assignment.topic || t('student.topic'))}</Text>
      <Text style={styles.meta}>{[assignment.subject_label || assignment.subject_key, due].map(text).filter(Boolean).join(' · ')}</Text>
      {assignment.topic && text(assignment.topic) !== text(assignment.title) ? <View style={styles.section}><Text style={styles.label}>{t('student.topic')}</Text><Text style={styles.body}>{text(assignment.topic)}</Text></View> : null}
      {assignment.teacher_note ? <View style={styles.section}><Text style={styles.label}>{t('student.lessonTopic.teacherNote')}</Text><Text style={styles.body}>{text(assignment.teacher_note)}</Text></View> : null}
      <Text style={styles.caption}>{t('student.lessonTopic.caption')}</Text>
    </Panel> : null}
    {assignment ? <View style={styles.resources}>
      {resourcesLoading ? <LoadingState /> : resourcesError ? <EmptyState title={t('student.loadFailed')} body={resourcesError} /> : <>
      {assignedResources.length ? <View style={styles.resourceSection}><Text style={styles.resourcesTitle}>{t('student.lessonTopic.teacherTasks')}</Text><View style={styles.grid}>{assignedResources.map((row) => {
        const kind = text(row.assignment_type) as PublicResourceKind;
        const item: PublicResource = { id: text(row.id), kind, title: text(row.title), subject: text(row.subject_label || row.subject_key), topic: text(row.topic), stage: '', level: '', author: '', description: text(row.teacher_note), imageUrl: '', createdAt: text(row.created_at), raw: row };
        return <ResourceShowcaseCard key={`assigned:${row.id}`} item={item} eyebrow={t('student.assignment')} description={text(row.teacher_note || row.topic)} onPress={() => router.push({ pathname: '/student-practice', params: { assignmentId: text(row.id), returnTo: 'student-lesson-topic', topicAssignmentId: assignmentId, topicReturnTo: returnTo || '' } })} />;
      })}</View></View> : null}
      {recommendations.length ? <View style={styles.resourceSection}><View style={styles.resourcesTitleWithHelp}><Text style={styles.resourcesTitle}>{t('student.lessonTopic.recommended')}</Text><HelpIcon title={t('transparency.howRecommendationsWork')}>{[t('transparency.studentScope'), t('transparency.studentChallenge')].join('\n\n')}</HelpIcon></View><Text style={styles.resourcesHint}>{t('student.lessonTopic.resourcesHint')}</Text><View style={styles.grid}>{recommendations.map((resource) => <ResourceShowcaseCard key={`${resource.kind}:${resource.id}`} item={resource} eyebrow={t('student.forYou')} description={resource.topic || resource.description || t('resources.noDescription')} onPress={() => { void logStudentRecommendationOpen({ ...resource, learningProgramTopicId: Number(assignment.learning_program_topic_id) || undefined }, 'student_lesson_topic').catch((reason) => console.warn('Lesson topic recommendation open failed', reason)); router.push({ pathname: '/student-practice', params: { kind: resource.kind, resourceId: resource.id, returnTo: 'student-lesson-topic', topicAssignmentId: assignmentId, topicReturnTo: returnTo || '' } }); }} />)}</View></View> : null}
      {!assignedResources.length && !recommendations.length ? <Text style={styles.caption}>{t('student.lessonTopic.noResources')}</Text> : null}
      </>}
    </View> : null}
  </AppShell>;
}

const styles = StyleSheet.create({
  card: { marginTop: 18, gap: 10 },
  kicker: { color: colors.primary, fontSize: 10, fontWeight: '900' },
  title: { color: colors.ink, fontSize: 22, lineHeight: 29, fontWeight: '900' },
  meta: { color: colors.muted, fontSize: 11 },
  section: { marginTop: 9, gap: 5 },
  label: { color: colors.primary, fontSize: 10, fontWeight: '900' },
  body: { color: colors.ink, fontSize: 14, lineHeight: 21 },
  caption: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: 10 },
  resources: { marginTop: 28, gap: 28 }, resourceSection: { gap: 14 },
  resourcesTitleWithHelp: { flexDirection: 'row', alignItems: 'center', gap: 4 }, resourcesTitle: { color: colors.ink, fontSize: 20, fontWeight: '900' },
  resourcesHint: { color: colors.muted, fontSize: 11, marginTop: -8 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
});
