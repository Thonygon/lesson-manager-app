import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';
import { canonicalSubjectKey, canonicalSubjectLabel, type TranslationLookup } from '@/lib/subjects';
import { extractResourceImageUrl } from '@/services/public-data';

async function studentId() {
  const { data, error } = await requireSupabase().auth.getUser();
  if (error || !data.user) throw error ?? new Error('Your session has expired.');
  return data.user.id;
}

export type StudentWorkspace = {
  assignments: ClassioRecord[];
  mlHistoryAssignments?: ClassioRecord[];
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
  recommendationFeedback?: ClassioRecord[];
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

export type StudentWorkspaceScope = 'home' | 'assignments' | 'practice' | 'study';

const inFlightStudentWorkspaces = new Map<string, Promise<StudentWorkspace>>();
let cachedRecommendationFeedback: { userId: string; expiresAt: number; promise: Promise<ClassioRecord[]> } | null = null;
let cachedStudentMlHistory: { userId: string; expiresAt: number; promise: Promise<ClassioRecord[]> } | null = null;

export function invalidateStudentRecommendationFeedback() { cachedRecommendationFeedback = null; }

async function getStudentRecommendationFeedback(uid: string): Promise<ClassioRecord[]> {
  if (cachedRecommendationFeedback?.userId === uid && cachedRecommendationFeedback.expiresAt > Date.now()) return cachedRecommendationFeedback.promise;
  const request = loadStudentRecommendationFeedback(uid);
  cachedRecommendationFeedback = { userId: uid, expiresAt: Date.now() + 20000, promise: request };
  request.catch(() => { if (cachedRecommendationFeedback?.promise === request) cachedRecommendationFeedback = null; });
  return request;
}

async function getStudentMlHistoryAssignments(uid: string, cutoff: string, fresh: boolean): Promise<ClassioRecord[]> {
  if (!fresh && cachedStudentMlHistory?.userId === uid && cachedStudentMlHistory.expiresAt > Date.now()) return cachedStudentMlHistory.promise;
  const request = (async () => {
    const { data, error } = await requireSupabase().from('teacher_assignments')
      .select('assignment_type,subject_key,topic,score_pct,status,created_at,updated_at,source_record_id,learning_program_topic_id,recommendation_bucket')
      .eq('student_id', uid).neq('status', 'archived').gte('updated_at', cutoff)
      .order('updated_at', { ascending: false }).limit(800);
    if (error) throw error;
    return (data ?? []) as ClassioRecord[];
  })();
  cachedStudentMlHistory = { userId: uid, expiresAt: Date.now() + 20000, promise: request };
  request.catch(() => { if (cachedStudentMlHistory?.promise === request) cachedStudentMlHistory = null; });
  return request;
}

async function loadStudentRecommendationFeedback(uid: string): Promise<ClassioRecord[]> {
  const client = requireSupabase();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6000);
  try {
  const activityRequest = (async () => {
    const { data } = await client.auth.getSession();
    const token = data.session?.access_token;
    if (!token) return [] as ClassioRecord[];
    const response = await fetch('/api/student-recommendation-feedback', { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal });
    if (!response.ok) return [] as ClassioRecord[];
    const payload = await response.json() as { rows?: ClassioRecord[] };
    return Array.isArray(payload.rows) ? payload.rows : [];
  })().catch(() => [] as ClassioRecord[]);
  const cutoff = new Date(Date.now() - 180 * 86400000).toISOString();
  const [exposures, events] = await Promise.all([
    client.from('resource_exposures').select('exposure_id,resource_type,resource_id,surface,context_json,shown_at,learned_score').eq('student_id', uid).eq('exposure_type', 'optional_student_recommendation').gte('shown_at', cutoff).order('shown_at', { ascending: false }).limit(800).abortSignal(controller.signal),
    client.from('resource_exposure_events').select('exposure_id,event_type,event_at').eq('student_id', uid).eq('event_type', 'opened').gte('event_at', cutoff).order('event_at', { ascending: false }).limit(800).abortSignal(controller.signal),
  ]);
  if (exposures.error || events.error) throw exposures.error ?? events.error;
  const opened = new Map((events.data ?? []).map((row) => [String(row.exposure_id), String(row.event_at)]));
  const derived = (exposures.data ?? []).flatMap((row) => {
    const context = row.context_json && typeof row.context_json === 'object' ? row.context_json as Record<string, unknown> : {};
    const meta = { ...context, surface: row.surface, resource_kind: row.resource_type, resource_id: row.resource_id, ml_score: row.learned_score ?? context.ml_score ?? 0 };
    const impression = { activity_type: 'student_recommendation_impression', meta_json: meta, created_at: row.shown_at };
    const openedAt = opened.get(String(row.exposure_id));
    return openedAt ? [impression, { activity_type: 'student_recommendation_open', meta_json: meta, created_at: openedAt }] : [impression];
  });
  const activity = await activityRequest;
  const seen = new Set<string>();
  return [...activity, ...derived].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))).filter((row) => {
    const meta = row.meta_json && typeof row.meta_json === 'object' ? row.meta_json as Record<string, unknown> : {};
    const signature = [row.activity_type, meta.surface, meta.resource_kind, meta.resource_id, meta.learning_program_assignment_id, meta.learning_program_topic_id, String(row.created_at).slice(0, 13)].join(':');
    if (seen.has(signature)) return false;
    seen.add(signature); return true;
  }).slice(0, 800);
  } finally {
    clearTimeout(timeout);
  }
}

