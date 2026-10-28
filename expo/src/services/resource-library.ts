import { hasCustomBranding } from '@/services/branding';
import { requireSupabase } from '@/lib/supabase';
import { materialFromAssignment } from '@/services/student-practice';
import { buildAssignmentSnapshot } from '@/services/assignment-snapshot';
import { programReady } from '@/shared/program-completion';
import { worksheetHasSource, worksheetReferencesSource } from '@/lib/worksheet-source';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { youtubeVideoId } from '@/lib/youtube';
import { canonicalChoice } from '@/services/student-practice-answer-normalization';
import { extractResourceImageUrl, type PublicResource, type PublicResourceKind } from '@/services/public-data';
import type { TeacherConnection } from '@/services/teacher-students';

export type ResourceScope = 'mine' | 'community' | 'archive';

export type SavedPublicResource = { resource_kind: PublicResourceKind; resource_id: string };

export async function getSavedPublicResources(): Promise<SavedPublicResource[]> {
  const { data, error } = await requireSupabase().from('classio_saved_public_resources')
    .select('resource_kind,resource_id');
  if (error) throw error;
  return (data || []) as SavedPublicResource[];
}

export async function savePublicResource(kind: PublicResourceKind, id: string): Promise<void> {
  const { error } = await requireSupabase().rpc('classio_save_public_resource', { p_kind: kind, p_resource_id: id });
  if (error) throw error;
}

export async function removeSavedPublicResource(kind: PublicResourceKind, id: string): Promise<void> {
  const { error } = await requireSupabase().from('classio_saved_public_resources')
    .delete().eq('resource_kind', kind).eq('resource_id', id);
  if (error) throw error;
}

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
  const resources = results.flatMap((result) => result.rows.map((row) => normalize(result.kind, row as unknown as Record<string, unknown>)));
  // A bookmarked public resource may have fallen outside the latest 1,000 rows.
  if (scope === 'community' && userData.user) {
    const saved = await getSavedPublicResources();
    const present = new Set(resources.map((item) => `${item.kind}:${item.id}`));
    for (const [kind, definition] of Object.entries(DEFINITIONS) as [PublicResourceKind, (typeof DEFINITIONS)[PublicResourceKind]][]) {
      const missing = saved.filter((item) => item.resource_kind === kind && !present.has(`${kind}:${item.resource_id}`)).map((item) => item.resource_id);
      for (let offset = 0; offset < missing.length; offset += 50) {
        const { data, error } = await client.from(definition.table).select(definition.columns)
          .in('id', missing.slice(offset, offset + 50)).eq('is_public', true).neq('status', 'archived');
        if (error) throw error;
        for (const row of data ?? []) {
          const item = normalize(kind, row as unknown as Record<string, unknown>);
          if (!present.has(`${kind}:${item.id}`)) { resources.push(item); present.add(`${kind}:${item.id}`); }
        }
      }
    }
  }
  return { resources, unavailable: results.filter((result) => result.failed).map((result) => result.kind) };
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

export async function saveLearningProgramUnit(programId: string, unitId: string, changes: { title: string; overview: string; unitObjectives: string[]; deliveryNotes: string[]; topicChanges: { id: string; title: string; subtopic: string; studentSummary: string }[] }): Promise<void> {
  const client = requireSupabase();
  if (!changes.title.trim()) throw new Error('The unit needs a title.');
  if (changes.topicChanges.some((topic) => !topic.title.trim())) throw new Error('Every topic needs a title.');
  const { error } = await client.rpc('classio_save_learning_program_unit', {
    p_program_id: Number(programId),
    p_unit_id: Number(unitId),
    p_changes: changes,
  });
  if (error) throw error;
}

