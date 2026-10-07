import { requireSupabase } from '@/lib/supabase';
import { programTopicRow, programUnitRow } from './program-storage';
import { nextProgramSequenceOrder } from '../shared/program-structure';

export type SmartToolKind = 'plan' | 'worksheet' | 'exam' | 'program';
export type SmartToolInput = { kind: SmartToolKind; subject: string; customSubject?: string; topic: string; stage: string; level: string; language: string; planLanguage?: string; nativeLanguage?: string; student?: string; generationMode?: string; lessonPurpose?: string; worksheetType?: string; examTitle?: string; examLength?: string; exerciseTypes?: string[]; instructions?: string; requestedUnits?: number; requestedLessons?: number; visibility?: string; programTrack?: string; examTarget?: string; duration: string; questionCount?: number; notes: string; programId?: string; programTopicId?: string; previousProgramId?: string };
export type GeneratedMaterial = { document: Record<string, unknown>; model: string; generatedAt: string; fallbackReason?: 'ai_unavailable' };

export type SmartToolProgram = { id: string; title: string; subject: string; customSubject: string; stage: string; level: string; sequenceGroupId: string; sequenceOrder: number };
export type SmartToolProgramTopic = { id: string; title: string; unitTitle: string; unitNumber: number; topicNumber: number; lessonPurpose: string; suggestedWorksheetTypes: string[]; suggestedExamTypes: string[] };

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
    client.from('learning_program_topics').select('id,unit_number,topic_number,title,lesson_focus,lesson_purpose,suggested_worksheet_types,suggested_exam_exercise_types').eq('program_id', programId).order('unit_number').order('topic_number').limit(500),
  ]);
  if (unitsResult.error || topicsResult.error) throw unitsResult.error ?? topicsResult.error;
  const unitTitles = new Map((unitsResult.data ?? []).map((row) => [Number(row.unit_number), String(row.title || '')]));
  const list = (value: unknown): string[] => Array.isArray(value) ? value.map(String).filter(Boolean) : [];
  return (topicsResult.data ?? []).map((row) => ({ id: String(row.id), title: String(row.title || row.lesson_focus || ''), unitTitle: unitTitles.get(Number(row.unit_number)) || '', unitNumber: Number(row.unit_number || 0), topicNumber: Number(row.topic_number || 0), lessonPurpose: String(row.lesson_purpose || ''), suggestedWorksheetTypes: list(row.suggested_worksheet_types), suggestedExamTypes: list(row.suggested_exam_exercise_types) }));
}

