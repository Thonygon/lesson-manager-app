import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';
import { canonicalSubjectKey, canonicalSubjectLabel, type TranslationLookup } from '@/lib/subjects';

async function studentId() {
  const { data, error } = await requireSupabase().auth.getUser();
  if (error || !data.user) throw error ?? new Error('Your session has expired.');
  return data.user.id;
}

export type StudentWorkspace = {
  assignments: ClassioRecord[];
  alignmentAssignments?: ClassioRecord[];
  attempts: ClassioRecord[];
  reviews: ClassioRecord[];
  sessions: ClassioRecord[];
  practiceProgress: ClassioRecord[];
  programs: ClassioRecord[];
  progress: ClassioRecord[];
  topics: ClassioRecord[];
  links: ClassioRecord[];
  recommendationEvents: ClassioRecord[];
  topicVideoLinks: ClassioRecord[];
  primarySubjects: string[];
  teacherNames: Record<string, string>;
};

export type ReviewableTeacher = { teacherId: string; name: string; subjects: string[] };

export async function getReviewableTeachers(subject: string): Promise<ReviewableTeacher[]> {
  const client = requireSupabase(); const uid = await studentId();
  const links = await client.from('teacher_student_links').select('id,teacher_id').eq('student_id', uid).eq('status', 'active').limit(500);
  if (links.error) throw links.error;
  const linkRows = links.data ?? []; if (!linkRows.length) return [];
  const linkIds = linkRows.map((row) => row.id); const teacherIds = linkRows.map((row) => String(row.teacher_id));
  const [scopes, profiles] = await Promise.all([
    client.from('teacher_student_subjects').select('link_id,teacher_id,subject_key,subject_label,status').in('link_id', linkIds).eq('status', 'active').limit(1000),
    client.from('profiles').select('user_id,display_name,username,email').in('user_id', teacherIds).limit(500),
  ]);
  if (scopes.error) throw scopes.error;
  const normalize = (value: unknown) => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  const wanted = normalize(subject); const profileMap = new Map((profiles.data ?? []).map((row) => [String(row.user_id), row]));
  return linkRows.flatMap((link) => { const active = (scopes.data ?? []).filter((row) => String(row.link_id) === String(link.id)); if (wanted && !active.some((row) => normalize(row.subject_key || row.subject_label) === wanted)) return []; const profile = profileMap.get(String(link.teacher_id)); return [{ teacherId: String(link.teacher_id), name: String(profile?.display_name || profile?.username || profile?.email || 'Teacher'), subjects: active.map((row) => String(row.subject_label || row.subject_key || '')).filter(Boolean) }]; });
}