export async function updateResourceContent(kind: 'plan' | 'worksheet' | 'exam', id: string, content: Record<string, unknown>): Promise<void> {
  const client = requireSupabase();
  const { data: userData, error: userError } = await client.auth.getUser();
  if (userError || !userData.user) throw userError ?? new Error('Your Classio session has expired.');
  const payloadColumn = { plan: 'plan_json', worksheet: 'worksheet_json', exam: 'exam_data' }[kind];
  const document = kind === 'exam' ? content.exam_data : content;
  if (!document || typeof document !== 'object' || Array.isArray(document) || !Object.keys(document).length) throw new Error('Resource content cannot be empty.');
  const body = document as Record<string, unknown>;
  if (kind === 'plan') {
    if (typeof body.objective !== 'string' || !body.objective.trim()) throw new Error('The lesson plan needs an objective.');
    if (!body.core_material || typeof body.core_material !== 'object' || Array.isArray(body.core_material)) throw new Error('The lesson plan needs valid teaching materials.');
    if (body.recommended_level !== undefined && !['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'beginner_band', 'intermediate_band', 'advanced_band'].includes(String(body.recommended_level))) throw new Error('Choose a valid recommended level.');
    const listFields = ['success_criteria', 'warm_up', 'main_activity', 'guided_practice', 'freer_task', 'wrap_up', 'core_examples', 'practice_questions', 'teacher_moves'];
    for (const field of listFields) {
      const value = body[field];
      if (value !== undefined && value !== null && (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || !item.trim()))) throw new Error(`Check the ${field.replaceAll('_', ' ')} list before saving.`);
    }
  }
  if (kind === 'worksheet') {
    const { data: originalRow, error: originalError } = await client.from('worksheets').select('worksheet_type,worksheet_json').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
    if (originalError) throw originalError;
    if (!originalRow) throw new Error('This worksheet is unavailable or cannot be edited.');
    const original = originalRow.worksheet_json && typeof originalRow.worksheet_json === 'object' && !Array.isArray(originalRow.worksheet_json) ? originalRow.worksheet_json as Record<string, unknown> : {};
    const worksheetType = String(original.worksheet_type || originalRow.worksheet_type || '').trim();
    if (body.worksheet_type !== undefined && String(body.worksheet_type).trim() !== worksheetType) throw new Error('The worksheet type cannot be changed in the content editor.');
    for (const field of ['title', 'subject', 'learner_stage', 'level_or_band', 'plan_language', 'student_material_language', 'source_type']) {
      if (original[field] !== undefined && body[field] !== undefined && body[field] !== original[field]) throw new Error(`Edit ${field.replaceAll('_', ' ')} in the resource settings.`);
    }
    for (const field of ['questions', 'items', 'prompts', 'sentences', 'statements', 'true_false_statements', 'multiple_choice_items', 'matching_pairs', 'left_items', 'right_items', 'vocabulary_words', 'words', 'vocabulary_bank', 'sections', 'teacher_notes']) {
      const next = body[field]; const previous = original[field];
      if (next !== undefined && !Array.isArray(next)) throw new Error(`${field.replaceAll('_', ' ')} must be a list.`);
      if (Array.isArray(previous) && previous.length && (!Array.isArray(next) || !next.length)) throw new Error(`Keep the ${field.replaceAll('_', ' ')} in this worksheet.`);
      if (Array.isArray(next) && next.some((item) => item === null || item === undefined || (typeof item === 'string' && !item.trim()) || (typeof item === 'object' && !Array.isArray(item) && !Object.keys(item).length))) throw new Error(`Check the ${field.replaceAll('_', ' ')} before saving.`);
    }
    const studentItems = ['questions', 'items', 'prompts', 'sentences', 'statements', 'true_false_statements', 'multiple_choice_items', 'matching_pairs', 'left_items', 'sections'].some((field) => Array.isArray(body[field]) && (body[field] as unknown[]).length > 0);
    if (!studentItems && worksheetType !== 'word_search_vocab') throw new Error('The worksheet needs at least one exercise.');
    if (worksheetType === 'word_search_vocab' && (!Array.isArray(body.vocabulary_bank) || body.vocabulary_bank.length < 2 || body.vocabulary_bank.some((word) => typeof word !== 'string' || !word.trim()))) throw new Error('A word search needs at least two valid words.');
    if (worksheetType === 'matching' && Array.isArray(body.left_items) && Array.isArray(body.right_items) && body.left_items.length !== body.right_items.length) throw new Error('Matching columns must have the same number of items.');
    if (worksheetType === 'reading_comprehension' && !String(body.reading_passage || body.source_text || '').trim()) throw new Error('Reading comprehension needs a reading text.');
    if (worksheetReferencesSource(body) && !worksheetHasSource(body)) throw new Error('Add the complete source text referenced by the questions before saving.');
    if (original.answer_key && !body.answer_key) throw new Error('Keep the worksheet answer key.');
    if (worksheetType === 'multiple_choice') {
      const oldItems = Array.isArray(original.multiple_choice_items) ? original.multiple_choice_items as Record<string, unknown>[] : [];
      const items = Array.isArray(body.multiple_choice_items) ? body.multiple_choice_items as Record<string, unknown>[] : [];
      const oldAnswers = oldItems.map((item) => String(item.answer || item.correct_answer || ''));
      const newAnswers = items.map((item) => String(item.answer || item.correct_answer || ''));
      const inlineChanged = JSON.stringify(oldAnswers) !== JSON.stringify(newAnswers);
      const keyChanged = JSON.stringify(original.answer_key || '') !== JSON.stringify(body.answer_key || '');
      const rawKey = body.answer_key;
      let keyAnswers = Array.isArray(rawKey) ? rawKey.map(String) : String(rawKey || '').split(/\n|;|\||,(?=\s*\d+[.):\-])/).map((part) => part.replace(/^\s*\d+[.):\-]\s*/, '').trim()).filter(Boolean);
      if (keyAnswers.length === 1 && items.length > 1) { const tokens = keyAnswers[0].split(/\s+/); if (tokens.length === items.length && tokens.every((token) => /^[A-Z]$/i.test(token))) keyAnswers = tokens; }
      if (keyChanged && keyAnswers.length !== items.length) throw new Error('The multiple-choice answer key must contain one answer for each question.');
      if (keyChanged && inlineChanged && items.some((item, index) => canonicalChoice(keyAnswers[index], Array.isArray(item.options) ? item.options.map(String) : []) !== canonicalChoice(newAnswers[index], Array.isArray(item.options) ? item.options.map(String) : []))) throw new Error('The question answers and answer key disagree. Make them match before saving.');
      if (keyChanged && !inlineChanged) body.multiple_choice_items = items.map((item, index) => ({ ...item, answer: keyAnswers[index] }));
      if (inlineChanged && !keyChanged) body.answer_key = newAnswers.map((answer, index) => `${index + 1}. ${answer}`).join('\n');
    }
  }
  const filled = (value: unknown): boolean => typeof value === 'string' ? Boolean(value.trim()) : Array.isArray(value) ? value.some(filled) : Boolean(value && typeof value === 'object' && Object.values(value).some(filled));
  const fields = kind === 'plan' ? ['objective', 'objectives', 'lesson_flow', 'warm_up', 'main_activity', 'presentation', 'guided_practice', 'independent_practice', 'assessment', 'homework', 'activities'] : kind === 'worksheet' ? ['questions', 'matching_pairs', 'true_false_statements', 'multiple_choice_items', 'vocabulary_bank', 'sections', 'instructions', 'reading_passage', 'source_text'] : ['instructions', 'reading_text', 'source_text', 'passage'];
  if (kind === 'exam') {
    const sections = Array.isArray(body.sections) ? body.sections as Record<string, unknown>[] : [];
    if (!sections.length || !(sections.some((section) => filled(section.questions)) || fields.some((field) => filled(body[field])))) throw new Error('An exam needs questions or student instructions.');
    for (const [index, section] of sections.entries()) {
      if (!section || typeof section !== 'object' || Array.isArray(section)) throw new Error(`Section ${index + 1} is invalid.`);
      if (typeof section.type !== 'string' || !section.type.trim()) throw new Error(`Choose an exercise type for section ${index + 1}.`);
      if (!Array.isArray(section.questions)) throw new Error(`Section ${index + 1} needs a valid question list.`);
      if (!section.questions.length) throw new Error(`Section ${index + 1} needs at least one question.`);
      if (String(section.type) === 'reading_comprehension' && !String(section.source_text || '').trim()) throw new Error(`Section ${index + 1} needs the reading text referenced by its questions.`);
      for (const [questionIndex, question] of section.questions.entries()) {
        if (typeof question !== 'string' && (!question || typeof question !== 'object' || Array.isArray(question))) throw new Error(`Question ${questionIndex + 1} in section ${index + 1} is invalid.`);
        const row = typeof question === 'string' ? {} : question as Record<string, unknown>;
        const prompt = typeof question === 'string' ? question : String(row.stem || row.text || row.question || row.sentence || row.prompt || row.original || row.word || row.term || '');
        if (String(section.type) === 'matching' ? !String(row.left || '').trim() || !String(row.right || '').trim() : !prompt.trim()) throw new Error(`Question ${questionIndex + 1} in section ${index + 1} needs its prompt.`);
        if (row.options !== undefined && (!Array.isArray(row.options) || row.options.some((option) => typeof option !== 'string' || !option.trim()))) throw new Error(`Check the choices for question ${questionIndex + 1} in section ${index + 1}.`);
      }
    }
  } else if (!fields.some((field) => filled(body[field]))) throw new Error('Keep the learning content when saving this resource.');
  // Legacy lesson-plan rows do not consistently expose updated_at; Streamlit saves
  // plan_json without requiring that column.
  const updates: Record<string, unknown> = { [payloadColumn]: document };
  if (kind !== 'plan') updates.updated_at = new Date().toISOString();
  if (kind === 'exam') {
    const answerKey = content.answer_key;
    if (!answerKey || typeof answerKey !== 'object' || Array.isArray(answerKey)) throw new Error('An exam needs an answer key.');
    const sections = body.sections as Record<string, unknown>[];
    const keyedSections = (answerKey as Record<string, unknown>).sections;
    if (!Array.isArray(keyedSections) || keyedSections.length !== sections.length) throw new Error('Every exam section needs a matching answer key.');
    for (const [index, section] of sections.entries()) {
      const questions = section.questions as unknown[];
      const keySection = keyedSections[index];
      const answers = keySection && typeof keySection === 'object' && !Array.isArray(keySection) ? (keySection as Record<string, unknown>).answers : null;
      if (!Array.isArray(answers) || answers.length !== questions.length) throw new Error(`Section ${index + 1} needs one answer per question.`);
      if (answers.some((answer) => answer === null || answer === undefined || (typeof answer === 'string' && !answer.trim()))) throw new Error(`Complete the answer key for section ${index + 1}.`);
      if (String(section.type) === 'multiple_choice') for (const [questionIndex, question] of questions.entries()) {
        const options = question && typeof question === 'object' && !Array.isArray(question) ? (question as Record<string, unknown>).options : null;
        if (!Array.isArray(options) || options.length < 2 || options.some((option) => typeof option !== 'string' || !option.trim())) throw new Error(`Question ${questionIndex + 1} in section ${index + 1} needs at least two valid choices.`);
        const canonicalAnswer = canonicalChoice(String(answers[questionIndex]), options.map(String));
        if (!options.some((option) => canonicalChoice(option, options.map(String)) === canonicalAnswer)) throw new Error(`Question ${questionIndex + 1} in section ${index + 1} has an invalid correct choice.`);
      }
    }
    updates.answer_key = answerKey;
  }
  const { data, error } = await client.from(DEFINITIONS[kind].table).update(updates).eq('id', id).eq('user_id', userData.user.id).select('id').maybeSingle();
  if (error) throw error;
  if (!data) throw new Error('This resource is unavailable or cannot be edited.');
}

