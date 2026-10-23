import { buildLessonPlanUserPrompt } from '../../server/lesson-plan-prompt';
import { buildWorksheetUserPrompt } from '../../server/worksheet-prompt';
import { buildExamUserPrompt } from '../../server/exam-prompt';
import { generalPlanTemplate } from '../../server/general-plan-template';
import { subjectPlanTemplate } from '../../server/subject-plan-template';
import { lessonPlanQualityIssues } from '../../server/lesson-plan-quality';
import { examQualityIssues, programQualityIssues, worksheetQualityIssues } from '../../server/resource-quality';
import { normalizeWorksheetAnswerKey, repairExamAnswerKey } from '../../server/answer-key';
import { worksheetHasSource, worksheetReferencesSource } from '../../lib/worksheet-source';
import { clampProgramStructure } from '../../shared/program-structure';
import { programSkeletonPrompts, programUnitPrompts, programSkeletonIssues, programUnitIssues } from '../../server/program-generation';
import { programFallback, fallbackProgramUnit } from '../../server/program-fallback';
import { programLanguageIssues } from '../../server/program-language-quality';
import { mergePreviousProgramRows, previousProgramFromStorage, previousProgramComplete, summarizePreviousProgram } from '../../server/program-continuation';
import { configuredAiProviders, requestAiProvider } from '../../server/ai-provider-chain';
import { reserveGuestGeneration } from '../../server/guest-generation-quota';
import { checkAiGenerationUsage, reserveAiGenerationUsage, logAiGeneration, type UsageContext } from '../../server/ai-generation-usage';
import { findGenerationMatches } from '../../server/generation-reuse';
import { sourceSystemPrompt } from '../../server/source-system-prompts';
import { examLengthRule } from '../../lib/exam-generation-rules';
import { programExamTargets } from '../../shared/program-builder-options';
import { gradeEvidencePrompt, loadMatchedGradeEvidence } from '../../server/student-generation-evidence';
import { beginAiOperation, beginProviderAttempt, finishAiOperation, finishProviderAttempt, type AiEconomicContext } from '../../server/ai-economic-events';

type ToolKind = 'plan' | 'worksheet' | 'exam' | 'program';
type GenerationRequest = { kind?: ToolKind; subject?: string; customSubject?: string; topic?: string; stage?: string; level?: string; language?: string; planLanguage?: string; nativeLanguage?: string; generationMode?: string; lessonPurpose?: string; objective?: string; worksheetType?: string; examTitle?: string; examLength?: string; exerciseTypes?: string[]; instructions?: string; requestedUnits?: number; requestedLessons?: number; visibility?: string; programTrack?: string; examTarget?: string; duration?: string; questionCount?: number; notes?: string; programId?: string; programTopicId?: string; previousProgramId?: string; programPhase?: 'skeleton' | 'unit'; programSkeleton?: Record<string, unknown>; programUnitIndex?: number; reuseConfirmed?: boolean; studentNameForRedaction?: string; studentIdForEvidence?: string };

const SCHEMAS: Record<ToolKind, string> = {
  plan: `{"title":"...","objective":"...","recommended_level":"...","plan_language":"...","student_material_language":"...","success_criteria":["..."],"warm_up":["..."],"main_activity":["..."],"core_examples":["..."],"guided_practice":["..."],"practice_questions":["..."],"freer_task":["..."],"wrap_up":["..."],"teacher_moves":["..."],"extension_task":"...","homework":"...","reading_passage":"...","listening_script":"...","core_material":{}}`,
  worksheet: `{"title":"...","subject":"...","topic":"...","learner_stage":"...","level_or_band":"...","worksheet_type":"...","plan_language":"...","student_material_language":"...","instructions":"...","text_kind":"passage","text_blocks":[],"reading_passage":"...","source_text":"...","questions":["..."],"true_false_statements":["..."],"vocabulary_bank":["..."],"matching_pairs":[{"left":"...","right":"..."}],"multiple_choice_items":[{"stem":"...","options":["...","...","..."],"answer":"..."}],"left_items":["..."],"right_items":["..."],"answer_key":"1. ...","teacher_notes":["..."]}`,
  exam: `{"title":"...","instructions":"...","sections":[{"type":"multiple_choice","title":"Part 1: Section Title","instructions":"...","source_text":"...","text_kind":"passage","text_blocks":[],"table_data":{"title":"...","caption":"...","columns":["..."],"rows":[["..."]]},"questions":[{"stem":"...","options":["...","...","...","..."]}],"answers":["..."]}]}`,
  program: `{"title":"...","program_overview":"...","teacher_rationale":"...","student_summary":"...","assessment_strategy":"...","entry_profile":"...","exit_profile":"...","units":[{"unit_number":1,"title":"...","unit_summary":"...","learning_objectives":["..."],"topics":[{"topic_number":1,"title":"...","topic":"...","student_summary":"...","estimated_lessons":2,"objectives":["..."]}]}]}`,
};

