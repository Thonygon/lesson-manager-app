/* eslint-disable react-hooks/set-state-in-effect -- the async assignment fetch populates server state after mount */
import { useCallback, useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Linking, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AudioModule, RecordingPresets, createAudioPlayer, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import * as DocumentPicker from 'expo-document-picker';
import { AppShell } from '@/components/app-shell';
import { Button, Field, LoadingState, Panel } from '@/components/ui';
import { requireSupabase } from '@/lib/supabase';
import { oralAudioExpiresSoon } from '@/lib/oral-audio-expiry';
import { PRIVACY_NOTICE_VERSION, privacyNoticeUrl } from '@/lib/privacy-notices';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import type { OralDocument } from '@/shared/oral-presentation';
import { oralAudioBytes, oralDocumentFromSnapshot, oralPlaybackUrl, requestNewOralAttempt, reviewOralAttempt, submitOralAudio, type OralRecording } from '@/services/oral-presentations';

type Row = Record<string, unknown>;
type DraftAudio = { uri: string; mime: string; duration: number; bytes?: ArrayBuffer };
type Attempt = { id: number; attempt_number: number; status: string; score_pct: number | null; teacher_feedback: string; submission_payload: Record<string, unknown>; submitted_at: string | null };

export default function OralAssignmentScreen() {
  const { assignmentId } = useLocalSearchParams<{ assignmentId?: string }>();
  const { t, language } = useAppPreferences();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const startedAt = useRef(0);
  const player = useRef<ReturnType<typeof createAudioPlayer> | null>(null);
  const draftObjectUrl = useRef<string | null>(null);
  const [row, setRow] = useState<Row | null>(null);
  const [document, setDocument] = useState<OralDocument | null>(null);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [recordings, setRecordings] = useState<OralRecording[]>([]);
  const [teacher, setTeacher] = useState(false);
  const [draft, setDraft] = useState<DraftAudio | null>(null);
  const [recording, setRecording] = useState(false);
  const [scores, setScores] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [playingId, setPlayingId] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [loadedAt, setLoadedAt] = useState(() => Date.now());

  const load = useCallback(async () => {
    if (!assignmentId || !/^\d+$/.test(assignmentId)) throw new Error(t('oral.unavailable'));
    const client = requireSupabase();
    const { data: auth } = await client.auth.getUser();
    if (!auth.user) throw new Error(t('oral.unavailable'));
    const { data: assignment, error: assignmentError } = await client.from('teacher_assignments').select('id,teacher_id,student_id,assignment_type,title,status,content_snapshot,score_pct,due_at').eq('id', assignmentId).maybeSingle();
    if (assignmentError || !assignment || assignment.assignment_type !== 'oral_presentation') throw assignmentError ?? new Error(t('oral.unavailable'));
    const isTeacher = assignment.teacher_id === auth.user.id;
    if (!isTeacher && assignment.student_id !== auth.user.id) throw new Error(t('oral.unavailable'));
    const parsed = oralDocumentFromSnapshot(assignment.content_snapshot);
    if (!parsed) throw new Error(t('oral.invalidResource'));
    const [attemptResult, recordingResult] = await Promise.all([
      client.from('teacher_assignment_attempts').select('id,attempt_number,status,score_pct,teacher_feedback,submission_payload,submitted_at').eq('assignment_id', assignmentId).order('id', { ascending: false }),
      client.from('classio_oral_recordings').select('id,attempt_id,status,submitted_at,expires_at,deleted_at,duration_seconds').eq('assignment_id', assignmentId),
    ]);
    if (attemptResult.error || recordingResult.error) throw attemptResult.error ?? recordingResult.error;
    setRow(assignment); setDocument(parsed); setTeacher(isTeacher); setAttempts((attemptResult.data || []) as Attempt[]); setRecordings((recordingResult.data || []) as OralRecording[]);
    setLoadedAt(Date.now());
  }, [assignmentId, t]);
  useEffect(() => { let active = true; void load().catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : t('oral.unavailable')); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; player.current?.remove(); if (draftObjectUrl.current) URL.revokeObjectURL(draftObjectUrl.current); draftObjectUrl.current = null; }; }, [load, t]);
  const latest = attempts.find((item) => item.status !== 'abandoned');

  function discardDraft() {
    player.current?.remove();
    if (draftObjectUrl.current) URL.revokeObjectURL(draftObjectUrl.current);
    draftObjectUrl.current = null;
    setDraft(null);
  }

  async function startRecording() {
    if (!document) return;
    try {
      setError(''); setMessage(''); discardDraft();
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) throw new Error(t('oral.permissionDenied'));
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record(); startedAt.current = Date.now(); setRecording(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.recordFailed')); }
  }
  async function stopRecording() {
    try {
      await recorder.stop(); setRecording(false);
      const duration = Math.max(1, Math.ceil((Date.now() - startedAt.current) / 1000));
      if (!recorder.uri) throw new Error(t('oral.recordFailed'));
      if (duration > (document?.max_duration_seconds || 600)) throw new Error(t('oral.invalidDuration'));
      setDraft({ uri: recorder.uri, mime: Platform.OS === 'web' ? 'audio/webm' : 'audio/mp4', duration });
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.recordFailed')); setRecording(false); }
  }
  async function pickAudio() {
    if (Platform.OS !== 'web') return;
    try {
      const result = await DocumentPicker.getDocumentAsync({ type: ['audio/webm', 'audio/mp4', 'audio/mpeg', 'audio/wav'], multiple: false });
      if (result.canceled || !result.assets[0]?.file) return;
      const file = result.assets[0].file;
      const uri = URL.createObjectURL(file);
      try {
        const duration = await new Promise<number>((resolve, reject) => { const audio = new Audio(); audio.preload = 'metadata'; audio.onloadedmetadata = () => { const seconds = Math.ceil(audio.duration); audio.src = ''; resolve(seconds); }; audio.onerror = () => reject(new Error(t('oral.audioUnavailable'))); audio.src = uri; });
        const bytes = await file.arrayBuffer();
        discardDraft(); draftObjectUrl.current = uri;
        setDraft({ uri, mime: file.type, duration, bytes }); setError('');
      } catch (reason) { URL.revokeObjectURL(uri); throw reason; }
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.audioUnavailable')); }
  }
  function play(uri: string, key: string) {
    player.current?.remove(); const next = createAudioPlayer(uri); player.current = next; next.play(); setPlayingId(key);
  }
  async function playSubmitted(attemptId: number) {
    try { const uri = await oralPlaybackUrl(String(attemptId)); if (!uri) throw new Error(t('oral.expired')); play(uri, String(attemptId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.audioUnavailable')); }
  }
  async function submit() {
    if (!row || !document || !draft) return;
    setBusy(true); setError('');
    try {
      const bytes = draft.bytes || await oralAudioBytes(draft.uri);
      if (!acknowledged) throw new Error(t('oral.noticeRequired'));
      await submitOralAudio(String(row.id), draft.mime, bytes, draft.duration, document.max_duration_seconds, language, PRIVACY_NOTICE_VERSION);
      discardDraft(); setMessage(t('oral.submitted')); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.submitFailed')); }
    finally { setBusy(false); }
  }
  async function grade(attemptId: number) {
    if (!document) return;
    setBusy(true); setError('');
    try {
      const values: Record<string, number> = {};
      for (const item of document.rubric) { const value = Number(scores[item.id]); if (scores[item.id] === undefined || !Number.isFinite(value) || value < 0 || value > item.max_score || Math.round(value * 10) !== value * 10) throw new Error(t('oral.scoreInvalid')); values[item.id] = value; }
      await reviewOralAttempt(String(attemptId), values, feedback); setMessage(t('oral.reviewSaved')); setScores({}); setFeedback(''); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.reviewFailed')); }
    finally { setBusy(false); }
  }
  async function retry() {
    if (!row) return; setBusy(true); setError('');
    try { await requestNewOralAttempt(String(row.id)); setMessage(t('oral.newAttemptReady')); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : t('oral.retryFailed')); }
    finally { setBusy(false); }
  }
  return <AppShell title={t('oral.title')} eyebrow={t('oral.eyebrow')}>
    {loading ? <LoadingState /> : error && !document ? <Panel><Text style={styles.error}>{error}</Text><Button secondary onPress={() => router.back()}>{t('common.close')}</Button></Panel> : document ? <ScrollView contentContainerStyle={styles.stack}>
      <Panel style={styles.stack}><Text style={styles.title}>{document.title}</Text><Text style={styles.meta}>{document.subject} · {document.topic} · {document.max_duration_seconds} s</Text><Text style={styles.body}>{document.student_instructions}</Text>{document.stimulus ? <Text style={styles.stimulus}>{document.stimulus}</Text> : null}<Text style={styles.body}>{document.expected_response}</Text><Text style={styles.meta}>{document.success_criteria.join(' · ')}</Text></Panel>
      {teacher ? <>{attempts.filter((item) => item.status !== 'abandoned').map((attempt) => { const recordingRow = recordings.find((item) => item.attempt_id === attempt.id); const expired = !recordingRow || Boolean(recordingRow.deleted_at) || Boolean(recordingRow.expires_at && Date.parse(recordingRow.expires_at) <= loadedAt); const result = attempt.submission_payload || {}; const rubricScores = result.rubric_scores && typeof result.rubric_scores === 'object' ? result.rubric_scores as Record<string, number> : {}; return <Panel key={attempt.id} style={styles.stack}><Text style={styles.heading}>{t('oral.attempt')} {attempt.attempt_number} · {t(`oral.status.${attempt.status}`)}</Text><Text style={styles.meta}>{attempt.submitted_at ? new Date(attempt.submitted_at).toLocaleString() : ''}</Text>{expired ? <Text style={styles.meta}>{t('oral.expired')}</Text> : <Button secondary onPress={() => void playSubmitted(attempt.id)}>{playingId === String(attempt.id) ? t('oral.playAgain') : t('oral.play')}</Button>}{recordingRow?.expires_at && attempt.status === 'submitted' ? <Text style={styles.meta}>{t('oral.expiresOn')}: {new Date(recordingRow.expires_at).toLocaleDateString()}</Text> : null}{attempt.status === 'submitted' && !expired && recordingRow?.expires_at && oralAudioExpiresSoon(recordingRow.expires_at, loadedAt) ? <Text style={styles.warning}>{t('oral.expiresSoon')}</Text> : null}{attempt.status === 'submitted' && !expired ? <>{document.rubric.map((criterion) => <View key={criterion.id} style={styles.criterion}><Text style={styles.body}>{criterion.label} / {criterion.max_score}</Text><Field keyboardType="decimal-pad" value={scores[criterion.id] || ''} onChangeText={(value) => setScores((current) => ({ ...current, [criterion.id]: value }))} placeholder="0" /></View>)}<Field multiline numberOfLines={4} value={feedback} onChangeText={setFeedback} placeholder={t('oral.feedback')} /><Button disabled={busy} onPress={() => void grade(attempt.id)}>{t('oral.publishReview')}</Button></> : attempt.status === 'graded' ? <><Text style={styles.heading}>{attempt.score_pct}%</Text>{document.rubric.map((criterion) => <Text key={criterion.id} style={styles.body}>{criterion.label}: {rubricScores[criterion.id] ?? '—'} / {criterion.max_score}</Text>)}{attempt.teacher_feedback ? <Text style={styles.body}>{attempt.teacher_feedback}</Text> : null}</> : null}</Panel>; })}{row?.status === 'graded' ? <Button secondary disabled={busy} onPress={() => void retry()}>{t('oral.requestNewAttempt')}</Button> : null}</> : <>
        {latest?.status === 'graded' ? <Panel style={styles.stack}><Text style={styles.heading}>{t('oral.reviewed')} · {latest.score_pct}%</Text>{document.rubric.map((criterion) => { const rubric = latest.submission_payload?.rubric_scores as Record<string, number> | undefined; return <Text key={criterion.id} style={styles.body}>{criterion.label}: {rubric?.[criterion.id] ?? '—'} / {criterion.max_score}</Text>; })}{latest.teacher_feedback ? <Text style={styles.body}>{latest.teacher_feedback}</Text> : null}{(() => { const recordingRow = recordings.find((item) => item.attempt_id === latest.id); return !recordingRow || recordingRow.deleted_at || (recordingRow.expires_at && Date.parse(recordingRow.expires_at) <= loadedAt) ? <Text style={styles.meta}>{t('oral.expired')}</Text> : <Button secondary onPress={() => void playSubmitted(latest.id)}>{t('oral.play')}</Button>; })()}</Panel> : null}
        {row?.status === 'submitted' ? <Panel><Text style={styles.body}>{t('oral.awaitingReview')}</Text></Panel> : ['assigned', 'started'].includes(String(row?.status)) ? <Panel style={styles.stack}><Text style={styles.heading}>{t('oral.recordAnswer')}</Text><Text style={styles.body}>{t('oral.audioNotice')}</Text><Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacyNoticeUrl(language, 'students'))}><Text style={styles.link}>{t('oral.readNotice')}</Text></Pressable><Pressable accessibilityRole="checkbox" accessibilityState={{ checked: acknowledged }} onPress={() => setAcknowledged((current) => !current)}><Text style={styles.body}>{acknowledged ? '☑' : '☐'} {t('oral.acknowledge')}</Text></Pressable><Text style={styles.meta}>{t('oral.audioLimit', { seconds: document.max_duration_seconds })}</Text>{recording ? <Button onPress={() => void stopRecording()}>{t('oral.stop')}</Button> : <Button disabled={busy || !acknowledged} onPress={() => void startRecording()}>{t('oral.record')}</Button>}{Platform.OS === 'web' && !recording ? <Button secondary disabled={!acknowledged} onPress={() => void pickAudio()}>{t('oral.uploadFile')}</Button> : null}{draft ? <View style={styles.stack}><Text style={styles.meta}>{t('oral.draftReady')} · {draft.duration} s</Text><Button secondary onPress={() => play(draft.uri, 'draft')}>{t('oral.preview')}</Button><Button secondary onPress={discardDraft}>{t('oral.discard')}</Button><Button disabled={busy || !acknowledged} onPress={() => void submit()}>{busy ? t('common.saving') : t('oral.submit')}</Button></View> : null}</Panel> : null}
        {attempts.filter((item) => item.status === 'graded' && item.id !== latest?.id).map((item) => <Panel key={item.id}><Text style={styles.body}>{t('oral.attempt')} {item.attempt_number} · {item.score_pct}%</Text></Panel>)}
      </>}
      {message ? <Text style={styles.success}>{message}</Text> : null}{error ? <Text style={styles.error}>{error.startsWith('oral.') ? t(error) : error}</Text> : null}
    </ScrollView> : null}
  </AppShell>;
}

const styles = StyleSheet.create({ stack: { gap: 14, paddingBottom: 20 }, title: { color: colors.ink, fontSize: 24, fontWeight: '900' }, heading: { color: colors.ink, fontSize: 17, fontWeight: '800' }, body: { color: colors.ink, fontSize: 14, lineHeight: 22 }, meta: { color: colors.muted, fontSize: 12, lineHeight: 18 }, link: { color: colors.primary, fontWeight: '800', textDecorationLine: 'underline' }, stimulus: { color: colors.ink, backgroundColor: colors.surfaceSoft, padding: 16, borderRadius: 12, lineHeight: 22 }, criterion: { gap: 5 }, error: { color: colors.danger, fontSize: 13 }, success: { color: colors.success, fontSize: 13 }, warning: { color: colors.danger, fontSize: 13, fontWeight: '700' } });
