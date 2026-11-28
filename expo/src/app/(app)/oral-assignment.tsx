/* eslint-disable react-hooks/set-state-in-effect -- the async assignment fetch populates server state after mount */
import { useCallback, useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams, type Href } from 'expo-router';
import { AccessibilityInfo, Animated, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AudioModule, RecordingPresets, createAudioPlayer, setAudioModeAsync, useAudioRecorder } from 'expo-audio';
import { Image } from 'expo-image';
import * as DocumentPicker from 'expo-document-picker';
import { AppShell } from '@/components/app-shell';
import { BackLink } from '@/components/back-link';
import { Button, Field, LoadingState, Panel } from '@/components/ui';
import { requireSupabase } from '@/lib/supabase';
import { oralAudioExpiresSoon } from '@/lib/oral-audio-expiry';
import { PRIVACY_NOTICE_VERSION, privacyNoticeUrl } from '@/lib/privacy-notices';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import { oralExerciseLabel, type OralDocument } from '@/shared/oral-presentation';
import { oralAudioBytes, oralDocumentFromSnapshot, oralPlaybackUrl, requestNewOralAttempt, reviewOralAttempt, submitOralAudio, type OralRecording } from '@/services/oral-presentations';

type Row = Record<string, unknown>;
type DraftAudio = { uri: string; mime: string; duration: number; bytes?: ArrayBuffer };
type Attempt = { id: number; attempt_number: number; status: string; score_pct: number | null; teacher_feedback: string; submission_payload: Record<string, unknown>; submitted_at: string | null };

function PlaybackControls({ active, playing, seconds, playLabel, pauseLabel, replayLabel, onToggle, onReplay }: { active: boolean; playing: boolean; seconds: number; playLabel: string; pauseLabel: string; replayLabel: string; onToggle: () => void; onReplay: () => void }) {
  return <View style={styles.audioControls}><Pressable accessibilityRole="button" accessibilityLabel={active && playing ? pauseLabel : playLabel} onPress={onToggle} style={styles.audioButton}><Text style={styles.audioGlyph}>{active && playing ? 'Ⅱ' : '▶'}</Text></Pressable><Pressable accessibilityRole="button" accessibilityLabel={replayLabel} onPress={onReplay} style={styles.audioButton}><Text style={styles.audioGlyph}>↺</Text></Pressable>{active ? <Text style={styles.meta}>{Math.floor(seconds / 60)}:{String(Math.floor(seconds % 60)).padStart(2, '0')}</Text> : null}</View>;
}

function RecordingWaveform({ wave, reduceMotion, label }: { wave: Animated.Value; reduceMotion: boolean; label: string }) {
  return <View accessible accessibilityRole="text" accessibilityLabel={label} style={styles.waveform}>{Array.from({ length: 27 }, (_, index) => <Animated.View key={index} style={[styles.waveBar, { height: 10 + ((index * 17) % 31), transform: [{ scaleY: reduceMotion ? 1 : wave.interpolate({ inputRange: [0, 1], outputRange: [index % 3 === 0 ? 0.55 : 1, index % 3 === 0 ? 1.4 : 0.6] }) }] }]} />)}</View>;
}

