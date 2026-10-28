/* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useIsFocused, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { ActionFeedback, Button, Disclosure, EmptyState, HelpIcon, LoadingState, Pagination, Panel, SelectField, TabRail } from '@/components/ui';
import { programTopics } from '@/lib/learning-program-topics';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import type { ClassioRecord } from '@/services/classio-data';
import { getPublicResourcePreviewImages, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import { getStudentPublicPracticeResources } from '@/services/student-resource-access';
import { getStudentWorkspace, setStudentNeedsMorePractice, type StudentWorkspace } from '@/services/student-data';
import { logStudentRecommendation, logStudentRecommendationOpen } from '@/services/student-practice';
import { selectSmartPlanResources } from '@/services/student-smart-plan-recommendations';
import { passedMissionResourceIds, smartPlanMissionComplete, smartPlanMissionResources } from '@/services/student-smart-plan-missions';
import { recommendationExcludedIds } from '@/services/student-recommendation-exclusions';
import { localSmartPlanDay, selectSmartPlanTaskTemplates, smartPlanGoalOptions, smartPlanWeeklyFocus, syncSmartPlanRewards } from '@/services/student-smart-plan-tasks';
import { colors } from '@/theme';

type Section = 'plan' | 'programs' | 'topics';
type SmartTask = { id: string; title: string; detail: string; minutes: number; category: string; xp: number; done: boolean };
type SmartPlan = { subject: string; goal: string; minutes: number; generatedFor: string; tasks: SmartTask[]; points: number; streak: number; lastCompletionDate?: string; anchorSignature?: string };

const DEFAULT_SUBJECTS = ['english', 'spanish', 'mathematics', 'science', 'music', 'study_skills', 'other'];
const MINUTES = [15, 20, 30, 45, 60];
const today = localSmartPlanDay;
const text = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value).trim() : '';
const normalize = (value: unknown) => text(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_|_$/g, '');

function programAnchorSignature(subject: string, workspace: StudentWorkspace | null) {
  const assignment = (workspace?.programs ?? []).find((row) => normalize((row.program as ClassioRecord | undefined)?.subject) === subject) ?? workspace?.programs?.[0];
  if (!assignment) return '';
  const topics = programTopics((assignment.program || {}) as ClassioRecord, (workspace?.topics ?? []).filter((row) => text(row.program_id) === text(assignment.program_id)));
  const done = new Set((workspace?.progress ?? []).filter((row) => text(row.assignment_id) === text(assignment.id) && Boolean(row.teacher_done)).map((row) => text(row.topic_id)));
  return JSON.stringify([assignment.id, assignment.program_id, topics.map((row) => [row.id, done.has(text(row.id))])]);
}

function generatedTasks(plan: Pick<SmartPlan, 'subject' | 'goal' | 'minutes'>, workspace: StudentWorkspace | null, t: (key: string, params?: Record<string, string | number>) => string): SmartTask[] {
  const assignment = (workspace?.programs ?? []).find((row) => normalize((row.program as ClassioRecord | undefined)?.subject) === plan.subject) ?? workspace?.programs?.[0];
  const assignmentId = text(assignment?.id); const programId = text(assignment?.program_id);
  const progress = new Map((workspace?.progress ?? []).filter((row) => text(row.assignment_id) === assignmentId).map((row) => [text(row.topic_id), row]));
  const resolvedTopics = programTopics((assignment?.program || {}) as ClassioRecord, (workspace?.topics ?? []).filter((topic) => text(topic.program_id) === programId));
  const count = plan.minutes <= 15 ? 3 : plan.minutes <= 30 ? 4 : 5;
  const pending = resolvedTopics.filter((topic) => !Boolean(progress.get(text(topic.id))?.teacher_done)).slice(0, count);
  const chosen = pending.length ? pending : resolvedTopics.slice(-count);
  if (chosen.length) return chosen.map((topic, index) => ({ id: `${today()}_program_${text(topic.id)}`, title: t('student.smartPlan.programTask', { number: Number(topic.topic_number || index + 1), title: text(topic.title) }), detail: text(topic.student_summary || topic.lesson_focus || topic.subtopic || t('student.smartPlan.programTaskFallback')), minutes: Math.max(5, Math.round(plan.minutes / chosen.length)), category: 'program', xp: 15, done: false }));
  return selectSmartPlanTaskTemplates(plan.subject, plan.goal, plan.minutes).map((item, index) => ({ id: `${today()}_${index + 1}`, title: t(`student.smartPlan.${item.titleKey}`), detail: t('student.smartPlan.taskDetail', { minutes: item.minutes }), minutes: item.minutes, category: item.category, xp: item.xp, done: false }));
}

export default function StudentStudyPlanScreen() {
  const { t } = useAppPreferences(); const { user } = useAuth(); const router = useRouter(); const isFocused = useIsFocused(); const params = useLocalSearchParams<{ missionId?: string }>();
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null); const [resources, setResources] = useState<PublicResource[]>([]);
  const hydratedImages = useRef(new Set<string>());
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [section, setSection] = useState<Section>('plan');
  const [page, setPage] = useState(1); const [topicPage, setTopicPage] = useState(1); const [busy, setBusy] = useState(''); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error'); const [messageTarget, setMessageTarget] = useState('plan'); const [openMissionId, setOpenMissionId] = useState(params.missionId || '');
  const [plan, setPlan] = useState<SmartPlan>({ subject: 'english', goal: 'general_practice', minutes: 20, generatedFor: '', tasks: [], points: 0, streak: 0 });
  const storageKey = `@classio/smart-plan/${user?.id || 'student'}`;
  const load = async () => {
    setLoading(true);
    const [student, publicResources, saved] = await Promise.allSettled([getStudentWorkspace('practice', true), getStudentPublicPracticeResources(), AsyncStorage.getItem(storageKey)]);
    const loadedWorkspace = student.status === 'fulfilled' ? student.value : null;
    if (loadedWorkspace) setWorkspace(loadedWorkspace);
    if (publicResources.status === 'fulfilled') setResources(publicResources.value);
    if (saved.status === 'fulfilled' && saved.value) {
      try {
        const stored = JSON.parse(saved.value) as SmartPlan;
        if (stored && Array.isArray(stored.tasks)) {
          const anchorSignature = loadedWorkspace ? programAnchorSignature(stored.subject, loadedWorkspace) : stored.anchorSignature;
          const refresh = Boolean(stored.generatedFor && loadedWorkspace && (stored.generatedFor !== today() || (stored.anchorSignature ?? '') !== anchorSignature));
          const current = refresh && loadedWorkspace ? { ...stored, generatedFor: today(), tasks: generatedTasks(stored, loadedWorkspace, t), anchorSignature } : stored;
          if (loadedWorkspace && publicResources.status === 'fulfilled') {
            const passed = passedMissionResourceIds(loadedWorkspace);
            const tasks = current.tasks.map((task) => ({ ...task, done: smartPlanMissionComplete(smartPlanMissionResources(publicResources.value, current.subject, task, current.goal, loadedWorkspace), passed) }));
            setPlan({ ...current, tasks, ...syncSmartPlanRewards(current, current.tasks, tasks) });
          } else setPlan(current);
        }
      } catch { /* ignore malformed local legacy state */ }
    }
    const failed = student.status === 'rejected' ? student.reason : publicResources.status === 'rejected' ? publicResources.reason : null;
    setError(failed instanceof Error ? failed.message : failed ? t('student.loadFailed') : '');
    setLoading(false);
  };
  useEffect(() => { if (isFocused) void load(); }, [storageKey, isFocused]);
  useEffect(() => { if (!loading) void AsyncStorage.setItem(storageKey, JSON.stringify(plan)); }, [plan, loading, storageKey]);

  const programs = workspace?.programs ?? []; const programPages = Math.max(1, programs.length); const shownPrograms = programs.slice(Math.min(page, programPages) - 1, Math.min(page, programPages));
  const assignedTopics = (workspace?.assignments ?? []).filter((row) => text(row.assignment_type) === 'lesson_plan_topic'); const topicPages = Math.max(1, Math.ceil(assignedTopics.length / 18)); const shownTopics = assignedTopics.slice((Math.min(topicPage, topicPages) - 1) * 18, Math.min(topicPage, topicPages) * 18);
  const completedTasks = plan.tasks.filter((task) => task.done).length; const planPct = plan.tasks.length ? Math.round(completedTasks / plan.tasks.length * 100) : 0;
  const availableSubjects = useMemo(() => [...new Set([...DEFAULT_SUBJECTS, ...programs.map((row) => normalize((row.program as ClassioRecord | undefined)?.subject)).filter(Boolean), ...(workspace?.assignments ?? []).map((row) => normalize(row.subject_key || row.subject_label)).filter(Boolean)])], [programs, workspace]);
  const recommendations = useMemo(() => { const excluded = recommendationExcludedIds(workspace); return selectSmartPlanResources(resources.filter((resource) => !excluded.has(`${resource.kind}:${resource.id}`)), plan.subject, plan.tasks, 6, plan.goal); }, [resources, plan.subject, plan.tasks, plan.goal, workspace]);
  const passedMissions = useMemo(() => passedMissionResourceIds(workspace), [workspace]);
  const openMission = plan.tasks.find((task) => task.id === openMissionId);
  const missionResources = useMemo(() => openMission ? smartPlanMissionResources(resources, plan.subject, openMission, plan.goal, workspace) : [], [resources, plan.subject, openMission, plan.goal, workspace]);
  useEffect(() => {
    if (!isFocused || loading || section !== 'plan' || !recommendations.length) return;
    void logStudentRecommendation(recommendations.map((resource) => ({ ...resource, recommendationReasonCodes: ['smart_plan_match'] })), 'student_study_plan').catch((reason) => console.warn('Study plan recommendation exposure failed', reason));
  }, [isFocused, loading, section, recommendations]);
  useEffect(() => {
    if (!isFocused || loading || section !== 'plan' || !openMissionId || !missionResources.length) return;
    void logStudentRecommendation(missionResources.map((resource) => ({ ...resource, recommendationReasonCodes: ['mission_match'] })), 'student_study_plan_mission').catch((reason) => console.warn('Study plan mission exposure failed', reason));
  }, [isFocused, loading, section, openMissionId, missionResources]);
  useEffect(() => {
    const groups = new Map<PublicResourceKind, PublicResource[]>();
    recommendations.filter((resource) => resource.kind !== 'video' && !resource.imageUrl).forEach((resource) => {
      const key = `${resource.kind}:${resource.id}`;
      if (hydratedImages.current.has(key)) return;
      hydratedImages.current.add(key);
      groups.set(resource.kind, [...(groups.get(resource.kind) ?? []), resource]);
    });
    groups.forEach((items, kind) => {
      void getPublicResourcePreviewImages(kind, items.map((item) => item.id)).then((images) => {
        if (Object.keys(images).length) setResources((current) => current.map((resource) => images[resource.id] ? { ...resource, imageUrl: images[resource.id] } : resource));
      });
    });
  }, [recommendations]);
  const generatePlan = () => { const tasks = generatedTasks(plan, workspace, t).map((task) => ({ ...task, done: smartPlanMissionComplete(smartPlanMissionResources(resources, plan.subject, task, plan.goal, workspace), passedMissions) })); setPlan((current) => ({ ...current, generatedFor: today(), tasks, anchorSignature: programAnchorSignature(current.subject, workspace), ...syncSmartPlanRewards(current, current.tasks, tasks) })); setOpenMissionId(''); setMessageTarget('plan'); setMessageTone('success'); setMessage(t('student.smartPlan.generated')); };
  const requestPractice = async (assignmentId: string, topicId: string, current: boolean) => { const key = `${assignmentId}:${topicId}`; setMessageTarget(key); setBusy(key); setMessage(''); try { await setStudentNeedsMorePractice(assignmentId, topicId, !current); setWorkspace(await getStudentWorkspace('practice', true)); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceRequestFailed')); } finally { setBusy(''); } };

  const renderPrograms = () => !shownPrograms.length ? <EmptyState title={t('student.noPrograms')} body={t('student.noProgramsBody')} /> : <>
    {shownPrograms.map((assignment, index) => {
      const assignmentId = text(assignment.id || index);
      const program = (assignment.program || {}) as ClassioRecord;
      const topics = programTopics(program, (workspace?.topics ?? []).filter((topic) => text(topic.program_id) === text(assignment.program_id)));
      const progress = (workspace?.progress ?? []).filter((row) => text(row.assignment_id) === assignmentId);
      const progressMap = new Map(progress.map((row) => [text(row.topic_id), row]));
      const isTopicDone = (topic: ClassioRecord) => Boolean(progressMap.get(text(topic.id))?.teacher_done);
      const done = topics.filter(isTopicDone).length;
      const pct = topics.length ? Math.round(done / topics.length * 100) : 0;
      const units = [...new Set(topics.map((topic) => Number(topic.unit_number || 0)))];
      return <Panel key={assignmentId} style={styles.program}>
        <View style={styles.hero}><View style={styles.heroCopy}><Text style={styles.kicker}>{t('student.assignedProgram')}</Text><Text style={styles.title}>{text(program.title || t('student.studyPlan'))}</Text><Text style={styles.subject}>{[program.subject, program.learner_stage, program.level_or_band].filter(Boolean).join(' · ')}</Text><Text style={styles.body}>{text(program.program_overview || assignment.teacher_note || t('student.programReady'))}</Text></View><View style={styles.score}><Text style={styles.scoreValue}>{pct}%</Text><Text style={styles.label}>{done}/{topics.length}</Text></View></View>
        <View style={styles.track}><View style={[styles.fill, { width: `${pct}%` }]} /></View>
        <Text style={styles.progress}>{t('student.progressCount', { done, total: topics.length })}</Text>
        {units.map((unitNumber, unitIndex) => {
          const unitTopics = topics.filter((topic) => Number(topic.unit_number || 0) === unitNumber);
          return <Disclosure key={`${assignmentId}-${unitNumber}`} title={t('student.unitNumber', { number: unitNumber || unitIndex + 1 })} summary={t('student.unitProgress', { done: unitTopics.filter(isTopicDone).length, total: unitTopics.length })} defaultOpen={unitIndex === 0} style={styles.unit}>
            {unitTopics.map((topic) => {
              const isDone = isTopicDone(topic);
              const topicId = text(topic.id);
              const needsPractice = Boolean(progressMap.get(topicId)?.student_done);
              const isBusy = busy === `${assignmentId}:${topicId}`;
              return <View key={text(topic.id)} style={[styles.topic, isDone && styles.topicDone]}>
                <View style={[styles.status, isDone && styles.statusDone]}><Text style={styles.statusText}>{isDone ? '✓' : '○'}</Text></View>
                <View style={styles.topicCopy}><Text style={[styles.topicTitle, isDone && styles.topicTitleDone]}>{t('student.topicNumber', { number: Number(topic.topic_number || 0) })}: {text(topic.title || t('student.topic'))}</Text>{topic.student_summary || topic.lesson_focus || topic.subtopic ? <Text style={styles.topicSummary}>{text(topic.student_summary || topic.lesson_focus || topic.subtopic)}</Text> : null}{needsPractice ? <Text style={styles.practiceBadge}>{t('student.needsPractice')}</Text> : null}</View>
                {isDone ? <View style={styles.practiceRequest}><Button secondary disabled={isBusy} onPress={() => void requestPractice(assignmentId, topicId, needsPractice)}>{isBusy ? t('common.saving') : needsPractice ? t('student.cancelPracticeRequest') : t('student.requestPractice')}</Button>{messageTarget === `${assignmentId}:${topicId}` && messageTone === 'error' ? <ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} /> : null}</View> : null}
              </View>;
            })}
          </Disclosure>;
        })}
      </Panel>;
    })}
    <Pagination page={Math.min(page, programPages)} totalPages={programPages} totalItems={programs.length} onPageChange={setPage} />
  </>;

  return <AppShell title={t('student.smartPlan.title')} eyebrow={t('student.learningSpace')}>
    <TabRail accessibilityLabel={t('student.smartPlan.title')} value={section} onChange={setSection} items={[{ value: 'plan', label: `✨ ${t('student.smartPlan.title')}` }, { value: 'programs', label: `📚 ${t('student.smartPlan.assignedPrograms')}` }, { value: 'topics', label: `📒 ${t('student.smartPlan.assignedTopics')}` }]} />

    {loading ? <LoadingState /> : error ? <EmptyState title={t('student.loadFailed')} body={error} /> : section === 'programs' ? renderPrograms() : section === 'topics' ? <>{!shownTopics.length ? <EmptyState title={t('student.smartPlan.noTopics')} body={t('student.smartPlan.noTopicsBody')} /> : <View style={styles.topicCards}>{shownTopics.map((row) => <Pressable key={text(row.id)} accessibilityRole="button" onPress={() => router.push({ pathname: '/student-lesson-topic' as never, params: { assignmentId: text(row.id), returnTo: 'student-study-plan' } })} style={({ pressed }) => [styles.topicCard, styles.topicCardSurface, pressed && styles.topicCardPressed]}><Text style={styles.kicker}>📒 {t('student.smartPlan.lessonTopic')}</Text><Text style={styles.topicCardTitle}>{text(row.title || t('student.topic'))}</Text><Text style={styles.body}>{[row.subject_label || row.subject_key, row.topic, row.created_at ? new Date(String(row.created_at)).toLocaleDateString() : ''].filter(Boolean).join(' · ')}</Text>{row.teacher_note ? <Text style={styles.topicSummary}>{text(row.teacher_note)}</Text> : null}</Pressable>)}</View>}<Pagination page={Math.min(topicPage, topicPages)} totalPages={topicPages} totalItems={assignedTopics.length} onPageChange={setTopicPage} /></> : <>
      <Panel style={styles.setup}><View style={styles.sectionHeading}><View><Text style={styles.sectionTitle}>{t('student.smartPlan.setup')}</Text><Text style={styles.body}>{t('student.smartPlan.setupBody')}</Text></View><Text style={styles.planDate}>{plan.generatedFor || t('student.smartPlan.notGenerated')}</Text></View><View style={styles.selects}><SelectField label={t('student.smartPlan.subject')} value={plan.subject} options={availableSubjects.map((value) => ({ value, label: t(`student.smartPlan.subject.${value}`) === `student.smartPlan.subject.${value}` ? value.replaceAll('_', ' ') : t(`student.smartPlan.subject.${value}`) }))} onChange={(subject) => setPlan((current) => ({ ...current, subject, goal: smartPlanGoalOptions(subject).includes(current.goal) ? current.goal : smartPlanGoalOptions(subject)[0] }))} /><SelectField label={t('student.smartPlan.focus')} value={plan.goal} options={smartPlanGoalOptions(plan.subject).map((value) => ({ value, label: t(`student.smartPlan.goal.${value}`) }))} onChange={(goal) => setPlan((current) => ({ ...current, goal }))} /><SelectField label={t('student.smartPlan.time')} value={String(plan.minutes)} options={MINUTES.map((value) => ({ value: String(value), label: t('student.smartPlan.minutes', { minutes: value }) }))} onChange={(minutes) => setPlan((current) => ({ ...current, minutes: Number(minutes) }))} /></View><Button onPress={generatePlan}>✨ {plan.tasks.length ? t('student.smartPlan.regenerate') : t('student.smartPlan.generate')}</Button>{messageTarget === 'plan' ? <ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} /> : null}</Panel>
      {!plan.tasks.length ? <EmptyState title={t('student.smartPlan.empty')} body={t('student.smartPlan.emptyBody')} /> : <>
        <View style={styles.metrics}><Panel style={styles.metric}><Text style={styles.value}>{Math.max(1, Math.floor(plan.points / 100) + 1)}</Text><Text style={styles.label}>{t('student.smartPlan.level')}</Text></Panel><Panel style={styles.metric}><Text style={styles.value}>{plan.points}</Text><Text style={styles.label}>{t('student.smartPlan.points')}</Text></Panel><Panel style={styles.metric}><Text style={styles.value}>🔥 {plan.streak}</Text><Text style={styles.label}>{t('student.smartPlan.streak')}</Text></Panel><Panel style={styles.metric}><Text style={styles.value}>{planPct}%</Text><Text style={styles.label}>{t('student.smartPlan.todayProgress')}</Text></Panel></View>
        <Panel style={styles.today}>
          <Text style={styles.sectionTitle}>{t('student.smartPlan.today')}</Text>
          <Text style={styles.body}>{t('student.smartPlan.todayBody', { done: completedTasks, total: plan.tasks.length })}</Text>
          <View style={styles.track}><View style={[styles.fill, { width: `${planPct}%` }]} /></View>
          {plan.tasks.map((task) => <View key={task.id}>
            <Pressable accessibilityRole="button" accessibilityLabel={t('student.smartPlan.openMission', { title: task.title })} onPress={() => setOpenMissionId((current) => current === task.id ? '' : task.id)} style={[styles.smartTask, task.done && styles.smartTaskDone]}>
              <View style={[styles.check, task.done && styles.checkDone]}><Text style={styles.checkText}>{task.done ? '✓' : ''}</Text></View>
              <View style={styles.topicCopy}><Text style={[styles.taskTitle, task.done && styles.topicTitleDone]}>{task.title}</Text><Text style={styles.topicSummary}>{task.detail}</Text><View style={styles.taskMeta}><Text style={styles.taskChip}>{t(`student.smartPlan.category.${task.category}`)}</Text><Text style={styles.taskXp}>{task.done ? t('student.smartPlan.missionPassed') : t('student.smartPlan.openMissionAction')}</Text></View></View><Text style={styles.taskArrow}>→</Text>
            </Pressable>
            {openMissionId === task.id ? <View style={styles.mission}>
              <View style={styles.sectionHeading}><View><Text style={styles.sectionTitle}>{task.title}</Text><Text style={styles.body}>{t('student.smartPlan.missionHelp')}</Text></View><Button secondary onPress={() => setOpenMissionId('')}>{t('student.smartPlan.closeMission')}</Button></View>
              {missionResources.length ? <><Text style={styles.missionStatus}>{task.done ? t('student.smartPlan.missionPassed') : t('student.smartPlan.missionProgress', { done: [...new Set(missionResources.filter((item) => passedMissions.has(`${item.kind}:${item.id}`)).map((item) => item.kind))].length, total: new Set(missionResources.map((item) => item.kind)).size })}</Text>
                <View style={styles.recommendations}>{missionResources.map((resource) => <View key={`${resource.kind}:${resource.id}`} style={styles.recommendation}><ResourceShowcaseCard compact item={resource} eyebrow={passedMissions.has(`${resource.kind}:${resource.id}`) ? t('student.smartPlan.missionPassed') : t(resource.kind === 'exam' ? 'student.smartPlan.examMission' : 'student.smartPlan.worksheetMission')} description={resource.topic || resource.description || t('resources.noDescription')} onPress={() => { void logStudentRecommendationOpen(resource, 'student_study_plan_mission').catch((reason) => console.warn('Mission recommendation open failed', reason)); router.push({ pathname: '/student-practice', params: { kind: resource.kind, resourceId: resource.id, returnTo: 'student-study-plan', missionId: task.id } }); }} /></View>)}</View></> : <Text style={styles.body}>{t('student.smartPlan.noMissionResources')}</Text>}
            </View> : null}
          </View>)}
        </Panel>
        <Panel style={styles.week}><Text style={styles.sectionTitle}>{t('student.smartPlan.weekly')}</Text>{[0, 1, 2, 3, 4].map((offset) => { const date = new Date(); date.setDate(date.getDate() + offset); const task = plan.tasks[offset % plan.tasks.length]; const focus = task.category === 'program' ? task.title : t(`student.smartPlan.goal.${smartPlanWeeklyFocus(plan.goal)[offset]}`); return <View key={offset} style={styles.weekRow}><Text style={styles.weekDay}>{offset === 0 ? t('student.smartPlan.todayLabel') : date.toLocaleDateString(undefined, { weekday: 'short' })}</Text><Text style={styles.weekFocus}>{focus}</Text><Text style={styles.weekMinutes}>{t('student.smartPlan.minutes', { minutes: plan.minutes })}</Text></View>; })}</Panel>
        <View style={styles.sectionHeading}><View><View style={styles.recommendationTitleWithHelp}><Text style={styles.sectionTitle}>{t('student.smartPlan.recommendations')}</Text><HelpIcon title={t('transparency.howRecommendationsWork')}>{[t('transparency.studentScope'), t('transparency.studentChallenge')].join('\n\n')}</HelpIcon></View><Text style={styles.body}>{t('student.smartPlan.recommendationsBody')}</Text></View><Button secondary onPress={() => router.push('/student-practice')}>{t('student.seePractice')}</Button></View>{recommendations.length ? <View style={styles.recommendations}>{recommendations.map((resource) => <View key={`${resource.kind}-${resource.id}`} style={styles.recommendation}><ResourceShowcaseCard compact item={resource} eyebrow={t('student.forYou')} description={resource.topic || resource.description || t('resources.noDescription')} onPress={() => { void logStudentRecommendationOpen(resource, 'student_study_plan').catch((reason) => console.warn('Study plan recommendation open failed', reason)); router.push({ pathname: '/student-practice', params: { kind: resource.kind, resourceId: resource.id, returnTo: 'student-study-plan' } }); }} /></View>)}</View> : <EmptyState title={t('student.noPractice')} body={t('student.noPracticeBody')} />}
      </>}
    </>}
  </AppShell>;
}

