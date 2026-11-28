import { useEffect, useMemo, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Image } from 'expo-image';
import { AppShell } from '@/components/app-shell';
import { BackLink } from '@/components/back-link';
import { SmartToolTabs } from '@/components/smart-tool-tabs';
import { ResourceEditor } from '@/components/resource-editor';
import { GenerationIntentQuestion } from '@/components/generation-intent-question';
import { ActionFeedback, Button, Disclosure, EditIconButton, Field, HelpIcon, Panel, SelectField } from '@/components/ui';
import { downloadResourceDocx, downloadResourcePdf } from '@/services/document-exports';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import { oralDocumentIssues, oralExerciseLabel, oralExercises, oralFamily, oralTemplateAvailable, type OralDocument } from '@/shared/oral-presentation';
import { generateMaterial, getPersonalizationStudents, getSmartToolPrograms, getSmartToolProgramTopics, saveGeneratedMaterial, setGeneratedMaterialVisibility, updateGeneratedMaterial, type GeneratedMaterial, type PersonalizationStudent, type SmartToolInput, type SmartToolProgram, type SmartToolProgramTopic, GenerationReuseError } from '@/services/smart-tools';
import { canonicalSubjectKey } from '@/lib/subjects';
import { generateLessonPlanCover } from '@/services/resource-library';

const SUBJECTS = ['English', 'Spanish', 'Turkish', 'Mathematics', 'Science', 'Music', 'Study skills', 'Other'];
const STAGES = ['Early primary', 'Upper primary', 'Lower secondary', 'Upper secondary', 'Adult'];
const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Beginner', 'Intermediate', 'Advanced'];
const LANGUAGES = ['en', 'es', 'tr'] as const;
const STAGE_ALIASES: Record<string, string> = { early_primary: 'Early primary', upper_primary: 'Upper primary', lower_secondary: 'Lower secondary', upper_secondary: 'Upper secondary', adult_stage: 'Adult' };
const LEVEL_ALIASES: Record<string, string> = { beginner_band: 'Beginner', intermediate_band: 'Intermediate', advanced_band: 'Advanced' };
const storedStage = (value: string) => Object.entries(STAGE_ALIASES).find(([, label]) => label === value)?.[0] || value;
const storedLevel = (value: string) => Object.entries(LEVEL_ALIASES).find(([, label]) => label === value)?.[0] || value;