export default function OralAssignmentScreen() {
  const { assignmentId, from, returnTo } = useLocalSearchParams<{ assignmentId?: string; from?: string; returnTo?: string }>();
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
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSeconds, setPlaybackSeconds] = useState(0);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [wave] = useState(() => new Animated.Value(0));
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
  useEffect(() => { void AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion); const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion); return () => subscription.remove(); }, []);
  useEffect(() => { if (!recording) { setRecordingSeconds(0); return; } const timer = setInterval(() => setRecordingSeconds(Math.floor((Date.now() - startedAt.current) / 1000)), 500); return () => clearInterval(timer); }, [recording]);
  useEffect(() => { if (!recording || reduceMotion) { wave.stopAnimation(); wave.setValue(0); return; } const animation = Animated.loop(Animated.sequence([Animated.timing(wave, { toValue: 1, duration: 420, useNativeDriver: true }), Animated.timing(wave, { toValue: 0, duration: 420, useNativeDriver: true })])); animation.start(); return () => animation.stop(); }, [recording, reduceMotion, wave]);
  const latest = attempts.find((item) => item.status !== 'abandoned');

  function discardDraft() {
    player.current?.remove();
    player.current = null; setPlayingId(''); setIsPlaying(false); setPlaybackSeconds(0);
    if (draftObjectUrl.current) URL.revokeObjectURL(draftObjectUrl.current);
    draftObjectUrl.current = null;
    setDraft(null);
  }

  async function startRecording() {
    if (!document) return;
    try {
      setError(''); setMessage('');
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) throw new Error(t('oral.permissionDenied'));
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record(); discardDraft(); startedAt.current = Date.now(); setRecording(true);
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
    player.current?.remove(); const next = createAudioPlayer(uri); player.current = next;
    next.addListener('playbackStatusUpdate', (status) => { if (player.current !== next) return; setIsPlaying(status.playing); setPlaybackSeconds(status.currentTime); });
    next.play(); setPlayingId(key); setIsPlaying(true); setPlaybackSeconds(0);
  }
  function togglePlayback() { if (!player.current) return; if (player.current.playing) player.current.pause(); else if (player.current.currentStatus.didJustFinish) { void replay(); return; } else player.current.play(); setIsPlaying(player.current.playing); }
  async function replay() { if (!player.current) return; await player.current.seekTo(0); player.current.play(); setIsPlaying(true); setPlaybackSeconds(0); }
  async function playSubmitted(attemptId: number, fromStart = false) {
    try { const key = String(attemptId); if (playingId === key && player.current) { if (fromStart) await replay(); else togglePlayback(); return; } const uri = await oralPlaybackUrl(key); if (!uri) throw new Error(t('oral.expired')); play(uri, key); }
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
  const backDestination = teacher
    ? ['/dashboard', '/students', '/assignments', '/lessons', '/payments', '/calendar', '/resources', '/smart-tools', '/analytics', '/community', '/profile', '/help', '/admin', '/admin-accounts', '/admin-operations', '/admin-business', '/developer-workspace'].includes(from || '') ? from! : '/assignments'
    : ['/student-home', '/student-practice', '/student-study-plan', '/student-assignments', '/student-find-teacher', '/profile', '/help'].includes(from || '') ? from! : returnTo === 'student-study-plan' ? '/student-study-plan' : '/student-assignments';
  return <AppShell title={t('oral.title')} eyebrow={t('oral.eyebrow')}>
    <BackLink label={t('oral.back')} onPress={() => router.replace(backDestination as Href)} />
    {loading ? <LoadingState /> : error && !document ? <Panel><Text style={styles.error}>{error}</Text><Button secondary onPress={() => router.back()}>{t('common.close')}</Button></Panel> : document ? <ScrollView contentContainerStyle={styles.stack}>
      <Panel style={styles.activityCard}><View style={styles.activityHeading}><View style={styles.activityIcon}><Text style={styles.activityIconText}>🎙</Text></View><View style={styles.activityTitleBlock}><Text style={styles.eyebrow}>{t('oral.eyebrow')}</Text><Text style={styles.title}>{document.title}</Text><Text style={styles.meta}>{oralExerciseLabel(document.exercise_type, language)} · {document.subject} · {document.topic} · {document.max_duration_seconds} s</Text></View></View><View style={styles.instructionsCard}><Text style={styles.heading}>{t('oral.teacherInstructions')}</Text><Text style={styles.body}>{document.student_instructions}</Text>{document.picture?.image_data_url ? <Image source={{ uri: document.picture.image_data_url }} style={{ width: '100%', aspectRatio: 16 / 9, borderRadius: 12 }} contentFit="contain" /> : null}{document.stimulus ? <Text style={styles.stimulus}>{document.stimulus}</Text> : null}<Text style={styles.body}>{document.expected_response}</Text></View><Text style={styles.meta}>{document.success_criteria.join(' · ')}</Text></Panel>
      {teacher ? <>{attempts.filter((item) => item.status !== 'abandoned').map((attempt) => { const recordingRow = recordings.find((item) => item.attempt_id === attempt.id); const expired = !recordingRow || Boolean(recordingRow.deleted_at) || Boolean(recordingRow.expires_at && Date.parse(recordingRow.expires_at) <= loadedAt); const result = attempt.submission_payload || {}; const rubricScores = result.rubric_scores && typeof result.rubric_scores === 'object' ? result.rubric_scores as Record<string, number> : {}; return <Panel key={attempt.id} style={styles.stack}><Text style={styles.heading}>{t('oral.attempt')} {attempt.attempt_number} · {t(`oral.status.${attempt.status}`)}</Text><Text style={styles.meta}>{attempt.submitted_at ? new Date(attempt.submitted_at).toLocaleString() : ''}</Text>{expired ? <Text style={styles.meta}>{t('oral.expired')}</Text> : <PlaybackControls active={playingId === String(attempt.id)} playing={isPlaying} seconds={playbackSeconds} playLabel={t('oral.play')} pauseLabel={t('oral.pause')} replayLabel={t('oral.playAgain')} onToggle={() => void playSubmitted(attempt.id)} onReplay={() => void playSubmitted(attempt.id, true)} />}{recordingRow?.expires_at && attempt.status === 'submitted' ? <Text style={styles.meta}>{t('oral.expiresOn')}: {new Date(recordingRow.expires_at).toLocaleDateString()}</Text> : null}{attempt.status === 'submitted' && !expired && recordingRow?.expires_at && oralAudioExpiresSoon(recordingRow.expires_at, loadedAt) ? <Text style={styles.warning}>{t('oral.expiresSoon')}</Text> : null}{attempt.status === 'submitted' && !expired ? <>{document.rubric.map((criterion) => <View key={criterion.id} style={styles.criterion}><Text style={styles.body}>{criterion.label} / {criterion.max_score}</Text><Field keyboardType="decimal-pad" value={scores[criterion.id] || ''} onChangeText={(value) => setScores((current) => ({ ...current, [criterion.id]: value }))} placeholder="0" /></View>)}<Field multiline numberOfLines={4} value={feedback} onChangeText={setFeedback} placeholder={t('oral.feedback')} /><Button disabled={busy} onPress={() => void grade(attempt.id)}>{t('oral.publishReview')}</Button></> : attempt.status === 'graded' ? <><Text style={styles.heading}>{attempt.score_pct}%</Text>{document.rubric.map((criterion) => <Text key={criterion.id} style={styles.body}>{criterion.label}: {rubricScores[criterion.id] ?? '—'} / {criterion.max_score}</Text>)}{attempt.teacher_feedback ? <Text style={styles.body}>{attempt.teacher_feedback}</Text> : null}</> : null}</Panel>; })}{row?.status === 'graded' ? <Button secondary disabled={busy} onPress={() => void retry()}>{t('oral.requestNewAttempt')}</Button> : null}</> : <>
        {latest?.status === 'graded' ? <Panel style={styles.reviewCard}><View style={styles.reviewHeading}><Text style={styles.reviewCheck}>✓</Text><Text style={styles.heading}>{t('oral.reviewed')} · {latest.score_pct}%</Text></View>{latest.teacher_feedback ? <Text style={styles.body}>{latest.teacher_feedback}</Text> : null}<View style={styles.rubricGrid}>{document.rubric.map((criterion) => { const rubric = latest.submission_payload?.rubric_scores as Record<string, number> | undefined; return <View key={criterion.id} style={styles.rubricCell}><Text style={styles.meta}>{criterion.label}</Text><Text style={styles.rubricScore}>{rubric?.[criterion.id] ?? '—'} / {criterion.max_score}</Text></View>; })}</View>{(() => { const recordingRow = recordings.find((item) => item.attempt_id === latest.id); return !recordingRow || recordingRow.deleted_at || (recordingRow.expires_at && Date.parse(recordingRow.expires_at) <= loadedAt) ? <Text style={styles.meta}>{t('oral.expired')}</Text> : <PlaybackControls active={playingId === String(latest.id)} playing={isPlaying} seconds={playbackSeconds} playLabel={t('oral.play')} pauseLabel={t('oral.pause')} replayLabel={t('oral.playAgain')} onToggle={() => void playSubmitted(latest.id)} onReplay={() => void playSubmitted(latest.id, true)} />; })()}</Panel> : null}
        {row?.status === 'submitted' ? <Panel><Text style={styles.body}>{t('oral.awaitingReview')}</Text></Panel> : ['assigned', 'started'].includes(String(row?.status)) ? <Panel style={styles.recordCard}><View style={styles.recordHeading}><View style={styles.recordIcon}><Text style={styles.recordIconText}>🎙</Text></View><View><Text style={styles.heading}>{t('oral.recordAnswer')}</Text><Text style={styles.meta}>{t('oral.audioLimit', { seconds: document.max_duration_seconds })}</Text></View></View><Text style={styles.body}>{t('oral.audioNotice')}</Text><Pressable accessibilityRole="link" onPress={() => void Linking.openURL(privacyNoticeUrl(language, 'students'))}><Text style={styles.link}>{t('oral.readNotice')}</Text></Pressable><Pressable accessibilityRole="checkbox" accessibilityState={{ checked: acknowledged }} onPress={() => setAcknowledged((current) => !current)}><Text style={styles.body}>{acknowledged ? '☑' : '☐'} {t('oral.acknowledge')}</Text></Pressable>{recording ? <View style={styles.recordingActive}><Text style={styles.recordingLabel}>● {t('oral.recordingNow')} · {Math.floor(recordingSeconds / 60)}:{String(recordingSeconds % 60).padStart(2, '0')}</Text><RecordingWaveform wave={wave} reduceMotion={reduceMotion} label={`${t('oral.recordingNow')} ${recordingSeconds} ${t('oral.seconds')}`} /><Button onPress={() => void stopRecording()}>■ {t('oral.stop')}</Button></View> : <Button disabled={busy || !acknowledged} onPress={() => void startRecording()}>🎙 {t(draft ? 'oral.recordAgain' : 'oral.record')}</Button>}{Platform.OS === 'web' && !recording ? <Button secondary disabled={!acknowledged} onPress={() => void pickAudio()}>{t('oral.uploadFile')}</Button> : null}{draft ? <View style={styles.draftPanel}><Text style={styles.heading}>♪ {t('oral.draftReady')}</Text><Text style={styles.meta}>{draft.duration} / {document.max_duration_seconds} s</Text><View style={styles.durationTrack}><View style={[styles.durationFill, { width: `${Math.min(100, draft.duration / document.max_duration_seconds * 100)}%` }]} /></View><PlaybackControls active={playingId === 'draft'} playing={isPlaying} seconds={playbackSeconds} playLabel={t('oral.preview')} pauseLabel={t('oral.pause')} replayLabel={t('oral.playAgain')} onToggle={() => playingId === 'draft' ? togglePlayback() : play(draft.uri, 'draft')} onReplay={() => playingId === 'draft' ? void replay() : play(draft.uri, 'draft')} /><Pressable accessibilityRole="button" accessibilityLabel={t('oral.discard')} onPress={discardDraft} style={styles.discardButton}><Text style={styles.discardGlyph}>🗑</Text><Text style={styles.discardText}>{t('oral.discard')}</Text></Pressable><Button disabled={busy || !acknowledged} onPress={() => void submit()}>{busy ? t('common.saving') : t('oral.submit')}</Button></View> : null}</Panel> : null}
        {attempts.filter((item) => item.status === 'graded' && item.id !== latest?.id).map((item) => <Panel key={item.id}><Text style={styles.body}>{t('oral.attempt')} {item.attempt_number} · {item.score_pct}%</Text></Panel>)}
      </>}
      {message ? <Text style={styles.success}>{message}</Text> : null}{error ? <Text style={styles.error}>{error.startsWith('oral.') ? t(error) : error}</Text> : null}
    </ScrollView> : null}
  </AppShell>;
}

