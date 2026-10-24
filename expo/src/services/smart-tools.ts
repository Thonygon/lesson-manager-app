import { hasCustomBranding } from '@/services/branding';
import { requireSupabase } from '@/lib/supabase';
import { programTopicRow, programUnitRow } from './program-storage';
import { nextProgramSequenceOrder } from '../shared/program-structure';
import { mergePreviousProgramRows, previousProgramComplete, previousProgramFromStorage } from '../server/program-continuation';
import { findGenerationMatches, type GenerationMatch } from '@/server/generation-reuse';
import { programReady } from '../shared/program-completion';
import { uniqueProgramTopics } from '@/lib/learning-program-topics';

export type SmartToolKind = 'plan' | 'worksheet' | 'exam' | 'program';
export type SmartToolInput = { kind: SmartToolKind; subject: string; customSubject?: string; topic: string; stage: string; level: string; language: string; planLanguage?: string; nativeLanguage?: string; generationMode?: string; generationId?: string; lessonPurpose?: string; objective?: string; worksheetType?: string; examTitle?: string; examLength?: string; exerciseTypes?: string[]; instructions?: string; requestedUnits?: number; requestedLessons?: number; visibility?: string; programTrack?: string; examTarget?: string; duration: string; questionCount?: number; notes: string; programId?: string; programTopicId?: string; previousProgramId?: string; reuseConfirmed?: boolean };
export class GenerationReuseError extends Error {
  constructor(public readonly matches: GenerationMatch[], message: string) { super(message); this.name = 'GenerationReuseError'; }
}
export class GenerationRequestError extends Error {
  constructor(public readonly status: number, public readonly code: string, public readonly phase: string, message?: string) { super(message || code); this.name = 'GenerationRequestError'; }
}
export type GeneratedMaterial = { document: Record<string, unknown>; model: string; generatedAt: string; generationId?: string; fallbackReason?: 'ai_unavailable' };

async function generationFeedbackRequest(path: string, body?: Record<string, unknown>) {
  const client = requireSupabase(); const { data, error } = await client.auth.getSession();
  if (error || !data.session) throw error ?? new Error('Your session has expired.');
  const response = await fetch(`/api/generation-feedback${path}`, { method: body ? 'POST' : 'GET', headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), Authorization: `Bearer ${data.session.access_token}` }, body: body ? JSON.stringify(body) : undefined, cache: 'no-store' });
  const payload = await response.json().catch(() => ({})) as { error?: string; eligible?: boolean; generationId?: string; satisfied?: boolean | null; reason?: string | null };
  if (!response.ok) throw new Error(payload.error || 'Generation feedback is unavailable.');
  return payload;
}

export async function bindGeneratedResource(generationId: string, resourceType: SmartToolKind, resourceId: string) {
  await generationFeedbackRequest('', { action: 'bind', generationId, resourceType, resourceId });
}

export async function getGenerationFeedbackForResource(resourceType: SmartToolKind, resourceId: string) {
  return generationFeedbackRequest(`?resourceType=${encodeURIComponent(resourceType)}&resourceId=${encodeURIComponent(resourceId)}`);
}

export async function saveGenerationIntentFeedback(generationId: string, satisfied: boolean, surface: 'generation_preview' | 'resource_page', reason?: 'content' | 'level' | 'format' | 'other'): Promise<void> {
  await generationFeedbackRequest('', { generationId, satisfied, surface, reason });
}

export async function discardUnsavedGeneration(generationId: string): Promise<void> {
  const { error } = await requireSupabase().rpc('classio_record_unsaved_generation_decision', { p_operation_id: generationId });
  if (error) throw error;
}

export type SmartToolProgram = { id: string; title: string; subject: string; customSubject: string; stage: string; level: string; sequenceGroupId: string; sequenceOrder: number };
export type SmartToolProgramTopic = { id: string; title: string; unitTitle: string; unitNumber: number; topicNumber: number; lessonPurpose: string; learningObjectives: string[]; suggestedWorksheetTypes: string[]; suggestedExamTypes: string[] };
export type PersonalizationStudent = { id: string; name: string; nativeLanguage: string };

export async function getPersonalizationStudents(): Promise<PersonalizationStudent[]> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const { data, error } = await client.from('students').select('id,student,linked_student_user_id,native_language').eq('user_id', auth.user.id).order('student').limit(500);
  if (error) throw error;
  return (data ?? []).map((row) => ({ id: String(row.linked_student_user_id || `roster:${row.id}`), name: String(row.student || 'Student'), nativeLanguage: String(row.native_language || '') }));
}