export default function OralPresentationsScreen() {
  const { t, language } = useAppPreferences();
  const params = useLocalSearchParams<{ subject?: string; customSubject?: string; topic?: string; stage?: string; level?: string; programId?: string; programTopicId?: string; objective?: string; oralExerciseType?: string; studentId?: string }>();
  const [subject, setSubject] = useState(() => SUBJECTS.includes(String(params.subject || '')) ? String(params.subject) : 'English');
  const [customSubject, setCustomSubject] = useState(String(params.customSubject || ''));
  const [topic, setTopic] = useState(String(params.topic || ''));
  const [stage, setStage] = useState(() => STAGES.includes(String(params.stage || '')) ? String(params.stage) : STAGE_ALIASES[String(params.stage || '')] || 'Adult');
  const [level, setLevel] = useState(() => LEVELS.includes(String(params.level || '')) ? String(params.level) : LEVEL_ALIASES[String(params.level || '')] || 'B1');
  const [exerciseType, setExerciseType] = useState(String(params.oralExerciseType || 'monologue'));
  const [objective, setObjective] = useState(String(params.objective || params.topic || ''));
  const [limit, setLimit] = useState('180');
  const [instructions, setInstructions] = useState('');
  const [studentLanguage, setStudentLanguage] = useState<'en' | 'es' | 'tr'>(language);
  const [teacherLanguage, setTeacherLanguage] = useState<'en' | 'es' | 'tr'>(language);
  const [mode, setMode] = useState('ai');
  const [visibility, setVisibility] = useState('private');
  const [students, setStudents] = useState<PersonalizationStudent[]>([]);
  const [programs, setPrograms] = useState<SmartToolProgram[]>([]);
  const [programTopics, setProgramTopics] = useState<SmartToolProgramTopic[]>([]);
  const [programId, setProgramId] = useState(String(params.programId || ''));
  const [programTopicId, setProgramTopicId] = useState(String(params.programTopicId || ''));
  const [programError, setProgramError] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState(String(params.studentId || ''));
  const [generated, setGenerated] = useState<GeneratedMaterial | null>(null);
  const [savedId, setSavedId] = useState('');
  const [showPreviewEditor, setShowPreviewEditor] = useState(false);
  const [picturePending, setPicturePending] = useState(false);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState<'error' | 'success'>('error');
  const [reuseConfirmed, setReuseConfirmed] = useState(false);
  const family = oralFamily(subject === 'Other' ? customSubject : subject);
  useEffect(() => { let active = true; void getPersonalizationStudents().then((rows) => { if (active) setStudents(rows); }).catch(() => {}); return () => { active = false; }; }, []);
  useEffect(() => { let active = true; void getSmartToolPrograms().then((rows) => { if (!active) return; setPrograms(rows); const linked = rows.find((row) => row.id === params.programId); if (linked && params.programTopicId) { setSubject(SUBJECTS.find((value) => canonicalSubjectKey(value) === canonicalSubjectKey(linked.subject)) || 'Other'); setCustomSubject(linked.customSubject); setStage(STAGE_ALIASES[linked.stage] || linked.stage); setLevel(LEVEL_ALIASES[linked.level] || linked.level); } }).catch((reason) => { if (active) setProgramError(reason instanceof Error ? reason.message : t('smart.programLoadFailed')); }); return () => { active = false; }; }, [params.programId, params.programTopicId, t]);
  useEffect(() => { if (!programId) return; let active = true; void getSmartToolProgramTopics(programId).then((rows) => { if (!active) return; setProgramTopics(rows); const linked = rows.find((row) => row.id === programTopicId); if (linked) { setTopic(linked.title); setObjective(linked.learningObjectives[0] || linked.title); } }).catch((reason) => { if (active) setProgramError(reason instanceof Error ? reason.message : t('smart.programLoadFailed')); }); return () => { active = false; }; }, [programId, programTopicId, t]);
  const selectedStudent = students.find((student) => student.id === selectedStudentId);
  const matchingPrograms = programs.filter((item) => canonicalSubjectKey(item.subject) === canonicalSubjectKey(subject) && (subject !== 'Other' || item.customSubject.trim().toLowerCase() === customSubject.trim().toLowerCase()) && (STAGE_ALIASES[item.stage] || item.stage) === stage && (LEVEL_ALIASES[item.level] || item.level) === level);
  const linkedTopic = programTopics.find((item) => item.id === programTopicId);
  function clearProgramSelection() { setProgramId(''); setProgramTopicId(''); setProgramTopics([]); setProgramError(''); }
  const options = useMemo(() => oralExercises(family), [family]);
  const selectedExercise = options.includes(exerciseType) ? exerciseType : options[0];
  const input: SmartToolInput = {
    kind: 'oral_presentation', subject, customSubject, topic: topic.trim(), stage: storedStage(stage), level: storedLevel(level),
    oralExerciseType: selectedExercise, objective: objective.trim(), maxDurationSeconds: Number(limit),
    language: studentLanguage, planLanguage: teacherLanguage, nativeLanguage: selectedStudent?.nativeLanguage || undefined, generationMode: mode,
    duration: `${limit} seconds`, instructions, notes: '', visibility: 'private', reuseConfirmed, programId: linkedTopic ? programId : undefined, programTopicId: linkedTopic?.id,
  };
  const validation = !topic.trim() || !objective.trim() || (subject === 'Other' && !customSubject.trim()) ||
    !Number.isInteger(Number(limit)) || Number(limit) < 30 || Number(limit) > 600 ||
    (mode === 'template' && !oralTemplateAvailable(selectedExercise));
  const document = generated?.document as OralDocument | undefined;

  async function create() {
    if (validation) return;
    setBusy(true); setMessage(''); setGenerated(null); setSavedId(''); setPicturePending(false); setShowPreviewEditor(false); setVisibility('private');
    try {
      const result = await generateMaterial(input, undefined, selectedStudent?.name || '', selectedStudentId);
      setGenerated(result);
      const saved = await saveGeneratedMaterial({ ...input, generationId: result.generationId }, result.document);
      setSavedId(saved.id);
      if (selectedExercise === 'picture_description') {
        setPicturePending(true);
        try {
          const image = await generateLessonPlanCover(saved.id, 'oral_presentation', 'picture');
          const updated = { ...result.document, picture: image };
          await updateGeneratedMaterial('oral_presentation', saved.id, updated);
          setGenerated({ ...result, document: updated });
          setPicturePending(false);
        } catch (reason) {
          setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('oral.pictureFailed'));
          return;
        }
      }
      setMessageTone('success'); setMessage(t('oral.saved'));
    }
    catch (reason) {
      setMessageTone('error');
      if (reason instanceof GenerationReuseError) setMessage(t('oral.similarFound'));
      else setMessage(reason instanceof Error ? reason.message : t('smart.generationFailed'));
    } finally { setBusy(false); }
  }
  async function save() {
    if (!generated || savedId) return;
    const issues = oralDocumentIssues(generated.document, family, selectedExercise);
    if (issues.length) { setMessageTone('error'); setMessage(issues.join(' · ')); return; }
    setBusy(true); setMessage('');
    try {
      const saved = await saveGeneratedMaterial({ ...input, generationId: generated.generationId }, generated.document);
      setSavedId(saved.id);
      if (selectedExercise === 'picture_description') {
        setPicturePending(true);
        const image = await generateLessonPlanCover(saved.id, 'oral_presentation', 'picture');
        const updated = { ...generated.document, picture: image };
        await updateGeneratedMaterial('oral_presentation', saved.id, updated);
        setGenerated({ ...generated, document: updated });
        setPicturePending(false);
      }
      setMessageTone('success'); setMessage(t('oral.saved'));
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('smart.saveFailed')); }
    finally { setBusy(false); }
  }
  async function retryPicture() {
    if (!savedId || !generated || !picturePending) return;
    setBusy(true); setMessage('');
    try {
      const image = await generateLessonPlanCover(savedId, 'oral_presentation', 'picture');
      const updated = { ...generated.document, picture: image };
      await updateGeneratedMaterial('oral_presentation', savedId, updated);
      setGenerated({ ...generated, document: updated });
      setPicturePending(false); setMessageTone('success'); setMessage(t('oral.saved'));
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('oral.pictureFailed')); }
    finally { setBusy(false); }
  }
  async function generateCover() {
    if (!savedId || !generated || picturePending) return;
    setBusy(true); setMessage('');
    try {
      const cover = await generateLessonPlanCover(savedId, 'oral_presentation');
      const updated = { ...generated.document, cover_image: cover };
      await updateGeneratedMaterial('oral_presentation', savedId, updated);
      setGenerated({ ...generated, document: updated });
      setMessageTone('success'); setMessage(t('planView.imageSaved'));
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('planView.imageFailed')); }
    finally { setBusy(false); }
  }
  async function edit(next: Record<string, unknown>) {
    if (!generated) return;
    const issues = oralDocumentIssues(next, family, selectedExercise);
    if (issues.length) { setMessageTone('error'); setMessage(issues.join(' · ')); return; }
    setMessage('');
    if (savedId) {
      try { await updateGeneratedMaterial('oral_presentation', savedId, next); setGenerated({ ...generated, document: next }); setShowPreviewEditor(false); setMessageTone('success'); setMessage(t('oral.saved')); }
      catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('smart.saveFailed')); }
    } else { setGenerated({ ...generated, document: next }); setShowPreviewEditor(false); }
  }
  async function exportDocument(format: 'pdf' | 'docx', variant: 'student' | 'teacher') {
    if (!document) return;
    setExporting(true); setMessage('');
    try {
      const detail = { oral_data: document, subject, topic, learner_stage: stage, level_or_band: level };
      if (format === 'pdf') await downloadResourcePdf(document.title, detail, language, variant);
      else await downloadResourceDocx(document.title, detail, language, variant);
    } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('smart.saveFailed')); }
    finally { setExporting(false); }
  }
  async function changeVisibility() {
    if (!savedId) return;
    const next = visibility === 'public' ? 'private' : 'public';
    if (next === 'public' && document?.exercise_type === 'picture_description' && (picturePending || !document.picture?.image_data_url)) {
      setMessageTone('error'); setMessage(t('oral.pictureRequired')); return;
    }
    setBusy(true); setMessage('');
    try { await setGeneratedMaterialVisibility('oral_presentation', savedId, next); setVisibility(next); setMessageTone('success'); setMessage(t(next === 'public' ? 'smart.visibilityPublic' : 'smart.visibilityPrivate')); }
    catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('smart.visibilityFailed')); }
    finally { setBusy(false); }
  }
  return <AppShell title={t('smart.title')} eyebrow={t('smart.eyebrow')}>
    {params.programId && params.programTopicId ? <BackLink label={t('smart.backToProgram')} onPress={() => router.push({ pathname: '/resources', params: { kind: 'program', scope: 'mine', resourceId: params.programId } })} /> : null}
    <Text style={styles.intro}>{t('smart.intro')}</Text>
    <SmartToolTabs active="oral_presentation" onSelect={(kind) => { if (kind !== 'oral_presentation') router.push({ pathname: '/smart-tools', params: { tool: kind, subject, customSubject, topic, stage, level, studentId: selectedStudentId, programId, programTopicId } }); }} />
    <View style={styles.columns}>
      <Panel style={styles.builder}>
        <Text style={styles.sectionTitle}>{t('smart.build', { tool: t('oral.title').toLocaleLowerCase(language) })}</Text>
        <Text style={styles.sectionBody}>{t('oral.createHelp')}</Text>
        <Disclosure title={t('smart.generationSetup')} summary={`${mode === 'ai' ? 'AI' : t('oral.template')} · ${selectedStudent?.name || t('smart.noStudent')}`} headerAction={<HelpIcon title={t('smart.generationDataTitle')}>{t('smart.generationDataHelp')}</HelpIcon>} defaultOpen>
          <View style={styles.fields}>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.generationMode')}</Text><SelectField label={t('smart.generationMode')} value={mode} options={[{ value: 'ai', label: 'AI' }, { value: 'template', label: t('oral.template') }]} onChange={setMode} /></View>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.selectedStudent')}</Text><SelectField label={t('smart.selectedStudent')} value={selectedStudentId} options={[{ value: '', label: t('smart.noStudent') }, ...students.map((student) => ({ value: student.id, label: student.name }))]} onChange={setSelectedStudentId} /></View>
            {selectedStudent?.nativeLanguage ? <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.nativeLanguage')}</Text><Field editable={false} value={selectedStudent.nativeLanguage} /></View> : null}
          </View>
        </Disclosure>
        <Disclosure title={t('smart.learningContext')} summary={`${subject} · ${stage} · ${level}`} defaultOpen>
          <View style={styles.fields}>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.subject')}</Text><SelectField label={t('smart.subject')} value={subject} options={SUBJECTS.map((value) => ({ value, label: value }))} onChange={(value) => { setSubject(value); setExerciseType(oralExercises(oralFamily(value))[0]); clearProgramSelection(); }} /></View>
            {subject === 'Other' ? <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.customSubject')}</Text><Field value={customSubject} onChangeText={(value) => { setCustomSubject(value); clearProgramSelection(); }} maxLength={120} /></View> : null}
            <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.stage')}</Text><SelectField label={t('smart.stage')} value={stage} options={STAGES.map((value) => ({ value, label: value }))} onChange={(value) => { setStage(value); clearProgramSelection(); }} /></View>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('smart.level')}</Text><SelectField label={t('smart.level')} value={level} options={LEVELS.map((value) => ({ value, label: value }))} onChange={(value) => { setLevel(value); clearProgramSelection(); }} /></View>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('oral.studentLanguage')}</Text><SelectField label={t('oral.studentLanguage')} value={studentLanguage} options={LANGUAGES.map((value) => ({ value, label: t(`language.${value}`) }))} onChange={(value) => setStudentLanguage(value as typeof studentLanguage)} /></View>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('oral.teacherLanguage')}</Text><SelectField label={t('oral.teacherLanguage')} value={teacherLanguage} options={LANGUAGES.map((value) => ({ value, label: t(`language.${value}`) }))} onChange={(value) => setTeacherLanguage(value as typeof teacherLanguage)} /></View>
          </View>
          <Text style={styles.label}>{t('smart.programTopicSource')}</Text><SelectField label={t('smart.programTopicSource')} value={programId} options={[{ value: '', label: t('smart.manualTopic') }, ...matchingPrograms.map((item) => ({ value: item.id, label: item.title }))]} onChange={(value) => { setProgramId(value); setProgramTopicId(''); setProgramTopics([]); setProgramError(''); if (value) { setTopic(''); setObjective(''); } }} />
          {programId ? <><Text style={styles.label}>{t('smart.programTopic')}</Text><SelectField label={t('smart.programTopic')} value={programTopicId} options={[{ value: '', label: t('smart.chooseProgramTopic') }, ...programTopics.map((item) => ({ value: item.id, label: `${item.unitTitle} · ${item.title}` }))]} onChange={(value) => { setProgramTopicId(value); const selected = programTopics.find((item) => item.id === value); if (selected) { setTopic(selected.title); setObjective(selected.learningObjectives[0] || selected.title); } else { setTopic(''); setObjective(''); } }} /></> : null}
          {programError ? <Text style={styles.warning}>{programError}</Text> : null}
          <Text style={styles.label}>{t('smart.topic')}</Text><Field value={topic} onChangeText={setTopic} editable={!linkedTopic} multiline numberOfLines={3} style={styles.topicField} placeholder={t('smart.topicPlaceholder')} maxLength={180} />
        </Disclosure>
        <Disclosure title={t('smart.toolOptions')} summary={`${oralExerciseLabel(selectedExercise, language)} · ${limit} s`} defaultOpen>
          <View style={styles.fields}>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('oral.exerciseType')}</Text><SelectField label={t('oral.exerciseType')} value={selectedExercise} options={options.map((value) => ({ value, label: oralExerciseLabel(value, language) }))} onChange={setExerciseType} /></View>
            <View style={styles.fieldCell}><Text style={styles.label}>{t('oral.maxDuration')}</Text><Field value={limit} onChangeText={setLimit} keyboardType="number-pad" maxLength={3} /></View>
          </View>
          <Text style={styles.label}>{t('oral.objective')}</Text><Field value={objective} onChangeText={setObjective} multiline numberOfLines={2} style={styles.topicField} maxLength={500} />
          <Text style={styles.label}>{t('oral.additionalInstructions')}</Text><Field value={instructions} onChangeText={setInstructions} multiline numberOfLines={4} style={styles.notesField} maxLength={1000} />
          {mode === 'template' && !oralTemplateAvailable(selectedExercise) ? <Text style={styles.warning}>{t('oral.templateUnavailable')}</Text> : null}
        </Disclosure>
        {message === t('oral.similarFound') ? <View style={styles.actions}><Text style={styles.sectionBody}>{message}</Text><Button secondary onPress={() => { setReuseConfirmed(true); setMessage(''); }}>{t('smart.reuseConfirmYes')}</Button><Button secondary onPress={() => setMessage('')}>{t('common.cancel')}</Button></View> : null}
        <Button disabled={busy || validation} onPress={() => void create()}>{busy ? t('smart.generating') : t('smart.generate', { tool: t('oral.title') })}</Button>
        {message !== t('oral.similarFound') ? <ActionFeedback message={message} tone={messageTone} onDismiss={() => setMessage('')} /> : null}
      </Panel>
      <Panel style={styles.preview}>
        <View style={styles.previewHeader}><View><Text style={styles.sectionTitle}>{t('smart.preview')}</Text><Text style={styles.sectionBody}>{document ? t('smart.previewReady') : busy ? t('smart.generatingHelp') : t('smart.previewEmpty')}</Text></View>{document ? <EditIconButton accessibilityLabel={t('resources.editContent')} onPress={() => setShowPreviewEditor((value) => !value)} /> : null}</View>
        {document ? <ScrollView style={styles.previewScroll} contentContainerStyle={styles.previewContent}>
          <View style={styles.actions}>
            <Button secondary disabled={exporting} onPress={() => void exportDocument('pdf', 'student')}>{t('common.downloadStudentPdf')}</Button>
            <Button secondary disabled={exporting} onPress={() => void exportDocument('pdf', 'teacher')}>{t('common.downloadTeacherPdf')}</Button>
            <Button secondary disabled={exporting} onPress={() => void exportDocument('docx', 'student')}>{t('common.downloadStudentWord')}</Button>
            <Button secondary disabled={exporting} onPress={() => void exportDocument('docx', 'teacher')}>{t('common.downloadTeacherWord')}</Button>
            {savedId ? <Button secondary disabled={busy || (visibility !== 'public' && document?.exercise_type === 'picture_description' && (picturePending || !document.picture?.image_data_url))} onPress={() => void changeVisibility()}>{t(visibility === 'public' ? 'resources.makePrivate' : 'resources.makePublic')}</Button> : null}
            {savedId ? <Button secondary disabled={busy || picturePending} onPress={() => void generateCover()}>{t(document.cover_image?.image_data_url ? 'planView.regenerateImage' : 'planView.generateImage')}</Button> : null}
            {savedId ? <Button secondary onPress={() => router.push({ pathname: '/resources', params: { kind: 'oral_presentation', scope: 'mine', resourceId: savedId, from: 'smart-tools', tool: 'oral_presentation', returnNonce: String(Date.now()) } })}>{t('smart.openSavedProgram')}</Button> : null}
            {picturePending && savedId ? <Button disabled={busy} onPress={() => void retryPicture()}>{t('oral.retryPicture')}</Button> : null}
            {savedId && !picturePending ? <Button onPress={() => router.push({ pathname: '/resources', params: { kind: 'oral_presentation', scope: 'mine', resourceId: savedId, assign: '1', from: 'smart-tools', tool: 'oral_presentation', returnNonce: String(Date.now()) } })}>{t('resources.assignToStudent')}</Button> : !savedId ? <Button disabled={busy} onPress={() => void save()}>{t('smart.retrySave')}</Button> : null}
          </View>
          {showPreviewEditor ? <ResourceEditor document={generated!.document} onApply={(next) => void edit(next)} /> : null}
          <View style={styles.document}><Text style={styles.documentTitle}>{document.title}</Text><Text style={styles.body}>{document.student_instructions}</Text>{document.cover_image?.image_data_url ? <Image source={{ uri: document.cover_image.image_data_url }} style={{ width: '100%', aspectRatio: 16 / 9, borderRadius: 12 }} contentFit="cover" /> : null}{document.picture?.image_data_url ? <Image source={{ uri: document.picture.image_data_url }} style={{ width: '100%', aspectRatio: 16 / 9, borderRadius: 12 }} contentFit="contain" /> : null}{document.stimulus ? <Text style={styles.stimulus}>{document.stimulus}</Text> : null}<Text style={styles.body}>{document.expected_response}</Text><Text style={styles.heading}>{t('oral.rubric')}</Text>{document.rubric.map((criterion) => <Text key={criterion.id} style={styles.body}>{criterion.label} · {criterion.max_score}</Text>)}</View>
          {savedId && mode === 'ai' ? <GenerationIntentQuestion resourceType="oral_presentation" resourceId={savedId} surface="generation_preview" /> : null}
        </ScrollView> : <View style={styles.emptyPreview} accessibilityLiveRegion="polite">{busy ? <ActivityIndicator size="large" color={colors.primary} /> : <Text style={styles.emptyIcon}>🎙️</Text>}<Text style={styles.emptyTitle}>{t(busy ? 'smart.generating' : 'smart.ready')}</Text><Text style={styles.emptyBody}>{t(busy ? 'smart.generatingHelp' : 'smart.readyHelp')}</Text></View>}
      </Panel>
    </View>
  </AppShell>;
}

