import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store' } });
const kinds = new Set(['lesson_plan', 'worksheet', 'exam', 'cv', 'cover_letter', 'student_report', 'student_history', 'dashboard_report', 'other']);
const variants = new Set(['full', 'student', 'teacher', 'answers']);
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to export a document.' }, 401);
  let body: Record<string, unknown>;
  try { body = await request.json(); } catch { return json({ error: 'Invalid export event.' }, 400); }
  if (!body || typeof body !== 'object' || !uuid(body.eventId)) return json({ error: 'Invalid export event.' }, 400);
  const action = body.action;
  if (action !== 'start' && action !== 'finish') return json({ error: 'Invalid export action.' }, 400);
  if (action === 'start' && (body.format !== 'pdf' && body.format !== 'docx' || !kinds.has(String(body.documentKind)) || !variants.has(String(body.variant)))) return json({ error: 'Invalid export metadata.' }, 400);
  if (action === 'finish' && body.status !== 'handoff_requested' && body.status !== 'failed') return json({ error: 'Invalid export status.' }, 400);
  const base = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!base || !publicKey || !serverKey) return json({ error: 'Export recording is not configured.' }, 503);
  try {
    const publicClient = createClient(base, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(base, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    if (action === 'start') {
      const { error } = await server.from('classio_document_export_events').insert({ event_id: body.eventId, actor_user_id: identity.user.id, source: 'expo', format: body.format, document_kind: body.documentKind, variant: body.variant, status: 'started' });
      if (error) throw error;
      return json({ eventId: body.eventId }, 201);
    }
    const errorKind = body.status === 'failed' && typeof body.errorKind === 'string' ? body.errorKind.replace(/[^a-z0-9_]/gi, '_').slice(0, 80) : null;
    const { data, error } = await server.from('classio_document_export_events').update({ status: body.status, finished_at: new Date().toISOString(), error_kind: errorKind }).eq('event_id', body.eventId).eq('actor_user_id', identity.user.id).eq('source', 'expo').eq('status', 'started').select('event_id');
    if (error) throw error;
    if (data?.length !== 1) return json({ error: 'Export event was not found or already finished.' }, 409);
    return json({ eventId: body.eventId });
  } catch (error) {
    console.error('Document export event failed', error instanceof Error ? error.message : 'unknown error');
    return json({ error: 'Export event could not be recorded.' }, 503);
  }
}
