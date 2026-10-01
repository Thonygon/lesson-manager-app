import { buildLessonPlanUserPrompt } from '../../server/lesson-plan-prompt';
import { buildWorksheetUserPrompt } from '../../server/worksheet-prompt';
import { buildExamUserPrompt } from '../../server/exam-prompt';

type ToolKind = 'plan' | 'worksheet' | 'exam' | 'program';
type GenerationRequest = { kind?: ToolKind; subject?: string; customSubject?: string; topic?: string; stage?: string; level?: string; language?: string; planLanguage?: string; nativeLanguage?: string; student?: string; generationMode?: string; lessonPurpose?: string; worksheetType?: string; examTitle?: string; examLength?: string; exerciseTypes?: string[]; instructions?: string; requestedUnits?: number; requestedLessons?: number; visibility?: string; programTrack?: string; examTarget?: string; duration?: string; questionCount?: number; notes?: string; programId?: string; programTopicId?: string };

const SCHEMAS: Record<ToolKind, string> = {
  plan: `{"title":"...","objective":"...","recommended_level":"...","plan_language":"...","student_material_language":"...","success_criteria":["..."],"warm_up":["..."],"main_activity":["..."],"core_examples":["..."],"guided_practice":["..."],"practice_questions":["..."],"freer_task":["..."],"wrap_up":["..."],"teacher_moves":["..."],"extension_task":"...","homework":"...","reading_passage":"...","listening_script":"...","core_material":{}}`,
  worksheet: `{"title":"...","subject":"...","topic":"...","learner_stage":"...","level_or_band":"...","worksheet_type":"...","plan_language":"...","student_material_language":"...","instructions":"...","text_kind":"passage","text_blocks":[],"reading_passage":"...","source_text":"...","questions":["..."],"true_false_statements":["..."],"vocabulary_bank":["..."],"matching_pairs":[{"left":"...","right":"..."}],"multiple_choice_items":[{"stem":"...","options":["...","...","..."],"answer":"..."}],"left_items":["..."],"right_items":["..."],"answer_key":"1. ...","teacher_notes":["..."]}`,
  exam: `{"title":"...","instructions":"...","sections":[{"type":"multiple_choice","title":"Part 1: Section Title","instructions":"...","source_text":"...","text_kind":"passage","text_blocks":[],"table_data":{"title":"...","caption":"...","columns":["..."],"rows":[["..."]]},"questions":[{"stem":"...","options":["...","...","...","..."]}],"answers":["..."]}]}`,
  program: `{"title":"...","program_overview":"...","teacher_rationale":"...","student_summary":"...","assessment_strategy":"...","entry_profile":"...","exit_profile":"...","units":[{"unit_number":1,"title":"...","unit_summary":"...","learning_objectives":["..."],"topics":[{"topic_number":1,"title":"...","topic":"...","student_summary":"...","estimated_lessons":2,"objectives":["..."]}]}]}`,
};

