/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useRef, useState } from 'react';
import { router } from 'expo-router';
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

import { Field } from '@/components/ui';
import { ResourceFilters } from '@/components/resource-filters';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { PublicResourceViewer } from '@/components/public-resource-viewer';
import { PublicPractice } from '@/components/public-practice';
import { PublicSmartTool } from '@/components/public-smart-tool';
import type { SmartToolKind } from '@/services/smart-tools';
import { publicExploreCopy } from '@/lib/public-explore-copy';
import { materialFromPublic, type PracticeMaterial } from '@/services/student-practice';
import { PreferenceSwitcher } from '@/components/preference-switcher';
import { formatPublicCopy, publicCopy } from '@/lib/public-copy';
import { publicConfig } from '@/lib/supabase';
import { useAppPreferences } from '@/providers/app-preferences';
import { getPublicResourcePreviewImages, getPublicResources, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import { colors } from '@/theme';
import { canonicalSubjectLabel } from '@/lib/subjects';

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
  const { t, language } = useAppPreferences();
  const copy = publicCopy(language);
  const explore = publicExploreCopy(language);
  const { width } = useWindowDimensions();
  const compact = width < 780;
  const pageRef = useRef<ScrollView>(null);
  const resourcesY = useRef(0);
  const goalY = useRef(0);
  const hydratedImages = useRef(new Set<string>());
  const [resources, setResources] = useState<PublicResource[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [resourceError, setResourceError] = useState('');
  const [kind, setKind] = useState<PublicResourceKind>('program');
  const [query, setQuery] = useState('');
  const [subject, setSubject] = useState('All subjects');
  const [stage, setStage] = useState('All stages');
  const [level, setLevel] = useState('All levels');
  const [resourcePage, setResourcePage] = useState(1);
  const [selected, setSelected] = useState<PublicResource | null>(null);
  const [practiceMaterial, setPracticeMaterial] = useState<PracticeMaterial | null>(null);
  const [openTool, setOpenTool] = useState<SmartToolKind | null>(null);
  const [goalSubject, setGoalSubject] = useState('English');
  const [modality, setModality] = useState<'Online' | 'In person'>('Online');
  const [audience, setAudience] = useState<'Kids' | 'Teens' | 'Adults'>('Adults');
  const [education, setEducation] = useState<'Student' | 'Bachelor’s' | 'Master’s' | 'Doctorate'>('Master’s');
  const [hourlyRate, setHourlyRate] = useState('40');
  const [incomeGoal, setIncomeGoal] = useState('50000');
  const [showPlan, setShowPlan] = useState(false);
  const [audienceView, setAudienceView] = useState<'teacher' | 'student'>('teacher');
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

  const subjects = useMemo(() => {
    const values = resources.filter((item) => item.kind === kind).map((item) => item.subject).filter(Boolean);
    return ['All subjects', ...Array.from(new Set(values)).sort()];
  }, [kind, resources]);

  const stages = useMemo(() => ['All stages', ...Array.from(new Set(resources.filter((item) => item.kind === kind).map((item) => item.stage).filter(Boolean))).sort()], [kind, resources]);
  const levels = useMemo(() => ['All levels', ...Array.from(new Set(resources.filter((item) => item.kind === kind).map((item) => item.level).filter(Boolean))).sort()], [kind, resources]);

  const visibleResources = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return resources.filter((item) => {
      if (item.kind !== kind) return false;
      if (subject !== 'All subjects' && item.subject !== subject) return false;
      if (stage !== 'All stages' && item.stage !== stage) return false;
      if (level !== 'All levels' && item.level !== level) return false;
      if (!needle) return true;
      return [item.title, item.subject, item.topic, item.stage, item.level, item.author, item.description]
        .join(' ')
        .toLowerCase()
        .includes(needle);
    });
  }, [kind, level, query, resources, stage, subject]);

  useEffect(() => setResourcePage(1), [kind, level, query, stage, subject]);

  const totalResourcePages = Math.max(1, Math.ceil(visibleResources.length / 9));
  const pagedResources = visibleResources.slice((resourcePage - 1) * 9, resourcePage * 9);
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

  return (
    <>
      <Head>
        <title>{copy.metaTitle}</title>
        <meta name="description" content={copy.metaDescription} />
      </Head>
      <ScrollView ref={pageRef} contentContainerStyle={styles.page}>
        <SafeAreaView style={styles.shell}>
          <View style={[styles.header, compact && styles.headerCompact]}>
            <Image accessibilityLabel="Classio" resizeMode="contain" source={require('../../assets/images/classio-logo.png')} style={styles.logo} />
            <View style={styles.headerActions}>
              <PreferenceSwitcher />
              {!compact ? <Pressable onPress={() => pageRef.current?.scrollTo({ y: resourcesY.current, animated: true })}><Text style={styles.headerLink}>{t('public.exploreResources')}</Text></Pressable> : null}
              {!compact ? <Pressable onPress={() => pageRef.current?.scrollTo({ y: goalY.current, animated: true })}><Text style={styles.headerLink}>{t('public.incomePlanner')}</Text></Pressable> : null}
              <Pressable onPress={() => router.push('/sign-in')} style={styles.signInButton}><Text style={styles.signInText}>{t('auth.signIn')}</Text></Pressable>
            </View>
          </View>

          <View style={[styles.hero, compact && styles.heroCompact]}>
            <View style={styles.heroCopy}>
              <View style={styles.livePill}><View style={styles.liveDot} /><Text style={styles.liveText}>{copy.heroEyebrow}</Text></View>
              <Text style={[styles.heroTitle, compact && styles.heroTitleCompact]}>{copy.heroTitle}</Text>
              <Text style={styles.heroBody}>{copy.heroBody}</Text>
              <View style={[styles.heroActions, compact && styles.stack]}>
                <Pressable accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.primaryButton}><Text style={styles.primaryButtonText}>{copy.teach}</Text></Pressable>
                <Pressable accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.secondaryHeroButton}><Text style={styles.secondaryHeroText}>{copy.study}</Text></Pressable>
              </View>
              <Pressable onPress={() => pageRef.current?.scrollTo({ y: resourcesY.current, animated: true })} style={styles.proofRow}><Text style={styles.proofIcons}>✦</Text><Text style={styles.proofText}>{copy.freeResources}</Text></Pressable>
            </View>
            <View style={styles.previewColumn}>
              <View style={styles.audienceSwitch}><Choice active={audienceView === 'teacher'} onPress={() => setAudienceView('teacher')}>{copy.teacherCardEyebrow}</Choice><Choice active={audienceView === 'student'} onPress={() => setAudienceView('student')}>{copy.studentCardEyebrow}</Choice></View>
              {audienceView === 'teacher' ? <View style={styles.dayCard}>
                <View style={styles.dayHeader}><View><Text style={styles.dayKicker}>{copy.teacherPreviewKicker}</Text><Text style={styles.dayTitle}>{copy.teacherPreview}</Text></View><View style={styles.avatar}><Text style={styles.avatarText}>T</Text></View></View>
                {[
                  ['09:00', copy.lessonOne, copy.lessonOneNote, colors.primary],
                  ['11:30', copy.lessonTwo, copy.lessonTwoNote, colors.violet],
                  ['15:00', copy.lessonThree, copy.lessonThreeNote, colors.success],
                ].map(([time, name, note, accent]) => <View key={time} style={styles.lessonRow}><View style={[styles.lessonAccent, { backgroundColor: accent }]} /><Text style={styles.lessonTime}>{time}</Text><View style={styles.lessonCopy}><Text style={styles.lessonName}>{name}</Text><Text style={styles.lessonNote}>{note}</Text></View></View>)}
                <View style={styles.nextAction}><Text style={styles.nextIcon}>✨</Text><View style={styles.lessonCopy}><Text style={styles.nextTitle}>{copy.nextAction}</Text><Text style={styles.nextBody}>{copy.nextActionBody}</Text></View></View>
              </View> : <View style={styles.dayCard}>
                <View style={styles.dayHeader}><View><Text style={styles.dayKicker}>{copy.studentPreviewKicker}</Text><Text style={styles.dayTitle}>{copy.studentPreview}</Text></View><View style={styles.avatar}><Text style={styles.avatarText}>S</Text></View></View>
                {[["01", copy.studentStepOne, copy.studentStepOneBody], ["02", copy.studentStepTwo, copy.studentStepTwoBody], ["03", copy.studentStepThree, copy.studentStepThreeBody]].map(([number, title, body]) => <View key={number} style={styles.lessonRow}><Text style={styles.studentStepNumber}>{number}</Text><View style={styles.lessonCopy}><Text style={styles.lessonName}>{title}</Text><Text style={styles.lessonNote}>{body}</Text></View></View>)}
                <Pressable onPress={() => router.push('/sign-in')} style={styles.studentPreviewAction}><Text style={styles.studentPreviewActionText}>{copy.findTeacher} →</Text></Pressable>
              </View>}
            </View>
          </View>

          <View style={[styles.audienceCards, compact && styles.stack]}>
            <Pressable accessibilityRole="button" onPress={() => { setAudienceView('teacher'); pageRef.current?.scrollTo({ y: 0, animated: true }); }} style={styles.audienceCard}><Text style={styles.audienceEyebrow}>{copy.teacherCardEyebrow}</Text><Text style={styles.audienceTitle}>{copy.teacherCardTitle}</Text><Text style={styles.audienceBody}>{copy.teacherCardBody}</Text><Text style={styles.audienceAction}>{copy.teacherCardAction} ↗</Text></Pressable>
            <Pressable accessibilityRole="button" onPress={() => { setAudienceView('student'); pageRef.current?.scrollTo({ y: 0, animated: true }); }} style={styles.audienceCard}><Text style={styles.audienceEyebrow}>{copy.studentCardEyebrow}</Text><Text style={styles.audienceTitle}>{copy.studentCardTitle}</Text><Text style={styles.audienceBody}>{copy.studentCardBody}</Text><Text style={styles.audienceAction}>{copy.studentCardAction} ↗</Text></Pressable>
          </View>

          <View style={styles.section}>
            <PublicPractice />
          </View>

          <View style={styles.section}>
            <SectionHeading eyebrow={explore.featureEyebrow} title={explore.featureTitle} body={explore.featureBody} />
            <View style={styles.featureGrid}>
              {([['◫', explore.featureDashboard, explore.featureDashboardBody], ['◉', explore.featureStudents, explore.featureStudentsBody], ['✎', explore.featureLessons, explore.featureLessonsBody], ['◇', explore.featurePayments, explore.featurePaymentsBody], ['▦', explore.featureCalendar, explore.featureCalendarBody], ['▥', explore.featureAnalytics, explore.featureAnalyticsBody]] as const).map(([icon, title, body]) => <Pressable key={title} accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.featureCard}><Text style={styles.featureIcon}>{icon}</Text><Text style={styles.featureTitle}>{title}</Text><Text style={styles.featureBody}>{body}</Text><Text style={styles.featureAction}>{explore.featureAction} ↗</Text></Pressable>)}
            </View>
          </View>

          <View style={styles.section}>
            <SectionHeading eyebrow={copy.toolsEyebrow} title={copy.toolsTitle} body={copy.toolsBody} />
            <View style={[styles.cardGrid, compact && styles.stack]}>
              {TOOLS.map((tool, index) => <Pressable key={tool.title} accessibilityRole="button" accessibilityLabel={copy[tool.title]} onPress={() => setOpenTool(['plan', 'worksheet', 'exam', 'program'][index] as SmartToolKind)} style={[styles.toolCard, { backgroundColor: tool.tint, borderColor: colors.lineStrong }]}><View pointerEvents="none" style={styles.toolWash} /><View style={styles.toolTop}><Text style={styles.toolIcon}>{tool.icon}</Text><Text style={[styles.toolBadge, { color: tool.accent }]}>{copy[tool.badge]}</Text></View><Text style={styles.toolTitle}>{copy[tool.title]}</Text><Text style={styles.toolBody}>{copy[tool.copy]}</Text><Text style={[styles.toolAction, { color: tool.accent }]}>{copy.toolTry} →</Text></Pressable>)}
            </View>
            {openTool ? <View style={styles.selectedArea}><PublicSmartTool key={openTool} initial={openTool} onClose={() => setOpenTool(null)} /></View> : null}
          </View>

          <View style={styles.section} onLayout={(event) => { resourcesY.current = event.nativeEvent.layout.y; }}>
            <SectionHeading eyebrow={copy.libraryEyebrow} title={copy.libraryTitle} body={copy.libraryBody} />
            <View style={styles.resourceTabs}>
              {(Object.keys(RESOURCE_META) as PublicResourceKind[]).map((key) => <Choice key={key} active={kind === key} onPress={() => { setKind(key); setSubject('All subjects'); setStage('All stages'); setLevel('All levels'); setSelected(null); }}>{`${RESOURCE_META[key].icon} ${copy[RESOURCE_META[key].label]}`}</Choice>)}
            </View>
            <ResourceFilters query={query} onQueryChange={setQuery} count={resourcesLoading ? undefined : visibleResources.length} searchLabel={copy.searchResources} facets={[
              { key: 'subject', label: t('resources.subject'), value: subject, allValue: 'All subjects', allLabel: t('resources.allSubjects'), options: subjects.slice(1).map((value) => ({ value, label: canonicalSubjectLabel(value, t) })), onChange: setSubject },
              { key: 'stage', label: t('resources.stage'), value: stage, allValue: 'All stages', allLabel: t('resources.allStages'), options: stages.slice(1).map((value) => ({ value, label: value.replaceAll('_', ' ') })), onChange: setStage },
              { key: 'level', label: t('resources.level'), value: level, allValue: 'All levels', allLabel: t('resources.allLevels'), options: levels.slice(1).map((value) => ({ value, label: value })), onChange: setLevel },
            ]} />
            {resourcesLoading ? <View style={styles.loading}><ActivityIndicator color={colors.primary} /><Text style={styles.muted}>{copy.libraryLoading}</Text></View> : null}
            {resourceError ? <View style={styles.notice}><Text style={styles.noticeTitle}>{copy.libraryUnavailable}</Text><Text style={styles.muted}>{resourceError}</Text></View> : null}
            {!resourcesLoading && !resourceError && visibleResources.length === 0 ? <View style={styles.notice}><Text style={styles.noticeTitle}>{copy.noMatches}</Text><Text style={styles.muted}>{copy.noMatchesBody}</Text></View> : null}
            <View style={[styles.resourceGrid, compact && styles.stack]}>
              {pagedResources.map((item) => <ResourceShowcaseCard key={`${item.kind}-${item.id}`} item={item} onPress={() => setSelected(item)} description={item.description || item.topic || copy.resourceFallback} eyebrow={copy[RESOURCE_META[item.kind].label]} />)}
            </View>
            {visibleResources.length > 9 ? <View style={styles.pagination}><Pressable disabled={resourcePage === 1} onPress={() => setResourcePage((value) => Math.max(1, value - 1))} style={[styles.pageButton, resourcePage === 1 && styles.pageButtonDisabled]}><Text style={styles.pageButtonText}>← {copy.previous}</Text></Pressable><Text style={styles.resultSummary}>{formatPublicCopy(copy.page, { page: resourcePage, total: totalResourcePages, count: visibleResources.length })}</Text><Pressable disabled={resourcePage === totalResourcePages} onPress={() => setResourcePage((value) => Math.min(totalResourcePages, value + 1))} style={[styles.pageButton, resourcePage === totalResourcePages && styles.pageButtonDisabled]}><Text style={styles.pageButtonText}>{copy.next} →</Text></Pressable></View> : null}
            {selected ? <View style={styles.selectedArea}><PublicResourceViewer selected={selected} onClose={() => { setSelected(null); setPracticeMaterial(null); }} onPractice={(resource) => setPracticeMaterial(materialFromPublic(resource))} />{practiceMaterial ? <PublicPractice material={practiceMaterial} onClose={() => setPracticeMaterial(null)} /> : null}</View> : null}
          </View>

          <View style={[styles.section, styles.goalSection]} onLayout={(event) => { goalY.current = event.nativeEvent.layout.y; }}>
            <SectionHeading eyebrow={copy.goalEyebrow} title={copy.goalTitle} body={copy.goalBody} />
            <View style={[styles.goalLayout, compact && styles.stack]}>
              <View style={styles.goalForm}>
                <Text style={styles.fieldLabel}>{copy.goalSubject}</Text><View style={styles.wrapChoices}>{Object.keys(RATE_RANGES).map((item) => <Choice key={item} active={goalSubject === item} onPress={() => chooseGoalSubject(item)}>{subjectLabels[item]}</Choice>)}</View>
                <Text style={styles.fieldLabel}>{copy.goalModality}</Text><View style={styles.wrapChoices}>{(['Online', 'In person'] as const).map((item) => <Choice key={item} active={modality === item} onPress={() => { setModality(item); setShowPlan(false); }}>{modalityLabels[item]}</Choice>)}</View>
                <Text style={styles.fieldLabel}>{copy.goalAudience}</Text><View style={styles.wrapChoices}>{(['Kids', 'Teens', 'Adults'] as const).map((item) => <Choice key={item} active={audience === item} onPress={() => { setAudience(item); setShowPlan(false); }}>{audienceLabels[item]}</Choice>)}</View>
                <Text style={styles.fieldLabel}>{copy.goalEducation}</Text><View style={styles.wrapChoices}>{(['Student', 'Bachelor’s', 'Master’s', 'Doctorate'] as const).map((item) => <Choice key={item} active={education === item} onPress={() => { setEducation(item); setShowPlan(false); }}>{educationLabels[item]}</Choice>)}</View>
                <View style={[styles.inputRow, compact && styles.stack]}><View style={styles.inputCell}><Text style={styles.fieldLabel}>{copy.goalRate}</Text><Field keyboardType="numeric" value={hourlyRate} onChangeText={(value) => { setHourlyRate(value); setShowPlan(false); }} /></View><View style={styles.inputCell}><Text style={styles.fieldLabel}>{copy.goalYearly}</Text><Field keyboardType="numeric" value={incomeGoal} onChangeText={(value) => { setIncomeGoal(value); setShowPlan(false); }} /></View></View>
                <Text style={styles.rateHint}>{formatPublicCopy(copy.goalRange, { subject: subjectLabels[goalSubject].toLocaleLowerCase(language), low: RATE_RANGES[goalSubject][0], high: RATE_RANGES[goalSubject][2] })}</Text>
                <Pressable onPress={() => setShowPlan(true)} style={styles.primaryButton}><Text style={styles.primaryButtonText}>{copy.goalBuild}</Text></Pressable>
              </View>
              <View style={[styles.goalResult, !showPlan && styles.goalResultIdle]}>
                {!showPlan ? <><Text style={styles.resultIcon}>🎯</Text><Text style={styles.resultTitle}>{copy.goalIdleTitle}</Text><Text style={styles.resultBody}>{copy.goalIdleBody}</Text></> : <><View style={styles.resultTop}><Text style={styles.resultKicker}>{copy.goalPlan}</Text><Text style={[styles.feasibility, { color: feasibility[1] }]}>{feasibility[0]}</Text></View><Text style={styles.goalAmount}>${goal.toLocaleString()}</Text><Text style={styles.resultBody}>{copy.goalAnnual}</Text><View style={styles.metrics}><View style={styles.metric}><Text style={styles.metricValue}>{annualHours}</Text><Text style={styles.metricLabel}>{copy.goalHoursYear}</Text></View><View style={styles.metric}><Text style={styles.metricValue}>{weeklyHours}</Text><Text style={styles.metricLabel}>{copy.goalHoursWeek}</Text></View><View style={styles.metric}><Text style={styles.metricValue}>{studentsNeeded}</Text><Text style={styles.metricLabel}>{copy.goalStudents}</Text></View></View><Text style={styles.advice}>{feasibility[2]}</Text><Pressable onPress={() => router.push('/sign-in')} style={styles.secondaryButton}><Text style={styles.secondaryButtonText}>{copy.goalCreate}</Text></Pressable></>}
              </View>
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
  headerCompact: { minHeight: 64 }, logo: { width: 154, height: 54 }, headerActions: { flexDirection: 'row', alignItems: 'center', gap: 24 },
  headerLink: { color: colors.muted, fontSize: 14, fontWeight: '600' }, signInButton: { backgroundColor: colors.navDark, borderRadius: 12, paddingHorizontal: 18, paddingVertical: 12 }, signInText: { color: colors.inverse, fontWeight: '800' },
  hero: { minHeight: 610, flexDirection: 'row', alignItems: 'center', gap: 64, paddingVertical: 68 }, heroCompact: { minHeight: 0, flexDirection: 'column', alignItems: 'stretch', gap: 38, paddingVertical: 44 }, heroCopy: { flex: 1.12 },
  livePill: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.successSoft, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7, marginBottom: 22 }, liveDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#10B981' }, liveText: { color: '#047857', fontSize: 10, fontWeight: '800', letterSpacing: 1 },
  heroTitle: { color: colors.ink, fontSize: 62, lineHeight: 66, fontWeight: '900', letterSpacing: -2.5 }, heroTitleCompact: { fontSize: 42, lineHeight: 47, letterSpacing: -1.4 }, heroBody: { color: colors.muted, fontSize: 18, lineHeight: 29, maxWidth: 620, marginTop: 24 }, heroActions: { flexDirection: 'row', alignItems: 'center', gap: 18, marginTop: 30 },
  primaryButton: { alignSelf: 'flex-start', backgroundColor: colors.primary, borderRadius: 13, paddingHorizontal: 20, paddingVertical: 15 }, primaryButtonText: { color: colors.inverse, fontSize: 15, fontWeight: '800' }, secondaryHeroButton: { alignSelf: 'flex-start', backgroundColor: colors.surface, borderColor: colors.primary, borderWidth: 1, borderRadius: 13, paddingHorizontal: 20, paddingVertical: 14 }, secondaryHeroText: { color: colors.primary, fontSize: 15, fontWeight: '800' }, proofRow: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 18 }, proofIcons: { color: colors.success, fontWeight: '900' }, proofText: { color: colors.muted, fontSize: 13, fontWeight: '600' },
  previewColumn: { flex: 0.88, minWidth: 320, gap: 12 }, audienceSwitch: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, studentStepNumber: { color: colors.primary, fontSize: 13, fontWeight: '900', width: 42 }, studentPreviewAction: { backgroundColor: colors.primarySoft, borderRadius: 12, padding: 13, marginTop: 14, alignItems: 'center' }, studentPreviewActionText: { color: colors.primary, fontSize: 12, fontWeight: '900' }, audienceCards: { flexDirection: 'row', gap: 14 }, audienceCard: { flex: 1, minWidth: 280, borderRadius: 20, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surface, padding: 22 }, audienceEyebrow: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, audienceTitle: { color: colors.ink, fontSize: 22, fontWeight: '900', marginTop: 10 }, audienceBody: { color: colors.muted, fontSize: 13, lineHeight: 20, marginTop: 8 }, audienceAction: { color: colors.primary, fontSize: 12, fontWeight: '900', marginTop: 18 },
  dayCard: { backgroundColor: colors.surface, borderRadius: 26, padding: 26, borderWidth: 1, borderColor: colors.line, shadowColor: colors.shadow, shadowOpacity: 0.1, shadowRadius: 28, shadowOffset: { width: 0, height: 16 } }, dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }, dayKicker: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, dayTitle: { color: colors.ink, fontSize: 22, fontWeight: '900', marginTop: 5 }, avatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' }, avatarText: { color: colors.primary, fontWeight: '900' },
  lessonRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, borderTopWidth: 1, borderTopColor: colors.line }, lessonAccent: { width: 4, height: 42, borderRadius: 4 }, lessonTime: { color: colors.muted, width: 42, fontSize: 12, fontWeight: '700' }, lessonCopy: { flex: 1 }, lessonName: { color: colors.ink, fontWeight: '800', fontSize: 14 }, lessonNote: { color: colors.muted, fontSize: 12, marginTop: 3 }, nextAction: { flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: colors.surfaceSoft, borderRadius: 14, padding: 14, marginTop: 8 }, nextIcon: { fontSize: 22 }, nextTitle: { color: colors.violet, fontSize: 11, fontWeight: '900', letterSpacing: 0.5 }, nextBody: { color: colors.inkSecondary, fontSize: 13, marginTop: 3 },
  valueStrip: { flexDirection: 'row', backgroundColor: colors.navDark, borderRadius: 22, paddingVertical: 22, paddingHorizontal: 28, gap: 18 }, valueItem: { flex: 1, alignItems: 'center', borderRightWidth: 1, borderRightColor: colors.navDarkSoft }, valueNumber: { color: colors.inverse, fontSize: 25, fontWeight: '900' }, valueLabel: { color: colors.subtle, fontSize: 12, marginTop: 3 },
  section: { paddingVertical: 84 }, sectionHeading: { maxWidth: 720, marginBottom: 34 }, eyebrow: { color: '#2563EB', fontSize: 11, fontWeight: '900', letterSpacing: 1.3, marginBottom: 10 }, sectionTitle: { color: colors.ink, fontSize: 38, lineHeight: 44, fontWeight: '900', letterSpacing: -1 }, sectionBody: { color: colors.muted, fontSize: 16, lineHeight: 25, marginTop: 12 },
  cardGrid: { flexDirection: 'row', gap: 14 }, toolCard: { flex: 1, minHeight: 250, borderRadius: 20, padding: 20, borderWidth: 1, overflow: 'hidden' }, toolWash: { position: 'absolute', inset: 0, backgroundColor: colors.surface, opacity: 0.82 }, toolTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 25 }, toolIcon: { fontSize: 28 }, toolBadge: { fontSize: 9, fontWeight: '900', letterSpacing: 1 }, toolTitle: { color: colors.ink, fontSize: 19, fontWeight: '900' }, toolBody: { color: colors.muted, fontSize: 13, lineHeight: 20, marginTop: 9, flex: 1 }, toolAction: { fontSize: 13, fontWeight: '800', marginTop: 18 },
  resourceTabs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 }, choice: { borderRadius: 999, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surface, paddingHorizontal: 14, paddingVertical: 9 }, choiceActive: { backgroundColor: colors.primary, borderColor: colors.primary }, choiceText: { color: colors.muted, fontSize: 12, fontWeight: '700' }, choiceTextActive: { color: colors.inverse }, search: { marginTop: 4 }, subjects: { gap: 8, paddingVertical: 13 }, filterRow: { gap: 8, marginBottom: 15 }, filterGroup: { gap: 7, paddingVertical: 3 },
  loading: { minHeight: 160, alignItems: 'center', justifyContent: 'center', gap: 10 }, muted: { color: colors.muted, fontSize: 14, lineHeight: 21 }, notice: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 16, padding: 22, gap: 5 }, noticeTitle: { color: colors.ink, fontSize: 16, fontWeight: '800' },
  resourceGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, resourceCard: { width: '31.9%', minWidth: 270, minHeight: 310, backgroundColor: colors.surface, borderRadius: 18, overflow: 'hidden', borderWidth: 1, borderColor: colors.line, borderTopWidth: 4 }, resourceVisual: { height: 132, alignItems: 'center', justifyContent: 'center', position: 'relative' }, resourceImage: { width: '100%', height: '100%' }, resourceVisualIcon: { fontSize: 40 }, resourceContent: { flex: 1, padding: 19 }, resourceKind: { fontSize: 9, fontWeight: '900', letterSpacing: 0.8, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 999 }, resourceKindOverlay: { position: 'absolute', top: 10, right: 10 }, resourceTitle: { color: colors.ink, fontSize: 17, lineHeight: 22, fontWeight: '900' }, resourceDescription: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 8 }, tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 14 }, tag: { color: colors.muted, fontSize: 10, fontWeight: '700', backgroundColor: colors.surfaceSoft, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 5 }, openText: { fontSize: 12, fontWeight: '800', marginTop: 'auto', paddingTop: 15 }, resultSummary: { color: colors.muted, fontSize: 12, textAlign: 'center' }, pagination: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 18 }, pageButton: { borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong }, pageButtonDisabled: { opacity: 0.4 }, pageButtonText: { color: colors.inkSecondary, fontSize: 12, fontWeight: '800' },
  selectedArea: { gap: 16, marginTop: 20 }, featureGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, featureCard: { flexBasis: '30%', flexGrow: 1, minWidth: 240, minHeight: 195, padding: 19, borderRadius: 18, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong }, featureIcon: { fontSize: 25, color: colors.primary }, featureTitle: { color: colors.ink, fontSize: 17, fontWeight: '900', marginTop: 12 }, featureBody: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 6, flex: 1 }, featureAction: { color: colors.primary, fontSize: 11, fontWeight: '800', marginTop: 12 },
  previewPanel: { backgroundColor: colors.surface, borderRadius: 22, padding: 24, borderWidth: 1, borderColor: colors.lineStrong, marginTop: 18, overflow: 'hidden' }, previewImage: { width: '100%', height: 230, borderRadius: 16, marginBottom: 20 }, previewHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }, previewHeading: { flex: 1, flexDirection: 'row', gap: 13 }, previewIcon: { fontSize: 30 }, previewEyebrow: { color: '#2563EB', fontSize: 9, fontWeight: '900', letterSpacing: 1 }, previewTitle: { color: colors.ink, fontSize: 22, lineHeight: 28, fontWeight: '900', marginTop: 4 }, closeButton: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: colors.surfaceSoft, borderRadius: 9 }, closeText: { color: colors.muted, fontSize: 12, fontWeight: '800' }, previewDescription: { color: colors.muted, fontSize: 15, lineHeight: 24, marginVertical: 20 }, detailGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 }, detailItem: { minWidth: 140, backgroundColor: colors.canvas, borderRadius: 12, padding: 12 }, detailLabel: { color: colors.subtle, fontSize: 9, fontWeight: '900', letterSpacing: 0.7 }, detailValue: { color: colors.ink, fontSize: 13, fontWeight: '700', marginTop: 4 },
  goalSection: { borderTopWidth: 1, borderTopColor: colors.line }, goalLayout: { flexDirection: 'row', gap: 22 }, goalForm: { flex: 1.2, backgroundColor: colors.surface, borderRadius: 22, padding: 24, borderWidth: 1, borderColor: colors.line }, fieldLabel: { color: colors.inkSecondary, fontSize: 12, fontWeight: '800', marginTop: 14, marginBottom: 8 }, wrapChoices: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, inputRow: { flexDirection: 'row', gap: 12 }, inputCell: { flex: 1 }, rateHint: { color: colors.muted, fontSize: 11, marginVertical: 10 }, goalResult: { flex: 0.8, minHeight: 390, backgroundColor: colors.navDark, borderRadius: 22, padding: 26, justifyContent: 'center' }, goalResultIdle: { alignItems: 'center' }, resultIcon: { fontSize: 38 }, resultTitle: { color: colors.inverse, fontSize: 20, fontWeight: '900', marginTop: 15 }, resultBody: { color: colors.subtle, fontSize: 13, lineHeight: 20, marginTop: 5, textAlign: 'center' }, resultTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, resultKicker: { color: '#93C5FD', fontSize: 10, fontWeight: '900', letterSpacing: 1 }, feasibility: { fontSize: 12, fontWeight: '900' }, goalAmount: { color: colors.inverse, fontSize: 44, fontWeight: '900', letterSpacing: -1, marginTop: 24 }, metrics: { flexDirection: 'row', gap: 8, marginVertical: 26 }, metric: { flex: 1, backgroundColor: colors.navDarkSoft, borderRadius: 13, padding: 12 }, metricValue: { color: colors.inverse, fontSize: 22, fontWeight: '900' }, metricLabel: { color: colors.subtle, fontSize: 9, marginTop: 3 }, advice: { color: colors.inverseMuted, fontSize: 13, lineHeight: 20, marginBottom: 22 }, secondaryButton: { borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 12, padding: 13, alignItems: 'center' }, secondaryButtonText: { color: colors.inverse, fontSize: 13, fontWeight: '800' },
  finalCta: { backgroundColor: colors.navDark, borderRadius: 28, padding: 54, alignItems: 'center', marginVertical: 40 }, finalEyebrow: { color: colors.inverseMuted, fontSize: 10, fontWeight: '900', letterSpacing: 1.2 }, finalTitle: { color: colors.inverse, fontSize: 38, lineHeight: 45, fontWeight: '900', textAlign: 'center', maxWidth: 760, marginTop: 12 }, finalBody: { color: colors.inverseMuted, fontSize: 15, lineHeight: 23, textAlign: 'center', maxWidth: 620, marginTop: 13 }, lightButton: { backgroundColor: '#FFFFFF', borderRadius: 12, paddingHorizontal: 22, paddingVertical: 14, marginTop: 24 }, lightButtonText: { color: '#1D4ED8', fontWeight: '900' },
  footer: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 10, paddingTop: 20, borderTopWidth: 1, borderTopColor: colors.line }, footerBrand: { color: colors.ink, fontSize: 13, fontWeight: '900', letterSpacing: 1.4 }, footerText: { color: colors.subtle, fontSize: 12 }, stack: { flexDirection: 'column', alignItems: 'stretch' },
});
