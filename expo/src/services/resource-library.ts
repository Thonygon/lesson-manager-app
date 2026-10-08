import { requireSupabase } from '@/lib/supabase';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { extractResourceImageUrl, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import type { TeacherConnection } from '@/services/teacher-students';

export type ResourceScope = 'mine' | 'community' | 'archive';

const DEFINITIONS: Record<PublicResourceKind, { table: string; columns: string; order: string }> = {
  program: { table: 'learning_programs', columns: 'id,user_id,title,subject,custom_subject_name,learner_stage,level_or_band,program_overview,is_public,status,total_units,total_topics,sequence_order,created_at,updated_at', order: 'updated_at' },
  plan: { table: 'lesson_plans', columns: 'id,user_id,title,subject,topic,learner_stage,level_or_band,lesson_purpose,source_type,planner_mode,author_name,subject_display,is_public,status,created_at', order: 'created_at' },
  worksheet: { table: 'worksheets', columns: 'id,user_id,title,subject,topic,learner_stage,level_or_band,worksheet_type,source_type,author_name,subject_display,is_public,status,created_at,updated_at', order: 'updated_at' },
  exam: { table: 'quick_exams', columns: 'id,user_id,title,subject,topic,learner_stage,level,exam_length,exercise_types,plan_language,student_material_language,is_public,status,created_at,updated_at', order: 'updated_at' },
  video: { table: 'videos', columns: 'id,user_id,title,subject,custom_subject_name,topic,description,video_id,youtube_url,thumbnail_url,learner_stage,level_or_band,student_material_language,is_public,status,created_at,updated_at', order: 'updated_at' },
};

function clean(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

function normalize(kind: PublicResourceKind, row: Record<string, unknown>): PublicResource {
  return {
    id: String(row.id ?? ''), kind,
    title: clean(row.title) || 'Untitled resource',
    subject: canonicalSubjectLabel(clean(row.subject_display) || clean(row.custom_subject_name) || clean(row.subject)),
    topic: clean(row.topic) || clean(row.lesson_purpose),
    stage: clean(row.learner_stage), level: clean(row.level_or_band) || clean(row.level),
    author: clean(row.author_name),
    description: clean(row.program_overview) || clean(row.description) || clean(row.lesson_purpose) || clean(row.worksheet_type) || clean(row.exam_length),
    imageUrl: extractResourceImageUrl(row),
    createdAt: clean(row.updated_at) || clean(row.created_at), raw: row,
  };
}

export async function getResourceLibrary(scope: ResourceScope): Promise<{ resources: PublicResource[]; unavailable: PublicResourceKind[] }> {
  const client = requireSupabase();
  const { data: userData } = await client.auth.getUser();
  if (scope !== 'community' && !userData.user) throw new Error('Your Classio session has expired.');
  const results = await Promise.all((Object.entries(DEFINITIONS) as [PublicResourceKind, (typeof DEFINITIONS)[PublicResourceKind]][]).map(async ([kind, definition]) => {
    let request = client.from(definition.table).select(definition.columns).order(definition.order, { ascending: false }).limit(1000);
    if (scope === 'community') request = request.eq('is_public', true).neq('status', 'archived');
    else if (scope === 'archive') request = request.eq('user_id', userData.user!.id).eq('status', 'archived');
    else request = request.eq('user_id', userData.user!.id).neq('status', 'archived');
    const { data, error } = await request;
    return { kind, rows: error ? [] : (data ?? []), failed: Boolean(error) };
  }));
  return {
    resources: results.flatMap((result) => result.rows.map((row) => normalize(result.kind, row as unknown as Record<string, unknown>))),
    unavailable: results.filter((result) => result.failed).map((result) => result.kind),
  };
}

export async function getResourceDetail(kind: PublicResourceKind, id: string): Promise<Record<string, unknown>> {
  const client = requireSupabase();
  const definition = DEFINITIONS[kind];
  const { data, error } = await client.from(definition.table).select('*').eq('id', id).maybeSingle();
  if (error) throw error;
  const record = (data ?? {}) as Record<string, unknown>;
  if (kind !== 'program' || !data) return record;
  const [{ data: units, error: unitsError }, { data: topics, error: topicsError }] = await Promise.all([
    client.from('learning_program_units').select('*').eq('program_id', id).order('unit_number'),
    client.from('learning_program_topics').select('*').eq('program_id', id).order('unit_number').order('topic_number'),
  ]);
  if (unitsError || topicsError) throw unitsError ?? topicsError;
  return { ...record, units: units ?? [], topics: topics ?? [] };
}

export async function updateResourceContent(kind: 'plan' | 'worksheet' | 'exam', id: string, content: Record<string, unknown>): Promise<void> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your Classio session has expired.');
  const payloadColumn = { plan: 'plan_json', worksheet: 'worksheet_json', exam: 'exam_data' }[kind];
  const document = kind === 'exam' ? content.exam_data : content;
  if (!document || typeof document !== 'object' || Array.isArray(document) || !Object.keys(document).length) throw new Error('Resource content cannot be empty.');
  const body = document as Record<string, unknown>;
  const filled = (value: unknown): boolean => typeof value === 'string' ? Boolean(value.trim()) : Array.isArray(value) ? value.some(filled) : Boolean(value && typeof value === 'object' && Object.values(value).some(filled));
  const fields = kind === 'plan' ? ['objective', 'objectives', 'lesson_flow', 'warm_up', 'main_activity', 'presentation', 'guided_practice', 'independent_practice', 'assessment', 'homework', 'activities'] : kind === 'worksheet' ? ['questions', 'matching_pairs', 'true_false_statements', 'multiple_choice_items', 'vocabulary_bank', 'sections', 'instructions', 'reading_passage', 'source_text'] : ['instructions', 'reading_text', 'source_text', 'passage'];
  if (kind === 'exam') {
    const sections = Array.isArray(body.sections) ? body.sections as Record<string, unknown>[] : [];
    if (!sections.length || !(sections.some((section) => filled(section.questions)) || fields.some((field) => filled(body[field])))) throw new Error('An exam needs questions or student instructions.');
  } else if (!fields.some((field) => filled(body[field]))) throw new Error('Keep the learning content when saving this resource.');
  const updates: Record<string, unknown> = { [payloadColumn]: document, updated_at: new Date().toISOString() };
  if (kind === 'exam') {
    const answerKey = content.answer_key;
    if (!answerKey || typeof answerKey !== 'object' || Array.isArray(answerKey)) throw new Error('An exam needs an answer key.');
    updates.answer_key = answerKey;
  }
  const { data, error } = await client.from(DEFINITIONS[kind].table).update(updates).eq('id', id).eq('user_id', userData.user.id).select('id').maybeSingle();
  if (error) throw error;
  if (!data) throw new Error('This resource is unavailable or cannot be edited.');
}

export async function getResourcePreviewImages(kind: PublicResourceKind, ids: string[]): Promise<Record<string, string>> {
  if (!ids.length || kind === 'video') return {};
  const payloadColumn: Record<Exclude<PublicResourceKind, 'video'>, string> = { program: 'program_data', plan: 'plan_json', worksheet: 'worksheet_json', exam: 'exam_data' };
  const column = payloadColumn[kind];
  const { data, error } = await requireSupabase().from(DEFINITIONS[kind].table).select(`id,${column}`).in('id', ids);
  if (error) return {};
  return Object.fromEntries(((data ?? []) as unknown as Record<string, unknown>[]).flatMap((row) => { const imageUrl = extractResourceImageUrl(row); return imageUrl ? [[String(row.id), imageUrl]] : []; }));
}

export async function updateResourceState(kind: PublicResourceKind, id: string, updates: { is_public?: boolean; status?: string }) {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from(DEFINITIONS[kind].table).update(updates).eq('id', id).eq('user_id', userData.user.id);
  if (error) throw error;
}

export async function updateResourceMetadata(kind: PublicResourceKind, id: string, updates: { title: string; topic?: string; subject?: string; learnerStage?: string; level?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const payload: Record<string, unknown> = { title: updates.title.trim() };
  if (kind !== 'program') payload.topic = updates.topic?.trim() || '';
  payload.subject = updates.subject?.trim() || '';
  payload.learner_stage = updates.learnerStage?.trim() || '';
  payload[kind === 'exam' ? 'level' : 'level_or_band'] = updates.level?.trim() || '';
  const { error } = await client.from(DEFINITIONS[kind].table).update(payload).eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}

export async function deleteResourcePermanently(kind: PublicResourceKind, id: string) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from(DEFINITIONS[kind].table).delete().eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}

function youtubeVideoId(value: string) {
  const match = value.trim().match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([A-Za-z0-9_-]{6,})/i);
  return match?.[1] || '';
}

