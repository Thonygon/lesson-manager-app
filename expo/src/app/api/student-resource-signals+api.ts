import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to view student progress.' }, 401);
  const body = await request.json().catch(() => null) as { studentId?: unknown } | null;
  const studentId = typeof body?.studentId === 'string' ? body.studentId.trim() : '';
  if (!/^[0-9a-f-]{36}$/i.test(studentId)) return json({ error: 'Choose a valid student.' }, 400);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'Student resource signals are unavailable.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your Classio session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: link, error: linkError } = await server.from('teacher_student_links').select('id').eq('teacher_id', identity.user.id).eq('student_id', studentId).eq('status', 'active').limit(1);
    if (linkError) throw linkError;
    if (!link?.length) return json({ error: 'This student connection is unavailable.' }, 403);
    const { data: sessions, error: sessionError } = await server.from('practice_sessions').select('id,source_type,source_id').eq('user_id', studentId).eq('status', 'completed').in('source_type', ['worksheet', 'exam', 'video']).order('completed_at', { ascending: false }).limit(500);
    if (sessionError) throw sessionError;
    const ids = (sessions || []).map((row) => Number(row.id)).filter((id) => Number.isSafeInteger(id) && id > 0);
    const assignedIds = new Set<number>();
    for (let offset = 0; offset < ids.length; offset += 100) {
      const { data: attempts, error: attemptError } = await server.from('teacher_assignment_attempts').select('practice_session_id').eq('student_id', studentId).in('practice_session_id', ids.slice(offset, offset + 100));
      if (attemptError) throw attemptError;
      attempts?.forEach((row) => assignedIds.add(Number(row.practice_session_id)));
    }
    const completed = [...new Set((sessions || []).filter((row) => !assignedIds.has(Number(row.id)) && row.source_id).map((row) => `${row.source_type}:${row.source_id}`))].map((key) => { const [kind, id] = key.split(':'); return { kind, id }; });
    return json({ completed });
  } catch (error) {
    console.error('Student resource signals lookup failed', error);
    return json({ error: 'Student resource signals could not be loaded.' }, 503);
  }
}