export async function getStudentWorkspace(): Promise<StudentWorkspace> {
  const client = requireSupabase(); const uid = await studentId();
  const [assignments, programs, links, profile] = await Promise.all([
    client.from('teacher_assignments').select('id,teacher_id,student_id,link_id,assignment_type,source_type,source_record_id,title,topic,subject_key,subject_label,status,due_at,score_pct,total_questions,correct_count,teacher_note,learning_program_assignment_id,learning_program_topic_id,assigned_at,opened_at,submitted_at,graded_at,completed_at,created_at,updated_at,content_snapshot').eq('student_id', uid).neq('status', 'archived').order('created_at', { ascending: false }).limit(1000),
    client.from('learning_program_assignments').select('id,program_id,teacher_id,student_user_id,student_name,status,start_on,target_completion_on,teacher_note,assigned_at,updated_at,program:learning_programs(id,title,subject,learner_stage,level_or_band,program_overview,total_units,total_topics,sequence_order,created_at,updated_at)').eq('student_user_id', uid).neq('status', 'archived').order('updated_at', { ascending: false }).limit(500),
    client.from('teacher_student_links').select('id,teacher_id,student_id,requested_subjects,request_note,status,created_at,updated_at').eq('student_id', uid).order('created_at', { ascending: false }).limit(500),
    client.from('profiles').select('primary_subjects').eq('user_id', uid).maybeSingle(),
  ]);
  const error = assignments.error ?? programs.error ?? links.error ?? profile.error;
  if (error) throw error;
  const teacherIds = [...new Set((assignments.data ?? []).map((row) => String(row.teacher_id || '')).filter(Boolean))].slice(0, 500);
  const teacherProfiles = teacherIds.length
    ? await client.from('profiles').select('user_id,display_name,username').in('user_id', teacherIds).limit(500)
    : { data: [], error: null };
  if (teacherProfiles.error) console.warn('Student teacher labels unavailable', teacherProfiles.error);
  const teacherNames = Object.fromEntries((teacherProfiles.data ?? []).map((row) => [String(row.user_id), String(row.display_name || row.username || '')]));
  const assignmentIds = (assignments.data ?? []).map((row) => row.id).filter(Boolean);
  const programAssignmentIds = (programs.data ?? []).map((row) => row.id).filter(Boolean); const programIds = (programs.data ?? []).map((row) => row.program_id).filter(Boolean);
  const cutoff = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString();
  const [progress, topics, attempts, reviews, sessions, practiceProgress, alignmentAssignments, recommendationEvents, topicVideoLinks] = await Promise.all([
    programAssignmentIds.length ? client.from('learning_program_progress').select('id,assignment_id,topic_id,teacher_done,student_done,is_done,note,completed_at,created_at,updated_at').in('assignment_id', programAssignmentIds).order('updated_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
    programIds.length ? client.from('learning_program_topics').select('id,program_id,unit_id,unit_number,topic_number,title,lesson_focus,subtopic,student_summary,lesson_purpose,estimated_lessons,suggested_worksheet_types,suggested_exam_exercise_types').in('program_id', programIds).order('unit_number').order('topic_number').limit(4000) : Promise.resolve({ data: [], error: null }),
    assignmentIds.length ? client.from('teacher_assignment_attempts').select('id,assignment_id,teacher_id,student_id,practice_session_id,attempt_number,status,score_pct,total_questions,correct_count,submission_payload,teacher_feedback,started_at,submitted_at,graded_at,completed_at,created_at').eq('student_id', uid).in('assignment_id', assignmentIds).order('created_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
    client.from('teacher_review_requests').select('id,teacher_id,student_id,assignment_id,practice_session_id,subject_key,subject_label,source_type,source_id,title,status,request_note,teacher_feedback,review_payload,override_score_pct,requested_at,reviewed_at,created_at').eq('student_id', uid).order('requested_at', { ascending: false }).limit(1000),
    client.from('practice_sessions').select('id,source_type,source_id,title,subject,topic,learner_stage,level,exercise_data,total_questions,correct_count,score_pct,xp_earned,best_streak,status,started_at,completed_at,created_at').eq('user_id', uid).order('created_at', { ascending: false }).limit(1000),
    client.from('practice_progress').select('*').eq('user_id', uid).order('last_practiced', { ascending: false }).limit(2000),
    client.from('teacher_assignments').select('assignment_type,source_record_id,learning_program_topic_id,score_pct,status,updated_at').eq('student_id', uid).neq('status', 'archived').not('source_record_id', 'is', null).not('learning_program_topic_id', 'is', null).gte('updated_at', cutoff).order('updated_at', { ascending: false }).limit(1200),
    client.from('learning_program_recommendation_events').select('teacher_id,student_id,learning_program_topic_id,resource_kind,resource_record_id,event_type,event_weight,created_at').eq('student_id', uid).not('resource_record_id', 'is', null).not('learning_program_topic_id', 'is', null).gte('created_at', cutoff).order('created_at', { ascending: false }).limit(1200),
    programIds.length ? client.from('learning_program_topic_videos').select('teacher_id,program_id,topic_id,video_id,created_at').in('program_id', [...new Set(programIds)]).order('created_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
  ]);
  const workspaceError = progress.error ?? topics.error ?? attempts.error ?? reviews.error
    ?? sessions.error ?? practiceProgress.error ?? alignmentAssignments.error ?? recommendationEvents.error ?? topicVideoLinks.error;
  if (workspaceError) throw workspaceError;
  return { assignments: (assignments.data ?? []) as ClassioRecord[], alignmentAssignments: (alignmentAssignments.data ?? []) as ClassioRecord[], attempts: (attempts.data ?? []) as ClassioRecord[], reviews: (reviews.data ?? []) as ClassioRecord[], sessions: (sessions.data ?? []) as ClassioRecord[], practiceProgress: (practiceProgress.data ?? []) as ClassioRecord[], programs: (programs.data ?? []) as ClassioRecord[], progress: (progress.data ?? []) as ClassioRecord[], topics: (topics.data ?? []) as ClassioRecord[], links: (links.data ?? []) as ClassioRecord[], recommendationEvents: (recommendationEvents.data ?? []) as ClassioRecord[], topicVideoLinks: (topicVideoLinks.data ?? []) as ClassioRecord[], primarySubjects: Array.isArray(profile.data?.primary_subjects) ? profile.data.primary_subjects.map(String).filter(Boolean) : [], teacherNames };
}

export async function setStudentNeedsMorePractice(assignmentId: string | number, topicId: string | number, needsPractice: boolean) {
  const client = requireSupabase(); const uid = await studentId(); const { data: assignment, error: assignmentError } = await client.from('learning_program_assignments').select('id').eq('id', assignmentId).eq('student_user_id', uid).maybeSingle(); if (assignmentError || !assignment) throw assignmentError ?? new Error('This learning-program assignment is unavailable.');
  const now = new Date().toISOString(); const { data: current, error: currentError } = await client.from('learning_program_progress').select('id,teacher_done,note,completed_at').eq('assignment_id', assignmentId).eq('topic_id', topicId).maybeSingle(); if (currentError) throw currentError; if (!current?.teacher_done) throw new Error('Complete this topic with your teacher before requesting more practice.');
  const payload = { assignment_id: Number(assignmentId), topic_id: Number(topicId), teacher_done: true, student_done: needsPractice, is_done: true, note: String(current.note || ''), completed_at: current.completed_at || now, updated_at: now };
  const result = current.id ? await client.from('learning_program_progress').update(payload).eq('id', current.id) : await client.from('learning_program_progress').insert({ ...payload, created_at: now }); if (result.error) throw result.error;
}

export async function getCommunityProfiles() {
  const uid = await studentId();
  const { data, error } = await requireSupabase().from('profiles').select('user_id,display_name,username,avatar_url,country,primary_subjects,custom_subjects,teaching_stages,teaching_languages,education_level,active_student_count,show_community_profile,show_community_contact,phone_number,email,role,primary_role,can_teach,can_study,last_active_mode').eq('show_community_profile', true).neq('user_id', uid).limit(1000);
  if (error) throw error;
  return (data ?? []) as ClassioRecord[];
}

export async function getStudentTeacherConnections(): Promise<ClassioRecord[]> {
  const client = requireSupabase(); const uid = await studentId();
  const links = await client.from('teacher_student_links').select('id,teacher_id,student_id,requested_subjects,request_note,status,created_at,updated_at').eq('student_id', uid).order('created_at', { ascending: false }).limit(500);
  if (links.error) throw links.error;
  const rows = links.data ?? [];
  if (!rows.length) return [];
  const [scopes, profiles] = await Promise.all([
    client.from('teacher_student_subjects').select('link_id,subject_key,subject_label,status').in('link_id', rows.map((row) => row.id)).order('subject_label').limit(1000),
    client.from('profiles').select('user_id,display_name,username,email').in('user_id', [...new Set(rows.map((row) => row.teacher_id))]).limit(500),
  ]);
  if (scopes.error) throw scopes.error;
  const names = new Map((profiles.data ?? []).map((row) => [String(row.user_id), String(row.display_name || row.username || row.email || '')]));
  return rows.map((row) => ({ ...row, teacher_name: names.get(String(row.teacher_id)) || '', active_subjects: (scopes.data ?? []).filter((scope) => String(scope.link_id) === String(row.id) && scope.status === 'active') })) as ClassioRecord[];
}

export async function requestTeacherConnection(teacherId: string, subjects: string[], note: string, t?: TranslationLookup) {
  const client = requireSupabase(); const uid = await studentId();
  if (teacherId === uid) throw new Error('You cannot request a connection with yourself.');
  const requestedSubjects = [...new Set(subjects.map((subject) => subject.trim()).filter(Boolean))].map((subject) => {
    const normalized = canonicalSubjectKey(subject);
    const isCustom = !['english', 'spanish', 'mathematics', 'science', 'music', 'study_skills'].includes(normalized);
    const label = subject.replace(/\s+/g, ' ').trim();
    return isCustom
      ? { subject_key: label.toLocaleLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'other', subject_label: label[0].toLocaleUpperCase() + label.slice(1), is_custom: true }
      : { subject_key: normalized, subject_label: canonicalSubjectLabel(normalized, t), is_custom: false };
  });
  if (!requestedSubjects.length) throw new Error('Select at least one subject.');
  const { data: existing, error: lookupError } = await client.from('teacher_student_links').select('id,status').eq('teacher_id', teacherId).eq('student_id', uid).limit(1).maybeSingle();
  if (lookupError) throw lookupError;
  if (existing && ['pending', 'active'].includes(existing.status)) throw new Error('A connection with this teacher already exists.');
  const now = new Date().toISOString();
  const payload = { teacher_id: teacherId, student_id: uid, requested_by: uid, requested_subjects: requestedSubjects, request_note: note.replace(/\s+/g, ' ').trim(), status: 'pending', responded_at: null, responded_by: null, archived_at: null, updated_at: now };
  const { error } = existing
    ? await client.from('teacher_student_links').update(payload).eq('id', existing.id).eq('student_id', uid)
    : await client.from('teacher_student_links').insert({ ...payload, created_at: now });
  if (error) throw error;
}

export async function updateStudentConnection(linkId: string | number, status: 'withdrawn' | 'archived') {
  if (status !== 'withdrawn' && status !== 'archived') throw new Error('Unsupported connection action.');
  const client = requireSupabase(); const { data: session, error: sessionError } = await client.auth.getSession();
  if (sessionError || !session.session?.access_token) throw sessionError ?? new Error('Your session has expired.');
  const response = await fetch('/api/student-connection', { method: 'POST', headers: { Authorization: `Bearer ${session.session.access_token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ linkId }) });
  if (!response.ok) { const result = await response.json().catch(() => ({})) as { error?: string }; throw new Error(result.error || 'The teacher connection could not be ended.'); }
}

export type BillingPlan = { id: string; name: string; price: number | null; billing_interval: string; features_json: Record<string, unknown>; limits_json: Record<string, unknown>; active: boolean };
const DEFAULT_PLANS: BillingPlan[] = [
  { id: 'free', name: 'Free', price: 0, billing_interval: 'month', features_json: { ai_tools: true, pdf_export: true, word_export: true, videos_access: true }, limits_json: { ai_generations: 10, pdf_exports: 3, word_exports: 3, students_count: 5, classes_count: 20 }, active: true },
  { id: 'teacher_pro', name: 'Teacher Pro', price: 1900, billing_interval: 'month', features_json: { ai_tools: true, pdf_export: true, word_export: true, videos_access: true, premium_tools: true }, limits_json: { ai_generations: 250, pdf_exports: 100, word_exports: 100, students_count: 75, classes_count: 500 }, active: true },
  { id: 'school', name: 'School Plan', price: null, billing_interval: 'month', features_json: { ai_tools: true, pdf_export: true, word_export: true, videos_access: true, premium_tools: true, school_admin: true }, limits_json: { ai_generations: 2000, pdf_exports: 1000, word_exports: 1000, students_count: 1000, classes_count: 10000 }, active: true },
];

export async function getBillingPlans() {
  const client = requireSupabase(); const uid = await studentId();
  const [plans, subscription, profile] = await Promise.all([
    client.from('plans').select('*').eq('active', true),
    client.from('user_subscriptions').select('*,plans(*)').eq('user_id', uid).limit(1).maybeSingle(),
    client.from('profiles').select('current_plan').eq('user_id', uid).maybeSingle(),
  ]);
  const catalog = plans.error || !plans.data?.length ? DEFAULT_PLANS : (plans.data as BillingPlan[]);
  return { plans: catalog.filter((plan) => plan.id !== 'beta_lifetime'), subscription: subscription.data as ClassioRecord | null, currentPlan: String(profile.data?.current_plan || subscription.data?.plan_id || 'free') };
}