const styles = StyleSheet.create({ stack: { gap: 14, paddingBottom: 20 }, activityCard: { gap: 16, borderColor: colors.lineStrong }, activityHeading: { flexDirection: 'row', alignItems: 'center', gap: 14 }, activityIcon: { width: 54, height: 54, borderRadius: 16, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' }, activityIconText: { fontSize: 27, color: colors.primary }, activityTitleBlock: { flex: 1, gap: 4 }, eyebrow: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1.1 }, instructionsCard: { gap: 9, padding: 16, borderRadius: 14, backgroundColor: colors.surfaceSoft }, recordCard: { gap: 16, borderColor: colors.primary }, recordHeading: { flexDirection: 'row', alignItems: 'center', gap: 12 }, recordIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' }, recordIconText: { fontSize: 22 }, draftPanel: { gap: 12, borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 14, padding: 16, backgroundColor: colors.surfaceSoft }, durationTrack: { height: 7, borderRadius: 7, backgroundColor: colors.lineStrong, overflow: 'hidden' }, durationFill: { height: 7, borderRadius: 7, backgroundColor: colors.primary }, recordingActive: { gap: 12 }, recordingLabel: { color: colors.danger, fontSize: 14, fontWeight: '800' }, waveform: { minHeight: 64, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 3, paddingHorizontal: 8, borderRadius: 12, backgroundColor: colors.primarySoft }, waveBar: { width: 4, borderRadius: 4, backgroundColor: colors.primary }, audioControls: { flexDirection: 'row', alignItems: 'center', gap: 10 }, audioButton: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surfaceSoft }, audioButtonDisabled: { opacity: 0.45 }, audioGlyph: { color: colors.primary, fontSize: 20, fontWeight: '800' }, discardButton: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', padding: 8 }, discardGlyph: { color: colors.danger, fontSize: 22, fontWeight: '800' }, discardText: { color: colors.danger, fontSize: 13, fontWeight: '700' }, reviewCard: { gap: 14, borderColor: colors.success }, reviewHeading: { flexDirection: 'row', alignItems: 'center', gap: 10 }, reviewCheck: { color: colors.success, fontSize: 18, fontWeight: '900' }, rubricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, rubricCell: { minWidth: 130, flexGrow: 1, flexBasis: '45%', padding: 12, borderRadius: 12, backgroundColor: colors.surfaceSoft, gap: 5 }, rubricScore: { color: colors.ink, fontWeight: '900', fontSize: 18 }, title: { color: colors.ink, fontSize: 24, fontWeight: '900' }, heading: { color: colors.ink, fontSize: 17, fontWeight: '800' }, body: { color: colors.ink, fontSize: 14, lineHeight: 22 }, meta: { color: colors.muted, fontSize: 12, lineHeight: 18 }, link: { color: colors.primary, fontWeight: '800', textDecorationLine: 'underline' }, stimulus: { color: colors.ink, backgroundColor: colors.surface, padding: 16, borderRadius: 12, lineHeight: 22 }, criterion: { gap: 5 }, error: { color: colors.danger, fontSize: 13 }, success: { color: colors.success, fontSize: 13 }, warning: { color: colors.danger, fontSize: 13, fontWeight: '700' } });
