import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Disclosure, Field, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { addVideoResource, getVideoProgramLink, getVideoProgramOptions, updateVideoResource, youtubeVideoId, type VideoProgramOption } from '@/services/resource-library';
import { canonicalSubjectLabel } from '@/lib/subjects';
import { learnerStageLabel } from '@/lib/learner-stages';
import { colors } from '@/theme';

const SUBJECTS = ['English', 'Spanish', 'Turkish', 'Mathematics', 'Science', 'Music', 'Study Skills', 'Other'];
const STAGES = ['Early primary', 'Upper primary', 'Lower secondary', 'Upper secondary', 'Adult'];
const LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const LANGUAGES = ['English', 'Spanish', 'Turkish'];
const stageKey = (value: string) => value.toLowerCase().replaceAll(' ', '_').replace(/^adult$/, 'adult_stage');
const levelKey = (value: string) => ['Beginner', 'Intermediate', 'Advanced'].includes(value) ? `${value.toLowerCase()}_band` : value;
const languageKey = (value: string) => ({ English: 'en', Spanish: 'es', Turkish: 'tr' } as Record<string, string>)[value] || value.toLowerCase();
const stageValue = (value: string) => STAGES.find((item) => stageKey(item) === stageKey(value)) || 'Adult';
const levelValue = (value: string) => LEVELS.find((item) => levelKey(item) === value) || 'Intermediate';
const languageValue = (value: string) => LANGUAGES.find((item) => languageKey(item) === value.toLowerCase()) || 'English';
const levelLabel = (value: string, t: (key: string) => string) => t(`smart.option.${levelKey(value).replace('_band', '').toLowerCase()}`);