export type VideoProgramOption = { id: string; title: string; subject: string; learnerStage: string; level: string; language: string; topics: { id: string; title: string; unitNumber: number; topicNumber: number }[] };

export async function getVideoProgramOptions(): Promise<VideoProgramOption[]> {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data: programs, error } = await client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,student_material_language,program_language').eq('user_id', userData.user.id).neq('status', 'archived').order('updated_at', { ascending: false }).limit(500); if (error) throw error;
  const ids = (programs ?? []).map((row) => row.id); const topicResult = ids.length ? await client.from('learning_program_topics').select('id,program_id,unit_number,topic_number,title,lesson_focus').in('program_id', ids).order('unit_number').order('topic_number') : { data: [], error: null }; if (topicResult.error) throw topicResult.error;
  return (programs ?? []).map((program) => ({ id: String(program.id), title: String(program.title || 'Learning program'), subject: String(program.custom_subject_name || program.subject || ''), learnerStage: String(program.learner_stage || ''), level: String(program.level_or_band || ''), language: String(program.student_material_language || program.program_language || 'English'), topics: (topicResult.data ?? []).filter((topic) => String(topic.program_id) === String(program.id)).map((topic) => ({ id: String(topic.id), title: String(topic.title || topic.lesson_focus || 'Topic'), unitNumber: Number(topic.unit_number || 0), topicNumber: Number(topic.topic_number || 0) })) }));
}