function text(value: unknown, max = 4000) { return String(value || '').trim().slice(0, max); }
function userIdFromAccessToken(token: string) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))) as { sub?: unknown };
    return typeof payload.sub === 'string' && /^[a-zA-Z0-9-]{20,100}$/.test(payload.sub) ? payload.sub : '';
  } catch { return ''; }
}
function jsonFromModel(value: string) { let cleaned = value.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').replace(/^\uFEFF/, ''); const start = cleaned.indexOf('{'); const end = cleaned.lastIndexOf('}'); if (start >= 0 && end > start) cleaned = cleaned.slice(start, end + 1); const parsed = JSON.parse(cleaned); if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('The model returned an invalid document.'); return parsed as Record<string, unknown>; }
function rows(value: unknown): Record<string, unknown>[] { return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : []; }
function present(value: unknown): boolean { return typeof value === 'string' ? Boolean(value.trim()) : Array.isArray(value) ? value.length > 0 : Boolean(value); }
function validGeneratedDocument(kind: ToolKind, document: Record<string, unknown>, request: GenerationRequest): boolean {
  if (!present(document.title)) return false;
  if (kind === 'plan') return present(document.objective) && present(document.success_criteria) && present(document.main_activity) && Boolean(document.core_material && typeof document.core_material === 'object' && !Array.isArray(document.core_material));
  if (kind === 'worksheet') {
    const type = String(document.worksheet_type || '');
    if (type !== String(request.worksheetType || '')) return false;
    if (worksheetReferencesSource(document) && !worksheetHasSource(document)) return false;
    if (type === 'short_answer' && worksheetReferencesSource(document) && !present(document.source_text)) return false;
    const content = type === 'matching' ? rows(document.matching_pairs) : type === 'multiple_choice' ? rows(document.multiple_choice_items) : type === 'true_false' ? document.true_false_statements : type === 'word_search_vocab' ? document.vocabulary_bank : document.questions;
    return present(document.instructions) && present(content) && (type === 'word_search_vocab' || present(document.answer_key));
  }
  if (kind === 'exam') {
    const sections = rows(document.sections);
    const selected = request.exerciseTypes || [];
    return sections.length === selected.length && sections.every((section, index) => {
      const questions = Array.isArray(section.questions) ? section.questions : [];
      const answers = Array.isArray(section.answers) ? section.answers : [];
      return section.type === selected[index] && questions.length > 0 && answers.length >= questions.length && answers.slice(0, questions.length).every((answer) => present(typeof answer === 'object' && answer !== null ? (answer as Record<string, unknown>).answer : answer));
    });
  }
  return rows(document.units).length > 0 && rows(document.units).every((unit) => rows(unit.topics).length > 0);
}
const noStore = { 'Cache-Control': 'private, no-store', Vary: 'Authorization' };
const json = (body: unknown, status = 200, extra?: Record<string, string>) => Response.json(body, { status, headers: { ...noStore, ...extra } });

function canTeach(profile: { can_teach?: boolean | null; primary_role?: string | null; role?: string | null }) {
  if (profile.can_teach !== null && profile.can_teach !== undefined) return profile.can_teach === true;
  return ['teacher', 'tutor'].includes(String(profile.primary_role || profile.role || '').toLowerCase());
}

type ProgramRow = { id: number; title?: string; subject?: string; custom_subject_name?: string; learner_stage?: string; level_or_band?: string; assessment_strategy?: string; resource_strategy?: string; status?: string };
type UnitRow = { unit_number?: number; title?: string };
type TopicRow = { id: number; program_id: number; unit_number?: number; title?: string; lesson_focus?: string; student_summary?: string; learning_objectives?: string[]; success_criteria?: string[]; suggested_worksheet_types?: string[]; suggested_exam_exercise_types?: string[]; lesson_purpose?: string };
function positiveId(value: unknown): number | null { const number = Number(value); return Number.isSafeInteger(number) && number > 0 ? number : null; }
async function readProgramTopic(base: string, key: string, token: string, userId: string, programId: number, topicId: number) {
  const url = new URL(`${base.replace(/\/$/, '')}/rest/v1/learning_program_topics`);
  url.searchParams.set('select', 'id,program_id,unit_number,title,lesson_focus,student_summary,learning_objectives,success_criteria,suggested_worksheet_types,suggested_exam_exercise_types,lesson_purpose,learning_programs!inner(id,title,subject,custom_subject_name,learner_stage,level_or_band,assessment_strategy,resource_strategy,status,user_id),learning_program_units(unit_number,title)');
  url.searchParams.set('id', `eq.${topicId}`);
  url.searchParams.set('program_id', `eq.${programId}`);
  url.searchParams.set('learning_programs.user_id', `eq.${userId}`);
  url.searchParams.set('limit', '1');
  const response = await fetch(url, { headers: { apikey: key, Authorization: `Bearer ${token}`, Accept: 'application/json' } });
  if (!response.ok) throw new Error('Program context could not be verified.');
  const rows = await response.json() as (TopicRow & { learning_programs?: ProgramRow; learning_program_units?: UnitRow })[];
  const row = rows[0];
  if (!row?.learning_programs || row.learning_programs.status === 'archived') return null;
  const { learning_programs: program, learning_program_units: unit, ...topic } = row;
  return { program, topic, unit: unit || null };
}
function programTopicPrompt(context: NonNullable<Awaited<ReturnType<typeof readProgramTopic>>>, kind: ToolKind): string {
  const { program, unit, topic } = context;
  const product = kind === 'plan' ? 'lesson plan' : kind;
  const list = (value: unknown, count: number) => Array.isArray(value) ? value.map((item) => text(item, 160)).filter(Boolean).slice(0, count).join(', ') : '';
  const lines = ['Program-linked resource brief:', `- Anchor this ${product} to the active program topic: ${text(topic.title || topic.lesson_focus, 300)}`];
  if (unit?.title) lines.push(`- Current unit: ${text(unit.title, 300)}`);
  if (program.title) lines.push(`- Learning program: ${text(program.title, 300)}`);
  if (topic.student_summary || topic.lesson_focus) lines.push(`- Topic focus: ${text(topic.student_summary || topic.lesson_focus)}`);
  if (list(topic.learning_objectives, 4)) lines.push(`- Learning objectives: ${list(topic.learning_objectives, 4)}`);
  if (list(topic.success_criteria, 4)) lines.push(`- Success criteria: ${list(topic.success_criteria, 4)}`);
  if (topic.lesson_purpose && kind === 'plan') lines.push(`- Suggested lesson purpose signal: ${text(topic.lesson_purpose, 100).replaceAll('_', ' ')}`);
  if (kind === 'worksheet' && list(topic.suggested_worksheet_types, 4)) lines.push(`- Suggested worksheet types from the program: ${list(topic.suggested_worksheet_types, 4)}`);
  if (kind === 'exam' && list(topic.suggested_exam_exercise_types, 5)) lines.push(`- Suggested exam exercise types from the program: ${list(topic.suggested_exam_exercise_types, 5)}`);
  if (program.resource_strategy) lines.push(`- Program resource strategy: ${text(program.resource_strategy)}`);
  if (program.assessment_strategy) lines.push(`- Program assessment strategy: ${text(program.assessment_strategy)}`);
  lines.push("- Suggested purposes and exercise types are recommendations. Honor the teacher's selected purpose and exercise types when they differ.", "- The output should feel like a deliberate next step in this program, not a generic stand-alone resource.", "- Reuse the program's progression logic, terminology, and skill emphasis when shaping the content.");
  return lines.join('\n');
}

async function readPreviousProgram(base: string, key: string, token: string, ownerId: string, id: number) {
  const url = new URL(`${base.replace(/\/$/, '')}/rest/v1/learning_programs`);
  url.searchParams.set('select', 'id,title,subject,custom_subject_name,learner_stage,level_or_band,status,program_data');
  url.searchParams.set('id', `eq.${id}`); url.searchParams.set('user_id', `eq.${ownerId}`); url.searchParams.set('limit', '1');
  const response = await fetch(url, { headers: { apikey: key, Authorization: `Bearer ${token}`, Accept: 'application/json' } });
  if (!response.ok) throw new Error('The previous program could not be verified.');
  const rows = await response.json() as Record<string, unknown>[];
  const stored = Array.isArray(rows) ? rows[0] : null;
  if (!stored || stored.status === 'archived') return null;
  const headers = { apikey: key, Authorization: `Bearer ${token}`, Accept: 'application/json' };
  async function details(table: string, select: string) {
    const query = new URL(`${base.replace(/\/$/, '')}/rest/v1/${table}`);
    query.searchParams.set('select', select);
    query.searchParams.set('program_id', `eq.${id}`);
    query.searchParams.set('order', 'unit_number.asc,topic_number.asc');
    query.searchParams.set('limit', '500');
    if (table === 'learning_program_units') query.searchParams.set('order', 'unit_number.asc');
    const result = await fetch(query, { headers });
    if (!result.ok) throw new Error('The previous program details could not be verified.');
    return await result.json() as Record<string, unknown>[];
  }
  const [units, topics] = await Promise.all([
    details('learning_program_units', 'unit_number,title,overview,unit_objectives,recommended_lesson_purposes,recommended_worksheet_types,recommended_exam_exercise_types,estimated_lessons'),
    details('learning_program_topics', 'unit_number,topic_number,title,subtopic,lesson_focus,lesson_purpose,learning_objectives,success_criteria,student_can_do,suggested_worksheet_types,suggested_exam_exercise_types,homework_idea,teacher_notes,student_summary,estimated_lessons'),
  ]);
  return mergePreviousProgramRows(previousProgramFromStorage(stored), units, topics);
}

export async function POST(request: Request) {
  let phase = 'authorization';
  let economicContext: AiEconomicContext | null = null;
  let economicOperationId = '';
  try {
    const authorization = request.headers.get('authorization') || ''; const token = authorization.replace(/^Bearer\s+/i, '').trim();
    const guest = !token;
    const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || ''; const anonKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
    let userId = '';
    let profilePlan = 'free';
    if (guest) {
      const origin = request.headers.get('origin') || '';
      const allowedOrigin = /^https:\/\/classio\.expo\.app$/i.test(origin);
      if (!allowedOrigin) return json({ error: 'This sample is available from the Classio website.' }, 403);
      if (request.headers.get('sec-fetch-site') === 'cross-site') return json({ error: 'This sample is available from the Classio website.' }, 403);
    } else {
      if (!supabaseUrl || !anonKey) return json({ error: 'Server authentication is not configured.' }, 503);
      userId = userIdFromAccessToken(token);
      if (!userId) return json({ error: 'Your Classio session has expired.' }, 401);
      const profileUrl = new URL(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/profiles`);
      profileUrl.searchParams.set('select', 'role,primary_role,can_teach,current_plan,account_status');
      profileUrl.searchParams.set('user_id', `eq.${userId}`);
      profileUrl.searchParams.set('limit', '1');
      const profileCheck = await fetch(profileUrl, { headers: { apikey: anonKey, Authorization: `Bearer ${token}`, Accept: 'application/json' } });
      if (!profileCheck.ok) return json({ error: 'Your teaching access could not be verified.', code: 'teaching_access_unavailable' }, 503);
      const profiles = await profileCheck.json() as { can_teach?: boolean | null; primary_role?: string | null; role?: string | null; current_plan?: string | null; account_status?: string | null }[];
      if (!Array.isArray(profiles) || profiles.length !== 1 || !canTeach(profiles[0])) return json({ error: 'Teacher access is required.', code: 'teacher_access_required' }, 403);
      if (profiles[0].account_status && profiles[0].account_status !== 'active') return json({ error: 'This account cannot generate resources.', code: 'account_inactive' }, 403);
      profilePlan = profiles[0].current_plan || 'free';
    }
    phase = 'request';
    const parsedBody = await request.json().catch(() => null);
    if (!parsedBody || typeof parsedBody !== 'object' || Array.isArray(parsedBody)) return json({ error: 'Choose a valid teaching tool.' }, 400);
    const body = parsedBody as GenerationRequest; const kind = body.kind;
    if (!kind || !SCHEMAS[kind]) return json({ error: 'Choose a valid teaching tool.' }, 400);
    if (kind === 'exam') {
      const selected = Array.isArray(body.exerciseTypes) ? body.exerciseTypes.map((value) => text(value, 60)).filter(Boolean) : [];
      const max = examLengthRule(body.examLength).sections;
      if (!selected.length || selected.length > max || new Set(selected).size !== selected.length) return json({ error: `Choose between 1 and ${max} distinct exercise types for this exam length.`, code: 'exam_type_limit' }, 400);
    }
    if (guest && (body.programId || body.programTopicId)) return json({ error: 'Sign in to use a program topic.' }, 403);
    const selectedSubject = text(body.subject, 100); const subject = selectedSubject === 'Other' ? text(body.customSubject, 100) : selectedSubject.toLowerCase().replaceAll(' ', '_'); let topic = text(body.topic, 300); let stage = text(body.stage, 100); let level = text(body.level, 100); const language = text(body.language, 80) || 'en'; const planLanguage = text(body.planLanguage, 10) || 'en'; const notes = text(body.notes);
    let programBlock = '';
    if (body.programId || body.programTopicId) {
      const programId = positiveId(body.programId); const topicId = positiveId(body.programTopicId);
      if (!programId || !topicId || kind === 'program') return json({ error: 'Choose a valid program topic.' }, 400);
      const context = await readProgramTopic(supabaseUrl, anonKey, token, userId, programId, topicId);
      if (!context) return json({ error: 'The selected program topic is unavailable.' }, 404);
      const programSubject = text(context.program.custom_subject_name || context.program.subject, 100);
      if (programSubject.toLowerCase().replaceAll('_', ' ') !== subject.toLowerCase().replaceAll('_', ' ')) return json({ error: 'The selected program belongs to a different subject.' }, 400);
      topic = text(context.topic.title || context.topic.lesson_focus, 300); stage = text(context.program.learner_stage, 100) || stage; level = text(context.program.level_or_band, 100) || level;
      programBlock = programTopicPrompt(context, kind);
    }
    if (!subject || (kind !== 'program' && !topic) || !stage || !level) return json({ error: 'Subject, learner stage, level, and a topic for teaching resources are required.' }, 400);
    if (kind === 'program') {
      const targets = programExamTargets(subject);
      const track = text(body.programTrack, 40) || 'general_language';
      const target = text(body.examTarget, 80);
      if (!['general_language', 'exam_prep'].includes(track) || (track === 'exam_prep' && (!targets.length || !targets.includes(target))) || (track !== 'exam_prep' && target)) return json({ error: 'Choose a supported program track and exam target.' }, 400);
    }
    phase = 'similar_resources';
    {
      let matches;
      try { matches = await findGenerationMatches(supabaseUrl, anonKey, token, userId, { kind, subject, topic, stage, level, lessonPurpose: body.lessonPurpose, worksheetType: body.worksheetType, exerciseTypes: body.exerciseTypes, programTrack: body.programTrack, examTarget: body.examTarget }); }
      catch { return json({ error: 'Existing resources could not be checked. Please try again.', code: 'reuse_unavailable' }, 503); }
      if (matches.some((match) => match.bucket === 'very_close') && body.reuseConfirmed !== true) return json({ error: 'Similar resources already exist. Review them before generating again.', matches }, 409);
    }
    const purpose = text(body.lessonPurpose, 80) || 'introduce_concept';
    const templateDocument = kind === 'plan' ? selectedSubject === 'Other' ? generalPlanTemplate({ topic, level, purpose, planLanguage }) : subjectPlanTemplate({ subject, topic, stage, level, purpose, planLanguage }) : null;
    if (templateDocument && text(body.objective, 500)) templateDocument.objective = text(body.objective, 500);
    if (text(body.generationMode, 40).toLowerCase() === 'template') {
      if (guest || kind !== 'plan') return json({ error: 'This template is not available for the selected tool or subject.' }, 400);
      if (!templateDocument) return json({ error: 'This template is not available for the selected stage or level.' }, 400);
      return json({ document: templateDocument, model: 'template', generatedAt: new Date().toISOString() });
    }
    let gradeBlock = '';
    if (body.studentIdForEvidence) {
      if (guest) return json({ error: 'Teacher access is required for learner history.' }, 403);
      phase = 'student_grade_evidence';
      try {
        const evidence = await loadMatchedGradeEvidence(supabaseUrl, anonKey, token, userId, text(body.studentIdForEvidence, 80), subject, topic, positiveId(body.programTopicId) || undefined);
        gradeBlock = gradeEvidencePrompt(evidence, text(body.studentNameForRedaction, 120));
      } catch (error) {
        console.error('Learner grade evidence failed', error instanceof Error ? error.message : 'unknown error');
        return json({ error: 'Learner grade history could not be checked. Try again.', code: 'grade_evidence_unavailable' }, 503);
      }
    }
    const fallbackPlan = (reason = 'ai_unavailable') => templateDocument && !guest ? json({ document: templateDocument, model: 'template', fallbackReason: reason, generatedAt: new Date().toISOString() }) : null;
    const schema = SCHEMAS[kind];
    const exerciseTypes = Array.isArray(body.exerciseTypes) ? body.exerciseTypes.slice(0, 12).map((value) => text(value, 60)).filter(Boolean) : [];
    const length = text(body.examLength, 20).toLowerCase(); const lengthRule = examLengthRule(length); const examSpec = { sections: lengthRule.sections, range: `${lengthRule.questionsMin}-${lengthRule.questionsMax}` };
    const selectedExamTypes = exerciseTypes;
    const programStructure = clampProgramStructure(subject, stage, body.requestedUnits, body.requestedLessons);
    if (kind === 'program' && body.programPhase !== 'skeleton' && body.programPhase !== 'unit') return json({ error: 'Choose a valid program generation phase.' }, 400);
    const programUnits = kind === 'program' && body.programPhase === 'unit' && body.programSkeleton ? rows(body.programSkeleton.units) : [];
    const programUnitIndex = Number(body.programUnitIndex);
    if (kind === 'program' && body.programPhase === 'unit' && (!body.programSkeleton || JSON.stringify(body.programSkeleton).length > 100000 || !Number.isSafeInteger(programUnitIndex) || programUnitIndex < 0 || programUnitIndex >= programUnits.length || programSkeletonIssues(body.programSkeleton, programStructure.units, programStructure.lessonsPerUnit).length)) return json({ error: 'The program skeleton is incomplete.' }, 400);
    let previousContext: Record<string, unknown> = {};
    if (kind === 'program' && body.previousProgramId) {
      const previousId = positiveId(body.previousProgramId);
      if (!previousId || guest) return json({ error: 'Choose a valid previous program.' }, 400);
      const previous = await readPreviousProgram(supabaseUrl, anonKey, token, userId, previousId);
      const expectedSubject = selectedSubject === 'Other' ? 'other' : subject;
      if (!previous || previous.subject !== expectedSubject || previous.learner_stage !== stage || (selectedSubject === 'Other' && String(previous.subject_display).toLowerCase() !== subject.toLowerCase()) || !previousProgramComplete(previous)) return json({ error: 'The selected previous program is unavailable or incomplete.' }, 400);
      previousContext = summarizePreviousProgram(previous);
    }
    const fallbackProgram = () => {
      if (kind !== 'program' || guest) return null;
      const starter = programFallback({ subject, subjectKey: selectedSubject === 'Other' ? 'other' : subject, stage, level, units: programStructure.units, lessonsPerUnit: programStructure.lessonsPerUnit, planLanguage, previousContext });
      const document = body.programPhase === 'unit' ? fallbackProgramUnit(body.programSkeleton!, starter, programUnitIndex) : starter;
      return json({ document, model: 'template', fallbackReason: 'ai_unavailable', generatedAt: new Date().toISOString() });
    };
    phase = 'provider_configuration';
    const providers = configuredAiProviders({
      OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY,
      GEMINI_API_KEY: process.env.GEMINI_API_KEY,
      OPENAI_API_KEY: process.env.OPENAI_API_KEY,
      AI_MODEL: process.env.AI_MODEL,
      OPENROUTER_MODEL: process.env.OPENROUTER_MODEL,
      GEMINI_MODEL: process.env.GEMINI_MODEL,
    }).filter((provider) => !guest || provider.provider !== 'openai');
    if (!providers.length) return fallbackProgram() ?? fallbackPlan() ?? json({ error: 'Classio AI is not connected.' }, 503);
    let usageContext: UsageContext | null = null;
    let usageLimit = 0;
    if (!guest) {
      const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
      if (!serverKey) return json({ error: 'AI usage protection is not configured.', code: 'usage_unavailable' }, 503);
      usageContext = { base: supabaseUrl, serverKey, userId, kind, profilePlan };
      phase = 'usage_check';
      let usage;
      try { usage = await checkAiGenerationUsage(usageContext); }
      catch (error) { console.error('AI usage check failed', error); return json({ error: 'AI usage could not be verified.', code: 'usage_unavailable' }, 503); }
      if (!usage.allowed) return json({ error: usage.reason, code: usage.status === 403 ? 'permission_blocked' : usage.remainingSeconds ? 'cooldown_active' : 'limit_reached', remainingSeconds: usage.remainingSeconds }, usage.status);
      if (!Number.isSafeInteger(usage.limit) || Number(usage.limit) < 0) return json({ error: 'AI usage limit is not configured.', code: 'usage_unavailable' }, 503);
      usageLimit = Number(usage.limit);
    }
    let guestCookie = '';
    if (guest) {
      phase = 'guest_usage_reservation';
      try {
        const reservation = await reserveGuestGeneration(request, {
          base: supabaseUrl,
          serverKey: process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '',
          secret: process.env.CLASSIO_GUEST_QUOTA_SECRET || '',
        });
        if (!reservation.allowed) return json({ error: 'Three free generations are available each day. Sign in for more.', code: 'guest_limit_reached' }, 429);
        guestCookie = reservation.cookie;
      } catch (error) {
        console.error('Guest quota reservation failed', error);
        return json({ error: 'Free generation is temporarily unavailable.', code: 'usage_unavailable' }, 503);
      }
    }
    const controls = [`Generation mode: ${text(body.generationMode, 40) || 'AI'}`, body.nativeLanguage ? `Student native language: ${text(body.nativeLanguage, 80)}` : '', body.lessonPurpose ? `Lesson purpose: ${text(body.lessonPurpose, 80)}` : '', body.worksheetType ? `Worksheet type: ${text(body.worksheetType, 80)}` : '', body.examLength ? `Exam length: ${text(body.examLength, 40)}` : '', selectedExamTypes.length ? `Exercise types: ${selectedExamTypes.join(', ')}` : '', body.instructions ? `Special instructions: ${text(body.instructions)}` : '', kind === 'program' ? `Requested units: ${programStructure.units}` : '', kind === 'program' ? `Lessons per unit: ${programStructure.lessonsPerUnit}` : '', body.programTrack ? `Program track: ${text(body.programTrack, 80)}` : '', body.examTarget ? `Exam target: ${text(body.examTarget, 100)}` : ''].filter(Boolean).join('. ');
    const shapeRules = kind === 'plan' ? 'Include all required sections. All activity sections and success_criteria must be arrays of strings; core_material must be a JSON object. Use an empty string or empty array where a section is not needed.' : kind === 'worksheet' ? `Use worksheet_type ${text(body.worksheetType, 80)}. Put only the relevant item family in questions, true_false_statements, matching_pairs, multiple_choice_items, or vocabulary_bank. Do not mix unrelated task families. Answer every item in answer_key, except a vocabulary word search. Keep teacher_notes separate from student instructions.` : kind === 'exam' ? `Create ${selectedExamTypes.length} sections, ${examSpec.range} questions per section. Exercise types in order: ${selectedExamTypes.join(', ')}. Each section must include both questions and aligned answers. Section instructions must match the actual response mode.` : '';
    const promptBase = kind === 'plan' ? buildLessonPlanUserPrompt({ subject, topic, learnerStage: stage, levelOrBand: level, lessonPurpose: text(body.lessonPurpose, 100), planLanguage, studentMaterialLanguage: language, programContextBlock: programBlock }) : kind === 'worksheet' ? buildWorksheetUserPrompt({ subject, topic, learnerStage: stage, levelOrBand: level, worksheetType: text(body.worksheetType, 80), planLanguage, studentMaterialLanguage: language, programContextBlock: programBlock }) : kind === 'exam' ? buildExamUserPrompt({ subject, topic, examTitle: text(body.examTitle, 200), learnerStage: stage, levelOrBand: level, examLength: length, exerciseTypes, planLanguage, studentMaterialLanguage: language, instructions: text(body.instructions), programContextBlock: programBlock }) : `Create a classroom-ready ${kind} for a teacher. Subject: ${subject}. Topic: ${topic}. Learner stage: ${stage}. Level: ${level}. Teacher-facing plan_language: ${planLanguage}. Student-facing student_material_language: ${language}. ${body.duration ? `Duration: ${text(body.duration, 50)}.` : ''} ${controls}. Teacher context: ${notes || 'None provided'}. ${programBlock} ${shapeRules} Use accurate, age-appropriate content, clear instructions, inclusive examples, and practical assessment. Return ONLY valid JSON matching this shape: ${schema}`;
    const objectiveInstruction = kind === 'plan' && text(body.objective, 500) ? `\n\nTeacher-selected lesson objective: ${text(body.objective, 500)}\nUse this objective as the plan's objective, phrased clearly for the selected learners. Program topic objectives are suggestions; the teacher's selected objective takes precedence.` : '';
    const prompt = `${kind === 'program' || !notes ? promptBase : `${promptBase}\n\nAdditional teacher context (apply only when compatible with the selected tool and learner level):\n${notes}`}${objectiveInstruction}`;
    const programContext = { subject, subjectKey: selectedSubject === 'Other' ? 'other' : selectedSubject.toLowerCase().replaceAll(' ', '_'), topic, stage, level, units: programStructure.units, lessonsPerUnit: programStructure.lessonsPerUnit, planLanguage, studentLanguage: language, nativeLanguage: text(body.nativeLanguage, 80), programTrack: text(body.programTrack, 80), examTarget: text(body.examTarget, 100), notes, previousContext };
    const programPrompts = kind === 'program' ? body.programPhase === 'unit' ? programUnitPrompts(programContext, body.programSkeleton!, programUnitIndex) : programSkeletonPrompts(programContext) : null;
    const providerUserPrompt = `${programPrompts?.user || prompt}${gradeBlock}`;
    let document: Record<string, unknown> | null = null;
    let providerName = '';
    let providerModel = '';
    let failure = 'The AI provider could not complete this generation. Try again.';
    let providerCalls = 0;
    const economicKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
    economicContext = { base: supabaseUrl, serverKey: economicKey, actorUserId: userId || null, source: 'expo' };
    try { economicOperationId = await beginAiOperation(economicContext, `generate_${kind}`, 'text'); }
    catch (error) { console.error('AI economic operation start failed', error); return json({ error: 'AI usage could not be recorded.', code: 'usage_unavailable' }, 503); }
    phase = 'provider_generation';
    for (const provider of providers) {
      let repair = '';
      for (let attempt = 0; attempt < (providers.length === 1 ? 2 : 1); attempt += 1) {
        if (providerCalls >= 2) break;
        if (usageContext) {
          phase = 'usage_reservation';
          let reservation;
          try { reservation = await reserveAiGenerationUsage(usageContext, usageLimit); }
          catch (error) { console.error('AI usage reservation failed', error); await finishAiOperation(economicContext, economicOperationId, 'failed', 'reservation_failed'); economicOperationId = ''; return json({ error: 'AI usage could not be reserved.', code: 'usage_unavailable' }, 503); }
          if (!reservation.allowed) { await finishAiOperation(economicContext, economicOperationId, 'failed', 'limit_reached'); economicOperationId = ''; return json({ error: 'Your AI generation limit has been reached.', code: 'limit_reached' }, 429); }
        }
        providerCalls += 1;
        phase = 'provider_generation';
        const economicAttemptId = await beginProviderAttempt(economicContext, economicOperationId, providerCalls, provider.provider, provider.model, 'text');
        let content: string;
        let model = '';
        let providerUsage: Awaited<ReturnType<typeof requestAiProvider>>['usage'] | null = null;
        let providerRequestId = '';
        let providerHttpStatus: number | undefined;
        try {
          const response = await requestAiProvider(provider, programPrompts?.system || sourceSystemPrompt(kind), repair ? `${providerUserPrompt}\n\nThe previous response was ${repair}. Return a complete, valid JSON document matching every required field and answer.` : providerUserPrompt, fetch, body.studentNameForRedaction ? [text(body.studentNameForRedaction, 120)] : []);
          content = response.content;
          model = response.model;
          providerUsage = response.usage;
          providerRequestId = response.providerRequestId;
          providerHttpStatus = response.httpStatus;
        } catch (error) {
          console.error('AI provider request failed', provider.provider, error instanceof Error ? error.message : 'unknown error');
          const status = /HTTP (\d{3})/.exec(error instanceof Error ? error.message : '');
          await finishProviderAttempt(economicContext, economicAttemptId, { status: 'failed', httpStatus: status ? Number(status[1]) : undefined, errorKind: status ? 'provider_http' : 'transport_error' });
          continue;
        }
        try { document = jsonFromModel(content); }
        catch { document = null; repair = 'not valid JSON'; failure = 'The AI provider returned an invalid document. Try again.'; await finishProviderAttempt(economicContext, economicAttemptId, { status: 'failed', modelReported: model, providerRequestId, httpStatus: providerHttpStatus, ...providerUsage, errorKind: 'invalid_json' }); continue; }
        if (kind === 'plan' && text(body.objective, 500)) document.objective = text(body.objective, 500);
        if (kind === 'worksheet') document = normalizeWorksheetAnswerKey(document);
        if (kind === 'exam') document = repairExamAnswerKey(document);
        const qualityIssues = kind === 'program' && body.programPhase === 'skeleton' ? [...programSkeletonIssues(document, programStructure.units, programStructure.lessonsPerUnit), ...programLanguageIssues(document, planLanguage, language)] : kind === 'program' && body.programPhase === 'unit' ? [...programUnitIssues(document, programUnits[programUnitIndex]), ...programLanguageIssues(document, planLanguage, language, true)] : kind === 'plan' ? lessonPlanQualityIssues(document, { subject, stage, level, purpose, programContext: programBlock }) : kind === 'worksheet' ? worksheetQualityIssues(document) : kind === 'exam' ? examQualityIssues(document, length) : programQualityIssues(document, programStructure.units, programStructure.lessonsPerUnit);
        if ((kind === 'program' || validGeneratedDocument(kind, document, body)) && qualityIssues.length === 0) { await finishProviderAttempt(economicContext, economicAttemptId, { status: 'success', modelReported: model, providerRequestId, httpStatus: providerHttpStatus, ...providerUsage }); providerName = provider.provider; providerModel = model; break; }
        await finishProviderAttempt(economicContext, economicAttemptId, { status: 'failed', modelReported: model, providerRequestId, httpStatus: providerHttpStatus, ...providerUsage, errorKind: 'invalid_output' });
        document = null; repair = qualityIssues.length ? qualityIssues.join('; ') : 'incomplete'; failure = 'The AI provider returned an incomplete document. Try again.';
      }
      if (document || providerCalls >= 2) break;
    }
    if (!document) {
      await finishAiOperation(economicContext, economicOperationId, 'failed', 'provider_failed'); economicOperationId = '';
      if (usageContext) await logAiGeneration(usageContext, 'failed', { prompt_version: 'expo-generate-v1', result: 'provider_failed', provider_calls: providerCalls }).catch((error) => console.error('AI usage failure log failed', error));
      return fallbackProgram() ?? fallbackPlan() ?? json({ error: failure }, 502);
    }
    const completedOperationId = economicOperationId;
    await finishAiOperation(economicContext, economicOperationId, 'success'); economicOperationId = '';
    if (usageContext) await logAiGeneration(usageContext, 'success', { prompt_version: 'expo-generate-v1', provider: providerName, model: providerModel, result: 'accepted', provider_calls: providerCalls }).catch((error) => console.error('AI usage success log failed', error));
    return json({ document, model: 'ai', generationId: userId ? completedOperationId : undefined, generatedAt: new Date().toISOString() }, 200, guestCookie ? { 'Set-Cookie': guestCookie } : undefined);
  } catch (error) { if (economicContext && economicOperationId) await finishAiOperation(economicContext, economicOperationId, 'failed', 'unexpected_error').catch((failure) => console.error('AI economic operation finalization failed', failure)); console.error('Generation route error', phase, error); return json({ error: 'Generation failed.', code: 'generation_failed', phase }, 500); }
}