export function AddVideoResource({ onSaved }: { onSaved: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const [url, setUrl] = useState(''); const [title, setTitle] = useState(''); const [description, setDescription] = useState('');
  const [subject, setSubject] = useState('English'); const [customSubject, setCustomSubject] = useState(''); const [topic, setTopic] = useState('');
  const [stage, setStage] = useState('Adult'); const [level, setLevel] = useState('A1'); const [language, setLanguage] = useState('English');
  const [isPublic, setIsPublic] = useState(false); const [saving, setSaving] = useState(false); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  const [programs, setPrograms] = useState<VideoProgramOption[]>([]); const [programId, setProgramId] = useState(''); const [topicId, setTopicId] = useState('');
  const options = (values: string[]) => values.map((value) => ({ value, label: value === 'English' || value === 'Spanish' || value === 'Turkish' || value === 'Mathematics' || value === 'Science' || value === 'Music' || value === 'Study Skills' || value === 'Other' ? canonicalSubjectLabel(value, t) : STAGES.includes(value) ? learnerStageLabel(stageKey(value), t) : levelLabel(value, t) }));
  useEffect(() => { void getVideoProgramOptions().then(setPrograms).catch(() => setPrograms([])); }, []);
  const selectedProgram = useMemo(() => programs.find((item) => item.id === programId), [programId, programs]);
  const selectedTopic = selectedProgram?.topics.find((item) => item.id === topicId);
  const chooseProgram = (value: string) => { if (selectedTopic && title === selectedTopic.title) setTitle(''); setProgramId(value); setTopicId(''); const program = programs.find((item) => item.id === value); if (program) { setSubject(SUBJECTS.find((candidate) => candidate.toLowerCase().replaceAll(' ', '_') === program.subject.toLowerCase().replaceAll(' ', '_')) || 'Other'); setCustomSubject(program.customSubject); setStage(stageValue(program.learnerStage)); setLevel(levelValue(program.level)); setLanguage(languageValue(program.language)); setTopic(''); } };
  const chooseTopic = (value: string) => { const previousTitle = selectedTopic?.title; setTopicId(value); const item = selectedProgram?.topics.find((candidate) => candidate.id === value); if (item) { setTopic(item.title); setTitle((current) => !current.trim() || current === previousTitle ? item.title : current); } };
  const save = async () => { setSaving(true); setMessage(''); try { await addVideoResource({ youtubeUrl: url, title, description, subject, customSubject, topic, learnerStage: stageKey(stage), level: levelKey(level), language: languageKey(language), isPublic, programId: programId || undefined, topicId: topicId || undefined }); setUrl(''); setTitle(''); setDescription(''); setTopic(''); setProgramId(''); setTopicId(''); await onSaved(); setMessageTone('success'); setMessage(t('resources.videoSaved')); } catch (reason) { const key = reason instanceof Error ? reason.message : ''; setMessageTone('error'); setMessage(key.startsWith('resources.') ? t(key) : t('resources.videoSaveFailed')); } finally { setSaving(false); } };
  const valid = Boolean(youtubeVideoId(url)) && (!programId || Boolean(selectedTopic)) && (subject !== 'Other' || Boolean(customSubject.trim()));
  return <Disclosure title={t('resources.addVideo')} summary={t('resources.addVideoSummary')} style={styles.wrap}>

    <View style={styles.fields}>
      <View style={styles.full}><Text style={styles.label}>{t('resources.youtubeLink')}</Text><Field autoCapitalize="none" value={url} onChangeText={setUrl} placeholder="https://youtube.com/watch?v=…" />{url.trim() && !youtubeVideoId(url) ? <Text style={styles.error}>{t('resources.videoInvalidUrl')}</Text> : null}</View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.subject')}</Text>{selectedTopic ? <Field editable={false} value={selectedProgram?.subject === 'other' ? selectedProgram.customSubject : canonicalSubjectLabel(selectedProgram?.subject || subject, t)} /> : <SelectField label={t('resources.subject')} value={subject} options={options(SUBJECTS)} onChange={(value) => { setSubject(value); setProgramId(''); setTopicId(''); setLevel(value === 'English' || value === 'Spanish' || value === 'Turkish' ? 'A1' : 'Intermediate'); }} />}</View>
      {subject === 'Other' && !selectedTopic ? <View style={styles.cell}><Text style={styles.label}>{t('resources.customSubject')}</Text><Field value={customSubject} onChangeText={setCustomSubject} /></View> : null}
      <View style={styles.cell}><Text style={styles.label}>{t('resources.learningProgram')}</Text><SelectField label={t('resources.learningProgram')} value={programId} options={[{ value: '', label: t('resources.noProgram') }, ...programs.filter((item) => !subject || (item.subject === 'other' ? item.customSubject : item.subject).toLowerCase().replaceAll('_', ' ') === (subject === 'Other' ? customSubject : subject).toLowerCase().replaceAll('_', ' ')).map((item) => ({ value: item.id, label: item.title }))]} onChange={chooseProgram} /></View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.programTopic')}</Text><SelectField label={t('resources.programTopic')} value={topicId} options={[{ value: '', label: t('resources.noTopic') }, ...(selectedProgram?.topics || []).map((item) => ({ value: item.id, label: item.title, detail: `${item.unitNumber}.${item.topicNumber}` }))]} onChange={chooseTopic} /></View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.videoTitle')}</Text><Field value={title} onChangeText={setTitle} /></View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.topic')}</Text><Field editable={!selectedTopic} value={topic} onChangeText={setTopic} /></View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.stage')}</Text>{selectedTopic ? <Field editable={false} value={learnerStageLabel(stageKey(stage), t)} /> : <SelectField label={t('resources.stage')} value={stage} options={options(STAGES)} onChange={setStage} />}</View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.level')}</Text>{selectedTopic ? <Field editable={false} value={level} /> : <SelectField label={t('resources.level')} value={level} options={options(subject === 'English' || subject === 'Spanish' || subject === 'Turkish' ? LEVELS.slice(3) : LEVELS.slice(0, 3))} onChange={setLevel} />}</View>
      <View style={styles.cell}><Text style={styles.label}>{t('resources.videoLanguage')}</Text><SelectField label={t('resources.videoLanguage')} value={language} options={options(LANGUAGES)} onChange={setLanguage} /></View>
      <View style={styles.full}><Text style={styles.label}>{t('resources.videoDescription')}</Text><Field multiline numberOfLines={3} value={description} onChangeText={setDescription} style={styles.description} /></View>
    </View>
    {selectedTopic ? <Text style={styles.hint}>{t('resources.videoLinkedFieldsLocked')}</Text> : null}
    <View style={styles.actions}><Button secondary={isPublic} onPress={() => setIsPublic(false)}>{t('resources.private')}</Button><Button secondary={!isPublic} onPress={() => setIsPublic(true)}>{t('resources.public')}</Button><Button disabled={saving || !valid} onPress={() => void save()}>{saving ? t('common.saving') : t('resources.saveVideo')}</Button></View><ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} />
  </Disclosure>;
}