export async function getSmartToolPrograms(): Promise<SmartToolProgram[]> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const { data, error } = await client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,sequence_group_id,sequence_order').eq('user_id', auth.user.id).neq('status', 'archived').order('updated_at', { ascending: false }).limit(200);
  if (error) throw error;
  return (data ?? []).map((row) => ({ id: String(row.id), title: String(row.title || ''), subject: String(row.subject || ''), customSubject: String(row.custom_subject_name || ''), stage: String(row.learner_stage || ''), level: String(row.level_or_band || ''), sequenceGroupId: String(row.sequence_group_id || ''), sequenceOrder: Number(row.sequence_order || 0) }));
}

export async function getSmartToolProgramTopics(programId: string): Promise<SmartToolProgramTopic[]> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const { data: program, error: programError } = await client.from('learning_programs').select('id').eq('id', programId).eq('user_id', auth.user.id).neq('status', 'archived').maybeSingle();
  if (programError) throw programError;
  if (!program) throw new Error('The selected program is unavailable.');
  const [unitsResult, topicsResult] = await Promise.all([
    client.from('learning_program_units').select('unit_number,title').eq('program_id', programId).order('unit_number').limit(200),
    client.from('learning_program_topics').select('id,unit_number,topic_number,title,lesson_focus,lesson_purpose,learning_objectives,suggested_worksheet_types,suggested_exam_exercise_types').eq('program_id', programId).order('unit_number').order('topic_number').limit(500),
  ]);
  if (unitsResult.error || topicsResult.error) throw unitsResult.error ?? topicsResult.error;
  const unitTitles = new Map((unitsResult.data ?? []).map((row) => [Number(row.unit_number), String(row.title || '')]));
  const list = (value: unknown): string[] => Array.isArray(value) ? value.map(String).filter(Boolean) : [];
  return (topicsResult.data ?? []).map((row) => ({ id: String(row.id), title: String(row.title || row.lesson_focus || ''), unitTitle: unitTitles.get(Number(row.unit_number)) || '', unitNumber: Number(row.unit_number || 0), topicNumber: Number(row.topic_number || 0), lessonPurpose: String(row.lesson_purpose || ''), learningObjectives: list(row.learning_objectives), suggestedWorksheetTypes: list(row.suggested_worksheet_types), suggestedExamTypes: list(row.suggested_exam_exercise_types) }));
}

export async function getSmartToolPreviousProgramComplete(programId: string): Promise<boolean> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const { data: program, error } = await client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,program_data').eq('id', programId).eq('user_id', auth.user.id).neq('status', 'archived').maybeSingle();
  if (error || !program) throw error ?? new Error('The previous program is unavailable.');
  const [units, topics] = await Promise.all([
    client.from('learning_program_units').select('unit_number,title,overview,unit_objectives,recommended_lesson_purposes,recommended_worksheet_types,recommended_exam_exercise_types,estimated_lessons').eq('program_id', programId).order('unit_number').limit(200),
    client.from('learning_program_topics').select('unit_number,topic_number,title,subtopic,lesson_focus,lesson_purpose,learning_objectives,success_criteria,student_can_do,suggested_worksheet_types,suggested_exam_exercise_types,homework_idea,teacher_notes,student_summary,estimated_lessons').eq('program_id', programId).order('unit_number').order('topic_number').limit(500),
  ]);
  if (units.error || topics.error) throw units.error ?? topics.error;
  return previousProgramComplete(mergePreviousProgramRows(previousProgramFromStorage(program as Record<string, unknown>), units.data, topics.data));
}

export async function getSimilarTeachingResources(input: SmartToolInput): Promise<GenerationMatch[]> {
  if (input.kind !== 'program' && !input.topic.trim()) return [];
  const client = requireSupabase();
  const { data, error } = await client.auth.getSession();
  if (error || !data.session) throw error ?? new Error('Your Classio session has expired.');
  const base = process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const key = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const subject = input.subject === 'Other' ? input.customSubject?.trim() || '' : input.subject.toLowerCase().replaceAll(' ', '_');
  return findGenerationMatches(base, key, data.session.access_token, data.session.user.id, { kind: input.kind, subject, topic: input.topic.trim(), stage: input.stage, level: input.level, lessonPurpose: input.lessonPurpose, worksheetType: input.worksheetType, exerciseTypes: input.exerciseTypes, programTrack: input.programTrack, examTarget: input.examTarget });
}

