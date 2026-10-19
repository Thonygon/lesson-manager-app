import { useEffect, useMemo, useState } from 'react';
import { router } from 'expo-router';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Disclosure, EditIconButton, Field } from '@/components/ui';
import { requireSupabase } from '@/lib/supabase';
import { canonicalSubjectLabel } from '@/lib/subjects';
import { programTopics } from '@/lib/learning-program-topics';
import { useAppPreferences } from '@/providers/app-preferences';
import { saveLearningProgramUnit } from '@/services/resource-library';
import { colors } from '@/theme';

type Row = Record<string, unknown>;
type Video = { id: string; title: string; url: string; topicId: string };
const str = (value: unknown) => String(value ?? '').trim();
const list = (value: unknown): string[] => Array.isArray(value) ? value.map(str).filter(Boolean) : [];
const number = (value: unknown, fallback: number) => Number(value) || fallback;

function useProgramTerms() {
  const { t } = useAppPreferences();
  const value = (raw: string) => { const code = raw.toLowerCase().replace(/[ -]+/g, '_'); for (const key of [`resources.term.${code}`, `student.exercise.${code}`]) { const found = t(key); if (found !== key) return found; } return raw.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()); };
  return { t, value };
}

function DetailList({ title, values, subtle = false }: { title: string; values: string[]; subtle?: boolean }) {
  const { value } = useProgramTerms();
  if (!values.length) return null;
  return <View style={styles.detailList}><Text style={[styles.detailLabel, subtle && styles.subtle]}>{title}</Text>{values.map((item, index) => <Text key={`${item}-${index}`} style={subtle ? styles.subtle : styles.detailText}>{values.length > 1 ? '• ' : ''}{value(item)}</Text>)}</View>;
}