export async function getStudentWorkspace(scope: StudentWorkspaceScope = 'practice', fresh = false): Promise<StudentWorkspace> {
  const uid = await studentId();
  const key = `${uid}:${scope}`;
  const inFlight = inFlightStudentWorkspaces.get(key);
  if (inFlight && !fresh) return inFlight;
  const request = loadStudentWorkspace(scope, uid, fresh);
  inFlightStudentWorkspaces.set(key, request);
  try {
    return await request;
  } finally {
    if (inFlightStudentWorkspaces.get(key) === request) inFlightStudentWorkspaces.delete(key);
  }
}

async function loadStudentWorkspace(scope: StudentWorkspaceScope, uid: string, fresh: boolean): Promise<StudentWorkspace> {
  const client = requireSupabase();
  const assignmentColumns = scope === 'home' || scope === 'study'
    ? 'id,teacher_id,student_id,link_id,assignment_type,source_type,source_record_id,title,topic,subject_key,subject_label,status,due_at,score_pct,total_questions,correct_count,teacher_note,source_archived,learning_program_assignment_id,learning_program_topic_id,assigned_at,opened_at,submitted_at,graded_at,completed_at,created_at,updated_at'
    : scope === 'assignments' || scope === 'practice'
      ? 'id,teacher_id,student_id,link_id,assignment_type,source_type,source_record_id,title,topic,subject_key,subject_label,status,due_at,score_pct,total_questions,correct_count,teacher_note,source_archived,learning_program_assignment_id,learning_program_topic_id,assigned_at,opened_at,submitted_at,graded_at,completed_at,created_at,updated_at'
      : 'id,teacher_id,student_id,link_id,assignment_type,source_type,source_record_id,title,topic,subject_key,subject_label,status,due_at,score_pct,total_questions,correct_count,teacher_note,learning_program_assignment_id,learning_program_topic_id,assigned_at,opened_at,submitted_at,graded_at,completed_at,created_at,updated_at,content_snapshot';
  const [assignments, programs, links, profile] = await Promise.all([
    client.from('teacher_assignments').select(assignmentColumns as string).eq('student_id', uid).neq('status', 'archived').order('created_at', { ascending: false }).limit(1000),
    scope === 'assignments' ? Promise.resolve({ data: [], error: null }) : client.from('learning_program_assignments').select((scope === 'study' ? 'id,program_id,teacher_id,student_user_id,student_name,status,start_on,target_completion_on,teacher_note,assigned_at,updated_at,program:learning_programs(id,title,subject,learner_stage,level_or_band,program_overview,total_units,total_topics,sequence_order,program_data,created_at,updated_at)' : 'id,program_id,teacher_id,student_user_id,student_name,status,start_on,target_completion_on,teacher_note,assigned_at,updated_at,program:learning_programs(id,title,subject,learner_stage,level_or_band,program_overview,total_units,total_topics,sequence_order,created_at,updated_at)') as string).eq('student_user_id', uid).neq('status', 'archived').order('updated_at', { ascending: false }).limit(500),
    scope === 'assignments' || scope === 'home' ? Promise.resolve({ data: [], error: null }) : client.from('teacher_student_links').select('id,teacher_id,student_id,requested_subjects,request_note,status,created_at,updated_at').eq('student_id', uid).order('created_at', { ascending: false }).limit(500),
    scope === 'assignments' ? Promise.resolve({ data: null, error: null }) : client.from('profiles').select('primary_subjects').eq('user_id', uid).maybeSingle(),
  ]);
  const error = assignments.error ?? programs.error ?? links.error ?? profile.error;
  if (error) throw error;
  const assignmentRows = (assignments.data ?? []) as unknown as ClassioRecord[];
  const programRows = (programs.data ?? []) as unknown as ClassioRecord[];
  if (scope === 'assignments') {
    const assignmentIds = assignmentRows.map((row) => row.id).filter(Boolean);
    const [attempts, reviews, drafts] = await Promise.all([
      assignmentIds.length ? client.from('teacher_assignment_attempts').select('id,assignment_id,practice_session_id,attempt_number,status,score_pct,created_at').eq('student_id', uid).order('created_at', { ascending: false }).limit(1000) : Promise.resolve({ data: [], error: null }),
      client.from('teacher_review_requests').select('id,assignment_id,status,teacher_feedback,reviewed_at').eq('student_id', uid).order('requested_at', { ascending: false }).limit(500),
      client.from('practice_sessions').select('id,source_type,source_id,status,started_at').eq('user_id', uid).eq('status', 'in_progress').in('source_type', ['worksheet', 'exam']).order('started_at', { ascending: false }).limit(500),
    ]);
    if (attempts.error || reviews.error || drafts.error) throw attempts.error ?? reviews.error ?? drafts.error;
    const teacherIds = [...new Set(assignmentRows.map((row) => String(row.teacher_id || '')).filter(Boolean))].slice(0, 500);
    const teacherProfiles = teacherIds.length ? await client.from('profiles').select('user_id,display_name,username').in('user_id', teacherIds).limit(500) : { data: [], error: null };
    if (teacherProfiles.error) console.warn('Assignment teacher labels unavailable', teacherProfiles.error);
    const teacherNames = Object.fromEntries((teacherProfiles.data ?? []).map((row) => [String(row.user_id), String(row.display_name || row.username || '')]));
    return { assignments: assignmentRows, attempts: (attempts.data ?? []) as unknown as ClassioRecord[], reviews: (reviews.data ?? []) as unknown as ClassioRecord[], sessions: (drafts.data ?? []) as unknown as ClassioRecord[], practiceProgress: [], programs: [], progress: [], topics: [], links: [], recommendationEvents: [], topicVideoLinks: [], primarySubjects: [], teacherNames };
  }
  if (scope === 'study') {
    const assignmentIds = programRows.map((row) => row.id).filter(Boolean);
    const programIds = [...new Set(programRows.map((row) => row.program_id).filter(Boolean))];
    const [progress, topics] = await Promise.all([
      assignmentIds.length ? client.from('learning_program_progress').select('id,assignment_id,topic_id,teacher_done,student_done,is_done,note,completed_at,created_at,updated_at').in('assignment_id', assignmentIds).order('updated_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
      programIds.length ? client.from('learning_program_topics').select('id,program_id,unit_id,unit_number,topic_number,title,lesson_focus,subtopic,student_summary,lesson_purpose,estimated_lessons,suggested_worksheet_types,suggested_exam_exercise_types').in('program_id', programIds).order('unit_number').order('topic_number').limit(4000) : Promise.resolve({ data: [], error: null }),
    ]);
    if (progress.error || topics.error) throw progress.error ?? topics.error;
    return { assignments: assignmentRows, attempts: [], reviews: [], sessions: [], practiceProgress: [], programs: programRows, progress: (progress.data ?? []) as ClassioRecord[], topics: (topics.data ?? []) as ClassioRecord[], links: [], recommendationEvents: [], topicVideoLinks: [], primarySubjects: [], teacherNames: {} };
  }
  const teacherIds = [...new Set(assignmentRows.map((row) => String(row.teacher_id || '')).filter(Boolean))].slice(0, 500);
  const teacherProfiles = teacherIds.length
    ? await client.from('profiles').select('user_id,display_name,username').in('user_id', teacherIds).limit(500)
    : { data: [], error: null };
  if (teacherProfiles.error) console.warn('Student teacher labels unavailable', teacherProfiles.error);
  const teacherNames = Object.fromEntries((teacherProfiles.data ?? []).map((row) => [String(row.user_id), String(row.display_name || row.username || '')]));
  const assignmentIds = assignmentRows.map((row) => row.id).filter(Boolean);
  const programAssignmentIds = programRows.map((row) => row.id).filter(Boolean); const programIds = programRows.map((row) => row.program_id).filter(Boolean);
  const cutoff = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString();
  const [progress, topics, attempts, reviews, sessions, practiceProgress, mlHistoryAssignments, alignmentAssignments, recommendationEvents, topicVideoLinks] = await Promise.all([
    programAssignmentIds.length ? client.from('learning_program_progress').select('id,assignment_id,topic_id,teacher_done,student_done,is_done,note,completed_at,created_at,updated_at').in('assignment_id', programAssignmentIds).order('updated_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
    programIds.length ? client.from('learning_program_topics').select('id,program_id,unit_id,unit_number,topic_number,title,lesson_focus,subtopic,student_summary,lesson_purpose,estimated_lessons,suggested_worksheet_types,suggested_exam_exercise_types,unit:learning_program_units!learning_program_topics_unit_id_fkey(id,program_id,unit_number)').in('program_id', programIds).order('unit_number').order('topic_number').limit(4000) : Promise.resolve({ data: [], error: null }),
    scope === 'home' ? Promise.resolve({ data: [], error: null }) : assignmentIds.length ? client.from('teacher_assignment_attempts').select('id,assignment_id,teacher_id,student_id,practice_session_id,attempt_number,status,score_pct,total_questions,correct_count,teacher_feedback,started_at,submitted_at,graded_at,completed_at,created_at').eq('student_id', uid).order('created_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
    client.from('teacher_review_requests').select(('id,teacher_id,student_id,assignment_id,practice_session_id,subject_key,subject_label,source_type,source_id,title,status,request_note,teacher_feedback,override_score_pct,requested_at,reviewed_at,created_at') as string).eq('student_id', uid).order('requested_at', { ascending: false }).limit(1000),
    client.from('practice_sessions').select((scope === 'practice' ? 'id,source_type,source_id,title,subject,topic,learner_stage,level,total_questions,correct_count,score_pct,xp_earned,best_streak,status,started_at,completed_at,created_at' : scope === 'home' ? 'id,source_type,source_id,assignment_id:exercise_data->>assignment_id,title,subject,topic,level,score_pct,status,started_at,completed_at,created_at' : 'id,source_type,source_id,subject,topic,level,score_pct,status,completed_at,created_at') as string).eq('user_id', uid).order('created_at', { ascending: false }).limit(scope === 'practice' ? 1000 : 800),
    client.from('practice_progress').select(scope === 'home' ? 'id,subject,topic,exercise_type,level,accuracy_pct,total_attempted,last_practiced' : '*').eq('user_id', uid).order('last_practiced', { ascending: false }).limit(2000),
    getStudentMlHistoryAssignments(uid, cutoff, fresh),
    client.from('teacher_assignments').select('assignment_type,source_record_id,learning_program_topic_id,score_pct,status,updated_at').eq('student_id', uid).neq('status', 'archived').not('source_record_id', 'is', null).not('learning_program_topic_id', 'is', null).gte('updated_at', cutoff).order('updated_at', { ascending: false }).limit(1200),
    client.from('learning_program_recommendation_events').select('teacher_id,student_id,learning_program_topic_id,resource_kind,resource_record_id,event_type,event_weight,created_at').eq('student_id', uid).not('resource_record_id', 'is', null).not('learning_program_topic_id', 'is', null).gte('created_at', cutoff).order('created_at', { ascending: false }).limit(1200),
    programIds.length ? client.from('learning_program_topic_videos').select('teacher_id,program_id,topic_id,video_id,created_at').in('program_id', [...new Set(programIds)]).order('created_at', { ascending: false }).limit(2000) : Promise.resolve({ data: [], error: null }),
  ]);
  const workspaceError = progress.error ?? topics.error ?? attempts.error ?? reviews.error
    ?? sessions.error ?? practiceProgress.error ?? alignmentAssignments.error ?? recommendationEvents.error ?? topicVideoLinks.error;
  if (workspaceError) throw workspaceError;
  const recommendationFeedback = await getStudentRecommendationFeedback(uid).catch((reason) => { console.warn('Student recommendation feedback unavailable', reason); return []; });
  return { assignments: assignmentRows, mlHistoryAssignments, alignmentAssignments: (alignmentAssignments.data ?? []) as ClassioRecord[], attempts: (attempts.data ?? []) as unknown as ClassioRecord[], reviews: (reviews.data ?? []) as unknown as ClassioRecord[], sessions: (sessions.data ?? []) as unknown as ClassioRecord[], practiceProgress: (practiceProgress.data ?? []) as unknown as ClassioRecord[], programs: programRows, progress: (progress.data ?? []) as ClassioRecord[], topics: (topics.data ?? []) as ClassioRecord[], links: (links.data ?? []) as ClassioRecord[], recommendationEvents: (recommendationEvents.data ?? []) as ClassioRecord[], recommendationFeedback, topicVideoLinks: (topicVideoLinks.data ?? []) as ClassioRecord[], primarySubjects: Array.isArray(profile.data?.primary_subjects) ? profile.data.primary_subjects.map(String).filter(Boolean) : [], teacherNames };
}

export async function getStudentPracticeSession(sessionId: string): Promise<ClassioRecord> {
  const client = requireSupabase(); const uid = await studentId();
  const { data, error } = await client.from('practice_sessions').select('id,source_type,source_id,title,subject,topic,learner_stage,level,exercise_data,total_questions,correct_count,score_pct,xp_earned,best_streak,status,started_at,completed_at,created_at').eq('id', sessionId).eq('user_id', uid).maybeSingle();
  if (error) throw error;
  if (!data) throw new Error('This practice session is unavailable.');
  return data as ClassioRecord;
}

export async function getStudentAssignmentDraftSessionId(assignmentId: string, sourceRecordId?: string): Promise<string | null> {
  const client = requireSupabase(); const uid = await studentId();
  const { data, error } = await client.from('practice_sessions').select('id').eq('user_id', uid)
    .in('source_id', [...new Set([assignmentId, sourceRecordId].filter((id): id is string => Boolean(id)))]).in('source_type', ['worksheet', 'exam'])
    .eq('status', 'in_progress').order('started_at', { ascending: false }).limit(1);
  if (error) throw error;
  return data?.[0]?.id == null ? null : String(data[0].id);
}

export async function getStudentAssignmentContent(assignmentId: string): Promise<unknown> {
  const client = requireSupabase(); const uid = await studentId();
  const { data, error } = await client.from('teacher_assignments').select('assignment_type,source_record_id,content_snapshot').eq('id', assignmentId).eq('student_id', uid).maybeSingle();
  if (error) throw error;
  if (!data) return null;
  return resolveStudentAssignmentContent(data, client);
}

async function resolveStudentAssignmentContent(data: { assignment_type?: unknown; source_record_id?: unknown; content_snapshot?: unknown }, client: ReturnType<typeof requireSupabase>): Promise<Record<string, unknown>> {
  const snapshot = data.content_snapshot && typeof data.content_snapshot === 'object' ? { ...data.content_snapshot as Record<string, unknown> } : {};
  const sourceId = String(data.source_record_id || snapshot.id || '');
  if (!sourceId) return snapshot;
  const kind = String(data.assignment_type || '');
  const source = kind === 'worksheet' ? await client.from('worksheets').select('worksheet_json').eq('id', sourceId).maybeSingle()
    : kind === 'exam' ? await client.from('quick_exams').select('exam_data,answer_key').eq('id', sourceId).maybeSingle()
      : kind === 'video' ? await client.from('videos').select('id,title,youtube_url,video_id,thumbnail_url,description,subject,topic').eq('id', sourceId).maybeSingle()
        : null;
  if (source?.error) { console.warn('Assignment source unavailable; using snapshot', source.error); return snapshot; }
  if (!source?.data) return snapshot;
  if (kind === 'worksheet' && 'worksheet_json' in source.data && source.data.worksheet_json && typeof source.data.worksheet_json === 'object') snapshot.worksheet = source.data.worksheet_json;
  if (kind === 'exam' && 'exam_data' in source.data && source.data.exam_data && typeof source.data.exam_data === 'object') {
    snapshot.exam_data = source.data.exam_data;
    if ('answer_key' in source.data && source.data.answer_key && typeof source.data.answer_key === 'object') snapshot.answer_key = source.data.answer_key;
  }
  if (kind === 'video') snapshot.video = source.data;
  return snapshot;
}

/** Load one owned assignment for a direct practice link without waiting for the full practice workspace. */
export async function getStudentAssignmentForPractice(assignmentId: string): Promise<ClassioRecord> {
  const client = requireSupabase(); const uid = await studentId();
  const { data, error } = await client.from('teacher_assignments')
    .select('id,teacher_id,student_id,assignment_type,source_record_id,title,topic,subject_key,subject_label,teacher_note,due_at,assigned_at,created_at,status,learning_program_assignment_id,content_snapshot')
    .eq('id', assignmentId).eq('student_id', uid).maybeSingle();
  if (error) throw error;
  if (!data) throw new Error('This assignment is unavailable.');
  const content = await resolveStudentAssignmentContent(data, client);
  return { ...data, content_snapshot: content } as ClassioRecord;
}

/** Only the six visible cards are read; source rows are tried before assignment snapshots, as in Streamlit. */
export async function getStudentAssignmentCardImages(assignments: ClassioRecord[]): Promise<Record<string, string>> {
  const visible = assignments.filter((row) => ['worksheet', 'exam', 'video'].includes(String(row.assignment_type))).slice(0, 6);
  if (!visible.length) return {};
  const client = requireSupabase();
  const uid = await studentId();
  const sources = [
    { kind: 'worksheet', table: 'worksheets', columns: 'id,worksheet_json' },
    { kind: 'exam', table: 'quick_exams', columns: 'id,exam_data' },
    { kind: 'video', table: 'videos', columns: 'id,thumbnail_url' },
  ] as const;
  const sourceImages = new Map<string, string>();
  await Promise.all(sources.map(async ({ kind, table, columns }) => {
    const ids = [...new Set(visible.filter((row) => String(row.assignment_type) === kind).map((row) => String(row.source_record_id || '')).filter(Boolean))];
    if (!ids.length) return;
    const { data, error } = await client.from(table).select(columns).in('id', ids).limit(6);
    if (error) { console.warn(`Student ${kind} card previews unavailable`, error); return; }
    for (const row of (data ?? []) as Record<string, unknown>[]) {
      const image = extractResourceImageUrl(row);
      if (image) sourceImages.set(`${kind}:${String(row.id)}`, image);
    }
  }));
  const images: Record<string, string> = {};
  for (const row of visible) {
    const image = sourceImages.get(`${String(row.assignment_type)}:${String(row.source_record_id || '')}`);
    if (image) images[String(row.id)] = image;
  }
  const missingIds = visible.map((row) => String(row.id)).filter((id) => !images[id]);
  if (!missingIds.length) return images;
  const { data, error } = await client.from('teacher_assignments').select('id,assignment_type,content_snapshot').eq('student_id', uid).in('id', missingIds).limit(6);
  if (error) { console.warn('Student assignment snapshot previews unavailable', error); return images; }
  for (const row of (data ?? []) as Record<string, unknown>[]) {
    const snapshot = row.content_snapshot && typeof row.content_snapshot === 'object' ? row.content_snapshot as Record<string, unknown> : {};
    const payload = String(row.assignment_type) === 'worksheet' ? snapshot.worksheet : String(row.assignment_type) === 'exam' ? snapshot.exam_data : snapshot.video;
    const image = extractResourceImageUrl(payload) || extractResourceImageUrl(snapshot);
    if (image) images[String(row.id)] = image;
  }
  return images;
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
    client.from('profiles').select('user_id,display_name,username,email,avatar_url').in('user_id', [...new Set(rows.map((row) => row.teacher_id))]).limit(500),
  ]);
  if (scopes.error) throw scopes.error;
  const names = new Map((profiles.data ?? []).map((row) => [String(row.user_id), String(row.display_name || row.username || row.email || '')]));
  const avatars = new Map((profiles.data ?? []).map((row) => [String(row.user_id), String(row.avatar_url || '')]));
  return rows.map((row) => ({ ...row, teacher_name: names.get(String(row.teacher_id)) || '', teacher_avatar_url: avatars.get(String(row.teacher_id)) || '', active_subjects: (scopes.data ?? []).filter((scope) => String(scope.link_id) === String(row.id) && scope.status === 'active') })) as ClassioRecord[];
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
