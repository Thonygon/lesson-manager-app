/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import Head from 'expo-router/head';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Field, Pagination, SelectField, TabRail } from '@/components/ui';
import { ResourceFilters } from '@/components/resource-filters';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { PublicResourceViewer } from '@/components/public-resource-viewer';
import { PublicSmartTool } from '@/components/public-smart-tool';
import type { SmartToolKind } from '@/services/smart-tools';
import { publicExploreCopy } from '@/lib/public-explore-copy';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { formatPublicCopy, publicCopy } from '@/lib/public-copy';
import { publicConfig } from '@/lib/supabase';
import { useAppPreferences } from '@/providers/app-preferences';
import { getPublicResourceDetail, getPublicResourcePreviewImages, getPublicResources, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import { colors } from '@/theme';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { canonicalLearnerStageKey, learnerStageLabel } from '@/lib/learner-stages';

const TOOLS = [
  { icon: '📝', title: 'toolLesson', badge: 'toolLessonBadge', copy: 'toolLessonBody', tint: colors.primarySoft, accent: colors.primary },
  { icon: '📋', title: 'toolWorksheet', badge: 'toolWorksheetBadge', copy: 'toolWorksheetBody', tint: colors.successSoft, accent: colors.success },
  { icon: '🧪', title: 'toolExam', badge: 'toolExamBadge', copy: 'toolExamBody', tint: colors.orangeSoft, accent: colors.orange },
  { icon: '📚', title: 'toolProgram', badge: 'toolProgramBadge', copy: 'toolProgramBody', tint: colors.violetSoft, accent: colors.violet },
] as const;

const RESOURCE_META: Record<PublicResourceKind, { label: 'kindProgram' | 'kindPlan' | 'kindWorksheet' | 'kindExam' | 'kindVideo'; icon: string; accent: string; tint: string }> = {
  program: { label: 'kindProgram', icon: '📚', accent: colors.violet, tint: colors.violetSoft },
  plan: { label: 'kindPlan', icon: '📝', accent: colors.primary, tint: colors.primarySoft },
  worksheet: { label: 'kindWorksheet', icon: '📋', accent: colors.success, tint: colors.successSoft },
  exam: { label: 'kindExam', icon: '🧪', accent: colors.orange, tint: colors.orangeSoft },
  video: { label: 'kindVideo', icon: '🎬', accent: colors.pink, tint: colors.pinkSoft },
};

const RATE_RANGES: Record<string, [number, number, number]> = {
  English: [25, 40, 80], Spanish: [25, 40, 80], Mathematics: [30, 50, 100], Science: [30, 50, 100], Music: [25, 45, 90], 'Study skills': [20, 35, 70],
};

function exerciseTypeKey(value: unknown) {
  return String(value ?? '').trim().toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '').replace('fill_in_the_blanks', 'fill_in_blank');
}

function Choice({ active, children, onPress }: { active: boolean; children: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ selected: active }} onPress={onPress} style={[styles.choice, active && styles.choiceActive]}>
      <Text style={[styles.choiceText, active && styles.choiceTextActive]}>{children}</Text>
    </Pressable>
  );
}

function SectionHeading({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.eyebrow}>{eyebrow}</Text>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionBody}>{body}</Text>
    </View>
  );
}

