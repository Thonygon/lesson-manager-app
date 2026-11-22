import { useMemo, useState } from 'react';
import { router } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { AppShell } from '@/components/app-shell';
import { ResourceEditor } from '@/components/resource-editor';
import { ActionFeedback, Button, Field, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import { oralDocumentIssues, oralExerciseLabel, oralExercises, oralFamily, oralTemplateAvailable, type OralDocument } from '@/shared/oral-presentation';
import { generateMaterial, saveGeneratedMaterial, updateGeneratedMaterial, type GeneratedMaterial, type SmartToolInput, GenerationReuseError } from '@/services/smart-tools';

const SUBJECTS = ['English', 'Spanish', 'Turkish', 'Mathematics', 'Science', 'Music', 'Study skills', 'Other'];
const STAGES = ['Early primary', 'Upper primary', 'Lower secondary', 'Upper secondary', 'Adult'];
const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Beginner', 'Intermediate', 'Advanced'];
const LANGUAGES = ['en', 'es', 'tr'] as const;

export default function OralPresentationsScreen() {
  const { t, language } = useAppPreferences();
  const [subject, setSubject] = useState('English');
  const [customSubject, setCustomSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [stage, setStage] = useState('Adult');
  const [level, setLevel] = useState('B1');
  const [exerciseType, setExerciseType] = useState('monologue');
  const [objective, setObjective] = useState('');
  const [limit, setLimit] = useState('180');
  const [instructions, setInstructions] = useState('');
  const [studentLanguage, setStudentLanguage] = useState<'en' | 'es' | 'tr'>(language);
  const [teacherLanguage, setTeacherLanguage] = useState<'en' | 'es' | 'tr'>(language);
  const [mode, setMode] = useState('ai');
  const [visibility, setVisibility] = useState('private');
  const [generated, setGenerated] = useState<GeneratedMaterial | null>(null);
  const [savedId, setSavedId] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [reuseConfirmed, setReuseConfirmed] = useState(false);
  const family = oralFamily(subject === 'Other' ? customSubject : subject);
  const options = useMemo(() => oralExercises(family), [family]);
  const selectedExercise = options.includes(exerciseType) ? exerciseType : options[0];
  const input: SmartToolInput = {
    kind: 'oral_presentation', subject, customSubject, topic: topic.trim(), stage, level,
    oralExerciseType: selectedExercise, objective: objective.trim(), maxDurationSeconds: Number(limit),
    language: studentLanguage, planLanguage: teacherLanguage, generationMode: mode,
    duration: `${limit} seconds`, instructions, notes: '', visibility, reuseConfirmed,
  };
  const validation = !topic.trim() || !objective.trim() || (subject === 'Other' && !customSubject.trim()) ||
    !Number.isInteger(Number(limit)) || Number(limit) < 30 || Number(limit) > 600 ||
    (mode === 'template' && !oralTemplateAvailable(selectedExercise));
  const document = generated?.document as OralDocument | undefined;

  async function create() {
    if (validation) return;
    setBusy(true); setMessage(''); setGenerated(null); setSavedId('');
    try { setGenerated(await generateMaterial(input)); }
    catch (reason) {
      if (reason instanceof GenerationReuseError) setMessage(t('oral.similarFound'));
      else setMessage(reason instanceof Error ? reason.message : t('smart.generationFailed'));
    } finally { setBusy(false); }
  }
  async function save() {
    if (!generated || savedId) return;
    const issues = oralDocumentIssues(generated.document, family, selectedExercise);
    if (issues.length) { setMessage(issues.join(' · ')); return; }
    setBusy(true); setMessage('');
    try {
      const saved = await saveGeneratedMaterial({ ...input, generationId: generated.generationId }, generated.document);
      setSavedId(saved.id); setMessage(t('oral.saved'));
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : t('smart.saveFailed')); }
    finally { setBusy(false); }
  }
  async function edit(next: Record<string, unknown>) {
    if (!generated) return;
    const issues = oralDocumentIssues(next, family, selectedExercise);
    if (issues.length) { setMessage(issues.join(' · ')); return; }
    setMessage('');
    if (savedId) {
      try { await updateGeneratedMaterial('oral_presentation', savedId, next); setGenerated({ ...generated, document: next }); setMessage(t('oral.saved')); }
      catch (reason) { setMessage(reason instanceof Error ? reason.message : t('smart.saveFailed')); }
    } else setGenerated({ ...generated, document: next });
  }
  return <AppShell title={t('oral.title')} eyebrow={t('smart.eyebrow')}>
    <ScrollView contentContainerStyle={styles.stack}>
      <Button secondary onPress={() => router.push('/smart-tools')}>{t('oral.backToTools')}</Button>
      <Panel style={styles.stack}>
        <Text style={styles.title}>{t('oral.createTitle')}</Text>
        <Text style={styles.body}>{t('oral.createHelp')}</Text>
        <View style={styles.grid}>
          <SelectField label={t('smart.subject')} value={subject} options={SUBJECTS.map((value) => ({ value, label: value }))} onChange={(value) => { setSubject(value); setExerciseType(oralExercises(oralFamily(value))[0]); }} />
          {subject === 'Other' ? <Field accessibilityLabel={t('smart.customSubject')} placeholder={t('smart.customSubject')} value={customSubject} onChangeText={setCustomSubject} /> : null}
          <Field accessibilityLabel={t('smart.topic')} placeholder={t('smart.topic')} value={topic} onChangeText={setTopic} maxLength={180} />
          <SelectField label={t('smart.stage')} value={stage} options={STAGES.map((value) => ({ value, label: value }))} onChange={setStage} />
          <SelectField label={t('smart.level')} value={level} options={LEVELS.map((value) => ({ value, label: value }))} onChange={setLevel} />
          <SelectField label={t('oral.exerciseType')} value={selectedExercise} options={options.map((value) => ({ value, label: oralExerciseLabel(value, language) }))} onChange={setExerciseType} />
          <Field accessibilityLabel={t('oral.objective')} placeholder={t('oral.objective')} value={objective} onChangeText={setObjective} maxLength={500} />
          <Field accessibilityLabel={t('oral.maxDuration')} placeholder={t('oral.maxDuration')} value={limit} onChangeText={setLimit} keyboardType="number-pad" />
          <SelectField label={t('oral.studentLanguage')} value={studentLanguage} options={LANGUAGES.map((value) => ({ value, label: t(`language.${value}`) }))} onChange={(value) => setStudentLanguage(value as typeof studentLanguage)} />
          <SelectField label={t('oral.teacherLanguage')} value={teacherLanguage} options={LANGUAGES.map((value) => ({ value, label: t(`language.${value}`) }))} onChange={(value) => setTeacherLanguage(value as typeof teacherLanguage)} />
          <SelectField label={t('smart.generationMode')} value={mode} options={[{ value: 'ai', label: 'AI' }, { value: 'template', label: t('oral.template') }]} onChange={setMode} />
          <SelectField label={t('resources.visibility')} value={visibility} options={[{ value: 'private', label: t('resources.private') }, { value: 'public', label: t('resources.public') }]} onChange={setVisibility} />
        </View>
        <Field accessibilityLabel={t('oral.additionalInstructions')} placeholder={t('oral.additionalInstructions')} value={instructions} onChangeText={setInstructions} multiline maxLength={1000} />
        {mode === 'template' && !oralTemplateAvailable(selectedExercise) ? <Text style={styles.warning}>{t('oral.templateUnavailable')}</Text> : null}
        {message === t('oral.similarFound') ? <Button secondary onPress={() => { setReuseConfirmed(true); setMessage(''); }}>{t('smart.reuseConfirmYes')}</Button> : null}
        <Button disabled={busy || validation} onPress={() => void create()}>{busy ? t('smart.generating') : t('oral.generate')}</Button>
        <ActionFeedback message={message} tone="error" onDismiss={() => setMessage('')} />
      </Panel>
      {document ? <Panel style={styles.stack}>
        <Text style={styles.title}>{document.title}</Text>
        <Text style={styles.body}>{document.student_instructions}</Text>
        {document.stimulus ? <Text style={styles.stimulus}>{document.stimulus}</Text> : null}
        <Text style={styles.body}>{document.expected_response}</Text>
        <Text style={styles.heading}>{t('oral.rubric')}</Text>
        {document.rubric.map((criterion) => <Text key={criterion.id} style={styles.body}>{criterion.label} · {criterion.max_score}</Text>)}
        <ResourceEditor document={generated!.document} onApply={(next) => void edit(next)} />
        {savedId ? <Button onPress={() => router.push({ pathname: '/resources', params: { kind: 'oral_presentation', scope: 'mine', resourceId: savedId, assign: '1' } })}>{t('resources.assignToStudent')}</Button> : <Button disabled={busy} onPress={() => void save()}>{t('smart.saveLibrary')}</Button>}
      </Panel> : null}
    </ScrollView>
  </AppShell>;
}

const styles = StyleSheet.create({ stack: { gap: 16, paddingBottom: 24 }, grid: { gap: 12 }, title: { fontSize: 22, color: colors.ink, fontWeight: '900' }, heading: { fontSize: 16, color: colors.ink, fontWeight: '800' }, body: { color: colors.ink, lineHeight: 22 }, stimulus: { color: colors.ink, backgroundColor: colors.surfaceSoft, padding: 16, borderRadius: 12 }, warning: { color: colors.danger } });
