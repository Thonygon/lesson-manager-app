import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { ActionFeedback, Field, OrderedMultiSelectField, Panel, SelectField, TabRail } from '@/components/ui';
import { LessonPlanView } from '@/components/lesson-plan-view';
import { WorksheetView } from '@/components/worksheet-view';
import { ExamView } from '@/components/exam-view';
import { publicExploreCopy } from '@/lib/public-explore-copy';
import { publicCopy } from '@/lib/public-copy';
import { canonicalSubjectLabel } from '@/lib/subjects';
import { learnerStageLabel } from '@/lib/learner-stages';
import { lessonPurposeLabel } from '@/lib/lesson-purpose';
import { useAppPreferences } from '@/providers/app-preferences';
import { GenerationReuseError, generateMaterial, saveGeneratedMaterial, setGeneratedMaterialVisibility, type SmartToolInput, type SmartToolKind } from '@/services/smart-tools';
import { findGenerationMatches, type GenerationMatch } from '@/server/generation-reuse';
import { supabase } from '@/lib/supabase';
import { colors } from '@/theme';
import { previewLabel } from '@/lib/generated-resource-labels';
import { examLengthRule } from '@/lib/exam-generation-rules';

type Kind = SmartToolKind;
const kinds: { value: Kind; icon: string }[] = [{ value: 'plan', icon: '📝' }, { value: 'worksheet', icon: '📋' }, { value: 'exam', icon: '🧪' }, { value: 'program', icon: '📚' }];
const SUBJECTS = ['english', 'spanish', 'mathematics', 'science', 'music', 'study_skills'];
const STAGES = ['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage'];
const LANGUAGE_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const ACADEMIC_LEVELS = ['beginner_band', 'intermediate_band', 'advanced_band'];
const WORKSHEET_TYPES = ['fill_in_the_blanks', 'multiple_choice', 'matching', 'short_answer', 'true_false', 'reading_comprehension', 'error_correction', 'word_search_vocab'];
const EXAM_TYPES: Record<string, string[]> = {
  english: ['multiple_choice', 'reading_comprehension', 'writing_prompt', 'error_correction'],
  spanish: ['multiple_choice', 'reading_comprehension', 'writing_prompt', 'error_correction'],
  mathematics: ['problem_solving', 'equation_solving', 'show_your_work', 'word_problems'],
  science: ['data_analysis', 'classification', 'process_explanation', 'diagram_questions'],
  music: ['theory_questions', 'symbol_identification', 'rhythm_counting', 'terminology'],
  study_skills: ['multiple_choice', 'short_answer', 'matching', 'true_false'],
};
function readable(value: string) { return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function DocumentView({ value, language }: { value: unknown; language: string }) {
  if (value == null || value === '') return null;
  if (typeof value === 'string' && (/^data:image\//i.test(value) || value.length > 4000)) return null;
  if (Array.isArray(value)) return <View style={styles.documentGroup}>{value.map((item, index) => <DocumentView key={index} value={item} language={language} />)}</View>;
  if (typeof value === 'object') return <View style={styles.documentGroup}>{Object.entries(value as Record<string, unknown>).filter(([key]) => !/prompt|base64|image_data/i.test(key)).map(([key, child]) => <View key={key} style={styles.documentLine}><Text style={styles.documentLabel}>{previewLabel(key, language)}</Text><DocumentView value={child} language={language} /></View>)}</View>;
  return <Text style={styles.documentText}>{String(value)}</Text>;
}
export function PublicSmartTool({ initial, onClose }: { initial: Kind; onClose: () => void }) {
  const { language, t } = useAppPreferences(); const copy = publicExploreCopy(language); const marketing = publicCopy(language); const narrow = useWindowDimensions().width < 850;
  const toolLabels: Record<Kind, string> = { plan: marketing.toolLesson, worksheet: marketing.toolWorksheet, exam: marketing.toolExam, program: marketing.toolProgram };
  const [kind, setKind] = useState<Kind>(initial); const [subject, setSubject] = useState('english'); const [stage, setStage] = useState('upper_secondary'); const [level, setLevel] = useState('A2'); const [topic, setTopic] = useState(''); const [worksheetType, setWorksheetType] = useState('multiple_choice'); const [examLength, setExamLength] = useState('short'); const [lessonPurpose, setLessonPurpose] = useState('introduce_concept'); const [notes, setNotes] = useState(''); const [exerciseTypes, setExerciseTypes] = useState<string[]>(['multiple_choice', 'reading_comprehension']); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [feedback, setFeedback] = useState(''); const [feedbackContext, setFeedbackContext] = useState<'generate' | 'preview'>('generate'); const [document, setDocument] = useState<Record<string, unknown> | null>(null); const [reuseMatches, setReuseMatches] = useState<GenerationMatch[]>([]); const [pendingReuse, setPendingReuse] = useState<Record<string, unknown> | null>(null); const [savedResourceId, setSavedResourceId] = useState<string | null>(null); const [pendingSaveInput, setPendingSaveInput] = useState<SmartToolInput | null>(null); const [publicVisibility, setPublicVisibility] = useState(false);
  const [confirmReuse, setConfirmReuse] = useState(false);
  const languageSubject = subject === 'english' || subject === 'spanish';
  const levels = languageSubject ? LANGUAGE_LEVELS : ACADEMIC_LEVELS;
  const availableExamTypes = [...new Set([...(EXAM_TYPES[subject] || EXAM_TYPES.study_skills), ...exerciseTypes])];
  const examRule = examLengthRule(examLength);
  const examTypeError = kind === 'exam' ? !exerciseTypes.length ? t('smart.examSelectTypes') : exerciseTypes.length > examRule.sections ? t('smart.examTooMany', { sections: examRule.sections }) : '' : '';
  const exerciseLabel = (value: string) => { for (const key of [`student.exercise.${value}`, `smart.option.${value}`]) { const translated = t(key); if (translated !== key) return translated; } return readable(value); };
  const chooseSubject = (value: string) => { setSubject(value); setLevel(value === 'english' || value === 'spanish' ? 'A2' : 'intermediate_band'); setExerciseTypes((EXAM_TYPES[value] || EXAM_TYPES.study_skills).slice(0, 2)); setDocument(null); };
  const select = (label: string, value: string, options: string[], onChange: (value: string) => void, format = readable) => <View style={styles.fieldCell}><Text style={styles.label}>{label}</Text><SelectField label={label} value={value} onChange={onChange} options={options.map((option) => ({ value: option, label: format(option) }))} /></View>;
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setConfirmReuse(false); setPendingReuse(null);
      if (!topic.trim() || kind === 'program') { setReuseMatches([]); return; }
      void (async () => {
        const session = await supabase?.auth.getSession();
        const token = session?.data.session?.access_token || '';
        const ownerId = session?.data.session?.user.id || '';
        const matches = await findGenerationMatches(process.env.EXPO_PUBLIC_SUPABASE_URL || '', process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '', token, ownerId, { kind, subject, topic: topic.trim(), stage, level, lessonPurpose, worksheetType, exerciseTypes });
        if (active) setReuseMatches(matches);
      })().catch(() => { if (active) setReuseMatches([]); });
    }, 400);
    return () => { active = false; clearTimeout(timer); };
  }, [kind, subject, topic, stage, level, lessonPurpose, worksheetType, exerciseTypes]);
  async function generate(confirmed?: Record<string, unknown>) {
    if (examTypeError) { setError(examTypeError); return; }
    if (kind !== 'program' && !topic.trim()) { setError(copy.toolRequired); return; }
    if (!confirmed && reuseMatches.length > 0) { setConfirmReuse(true); return; }
    const session = await supabase?.auth.getSession();
    const authenticated = Boolean(session?.data.session);
    if (kind === 'program') { router.push(authenticated ? '/smart-tools?tool=program' : '/sign-in'); return; }
    setBusy(true); setError(''); setFeedback(''); setFeedbackContext('generate'); setDocument(null); setSavedResourceId(null); setPendingSaveInput(null); setPublicVisibility(false); setPendingReuse(null);
    setConfirmReuse(false);
    try {
      const requestBody = confirmed ? { ...confirmed, reuseConfirmed: true } : { kind, subject, topic: topic.trim(), stage, level, language: subject === 'english' ? 'en' : subject === 'spanish' ? 'es' : language, planLanguage: language, lessonPurpose, worksheetType, examLength, exerciseTypes, notes, duration: '45 minutes', generationMode: 'ai', visibility: 'private' };
      if (authenticated) {
        const input = requestBody as SmartToolInput;
        const generated = await generateMaterial(input);
        setDocument(generated.document); setFeedback(t('smart.previewReady'));
        setPendingSaveInput({ ...input, generationMode: generated.model === 'template' ? 'template' : 'ai' });
        if (generated.model !== 'template') {
          try {
            const saved = await saveGeneratedMaterial(input, generated.document);
            setSavedResourceId(saved.id); setPendingSaveInput(null); setFeedbackContext('preview'); setFeedback(t('smart.saved'));
          } catch { setFeedbackContext('preview'); setError(t('smart.saveFailed')); }
        }
        return;
      }
      const response = await fetch('/api/generate', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody) });
      const payload = await response.json() as { document?: Record<string, unknown>; error?: string; matches?: GenerationMatch[] };
      if (response.status === 409 && payload.matches?.length) { setReuseMatches(payload.matches); setPendingReuse(requestBody); setConfirmReuse(true); return; }
      if (!response.ok || !payload.document) throw new Error(payload.error || copy.toolError);
      setDocument(payload.document); setFeedback(t('smart.previewReady'));
    } catch (failure) { if (failure instanceof GenerationReuseError) { setReuseMatches(failure.matches); setPendingReuse(confirmed || { kind, subject, topic: topic.trim(), stage, level, language: subject === 'english' ? 'en' : subject === 'spanish' ? 'es' : language, planLanguage: language, lessonPurpose, worksheetType, examLength, exerciseTypes, notes, duration: '45 minutes', generationMode: 'ai', visibility: 'private' }); setConfirmReuse(true); } else setError(pendingSaveInput ? t('smart.saveFailed') : failure instanceof Error ? failure.message : copy.toolError); } finally { setBusy(false); }
  }
  async function retrySave() {
    if (!pendingSaveInput || !document || busy) return;
    setBusy(true); setError(''); setFeedback(''); setFeedbackContext('preview');
    try { const saved = await saveGeneratedMaterial(pendingSaveInput, document); setSavedResourceId(saved.id); setPendingSaveInput(null); setFeedbackContext('preview'); setFeedback(t('smart.saved')); }
    catch { setError(t('smart.saveFailed')); }
    finally { setBusy(false); }
  }
  async function changeVisibility() {
    if (!savedResourceId || busy) return;
    setBusy(true); setError(''); setFeedback(''); setFeedbackContext('preview');
    try { await setGeneratedMaterialVisibility(kind, savedResourceId, publicVisibility ? 'private' : 'public'); setPublicVisibility(!publicVisibility); setFeedback(t(publicVisibility ? 'smart.saved' : 'smart.savedPublic')); }
    catch { setError(t('smart.visibilityFailed')); }
    finally { setBusy(false); }
  }
  return <View style={styles.shell}>
    <View style={styles.header}><View style={styles.headerCopy}><Text style={styles.kicker}>{copy.toolLimit}</Text><Text style={styles.title}>{copy.toolPreview}</Text></View><Pressable accessibilityRole="button" accessibilityLabel={copy.toolClose} onPress={onClose} style={styles.close}><Text style={styles.closeText}>✕</Text></Pressable></View>
    <TabRail accessibilityLabel={copy.toolPreview} items={kinds.map((item) => ({ value: item.value, label: `${item.icon} ${toolLabels[item.value]}` }))} value={kind} onChange={(value) => { setKind(value as Kind); setDocument(null); setSavedResourceId(null); setPendingSaveInput(null); setError(''); }} />
    <View style={[styles.columns, narrow && styles.columnsNarrow]}>
      <Panel style={[styles.builder, narrow && styles.narrowPanel]}>
        <Text style={styles.panelTitle}>{toolLabels[kind]}</Text>
        <View style={styles.grid}>{select(copy.toolSubject, subject, SUBJECTS, chooseSubject, (value) => canonicalSubjectLabel(value, t))}{select(copy.toolStage, stage, STAGES, setStage, (value) => learnerStageLabel(value, t))}{select(copy.toolLevel, level, levels, setLevel)}{kind !== 'program' ? <View style={styles.fieldCell}><Text style={styles.label}>{copy.toolTopic}</Text><Field value={topic} onChangeText={setTopic} placeholder={copy.toolTopic} /></View> : null}{kind === 'worksheet' ? select(copy.toolType, worksheetType, WORKSHEET_TYPES, setWorksheetType) : null}{kind === 'exam' ? select(copy.toolLength, examLength, ['short', 'medium', 'long'], (value) => { setExamLength(value); setError(''); }) : null}{kind === 'plan' ? select(copy.toolPurpose, lessonPurpose, ['introduce_concept', 'practice_skill', 'review_topic', 'diagnose_difficulty', 'discussion_exploration'], setLessonPurpose, (value) => lessonPurposeLabel(value, t)) : null}</View>
        {kind === 'exam' ? <OrderedMultiSelectField label={t('smart.exerciseTypes')} values={exerciseTypes} options={availableExamTypes.map((value) => ({ value, label: exerciseLabel(value) }))} maxItems={examRule.sections} help={t('smart.examLengthRule', { length: t(`smart.option.${examLength}`), sections: examRule.sections, min: examRule.questionsMin, max: examRule.questionsMax })} addLabel={t('smart.addExerciseType')} emptyLabel={t('smart.noExerciseTypes')} moveUpLabel={t('smart.moveExerciseUp')} moveDownLabel={t('smart.moveExerciseDown')} removeLabel={t('smart.removeExerciseType')} onChange={(values) => { setExerciseTypes(values); setError(''); }} /> : null}
        <View><Text style={styles.label}>{copy.toolNotes}</Text><Field value={notes} onChangeText={setNotes} placeholder={copy.toolNotes} multiline numberOfLines={3} style={styles.notes} /></View>
        {kind === 'program' ? <Text style={styles.muted}>{copy.toolProgramNote}</Text> : null}
        {reuseMatches.length ? <View style={styles.result}><Text style={styles.reuseNotice}>{t('smart.reuseMatches')}</Text>{reuseMatches.map((match) => <Pressable key={`${match.kind}-${match.id}`} onPress={() => router.push(match.source === 'own' ? { pathname: '/resources', params: { kind: match.kind, scope: 'mine', resourceId: match.id, from: 'explorer', tool: kind, returnNonce: String(Date.now()) } } : { pathname: '/', params: { resourceKind: match.kind, resourceId: match.id, from: 'explorer', tool: kind } })}><Text style={styles.saveText}>{match.title || match.topic} →</Text></Pressable>)}{confirmReuse ? <View accessibilityLiveRegion="polite"><Text style={styles.muted}>{t('smart.reuseContinueQuestion')}</Text><Pressable accessibilityRole="button" disabled={busy} onPress={() => void generate(pendingReuse || { kind, subject, topic: topic.trim(), stage, level, language: subject === 'english' ? 'en' : subject === 'spanish' ? 'es' : language, planLanguage: language, lessonPurpose, worksheetType, examLength, exerciseTypes, notes, duration: '45 minutes', generationMode: 'ai', visibility: 'private' })} style={[styles.action, busy && styles.disabled]}><Text style={styles.actionText}>{t('smart.reuseConfirmYes')}</Text></Pressable><Pressable accessibilityRole="button" onPress={() => { setConfirmReuse(false); setPendingReuse(null); }} style={styles.save}><Text style={styles.saveText}>{t('common.cancel')}</Text></Pressable></View> : null}</View> : null}
        <Pressable accessibilityRole="button" disabled={busy || confirmReuse || Boolean(examTypeError)} onPress={() => void generate()} style={[styles.action, busy && styles.disabled]}><Text style={styles.actionText}>{busy ? copy.toolGenerating : reuseMatches.length ? t('smart.reuseContinueQuestion') : kind === 'program' ? copy.toolProgramContinue : copy.toolGenerate}</Text></Pressable>{examTypeError ? <ActionFeedback message={examTypeError} tone="error" /> : null}{feedbackContext === 'generate' ? <ActionFeedback message={error || feedback} tone={error ? 'error' : 'success'} /> : null}
      </Panel>
      <Panel style={[styles.preview, narrow && styles.narrowPanel]}><Text style={styles.panelTitle}>{copy.toolPreview}</Text>{document ? <View style={styles.result}>{kind === 'worksheet' ? <WorksheetView detail={{ worksheet_json: document, worksheet_type: worksheetType }} locale={language} /> : kind === 'exam' ? <ExamView detail={{ exam_data: document, answer_key: document.answer_key }} locale={language} /> : kind === 'plan' ? <LessonPlanView detail={{ plan_json: document }} locale={language} /> : <DocumentView value={document} language={language} />}{savedResourceId ? <Pressable accessibilityRole="button" disabled={busy} onPress={() => void changeVisibility()} style={styles.save}><Text style={styles.saveText}>{t(publicVisibility ? 'resources.makePrivate' : 'resources.makePublic')}</Text></Pressable> : pendingSaveInput ? <Pressable accessibilityRole="button" disabled={busy} onPress={() => void retrySave()} style={styles.save}><Text style={styles.saveText}>{t('smart.saveLibrary')}</Text></Pressable> : <Pressable accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.save}><Text style={styles.saveText}>{copy.toolSave} →</Text></Pressable>}{feedbackContext === 'preview' ? <ActionFeedback message={error || feedback} tone={error ? 'error' : 'success'} /> : null}</View> : <View style={styles.emptyPreview} accessibilityLiveRegion="polite">{busy ? <><ActivityIndicator size="large" color={colors.primary} /><Text style={styles.muted}>{t('smart.generatingHelp')}</Text></> : <><Text style={styles.emptyIcon}>{kinds.find((item) => item.value === kind)?.icon}</Text><Text style={styles.muted}>{kind === 'program' ? copy.toolProgramNote : copy.toolLimit}</Text></>}</View>}</Panel>
    </View>
  </View>;
}
const styles = StyleSheet.create({
  shell: { gap: 18 }, header: { flexDirection: 'row', gap: 14, alignItems: 'center' }, headerCopy: { flex: 1 }, kicker: { color: colors.primary, fontSize: 11, fontWeight: '800' }, title: { color: colors.ink, fontSize: 24, fontWeight: '900', marginTop: 5 }, close: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center', borderRadius: 18, backgroundColor: colors.surfaceSoft }, closeText: { color: colors.ink, fontWeight: '900' },
  columns: { flexDirection: 'row', gap: 14, alignItems: 'flex-start' }, columnsNarrow: { flexDirection: 'column', alignItems: 'stretch' }, builder: { flexGrow: 1, flexBasis: 300, minWidth: 0, gap: 15 }, preview: { flexGrow: 1, flexBasis: 300, minWidth: 0, minHeight: 360, gap: 14 }, narrowPanel: { flexGrow: 0, flexBasis: 'auto', width: '100%' }, panelTitle: { color: colors.ink, fontSize: 18, fontWeight: '900' }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, fieldCell: { flexBasis: '45%', flexGrow: 1, minWidth: 165, gap: 5 }, label: { color: colors.inkSecondary, fontSize: 11, fontWeight: '800', marginBottom: 6 }, notes: { minHeight: 80, paddingTop: 12, textAlignVertical: 'top' }, muted: { color: colors.muted, fontSize: 12, lineHeight: 18 }, error: { color: colors.danger, fontSize: 12, fontWeight: '800' }, reuseNotice: { color: colors.primary, backgroundColor: colors.primarySoft, fontSize: 12, fontWeight: '800', padding: 10, borderRadius: 9 },
  exerciseGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, exerciseChip: { borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surface, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8 }, exerciseChipActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, exerciseText: { color: colors.muted, fontSize: 11, fontWeight: '700' }, exerciseTextActive: { color: colors.primary }, action: { alignSelf: 'flex-start', paddingHorizontal: 18, paddingVertical: 13, backgroundColor: colors.primary, borderRadius: 12 }, disabled: { opacity: 0.5 }, actionText: { color: colors.inverse, fontWeight: '900' }, emptyPreview: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 20 }, emptyIcon: { fontSize: 40 }, result: { gap: 12 }, documentGroup: { gap: 9 }, documentLine: { paddingLeft: 11, borderLeftWidth: 2, borderLeftColor: colors.lineStrong, gap: 3 }, documentLabel: { color: colors.primary, fontSize: 12, fontWeight: '800' }, documentText: { color: colors.inkSecondary, fontSize: 13, lineHeight: 20 }, save: { alignSelf: 'flex-start', paddingVertical: 9 }, saveText: { color: colors.primary, fontWeight: '800' },
});