// Source: streamlit/helpers/generation_guidance.py:build_expert_panel_prompt_blurb.
const EXPERT_PANEL = "You are Classio's expert generation panel: a coordinated team of PhD-level professionals in education, instructional design, assessment, curriculum planning, differentiation, and subject-specific pedagogy. Act as if a subject specialist, learner-stage specialist, classroom practitioner, and instructional designer are jointly reviewing every decision for ";
export function sourceSystemPrompt(kind: ToolKind): string {
  if (kind === 'plan') return `${EXPERT_PANEL}practical one-to-one lesson design. Prioritize production-ready teacher usability, accuracy, alignment, age appropriateness, and polished classroom delivery. You are an expert private lesson planner. Return exactly one valid JSON object and nothing else. Do not use markdown. Do not use code fences. All list fields must be arrays of strings. The core_material field must be a JSON object. Use the requested plan_language for teacher-facing sections. Use the requested student_material_language for reading_passage, listening_script, target_vocabulary, and comprehension questions whenever appropriate. Make the lesson practical for one 45-minute private lesson. Use subject-appropriate materials. Do not force reading or listening for non-language subjects. Never use raw JSON key names as visible headings inside content.`;
  if (kind === 'worksheet') return `${EXPERT_PANEL}premium worksheet design. Prioritize production-ready teacher usability, accuracy, alignment, age appropriateness, and polished classroom delivery. You are an expert curriculum designer holding a Doctorate in Education (Ed.D.) with specialisation in differentiated instruction, formative assessment, and evidence-based resource design. Your task is to create a high-quality, classroom-ready worksheet. Return exactly one valid JSON object and nothing else. Do not use markdown. Do not use code fences. Use the requested plan_language for teacher-facing sections (answer_key, teacher_notes). Use the requested student_material_language for student-facing sections (instructions, questions, reading_passage, source_text, true_false_statements, vocabulary_bank, matching_pairs values, multiple_choice_items).`;
  if (kind === 'exam') return `${EXPERT_PANEL}high-validity assessment design. Prioritize production-ready teacher usability, accuracy, alignment, age appropriateness, and polished classroom delivery. You are a world-class assessment and evaluation specialist with a PhD in Education, deep expertise in instructional design, strong assessment literacy, and classroom exam-writing experience across school subjects. Your task is to create a premium, classroom-ready exam paper that a professional teacher could use immediately. Think like an expert in validity, alignment, cognitive demand, item quality, learner accessibility, and efficient evidence collection. Return exactly one valid JSON object and nothing else. Do not use markdown. Do not use code fences. Use the requested plan_language for teacher-facing sections (answers). Use the requested student_material_language for student-facing sections (instructions, questions, source_text). Be pedagogically accurate, age-appropriate, and internally consistent.`;
  return "You are Classio, an expert curriculum designer. Follow the requested JSON schema exactly. Never wrap JSON in prose.";
}

