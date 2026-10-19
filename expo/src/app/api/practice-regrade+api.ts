import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { exerciseDataForMaterial, gradePractice, materialFromAssignment, materialFromSession, type PracticeMaterial } from '@/services/student-practice';
import { aggregatePracticeProgress, practiceAccuracyPct } from '@/services/student-practice-progress';

const headers = { 'Cache-Control': 'private, no-store', Vary: 'Authorization' };
const json = (body: unknown, status = 200) => Response.json(body, { status, headers });
const row = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const resourceTable = { worksheet: 'worksheets', exam: 'quick_exams' } as const;
const RESOURCE_REPAIR_BATCH = 2;
const REGRADE_VERSION = 3;

function assignmentSnapshot(value: unknown, depth = 0): unknown {
  if (depth > 6) return undefined;
  if (typeof value === 'string') return value.startsWith('data:') ? undefined : value;
  if (Array.isArray(value)) return value.map((item) => assignmentSnapshot(item, depth + 1)).filter((item) => item !== undefined);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(row(value)).flatMap(([key, item]) => {
    if (/base64|image_data|thumbnail/i.test(key)) return [];
    const safe = assignmentSnapshot(item, depth + 1);
    return safe === undefined ? [] : [[key, safe]];
  }));
  return value;
}

async function syncAssignmentCopies(server: SupabaseClient, kind: 'worksheet' | 'exam', id: string, teacherId: string, assignmentIds: string[]) {
  if (!assignmentIds.length) return;
  const fields = kind === 'worksheet' ? 'title,topic,learner_stage,level_or_band,worksheet_json' : 'title,topic,learner_stage,level,exam_data,answer_key';
  const { data, error } = await server.from(resourceTable[kind]).select(fields).eq('id', id).eq('user_id', teacherId).maybeSingle();
  if (error) throw error;
  if (!data) throw new Error('The edited resource is unavailable.');
  const source = row(data);
  const content = kind === 'worksheet' ? { worksheet_json: assignmentSnapshot(source.worksheet_json) } : { exam_data: assignmentSnapshot(source.exam_data), answer_key: assignmentSnapshot(source.answer_key) };
  const snapshot = { ...content, meta: { learner_stage: source.learner_stage, level_or_band: source.level_or_band || source.level } };
  const { error: syncError } = await server.from('teacher_assignments').update({ title: String(source.title || ''), topic: String(source.topic || ''), content_snapshot: snapshot, updated_at: new Date().toISOString() }).eq('teacher_id', teacherId).eq('assignment_type', kind).eq('source_record_id', id);
  if (syncError) throw syncError;
}

async function sourceMaterial(server: SupabaseClient, kind: 'worksheet' | 'exam', id: string, assignment?: Record<string, unknown>): Promise<PracticeMaterial | null> {
  const columns = kind === 'worksheet' ? 'id,user_id,worksheet_json' : 'id,user_id,exam_data,answer_key';
  const { data, error } = await server.from(resourceTable[kind]).select(columns).eq('id', id).maybeSingle();
  if (error) throw error;
  if (!data) return null;
  const source = row(data);
  const snapshot = kind === 'worksheet' ? { worksheet: source.worksheet_json } : { exam_data: source.exam_data, answer_key: source.answer_key };
  return materialFromAssignment({ ...assignment, assignment_type: kind, source_record_id: id, title: row(kind === 'worksheet' ? source.worksheet_json : source.exam_data).title || assignment?.title, content_snapshot: snapshot });
}