export default function HomeScreen() {
  const params = useLocalSearchParams<{ resourceKind?: string; resourceId?: string; from?: string; tool?: string }>();
  const { t, language } = useAppPreferences();
  const copy = publicCopy(language);
  const explore = publicExploreCopy(language);
  const { width } = useWindowDimensions();
  const compact = width < 780;
  const phone = width < 560;
  const pageRef = useRef<ScrollView>(null);
  const resourcesY = useRef(0);
  const goalY = useRef(0);
  const toolsY = useRef(0);
  const selectedToolY = useRef(0);
  const pendingToolScroll = useRef(false);
  const hydratedImages = useRef(new Set<string>());
  const [resources, setResources] = useState<PublicResource[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [resourceError, setResourceError] = useState('');
  const [sharedResourceError, setSharedResourceError] = useState('');
  const [kind, setKind] = useState<PublicResourceKind>('program');
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('All subjects');
  const [stage, setStage] = useState('All stages');
  const [level, setLevel] = useState('All levels');
  const [exerciseFilter, setExerciseFilter] = useState('All exercises');
  const [resourcePage, setResourcePage] = useState(1);
  const [selected, setSelected] = useState<PublicResource | null>(null);
  const [openTool, setOpenTool] = useState<SmartToolKind | null>(null);
  useEffect(() => { if (params.from === 'explorer' && !params.resourceId && ['plan', 'worksheet', 'exam', 'program'].includes(String(params.tool))) { pendingToolScroll.current = true; setOpenTool(params.tool as SmartToolKind); } }, [params.from, params.resourceId, params.tool]);
  const [goalSubject, setGoalSubject] = useState('English');
  const [modality, setModality] = useState<'Online' | 'In person'>('Online');
  const [audience, setAudience] = useState<'Kids' | 'Teens' | 'Adults'>('Adults');
  const [education, setEducation] = useState<'Student' | 'Bachelor’s' | 'Master’s' | 'Doctorate'>('Master’s');
  const [hourlyRate, setHourlyRate] = useState('40');
  const [incomeGoal, setIncomeGoal] = useState('50000');
  const [showPlan, setShowPlan] = useState(false);
  const [audienceView, setAudienceView] = useState<'teacher' | 'student'>('teacher');
  useEffect(() => {
    const sharedKind = String(params.resourceKind || ''); const sharedId = String(params.resourceId || '');
    if (!Object.hasOwn(RESOURCE_META, sharedKind) || !/^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[1-9]\d*)$/i.test(sharedId)) return;
    let active = true;
    setAudienceView('teacher'); setKind(sharedKind as PublicResourceKind); setSharedResourceError(''); if (params.from === 'explorer' && ['plan', 'worksheet', 'exam', 'program'].includes(String(params.tool))) setOpenTool(params.tool as SmartToolKind);
    void getPublicResourceDetail(sharedKind as PublicResourceKind, sharedId).then((resource) => { if (active) setSelected(resource); }).catch(() => { if (active) setSharedResourceError('This shared resource is private or no longer available.'); });
    return () => { active = false; };
  }, [params.resourceId, params.resourceKind, params.from, params.tool]);
  useEffect(() => { if (selected && params.resourceId) requestAnimationFrame(() => pageRef.current?.scrollTo({ y: resourcesY.current, animated: true })); }, [params.resourceId, selected]);
  const resourceKinds = audienceView === 'teacher' ? Object.keys(RESOURCE_META) as PublicResourceKind[] : ['worksheet', 'exam', 'video'] as PublicResourceKind[];
  const selectAudience = (next: 'teacher' | 'student') => { setAudienceView(next); setKind(next === 'teacher' ? 'program' : 'worksheet'); setSelected(null); setResourcePage(1); setStage('All stages'); setLevel('All levels'); setExerciseFilter('All exercises'); };
  const subjectLabels: Record<string, string> = { English: copy.english, Spanish: copy.spanish, Mathematics: copy.mathematics, Science: copy.science, Music: copy.music, 'Study skills': copy.studySkills };
  const modalityLabels = { Online: copy.online, 'In person': copy.inPerson };
  const audienceLabels = { Kids: copy.kids, Teens: copy.teens, Adults: copy.adults };
  const educationLabels = { Student: copy.educationStudent, 'Bachelor’s': copy.bachelors, 'Master’s': copy.masters, Doctorate: copy.doctorate };

  useEffect(() => {
    if (!publicConfig) {
      setResourceError(copy.libraryConfig);
      setResourcesLoading(false);
      return;
    }
    getPublicResources()
      .then(setResources)
      .catch(() => setResourceError(copy.libraryFailed))
      .finally(() => setResourcesLoading(false));
  }, [copy.libraryConfig, copy.libraryFailed]);

  const kindResources = useMemo(() => resources.filter((item) => item.kind === kind), [kind, resources]);
  const subjects = useMemo(() => [...new Map(resources.map((item) => item.subject).filter(Boolean).map((value) => [canonicalSubjectKey(value), value])).values()].sort((a, b) => canonicalSubjectLabel(a, t).localeCompare(canonicalSubjectLabel(b, t))), [resources, t]);
  const subjectResources = useMemo(() => kindResources.filter((item) => subject === 'All subjects' || canonicalSubjectKey(item.subject) === canonicalSubjectKey(subject)), [kindResources, subject]);
  const stageOptions = useMemo(() => [...new Map(subjectResources.map((item) => item.stage).filter(Boolean).map((value) => [canonicalLearnerStageKey(value), value])).values()].sort((a, b) => learnerStageLabel(a, t).localeCompare(learnerStageLabel(b, t))), [subjectResources, t]);
  const levelOptions = useMemo(() => [...new Map(subjectResources.filter((item) => stage === 'All stages' || canonicalLearnerStageKey(item.stage) === canonicalLearnerStageKey(stage)).map((item) => item.level).filter(Boolean).map((value) => [value.toLocaleLowerCase(), value])).values()].sort(), [stage, subjectResources]);
  const exerciseOptions = useMemo(() => [...new Set(subjectResources.map((item) => kind === 'worksheet' ? exerciseTypeKey(item.raw.worksheet_type) : kind === 'exam' ? exerciseTypeKey(item.raw.exam_length) : '').filter(Boolean))].sort(), [kind, subjectResources]);
  const visibleResources = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return kindResources.filter((item) => {
      if (subject !== 'All subjects' && canonicalSubjectKey(item.subject) !== canonicalSubjectKey(subject)) return false;
      if (stage !== 'All stages' && canonicalLearnerStageKey(item.stage) !== canonicalLearnerStageKey(stage)) return false;
      if (level !== 'All levels' && item.level.toLocaleLowerCase() !== level.toLocaleLowerCase()) return false;
      if (exerciseFilter !== 'All exercises' && (kind === 'worksheet' ? exerciseTypeKey(item.raw.worksheet_type) : kind === 'exam' ? exerciseTypeKey(item.raw.exam_length) : '') !== exerciseFilter) return false;
      return !needle || [item.title, item.subject, item.topic, item.stage, item.level, item.author, item.description].join(' ').toLocaleLowerCase().includes(needle);
    });
  }, [exerciseFilter, kind, kindResources, level, query, stage, subject]);

  useEffect(() => setResourcePage(1), [exerciseFilter, kind, level, query, stage, subject]);

  const totalResourcePages = Math.max(1, Math.ceil(visibleResources.length / 18));
  const pagedResources = visibleResources.slice((resourcePage - 1) * 18, resourcePage * 18);
  useEffect(() => {
    if (kind === 'video') return;
    const missing = pagedResources.filter((item) => !item.imageUrl && !hydratedImages.current.has(`${item.kind}:${item.id}`));
    if (!missing.length) return;
    missing.forEach((item) => hydratedImages.current.add(`${item.kind}:${item.id}`));
    void getPublicResourcePreviewImages(kind, missing.map((item) => item.id)).then((images) => {
      if (!Object.keys(images).length) return;
      setResources((current) => current.map((item) => item.kind === kind && images[item.id] ? { ...item, imageUrl: images[item.id] } : item));
      setSelected((current) => current && images[current.id] ? { ...current, imageUrl: images[current.id] } : current);
    });
  }, [kind, pagedResources]);

  const rate = Math.max(1, Number(hourlyRate) || 1);
  const goal = Math.max(0, Number(incomeGoal) || 0);
  const annualHours = Math.ceil(goal / rate);
  const weeklyHours = Math.ceil(annualHours / 44);
  const studentsNeeded = Math.ceil(weeklyHours / 1.5);
  const feasibility = weeklyHours <= 24 ? [copy.goalComfortable, colors.success, copy.goalComfortableBody] : weeklyHours <= 31 ? [copy.goalFocused, colors.warning, copy.goalFocusedBody] : weeklyHours <= 42 ? [copy.goalAmbitious, colors.orange, copy.goalAmbitiousBody] : [copy.goalOverloaded, colors.danger, copy.goalOverloadedBody];

  const chooseGoalSubject = (next: string) => {
    setGoalSubject(next);
    setHourlyRate(String(RATE_RANGES[next][1]));
    setShowPlan(false);
  };
  const openSmartTool = (next: SmartToolKind) => { pendingToolScroll.current = true; setOpenTool(next); if (openTool) requestAnimationFrame(() => scrollToSmartTool(selectedToolY.current)); };
  const scrollToSmartTool = (y: number) => {
    if (!pendingToolScroll.current) return;
    pendingToolScroll.current = false;
    requestAnimationFrame(() => pageRef.current?.scrollTo({ y: Math.max(0, toolsY.current + y - 16), animated: true }));
  };

  return (
    <>
      <Head>
        <title>{copy.metaTitle}</title>
        <meta name="description" content={copy.metaDescription} />
      </Head>
      <ScrollView ref={pageRef} contentContainerStyle={styles.page}>
        <SafeAreaView style={styles.shell}>
          <View style={[styles.header, compact && styles.headerCompact, phone && styles.headerPhone]}>
            {phone ? <>
              <View style={styles.headerPhoneTop}><Image accessibilityLabel="Classio" resizeMode="contain" source={require('../../assets/images/classio-logo.png')} style={styles.logoPhone} /><Pressable onPress={() => router.push('/sign-in')} style={styles.signInButton}><Text style={styles.signInText}>{t('auth.signIn')}</Text></Pressable></View>
              <PreferenceSwitcher compact />
            </> : <>
              <Image accessibilityLabel="Classio" resizeMode="contain" source={require('../../assets/images/classio-logo.png')} style={styles.logo} />
              <View style={[styles.headerActions, compact && styles.headerActionsCompact]}>
                <PreferenceSwitcher />
                {!compact ? <Pressable onPress={() => pageRef.current?.scrollTo({ y: resourcesY.current, animated: true })}><Text style={styles.headerLink}>{t('public.exploreResources')}</Text></Pressable> : null}
                {!compact ? <Pressable onPress={() => pageRef.current?.scrollTo({ y: goalY.current, animated: true })}><Text style={styles.headerLink}>{t('public.incomePlanner')}</Text></Pressable> : null}
                <Pressable onPress={() => router.push('/sign-in')} style={styles.signInButton}><Text style={styles.signInText}>{t('auth.signIn')}</Text></Pressable>
              </View>
            </>}
          </View>

          <View style={[styles.hero, compact && styles.heroCompact]}>
            <View style={[styles.heroCopy, compact && styles.heroCopyCompact]}>
              <View style={styles.livePill}><View style={styles.liveDot} /><Text style={styles.liveText}>{copy.heroEyebrow}</Text></View>
              <Text style={[styles.heroTitle, compact && styles.heroTitleCompact]}>{copy.heroTitle}</Text>
              <Text style={styles.heroBody}>{copy.heroBody}</Text>
              <View style={[styles.heroActions, compact && styles.stack]}>
                <Pressable accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.primaryButton}><Text style={styles.primaryButtonText}>{copy.teach}</Text></Pressable>
                <Pressable accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.secondaryHeroButton}><Text style={styles.secondaryHeroText}>{copy.study}</Text></Pressable>
              </View>
              <Pressable onPress={() => pageRef.current?.scrollTo({ y: resourcesY.current, animated: true })} style={styles.proofRow}><Text style={styles.proofIcons}>✦</Text><Text style={styles.proofText}>{copy.freeResources}</Text></Pressable>
            </View>
            <View style={[styles.previewColumn, compact && styles.previewColumnCompact]}>
              <View style={styles.audienceSwitch}><Choice active={audienceView === 'teacher'} onPress={() => selectAudience('teacher')}>{copy.teacherCardEyebrow}</Choice><Choice active={audienceView === 'student'} onPress={() => selectAudience('student')}>{copy.studentCardEyebrow}</Choice></View>
              {audienceView === 'teacher' ? <View style={[styles.dayCard, phone && styles.dayCardPhone]}>
                <View style={styles.dayHeader}><View style={styles.dayHeaderCopy}><Text style={styles.dayKicker}>{copy.teacherPreviewKicker}</Text><Text style={styles.dayTitle}>{copy.teacherPreview}</Text></View><View style={styles.avatar}><Text style={styles.avatarText}>T</Text></View></View>
                {[
                  ['09:00', copy.lessonOne, copy.lessonOneNote, colors.primary],
                  ['11:30', copy.lessonTwo, copy.lessonTwoNote, colors.violet],
                  ['15:00', copy.lessonThree, copy.lessonThreeNote, colors.success],
                ].map(([time, name, note, accent]) => <View key={time} style={styles.lessonRow}><View style={[styles.lessonAccent, { backgroundColor: accent }]} /><Text style={styles.lessonTime}>{time}</Text><View style={styles.lessonCopy}><Text style={styles.lessonName}>{name}</Text><Text style={styles.lessonNote}>{note}</Text></View></View>)}
                <View style={styles.nextAction}><Text style={styles.nextIcon}>✨</Text><View style={styles.lessonCopy}><Text style={styles.nextTitle}>{copy.nextAction}</Text><Text style={styles.nextBody}>{copy.nextActionBody}</Text></View></View>
              </View> : <View style={[styles.dayCard, phone && styles.dayCardPhone]}>
                <View style={styles.dayHeader}><View style={styles.dayHeaderCopy}><Text style={styles.dayKicker}>{copy.studentPreviewKicker}</Text><Text style={styles.dayTitle}>{copy.studentPreview}</Text></View><View style={styles.avatar}><Text style={styles.avatarText}>S</Text></View></View>
                {[["01", copy.studentStepOne, copy.studentStepOneBody], ["02", copy.studentStepTwo, copy.studentStepTwoBody], ["03", copy.studentStepThree, copy.studentStepThreeBody]].map(([number, title, body]) => <View key={number} style={styles.lessonRow}><Text style={styles.studentStepNumber}>{number}</Text><View style={styles.lessonCopy}><Text style={styles.lessonName}>{title}</Text><Text style={styles.lessonNote}>{body}</Text></View></View>)}
                <Pressable onPress={() => router.push('/sign-in')} style={styles.studentPreviewAction}><Text style={styles.studentPreviewActionText}>{copy.findTeacher} →</Text></Pressable>
              </View>}
            </View>
          </View>

          <View style={styles.section} onLayout={(event) => { resourcesY.current = event.nativeEvent.layout.y; }}>
            <SectionHeading eyebrow={copy.libraryEyebrow} title={audienceView === 'teacher' ? copy.libraryTeacherTitle : copy.libraryTitle} body={copy.libraryBody} />
            {sharedResourceError ? <View style={styles.notice}><Text style={styles.noticeTitle}>{sharedResourceError}</Text></View> : null}
            {selected ? <PublicResourceViewer selected={selected} mode={audienceView} onClose={() => setSelected(null)} /> : <>
            <TabRail accessibilityLabel={audienceView === 'teacher' ? copy.libraryTeacherTitle : copy.libraryTitle} value={kind} onChange={(value) => { setKind(value as PublicResourceKind); setStage('All stages'); setLevel('All levels'); setExerciseFilter('All exercises'); setSelected(null); }} items={resourceKinds.map((key) => ({ value: key, label: `${RESOURCE_META[key].icon} ${copy[RESOURCE_META[key].label]}` }))} />
            <ResourceFilters query={query} onQueryChange={setQuery} count={resourcesLoading ? undefined : visibleResources.length} searchLabel={copy.searchResources} facets={[
              { key: 'subject', label: t('resources.subject'), value: subject, allValue: 'All subjects', allLabel: t('resources.allSubjects'), options: subjects.map((value) => ({ value, label: canonicalSubjectLabel(value, t) })), onChange: (value) => { setSubject(value); setStage('All stages'); setLevel('All levels'); setExerciseFilter('All exercises'); } },
              { key: 'stage', label: t('resources.stage'), value: stage, allValue: 'All stages', allLabel: t('resources.allStages'), options: stageOptions.map((value) => ({ value, label: learnerStageLabel(value, t) })), onChange: (value) => { setStage(value); setLevel('All levels'); } },
              { key: 'level', label: t('resources.level'), value: level, allValue: 'All levels', allLabel: t('resources.allLevels'), options: levelOptions.map((value) => ({ value, label: value })), onChange: setLevel },
              ...(kind === 'worksheet' || kind === 'exam' ? [{ key: 'exercise', label: kind === 'exam' ? t('smart.examLength') : t('student.exerciseType'), value: exerciseFilter, allValue: 'All exercises', allLabel: kind === 'exam' ? t('student.allExamLengths') : t('student.allExerciseTypes'), options: exerciseOptions.map((value) => { const key = kind === 'exam' ? `smart.option.${value}` : `student.exercise.${value}`; const translated = t(key); return { value, label: translated === key ? value.replaceAll('_', ' ') : translated }; }), onChange: setExerciseFilter }] : []),
            ]} />
            {resourcesLoading ? <View style={styles.loading}><ActivityIndicator color={colors.primary} /><Text style={styles.muted}>{copy.libraryLoading}</Text></View> : null}
            {resourceError ? <View style={styles.notice}><Text style={styles.noticeTitle}>{copy.libraryUnavailable}</Text><Text style={styles.muted}>{resourceError}</Text></View> : null}
            {!resourcesLoading && !resourceError && visibleResources.length === 0 ? <View style={styles.notice}><Text style={styles.noticeTitle}>{copy.noMatches}</Text><Text style={styles.muted}>{copy.noMatchesBody}</Text></View> : null}
            <View style={styles.resourceGrid}>
              {pagedResources.map((item) => <View key={`${item.kind}-${item.id}`} style={styles.resourceSlot}><ResourceShowcaseCard compact item={item} onPress={() => setSelected(item)} description={item.description || item.topic || copy.resourceFallback} eyebrow={copy[RESOURCE_META[item.kind].label]} /></View>)}
            </View>
            <Pagination page={resourcePage} totalPages={totalResourcePages} totalItems={visibleResources.length} onPageChange={setResourcePage} />
            </>}
          </View>

          <View style={[styles.section, compact && styles.sectionCompact]} onLayout={(event) => { toolsY.current = event.nativeEvent.layout.y; }}>
            <SectionHeading eyebrow={copy.toolsEyebrow} title={copy.toolsTitle} body={copy.toolsBody} />
            <View style={styles.cardGrid}>
              {TOOLS.map((tool, index) => { const toolKind = ['plan', 'worksheet', 'exam', 'program'][index] as SmartToolKind; return <Pressable key={tool.title} accessibilityRole="button" accessibilityState={{ selected: openTool === toolKind }} accessibilityLabel={copy[tool.title]} onPress={() => openSmartTool(toolKind)} style={({ pressed, hovered }) => [styles.toolCard, phone && styles.toolCardPhone, { backgroundColor: tool.tint, borderColor: openTool === toolKind ? tool.accent : colors.lineStrong }, (pressed || hovered) && styles.toolCardHover]}><View pointerEvents="none" style={styles.toolWash} /><View pointerEvents="none" style={[styles.toolGlow, { backgroundColor: tool.tint }]} /><View pointerEvents="none" style={[styles.toolBar, { backgroundColor: tool.accent }]} /><View style={styles.toolTop}><View style={[styles.toolIconBubble, { backgroundColor: tool.tint, borderColor: tool.accent }]}><Text style={styles.toolIcon}>{tool.icon}</Text></View>{!phone ? <Text style={[styles.toolBadge, { color: tool.accent }]}>{copy[tool.badge]}</Text> : null}</View><Text style={[styles.toolTitle, phone && styles.toolTitlePhone]}>{copy[tool.title]}</Text>{!phone ? <Text style={styles.toolBody}>{copy[tool.copy]}</Text> : null}<Text style={[styles.toolAction, { color: tool.accent }]}>{copy.toolTry} →</Text></Pressable>; })}
            </View>
            {openTool ? <View style={styles.selectedArea} onLayout={(event) => { selectedToolY.current = event.nativeEvent.layout.y; scrollToSmartTool(selectedToolY.current); }}><PublicSmartTool key={openTool} initial={openTool} onClose={() => setOpenTool(null)} /></View> : null}
          </View>

          <View style={[styles.section, styles.goalSection]} onLayout={(event) => { goalY.current = event.nativeEvent.layout.y; }}>
            <SectionHeading eyebrow={copy.goalEyebrow} title={copy.goalTitle} body={copy.goalBody} />
            <View style={[styles.goalLayout, compact && styles.goalLayoutCompact]}>
              <View style={[styles.goalForm, compact && styles.goalPanelCompact]}>
                <View style={styles.goalFilters}>
                  <View style={styles.goalFilterCell}><Text style={styles.goalFilterLabel}>{copy.goalSubject}</Text><SelectField label={copy.goalSubject} value={goalSubject} options={Object.keys(RATE_RANGES).map((item) => ({ value: item, label: subjectLabels[item] }))} onChange={chooseGoalSubject} /></View>
                  <View style={styles.goalFilterCell}><Text style={styles.goalFilterLabel}>{copy.goalModality}</Text><SelectField label={copy.goalModality} value={modality} options={(['Online', 'In person'] as const).map((item) => ({ value: item, label: modalityLabels[item] }))} onChange={(value) => { setModality(value as typeof modality); setShowPlan(false); }} /></View>
                  <View style={styles.goalFilterCell}><Text style={styles.goalFilterLabel}>{copy.goalAudience}</Text><SelectField label={copy.goalAudience} value={audience} options={(['Kids', 'Teens', 'Adults'] as const).map((item) => ({ value: item, label: audienceLabels[item] }))} onChange={(value) => { setAudience(value as typeof audience); setShowPlan(false); }} /></View>
                  <View style={styles.goalFilterCell}><Text style={styles.goalFilterLabel}>{copy.goalEducation}</Text><SelectField label={copy.goalEducation} value={education} options={(['Student', 'Bachelor’s', 'Master’s', 'Doctorate'] as const).map((item) => ({ value: item, label: educationLabels[item] }))} onChange={(value) => { setEducation(value as typeof education); setShowPlan(false); }} /></View>
                </View>
                <View style={[styles.inputRow, compact && styles.stack]}><View style={styles.inputCell}><Text style={styles.fieldLabel}>{copy.goalRate}</Text><Field keyboardType="numeric" value={hourlyRate} onChangeText={(value) => { setHourlyRate(value); setShowPlan(false); }} /></View><View style={styles.inputCell}><Text style={styles.fieldLabel}>{copy.goalYearly}</Text><Field keyboardType="numeric" value={incomeGoal} onChangeText={(value) => { setIncomeGoal(value); setShowPlan(false); }} /></View></View>
                <Text style={styles.rateHint}>{formatPublicCopy(copy.goalRange, { subject: subjectLabels[goalSubject].toLocaleLowerCase(language), low: RATE_RANGES[goalSubject][0], high: RATE_RANGES[goalSubject][2] })}</Text>
                <Pressable onPress={() => setShowPlan(true)} style={styles.primaryButton}><Text style={styles.primaryButtonText}>{copy.goalBuild}</Text></Pressable>
              </View>
              <View style={[styles.goalResult, compact && styles.goalPanelCompact, !showPlan && styles.goalResultIdle]}>
                {!showPlan ? <><Text style={styles.resultIcon}>🎯</Text><Text style={styles.resultTitle}>{copy.goalIdleTitle}</Text><Text style={styles.resultBody}>{copy.goalIdleBody}</Text></> : <><View style={styles.resultTop}><Text style={styles.resultKicker}>{copy.goalPlan}</Text><Text style={[styles.feasibility, { color: feasibility[1] }]}>{feasibility[0]}</Text></View><Text style={styles.goalAmount}>${goal.toLocaleString()}</Text><Text style={styles.resultBody}>{copy.goalAnnual}</Text><View style={styles.metrics}><View style={styles.metric}><Text style={styles.metricValue}>{annualHours}</Text><Text style={styles.metricLabel}>{copy.goalHoursYear}</Text></View><View style={styles.metric}><Text style={styles.metricValue}>{weeklyHours}</Text><Text style={styles.metricLabel}>{copy.goalHoursWeek}</Text></View><View style={styles.metric}><Text style={styles.metricValue}>{studentsNeeded}</Text><Text style={styles.metricLabel}>{copy.goalStudents}</Text></View></View><Text style={styles.advice}>{feasibility[2]}</Text><Pressable onPress={() => router.push('/sign-in')} style={styles.secondaryButton}><Text style={styles.secondaryButtonText}>{copy.goalCreate}</Text></Pressable></>}
              </View>
            </View>
          </View>

          <View style={[styles.section, compact && styles.sectionCompact]}>
            <SectionHeading eyebrow={explore.featureEyebrow} title={explore.featureTitle} body={explore.featureBody} />
            <View style={styles.featureGrid}>
              {([['◫', explore.featureDashboard, explore.featureDashboardBody, colors.primary, colors.primarySoft], ['◉', explore.featureStudents, explore.featureStudentsBody, colors.success, colors.successSoft], ['✎', explore.featureLessons, explore.featureLessonsBody, colors.orange, colors.orangeSoft], ['◇', explore.featurePayments, explore.featurePaymentsBody, colors.warning, colors.warningSoft], ['▦', explore.featureCalendar, explore.featureCalendarBody, colors.violet, colors.violetSoft], ['▥', explore.featureAnalytics, explore.featureAnalyticsBody, colors.pink, colors.pinkSoft]] as const).map(([icon, title, body, accent, tint]) => <Pressable key={title} accessibilityRole="button" onPress={() => router.push('/sign-in')} style={({ pressed, hovered }) => [styles.featureCard, phone && styles.featureCardPhone, (pressed || hovered) && styles.toolCardHover]}><View style={[styles.featureIconBubble, { backgroundColor: tint, borderColor: accent }]}><Text style={[styles.featureIcon, { color: accent }]}>{icon}</Text></View><Text numberOfLines={2} style={[styles.featureTitle, phone && styles.featureTitlePhone]}>{title}</Text>{!phone ? <Text style={styles.featureBody}>{body}</Text> : null}<Text style={[styles.featureAction, { color: accent }]}>{phone ? '↗' : `${explore.featureAction} ↗`}</Text></Pressable>)}
            </View>
          </View>


          <View style={styles.finalCta}><Text style={styles.finalEyebrow}>{copy.finalEyebrow}</Text><Text style={[styles.finalTitle, compact && styles.sectionTitle]}>{copy.finalTitle}</Text><Text style={styles.finalBody}>{copy.finalBody}</Text><Pressable onPress={() => router.push('/sign-in')} style={styles.lightButton}><Text style={styles.lightButtonText}>{copy.finalAction}</Text></Pressable></View>
          <View style={styles.footer}><Text style={styles.footerBrand}>CLASSIO</Text><Text style={styles.footerText}>{copy.footer}</Text></View>
        </SafeAreaView>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  page: { minHeight: '100%', backgroundColor: 'transparent' },
  shell: { width: '100%', maxWidth: 1220, alignSelf: 'center', paddingHorizontal: 24, paddingTop: 12, paddingBottom: 36 },
  header: { minHeight: 72, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 18 },
  headerCompact: { minHeight: 64 }, headerPhone: { flexDirection: 'column', alignItems: 'stretch', gap: 8 }, headerPhoneTop: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 }, logo: { width: 154, height: 54 }, logoPhone: { width: 116, height: 48 }, headerActions: { flexDirection: 'row', alignItems: 'center', gap: 24 }, headerActionsCompact: { flexShrink: 1, flexWrap: 'wrap', justifyContent: 'flex-end', gap: 10 },
  headerLink: { color: colors.muted, fontSize: 14, fontWeight: '600' }, signInButton: { backgroundColor: colors.navDark, borderRadius: 12, paddingHorizontal: 18, paddingVertical: 12 }, signInText: { color: colors.inverse, fontWeight: '800' },
  hero: { minHeight: 610, flexDirection: 'row', alignItems: 'center', gap: 64, paddingVertical: 68 }, heroCompact: { minHeight: 0, flexDirection: 'column', alignItems: 'stretch', gap: 38, paddingVertical: 44 }, heroCopy: { flex: 1.12 }, heroCopyCompact: { flexGrow: 0, flexShrink: 0, flexBasis: 'auto', minWidth: 0 },
  livePill: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.successSoft, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7, marginBottom: 22 }, liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#10B981' }, liveText: { color: '#047857', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  heroTitle: { color: colors.ink, fontSize: 62, lineHeight: 66, fontWeight: '900', letterSpacing: -2.5 }, heroTitleCompact: { fontSize: 42, lineHeight: 47, letterSpacing: -1.4 }, heroBody: { color: colors.muted, fontSize: 18, lineHeight: 29, maxWidth: 620, marginTop: 24 }, heroActions: { flexDirection: 'row', alignItems: 'center', gap: 18, marginTop: 30 },
  primaryButton: { alignSelf: 'flex-start', backgroundColor: colors.primary, borderRadius: 13, paddingHorizontal: 20, paddingVertical: 15 }, primaryButtonText: { color: colors.inverse, fontSize: 15, fontWeight: '800' }, secondaryHeroButton: { alignSelf: 'flex-start', backgroundColor: colors.surface, borderColor: colors.primary, borderWidth: 1, borderRadius: 13, paddingHorizontal: 20, paddingVertical: 14 }, secondaryHeroText: { color: colors.primary, fontSize: 15, fontWeight: '800' }, proofRow: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 18 }, proofIcons: { color: colors.success, fontWeight: '900' }, proofText: { color: colors.muted, fontSize: 13, fontWeight: '600' },
  previewColumn: { flex: 0.88, minWidth: 320, gap: 12 }, previewColumnCompact: { flexGrow: 0, flexShrink: 0, flexBasis: 'auto', minWidth: 0, width: '100%' }, audienceSwitch: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, studentStepNumber: { color: colors.primary, fontSize: 13, fontWeight: '900', width: 42 }, studentPreviewAction: { backgroundColor: colors.primarySoft, borderRadius: 12, padding: 13, marginTop: 14, alignItems: 'center' }, studentPreviewActionText: { color: colors.primary, fontSize: 12, fontWeight: '900' }, audienceCards: { flexDirection: 'row', gap: 14 }, audienceCard: { flex: 1, minWidth: 280, borderRadius: 20, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surface, padding: 22 }, audienceEyebrow: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, audienceTitle: { color: colors.ink, fontSize: 22, fontWeight: '900', marginTop: 10 }, audienceBody: { color: colors.muted, fontSize: 13, lineHeight: 20, marginTop: 8 }, audienceAction: { color: colors.primary, fontSize: 12, fontWeight: '900', marginTop: 18 },
  dayCard: { backgroundColor: colors.surface, borderRadius: 26, padding: 26, borderWidth: 1, borderColor: colors.line, shadowColor: colors.shadow, shadowOpacity: 0.1, shadowRadius: 28, shadowOffset: { width: 0, height: 16 } }, dayCardPhone: { padding: 18, width: '100%', minWidth: 0 }, dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, gap: 10 }, dayHeaderCopy: { flex: 1, minWidth: 0 }, dayKicker: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, dayTitle: { color: colors.ink, fontSize: 22, lineHeight: 27, fontWeight: '900', marginTop: 5, flexShrink: 1, width: '100%' }, avatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center', flexShrink: 0 }, avatarText: { color: colors.primary, fontWeight: '900' },
  lessonRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderTopWidth: 1, borderTopColor: colors.line }, lessonAccent: { width: 4, height: 42, borderRadius: 4 }, lessonTime: { color: colors.muted, width: 42, fontSize: 12, fontWeight: '700' }, lessonCopy: { flex: 1 }, lessonName: { color: colors.ink, fontWeight: '800', fontSize: 14 }, lessonNote: { color: colors.muted, fontSize: 12, marginTop: 3 }, nextAction: { flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: colors.surfaceSoft, borderRadius: 14, padding: 14, marginTop: 8 }, nextIcon: { fontSize: 22 }, nextTitle: { color: colors.violet, fontSize: 11, fontWeight: '900', letterSpacing: 0.5 }, nextBody: { color: colors.inkSecondary, fontSize: 13, marginTop: 3 },
  valueStrip: { flexDirection: 'row', backgroundColor: colors.navDark, borderRadius: 22, paddingVertical: 22, paddingHorizontal: 28, gap: 18 }, valueItem: { flex: 1, alignItems: 'center', borderRightWidth: 1, borderRightColor: colors.navDarkSoft }, valueNumber: { color: colors.inverse, fontSize: 25, fontWeight: '900' }, valueLabel: { color: colors.subtle, fontSize: 12, marginTop: 3 },
  section: { paddingVertical: 78 }, sectionCompact: { paddingVertical: 46 }, sectionHeading: { maxWidth: 720, marginBottom: 34 }, eyebrow: { color: '#2563EB', fontSize: 11, fontWeight: '900', letterSpacing: 1.3, marginBottom: 10 }, sectionTitle: { color: colors.ink, fontSize: 38, lineHeight: 44, fontWeight: '900', letterSpacing: -1 }, sectionBody: { color: colors.muted, fontSize: 16, lineHeight: 25, marginTop: 12 },
  cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, toolCard: { flexGrow: 1, flexBasis: 250, minWidth: 220, minHeight: 210, borderRadius: 19, padding: 18, borderWidth: 1, overflow: 'hidden' }, toolCardPhone: { flexBasis: '46%', minWidth: 0, minHeight: 176, padding: 13 }, toolCardHover: { transform: [{ translateY: -2 }] }, toolWash: { position: 'absolute', inset: 0, backgroundColor: colors.surface, opacity: 0.82 }, toolGlow: { position: 'absolute', top: -45, right: -48, width: 135, height: 120, borderRadius: 999, opacity: 0.9 }, toolBar: { position: 'absolute', left: 18, right: 18, top: 0, height: 4, borderBottomLeftRadius: 999, borderBottomRightRadius: 999 }, toolTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 15 }, toolIconBubble: { width: 42, height: 42, borderRadius: 13, borderWidth: 1, alignItems: 'center', justifyContent: 'center' }, toolIcon: { fontSize: 22 }, toolBadge: { fontSize: 9, fontWeight: '900', letterSpacing: 1 }, toolTitle: { color: colors.ink, fontSize: 18, fontWeight: '900' }, toolTitlePhone: { fontSize: 14, lineHeight: 18 }, toolBody: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 7, flex: 1 }, toolAction: { fontSize: 11, fontWeight: '900', marginTop: 'auto', paddingTop: 15 },
  resourceTabs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 }, choice: { borderRadius: 999, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surface, paddingHorizontal: 14, paddingVertical: 9 }, choiceActive: { backgroundColor: colors.primary, borderColor: colors.primary }, choiceText: { color: colors.muted, fontSize: 12, fontWeight: '700' }, choiceTextActive: { color: colors.inverse }, search: { marginTop: 4 }, subjects: { gap: 8, paddingVertical: 13 }, filterRow: { gap: 8, marginBottom: 15 }, filterGroup: { gap: 7, paddingVertical: 3 },
  loading: { minHeight: 160, alignItems: 'center', justifyContent: 'center', gap: 10 }, muted: { color: colors.muted, fontSize: 14, lineHeight: 21 }, notice: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 16, padding: 22, gap: 5 }, noticeTitle: { color: colors.ink, fontSize: 16, fontWeight: '800' },
  resourceGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, resourceSlot: { flexGrow: 1, flexBasis: 320, minWidth: 0, maxWidth: 530 }, resourceCard: { width: '31.9%', minWidth: 270, minHeight: 310, backgroundColor: colors.surface, borderRadius: 18, overflow: 'hidden', borderWidth: 1, borderColor: colors.line, borderTopWidth: 4 }, resourceVisual: { height: 132, alignItems: 'center', justifyContent: 'center', position: 'relative' }, resourceImage: { width: '100%', height: '100%' }, resourceVisualIcon: { fontSize: 40 }, resourceContent: { flex: 1, padding: 19 }, resourceKind: { fontSize: 9, fontWeight: '900', letterSpacing: 0.8, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 999 }, resourceKindOverlay: { position: 'absolute', top: 10, right: 10 }, resourceTitle: { color: colors.ink, fontSize: 17, lineHeight: 22, fontWeight: '900' }, resourceDescription: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 8 }, tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 14 }, tag: { color: colors.muted, fontSize: 10, fontWeight: '700', backgroundColor: colors.surfaceSoft, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 5 }, openText: { fontSize: 12, fontWeight: '800', marginTop: 'auto', paddingTop: 15 }, resultSummary: { color: colors.muted, fontSize: 12, textAlign: 'center' }, pagination: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 18 }, pageButton: { borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong }, pageButtonDisabled: { opacity: 0.4 }, pageButtonText: { color: colors.inkSecondary, fontSize: 12, fontWeight: '800' },
  selectedArea: { gap: 16, marginTop: 20 }, featureGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, featureCard: { flexBasis: '30%', flexGrow: 1, minWidth: 240, minHeight: 180, padding: 18, borderRadius: 18, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong }, featureCardPhone: { flexBasis: '46%', minWidth: 0, minHeight: 150, padding: 13 }, featureIconBubble: { width: 42, height: 42, borderRadius: 12, borderWidth: 1, alignItems: 'center', justifyContent: 'center' }, featureIcon: { fontSize: 21, fontWeight: '900' }, featureTitle: { color: colors.ink, fontSize: 16, fontWeight: '900', marginTop: 11 }, featureTitlePhone: { fontSize: 14, lineHeight: 18 }, featureBody: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 6, flex: 1 }, featureAction: { fontSize: 11, fontWeight: '900', marginTop: 12 },
  previewPanel: { backgroundColor: colors.surface, borderRadius: 22, padding: 24, borderWidth: 1, borderColor: colors.lineStrong, marginTop: 18, overflow: 'hidden' }, previewImage: { width: '100%', height: 230, borderRadius: 16, marginBottom: 20 }, previewHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }, previewHeading: { flex: 1, flexDirection: 'row', gap: 13 }, previewIcon: { fontSize: 30 }, previewEyebrow: { color: '#2563EB', fontSize: 9, fontWeight: '900', letterSpacing: 1 }, previewTitle: { color: colors.ink, fontSize: 22, lineHeight: 28, fontWeight: '900', marginTop: 4 }, closeButton: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: colors.surfaceSoft, borderRadius: 9 }, closeText: { color: colors.muted, fontSize: 12, fontWeight: '800' }, previewDescription: { color: colors.muted, fontSize: 15, lineHeight: 24, marginVertical: 20 }, detailGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 }, detailItem: { minWidth: 140, backgroundColor: colors.canvas, borderRadius: 12, padding: 12 }, detailLabel: { color: colors.subtle, fontSize: 9, fontWeight: '900', letterSpacing: 0.7 }, detailValue: { color: colors.ink, fontSize: 13, fontWeight: '700', marginTop: 4 },
  goalSection: { borderTopWidth: 1, borderTopColor: colors.line }, goalLayout: { flexDirection: 'row', gap: 22 }, goalLayoutCompact: { flexDirection: 'column', alignItems: 'stretch' }, goalPanelCompact: { flexGrow: 0, flexShrink: 0, flexBasis: 'auto', width: '100%', minWidth: 0 }, goalForm: { flex: 1.2, backgroundColor: colors.surface, borderRadius: 22, padding: 24, borderWidth: 1, borderColor: colors.line }, goalFilters: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, goalFilterCell: { flexGrow: 1, flexBasis: 190, minWidth: 180, gap: 5 }, goalFilterLabel: { color: colors.ink, fontSize: 10, fontWeight: '800' }, fieldLabel: { color: colors.inkSecondary, fontSize: 12, fontWeight: '800', marginTop: 14, marginBottom: 8 }, wrapChoices: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, inputRow: { flexDirection: 'row', gap: 12 }, inputCell: { flex: 1 }, rateHint: { color: colors.muted, fontSize: 11, marginVertical: 10 }, goalResult: { flex: 0.8, minHeight: 390, backgroundColor: colors.navDark, borderRadius: 22, padding: 26, justifyContent: 'center' }, goalResultIdle: { alignItems: 'center' }, resultIcon: { fontSize: 38 }, resultTitle: { color: colors.inverse, fontSize: 20, fontWeight: '900', marginTop: 15 }, resultBody: { color: colors.subtle, fontSize: 13, lineHeight: 20, marginTop: 5, textAlign: 'center' }, resultTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, resultKicker: { color: '#93C5FD', fontSize: 10, fontWeight: '900', letterSpacing: 1 }, feasibility: { fontSize: 12, fontWeight: '900' }, goalAmount: { color: colors.inverse, fontSize: 44, fontWeight: '900', letterSpacing: -1, marginTop: 24 }, metrics: { flexDirection: 'row', gap: 8, marginVertical: 26 }, metric: { flex: 1, backgroundColor: colors.navDarkSoft, borderRadius: 13, padding: 12 }, metricValue: { color: colors.inverse, fontSize: 22, fontWeight: '900' }, metricLabel: { color: colors.subtle, fontSize: 9, marginTop: 3 }, advice: { color: colors.inverseMuted, fontSize: 13, lineHeight: 20, marginBottom: 22 }, secondaryButton: { borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 12, padding: 13, alignItems: 'center' }, secondaryButtonText: { color: colors.inverse, fontSize: 13, fontWeight: '800' },
  finalCta: { backgroundColor: colors.navDark, borderRadius: 28, padding: 54, alignItems: 'center', marginVertical: 40 }, finalEyebrow: { color: colors.inverseMuted, fontSize: 10, fontWeight: '900', letterSpacing: 1.2 }, finalTitle: { color: colors.inverse, fontSize: 38, lineHeight: 45, fontWeight: '900', textAlign: 'center', maxWidth: 760, marginTop: 12 }, finalBody: { color: colors.inverseMuted, fontSize: 15, lineHeight: 23, textAlign: 'center', maxWidth: 620, marginTop: 13 }, lightButton: { backgroundColor: '#FFFFFF', borderRadius: 12, paddingHorizontal: 22, paddingVertical: 14, marginTop: 24 }, lightButtonText: { color: '#1D4ED8', fontWeight: '900' },
  footer: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 10, paddingTop: 20, borderTopWidth: 1, borderTopColor: colors.line }, footerBrand: { color: colors.ink, fontSize: 13, fontWeight: '900', letterSpacing: 1.4 }, footerText: { color: colors.subtle, fontSize: 12 }, stack: { flexDirection: 'column', alignItems: 'stretch' },
});
