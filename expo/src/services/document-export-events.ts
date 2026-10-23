import { requireSupabase } from '@/lib/supabase';

export type DocumentKind = 'lesson_plan' | 'worksheet' | 'exam' | 'cv' | 'cover_letter' | 'student_report' | 'student_history' | 'dashboard_report' | 'other';
export type ExportVariant = 'full' | 'student' | 'teacher' | 'answers';

async function sendExportEvent(token: string, payload: Record<string, unknown>): Promise<void> {
  const response = await fetch('/api/document-export-event', { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error('Document export could not be recorded. Try again.');
}

/** Records signed-in file preparation and browser handoff, never a completed download. */
export async function recordedDocumentExport(format: 'pdf' | 'docx', documentKind: DocumentKind, variant: ExportVariant, prepareAndHandoff: () => Promise<void>): Promise<void> {
  const { data, error } = await requireSupabase().auth.getSession();
  // Public resource downloads remain available to visitors, with no billable user or event.
  if (error || !data.session) { await prepareAndHandoff(); return; }
  const eventId = crypto.randomUUID();
  const token = data.session.access_token;
  await sendExportEvent(token, { action: 'start', eventId, format, documentKind, variant });
  try {
    await prepareAndHandoff();
  } catch (reason) {
    await sendExportEvent(token, { action: 'finish', eventId, status: 'failed', errorKind: reason instanceof Error ? reason.name : 'unknown_error' });
    throw reason;
  }
  await sendExportEvent(token, { action: 'finish', eventId, status: 'handoff_requested' });
}