async function repairSession(server: SupabaseClient, session: Record<string, unknown>, current: PracticeMaterial | null, assignment?: Record<string, unknown>): Promise<boolean> {
  const sessionId = Number(session.id);
  const userId = String(session.user_id || '');
  if (!Number.isSafeInteger(sessionId) || !userId || session.status !== 'completed') return false;
  const { data: answerData, error: answerError } = await server.from('practice_answers').select('id,exercise_idx,question_idx,exercise_type,student_answer,correct_answer,is_correct,answered_at').eq('session_id', sessionId).eq('user_id', userId);
  if (answerError) throw answerError;
  const saved = (answerData || []).map(row);
  if (!saved.length || !saved.some((answer) => String(answer.student_answer || '').trim())) return false;
  const material = current || materialFromSession(session);
  if (!material?.questions.length) return false;
  const savedByQuestion = new Map(saved.map((answer) => [`${answer.exercise_idx}:${answer.question_idx}`, answer]));
  const answers = Object.fromEntries(material.questions.map((question, index) => [String(index), String(savedByQuestion.get(`${question.exerciseIndex}:${question.questionIndex}`)?.student_answer || '')]));
  const graded = gradePractice(material, answers);
  const refreshedData = current ? exerciseDataForMaterial({ ...material, assignmentId: String(assignment?.id || material.assignmentId || '') }) : session.exercise_data;
  const changed = graded.score !== Number(session.score_pct || 0) || graded.correct !== Number(session.correct_count || 0) || graded.total !== Number(session.total_questions || 0) || graded.rows.some((question) => { const old = savedByQuestion.get(`${question.exerciseIndex}:${question.questionIndex}`); return !old || old.is_correct !== question.isCorrect || String(old.correct_answer || '') !== question.answer || String(old.exercise_type || '') !== question.exerciseType; }) || Boolean(current && JSON.stringify(row(session.exercise_data).exercises || []) !== JSON.stringify(row(refreshedData).exercises || []));
  if (!changed) {
    if (row(session.exercise_data).regrade_version !== REGRADE_VERSION) {
      const { error } = await server.from('practice_sessions').update({ exercise_data: { ...row(session.exercise_data), regrade_version: REGRADE_VERSION } }).eq('id', sessionId).eq('user_id', userId);
      if (error) throw error;
    }
    return false;
  }
  const { data: reviewed, error: reviewedError } = await server.from('teacher_review_requests').select('id').eq('practice_session_id', sessionId).eq('status', 'reviewed').limit(1);
  if (reviewedError) throw reviewedError;
  const manuallyReviewed = Boolean(reviewed?.length);
  const updatedAnswers: { id: unknown; exerciseType: string; answer: string; isCorrect: boolean }[] = [];
  const insertedAnswers: Record<string, unknown>[] = [];
  for (const question of graded.rows) {
    const old = savedByQuestion.get(`${question.exerciseIndex}:${question.questionIndex}`);
    if (old) {
      updatedAnswers.push({ id: old.id, exerciseType: question.exerciseType, answer: question.answer, isCorrect: manuallyReviewed ? old.is_correct === true : question.isCorrect });
    } else {
      insertedAnswers.push({ session_id: sessionId, user_id: userId, exercise_idx: question.exerciseIndex, question_idx: question.questionIndex, exercise_type: question.exerciseType, student_answer: '', correct_answer: question.answer, is_correct: false });
    }
  }
  // practice_answers.id is GENERATED ALWAYS. PostgREST upsert attempts an
  // INSERT with that id and PostgreSQL rejects it (428C9). Update rows by id
  // instead, with bounded concurrency to avoid a burst against Supabase.
  for (let start = 0; start < updatedAnswers.length; start += 4) {
    const results = await Promise.all(updatedAnswers.slice(start, start + 4).map((answer) => server.from('practice_answers').update({ exercise_type: answer.exerciseType, correct_answer: answer.answer, is_correct: answer.isCorrect }).eq('id', answer.id).eq('user_id', userId)));
    for (const result of results) if (result.error) throw result.error;
  }
  if (manuallyReviewed) {
    // Teacher feedback and its manual score remain authoritative, while the
    // student review receives the corrected resource and expected answers.
    const { error } = await server.from('practice_sessions').update({ exercise_data: { ...row(refreshedData), regrade_version: REGRADE_VERSION } }).eq('id', sessionId).eq('user_id', userId);
    if (error) throw error;
    return true;
  }
  if (insertedAnswers.length) {
    const { error } = await server.from('practice_answers').insert(insertedAnswers);
    if (error) throw error;
  }
  const validKeys = new Set(graded.rows.map((question) => `${question.exerciseIndex}:${question.questionIndex}`));
  const removedIds = saved.filter((old) => !validKeys.has(`${old.exercise_idx}:${old.question_idx}`)).map((old) => old.id);
  if (removedIds.length) {
    const { error } = await server.from('practice_answers').delete().in('id', removedIds).eq('user_id', userId);
    if (error) throw error;
  }
  const exerciseData = { ...row(refreshedData), regrade_version: REGRADE_VERSION };
  const { error: sessionError } = await server.from('practice_sessions').update({ exercise_data: exerciseData, total_questions: graded.total, correct_count: graded.correct, score_pct: graded.score, xp_earned: graded.xp, best_streak: graded.bestStreak }).eq('id', sessionId).eq('user_id', userId);
  if (sessionError) throw sessionError;
  const oldProgress = new Map(aggregatePracticeProgress(saved.map((answer) => ({ exerciseType: String(answer.exercise_type || ''), isCorrect: answer.is_correct === true })), Number(session.xp_earned || 0)).map((group) => [group.exerciseType, group]));
  const newProgress = new Map(aggregatePracticeProgress(graded.rows, graded.xp).map((group) => [group.exerciseType, group]));
  const changesByType = new Map<string, { attempted: number; correct: number; xp: number }>();
  for (const type of new Set([...oldProgress.keys(), ...newProgress.keys()])) {
    const before = oldProgress.get(type); const after = newProgress.get(type);
    changesByType.set(type, { attempted: Number(after?.attempted || 0) - Number(before?.attempted || 0), correct: Number(after?.correct || 0) - Number(before?.correct || 0), xp: Number(after?.xp || 0) - Number(before?.xp || 0) });
  }
  for (const [exerciseType, change] of changesByType) {
    if (!change.attempted && !change.correct && !change.xp) continue;
    const scopeKey = assignment ? `assignment:${assignment.id}` : 'independent';
    const { data: progress, error: progressError } = await server.from('practice_progress').select('id,total_attempted,total_correct,total_xp').eq('user_id', userId).eq('scope_key', scopeKey).eq('source_type', material.sourceType).eq('subject', session.subject || '').eq('topic', session.topic || '').eq('exercise_type', exerciseType).eq('level', session.level || '').maybeSingle();
    if (progressError) throw progressError;
    if (progress) {
      const attempted = Math.max(0, Number(progress.total_attempted || 0) + change.attempted);
      const correct = Math.max(0, Math.min(attempted, Number(progress.total_correct || 0) + change.correct));
      const { error } = await server.from('practice_progress').update({ total_attempted: attempted, total_correct: correct, accuracy_pct: practiceAccuracyPct(correct, attempted), total_xp: Math.max(0, Number(progress.total_xp || 0) + change.xp) }).eq('id', progress.id).eq('user_id', userId);
      if (error) throw error;
    } else if (newProgress.get(exerciseType)?.attempted) {
      const next = newProgress.get(exerciseType)!;
      const { error } = await server.from('practice_progress').insert({ user_id: userId, scope_key: scopeKey, source_type: material.sourceType, teacher_id: assignment?.teacher_id || null, assignment_id: assignment ? Number(assignment.id) : null, subject: session.subject || '', topic: session.topic || '', exercise_type: exerciseType, level: session.level || '', total_attempted: next.attempted, total_correct: next.correct, accuracy_pct: practiceAccuracyPct(next.correct, next.attempted), total_xp: next.xp, best_streak: graded.bestStreak, last_practiced: session.completed_at || new Date().toISOString() });
      if (error) throw error;
    }
  }
  const { data: attempts, error: attemptError } = await server.from('teacher_assignment_attempts').select('id,assignment_id,submission_payload').eq('practice_session_id', sessionId).eq('student_id', userId);
  if (attemptError) throw attemptError;
  for (const item of attempts || []) {
    const payload = row(item.submission_payload);
    const { error } = await server.from('teacher_assignment_attempts').update({ score_pct: graded.score, total_questions: graded.total, correct_count: graded.correct, submission_payload: { ...payload, result: { ...row(payload.result), total: graded.total, correct: graded.correct, score: graded.score, xp: graded.xp, bestStreak: graded.bestStreak } } }).eq('id', item.id);
    if (error) throw error;
    const { data: latest } = await server.from('teacher_assignment_attempts').select('id').eq('assignment_id', item.assignment_id).order('created_at', { ascending: false }).limit(1);
    if (String(latest?.[0]?.id) === String(item.id)) {
      const { error: assignmentError } = await server.from('teacher_assignments').update({ score_pct: graded.score, total_questions: graded.total, correct_count: graded.correct }).eq('id', item.assignment_id).eq('student_id', userId);
      if (assignmentError) throw assignmentError;
    }
  }
  return true;
}

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to update practice scores.' }, 401);
  const body = await request.json().catch(() => null) as { kind?: unknown; resourceKind?: unknown; resourceId?: unknown; sessionIds?: unknown; reviewId?: unknown; cursor?: unknown } | null;
  const mode = String(body?.kind || '');
  if (!['history', 'resource', 'review'].includes(mode)) return json({ error: 'Invalid regrade request.' }, 400);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const secret = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !secret) return json({ error: 'The score repair service is unavailable.' }, 503);
  try {
    const auth = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await auth.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your Classio session has expired.' }, 401);
    const server = createClient(url, secret, { auth: { persistSession: false, autoRefreshToken: false } });
    const uid = identity.user.id;
    let sessions: Record<string, unknown>[] = [];
    let moreResourceSessions = false;
    let source: PracticeMaterial | null = null;
    let assignments = new Map<string, Record<string, unknown>>();
    if (mode === 'resource') {
      const kind = String(body?.resourceKind || ''); const id = String(body?.resourceId || '');
      if ((kind !== 'worksheet' && kind !== 'exam') || !id) return json({ error: 'A worksheet or exam is required.' }, 400);
      const cursor = Number(body?.cursor || 0);
      if (!Number.isSafeInteger(cursor) || cursor < 0) return json({ error: 'Invalid score refresh cursor.' }, 400);
      const { data: owned, error: ownerError } = await server.from(resourceTable[kind]).select('id').eq('id', id).eq('user_id', uid).maybeSingle();
      if (ownerError) throw ownerError;
      if (!owned) return json({ error: 'Only the resource owner can refresh scores.' }, 403);
      source = await sourceMaterial(server, kind, id);
      const { data: linked, error: linkError } = await server.from('teacher_assignments').select('id,student_id,assignment_type,source_record_id,title,topic,subject_key,subject_label').eq('teacher_id', uid).eq('assignment_type', kind).eq('source_record_id', id);
      if (linkError) throw linkError;
      assignments = new Map((linked || []).map((item) => [String(item.id), row(item)]));
      if (cursor === 0) await syncAssignmentCopies(server, kind, id, uid, [...assignments.keys()]);
      const sourceIds = [id, ...assignments.keys()];
      const batch = await server.from('practice_sessions').select('id,user_id,source_type,source_id,subject,topic,level,exercise_data,status,score_pct,correct_count,total_questions,xp_earned,completed_at').eq('source_type', kind).in('source_id', sourceIds).eq('status', 'completed').gt('id', cursor).order('id', { ascending: true }).limit(RESOURCE_REPAIR_BATCH);
      if (batch.error) throw batch.error;
      const candidates = new Map((batch.data || []).map((item) => [Number(item.id), row(item)]));
      moreResourceSessions = (batch.data || []).length === RESOURCE_REPAIR_BATCH;
      // Streamlit also follows assignment attempts. Older sessions can have
      // an assignment link even when source_id was stored in another format.
      if (assignments.size) {
        const linkedAttempts = await server.from('teacher_assignment_attempts').select('practice_session_id').in('assignment_id', [...assignments.keys()]).gt('practice_session_id', cursor).order('practice_session_id', { ascending: true }).limit(RESOURCE_REPAIR_BATCH);
        if (linkedAttempts.error) throw linkedAttempts.error;
        moreResourceSessions ||= (linkedAttempts.data || []).length === RESOURCE_REPAIR_BATCH;
        const missing = (linkedAttempts.data || []).map((item) => Number(item.practice_session_id)).filter((sessionId) => Number.isSafeInteger(sessionId) && sessionId > cursor && !candidates.has(sessionId));
        if (missing.length) {
          const linkedSessions = await server.from('practice_sessions').select('id,user_id,source_type,source_id,subject,topic,level,exercise_data,status,score_pct,correct_count,total_questions,xp_earned,completed_at').in('id', missing).eq('status', 'completed').eq('source_type', kind);
          if (linkedSessions.error) throw linkedSessions.error;
          for (const item of linkedSessions.data || []) candidates.set(Number(item.id), row(item));
        }
      }
      sessions = [...candidates.values()].sort((left, right) => Number(left.id) - Number(right.id)).slice(0, RESOURCE_REPAIR_BATCH);
      // Student assignment opening resolves its current owned source. Preserve
      // existing snapshots, including exam keys and assignment metadata.
    } else if (mode === 'review') {
      const reviewId = Number(body?.reviewId);
      if (!Number.isSafeInteger(reviewId) || reviewId <= 0) return json({ error: 'A valid review request is required.' }, 400);
      const review = await server.from('teacher_review_requests').select('id,student_id,practice_session_id,assignment_id').eq('id', reviewId).eq('teacher_id', uid).maybeSingle();
      if (review.error) throw review.error;
      if (!review.data) return json({ error: 'Review request not found.' }, 404);
      const found = await server.from('practice_sessions').select('id,user_id,source_type,source_id,subject,topic,level,exercise_data,status,score_pct,correct_count,total_questions,xp_earned').eq('id', review.data.practice_session_id).eq('user_id', review.data.student_id).maybeSingle();
      if (found.error) throw found.error;
      if (found.data) sessions = [{ ...row(found.data), exercise_data: { ...row(found.data.exercise_data), assignment_id: row(found.data.exercise_data).assignment_id || review.data.assignment_id || undefined } }];
      const assignmentId = String(review.data.assignment_id || '');
      if (assignmentId) {
        const assignment = await server.from('teacher_assignments').select('id,student_id,assignment_type,source_record_id,title,topic,subject_key,subject_label').eq('id', assignmentId).eq('teacher_id', uid).maybeSingle();
        if (assignment.error) throw assignment.error;
        if (assignment.data) assignments.set(assignmentId, row(assignment.data));
      }
    } else {
      const ids = Array.isArray(body?.sessionIds) ? body.sessionIds.map(Number).filter((id) => Number.isSafeInteger(id) && id > 0).slice(0, 18) : [];
      if (!ids.length) return json({ examined: 0, repaired: 0 });
      const { data, error } = await server.from('practice_sessions').select('id,user_id,source_type,source_id,subject,topic,level,exercise_data,status,score_pct,correct_count,total_questions,xp_earned').eq('user_id', uid).eq('status', 'completed').in('source_type', ['worksheet', 'exam']).in('id', ids);
      if (error) throw error;
      sessions = (data || []).map(row);
    }
    let repaired = 0;
    const sourceCache = new Map<string, PracticeMaterial | null>();
    for (const session of sessions) {
      const embedded = row(session.exercise_data);
      if (mode === 'history' && embedded.regrade_version === REGRADE_VERSION) continue;
      let assignmentId = String(embedded.assignment_id || '');
      if ((mode === 'history' || mode === 'review') && !assignmentId) {
        const { data: linked, error: linkedError } = await server.from('teacher_assignment_attempts').select('assignment_id').eq('practice_session_id', session.id).eq('student_id', session.user_id).limit(1);
        if (linkedError) throw linkedError;
        assignmentId = String(linked?.[0]?.assignment_id || '');
      }
      if (mode === 'resource') {
        if (assignmentId && !assignments.has(assignmentId)) continue;
        const { data: linkedAttempts, error: linkedError } = await server.from('teacher_assignment_attempts').select('assignment_id').eq('practice_session_id', session.id).limit(2);
        if (linkedError) throw linkedError;
        if (linkedAttempts?.length && linkedAttempts.some((item) => !assignments.has(String(item.assignment_id)))) continue;
        if (!assignmentId && !linkedAttempts?.length && String(embedded.source_id || session.source_id || '') !== String(body?.resourceId || '')) continue;
      }
      let assignment = assignments.get(assignmentId);
      if (!assignment && assignmentId) {
        const lookup = await server.from('teacher_assignments').select('id,student_id,assignment_type,source_record_id,title,topic,subject_key,subject_label').eq('id', assignmentId).eq('student_id', session.user_id).maybeSingle();
        if (lookup.error) throw lookup.error;
        assignment = lookup.data ? row(lookup.data) : undefined;
        if (assignment) assignments.set(assignmentId, assignment);
      }
      const type = String(session.source_type || '');
      const sourceId = assignment ? String(assignment.source_record_id || '') : String(embedded.source_id || session.source_id || '');
      const cacheKey = `${type}:${sourceId}`;
      if (mode !== 'resource' && !sourceCache.has(cacheKey) && (type === 'worksheet' || type === 'exam') && sourceId) sourceCache.set(cacheKey, await sourceMaterial(server, type, sourceId, assignment));
      const current = mode === 'resource' ? source : sourceCache.get(cacheKey) || null;
      if (mode === 'resource' && current && embedded.regrade_version === REGRADE_VERSION && JSON.stringify(embedded.exercises || []) === JSON.stringify(exerciseDataForMaterial({ ...current, assignmentId: String(assignment?.id || '') }).exercises || [])) continue;
      if (await repairSession(server, session, current, assignment)) repaired += 1;
    }
    const nextCursor = mode === 'resource' && sessions.length && (moreResourceSessions || sessions.length === RESOURCE_REPAIR_BATCH) ? Number(sessions[sessions.length - 1].id) : null;
    return json({ examined: sessions.length, repaired, nextCursor });
  } catch (error) {
    console.error('Practice score repair failed', error);
    return json({ error: 'Practice scores could not be refreshed.' }, 502);
  }
}
