import { requireSupabase } from '@/lib/supabase';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import type { ClassioRecord } from '@/services/classio-data';

export type RosterCandidate = { id: string; student: string; email: string; match: 'email' | 'name' };
export type TeacherConnection = ClassioRecord & { student_name: string; student_email: string; subjects: ClassioRecord[]; roster_candidates: RosterCandidate[] };
export type StudentLearningWorkspace = { assignments: ClassioRecord[]; attempts: ClassioRecord[]; reviews: ClassioRecord[]; programs: ClassioRecord[]; progress: ClassioRecord[]; topics: ClassioRecord[]; recommendationEvents: ClassioRecord[]; proactiveCompletedResources?: { kind: string; id: string }[] };

async function completedProactiveResources(studentUserId: string): Promise<{ kind: string; id: string }[]> {
  if (!studentUserId) return [];
  const client = requireSupabase();
  const { data, error } = await client.auth.getSession();
  if (error || !data.session?.access_token) return [];
  try {
    const response = await fetch('/api/student-resource-signals', { method: 'POST', headers: { Authorization: `Bearer ${data.session.access_token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ studentId: studentUserId }) });
    if (!response.ok) return [];
    const payload = await response.json() as { completed?: { kind: string; id: string }[] };
    return Array.isArray(payload.completed) ? payload.completed : [];
  } catch { return []; }
}

async function currentUserId() { const { data, error } = await requireSupabase().auth.getUser(); if (error || !data.user) throw error ?? new Error('Your session has expired.'); return data.user.id; }
function cleanScopes(value: unknown): { subject_key: string; subject_label: string }[] { if (!Array.isArray(value)) return []; const unique = new Map<string, { subject_key: string; subject_label: string }>(); value.forEach((item) => { const raw = typeof item === 'string' ? item : item && typeof item === 'object' ? String((item as Record<string, unknown>).subject_key || (item as Record<string, unknown>).subject_label || '') : ''; if (!raw.trim()) return; const key = canonicalSubjectKey(raw); unique.set(key, { subject_key: key, subject_label: canonicalSubjectLabel(raw) }); }); return [...unique.values()]; }
function normalized(value: unknown) { return String(value || '').trim().toLocaleLowerCase(); }

export async function getTeacherConnections(): Promise<TeacherConnection[]> {
  const client = requireSupabase(); const uid = await currentUserId(); const [links, subjects, roster] = await Promise.all([
    client.from('teacher_student_links').select('id,teacher_id,student_id,requested_by,requested_subjects,request_note,status,responded_at,archived_at,created_at,updated_at').eq('teacher_id', uid).order('created_at', { ascending: false }).limit(1000),
    client.from('teacher_student_subjects').select('id,link_id,student_id,subject_key,subject_label,status,activated_at,deactivated_at').eq('teacher_id', uid).limit(2000),
    client.from('students').select('id,student,email,linked_student_user_id').eq('user_id', uid).limit(1000),
  ]); if (links.error || subjects.error || roster.error) throw links.error ?? subjects.error ?? roster.error;
  const ids = (links.data ?? []).map((row) => String(row.student_id)); let profiles: { user_id: string; display_name?: string; username?: string; email?: string }[] = [];
  if (ids.length) { const result = await client.from('profiles').select('user_id,display_name,username,email').in('user_id', ids); if (!result.error) profiles = result.data ?? []; }
  const profileMap = new Map(profiles.map((row) => [String(row.user_id), row])); const rosterMap = new Map((roster.data ?? []).filter((row) => row.linked_student_user_id).map((row) => [String(row.linked_student_user_id), row]));
  return (links.data ?? []).map((row) => { const profile = profileMap.get(String(row.student_id)); const localStudent = rosterMap.get(String(row.student_id)); const studentName = String(profile?.display_name || profile?.username || localStudent?.student || profile?.email?.split('@')[0] || 'Student'); const studentEmail = String(profile?.email || localStudent?.email || ''); const candidates = (roster.data ?? []).flatMap((candidate) => { if (candidate.linked_student_user_id && String(candidate.linked_student_user_id) !== String(row.student_id)) return []; const emailMatch = Boolean(normalized(studentEmail) && normalized(candidate.email) === normalized(studentEmail)); const nameMatch = normalized(candidate.student) === normalized(studentName); return emailMatch || nameMatch ? [{ id: String(candidate.id), student: String(candidate.student || 'Student'), email: String(candidate.email || ''), match: emailMatch ? 'email' as const : 'name' as const }] : []; }); const canonicalSubjects = new Map<string, ClassioRecord>(); (subjects.data ?? []).filter((scope) => String(scope.link_id) === String(row.id)).forEach((scope) => { const key = canonicalSubjectKey(scope.subject_key || scope.subject_label); canonicalSubjects.set(key, { ...(scope as unknown as ClassioRecord), subject_key: key, subject_label: canonicalSubjectLabel(scope.subject_label || scope.subject_key) }); }); return { ...(row as unknown as ClassioRecord), requested_subjects: cleanScopes(row.requested_subjects), student_name: studentName, student_email: studentEmail, subjects: [...canonicalSubjects.values()], roster_candidates: candidates } as TeacherConnection; });
}

export async function getProgramAssignmentTargets(): Promise<TeacherConnection[]> {
  const client = requireSupabase();
  const uid = await currentUserId();
  const [connections, roster] = await Promise.all([
    getTeacherConnections(),
    client.from('students').select('id,student,email,linked_student_user_id').eq('user_id', uid).order('student').limit(1000),
  ]);
  if (roster.error) throw roster.error;
  return [
    ...connections.filter((row) => String(row.status) === 'active'),
    ...(roster.data ?? []).filter((row) => !row.linked_student_user_id).map((row) => ({
      id: `roster:${row.id}`, teacher_id: uid, student_id: row.linked_student_user_id || '',
      roster_student_id: row.id, student_name: String(row.student || ''), student_email: String(row.email || ''),
      status: 'active', subjects: [], roster_candidates: [],
    } as TeacherConnection)),
  ];
}

export async function respondToTeacherConnection(connection: TeacherConnection, accept: boolean, selectedSubjectKeys?: string[], rosterId?: string) {
  const client = requireSupabase(); const uid = await currentUserId(); const now = new Date().toISOString();
  if (!accept) { const { error } = await client.from('teacher_student_links').update({ status: 'rejected', responded_at: now, responded_by: uid, updated_at: now }).eq('id', connection.id).eq('teacher_id', uid); if (error) throw error; return; }
  const requestedScopes = cleanScopes(connection.requested_subjects); const allowed = new Set(selectedSubjectKeys?.length ? selectedSubjectKeys : requestedScopes.map((scope) => scope.subject_key)); const scopes = requestedScopes.filter((scope) => allowed.has(scope.subject_key)); if (!scopes.length) throw new Error('Select at least one subject before accepting this request.');
  const { error: linkError } = await client.from('teacher_student_links').update({ status: 'active', responded_at: now, responded_by: uid, archived_at: null, updated_at: now }).eq('id', connection.id).eq('teacher_id', uid); if (linkError) throw linkError;
  try {
    const subjectRows = scopes.map((scope) => ({ link_id: connection.id, teacher_id: uid, student_id: connection.student_id, subject_key: scope.subject_key, subject_label: scope.subject_label, status: 'active', activated_at: now, deactivated_at: null, updated_at: now })); const { error: scopeError } = await client.from('teacher_student_subjects').upsert(subjectRows, { onConflict: 'link_id,subject_key' }); if (scopeError) throw scopeError;
    const existing = rosterId ? { data: [{ id: rosterId }], error: null } : await client.from('students').select('id').eq('user_id', uid).eq('linked_student_user_id', connection.student_id).limit(1); if (existing.error) throw existing.error;
    if (existing.data?.[0]) { const { error } = await client.from('students').update({ linked_student_user_id: connection.student_id, teacher_student_link_id: connection.id, linked_at: now, student_source: 'teacher_student_link' }).eq('id', existing.data[0].id).eq('user_id', uid); if (error) throw error; }
    else { const { error } = await client.from('students').insert({ user_id: uid, student: connection.student_name, email: connection.student_email, linked_student_user_id: connection.student_id, teacher_student_link_id: connection.id, linked_at: now, student_source: 'teacher_student_link' }); if (error) throw error; }
  } catch (error) { await client.from('teacher_student_links').update({ status: 'pending', responded_at: null, responded_by: null, updated_at: now }).eq('id', connection.id).eq('teacher_id', uid); throw error; }
}

export async function archiveTeacherConnection(connection: TeacherConnection) { const client = requireSupabase(); const uid = await currentUserId(); const now = new Date().toISOString(); const { error } = await client.from('teacher_student_links').update({ status: 'archived', archived_at: now, updated_at: now }).eq('id', connection.id).eq('teacher_id', uid); if (error) throw error; const { error: subjectError } = await client.from('teacher_student_subjects').update({ status: 'archived', deactivated_at: now, updated_at: now }).eq('link_id', connection.id).eq('teacher_id', uid); if (subjectError) throw subjectError; }

export async function archiveTeacherAssignment(id: string | number) { const client = requireSupabase(); const uid = await currentUserId(); const { error } = await client.from('teacher_assignments').update({ status: 'archived', updated_at: new Date().toISOString() }).eq('id', id).eq('teacher_id', uid); if (error) throw error; }

export async function setTeacherProgramTopicProgress(assignmentId: string | number, topicId: string | number, done: boolean) {
  const client = requireSupabase(); const uid = await currentUserId(); const { data: assignment, error: assignmentError } = await client.from('learning_program_assignments').select('id').eq('id', assignmentId).eq('teacher_id', uid).maybeSingle(); if (assignmentError || !assignment) throw assignmentError ?? new Error('This learning-program assignment is unavailable.');
  const now = new Date().toISOString(); const { data: current, error: currentError } = await client.from('learning_program_progress').select('id,teacher_done,student_done,note').eq('assignment_id', assignmentId).eq('topic_id', topicId).maybeSingle(); if (currentError) throw currentError;
  const firstTeacherCompletion = done && !Boolean(current?.teacher_done);
  const payload = { assignment_id: Number(assignmentId), topic_id: Number(topicId), teacher_done: done, student_done: firstTeacherCompletion ? false : Boolean(current?.student_done), is_done: done, note: String(current?.note || ''), completed_at: done ? now : null, updated_at: now };
  const result = current?.id ? await client.from('learning_program_progress').update(payload).eq('id', current.id) : await client.from('learning_program_progress').insert({ ...payload, created_at: now }); if (result.error) throw result.error;
}

export async function addressTeacherPracticeRequest(assignmentId: string | number, topicId: string | number) {
  const client = requireSupabase(); const uid = await currentUserId();
  const { data: assignment, error: assignmentError } = await client.from('learning_program_assignments').select('id').eq('id', assignmentId).eq('teacher_id', uid).maybeSingle();
  if (assignmentError || !assignment) throw assignmentError ?? new Error('This learning-program assignment is unavailable.');
  const { error } = await client.from('learning_program_progress').update({ student_done: false, updated_at: new Date().toISOString() }).eq('assignment_id', assignmentId).eq('topic_id', topicId).eq('teacher_done', true).eq('student_done', true);
  if (error) throw error;
}

export async function requestTeacherRevision(assignment: ClassioRecord, attempt: ClassioRecord) {
  const client = requireSupabase(); await currentUserId(); const practiceSessionId = Number(attempt.practice_session_id || 0); if (!practiceSessionId) throw new Error('This attempt is not linked to a practice session.');
  const { data, error } = await client.rpc('classio_request_teacher_revision', { p_assignment_id: Number(assignment.id), p_practice_session_id: practiceSessionId }); if (error) throw error; return (data ?? {}) as unknown as ClassioRecord;
}

export async function getStudentLearningWorkspace(studentName: string, studentUserId?: string, rosterStudentId?: string): Promise<StudentLearningWorkspace> {
  const client = requireSupabase(); const uid = await currentUserId(); const safeName = studentName.trim();
  const [assignmentResult, reviewResult, programByIdResult, programByNameResult, programByRosterResult] = await Promise.all([
    studentUserId ? client.from('teacher_assignments').select('id,student_id,title,topic,subject_key,subject_label,assignment_type,source_type,source_record_id,status,score_pct,total_questions,correct_count,due_at,assigned_at,opened_at,submitted_at,graded_at,completed_at,created_at,updated_at,learning_program_assignment_id,learning_program_topic_id').eq('teacher_id', uid).eq('student_id', studentUserId).neq('status', 'archived').order('created_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
    studentUserId ? client.from('teacher_review_requests').select('id,student_id,assignment_id,practice_session_id,title,subject_key,subject_label,status,request_note,teacher_feedback,override_score_pct,requested_at,reviewed_at').eq('teacher_id', uid).eq('student_id', studentUserId).order('requested_at', { ascending: false }).limit(1000) : Promise.resolve({ data: [], error: null }),
    studentUserId ? client.from('learning_program_assignments').select('id,program_id,student_user_id,student_name,status,start_on,target_completion_on,teacher_note,assigned_at,updated_at').eq('teacher_id', uid).eq('student_user_id', studentUserId).order('updated_at', { ascending: false }).limit(1000) : Promise.resolve({ data: [], error: null }),
    safeName ? client.from('learning_program_assignments').select('id,program_id,student_user_id,student_name,status,start_on,target_completion_on,teacher_note,assigned_at,updated_at').eq('teacher_id', uid).eq('student_name', safeName).is('roster_student_id', null).order('updated_at', { ascending: false }).limit(1000) : Promise.resolve({ data: [], error: null }),
    rosterStudentId ? client.from('learning_program_assignments').select('id,program_id,student_user_id,student_name,roster_student_id,status,start_on,target_completion_on,teacher_note,assigned_at,updated_at').eq('teacher_id', uid).eq('roster_student_id', rosterStudentId).order('updated_at', { ascending: false }).limit(1000) : Promise.resolve({ data: [], error: null }),
  ]); const error = assignmentResult.error ?? reviewResult.error ?? programByIdResult.error ?? programByNameResult.error ?? programByRosterResult.error; if (error) throw error;
  const assignments = assignmentResult.data ?? []; const reviews = reviewResult.data ?? [];
  const programs = [...new Map([...(programByIdResult.data ?? []), ...(programByNameResult.data ?? []), ...(programByRosterResult.data ?? [])].map((row) => [String(row.id), row])).values()];
  const assignmentIds = assignments.map((row) => row.id); const programIds = [...new Set(programs.map((row) => row.program_id))]; const programAssignmentIds = programs.map((row) => row.id);
  const [attemptResult, titleResult, progressResult, eventResult, proactiveCompletedResources] = await Promise.all([
    assignmentIds.length ? client.from('teacher_assignment_attempts').select('id,assignment_id,student_id,practice_session_id,attempt_number,status,score_pct,total_questions,correct_count,teacher_feedback,submitted_at,graded_at,completed_at,created_at').eq('teacher_id', uid).in('assignment_id', assignmentIds).order('created_at', { ascending: false }) : Promise.resolve({ data: [], error: null }),
    programIds.length ? client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,program_overview,total_units,total_topics,sequence_order,program_data,status,created_at,updated_at').in('id', programIds) : Promise.resolve({ data: [], error: null }),
    programAssignmentIds.length ? client.from('learning_program_progress').select('id,assignment_id,topic_id,teacher_done,student_done,is_done,note,completed_at,updated_at').in('assignment_id', programAssignmentIds) : Promise.resolve({ data: [], error: null }),
    (studentUserId || rosterStudentId) ? client.from('learning_program_recommendation_events').select('learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,event_type,created_at,metadata').eq('teacher_id', uid).eq('student_id', studentUserId || `roster:${rosterStudentId}`).gte('created_at', new Date(Date.now() - 180 * 86400000).toISOString()).order('created_at', { ascending: false }).limit(500) : Promise.resolve({ data: [], error: null }),
    completedProactiveResources(studentUserId || ''),
  ]); if (attemptResult.error || titleResult.error || progressResult.error) throw attemptResult.error ?? titleResult.error ?? progressResult.error; const topicResult = programIds.length ? await client.from('learning_program_topics').select('id,program_id,unit_id,unit_number,topic_number,title,lesson_focus,subtopic,student_summary,estimated_lessons,unit:learning_program_units!learning_program_topics_unit_id_fkey(id,program_id,unit_number)').in('program_id', programIds).order('unit_number').order('topic_number') : { data: [], error: null }; if (topicResult.error) throw topicResult.error;
  const titles = new Map((titleResult.data ?? []).map((row) => [String(row.id), row])); return { assignments: assignments as unknown as ClassioRecord[], attempts: (attemptResult.data ?? []) as unknown as ClassioRecord[], reviews: reviews as unknown as ClassioRecord[], programs: programs.map((row) => ({ ...row, program: titles.get(String(row.program_id)) || {} })) as unknown as ClassioRecord[], progress: (progressResult.data ?? []) as unknown as ClassioRecord[], topics: (topicResult.data ?? []) as unknown as ClassioRecord[], recommendationEvents: (eventResult.error ? [] : eventResult.data ?? []) as unknown as ClassioRecord[], proactiveCompletedResources };
}