export function EditVideoResource({ id, detail, onSaved }: { id: string; detail: Record<string, unknown>; onSaved: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const [url, setUrl] = useState(String(detail.youtube_url || '')); const [title, setTitle] = useState(String(detail.title || '')); const [description, setDescription] = useState(String(detail.description || ''));
  const [topic, setTopic] = useState(String(detail.topic || '')); const [subject, setSubject] = useState(SUBJECTS.find((item) => item.toLowerCase().replaceAll(' ', '_') === String(detail.subject || '').toLowerCase()) || 'Other'); const [customSubject, setCustomSubject] = useState(String(detail.custom_subject_name || '')); const [stage, setStage] = useState(String(detail.learner_stage || '')); const [level, setLevel] = useState(String(detail.level_or_band || ''));
  const [language, setLanguage] = useState(String(detail.student_material_language || 'en')); const [isPublic, setIsPublic] = useState(Boolean(detail.is_public));
  const [linked, setLinked] = useState<Awaited<ReturnType<typeof getVideoProgramLink>>>(null); const [saving, setSaving] = useState(false); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  useEffect(() => { let active = true; void getVideoProgramLink(id).then((value) => { if (active) setLinked(value); }).catch(() => { if (active) { setMessageTone('error'); setMessage(t('resources.videoLinkLookupFailed')); } }); return () => { active = false; }; }, [id, t]);
  const save = async () => { setSaving(true); setMessage(''); try { await updateVideoResource(id, { youtubeUrl: url, title, description, topic, subject, customSubject, learnerStage: stage, level, language, isPublic }); await onSaved(); setMessageTone('success'); setMessage(t('resources.metadataSaved')); } catch (reason) { const key = reason instanceof Error ? reason.message : ''; setMessageTone('error'); setMessage(key.startsWith('resources.') ? t(key) : t('resources.videoSaveFailed')); } finally { setSaving(false); } };
  return <View style={styles.edit}>

    {linked ? <Text style={styles.hint}>{t('resources.videoLinkedFieldsLocked')} · {linked.program.title} · {linked.topic.title}</Text> : null}
    <Text style={styles.label}>{t('resources.youtubeLink')}</Text><Field autoCapitalize="none" value={url} onChangeText={setUrl} />{url.trim() && !youtubeVideoId(url) ? <Text style={styles.error}>{t('resources.videoInvalidUrl')}</Text> : null}
    <Text style={styles.label}>{t('resources.videoTitle')}</Text><Field value={title} onChangeText={setTitle} />
    <Text style={styles.label}>{t('resources.subject')}</Text>{linked ? <Field editable={false} value={linked.program.subject === 'other' ? linked.program.customSubject : canonicalSubjectLabel(linked.program.subject, t)} /> : <SelectField label={t('resources.subject')} value={subject} options={SUBJECTS.map((item) => ({ value: item, label: canonicalSubjectLabel(item, t) }))} onChange={(value) => { setSubject(value); setLevel(value === 'English' || value === 'Spanish' || value === 'Turkish' ? 'A1' : 'intermediate_band'); }} />}{subject === 'Other' && !linked ? <><Text style={styles.label}>{t('resources.customSubject')}</Text><Field value={customSubject} onChangeText={setCustomSubject} /></> : null}
    <Text style={styles.label}>{t('resources.topic')}</Text><Field editable={!linked} value={linked?.topic.title || topic} onChangeText={setTopic} />
    <Text style={styles.label}>{t('resources.stage')}</Text>{linked ? <Field editable={false} value={learnerStageLabel(linked.program.learnerStage, t)} /> : <SelectField label={t('resources.stage')} value={stage} options={STAGES.map((item) => ({ value: stageKey(item), label: learnerStageLabel(stageKey(item), t) }))} onChange={setStage} />}
    <Text style={styles.label}>{t('resources.level')}</Text>{linked ? <Field editable={false} value={levelLabel(levelValue(linked.program.level), t)} /> : <SelectField label={t('resources.level')} value={level} options={(subject.toLowerCase() === 'english' || subject.toLowerCase() === 'spanish' || subject.toLowerCase() === 'turkish' ? LEVELS.slice(3) : LEVELS.slice(0, 3)).map((item) => ({ value: levelKey(item), label: levelLabel(item, t) }))} onChange={setLevel} />}
    <Text style={styles.label}>{t('resources.videoLanguage')}</Text><SelectField label={t('resources.videoLanguage')} value={language} options={LANGUAGES.map((item) => ({ value: languageKey(item), label: canonicalSubjectLabel(item, t) }))} onChange={setLanguage} />
    <Text style={styles.label}>{t('resources.videoDescription')}</Text><Field multiline numberOfLines={3} value={description} onChangeText={setDescription} style={styles.description} />
    <View style={styles.actions}><Button secondary={isPublic} onPress={() => setIsPublic(false)}>{t('resources.private')}</Button><Button secondary={!isPublic} onPress={() => setIsPublic(true)}>{t('resources.public')}</Button><Button disabled={saving || !youtubeVideoId(url) || !title.trim() || (subject === 'Other' && !customSubject.trim())} onPress={() => void save()}>{saving ? t('common.saving') : t('resources.saveMetadata')}</Button></View><ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} />
  </View>;
}

const styles = StyleSheet.create({ wrap: { marginTop: 12, marginBottom: 4 }, edit: { gap: 8 }, fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, cell: { flex: 1, minWidth: 210 }, full: { width: '100%' }, label: { color: colors.ink, fontSize: 10, fontWeight: '800', marginBottom: 5 }, description: { minHeight: 82, paddingTop: 12, textAlignVertical: 'top' }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 }, message: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 10, padding: 10, fontSize: 11, fontWeight: '700', marginBottom: 10 }, hint: { color: colors.primary, backgroundColor: colors.primarySoft, padding: 10, borderRadius: 9, fontSize: 11 }, error: { color: colors.danger, fontSize: 11 } });