export async function generateMaterial(input: SmartToolInput, onProgress?: (message: string) => void, studentNameForRedaction = '', studentIdForEvidence = ''): Promise<GeneratedMaterial> {
  const client = requireSupabase(); const { data, error } = await client.auth.getSession(); if (error || !data.session) throw error ?? new Error('Sign in to generate teaching material.');
  const request = async (body: Record<string, unknown>): Promise<GeneratedMaterial> => {
    const response = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify({ ...body, studentNameForRedaction, studentIdForEvidence }) });
    const payload = await response.json().catch(() => ({})) as GeneratedMaterial & { error?: string; code?: string; phase?: string; matches?: GenerationMatch[] };
    if (response.status === 409 && payload.matches?.length) throw new GenerationReuseError(payload.matches, payload.error || 'Similar resources already exist.');
    if (!response.ok) throw new GenerationRequestError(response.status, payload.code || (response.status >= 500 ? 'generation_failed' : 'request_failed'), payload.phase || '', payload.error);
    return payload;
  };
  if (input.kind !== 'program') return request(input);
  onProgress?.('Building the program scope and sequence…');
  const skeletonResult = await request({ ...input, programPhase: 'skeleton' });
  const skeleton = skeletonResult.document;
  return skeletonResult;
}


export async function generateProgramUnit(input: SmartToolInput, skeleton: Record<string, unknown>, unitIndex: number, studentNameForRedaction = '', studentIdForEvidence = ''): Promise<{ document: Record<string, unknown>; generationId?: string }> {
  const client = requireSupabase();
  const { data, error } = await client.auth.getSession();
  if (error || !data.session) throw error ?? new Error('Sign in to continue the program.');
  const units = Array.isArray(skeleton.units) ? skeleton.units as Record<string, unknown>[] : [];
  const unit = units[unitIndex];
  if (!unit || !Number.isSafeInteger(unitIndex) || unitIndex < 0) throw new Error('Choose a valid program unit.');
  const response = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify({ ...input, programPhase: 'unit', programSkeleton: skeleton, programUnitIndex: unitIndex, reuseConfirmed: true, studentNameForRedaction, studentIdForEvidence }) });
  const payload = await response.json().catch(() => ({})) as GeneratedMaterial & { error?: string; code?: string; phase?: string };
  if (!response.ok) throw new GenerationRequestError(response.status, payload.code || 'generation_failed', payload.phase || '', payload.error);
  const details = payload.document;
  const baseTopics = Array.isArray(unit.topics) ? unit.topics as Record<string, unknown>[] : [];
  const detailTopics = Array.isArray(details.topics) ? details.topics as Record<string, unknown>[] : [];
  const mergedUnit = { ...unit, ...details, unit_number: unitIndex + 1, title: unit.title, overview: unit.overview, topics: baseTopics.map((topic, index) => ({ ...topic, ...(detailTopics[index] || {}), topic_number: index + 1, title: topic.title, lesson_purpose: topic.lesson_purpose })) };
  return { document: { ...skeleton, units: units.map((current, index) => index === unitIndex ? mergedUnit : current) }, generationId: payload.generationId };
}

export async function syncGeneratedProgramUnit(id: string, document: Record<string, unknown>, unitIndex: number, generationId?: string): Promise<void> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const units = Array.isArray(document.units) ? document.units as Record<string, unknown>[] : [];
  const unit = units[unitIndex];
  if (!unit) throw new Error('The generated unit is missing.');
  const unitNumber = unitIndex + 1;
  const { data: owned, error: ownedError } = await client.from('learning_programs').select('id,status').eq('id', id).eq('user_id', auth.user.id).neq('status', 'archived').maybeSingle();
  if (ownedError || !owned) throw ownedError ?? new Error('The saved program is unavailable.');
  const { data: savedUnit, error: unitLookupError } = await client.from('learning_program_units').select('id').eq('program_id', id).eq('unit_number', unitNumber).maybeSingle();
  if (unitLookupError || !savedUnit) throw unitLookupError ?? new Error('The saved unit is unavailable.');
  const topics = Array.isArray(unit.topics) ? unit.topics as Record<string, unknown>[] : [];
  const { data: savedTopics, error: topicLookupError } = await client.from('learning_program_topics').select('id,topic_number').eq('program_id', id).eq('unit_number', unitNumber);
  if (topicLookupError) throw topicLookupError;
  for (const [index, topic] of topics.entries()) {
    const saved = (savedTopics || []).find((row) => Number(row.topic_number) === index + 1);
    if (!saved) throw new Error('A saved program topic is missing.');
    const { error: topicError } = await client.from('learning_program_topics').update({ ...programTopicRow(topic, index, unitNumber), updated_at: new Date().toISOString() }).eq('id', saved.id).eq('program_id', id);
    if (topicError) throw topicError;
  }
  const complete = programReady(document);
  const { error: programError } = await client.from('learning_programs').update({ program_data: document, status: complete ? 'active' : 'draft', is_public: complete ? undefined : false, visibility: complete ? undefined : 'private', updated_at: new Date().toISOString() }).eq('id', id).eq('user_id', auth.user.id);
  if (programError) throw programError;
  const { error: unitError } = await client.from('learning_program_units').update({ ...programUnitRow(unit, unitIndex), generation_operation_id: generationId || null, updated_at: new Date().toISOString() }).eq('id', savedUnit.id).eq('program_id', id);
  if (unitError) throw unitError;
}