function text(value: unknown, max = 4000) { return String(value || '').trim().slice(0, max); }
function boundedInt(value: unknown, fallback: number, low: number, high: number) { const parsed = Number(value); return Number.isFinite(parsed) ? Math.max(low, Math.min(high, Math.round(parsed))) : fallback; }
function jsonFromModel(value: string) { let cleaned = value.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').replace(/^\uFEFF/, ''); const start = cleaned.indexOf('{'); const end = cleaned.lastIndexOf('}'); if (start >= 0 && end > start) cleaned = cleaned.slice(start, end + 1); const parsed = JSON.parse(cleaned); if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('The model returned an invalid document.'); return parsed as Record<string, unknown>; }
function rows(value: unknown): Record<string, unknown>[] { return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : []; }
function present(value: unknown): boolean { return typeof value === 'string' ? Boolean(value.trim()) : Array.isArray(value) ? value.length > 0 : Boolean(value); }
function validGeneratedDocument(kind: ToolKind, document: Record<string, unknown>, request: GenerationRequest): boolean {
  if (!present(document.title)) return false;
  if (kind === 'plan') return present(document.objective) && present(document.success_criteria) && present(document.main_activity) && Boolean(document.core_material && typeof document.core_material === 'object' && !Array.isArray(document.core_material));
  if (kind === 'worksheet') {
    const type = String(document.worksheet_type || '');
    if (type !== String(request.worksheetType || '')) return false;
    const content = type === 'matching' ? rows(document.matching_pairs) : type === 'multiple_choice' ? rows(document.multiple_choice_items) : type === 'true_false' ? document.true_false_statements : type === 'word_search_vocab' ? document.vocabulary_bank : document.questions;
    return present(document.instructions) && present(content) && (type === 'word_search_vocab' || present(document.answer_key));
  }
  if (kind === 'exam') {
    const sections = rows(document.sections);
    const count = String(request.examLength).toLowerCase() === 'short' ? 3 : String(request.examLength).toLowerCase() === 'long' ? 5 : 4;
    const selected = (request.exerciseTypes || []).slice(0, count);
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
const guestBits: Record<string, number> = { plan: 1, worksheet: 2, exam: 4 };
async function guestSignature(mask: number, secret: string) { const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']); const bytes = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(`classio-guest:${mask}`))); return Array.from(bytes).map((byte) => byte.toString(16).padStart(2, '0')).join(''); }
async function guestMask(request: Request, secret: string) { const cookie = request.headers.get('cookie')?.match(/(?:^|;\s*)classio_guest_tools=([0-7])\.([a-f0-9]{64})/); if (!cookie) return 0; const mask = Number(cookie[1]); return await guestSignature(mask, secret) === cookie[2] ? mask : 0; }

function canTeach(profile: { can_teach?: boolean | null; primary_role?: string | null; role?: string | null }) {
  if (profile.can_teach !== null && profile.can_teach !== undefined) return profile.can_teach === true;
  return ['teacher', 'tutor'].includes(String(profile.primary_role || profile.role || '').toLowerCase());
}

type ProgramRow = { id: number; title?: string; subject?: string; custom_subject_name?: string; learner_stage?: string; level_or_band?: string; assessment_strategy?: string; resource_strategy?: string; status?: string };
type UnitRow = { unit_number?: number; title?: string };
type TopicRow = { id: number; program_id: number; unit_number?: number; title?: string; lesson_focus?: string; student_summary?: string; learning_objectives?: string[]; success_criteria?: string[]; suggested_worksheet_types?: string[]; suggested_exam_exercise_types?: string[]; lesson_purpose?: string };
function positiveId(value: unknown): number | null { const number = Number(value); return Number.isSafeInteger(number) && number > 0 ? number : null; }
async function readProgramTopic(base: string, key: string, token: string, userId: string, programId: number, topicId: number) {
  const headers = { apikey: key, Authorization: `Bearer ${token}`, Accept: 'application/json' };
  async function get<T>(table: string, select: string, filters: Record<string, string>): Promise<T | null> {
    const url = new URL(`${base.replace(/\/$/, '')}/rest/v1/${table}`); url.searchParams.set('select', select); url.searchParams.set('limit', '1');
    for (const [column, value] of Object.entries(filters)) url.searchParams.set(column, `eq.${value}`);
    const response = await fetch(url, { headers }); if (!response.ok) throw new Error('Program context could not be verified.');
    const rows = await response.json() as T[]; return Array.isArray(rows) ? rows[0] ?? null : null;
  }
  const program = await get<ProgramRow>('learning_programs', 'id,title,subject,custom_subject_name,learner_stage,level_or_band,assessment_strategy,resource_strategy,status', { id: String(programId), user_id: userId });
  if (!program || program.status === 'archived') return null;
  const topic = await get<TopicRow>('learning_program_topics', 'id,program_id,unit_number,title,lesson_focus,student_summary,learning_objectives,success_criteria,suggested_worksheet_types,suggested_exam_exercise_types,lesson_purpose', { id: String(topicId), program_id: String(programId) });
  if (!topic) return null;
  const unit = await get<UnitRow>('learning_program_units', 'unit_number,title', { program_id: String(programId), unit_number: String(topic.unit_number || 0) });
  return { program, topic, unit };
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
  lines.push("- The output should feel like a deliberate next step in this program, not a generic stand-alone resource.", "- Reuse the program's progression logic, terminology, and skill emphasis when shaping the content.");
  return lines.join('\n');
}

export async function POST(request: Request) {
  try {
    const authorization = request.headers.get('authorization') || ''; const token = authorization.replace(/^Bearer\s+/i, '').trim();
    const guest = !token;
    const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || ''; const anonKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
    let userId = '';
    if (guest) {
      const origin = request.headers.get('origin') || '';
      const allowedOrigin = /^https:\/\/classio\.expo\.app$/i.test(origin);
      if (!allowedOrigin) return json({ error: 'This sample is available from the Classio website.' }, 403);
      if (request.headers.get('sec-fetch-site') === 'cross-site') return json({ error: 'This sample is available from the Classio website.' }, 403);
    } else {
      if (!supabaseUrl || !anonKey) return json({ error: 'Server authentication is not configured.' }, 503);
      const authCheck = await fetch(`${supabaseUrl.replace(/\/$/, '')}/auth/v1/user`, { headers: { apikey: anonKey, Authorization: `Bearer ${token}` } });
      if (!authCheck.ok) return json({ error: 'Your Classio session has expired.' }, 401);
      const user = await authCheck.json() as { id?: string };
      if (!user.id) return json({ error: 'Your Classio session has expired.' }, 401);
      userId = user.id;
      const profileUrl = new URL(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/profiles`);
      profileUrl.searchParams.set('select', 'role,primary_role,can_teach');
      profileUrl.searchParams.set('user_id', `eq.${userId}`);
      profileUrl.searchParams.set('limit', '1');
      const profileCheck = await fetch(profileUrl, { headers: { apikey: anonKey, Authorization: `Bearer ${token}`, Accept: 'application/json' } });
      if (!profileCheck.ok) return json({ error: 'Your teaching access could not be verified.' }, 503);
      const profiles = await profileCheck.json() as { can_teach?: boolean | null; primary_role?: string | null; role?: string | null }[];
      if (!Array.isArray(profiles) || profiles.length !== 1 || !canTeach(profiles[0])) return json({ error: 'Teacher access is required.' }, 403);
    }
    const parsedBody = await request.json().catch(() => null);
    if (!parsedBody || typeof parsedBody !== 'object' || Array.isArray(parsedBody)) return json({ error: 'Choose a valid teaching tool.' }, 400);
    const body = parsedBody as GenerationRequest; const kind = body.kind;
    if (!kind || !SCHEMAS[kind]) return json({ error: 'Choose a valid teaching tool.' }, 400);
    const apiKey = process.env.OPENROUTER_API_KEY || ''; if (!apiKey) return json({ error: 'Classio AI is not connected.' }, 503);
    const priorGuestMask = guest ? await guestMask(request, apiKey) : 0;
    if (guest && (!guestBits[kind] || (priorGuestMask & guestBits[kind]))) return json({ error: 'This free try has been used. Sign in to create more.' }, 429);
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
    if (!subject || !topic || !stage || !level) return json({ error: 'Subject, topic, learner stage, and level are required.' }, 400);
    const schema = SCHEMAS[kind];
    const exerciseTypes = Array.isArray(body.exerciseTypes) ? body.exerciseTypes.slice(0, 12).map((value) => text(value, 60)).filter(Boolean) : [];
    const length = text(body.examLength, 20).toLowerCase(); const examSpec = length === 'short' ? { sections: 3, range: '4-5' } : length === 'long' ? { sections: 5, range: '6-10' } : { sections: 4, range: '5-7' };
    const selectedExamTypes = exerciseTypes.slice(0, examSpec.sections);
    const controls = [`Generation mode: ${text(body.generationMode, 40) || 'AI'}`, body.student ? `Selected student: ${text(body.student, 120)}` : '', body.nativeLanguage ? `Student native language: ${text(body.nativeLanguage, 80)}` : '', body.lessonPurpose ? `Lesson purpose: ${text(body.lessonPurpose, 80)}` : '', body.worksheetType ? `Worksheet type: ${text(body.worksheetType, 80)}` : '', body.examLength ? `Exam length: ${text(body.examLength, 40)}` : '', selectedExamTypes.length ? `Exercise types: ${selectedExamTypes.join(', ')}` : '', body.instructions ? `Special instructions: ${text(body.instructions)}` : '', body.requestedUnits ? `Requested units: ${boundedInt(body.requestedUnits, 6, 1, 20)}` : '', body.requestedLessons ? `Lessons per unit: ${boundedInt(body.requestedLessons, 4, 1, 30)}` : '', body.programTrack ? `Program track: ${text(body.programTrack, 80)}` : '', body.examTarget ? `Exam target: ${text(body.examTarget, 100)}` : ''].filter(Boolean).join('. ');
    const shapeRules = kind === 'plan' ? 'Include all required sections. All activity sections and success_criteria must be arrays of strings; core_material must be a JSON object. Use an empty string or empty array where a section is not needed.' : kind === 'worksheet' ? `Use worksheet_type ${text(body.worksheetType, 80)}. Put only the relevant item family in questions, true_false_statements, matching_pairs, multiple_choice_items, or vocabulary_bank. Do not mix unrelated task families. Answer every item in answer_key, except a vocabulary word search. Keep teacher_notes separate from student instructions.` : kind === 'exam' ? `Create ${selectedExamTypes.length} sections, ${examSpec.range} questions per section. Exercise types in order: ${selectedExamTypes.join(', ')}. Each section must include both questions and aligned answers. Section instructions must match the actual response mode.` : '';
    const prompt = kind === 'plan' ? buildLessonPlanUserPrompt({ subject, topic, learnerStage: stage, levelOrBand: level, lessonPurpose: text(body.lessonPurpose, 100), planLanguage, studentMaterialLanguage: language, programContextBlock: programBlock }) : kind === 'worksheet' ? buildWorksheetUserPrompt({ subject, topic, learnerStage: stage, levelOrBand: level, worksheetType: text(body.worksheetType, 80), planLanguage, studentMaterialLanguage: language, programContextBlock: programBlock }) : kind === 'exam' ? buildExamUserPrompt({ subject, topic, examTitle: text(body.examTitle, 200), learnerStage: stage, levelOrBand: level, examLength: length, exerciseTypes, planLanguage, studentMaterialLanguage: language, instructions: text(body.instructions), programContextBlock: programBlock }) : `Create a classroom-ready ${kind} for a teacher. Subject: ${subject}. Topic: ${topic}. Learner stage: ${stage}. Level: ${level}. Teacher-facing plan_language: ${planLanguage}. Student-facing student_material_language: ${language}. ${body.duration ? `Duration: ${text(body.duration, 50)}.` : ''} ${controls}. Teacher context: ${notes || 'None provided'}. ${programBlock} ${shapeRules} Use accurate, age-appropriate content, clear instructions, inclusive examples, and practical assessment. Return ONLY valid JSON matching this shape: ${schema}`;
    const aiResponse = await fetch('https://openrouter.ai/api/v1/chat/completions', { method: 'POST', headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json', 'HTTP-Referer': 'https://classio.expo.app', 'X-Title': 'Classio' }, body: JSON.stringify({ model: process.env.OPENROUTER_MODEL || process.env.AI_MODEL || 'openrouter/free', messages: [{ role: 'system', content: sourceSystemPrompt(kind) }, { role: 'user', content: prompt }], temperature: 0.35, response_format: { type: 'json_object' } }) });
    if (!aiResponse.ok) { const providerBody = await aiResponse.text(); console.error('OpenRouter generation failed', aiResponse.status, providerBody.slice(0, 300)); return json({ error: 'The AI provider could not complete this generation. Try again.' }, 502); }
    const ai = await aiResponse.json() as { choices?: { message?: { content?: string } }[]; model?: string }; const content = ai.choices?.[0]?.message?.content || '';
    let document: Record<string, unknown>;
    try { document = jsonFromModel(content); } catch { return json({ error: 'The AI provider returned an invalid document. Try again.' }, 502); }
    if (!validGeneratedDocument(kind, document, body)) return json({ error: 'The AI provider returned an incomplete document. Try again.' }, 502);
    const cookie = guest ? `classio_guest_tools=${priorGuestMask | guestBits[kind]}.${await guestSignature(priorGuestMask | guestBits[kind], apiKey)}; Path=/api/generate; HttpOnly; Secure; SameSite=Lax` : '';
    return json({ document, model: ai.model || 'openrouter', generatedAt: new Date().toISOString() }, 200, cookie ? { 'Set-Cookie': cookie } : undefined);
  } catch (error) { console.error('Generation route error', error); return json({ error: 'Generation failed.' }, 500); }
}