function UnitEditor({ programId, unit, topics, onSaved, onCancel }: { programId: string; unit: Row; topics: Row[]; onSaved: () => void; onCancel: () => void }) {
  const { t } = useProgramTerms();
  const [title, setTitle] = useState(str(unit.title));
  const [overview, setOverview] = useState(str(unit.overview));
  const [objectives, setObjectives] = useState(list(unit.unit_objectives).join('\n'));
  const [deliveryNotes, setDeliveryNotes] = useState(list(unit.delivery_notes).join('\n'));
  const [topicFields, setTopicFields] = useState(() => topics.map((topic) => ({ id: str(topic.id), title: str(topic.title), subtopic: str(topic.subtopic), studentSummary: str(topic.student_summary) })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const updateTopic = (index: number, key: 'title' | 'subtopic' | 'studentSummary', value: string) => setTopicFields((current) => current.map((topic, position) => position === index ? { ...topic, [key]: value } : topic));
  const save = async () => { setBusy(true); setError(''); try { await saveLearningProgramUnit(programId, str(unit.id), { title, overview, unitObjectives: objectives.split('\n').map((line) => line.trim()).filter(Boolean), deliveryNotes: deliveryNotes.split('\n').map((line) => line.trim()).filter(Boolean), topicChanges: topicFields }); onSaved(); } catch (reason) { setError(reason instanceof Error ? reason.message : t('programView.saveFailed')); } finally { setBusy(false); } };
  return <View style={styles.editor}><Text style={styles.heading}>{t('programView.editUnit')}</Text><Text style={styles.detailLabel}>{t('programView.unitTitle')}</Text><Field value={title} onChangeText={setTitle} /><Text style={styles.detailLabel}>{t('programView.overview')}</Text><Field value={overview} onChangeText={setOverview} multiline style={styles.multiline} /><Text style={styles.detailLabel}>{t('resources.term.unit_objectives')}</Text><Field value={objectives} onChangeText={setObjectives} multiline style={styles.multiline} /><Text style={styles.detailLabel}>{t('programView.deliveryNotes')}</Text><Field value={deliveryNotes} onChangeText={setDeliveryNotes} multiline style={styles.multiline} />
    {topicFields.map((topic, index) => <View key={topic.id} style={styles.topicEditor}><Text style={styles.detailLabel}>{t('resources.topicNumber', { number: index + 1 })}</Text><Field value={topic.title} onChangeText={(value) => updateTopic(index, 'title', value)} placeholder={t('programView.topicTitle')} /><Field value={topic.subtopic} onChangeText={(value) => updateTopic(index, 'subtopic', value)} placeholder={t('resources.term.subtopic')} /><Field value={topic.studentSummary} onChangeText={(value) => updateTopic(index, 'studentSummary', value)} placeholder={t('resources.term.student_summary')} multiline style={styles.multiline} /></View>)}
    {error ? <Text style={styles.error}>{error}</Text> : null}<View style={styles.actions}><Button disabled={busy || !title.trim()} onPress={() => void save()}>{busy ? t('common.saving') : t('programView.saveUnit')}</Button><Button secondary onPress={onCancel}>{t('common.cancel')}</Button></View>
  </View>;
}

export function LearningProgramView({ programId, detail, owner = false, onSaved }: { programId: string; detail: Row; owner?: boolean; onSaved?: (detail: Row) => void }) {
  const { t } = useProgramTerms();
  const [videos, setVideos] = useState<Video[]>([]);
  const [editingUnit, setEditingUnit] = useState('');
  const sourceUnits = useMemo(() => { const document = detail.program_data && typeof detail.program_data === 'object' ? detail.program_data as Row : {}; return Array.isArray(document.units) ? document.units as Row[] : []; }, [detail.program_data]);
  const units = useMemo(() => (Array.isArray(detail.units) ? detail.units as Row[] : sourceUnits).map((unit, index) => ({ ...sourceUnits.find((source, sourceIndex) => number(source.unit_number, sourceIndex + 1) === number(unit.unit_number, index + 1)), ...unit })), [detail.units, sourceUnits]);
  const topics = useMemo<Row[]>(() => programTopics(detail, Array.isArray(detail.topics) ? detail.topics as Row[] : []), [detail]);
  useEffect(() => { let active = true; const load = async () => {
    if (!programId || !topics.length) return;
    if (!owner) { try { const response = await fetch(`/api/program-topic-videos?programId=${encodeURIComponent(programId)}`); const result = await response.json() as { videos?: Video[] }; if (active && response.ok) setVideos(result.videos || []); } catch { /* Optional videos do not block the program. */ } return; }
    const client = requireSupabase();
    const { data: links, error: linkError } = await client.from('learning_program_topic_videos').select('topic_id,video_id').eq('program_id', programId).limit(300);
    if (linkError || !links?.length) return;
    const ids = [...new Set(links.map((link) => Number(link.video_id)).filter((id) => id > 0))];
    let request = client.from('videos').select('id,title,youtube_url,video_id,status,is_public').in('id', ids).neq('status', 'archived');
    const { data: rows, error } = await request;
    if (error || !active) return;
    const lookup = new Map((rows ?? []).map((row) => [Number(row.id), row]));
    setVideos(links.flatMap((link) => { const video = lookup.get(Number(link.video_id)); if (!video) return []; const url = str(video.youtube_url) || (video.video_id ? `https://www.youtube.com/watch?v=${video.video_id}` : ''); return [{ id: str(video.id), title: str(video.title), url, topicId: str(link.topic_id) }]; }));
  }; void load(); return () => { active = false; }; }, [owner, programId, topics]);
  const openTool = (kind: 'plan' | 'worksheet' | 'exam', topic: Row) => { if (!owner) return; router.push({ pathname: '/smart-tools', params: { tool: kind, programId, programTopicId: str(topic.id), subject: canonicalSubjectLabel(detail.subject), customSubject: str(detail.custom_subject_name), topic: str(topic.title), stage: str(detail.learner_stage), level: str(detail.level_or_band) } }); };
  return <View style={styles.root}>
    {detail.program_overview ? <View style={styles.overview}><Text style={styles.heading}>{t('resources.programOverview')}</Text><Text style={styles.body}>{str(detail.program_overview)}</Text></View> : null}
    <Text style={styles.sectionTitle}>{t('resources.programStructure')}</Text>
    {units.map((unit, index) => { const unitNumber = number(unit.unit_number, index + 1); const unitTopics = topics.filter((topic) => number(topic.unit_number, 0) === unitNumber); const currentVideos = videos; return <View key={str(unit.id) || String(unitNumber)} style={styles.unitBlock}>
      <View style={styles.unitHeader}><View style={styles.unitHeading}><Text style={styles.unitTitle}>{t('resources.unit')} {unitNumber}: {str(unit.title)}</Text>{unit.overview ? <Text style={styles.body}>{str(unit.overview)}</Text> : null}</View>{owner && unit.id ? <EditIconButton accessibilityLabel={t('programView.editUnit')} onPress={() => setEditingUnit((current) => current === str(unit.id) ? '' : str(unit.id))} /> : null}</View>
      {editingUnit === str(unit.id) ? <UnitEditor key={str(unit.id)} programId={programId} unit={unit} topics={unitTopics} onCancel={() => setEditingUnit('')} onSaved={async () => { setEditingUnit(''); const client = requireSupabase(); const [unitRows, topicRows, programRow] = await Promise.all([client.from('learning_program_units').select('*').eq('program_id', programId).order('unit_number'), client.from('learning_program_topics').select('*').eq('program_id', programId).order('unit_number').order('topic_number'), client.from('learning_programs').select('program_data').eq('id', programId).maybeSingle()]); if (!unitRows.error && !topicRows.error && !programRow.error) onSaved?.({ ...detail, program_data: programRow.data?.program_data, units: unitRows.data || [], topics: topicRows.data || [] }); }} /> : null}
      <Disclosure title={`${t('resources.unit')} ${unitNumber}: ${str(unit.title)}`} summary={t('resources.topicCount', { count: unitTopics.length })} defaultOpen={index === 0} style={styles.disclosure} titleStyle={{ color: colors.primary }}>
        <DetailList title={t('resources.term.unit_objectives')} values={list(unit.unit_objectives)} />
        <DetailList title={t('resources.term.recommended_lesson_purposes')} values={list(unit.recommended_lesson_purposes)} subtle />
        <DetailList title={t('resources.term.recommended_worksheet_types')} values={list(unit.recommended_worksheet_types)} subtle />
        <DetailList title={t('resources.term.recommended_exam_exercise_types')} values={list(unit.recommended_exam_exercise_types)} subtle />
        <DetailList title={t('programView.complementaryActivities')} values={list(unit.recommended_non_classio_activities)} subtle />
        <DetailList title={t('programView.deliveryNotes')} values={list(unit.delivery_notes)} />
        {unitTopics.map((topic, topicIndex) => <View key={str(topic.id) || String(topicIndex)} style={styles.topic}><Text style={styles.topicTitle}>{t('resources.topicNumber', { number: number(topic.topic_number, topicIndex + 1) })}: {str(topic.title)}</Text>{topic.subtopic ? <Text style={styles.subtle}>{str(topic.subtopic)}</Text> : null}{topic.student_summary ? <Text style={styles.body}>{str(topic.student_summary)}</Text> : null}
          <DetailList title={t('resources.term.learning_objectives')} values={list(topic.learning_objectives)} /><DetailList title={t('resources.term.success_criteria')} values={list(topic.success_criteria)} /><DetailList title={t('resources.term.suggested_worksheet_types')} values={list(topic.suggested_worksheet_types)} subtle /><DetailList title={t('resources.term.suggested_exam_exercise_types')} values={list(topic.suggested_exam_exercise_types)} subtle /><DetailList title={t('programView.complementaryActivities')} values={list(topic.suggested_non_classio_activities)} subtle />
          {owner && topic.id ? <View style={styles.toolArea}><Text style={styles.subtle}>{t('programView.createAligned')}</Text><View style={styles.actions}><Button secondary onPress={() => openTool('plan', topic)}>{t('programView.plan')}</Button><Button secondary onPress={() => openTool('worksheet', topic)}>{t('programView.worksheet')}</Button><Button secondary onPress={() => openTool('exam', topic)}>{t('programView.exam')}</Button></View></View> : null}
          {programId ? <Disclosure title={t('programView.topicVideos')} summary={t('programView.videoCount', { count: currentVideos.filter((video) => video.topicId === str(topic.id)).length })} style={styles.videoDisclosure}>{currentVideos.filter((video) => video.topicId === str(topic.id)).length ? currentVideos.filter((video) => video.topicId === str(topic.id)).map((video) => <Pressable key={video.id} accessibilityRole="link" onPress={() => { if (video.url) void Linking.openURL(video.url); }} style={styles.videoRow}><Text style={styles.videoTitle}>🎬 {video.title}</Text><Text style={styles.videoArrow}>↗</Text></Pressable>) : <Text style={styles.subtle}>{t('programView.noVideos')}</Text>}</Disclosure> : null}
        </View>)}
      </Disclosure>
    </View>; })}
  </View>;
}

const styles = StyleSheet.create({ root: { gap: 16 }, overview: { padding: 16, borderRadius: 16, backgroundColor: colors.primarySoft, gap: 8 }, heading: { color: colors.ink, fontSize: 17, fontWeight: '900' }, body: { color: colors.inkSecondary, fontSize: 13, lineHeight: 20 }, sectionTitle: { color: colors.ink, fontSize: 18, fontWeight: '900' }, unitBlock: { gap: 10 }, unitHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 }, unitHeading: { flex: 1, gap: 5 }, unitTitle: { color: colors.ink, fontSize: 16, fontWeight: '900' }, disclosure: { marginBottom: 8 }, detailList: { gap: 4, marginBottom: 9 }, detailLabel: { color: colors.ink, fontSize: 12, fontWeight: '800' }, detailText: { color: colors.inkSecondary, fontSize: 12, lineHeight: 19 }, subtle: { color: colors.muted, fontSize: 11, lineHeight: 17 }, topic: { borderWidth: 1, borderColor: colors.line, borderRadius: 12, padding: 13, marginTop: 12, gap: 7 }, topicTitle: { color: colors.ink, fontSize: 13, fontWeight: '900' }, toolArea: { gap: 7, marginTop: 8 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, videoDisclosure: { marginTop: 8 }, videoRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8, paddingVertical: 7 }, videoTitle: { flex: 1, color: colors.primary, fontSize: 12, fontWeight: '800' }, videoArrow: { color: colors.primary }, editor: { padding: 14, borderWidth: 1, borderColor: colors.line, borderRadius: 14, gap: 8 }, multiline: { minHeight: 75, textAlignVertical: 'top' }, topicEditor: { gap: 7, paddingTop: 8, borderTopWidth: 1, borderTopColor: colors.line }, error: { color: colors.danger, fontSize: 12 } });