export async function getSavedProgramGeneration(id: string): Promise<{ input: SmartToolInput; result: GeneratedMaterial }> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const { data: row, error } = await client.from('learning_programs').select('id,subject,custom_subject_name,learner_stage,level_or_band,program_language,student_material_language,builder_config,program_data,parent_program_id,source_type,updated_at').eq('id', id).eq('user_id', auth.user.id).neq('status', 'archived').maybeSingle();
  if (error || !row) throw error ?? new Error('The saved program is unavailable.');
  const config = row.builder_config && typeof row.builder_config === 'object' ? row.builder_config as Record<string, unknown> : {};
  const subjectKey = String(row.subject || '');
  const subject = ({ english: 'English', spanish: 'Spanish', mathematics: 'Mathematics', science: 'Science', music: 'Music', study_skills: 'Study skills', other: 'Other' } as Record<string, string>)[subjectKey] || 'Other';
  const document = row.program_data && typeof row.program_data === 'object' ? row.program_data as Record<string, unknown> : {};
  const input: SmartToolInput = { kind: 'program', subject, customSubject: String(row.custom_subject_name || ''), topic: '', stage: String(row.learner_stage || ''), level: String(row.level_or_band || ''), language: String(row.student_material_language || 'en'), planLanguage: String(row.program_language || 'en'), nativeLanguage: String(config.student_native_language || ''), generationMode: 'ai', requestedUnits: Number(config.requested_units || (Array.isArray(document.units) ? document.units.length : 0)), requestedLessons: Number(config.requested_lessons_per_unit || 4), programTrack: String(config.program_track || 'general_language'), examTarget: String(config.exam_prep_target || ''), duration: '60 minutes', notes: String(config.additional_notes || ''), previousProgramId: row.parent_program_id ? String(row.parent_program_id) : undefined, visibility: 'private' };
  return { input, result: { document, model: String(row.source_type || 'ai'), generationId: String(config.generation_id || '') || undefined, generatedAt: String(row.updated_at || '') } };
}