export async function addVideoResource(input: { youtubeUrl: string; title?: string; description?: string; subject: string; customSubject?: string; topic?: string; learnerStage: string; level: string; language: string; isPublic: boolean; programId?: string; topicId?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const videoId = youtubeVideoId(input.youtubeUrl); if (!videoId) throw new Error('Enter a valid YouTube video link.');
  const now = new Date().toISOString(); const { data: saved, error } = await client.from('videos').insert({ user_id: userData.user.id, title: input.title?.trim() || 'YouTube video', description: input.description?.trim() || '', subject: input.subject === 'Other' ? 'other' : input.subject.trim().toLowerCase().replace(/\s+/g, '_'), custom_subject_name: input.subject === 'Other' ? input.customSubject?.trim() || '' : '', topic: input.topic?.trim() || '', video_id: videoId, youtube_url: `https://www.youtube.com/watch?v=${videoId}`, thumbnail_url: `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`, learner_stage: input.learnerStage, level_or_band: input.level, student_material_language: input.language, is_public: input.isPublic, status: 'active', created_at: now, updated_at: now }).select('id').single();
  if (error || !saved) throw error ?? new Error('Video could not be saved.');
  if (input.programId && input.topicId) { const { error: linkError } = await client.from('learning_program_topic_videos').insert({ teacher_id: userData.user.id, program_id: Number(input.programId), topic_id: Number(input.topicId), video_id: Number(saved.id), created_at: now, updated_at: now }); if (linkError) throw linkError; }
}

function snapshotValue(value: unknown, depth = 0): unknown {
  if (depth > 5) return undefined; if (typeof value === 'string') return value.startsWith('data:') || value.length > 20000 ? undefined : value; if (Array.isArray(value)) return value.slice(0, 200).map((item) => snapshotValue(item, depth + 1)).filter((item) => item !== undefined); if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => { const normalized = key.toLowerCase(); if (normalized.includes('base64') || normalized.includes('image_data') || normalized.includes('thumbnail')) return []; const safe = snapshotValue(child, depth + 1); return safe === undefined ? [] : [[key, safe]]; })); return value;
}

export async function assignResource(input: { resource: PublicResource; detail: Record<string, unknown>; connection: TeacherConnection; dueDate?: string; teacherNote?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.'); const uid = userData.user.id;
  if (String(input.connection.status) !== 'active' || String(input.connection.teacher_id) !== uid) throw new Error('Choose an active student connection.');
  if (input.resource.kind === 'program') { const { error } = await client.from('learning_program_assignments').insert({ program_id: Number(input.resource.id), teacher_id: uid, student_user_id: String(input.connection.student_id), student_name: input.connection.student_name, assigned_by_user_id: uid, status: 'assigned', start_on: new Date().toISOString().slice(0, 10), target_completion_on: input.dueDate || null, teacher_note: input.teacherNote?.trim() || '' }); if (error) throw error; return; }
  const normalizedSubject = canonicalSubjectKey(input.resource.subject); const activeScopes = input.connection.subjects.filter((row) => String(row.status) === 'active'); const scope = activeScopes.find((row) => canonicalSubjectKey(row.subject_key || row.subject_label) === normalizedSubject) || activeScopes[0]; if (!scope) throw new Error('This connection has no active subject scope.');
  const typeMap = { plan: 'lesson_plan_topic', worksheet: 'worksheet', exam: 'exam', video: 'video' } as const; const sourceMap = { plan: 'lesson_plan_builder', worksheet: 'worksheet_builder', exam: 'exam_builder', video: 'video_library' } as const; const kind = input.resource.kind as keyof typeof typeMap; const now = new Date().toISOString();
  const { error } = await client.from('teacher_assignments').insert({ link_id: input.connection.id, subject_scope_id: scope.id, teacher_id: uid, student_id: input.connection.student_id, assignment_type: typeMap[kind], source_type: sourceMap[kind], source_record_id: Number(input.resource.id), title: input.resource.title, subject_key: canonicalSubjectKey(scope.subject_key || normalizedSubject), subject_label: canonicalSubjectLabel(scope.subject_label || input.resource.subject), topic: input.resource.topic || '', teacher_note: input.teacherNote?.trim() || '', content_snapshot: snapshotValue(input.detail) || {}, status: 'assigned', due_at: input.dueDate ? new Date(`${input.dueDate}T00:00:00Z`).toISOString() : null, assigned_at: now, created_at: now, updated_at: now }); if (error) throw error;
}
