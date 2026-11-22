import { File } from 'expo-file-system';
import { requireSupabase } from '@/lib/supabase';
import { oralDocumentIssues, oralFamily, type OralDocument } from '@/shared/oral-presentation';

export const ORAL_AUDIO_BUCKET = 'classio-oral-audio';
export const ORAL_AUDIO_MAX_BYTES = 15 * 1024 * 1024;
const AUDIO_MIME = new Set(['audio/webm', 'audio/mp4', 'audio/mpeg', 'audio/wav', 'audio/x-m4a']);
export type OralRecording = { id: string; attempt_id: number; status: string; submitted_at: string | null; expires_at: string | null; deleted_at: string | null; duration_seconds: number | null };

export function validateOralAudio(mime: string, bytes: number, duration: number, limit: number): void {
  if (!AUDIO_MIME.has(mime)) throw new Error('oral.invalidFormat');
  if (!Number.isSafeInteger(bytes) || bytes < 1 || bytes > ORAL_AUDIO_MAX_BYTES) throw new Error('oral.invalidSize');
  if (!Number.isSafeInteger(duration) || duration < 1 || duration > Math.min(limit, 600)) throw new Error('oral.invalidDuration');
}

export function matchesAudioSignature(mime: string, bytes: ArrayBuffer): boolean {
  const head = new Uint8Array(bytes, 0, Math.min(bytes.byteLength, 16));
  if (head.length < 12) return false;
  const ascii = (start: number, value: string) => [...value].every((letter, index) => head[start + index] === letter.charCodeAt(0));
  if (mime === 'audio/webm') return head[0] === 0x1a && head[1] === 0x45 && head[2] === 0xdf && head[3] === 0xa3;
  if (mime === 'audio/mp4' || mime === 'audio/x-m4a') return ascii(4, 'ftyp');
  if (mime === 'audio/wav') return ascii(0, 'RIFF') && ascii(8, 'WAVE');
  if (mime === 'audio/mpeg') return ascii(0, 'ID3') || (head[0] === 0xff && (head[1] & 0xe0) === 0xe0);
  return false;
}

export async function oralAudioBytes(uri: string): Promise<ArrayBuffer> {
  if (uri.startsWith('blob:') || uri.startsWith('data:')) {
    const response = await fetch(uri);
    if (!response.ok) throw new Error('oral.audioUnavailable');
    return response.arrayBuffer();
  }
  return new File(uri).arrayBuffer();
}

export async function submitOralAudio(assignmentId: string, mime: string, bytes: ArrayBuffer, duration: number, maxDuration: number, noticeLanguage: 'en' | 'es' | 'tr', noticeVersion: string): Promise<void> {
  validateOralAudio(mime, bytes.byteLength, duration, maxDuration);
  if (!matchesAudioSignature(mime, bytes)) throw new Error('oral.invalidFormat');
  const client = requireSupabase();
  const { data: started, error: startError } = await client.rpc('classio_begin_oral_submission', { p_assignment_id: Number(assignmentId), p_mime: mime, p_notice_version: noticeVersion, p_notice_language: noticeLanguage, p_acknowledged: true });
  if (startError || !started) throw startError ?? new Error('oral.submitFailed');
  const ticket = started as { path: string; recording_id: string };
  const upload = await client.storage.from(ORAL_AUDIO_BUCKET).upload(ticket.path, bytes, { contentType: mime, upsert: false });
  if (upload.error && !/already exists|duplicate/i.test(upload.error.message)) throw upload.error;
  const { error } = await client.rpc('classio_submit_oral_recording', { p_recording_id: ticket.recording_id, p_duration_seconds: duration });
  if (error) throw error;
}

export async function oralRecordingForAttempt(attemptId: string): Promise<OralRecording | null> {
  const { data, error } = await requireSupabase().from('classio_oral_recordings')
    .select('id,attempt_id,status,submitted_at,expires_at,deleted_at,duration_seconds').eq('attempt_id', attemptId).maybeSingle();
  if (error) throw error;
  return data as OralRecording | null;
}

export async function oralPlaybackUrl(attemptId: string): Promise<string | null> {
  const client = requireSupabase();
  const { data: row, error } = await client.from('classio_oral_recordings').select('object_path,expires_at,deleted_at,status').eq('attempt_id', attemptId).maybeSingle();
  if (error) throw error;
  if (!row || row.deleted_at || !['submitted', 'cleanup_failed'].includes(row.status) || !row.expires_at || Date.parse(row.expires_at) <= Date.now()) return null;
  const remainingSeconds = Math.floor((Date.parse(row.expires_at) - Date.now()) / 1000);
  if (remainingSeconds < 1) return null;
  const signed = await client.storage.from(ORAL_AUDIO_BUCKET).createSignedUrl(row.object_path, Math.min(60, remainingSeconds));
  if (signed.error) throw signed.error;
  return signed.data?.signedUrl || null;
}

export async function reviewOralAttempt(attemptId: string, scores: Record<string, number>, feedback: string): Promise<number> {
  const { data, error } = await requireSupabase().rpc('classio_review_oral_submission', { p_attempt_id: Number(attemptId), p_scores: scores, p_feedback: feedback });
  if (error) throw error;
  return Number((data as { score_pct?: number } | null)?.score_pct || 0);
}

export async function requestNewOralAttempt(assignmentId: string): Promise<void> {
  const { error } = await requireSupabase().rpc('classio_retry_oral_assignment', { p_assignment_id: Number(assignmentId) });
  if (error) throw error;
}

export function oralDocumentFromSnapshot(snapshot: unknown): OralDocument | null {
  const row = snapshot && typeof snapshot === 'object' ? snapshot as Record<string, unknown> : {};
  const raw = row.oral_data;
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const document = raw as Record<string, unknown>;
  const issues = oralDocumentIssues(document, oralFamily(String(document.subject || '')), String(document.exercise_type || ''));
  return issues.length ? null : document as OralDocument;
}