export async function saveGeneratedMaterial(input: SmartToolInput, document: Record<string, unknown>) {
  const client = requireSupabase(); const { data, error: userError } = await client.auth.getUser(); if (userError || !data.user) throw userError ?? new Error('Your session has expired.'); const uid = data.user.id; const now = new Date().toISOString(); const title = String(document.title || `${input.topic} ${input.kind}`).trim();
  const storedSubject = input.subject === 'Other' && input.customSubject?.trim() ? input.customSubject.trim() : input.subject;
  const makePublic = input.visibility === 'public' && !(await hasCustomBranding());
  const generationOperationId = input.generationMode === 'ai' && input.generationId ? input.generationId : null;
  if (input.kind === 'plan') { const { data: saved, error } = await client.from('lesson_plans').insert({ user_id: uid, title, subject: storedSubject, topic: input.topic, learner_stage: input.stage, level_or_band: input.level, lesson_purpose: input.lessonPurpose || 'introduce_concept', plan_language: input.planLanguage || input.language, student_material_language: input.language, source_type: input.generationMode === 'template' ? 'template' : 'ai', planner_mode: input.generationMode || 'ai', plan_json: document, generation_operation_id: generationOperationId, author_name: data.user.user_metadata?.full_name || data.user.email?.split('@')[0] || 'Teacher', subject_display: storedSubject, is_public: makePublic, status: 'active', created_at: now }).select('id').single(); if (error || !saved) throw error ?? new Error('Resource could not be saved.'); return { id: String(saved.id) }; }
  if (input.kind === 'worksheet') { const { data: saved, error } = await client.from('worksheets').insert({ user_id: uid, title, subject: storedSubject, topic: input.topic, learner_stage: input.stage, level_or_band: input.level, worksheet_type: input.worksheetType || 'mixed_practice', plan_language: input.planLanguage || input.language, student_material_language: input.language, source_type: 'ai', worksheet_json: document, generation_operation_id: generationOperationId, author_name: data.user.user_metadata?.full_name || data.user.email?.split('@')[0] || 'Teacher', subject_display: storedSubject, is_public: makePublic, status: 'active', created_at: now, updated_at: now }).select('id').single(); if (error || !saved) throw error ?? new Error('Resource could not be saved.'); return { id: String(saved.id) }; }
  if (input.kind === 'exam') { const sections = Array.isArray(document.sections) ? document.sections as Record<string, unknown>[] : []; const answerKey = document.answer_key || { sections: sections.map((section) => ({ title: section.title, answers: section.answers || [] })) }; const { data: saved, error } = await client.from('quick_exams').insert({ user_id: uid, title, subject: storedSubject, topic: input.topic, learner_stage: input.stage, level: input.level, exam_length: input.examLength || 'medium', exercise_types: input.exerciseTypes?.length ? input.exerciseTypes : ['mixed'], plan_language: input.planLanguage || input.language, student_material_language: input.language, exam_data: document, answer_key: answerKey, generation_operation_id: generationOperationId, is_public: makePublic, status: 'active', created_at: now, updated_at: now }).select('id').single(); if (error || !saved) throw error ?? new Error('Resource could not be saved.'); return { id: String(saved.id) }; }
  const units = (Array.isArray(document.units) ? document.units as Record<string, unknown>[] : []).map((unit, unitIndex) => ({
    ...unit,
    topics: uniqueProgramTopics((Array.isArray(unit.topics) ? unit.topics as Record<string, unknown>[] : []).map((topic) => ({ ...topic, unit_number: unitIndex + 1 }))).map((topic, topicIndex) => ({ ...topic, topic_number: topicIndex + 1 })),
  }));
  const savedDocument = { ...document, units };
  const totalTopics = units.reduce((sum, unit) => sum + (Array.isArray(unit.topics) ? unit.topics.length : 0), 0);
  const complete = programReady(savedDocument);
  const isPublic = complete && makePublic;
  let parent: { id: number; sequence_group_id: string | null; sequence_order: number | null; level_or_band: string } | null = null;
  if (input.previousProgramId) {
    const parentId = Number(input.previousProgramId);
    if (!Number.isSafeInteger(parentId) || parentId <= 0) throw new Error('Choose a valid previous program.');
    const { data: previous, error: previousError } = await client.from('learning_programs').select('id,sequence_group_id,sequence_order,subject,custom_subject_name,learner_stage,level_or_band,status').eq('id', parentId).eq('user_id', uid).maybeSingle();
    if (previousError || !previous || previous.status === 'archived' || String(previous.subject) !== (input.subject === 'Other' ? 'other' : input.subject.toLowerCase().replaceAll(' ', '_')) || String(previous.learner_stage) !== input.stage || (input.subject === 'Other' && String(previous.custom_subject_name || '').toLowerCase() !== input.customSubject?.trim().toLowerCase())) throw previousError ?? new Error('The previous program is unavailable.');
    parent = { id: Number(previous.id), sequence_group_id: previous.sequence_group_id, sequence_order: previous.sequence_order, level_or_band: String(previous.level_or_band || '') };
  }
  const { data: program, error } = await client.from('learning_programs').insert({
    user_id: uid,
    title,
    slug: `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}-${Date.now().toString(36)}`,
    subject: input.subject === 'Other' ? 'other' : input.subject.toLowerCase().replaceAll(' ', '_'),
    custom_subject_name: input.subject === 'Other' ? storedSubject : null,
    learner_stage: input.stage,
    level_or_band: input.level,
    program_language: input.planLanguage || input.language,
    student_material_language: input.language,
    program_overview: String(document.program_overview || ''),
    teacher_rationale: String(document.teacher_rationale || ''),
    student_summary: String(document.student_summary || ''),
    assessment_strategy: String(document.assessment_strategy || ''),
    resource_strategy: String(document.resource_strategy || ''),
    best_practice_frameworks: Array.isArray(document.best_practice_frameworks) ? document.best_practice_frameworks : [],
    source_type: input.generationMode === 'template' ? 'template' : 'ai',
    generation_mode: input.generationMode || 'ai',
    parent_program_id: parent?.id || null,
    sequence_group_id: parent ? parent.sequence_group_id || `${storedSubject.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${input.stage}-${Date.now().toString(36)}` : null,
    sequence_order: parent ? nextProgramSequenceOrder(parent.level_or_band, parent.sequence_order) : null,
    visibility: isPublic ? 'public' : 'private',
    is_public: isPublic,
    status: complete ? 'active' : 'draft',
    total_units: units.length,
    total_topics: totalTopics,
    builder_config: { expo_native: true, generation_path: parent ? 'next_level' : 'standalone', previous_program_id: parent?.id || null, generation_id: input.generationId || null, requested_units: input.requestedUnits, requested_lessons_per_unit: input.requestedLessons, program_track: input.programTrack || 'general_language', exam_prep_target: input.examTarget || '', student_native_language: input.nativeLanguage || '', additional_notes: input.notes || '' },
    program_data: savedDocument,
    updated_at: now,
    created_at: now,
  }).select('id').single();
  if (error || !program) throw error ?? new Error('Program could not be saved.');
  try {
    for (const [index, unit] of units.entries()) {
      const unitRow = programUnitRow(unit, index);
      const { data: savedUnit, error: unitError } = await client.from('learning_program_units').insert({ ...unitRow, program_id: program.id, created_at: now, updated_at: now }).select('id').single();
      if (unitError || !savedUnit) throw unitError ?? new Error('A program unit could not be saved.');
      const topics = Array.isArray(unit.topics) ? unit.topics as Record<string, unknown>[] : [];
      if (topics.length) {
        const topicRows = topics.map((topic, topicIndex) => ({ ...programTopicRow(topic, topicIndex, unitRow.unit_number), program_id: program.id, unit_id: savedUnit.id, created_at: now, updated_at: now }));
        const { error: topicError } = await client.from('learning_program_topics').insert(topicRows);
        if (topicError) throw topicError;
      }
    }
  } catch (saveError) {
    await client.from('learning_programs').delete().eq('id', program.id).eq('user_id', uid);
    throw saveError;
  }
  return { id: String(program.id) };
}