const styles = StyleSheet.create({
  message: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 11, padding: 11, fontSize: 11, fontWeight: '800', marginVertical: 12 },
  setup: { gap: 14, marginTop: 14, marginBottom: 16 }, sectionHeading: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginVertical: 12 }, sectionTitle: { color: colors.ink, fontSize: 20, lineHeight: 26, fontWeight: '900' }, planDate: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, fontSize: 9, fontWeight: '900' }, selects: { gap: 10 },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 15 }, metric: { flex: 1, minWidth: 150 }, value: { color: colors.ink, fontSize: 25, fontWeight: '900' }, label: { color: colors.muted, fontSize: 10, marginTop: 4 },
  today: { gap: 10, marginBottom: 15 }, track: { height: 8, backgroundColor: colors.line, borderRadius: 99, overflow: 'hidden', marginTop: 8 }, fill: { height: '100%', backgroundColor: colors.success }, smartTask: { flexDirection: 'row', gap: 11, alignItems: 'flex-start', borderWidth: 1, borderColor: colors.line, borderRadius: 14, padding: 12, backgroundColor: colors.surface }, smartTaskDone: { borderColor: colors.success, backgroundColor: colors.successSoft }, check: { width: 26, height: 26, borderRadius: 8, borderWidth: 1, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' }, checkDone: { backgroundColor: colors.success, borderColor: colors.success }, checkText: { color: colors.inverse, fontWeight: '900' }, taskTitle: { color: colors.ink, fontSize: 13, fontWeight: '900' }, taskMeta: { flexDirection: 'row', gap: 8, marginTop: 7 }, taskChip: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 4, fontSize: 8, fontWeight: '900', textTransform: 'capitalize' }, taskXp: { color: colors.violet, fontSize: 9, fontWeight: '900' },
  mission: { gap: 12, marginBottom: 16 }, missionStatus: { color: colors.success, fontSize: 12, fontWeight: '800' }, taskArrow: { color: colors.primary, fontSize: 18, fontWeight: '900', alignSelf: 'center' }, week: { gap: 8, marginBottom: 18 }, weekRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: colors.line, paddingVertical: 10 }, weekDay: { width: 60, color: colors.primary, fontSize: 10, fontWeight: '900', textTransform: 'capitalize' }, weekFocus: { flex: 1, minWidth: 180, color: colors.ink, fontSize: 11, fontWeight: '800' }, weekMinutes: { color: colors.muted, fontSize: 9 },
  recommendationTitleWithHelp: { flexDirection: 'row', alignItems: 'center', gap: 4 }, recommendations: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 18 }, recommendation: { flexGrow: 1, flexBasis: 320, minWidth: 280, maxWidth: 530 },
  program: { marginBottom: 12, gap: 8 }, hero: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, alignItems: 'flex-start' }, heroCopy: { flex: 1, minWidth: 240 }, kicker: { color: colors.primary, fontSize: 9, fontWeight: '900', letterSpacing: 0.7, textTransform: 'uppercase' }, title: { color: colors.ink, fontSize: 20, lineHeight: 26, fontWeight: '900', marginTop: 4 }, subject: { color: colors.primary, fontSize: 10, fontWeight: '800', textTransform: 'capitalize', marginTop: 5 }, body: { color: colors.muted, fontSize: 11, lineHeight: 18, marginTop: 3 }, score: { minWidth: 78, alignItems: 'center', backgroundColor: colors.successSoft, borderRadius: 14, padding: 12 }, scoreValue: { color: colors.success, fontSize: 22, fontWeight: '900' }, progress: { color: colors.success, fontSize: 9, fontWeight: '800' }, unit: { marginTop: 8 }, topic: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10, paddingVertical: 11, marginBottom: 8, borderBottomWidth: 1, borderBottomColor: colors.line }, topicDone: { backgroundColor: colors.successSoft, borderRadius: 10, paddingHorizontal: 10 }, status: { width: 28, height: 28, borderRadius: 14, borderWidth: 1, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' }, statusDone: { backgroundColor: colors.success, borderColor: colors.success }, statusText: { color: colors.inverse, fontWeight: '900' }, topicCopy: { flex: 1, minWidth: 190 }, topicTitle: { color: colors.ink, fontSize: 12, fontWeight: '900' }, topicTitleDone: { textDecorationLine: 'line-through', color: colors.muted }, topicSummary: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 3 }, practiceBadge: { color: colors.orange, fontSize: 9, fontWeight: '900', marginTop: 5 },
  practiceRequest: { maxWidth: 220 }, topicCards: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 14 }, topicCard: { flexGrow: 1, flexBasis: 280, maxWidth: 360, gap: 8 }, topicCardSurface: { borderWidth: 1, borderColor: colors.line, borderRadius: 16, padding: 18, backgroundColor: colors.surface }, topicCardPressed: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, topicCardTitle: { color: colors.ink, fontSize: 15, lineHeight: 21, fontWeight: '900' },
});