const styles = StyleSheet.create({
  intro: { color: colors.muted, fontSize: 16, lineHeight: 24, marginBottom: 18, maxWidth: 800 },
  columns: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, alignItems: 'flex-start' },
  builder: { flex: 1, minWidth: 320, gap: 8 },
  preview: { flex: 1.2, minWidth: 340, minHeight: 620 },
  previewHeader: { flexDirection: 'row', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' },
  sectionTitle: { color: colors.ink, fontSize: 19, fontWeight: '900' },
  sectionBody: { color: colors.muted, fontSize: 11, lineHeight: 17, marginTop: 3, marginBottom: 5 },
  fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 },
  fieldCell: { flex: 1, minWidth: 150 },
  label: { color: colors.ink, fontSize: 10, fontWeight: '800', marginTop: 6, marginBottom: 4 },
  topicField: { minHeight: 78, paddingTop: 12, textAlignVertical: 'top' },
  notesField: { minHeight: 100, paddingTop: 12, textAlignVertical: 'top' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, marginBottom: 12 },
  previewScroll: { maxHeight: 690, marginTop: 10 },
  previewContent: { gap: 14, paddingBottom: 20 },
  emptyPreview: { minHeight: 450, alignItems: 'center', justifyContent: 'center', padding: 30 },
  emptyIcon: { fontSize: 44 },
  emptyTitle: { color: colors.ink, fontSize: 18, fontWeight: '900', marginTop: 12 },
  emptyBody: { color: colors.muted, fontSize: 12, lineHeight: 19, textAlign: 'center', maxWidth: 300, marginTop: 6 },
  document: { gap: 12, padding: 16, borderRadius: 14, backgroundColor: colors.surfaceSoft },
  documentTitle: { fontSize: 20, color: colors.ink, fontWeight: '900' },
  heading: { fontSize: 16, color: colors.ink, fontWeight: '800' },
  body: { color: colors.ink, lineHeight: 22 },
  stimulus: { color: colors.ink, backgroundColor: colors.surface, padding: 16, borderRadius: 12 },
  warning: { color: colors.danger },
});