export async function setGeneratedMaterialVisibility(kind: SmartToolKind, id: string, visibility: 'private' | 'public') {
  const client = requireSupabase();
  const { data, error: authError } = await client.auth.getUser();
  if (authError || !data.user) throw authError ?? new Error('Your session has expired.');
  if (visibility === 'public' && await hasCustomBranding()) throw new Error('Turn off custom branding before making this document public.');
  if (kind === 'program' && visibility === 'public') {
    const { data: program, error } = await client.from('learning_programs').select('program_data').eq('id', id).eq('user_id', data.user.id).maybeSingle();
    if (error || !program || !programReady(program.program_data as Record<string, unknown>)) throw error ?? new Error('Complete every program unit before publishing.');
  }
  const table = { plan: 'lesson_plans', worksheet: 'worksheets', exam: 'quick_exams', program: 'learning_programs' }[kind];
  const values = kind === 'program' ? { is_public: visibility === 'public', visibility } : { is_public: visibility === 'public' };
  const { data: updated, error } = await client.from(table).update(values).eq('id', id).eq('user_id', data.user.id).select('id').single();
  if (error || !updated) throw error ?? new Error('Resource visibility could not be updated.');
}


export async function updateGeneratedMaterial(kind: SmartToolKind, id: string, document: Record<string, unknown>) {
  const client = requireSupabase();
  const { data, error: authError } = await client.auth.getUser();
  if (authError || !data.user) throw authError ?? new Error('Your session has expired.');
  const config = {
    plan: { table: 'lesson_plans', values: { title: String(document.title || ''), plan_json: document } },
    worksheet: { table: 'worksheets', values: { title: String(document.title || ''), worksheet_json: document } },
    exam: { table: 'quick_exams', values: { title: String(document.title || ''), exam_data: document, answer_key: document.answer_key || {} } },
    program: { table: 'learning_programs', values: { title: String(document.title || ''), program_data: document } },
  }[kind];
  const { data: updated, error } = await client.from(config.table).update(config.values).eq('id', id).eq('user_id', data.user.id).select('id').single();
  if (error || !updated) throw error ?? new Error('Resource changes could not be saved.');
}
