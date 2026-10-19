/* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
import { createElement, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { Linking, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { BackLink } from '@/components/back-link';
import { AppShell } from '@/components/app-shell';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { canonicalChoice, canonicalTrueFalse } from '@/services/student-practice-answer-normalization';
import { canonicalLearnerStageKey, learnerStageLabel } from '@/lib/learner-stages';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { ResourceFilters } from '@/components/resource-filters';
import { ActionFeedback, Button, Disclosure, EmptyState, Field, LoadingState, Pagination, Panel, SelectField, TabRail } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { extractResourceImageUrl, getPublicResourceDetail, getPublicResourcePreviewImages, type PublicResource } from '@/services/public-data';
import { getReviewableTeachers, getStudentAssignmentContent, getStudentAssignmentDraftSessionId, getStudentAssignmentForPractice, getStudentPracticeSession, getStudentWorkspace, type ReviewableTeacher, type StudentWorkspace } from '@/services/student-data';
import { getStudentPublicPracticeResources } from '@/services/student-resource-access';
import { gradePractice, loadPracticeReview, materialFromAssignment, materialFromPublic, practiceAnswerProgress, practiceRank, recordVideoWatch, repairVisiblePracticeHistory, requestTeacherReview, savePractice, savePracticeDraft, type PracticeMaterial, type PracticeResult } from '@/services/student-practice';
import { groupPracticeRows } from '@/services/student-practice-groups';
import { createStudentDraftSaveQueue } from '@/services/student-draft-save-queue';
import { colors } from '@/theme';

type Kind = 'worksheet' | 'exam' | 'video';
type PracticeItem = Omit<PublicResource, 'kind'> & { kind: Kind; assignmentId?: string; assignment?: Record<string, unknown>; score?: number; reason?: string; reasonLines?: string[]; historyPlayback?: boolean };
const PRACTICE_PAGE_SIZE = 18;
const LANGUAGE_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const ACADEMIC_LEVELS = ['beginner_band', 'intermediate_band', 'advanced_band'];
function subjectCatalogGroup(subject: string) {
  if (['english', 'spanish', 'turkish'].includes(subject)) return 'language';
  return subject;
}
function subjectLevelCatalog(subject: string) {
  return subject === '__all__' ? [...LANGUAGE_LEVELS, ...ACADEMIC_LEVELS]
    : subjectCatalogGroup(subject) === 'language' ? LANGUAGE_LEVELS : ACADEMIC_LEVELS;
}
function normalizedExerciseType(value: unknown) { return text(value).trim().toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_+|_+$/g, '').replace('fill_in_the_blanks', 'fill_in_blank'); }
function resourceExerciseTypes(item: PracticeItem) {
  const values = item.kind === 'worksheet' ? [item.raw.worksheet_type] : [];
  return values.map(normalizedExerciseType).filter(Boolean);
}
function text(value: unknown) { return typeof value === 'string' || typeof value === 'number' ? String(value) : ''; }
function videoUrl(item: PracticeItem) { const raw = item.raw; const nested = raw.video && typeof raw.video === 'object' ? raw.video as Record<string, unknown> : {}; return text(raw.youtube_url || raw.video_url || raw.watch_url || raw.url || raw.link || nested.youtube_url || nested.video_url || nested.url); }
function youtubeEmbedUrl(url: string) { const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([A-Za-z0-9_-]{6,})/); return match ? `https://www.youtube-nocookie.com/embed/${match[1]}` : ''; }
function exerciseName(item: PracticeItem, t: (key: string) => string) { const raw = text(item.raw.worksheet_type || item.raw.exam_length); if (!raw) return item.kind === 'video' ? t('student.videos') : t(`student.${item.kind}s`); const key = raw.replace('fill_in_the_blanks', 'fill_in_blank'); const translated = t(`student.exercise.${key}`); return translated === `student.exercise.${key}` ? raw.replaceAll('_', ' ') : translated; }
function ResourceCard({ item, onPress, t, busy = false }: { item: PracticeItem; onPress: () => void; t: (key: string) => string; busy?: boolean }) {
  return <View style={styles.resourceSlot}>
    <ResourceShowcaseCard compact item={item} onPress={() => { if (!busy) onPress(); }} eyebrow={item.assignmentId ? t('student.assignedByTeacher') : exerciseName(item, t)} description={item.topic || item.description || t('resources.noDescription')} />
  </View>;
}
function wordSearchLine(start: [number, number], end: [number, number]) { const [sr, sc] = start; const [er, ec] = end; const dr = er - sr; const dc = ec - sc; if (dr !== 0 && dc !== 0 && Math.abs(dr) !== Math.abs(dc)) return []; const stepR = dr === 0 ? 0 : dr > 0 ? 1 : -1; const stepC = dc === 0 ? 0 : dc > 0 ? 1 : -1; const length = Math.max(Math.abs(dr), Math.abs(dc)) + 1; return Array.from({ length }, (_, index) => [sr + stepR * index, sc + stepC * index] as [number, number]); }
function sameCoords(left: [number, number][], right: [number, number][]) { return left.length === right.length && left.every(([row, col], index) => row === right[index]?.[0] && col === right[index]?.[1]); }
function WordSearchAnswer({ question, index, answers, result, setAnswers, t }: { question: PracticeMaterial['questions'][number]; index: number; answers: Record<string, string>; result: PracticeResult | null; setAnswers: Dispatch<SetStateAction<Record<string, string>>>; t: (key: string, params?: Record<string, string | number>) => string }) {
  const [start, setStart] = useState<[number, number] | null>(null); const [end, setEnd] = useState<[number, number] | null>(null); const [notice, setNotice] = useState(''); const grid = question.grid ?? []; const words = question.words ?? []; let found: string[] = []; try { found = JSON.parse(answers[String(index)] || '[]'); } catch { found = []; } const foundSet = new Set(found); const foundCells = new Set((question.placements ?? []).filter((item) => foundSet.has(item.word)).flatMap((item) => item.coords.map(([row, col]) => `${row}:${col}`))); const selectedCells = new Set(start && end ? wordSearchLine(start, end).map(([row, col]) => `${row}:${col}`) : start ? [`${start[0]}:${start[1]}`] : []); const choose = (coord: [number, number]) => { if (result) return; if (!start || end) { setStart(coord); setEnd(null); setNotice(t('student.wordSearchChooseEnd')); return; } setEnd(coord); const line = wordSearchLine(start, coord); const match = (question.placements ?? []).find((item) => sameCoords(item.coords, line) || sameCoords([...item.coords].reverse(), line)); if (match) { const next = [...new Set([...found, match.word])]; setAnswers((current) => ({ ...current, [String(index)]: JSON.stringify(next) })); setNotice(foundSet.has(match.word) ? t('student.wordSearchAlreadyFound', { word: match.word }) : t('student.wordSearchFound', { word: match.word })); } else setNotice(t('student.wordSearchTryAgain')); setTimeout(() => { setStart(null); setEnd(null); }, 350); };
  return <View style={styles.wordSearch}><Text style={styles.wordSearchHelp}>{t('student.wordSearchHelp')}</Text><View style={styles.wordProgress}><View style={[styles.wordProgressFill, { width: `${words.length ? Math.round(found.length / words.length * 100) : 0}%` }]} /></View><Text style={styles.wordProgressLabel}>{t('student.wordSearchProgress', { found: found.length, total: words.length })}</Text><View style={styles.wordChips}>{words.map((word) => <Text key={word} style={[styles.wordChip, foundSet.has(word) && styles.wordChipFound]}>{foundSet.has(word) ? '✓ ' : ''}{word}</Text>)}</View>{grid.length ? <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={styles.wordBoardWrap}><View><View style={styles.wordRow}><View style={styles.wordAxis} />{grid[0].map((_, colIndex) => <Text key={colIndex} style={styles.wordAxisText}>{String.fromCharCode(65 + colIndex)}</Text>)}</View>{grid.map((row, rowIndex) => <View key={rowIndex} style={styles.wordRow}><Text style={styles.wordAxisText}>{rowIndex + 1}</Text>{row.map((letter, colIndex) => { const key = `${rowIndex}:${colIndex}`; return <Pressable accessibilityRole="button" accessibilityLabel={`${String.fromCharCode(65 + colIndex)}${rowIndex + 1} ${letter}`} key={key} onPress={() => choose([rowIndex, colIndex])} style={[styles.wordCell, foundCells.has(key) && styles.wordCellFound, selectedCells.has(key) && styles.wordCellSelected]}><Text style={styles.wordLetter}>{letter}</Text></Pressable>; })}</View>)}</View></ScrollView> : <Text style={styles.bad}>{t('student.wordSearchUnavailable')}</Text>}{notice ? <Text style={styles.wordNotice}>{notice}</Text> : null}{start ? <Button secondary disabled={Boolean(result)} onPress={() => { setStart(null); setEnd(null); setNotice(''); }}>{t('student.wordSearchClear')}</Button> : null}</View>;
}
function QuestionAnswer({ question, index, answers, result, gradedCorrect, setAnswers, t }: { question: PracticeMaterial['questions'][number]; index: number; answers: Record<string, string>; result: PracticeResult | null; gradedCorrect?: boolean; setAnswers: Dispatch<SetStateAction<Record<string, string>>>; t: (key: string, params?: Record<string, string | number>) => string }) {
  const value = answers[String(index)] || '';
  if (question.exerciseType === 'word_search_vocab') return <WordSearchAnswer question={question} index={index} answers={answers} result={result} setAnswers={setAnswers} t={t} />;
  if (question.options.length && ['matching', 'vocabulary'].includes(question.exerciseType)) return <SelectField label={question.exerciseType === 'matching' ? t('student.matchAnswer') : t('student.vocabularyAnswer')} value={value} options={[{ value: '', label: t('student.chooseAnswer') }, ...question.options.map((option) => ({ value: option, label: option }))]} onChange={(next) => { if (!result) setAnswers((current) => ({ ...current, [String(index)]: next })); }} />;
  if (question.options.length) return <View style={styles.options}>{question.options.map((option) => { const display = question.exerciseType === 'true_false' ? t(option.toLocaleLowerCase() === 'true' ? 'student.true' : 'student.false') : option; const canonical = (answer: string) => question.exerciseType === 'true_false' ? canonicalTrueFalse(answer) : canonicalChoice(answer, question.options); const selected = Boolean(value) && canonical(value) === canonical(option); const expected = canonical(option) === canonical(question.answer); return <Pressable key={option} onPress={() => !result && setAnswers((current) => ({ ...current, [String(index)]: option }))} style={[styles.option, selected && !result && styles.optionSelected, result && selected && (gradedCorrect ? styles.optionCorrect : styles.optionIncorrect), result && expected && styles.optionCorrect]}><Text style={styles.optionText}>{display}</Text></Pressable>; })}</View>;
  return <Field editable={!result} value={value} onChangeText={(next) => setAnswers((current) => ({ ...current, [String(index)]: next }))} multiline={['short_answer', 'reading_comprehension', 'writing_prompt', 'problem_solving', 'show_your_work', 'data_analysis', 'process_explanation', 'hypothesis_and_conclusion', 'theory_questions'].includes(question.exerciseType)} placeholder={t('student.yourAnswer')} />;
}

export default function StudentPracticeScreen() {
  const { t } = useAppPreferences(); const params = useLocalSearchParams<{ assignmentId?: string; topicAssignmentId?: string; topicReturnTo?: string; missionId?: string; draftSessionId?: string; kind?: string; resourceId?: string; returnTo?: string; reviewSessionId?: string }>();
  const [historyScope, setHistoryScope] = useState('');
  const [progressScope, setProgressScope] = useState('');
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null); const [publicItems, setPublicItems] = useState<PublicResource[]>([]); const [section, setSection] = useState<'browse' | 'history' | 'progress'>('browse'); const [kind, setKind] = useState<Kind | '__all__'>(params.kind === 'worksheet' || params.kind === 'exam' || params.kind === 'video' ? params.kind : '__all__'); const [query, setQuery] = useState(''); const [subject, setSubject] = useState('__all__'); const [level, setLevel] = useState('__all__'); const [stage, setStage] = useState('__all__'); const [exerciseType, setExerciseType] = useState<string | null>(null); const [page, setPage] = useState(1); const [historyPage, setHistoryPage] = useState(1); const [progressPage, setProgressPage] = useState(1); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [active, setActive] = useState<PracticeMaterial | null>(null); const [activeVideo, setActiveVideo] = useState<PracticeItem | null>(null); const [draftSessionId, setDraftSessionId] = useState<string>(); const [answers, setAnswers] = useState<Record<string, string>>({}); const [result, setResult] = useState<PracticeResult | null>(null); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error'); const [reviewNote, setReviewNote] = useState(''); const [reviewTeachers, setReviewTeachers] = useState<ReviewableTeacher[]>([]); const [reviewTeacherId, setReviewTeacherId] = useState(''); const hydratedImages = useRef(new Set<string>()); const loggedVideos = useRef(new Set<string>()); const openedRouteRequest = useRef(''); const draftSave = useMemo(() => createStudentDraftSaveQueue<PracticeMaterial>(savePracticeDraft), []); const submitting = useRef(false);
  const load = async () => { setLoading(true); setError(''); const [student, resources] = await Promise.allSettled([getStudentWorkspace('practice'), getStudentPublicPracticeResources()]); if (student.status === 'fulfilled') setWorkspace(student.value); if (resources.status === 'fulfilled') setPublicItems(resources.value); if (student.status === 'rejected') setError(student.reason instanceof Error ? student.reason.message : t('student.loadFailed')); else if (resources.status === 'rejected') setError(resources.reason instanceof Error ? resources.reason.message : t('student.loadFailed')); setLoading(false); };
  useEffect(() => { if ((!params.assignmentId && !params.resourceId && !params.draftSessionId) || params.reviewSessionId) void load(); }, []);
  const libraryItems = useMemo(() => publicItems.filter((item): item is PracticeItem => ['worksheet', 'exam', 'video'].includes(item.kind)), [publicItems]);
  const kindLibraryItems = useMemo(() => libraryItems.filter((item) => kind === '__all__' || item.kind === kind), [libraryItems, kind]);
  const subjects = useMemo(() => [...new Set(libraryItems.map((item) => canonicalSubjectKey(item.subject)).filter(Boolean))].sort(), [libraryItems]);
  const subjectLibraryItems = useMemo(() => kindLibraryItems.filter((item) => subject === '__all__' || canonicalSubjectKey(item.subject) === subject), [kindLibraryItems, subject]);
  const levels = useMemo(() => [...new Set([...subjectLevelCatalog(subject), ...subjectLibraryItems.map((item) => item.level).filter(Boolean)])], [subject, subjectLibraryItems]);
  const stages = useMemo(() => [...new Set(kindLibraryItems.map((item) => canonicalLearnerStageKey(item.stage)).filter(Boolean))].sort(), [kindLibraryItems]);
  const exerciseTypes = useMemo(() => [...new Set(subjectLibraryItems.filter((item) => item.kind === 'worksheet').flatMap(resourceExerciseTypes))].sort(), [subjectLibraryItems]);
  const examLengths = useMemo(() => [...new Set(subjectLibraryItems.filter((item) => item.kind === 'exam').map((item) => text(item.raw.exam_length).trim().toLocaleLowerCase()).filter(Boolean))].sort(), [subjectLibraryItems]);
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return libraryItems.filter((item) => {
      return (kind === '__all__' || item.kind === kind)
        && (subject === '__all__' || canonicalSubjectKey(item.subject) === subject)
        && (level === '__all__' || item.level === level)
        && (stage === '__all__' || canonicalLearnerStageKey(item.stage) === stage)
        && (exerciseType === null || exerciseType === '__all__' || (item.kind === 'exam' ? text(item.raw.exam_length).trim().toLocaleLowerCase() === exerciseType : resourceExerciseTypes(item).includes(exerciseType)))
        && (!needle || [item.title, item.topic, item.subject, item.level, item.description].join(' ').toLocaleLowerCase().includes(needle));
    });
  }, [libraryItems, kind, query, subject, level, stage, exerciseType]);
  const pages = Math.max(1, Math.ceil(visible.length / PRACTICE_PAGE_SIZE));
  const shown = visible.slice((Math.min(page, pages) - 1) * PRACTICE_PAGE_SIZE, Math.min(page, pages) * PRACTICE_PAGE_SIZE);
  useEffect(() => {
    const groups = new Map<Kind, PracticeItem[]>();
    shown.filter((item) => item.kind !== 'video' && !item.imageUrl).forEach((item) => {
      const key = `${item.kind}:${item.id}`;
      if (hydratedImages.current.has(key)) return;
      hydratedImages.current.add(key);
      groups.set(item.kind, [...(groups.get(item.kind) ?? []), item]);
    });
    groups.forEach((items, resourceKind) => {
      void getPublicResourcePreviewImages(resourceKind, items.map((item) => item.id)).then((images) => {
        if (Object.keys(images).length) setPublicItems((current) => current.map((item) => images[item.id] ? { ...item, imageUrl: images[item.id] } : item));
      });
    });
  }, [shown]);
  const xp = (workspace?.sessions ?? []).reduce((sum, row) => sum + Number(row.xp_earned || 0), 0);
  const completed = (workspace?.sessions ?? []).filter((row) => row.status === 'completed');
  const bestStreak = completed.reduce((best, row) => Math.max(best, Number(row.best_streak || 0)), 0);
  const rank = practiceRank(xp);
  const assignmentById = new Map((workspace?.assignments ?? []).map((row) => [text(row.id), row]));
  const historyAssignment = new Map((workspace?.attempts ?? []).map((row) => [text(row.practice_session_id), assignmentById.get(text(row.assignment_id))]));
  const historyGroups = groupPracticeRows(completed, (row) => {
    const assignment = historyAssignment.get(text(row.id));
    return { teacherId: assignment?.teacher_id, teacherName: workspace?.teacherNames?.[text(assignment?.teacher_id)] };
  }, t);
  const progressRows = workspace?.practiceProgress ?? [];
  const progressGroups = groupPracticeRows(progressRows, (row) => {
    const assignment = assignmentById.get(text(row.assignment_id));
    const teacherId = text(row.teacher_id || assignment?.teacher_id);
    return { teacherId, teacherName: workspace?.teacherNames?.[teacherId] };
  }, t);
  const historyRows = historyGroups.length > 1 ? historyGroups.find((group) => group.key === historyScope)?.rows ?? historyGroups[0].rows : completed;
  const visibleProgressRows = progressGroups.length > 1 ? progressGroups.find((group) => group.key === progressScope)?.rows ?? progressGroups[0].rows : progressRows;
  const selectedProgressScope = progressGroups.length > 1 ? (progressGroups.some((group) => group.key === progressScope) ? progressScope : progressGroups[0].key) : '';
  const progressSessions = selectedProgressScope ? historyGroups.find((group) => group.key === selectedProgressScope)?.rows ?? [] : completed;
  const scoredProgressSessions = progressSessions.filter((row) => text(row.source_type) !== 'video');
  const progressAverage = scoredProgressSessions.length ? Math.round(scoredProgressSessions.reduce((sum, row) => sum + Number(row.score_pct || 0), 0) / scoredProgressSessions.length) : 0;
  const progressXp = visibleProgressRows.reduce((sum, row) => sum + Number(row.total_xp || 0), 0);
  const historyPages = Math.max(1, Math.ceil(historyRows.length / PRACTICE_PAGE_SIZE));
  const shownHistory = historyRows.slice((Math.min(historyPage, historyPages) - 1) * PRACTICE_PAGE_SIZE, Math.min(historyPage, historyPages) * PRACTICE_PAGE_SIZE);
  const progressPages = Math.max(1, Math.ceil(visibleProgressRows.length / PRACTICE_PAGE_SIZE));
  const shownProgress = visibleProgressRows.slice((Math.min(progressPage, progressPages) - 1) * PRACTICE_PAGE_SIZE, Math.min(progressPage, progressPages) * PRACTICE_PAGE_SIZE);
  const checkedHistory = useRef(new Set<string>());
  const visibleHistoryIds = (section === 'progress' ? scoredProgressSessions.slice(0, PRACTICE_PAGE_SIZE) : shownHistory).filter((item) => ['worksheet', 'exam'].includes(text(item.source_type))).map((item) => text(item.id));
  useEffect(() => {
    if (section !== 'history' && section !== 'progress') return;
    const pending = visibleHistoryIds.filter((id) => !checkedHistory.current.has(id));
    if (!pending.length) return;
    pending.forEach((id) => checkedHistory.current.add(id));
    void repairVisiblePracticeHistory(pending).then(async (repaired) => { if (repaired) setWorkspace(await getStudentWorkspace('practice', true)); }).catch(() => { pending.forEach((id) => checkedHistory.current.delete(id)); });
  }, [section, visibleHistoryIds.join(',')]);
  async function openItem(item: PracticeItem, detailLoaded = false): Promise<boolean> {
    setBusy(true); setMessage('');
    try {
      const snapshot = item.assignment ? await getStudentAssignmentContent(item.assignmentId || '') : null;
      const assignment = item.assignment ? { ...item.assignment, content_snapshot: snapshot } : null;
      const source = assignment ? { ...item, assignment, raw: (snapshot && typeof snapshot === 'object' ? snapshot : {}) as Record<string, unknown> } : detailLoaded ? item : await getPublicResourceDetail(item.kind, item.id);
      if (item.kind === 'video') {
        const url = videoUrl(source as PracticeItem);
        if (!url) { setMessage(t('student.videoUnavailable')); return false; }
        setActiveVideo(source as PracticeItem);
        return true;
      }
      const material = assignment ? materialFromAssignment(assignment) : materialFromPublic(source);
      if (!material?.questions.length) { setMessage(t('student.practiceUnavailable')); return false; }
      draftSave.reset(`${material.sourceType}:${material.assignmentId || material.sourceId}`);
      setActive(material); setAnswers({}); setResult(null); setDraftSessionId(undefined);
      return true;
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceUnavailable')); return false; } finally { setBusy(false); }
  }
  useEffect(() => {
    const id = params.assignmentId;
    if (!id || params.reviewSessionId || openedRouteRequest.current === `assignment:${id}`) return;
    if (params.kind === 'lesson_plan_topic') {
      router.replace({ pathname: '/student-lesson-topic' as never, params: { assignmentId: id } });
      return;
    }
    openedRouteRequest.current = `assignment:${id}`;
    let activeRequest = true;
    void (async () => {
      setBusy(true);
      setMessage('');
      try {
        const assignment = await getStudentAssignmentForPractice(id);
        if (!activeRequest) return;
        const assignmentKind = text(assignment.assignment_type);
        if (assignmentKind === 'lesson_plan_topic') {
          router.replace({ pathname: '/student-lesson-topic' as never, params: { assignmentId: id } });
          return;
        }
        if (!['worksheet', 'exam', 'video'].includes(assignmentKind)) throw new Error(t('student.practiceUnavailable'));
        setKind(assignmentKind as Kind);
        if (assignmentKind === 'video') {
          const snapshot = assignment.content_snapshot && typeof assignment.content_snapshot === 'object' ? assignment.content_snapshot as Record<string, unknown> : {};
          const video: PracticeItem = { id: `assignment-${id}`, assignmentId: id, assignment, kind: 'video', title: text(assignment.title), subject: text(assignment.subject_label || assignment.subject_key), topic: text(assignment.topic), stage: '', level: '', author: '', description: '', imageUrl: extractResourceImageUrl(snapshot), createdAt: text(assignment.assigned_at), raw: snapshot };
          if (!videoUrl(video)) throw new Error(t('student.videoUnavailable'));
          setActiveVideo(video);
          return;
        }
        let draftId: string | null = null;
        try { draftId = await getStudentAssignmentDraftSessionId(id, text(assignment.source_record_id)); }
        catch (reason) { console.warn('Student assignment draft lookup failed', reason); }
        if (!activeRequest) return;
        if (draftId) { await resumeDraft({ id: draftId }); return; }
        const material = materialFromAssignment(assignment);
        if (!material?.questions.length) throw new Error(t('student.practiceUnavailable'));
        draftSave.reset(`${material.sourceType}:${material.assignmentId || material.sourceId}`);
        setActive(material); setAnswers({}); setResult(null); setDraftSessionId(undefined);
      } catch (reason) { if (activeRequest) setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceUnavailable')); }
      finally { if (activeRequest) { setBusy(false); setLoading(false); } }
    })();
    return () => { activeRequest = false; };
  }, [params.assignmentId, params.reviewSessionId]);
  useEffect(() => {
    if (!params.reviewSessionId || openedRouteRequest.current === `review:${params.reviewSessionId}`) return;
    openedRouteRequest.current = `review:${params.reviewSessionId}`;
    void openHistory({ id: params.reviewSessionId });
  }, [params.reviewSessionId]);
  useEffect(() => {
    const id = params.resourceId;
    const resourceKind = params.kind;
    if (!id || !['worksheet', 'exam', 'video'].includes(resourceKind || '') || openedRouteRequest.current === `resource:${resourceKind}:${id}`) return;
    openedRouteRequest.current = `resource:${resourceKind}:${id}`;
    void (async () => {
      setLoading(true);
      try {
        const resource = await getPublicResourceDetail(resourceKind as Kind, id);
        setKind(resourceKind as Kind);
        await openItem(resource as PracticeItem, true);
      } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceUnavailable')); }
      finally { setLoading(false); }
    })();
  }, [params.resourceId, params.kind]);
  async function leaveActivity() {
    if (active && !result) await draftSave.flush().catch((reason) => console.warn('Practice draft save before leaving failed', reason));
    if (params.returnTo === 'student-home') {
      router.replace('/student-home');
      return;
    }
    if (params.returnTo === 'student-lesson-topic' && params.topicAssignmentId) {
      router.replace({ pathname: '/student-lesson-topic' as never, params: { assignmentId: params.topicAssignmentId, returnTo: params.topicReturnTo || '' } });
      return;
    }
    if (params.returnTo === 'student-assignments' && params.assignmentId) {
      router.replace({ pathname: '/student-assignments', params: { kind: params.kind || 'worksheet' } });
      return;
    }
    if (params.returnTo === 'student-study-plan') {
      router.replace({ pathname: '/student-study-plan', params: { missionId: params.missionId || '' } });
      return;
    }
    if (params.assignmentId || params.resourceId || params.draftSessionId || params.reviewSessionId) {
      router.replace('/student-practice');
      return;
    }
    setActive(null); setActiveVideo(null); setResult(null); setAnswers({}); setDraftSessionId(undefined); setMessage(''); void load();
  }
  async function submit() { if (!active || submitting.current) return; submitting.current = true; setBusy(true); setMessage(''); try { const pendingId = await draftSave.flush(); const saved = await savePractice(active, answers, pendingId || draftSessionId); setResult(saved); draftSave.reset(''); setDraftSessionId(undefined); setWorkspace(await getStudentWorkspace('practice', true)); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceSaveFailed')); } finally { submitting.current = false; setBusy(false); } }
  async function requestReview() { if (!active || !result) return; setBusy(true); try { await requestTeacherReview(active, result.sessionId, reviewNote, reviewTeacherId || undefined); setMessageTone('success'); setMessage(t('student.reviewRequested')); setWorkspace(await getStudentWorkspace('practice', true)); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.reviewFailed')); } finally { setBusy(false); } }
  async function openHistory(row: Record<string, unknown>) {
    setBusy(true); setMessage('');
    try {
      const session = await getStudentPracticeSession(text(row.id));
      if (text(session.source_type) === 'video') {
        const data = session.exercise_data && typeof session.exercise_data === 'object' ? session.exercise_data as Record<string, unknown> : {};
        setActiveVideo({ id: text(data.source_id || session.source_id || session.id), kind: 'video', title: text(session.title), subject: text(session.subject), topic: text(session.topic), stage: text(session.learner_stage), level: text(session.level), author: '', description: '', imageUrl: '', createdAt: text(session.created_at), raw: data, historyPlayback: true });
        return;
      }
      const review = await loadPracticeReview(session);
      setActive(review.material); setAnswers(review.answers); setResult(review.result);
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceUnavailable')); } finally { setBusy(false); }
  }
  async function resumeDraft(row: Record<string, unknown>) {
    setBusy(true); setMessage('');
    try {
      const session = await getStudentPracticeSession(text(row.id));
      const review = await loadPracticeReview(session);
      const data = session.exercise_data && typeof session.exercise_data === 'object' ? session.exercise_data as Record<string, unknown> : {};
      const embedded = data.draft_answers && typeof data.draft_answers === 'object' ? data.draft_answers as Record<string, unknown> : {};
      const restored = { ...Object.fromEntries(Object.entries(embedded).map(([key, value]) => [key, text(value)])), ...Object.fromEntries(Object.entries(review.answers).filter(([, value]) => Boolean(value))) };
      draftSave.reset(`${review.material.sourceType}:${review.material.assignmentId || review.material.sourceId}`, text(session.id), restored);
      setActive(review.material); setAnswers(restored); setResult(null); setDraftSessionId(text(session.id)); setMessageTone('success'); setMessage(t('student.practiceResumed'));
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceUnavailable')); } finally { setBusy(false); }
  }
  useEffect(() => {
    const id = params.draftSessionId;
    if (!id || openedRouteRequest.current === `draft:${id}`) return;
    openedRouteRequest.current = `draft:${id}`;
    void resumeDraft({ id }).finally(() => setLoading(false));
  }, [params.draftSessionId]);
  useEffect(() => { if (!activeVideo || activeVideo.historyPlayback) return; const logKey = activeVideo.assignmentId ? `assignment:${activeVideo.assignmentId}` : `video:${activeVideo.id}`; if (loggedVideos.current.has(logKey)) return; loggedVideos.current.add(logKey); const assignment = activeVideo.assignment; void recordVideoWatch({ id: text(assignment?.source_record_id || activeVideo.id), assignmentId: activeVideo.assignmentId, teacherId: text(assignment?.teacher_id), title: activeVideo.title, subject: activeVideo.subject, topic: activeVideo.topic, stage: activeVideo.stage, level: activeVideo.level, url: videoUrl(activeVideo) }).then(() => getStudentWorkspace('practice', true)).then(setWorkspace).catch((reason) => { loggedVideos.current.delete(logKey); setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.practiceSaveFailed')); }); }, [activeVideo]);
  useEffect(() => {
    if (!active || result || busy || submitting.current || !Object.values(answers).some(Boolean)) return;
    const key = `${active.sourceType}:${active.assignmentId || active.sourceId}`;
    const timeout = setTimeout(() => {
      if (submitting.current) return;
      const pending = draftSave.enqueue(key, active, answers);
      if (pending) void pending.then((id) => { if (draftSave.key() === key) { setDraftSessionId(id); setMessageTone('success'); setMessage(t('student.practiceAutosaved')); } }).catch(() => { if (draftSave.key() === key) setMessageTone('error'); setMessage(t('student.practiceAutosaveFailed')); });
    }, 900);
    return () => clearTimeout(timeout);
  }, [active, answers, result, busy, t]);
  useEffect(() => { if (!active || !result || active.assignmentId) { setReviewTeachers([]); setReviewTeacherId(''); return; } void getReviewableTeachers(active.subject).then((rows) => { setReviewTeachers(rows); setReviewTeacherId((current) => rows.some((row) => row.teacherId === current) ? current : rows[0]?.teacherId || ''); }).catch(() => { setReviewTeachers([]); setReviewTeacherId(''); }); }, [active?.subject, active?.assignmentId, result?.sessionId]);
  const backLabel = t(params.returnTo === 'student-assignments' ? 'student.backToAssignments' : params.returnTo === 'student-study-plan' ? 'student.backToSmartPlan' : params.returnTo === 'student-lesson-topic' ? 'student.lessonTopic.backTopic' : params.returnTo === 'student-home' ? 'student.lessonTopic.backHome' : 'student.backToPractice');
  const backLink = <BackLink label={backLabel} onPress={() => void leaveActivity()} />;
  if (activeVideo) { const url = videoUrl(activeVideo); const embed = youtubeEmbedUrl(url); return <AppShell title={activeVideo.title} eyebrow={t('student.videoSession')}>{backLink}<Panel style={styles.videoSession}><Text style={styles.sessionMeta}>{[activeVideo.subject, activeVideo.topic, activeVideo.level].filter(Boolean).join(' · ')}</Text><Text style={styles.sessionTitle}>{activeVideo.title}</Text>{Platform.OS === 'web' && embed ? createElement('iframe', { src: embed, title: activeVideo.title, allow: 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture', allowFullScreen: true, style: { width: '100%', aspectRatio: '16 / 9', border: 0, borderRadius: 16, marginTop: 14 } }) : activeVideo.imageUrl ? <Image source={activeVideo.imageUrl} style={styles.videoPreview} contentFit="cover" /> : null}{activeVideo.description ? <Text style={styles.videoDescription}>{activeVideo.description}</Text> : null}<Button onPress={() => void Linking.openURL(url)}>▶ {t('student.openYouTube')}</Button><Text style={styles.videoLogged}>✓ {t('student.videoProgressSaved')}</Text><ActionFeedback message={message} tone={messageTone} /></Panel></AppShell>; }
  if (active) {
    const preview = gradePractice(active, answers); const review = (workspace?.reviews ?? []).find((row) => text(row.practice_session_id) === result?.sessionId); const progress = practiceAnswerProgress(preview, answers);
    return <AppShell title={active.title} eyebrow={t('student.practiceSession')}>
      {backLink}
      <Panel style={styles.sessionHero}><Text style={styles.sessionMeta}>{[active.subject, active.topic, active.level].filter(Boolean).join(' · ')}</Text><Text style={styles.sessionTitle}>{active.title}</Text><Text style={styles.sessionBody}>{t('student.questionProgress', { answered: progress.answered, total: progress.total })}</Text><View style={styles.sessionTrack}><View style={[styles.sessionFill, { width: `${progress.total ? Math.round(progress.answered / progress.total * 100) : 0}%` }]} /></View></Panel>
      {active.questions.map((question, index) => { const graded = preview.rows[index]; const firstInSection = question.questionIndex === 0; return <View key={`${question.exerciseIndex}-${question.questionIndex}`}>
        {firstInSection && question.sectionTitle && question.sectionTitle !== active.title ? <View style={styles.sectionDivider}><Text style={styles.exerciseSectionTitle}>{question.sectionTitle}</Text><Text style={styles.exerciseSectionType}>{t(`student.exercise.${question.exerciseType}`)}</Text></View> : null}
        {firstInSection && question.visualSupportUrl ? <Image source={question.visualSupportUrl} style={styles.exerciseVisual} contentFit="contain" transition={180} /> : null}
        <Panel style={styles.question}><Text style={styles.questionNumber}>{t('student.questionNumber', { number: index + 1 })} · {t(`student.exercise.${question.exerciseType}`)}</Text>{question.sourceText && firstInSection ? <Disclosure title={t('student.readingPassage')} summary={t('student.openPassage')} defaultOpen style={styles.readingDisclosure}><Text style={styles.passage}>{question.sourceText}</Text></Disclosure> : null}{question.vocabularyBank?.length && firstInSection && question.exerciseType !== 'word_search_vocab' ? <Disclosure title={t('student.vocabularyBank')} defaultOpen style={styles.vocabulary}><Text style={styles.wordList}>{question.vocabularyBank.join(' · ')}</Text></Disclosure> : null}{question.instructions && firstInSection ? <Text style={styles.instructions}>{question.instructions}</Text> : null}{question.exerciseType !== 'word_search_vocab' ? <Text style={styles.prompt}>{question.prompt}</Text> : null}<QuestionAnswer question={question} index={index} answers={answers} result={result} gradedCorrect={graded?.isCorrect} setAnswers={setAnswers} t={t} />{result ? question.exerciseType === 'word_search_vocab' ? <Text style={[styles.feedback, graded?.isCorrect ? styles.good : styles.warning]}>{graded?.isCorrect ? `✓ ${t('student.wordSearchCompleted')}` : t('student.wordSearchResult', { found: graded?.correctCount ?? 0, total: graded?.totalCount ?? 0 })}</Text> : <Text style={[styles.feedback, graded?.isCorrect ? styles.good : styles.bad]}>{graded?.writingFeedback ? t(graded.writingFeedback.isCorrect ? 'student.writing_feedback_pass' : 'student.writing_feedback_revise') : graded?.isCorrect ? `✓ ${t('student.correct')}` : `✕ ${t('student.answerWas', { answer: question.answer || '—' })}`}</Text> : null}{result && graded?.writingFeedback ? <View style={styles.writingFeedback}><Text style={styles.feedback}>{t(graded.writingFeedback.isCorrect ? 'student.writing_feedback_pass' : 'student.writing_feedback_revise')} · {Math.round(graded.writingFeedback.score * 100)}%</Text>{graded.writingFeedback.feedbackKeys.map((key) => <Text key={key} style={styles.meta}>{t(`student.${key}`)}</Text>)}<Text style={styles.meta}>{t('student.writing_feedback_model_points')}: {question.answer || '—'}</Text></View> : null}</Panel>
      </View>; })}
      {result ? <Panel style={styles.result}><Text style={styles.resultEmoji}>{result.score >= 80 ? '🌟' : result.score >= 60 ? '👍' : '💪'}</Text><Text style={[styles.resultScore, result.score < 80 && { color: result.score >= 60 ? colors.orange : colors.danger }]}>{result.score}%</Text><Text style={styles.resultTitle}>{result.score >= 80 ? t('student.excellentScore') : result.score >= 60 ? t('student.goodScore') : t('student.keepPracticing')}</Text><Text style={styles.resultBody}>{t('student.resultSummary', { correct: result.correct, total: result.total, xp: result.xp })} · 🔥 {result.bestStreak}</Text>{active.assignmentId || reviewTeachers.length || review ? <Disclosure title={t('student.teacherReview')} summary={review ? t(`student.reviewStatus.${text(review.status)}`) : t('student.teacherReviewHelp')}>{!active.assignmentId && reviewTeachers.length ? <SelectField label={t('student.teacher')} value={reviewTeacherId} options={reviewTeachers.map((row) => ({ value: row.teacherId, label: row.name, detail: row.subjects.join(' · ') }))} onChange={setReviewTeacherId} /> : null}<Field value={reviewNote} onChangeText={setReviewNote} placeholder={t('student.reviewNote')} multiline /> <Button disabled={busy || Boolean(review) || (!active.assignmentId && !reviewTeacherId)} onPress={() => void requestReview()}>{review ? t(`student.reviewStatus.${text(review.status)}`) : t('student.requestReview')}</Button>{review?.teacher_feedback ? <Text style={styles.teacherFeedback}>{text(review.teacher_feedback)}</Text> : null}</Disclosure> : !active.assignmentId ? <Disclosure title={t('student.teacherReview')} summary={t('student.teacherReviewHelp')}><Text style={styles.teacherFeedback}>{t('student.findTeacherBody')}</Text><Button secondary onPress={() => router.push('/student-find-teacher')}>{t('student.findTeacher')}</Button></Disclosure> : null}<View style={styles.resultActions}><Button secondary onPress={() => { draftSave.reset(`${active.sourceType}:${active.assignmentId || active.sourceId}`); setAnswers({}); setResult(null); setDraftSessionId(undefined); setMessage(''); }}>↻ {t('student.tryAgain')}</Button><Button onPress={() => void leaveActivity()}>✓ {t('student.finish')}</Button></View></Panel> : <Button disabled={busy || !progress.ready} onPress={() => void submit()}>{busy ? t('common.saving') : t('student.submitAnswers')}</Button>}<ActionFeedback message={message} tone={messageTone} />
    </AppShell>;
  }
  if (params.assignmentId || params.resourceId || params.draftSessionId || params.reviewSessionId) {
    return <AppShell title={t('student.practice')} eyebrow={t('student.learningSpace')}>
      {backLink}
      {loading || busy ? <LoadingState /> : <EmptyState title={t('student.practiceUnavailable')} body={message || t('student.practiceUnavailable')} />}
    </AppShell>;
  }
  const exerciseIcons: Record<string, string> = { multiple_choice: '🔘', true_false: '✅', fill_in_blank: '✏️', short_answer: '📝', matching: '🔗', reading_comprehension: '📖', error_correction: '🔍', word_search_vocab: '🔠', problem_solving: '🧮', equation_solving: '➗', data_analysis: '📊', classification: '🔬', symbol_identification: '🎼', rhythm_counting: '🥁' };
  return <AppShell title={t('student.practice')} eyebrow={t('student.learningSpace')}>
    <TabRail accessibilityLabel={t('student.practice')} value={section} onChange={setSection} items={[{ value: 'browse', label: t('student.browsePractice') }, { value: 'history', label: t('student.history') }, { value: 'progress', label: t('student.myProgress') }]} />
    <View style={styles.xp}><Text style={styles.rank}>{rank.emoji} {t(`student.rank.${rank.key}`)}</Text><View style={styles.rankProgress}><View style={styles.track}><View style={[styles.fill, { width: `${rank.pct}%` }]} /></View><Text style={styles.rankDetail}>{rank.span ? `${rank.into}/${rank.span} XP → ${t(`student.rank.${rank.next?.key}`)}` : 'MAX'}</Text></View><View style={styles.stat}><Text style={styles.xpText}>{xp}</Text><Text style={styles.statLabel}>XP</Text></View><View style={styles.stat}><Text style={styles.streak}>🔥 {bestStreak}</Text><Text style={styles.statLabel}>{t('student.bestStreak')}</Text></View></View>
    {section === 'browse' ? <ActionFeedback message={message} tone={messageTone} /> : null}
    {section === 'progress' ? <>{progressGroups.length > 1 ? <TabRail accessibilityLabel={t('student.myProgress')} value={progressGroups.some((group) => group.key === progressScope) ? progressScope : progressGroups[0].key} onChange={(value) => { setProgressScope(value); setProgressPage(1); }} items={progressGroups.map((group) => ({ value: group.key, label: group.label }))} /> : null}<View style={styles.metrics}><Panel style={styles.metric}><Text style={styles.metricValue}>{progressSessions.length}</Text><Text style={styles.metricLabel}>{t('student.sessionsCompleted')}</Text></Panel><Panel style={styles.metric}><Text style={styles.metricValue}>{progressAverage}%</Text><Text style={styles.metricLabel}>{t('student.averageScore')}</Text></Panel><Panel style={styles.metric}><Text style={styles.metricValue}>{progressXp}</Text><Text style={styles.metricLabel}>XP</Text></Panel></View>{!progressRows.length ? <EmptyState title={t('student.noProgress')} body={t('student.noProgressBody')} /> : <><View style={styles.stack}>{shownProgress.map((row) => { const video = text(row.source_type) === 'video' || text(row.exercise_type) === 'video_watch'; return <Disclosure key={text(row.id)} title={[text(row.subject) ? canonicalSubjectLabel(row.subject, t) : '', row.topic].filter(Boolean).join(' · ')} summary={video ? `${t('student.watched')} · ${text(row.total_attempted)} ${t('student.views')}` : `${text(row.accuracy_pct)}% · ${text(row.total_attempted)} ${t('student.attempted')}`}><Text style={styles.progressDetail}>{video ? `${t('student.videoProgress')} · +${Number(row.total_xp || 0)} XP` : `${t('student.progressDetail', { correct: Number(row.total_correct || 0), total: Number(row.total_attempted || 0), xp: Number(row.total_xp || 0) })} · 🔥 ${Number(row.best_streak || 0)}`}</Text></Disclosure>; })}</View><Pagination page={Math.min(progressPage, progressPages)} totalPages={progressPages} totalItems={visibleProgressRows.length} onPageChange={setProgressPage} /></>}</> : section === 'history' ? <>
      {historyGroups.length > 1 ? <TabRail accessibilityLabel={t('student.history')} value={historyGroups.some((group) => group.key === historyScope) ? historyScope : historyGroups[0].key} onChange={(value) => { setHistoryScope(value); setHistoryPage(1); }} items={historyGroups.map((group) => ({ value: group.key, label: group.label }))} /> : null}
      {!completed.length ? <EmptyState title={t('student.noHistory')} body={t('student.noHistoryBody')} /> : <>
        <View style={styles.stack}>{shownHistory.map((row) => {
          const video = text(row.source_type) === 'video';
          const score = Number(row.score_pct || 0);
          const details = [text(row.subject) ? canonicalSubjectLabel(row.subject, t) : '', row.topic, row.created_at ? new Date(String(row.created_at)).toLocaleDateString() : ''].filter(Boolean).join(' · ');
          return <Pressable key={text(row.id)} accessibilityRole="button" accessibilityLabel={`${text(row.title || t('student.practice'))}, ${video ? t('student.watchAgain') : t('student.reviewAnswers')}`} disabled={busy} onPress={() => void openHistory(row)} style={({ pressed }) => [styles.historyCard, (pressed || busy) && styles.historyCardPressed]}>
            <View style={styles.historyCopy}>
              <Text style={styles.historyKind}>{video ? `🎬 ${t('student.videos')}` : `🧩 ${text(row.source_type)}`}</Text>
              <Text numberOfLines={1} style={styles.historyTitle}>{text(row.title || t('student.practice'))}</Text>
              <Text numberOfLines={1} style={styles.historyMeta}>{details}</Text>
            </View>
            <View style={styles.historySummary}>
              <Text style={[styles.historyScore, video ? styles.videoWatched : score >= 80 ? styles.good : score >= 60 ? styles.warning : styles.bad]}>{video ? t('student.watched') : `${score}%`}</Text>
              <Text numberOfLines={1} style={styles.historyCompactStats}>{video ? `${Math.max(1, Number(row.total_questions || 0))} ${t('student.views')}` : `✓ ${Number(row.correct_count || 0)}/${Number(row.total_questions || 0)} · 🔥 ${Number(row.best_streak || 0)}`} · +{Number(row.xp_earned || 0)} XP</Text>
            </View>
            <Text style={styles.historyChevron}>›</Text>
          </Pressable>;
        })}</View>
        <Pagination page={Math.min(historyPage, historyPages)} totalPages={historyPages} totalItems={historyRows.length} onPageChange={setHistoryPage} />
      </>}
    </> : <>
      <TabRail accessibilityLabel={t('student.resourceType')} value={kind} onChange={(value) => { setKind(value as Kind); setStage('__all__'); setLevel('__all__'); setExerciseType(null); setPage(1); }} items={[{ value: 'worksheet', label: `📋 ${t('student.worksheets')}` }, { value: 'video', label: `🎬 ${t('student.videos')}` }, { value: 'exam', label: `📄 ${t('student.exams')}` }]} />
      <ResourceFilters query={query} onQueryChange={(value) => { setQuery(value); setPage(1); }} count={loading ? undefined : visible.length} searchLabel={t('common.search')} searchPlaceholder={t('student.searchPractice')} facets={[
        { key: 'subject', label: t('resources.subject'), value: subject, allValue: '__all__', allLabel: t('resources.allSubjects'), options: subjects.map((value) => ({ value, label: canonicalSubjectLabel(value, t) })), onChange: (value) => { setSubject(value); setLevel('__all__'); setExerciseType(null); setPage(1); } },
        { key: 'stage', label: t('resources.stage'), value: stage, allValue: '__all__', allLabel: t('resources.allStages'), options: stages.map((value) => ({ value, label: learnerStageLabel(value, t) })), onChange: (value) => { setStage(value); setPage(1); } },
        { key: 'level', label: t('resources.level'), value: level, allValue: '__all__', allLabel: t('resources.allLevels'), options: levels.map((value) => ({ value, label: ACADEMIC_LEVELS.includes(value) ? t(`smart.option.${value.replace('_band', '')}`) : value })), onChange: (value) => { setLevel(value); setPage(1); } },
        ...(kind === 'video' || kind === '__all__' ? [] : [{ key: 'exercise', label: kind === 'exam' ? t('smart.examLength') : t('student.exerciseType'), value: exerciseType ?? '__all__', allValue: '__all__', allLabel: kind === 'exam' ? t('student.allExamLengths') : t('student.allExerciseTypes'), options: kind === 'exam' ? examLengths.map((value) => ({ value, label: t(`smart.option.${value}`) === `smart.option.${value}` ? value.replaceAll('_', ' ') : t(`smart.option.${value}`) })) : exerciseTypes.map((value) => { const translated = t(`student.exercise.${value}`); return { value, label: `${exerciseIcons[value] || '🧩'} ${translated === `student.exercise.${value}` ? value.replaceAll('_', ' ') : translated}` }; }), onChange: (value: string) => { setExerciseType(value === '__all__' ? null : value); setPage(1); } }]),
      ]} />
      {loading ? <LoadingState /> : error ? <EmptyState title={t('student.loadFailed')} body={error} /> : !shown.length ? <EmptyState title={t('student.noPractice')} body={t('student.noPracticeBody')} /> : <View style={styles.grid}>{shown.map((item) => <ResourceCard key={`${item.kind}-${item.id}`} item={item} busy={busy} onPress={() => void openItem(item)} t={t} />)}</View>}
      {!loading && !error ? <Pagination page={Math.min(page, pages)} totalPages={pages} totalItems={visible.length} onPageChange={setPage} /> : null}
    </>}
  </AppShell>;
}

const styles = StyleSheet.create({
  message: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 10, padding: 11, marginVertical: 12, fontSize: 11, fontWeight: '800' },
  xp: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 12, padding: 14, marginVertical: 15, borderRadius: 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  rank: { color: colors.ink, fontSize: 14, fontWeight: '900' }, rankProgress: { flex: 1, minWidth: 190, gap: 5 }, rankDetail: { color: colors.muted, fontSize: 9, fontWeight: '700' },
  track: { width: '100%', height: 7, backgroundColor: colors.line, borderRadius: 99, overflow: 'hidden' }, fill: { height: '100%', backgroundColor: colors.violet },
  stat: { minWidth: 72, alignItems: 'center', paddingLeft: 10, borderLeftWidth: 1, borderLeftColor: colors.line }, xpText: { color: colors.violet, fontSize: 18, fontWeight: '900' }, streak: { color: colors.orange, fontSize: 18, fontWeight: '900' }, statLabel: { color: colors.muted, fontSize: 8, fontWeight: '800', textTransform: 'uppercase' },
  kindTabs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingBottom: 15 }, kindTab: { borderWidth: 1, borderColor: colors.line, borderRadius: 999, backgroundColor: colors.surface, paddingHorizontal: 14, paddingVertical: 9 }, kindActive: { backgroundColor: colors.primary, borderColor: colors.primary }, kindText: { color: colors.muted, fontSize: 11, fontWeight: '800' }, kindTextActive: { color: colors.inverse },
  draftTray: { marginTop: 6, marginBottom: 24 }, draftCard: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 12 }, recommendations: { marginTop: 6, marginBottom: 26 }, libraryHeader: { marginTop: 4, marginBottom: 13 }, sectionTitle: { color: colors.ink, fontSize: 20, lineHeight: 26, fontWeight: '900' }, sectionBody: { color: colors.muted, fontSize: 11, lineHeight: 18, marginTop: 3 },
  filters: { gap: 10 }, exerciseCategories: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 14, marginBottom: 6 }, categoryPrompt: { width: '100%', color: colors.muted, fontSize: 10, fontWeight: '800', marginBottom: 2 }, exerciseCategory: { flexGrow: 1, flexBasis: 240, minHeight: 64, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 15, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, paddingHorizontal: 14, paddingVertical: 12 }, exerciseCategoryActive: { borderColor: colors.violet, backgroundColor: colors.violetSoft }, categoryIcon: { fontSize: 18 }, exerciseCategoryText: { flex: 1, color: colors.ink, fontSize: 11, fontWeight: '900' }, exerciseCategoryTextActive: { color: colors.violet }, categoryArrow: { color: colors.muted, fontSize: 20, fontWeight: '900' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 15 }, resourceSlot: { flexGrow: 1, flexBasis: 320, minWidth: 280, maxWidth: 530 }, meta: { color: colors.muted, fontSize: 9, marginTop: 6, textTransform: 'capitalize' },
  sessionHero: { marginVertical: 14, backgroundColor: colors.primarySoft }, sessionMeta: { color: colors.primary, fontSize: 9, fontWeight: '900', textTransform: 'capitalize' }, sessionTitle: { color: colors.ink, fontSize: 24, lineHeight: 30, fontWeight: '900', marginTop: 6 }, sessionBody: { color: colors.muted, fontSize: 11, marginTop: 6 }, sessionTrack: { height: 8, marginTop: 12, backgroundColor: colors.line, borderRadius: 999, overflow: 'hidden' }, sessionFill: { height: '100%', borderRadius: 999, backgroundColor: colors.violet }, sectionDivider: { marginTop: 12, marginBottom: 8, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 }, exerciseSectionTitle: { color: colors.ink, fontSize: 19, lineHeight: 25, fontWeight: '900' }, exerciseSectionType: { color: colors.violet, backgroundColor: colors.violetSoft, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, fontSize: 9, fontWeight: '900', textTransform: 'uppercase' }, exerciseVisual: { width: '100%', height: 280, marginBottom: 12, borderRadius: 18, backgroundColor: colors.surfaceSoft }, question: { marginBottom: 11, gap: 10 }, questionNumber: { color: colors.primary, fontSize: 9, fontWeight: '900', textTransform: 'uppercase' }, instructions: { color: colors.muted, fontSize: 10, fontStyle: 'italic' }, prompt: { color: colors.ink, fontSize: 16, lineHeight: 24, fontWeight: '800' }, passage: { color: colors.ink, fontSize: 13, lineHeight: 21 }, readingDisclosure: { backgroundColor: colors.violetSoft, borderColor: colors.violet }, vocabulary: { borderRadius: 11, backgroundColor: colors.primarySoft, borderColor: colors.primary }, vocabularyTitle: { color: colors.violet, fontSize: 9, fontWeight: '900', textTransform: 'uppercase', marginBottom: 5 },
  videoSession: { marginTop: 14, gap: 12 }, videoPreview: { width: '100%', aspectRatio: 16 / 9, marginTop: 4, borderRadius: 16, backgroundColor: colors.surfaceSoft }, videoDescription: { color: colors.muted, fontSize: 12, lineHeight: 20 }, videoLogged: { color: colors.success, fontSize: 10, fontWeight: '900', textAlign: 'center' },
  wordSearch: { gap: 10 }, wordSearchHelp: { color: colors.muted, fontSize: 11, lineHeight: 18 }, wordProgress: { height: 9, borderRadius: 999, backgroundColor: colors.line, overflow: 'hidden' }, wordProgressFill: { height: '100%', borderRadius: 999, backgroundColor: colors.success }, wordProgressLabel: { color: colors.muted, fontSize: 10, fontWeight: '800' }, wordChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, wordChip: { color: colors.ink, backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.line, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5, fontSize: 9, fontWeight: '900' }, wordChipFound: { color: colors.success, backgroundColor: colors.successSoft, borderColor: colors.success }, wordBoardWrap: { flexGrow: 1, justifyContent: 'center', paddingVertical: 5 }, wordRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4 }, wordAxis: { width: 28, height: 24 }, wordAxisText: { width: 28, color: colors.muted, textAlign: 'center', fontSize: 9, fontWeight: '900' }, wordCell: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.line, borderRadius: 8, backgroundColor: colors.surface }, wordCellFound: { borderWidth: 2, borderColor: colors.success, backgroundColor: colors.successSoft }, wordCellSelected: { borderWidth: 2, borderColor: colors.primary, backgroundColor: colors.primarySoft }, wordLetter: { color: colors.ink, fontSize: 12, fontWeight: '900' }, wordList: { color: colors.ink, fontSize: 11, lineHeight: 18, fontWeight: '700' }, wordNotice: { color: colors.primary, fontSize: 10, lineHeight: 17, fontWeight: '800' },
  options: { gap: 7 }, option: { borderWidth: 1, borderColor: colors.line, borderRadius: 11, padding: 12, backgroundColor: colors.surface }, optionSelected: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, optionCorrect: { borderColor: colors.success, backgroundColor: colors.successSoft }, optionIncorrect: { borderColor: colors.danger, backgroundColor: colors.dangerSoft }, optionText: { color: colors.ink, fontSize: 13, fontWeight: '700' }, feedback: { fontSize: 11, fontWeight: '900' }, writingFeedback: { gap: 5, padding: 9, borderRadius: 9, backgroundColor: colors.surface }, good: { color: colors.success }, warning: { color: colors.orange }, bad: { color: colors.danger },
  result: { marginTop: 14, gap: 10, alignItems: 'stretch' }, resultEmoji: { fontSize: 38, textAlign: 'center' }, resultScore: { color: colors.success, fontSize: 38, fontWeight: '900', textAlign: 'center' }, resultTitle: { color: colors.ink, fontSize: 18, fontWeight: '900', textAlign: 'center' }, resultBody: { color: colors.muted, fontSize: 12, textAlign: 'center', marginBottom: 8 }, resultActions: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 10, marginTop: 4 }, teacherFeedback: { color: colors.ink, fontSize: 12, lineHeight: 19, marginTop: 9 },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginVertical: 15 }, metric: { flex: 1, minWidth: 180 }, metricValue: { color: colors.ink, fontSize: 27, fontWeight: '900' }, metricLabel: { color: colors.muted, fontSize: 10, marginTop: 3 }, stack: { gap: 10, marginTop: 12 }, progressDetail: { color: colors.muted, fontSize: 12, lineHeight: 19 },
  historyCard: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 76, paddingHorizontal: 16, paddingVertical: 12, borderWidth: 1, borderColor: colors.line, borderRadius: 15, backgroundColor: colors.surface }, historyCardPressed: { opacity: 0.65 }, historyCopy: { flex: 1, minWidth: 0 }, historyKind: { color: colors.violet, fontSize: 8, fontWeight: '900', textTransform: 'uppercase' }, historyTitle: { color: colors.ink, fontSize: 14, fontWeight: '900', marginTop: 3 }, historyMeta: { color: colors.muted, fontSize: 10, marginTop: 3 }, historySummary: { alignItems: 'flex-end', maxWidth: '42%', gap: 4 }, historyScore: { fontSize: 17, fontWeight: '900' }, videoWatched: { color: colors.primary, fontSize: 11 }, historyCompactStats: { color: colors.muted, fontSize: 9, fontWeight: '700' }, historyChevron: { color: colors.muted, fontSize: 24, fontWeight: '600' },
});