// Regrading is a separate operation: a failure here must never make an already
// committed resource edit look like a failed save or invite a duplicate save.
export async function refreshResourceScores(kind: 'worksheet' | 'exam', id: string): Promise<void> {
  const { data: sessionData } = await requireSupabase().auth.getSession();
  const accessToken = sessionData.session?.access_token;
  if (!accessToken) throw new Error('Your Classio session has expired.');
  let cursor = 0;
  do {
    const response = await fetch('/api/practice-regrade', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` }, body: JSON.stringify({ kind: 'resource', resourceKind: kind, resourceId: id, cursor }) });
    const result = await response.json().catch(() => null) as { nextCursor?: number | null; error?: string } | null;
    if (!response.ok) throw new Error(result?.error || 'Previous student scores could not be refreshed.');
    const next = Number(result?.nextCursor || 0);
    if (next && (!Number.isSafeInteger(next) || next <= cursor)) throw new Error('Score refresh stopped at an invalid cursor.');
    cursor = next;
  } while (cursor);
}

export async function refineResourceContent(kind: 'plan' | 'worksheet' | 'exam', id: string, prompt: string): Promise<Record<string, unknown>> {
  const { data } = await requireSupabase().auth.getSession();
  if (!data.session?.access_token) throw new Error('Your Classio session has expired.');
  const response = await fetch('/api/resource-refine', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify({ kind, id, prompt }) });
  const result = await response.json() as { document?: Record<string, unknown>; error?: string };
  if (!response.ok || !result.document) throw new Error(result.error || 'Classio could not refine this resource.');
  return result.document;
}

export async function generateLessonPlanCover(id: string, kind: 'plan' | 'worksheet' | 'exam' = 'plan'): Promise<Record<string, unknown>> {
  const { data } = await requireSupabase().auth.getSession();
  if (!data.session?.access_token) throw new Error('Your Classio session has expired.');
  const response = await fetch('/api/lesson-plan-cover', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify({ id, kind }) });
  const result = await response.json() as { cover_image?: Record<string, unknown>; error?: string; code?: string };
  if (!response.ok || !result.cover_image) throw new Error(result.code === 'image_provider_credit' ? 'image_provider_credit' : result.error || 'Classio could not generate the image.');
  return result.cover_image;
}

export async function saveLessonPlanCover(id: string, cover: Record<string, unknown>, kind: 'plan' | 'worksheet' | 'exam' = 'plan'): Promise<void> {
  const client = requireSupabase();
  const operationId = typeof cover.operation_id === 'string' ? cover.operation_id : '';
  if (!operationId) throw new Error('The image generation reference is missing.');
  const { error } = await client.rpc('classio_save_generated_cover', {
    p_resource_type: kind,
    p_resource_id: id,
    p_operation_id: operationId,
    p_cover: cover,
  });
  if (error) throw error;
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
  if (kind !== 'video' && updates.is_public === true && await hasCustomBranding()) throw new Error('Turn off custom branding before making this document public.');
  if (kind === 'program' && updates.is_public === true) {
    const { data: program, error } = await client.from('learning_programs').select('program_data').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
    if (error || !program || !programReady(program.program_data as Record<string, unknown>)) throw error ?? new Error('Complete every program unit before publishing.');
  }
  const archiveChange = updates.status === 'archived' || updates.status === 'active';
  let payload = updates.status === 'archived' ? { ...updates, is_public: false } : updates;
  if (kind === 'program' && updates.status === 'active') {
    const { data: program, error: programError } = await client.from('learning_programs').select('program_data').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
    if (programError || !program) throw programError ?? new Error('The program is unavailable.');
    if (!programReady(program.program_data as Record<string, unknown>)) payload = { ...payload, status: 'draft', is_public: false };
  }
  const { data, error } = await client.from(DEFINITIONS[kind].table).update(payload).eq('id', id).eq('user_id', userData.user.id).select('id').maybeSingle();
  if (error || !data) throw error ?? new Error('Only the owner can change this resource.');
  const assignmentSource = { plan: ['lesson_plan_topic', 'lesson_plan_builder'], worksheet: ['worksheet', 'worksheet_builder'], exam: ['exam', 'exam_builder'], video: ['video', 'video_library'] } as const;
  if (archiveChange && kind !== 'program') {
    const [assignmentType, sourceType] = assignmentSource[kind];
    // Older databases may not have these additive columns. Keep the resource
    // change successful, matching the Streamlit archive behavior.
    await client.from('teacher_assignments').update({ source_archived: updates.status === 'archived', source_archived_at: updates.status === 'archived' ? new Date().toISOString() : null, updated_at: new Date().toISOString() }).eq('teacher_id', userData.user.id).eq('assignment_type', assignmentType).eq('source_type', sourceType).eq('source_record_id', id);
  }
}

export async function updateResourceMetadata(kind: PublicResourceKind, id: string, updates: { title: string; topic?: string; subject?: string; learnerStage?: string; level?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  if (!updates.title.trim()) throw new Error('A title is required.');
  if (kind === 'program') {
    const stages = new Set(['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage']);
    const languageLevels = new Set(['A1', 'A2', 'B1', 'B2', 'C1', 'C2']);
    const academicLevels = new Set(['beginner_band', 'intermediate_band', 'advanced_band']);
    const { data: current, error: currentError } = await client.from('learning_programs').select('id,subject,program_data').eq('id', id).eq('user_id', userData.user.id).maybeSingle();
    if (currentError || !current) throw currentError ?? new Error('This program is unavailable.');
    const stage = updates.learnerStage?.trim() || '';
    const level = updates.level?.trim() || '';
    const isLanguage = ['english', 'spanish', 'turkish'].includes(canonicalSubjectKey(current.subject));
    if (!stages.has(stage) || !(isLanguage ? languageLevels : academicLevels).has(level)) throw new Error('Choose a valid learner stage and level.');
    const document = current.program_data && typeof current.program_data === 'object' && !Array.isArray(current.program_data) ? current.program_data as Record<string, unknown> : {};
    const { data: saved, error } = await client.from('learning_programs').update({ title: updates.title.trim(), learner_stage: stage, level_or_band: level, program_data: { ...document, title: updates.title.trim(), learner_stage: stage, level_or_band: level }, updated_at: new Date().toISOString() }).eq('id', id).eq('user_id', userData.user.id).select('id').maybeSingle();
    if (error || !saved) throw error ?? new Error('This program could not be updated.');
    return;
  }
  const payload: Record<string, unknown> = { title: updates.title.trim() };
  payload.topic = updates.topic?.trim() || '';
  payload.subject = updates.subject?.trim() || '';
  payload.learner_stage = updates.learnerStage?.trim() || '';
  payload[kind === 'exam' ? 'level' : 'level_or_band'] = updates.level?.trim() || '';
  const { error } = await client.from(DEFINITIONS[kind].table).update(payload).eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}

export async function deleteResourcePermanently(kind: PublicResourceKind, id: string) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { error } = await client.from(DEFINITIONS[kind].table).delete().eq('id', id).eq('user_id', userData.user.id); if (error) throw error;
}

export { youtubeVideoId };

const VIDEO_STAGES = new Set(['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage']);
const VIDEO_LANGUAGE_LEVELS = new Set(['A1', 'A2', 'B1', 'B2', 'C1', 'C2']);
const VIDEO_ACADEMIC_LEVELS = new Set(['beginner_band', 'intermediate_band', 'advanced_band']);
const VIDEO_LANGUAGES = new Set(['en', 'es', 'tr']);
function videoStage(value: string) { const key = value.trim().toLowerCase().replaceAll(' ', '_'); return key === 'adult' ? 'adult_stage' : key; }
function videoLevel(value: string) { const key = value.trim().toLowerCase(); return ['beginner', 'intermediate', 'advanced'].includes(key) ? `${key}_band` : value.trim(); }
function videoLanguage(value: string) { const key = value.trim().toLowerCase(); return ({ english: 'en', spanish: 'es', turkish: 'tr' } as Record<string, string>)[key] || key; }
function videoMetadata(input: { subject: string; customSubject?: string; topic?: string; learnerStage: string; level: string; language: string }, linked?: VideoProgramOption, linkedTopic?: VideoProgramOption['topics'][number]) {
  const subject = linked?.subject || input.subject;
  const subjectKey = canonicalSubjectKey(subject);
  const stage = videoStage(linked?.learnerStage || input.learnerStage);
  const level = videoLevel(linked?.level || input.level);
  const language = videoLanguage(input.language || linked?.language || '');
  if (!subjectKey || !VIDEO_STAGES.has(stage) || !(subjectKey === 'english' || subjectKey === 'spanish' || subjectKey === 'turkish' ? VIDEO_LANGUAGE_LEVELS : VIDEO_ACADEMIC_LEVELS).has(level) || !VIDEO_LANGUAGES.has(language)) throw new Error('resources.videoInvalidMetadata');
  const customSubject = subjectKey === 'other' ? (linked?.customSubject || input.customSubject || '').trim() : '';
  if (subjectKey === 'other' && !customSubject) throw new Error('resources.videoInvalidMetadata');
  return { subject: subjectKey, custom_subject_name: customSubject, topic: linkedTopic?.title || input.topic?.trim() || '', learner_stage: stage, level_or_band: level, student_material_language: language };
}

export type VideoProgramOption = { id: string; title: string; subject: string; customSubject: string; learnerStage: string; level: string; language: string; topics: { id: string; title: string; unitNumber: number; topicNumber: number }[] };

export async function getVideoProgramOptions(): Promise<VideoProgramOption[]> {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const { data: programs, error } = await client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,student_material_language,program_language').eq('user_id', userData.user.id).neq('status', 'archived').order('updated_at', { ascending: false }).limit(500); if (error) throw error;
  const ids = (programs ?? []).map((row) => row.id); const topicResult = ids.length ? await client.from('learning_program_topics').select('id,program_id,unit_number,topic_number,title,lesson_focus').in('program_id', ids).order('unit_number').order('topic_number') : { data: [], error: null }; if (topicResult.error) throw topicResult.error;
  return (programs ?? []).map((program) => ({ id: String(program.id), title: String(program.title || 'Learning program'), subject: String(program.subject || ''), customSubject: String(program.custom_subject_name || ''), learnerStage: String(program.learner_stage || ''), level: String(program.level_or_band || ''), language: String(program.student_material_language || program.program_language || 'English'), topics: (topicResult.data ?? []).filter((topic) => String(topic.program_id) === String(program.id)).map((topic) => ({ id: String(topic.id), title: String(topic.title || topic.lesson_focus || 'Topic'), unitNumber: Number(topic.unit_number || 0), topicNumber: Number(topic.topic_number || 0) })) }));
}

export async function addVideoResource(input: { youtubeUrl: string; title?: string; description?: string; subject: string; customSubject?: string; topic?: string; learnerStage: string; level: string; language: string; isPublic: boolean; programId?: string; topicId?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const videoId = youtubeVideoId(input.youtubeUrl); if (!videoId) throw new Error('resources.videoInvalidUrl');
  if ((input.title || '').trim().length > 200 || (input.topic || '').trim().length > 200 || (input.description || '').trim().length > 5000) throw new Error('resources.videoInvalidMetadata');
  if (input.programId && !input.topicId) throw new Error('resources.videoChooseTopic');
  let linkedProgram: VideoProgramOption | undefined; let linkedTopic: VideoProgramOption['topics'][number] | undefined;
  if (input.programId) { linkedProgram = (await getVideoProgramOptions()).find((item) => item.id === input.programId); linkedTopic = linkedProgram?.topics.find((item) => item.id === input.topicId); if (!linkedProgram || !linkedTopic) throw new Error('resources.videoChooseTopic'); }
  const now = new Date().toISOString();
  const payload = { user_id: userData.user.id, title: input.title?.trim() || linkedTopic?.title || 'YouTube video', description: input.description?.trim() || '', ...videoMetadata(input, linkedProgram, linkedTopic), video_id: videoId, youtube_url: `https://www.youtube.com/watch?v=${videoId}`, thumbnail_url: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`, is_public: input.isPublic, status: 'active', updated_at: now };
  const existing = await client.from('videos').select('id').eq('user_id', userData.user.id).eq('video_id', videoId).maybeSingle(); if (existing.error) throw existing.error;
  let result = existing.data ? await client.from('videos').update(payload).eq('id', existing.data.id).eq('user_id', userData.user.id).select('id').single() : await client.from('videos').insert({ ...payload, created_at: now }).select('id').single();
  if (result.error?.code === '23505' && !existing.data) {
    const raced = await client.from('videos').select('id').eq('user_id', userData.user.id).eq('video_id', videoId).maybeSingle();
    if (raced.error) throw raced.error;
    if (raced.data) result = await client.from('videos').update(payload).eq('id', raced.data.id).eq('user_id', userData.user.id).select('id').single();
  }
  if (result.error || !result.data) throw result.error ?? new Error('resources.videoSaveFailed');
  if (linkedProgram && linkedTopic) {
    const link = await client.from('learning_program_topic_videos').select('id').eq('teacher_id', userData.user.id).eq('program_id', Number(linkedProgram.id)).eq('topic_id', Number(linkedTopic.id)).eq('video_id', Number(result.data.id)).maybeSingle(); if (link.error) throw link.error;
    if (!link.data) { const { error: linkError } = await client.from('learning_program_topic_videos').insert({ teacher_id: userData.user.id, program_id: Number(linkedProgram.id), topic_id: Number(linkedTopic.id), video_id: Number(result.data.id), created_at: now, updated_at: now }); if (linkError) throw linkError; }
  }
  return String(result.data.id);
}

export async function getVideoProgramLink(videoId: string): Promise<{ program: VideoProgramOption; topic: VideoProgramOption['topics'][number] } | null> {
  const client = requireSupabase(); const { data: userData } = await client.auth.getUser(); if (!userData.user) return null;
  const { data, error } = await client.from('learning_program_topic_videos').select('program_id,topic_id').eq('teacher_id', userData.user.id).eq('video_id', Number(videoId)).limit(1).maybeSingle(); if (error) throw error;
  if (!data) return null;
  const [programResult, topicResult] = await Promise.all([
    client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,student_material_language,program_language').eq('id', data.program_id).eq('user_id', userData.user.id).maybeSingle(),
    client.from('learning_program_topics').select('id,program_id,unit_number,topic_number,title,lesson_focus').eq('id', data.topic_id).eq('program_id', data.program_id).maybeSingle(),
  ]);
  if (programResult.error || topicResult.error) throw programResult.error ?? topicResult.error;
  if (!programResult.data || !topicResult.data) throw new Error('resources.videoLinkLookupFailed');
  const row = programResult.data; const topicRow = topicResult.data;
  const topic = { id: String(topicRow.id), title: String(topicRow.title || topicRow.lesson_focus || ''), unitNumber: Number(topicRow.unit_number || 0), topicNumber: Number(topicRow.topic_number || 0) };
  const program: VideoProgramOption = { id: String(row.id), title: String(row.title || ''), subject: String(row.subject || ''), customSubject: String(row.custom_subject_name || ''), learnerStage: String(row.learner_stage || ''), level: String(row.level_or_band || ''), language: String(row.student_material_language || row.program_language || ''), topics: [topic] };
  return { program, topic };
}

export async function updateVideoResource(id: string, input: { youtubeUrl: string; title: string; description: string; subject: string; customSubject?: string; topic: string; learnerStage: string; level: string; language: string; isPublic: boolean }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.');
  const videoId = youtubeVideoId(input.youtubeUrl); if (!videoId) throw new Error('resources.videoInvalidUrl');
  if (input.title.trim().length > 200 || input.topic.trim().length > 200 || input.description.trim().length > 5000) throw new Error('resources.videoInvalidMetadata');
  const { data: current, error } = await client.from('videos').select('id,video_id').eq('id', id).eq('user_id', userData.user.id).maybeSingle(); if (error || !current) throw error ?? new Error('resources.videoUnavailable');
  const linked = await getVideoProgramLink(id);
  if (videoId !== current.video_id) { const duplicate = await client.from('videos').select('id').eq('user_id', userData.user.id).eq('video_id', videoId).maybeSingle(); if (duplicate.error) throw duplicate.error; if (duplicate.data && String(duplicate.data.id) !== id) throw new Error('resources.videoAlreadySaved'); }
  const payload = { title: input.title.trim() || linked?.topic.title || 'YouTube video', description: input.description.trim(), ...videoMetadata(input, linked?.program, linked?.topic), video_id: videoId, youtube_url: `https://www.youtube.com/watch?v=${videoId}`, thumbnail_url: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`, is_public: input.isPublic, updated_at: new Date().toISOString() };
  const saved = await client.from('videos').update(payload).eq('id', id).eq('user_id', userData.user.id).select('id').maybeSingle(); if (saved.error || !saved.data) throw saved.error ?? new Error('resources.videoSaveFailed');
}

export async function assignResource(input: { resource: PublicResource; detail: Record<string, unknown>; connection: TeacherConnection; dueDate?: string; teacherNote?: string }) {
  const client = requireSupabase(); const { data: userData, error: userError } = await client.auth.getUser(); if (userError || !userData.user) throw userError ?? new Error('Your session has expired.'); const uid = userData.user.id;
  if (String(input.connection.status) !== 'active' || String(input.connection.teacher_id) !== uid) throw new Error('Choose an active student connection.');
  if (input.resource.kind === 'program') {
    if (!programReady(input.detail.program_data as Record<string, unknown>)) throw new Error('Complete every program unit before assigning it.');
    const rosterId = Number(input.connection.roster_student_id || 0);
    const studentId = String(input.connection.student_id || '');
    const existing = client.from('learning_program_assignments').select('id').eq('program_id', Number(input.resource.id)).eq('teacher_id', uid).neq('status', 'archived').limit(1);
    const duplicate = await (rosterId ? existing.eq('roster_student_id', rosterId) : existing.eq('student_user_id', studentId));
    if (duplicate.error) throw duplicate.error;
    if (duplicate.data?.length) throw new Error('resources.alreadyAssigned');
    if (rosterId) {
      const roster = await client.from('students').select('id,student,linked_student_user_id').eq('id', rosterId).eq('user_id', uid).maybeSingle();
      if (roster.error || !roster.data) throw roster.error ?? new Error('This student is unavailable.');
      const { error } = await client.from('learning_program_assignments').insert({ program_id: Number(input.resource.id), teacher_id: uid, roster_student_id: rosterId, student_user_id: roster.data.linked_student_user_id || null, student_name: roster.data.student, assigned_by_user_id: uid, status: 'assigned', start_on: new Date().toISOString().slice(0, 10), target_completion_on: input.dueDate || null, teacher_note: input.teacherNote?.trim() || '' });
      if (error) throw error;
      return;
    }
    const { error } = await client.from('learning_program_assignments').insert({ program_id: Number(input.resource.id), teacher_id: uid, student_user_id: studentId, student_name: input.connection.student_name, assigned_by_user_id: uid, status: 'assigned', start_on: new Date().toISOString().slice(0, 10), target_completion_on: input.dueDate || null, teacher_note: input.teacherNote?.trim() || '' });
    if (error) throw error;
    return;
  }
  const normalizedSubject = canonicalSubjectKey(input.resource.subject); const activeScopes = input.connection.subjects.filter((row) => String(row.status) === 'active'); const scope = activeScopes.find((row) => canonicalSubjectKey(row.subject_key || row.subject_label) === normalizedSubject); if (!scope) throw new Error(`This student is not connected for ${input.resource.subject || 'this subject'}.`);
  const typeMap = { plan: 'lesson_plan_topic', worksheet: 'worksheet', exam: 'exam', video: 'video' } as const; const sourceMap = { plan: 'lesson_plan_builder', worksheet: 'worksheet_builder', exam: 'exam_builder', video: 'video_library' } as const; const kind = input.resource.kind as keyof typeof typeMap; const now = new Date().toISOString();
  const parsedSourceId = Number(input.resource.id);
  const numericSourceId = Number.isSafeInteger(parsedSourceId) && parsedSourceId > 0 ? parsedSourceId : null;
  const existing = client.from('teacher_assignments').select('id').eq('teacher_id', uid).eq('student_id', input.connection.student_id).eq('assignment_type', typeMap[kind]).neq('status', 'archived').limit(1);
  const duplicate = await (numericSourceId ? existing.eq('source_record_id', numericSourceId) : existing.is('source_record_id', null).contains('content_snapshot', { id: input.resource.id }));
  if (duplicate.error) throw duplicate.error;
  if (duplicate.data?.length) throw new Error('resources.alreadyAssigned');
  const snapshot = buildAssignmentSnapshot(input.detail) as Record<string, unknown> || {};
  if (!numericSourceId) snapshot.id = input.resource.id;
  if ((kind === 'worksheet' || kind === 'exam') && !materialFromAssignment({ assignment_type: typeMap[kind], content_snapshot: snapshot })?.questions.length) throw new Error('resources.assignmentContentUnavailable');
  const { error } = await client.from('teacher_assignments').insert({ link_id: input.connection.id, subject_scope_id: scope.id, teacher_id: uid, student_id: input.connection.student_id, assignment_type: typeMap[kind], source_type: sourceMap[kind], source_record_id: numericSourceId, title: input.resource.title, subject_key: canonicalSubjectKey(scope.subject_key || normalizedSubject), subject_label: canonicalSubjectLabel(scope.subject_label || input.resource.subject), topic: input.resource.topic || '', teacher_note: input.teacherNote?.trim() || '', content_snapshot: snapshot, status: 'assigned', due_at: input.dueDate ? new Date(`${input.dueDate}T00:00:00Z`).toISOString() : null, assigned_at: now, created_at: now, updated_at: now }); if (error) throw error;
}