export async function generateMaterial(input: SmartToolInput, onProgress?: (message: string) => void): Promise<GeneratedMaterial> {
  const client = requireSupabase(); const { data, error } = await client.auth.getSession(); if (error || !data.session) throw error ?? new Error('Sign in to generate teaching material.');
  const request = async (body: Record<string, unknown>): Promise<GeneratedMaterial> => {
    const response = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.session.access_token}` }, body: JSON.stringify(body) });
    const payload = await response.json() as GeneratedMaterial & { error?: string };
    if (!response.ok) throw new Error(payload.error || 'Generation failed.');
    return payload;
  };
  if (input.kind !== 'program') return request(input);
  onProgress?.('Building the program scope and sequence…');
  const skeletonResult = await request({ ...input, programPhase: 'skeleton' });
  const skeleton = skeletonResult.document;
  const units = Array.isArray(skeleton.units) ? skeleton.units as Record<string, unknown>[] : [];
  const enriched: Record<string, unknown>[] = [];
  let usedFallback = skeletonResult.model === 'template';
  for (const [index, unit] of units.entries()) {
    onProgress?.(`Enriching unit ${index + 1} of ${units.length}…`);
    const result = await request({ ...input, programPhase: 'unit', programSkeleton: skeleton, programUnitIndex: index });
    usedFallback ||= result.model === 'template';
    const details = result.document;
    const originalTopics = Array.isArray(unit.topics) ? unit.topics as Record<string, unknown>[] : [];
    const detailTopics = Array.isArray(details.topics) ? details.topics as Record<string, unknown>[] : [];
    enriched.push({ ...unit, ...details, unit_number: index + 1, title: unit.title, overview: unit.overview, topics: originalTopics.map((topic, topicIndex) => ({ ...topic, ...(detailTopics[topicIndex] || {}), topic_number: topicIndex + 1, title: topic.title, lesson_purpose: topic.lesson_purpose })) });
  }
  onProgress?.('Preparing the completed program…');
  return { ...skeletonResult, model: usedFallback ? 'template' : skeletonResult.model, fallbackReason: usedFallback ? 'ai_unavailable' : undefined, document: { ...skeleton, units: enriched } };
}

export async function saveGeneratedMaterial(input: SmartToolInput, document: Record<string, unknown>) {
  const client = requireSupabase(); const { data, error: userError } = await client.auth.getUser(); if (userError || !data.user) throw userError ?? new Error('Your session has expired.'); const uid = data.user.id; const now = new Date().toISOString(); const title = String(document.title || `${input.topic} ${input.kind}`).trim();
  const storedSubject = input.subject === 'Other' && input.customSubject?.trim() ? input.customSubject.trim() : input.subject;
  if (input.kind === 'plan') { const { error } = await client.from('lesson_plans').insert({ user_id: uid, title, subject: storedSubject, topic: input.topic, learner_stage: input.stage, level_or_band: input.level, lesson_purpose: input.lessonPurpose || 'introduce_concept', plan_language: input.planLanguage || input.language, student_material_language: input.language, source_type: input.generationMode === 'template' ? 'template' : 'ai', planner_mode: input.generationMode || 'ai', plan_json: document, author_name: data.user.user_metadata?.full_name || data.user.email?.split('@')[0] || 'Teacher', subject_display: storedSubject, is_public: false, status: 'active', created_at: now }); if (error) throw error; return; }
  if (input.kind === 'worksheet') { const { error } = await client.from('worksheets').insert({ user_id: uid, title, subject: storedSubject, topic: input.topic, learner_stage: input.stage, level_or_band: input.level, worksheet_type: input.worksheetType || 'mixed_practice', plan_language: input.planLanguage || input.language, student_material_language: input.language, source_type: 'ai', worksheet_json: document, author_name: data.user.user_metadata?.full_name || data.user.email?.split('@')[0] || 'Teacher', subject_display: storedSubject, is_public: false, status: 'active', created_at: now, updated_at: now }); if (error) throw error; return; }
  if (input.kind === 'exam') { const sections = Array.isArray(document.sections) ? document.sections as Record<string, unknown>[] : []; const answerKey = document.answer_key || { sections: sections.map((section) => ({ title: section.title, answers: section.answers || [] })) }; const { error } = await client.from('quick_exams').insert({ user_id: uid, title, subject: storedSubject, topic: input.topic, learner_stage: input.stage, level: input.level, exam_length: input.examLength || 'medium', exercise_types: input.exerciseTypes?.length ? input.exerciseTypes : ['mixed'], plan_language: input.planLanguage || input.language, student_material_language: input.language, exam_data: document, answer_key: answerKey, is_public: false, status: 'active', created_at: now, updated_at: now }); if (error) throw error; return; }
  const units = Array.isArray(document.units) ? document.units as Record<string, unknown>[] : [];
  const totalTopics = units.reduce((sum, unit) => sum + (Array.isArray(unit.topics) ? unit.topics.length : 0), 0);
  const isPublic = input.visibility === 'public';
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
    visibility: input.visibility || 'private',
    is_public: isPublic,
    status: 'draft',
    total_units: units.length,
    total_topics: totalTopics,
    builder_config: { expo_native: true, generation_path: parent ? 'next_level' : 'standalone', previous_program_id: parent?.id || null, requested_units: input.requestedUnits, requested_lessons: input.requestedLessons, program_track: input.programTrack, exam_target: input.examTarget, student: input.student, native_language: input.nativeLanguage },
    program_data: document,
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
}
