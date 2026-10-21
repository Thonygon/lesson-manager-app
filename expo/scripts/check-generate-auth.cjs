const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const cache = new Map();
function loadTypeScript(filename) {
  if (cache.has(filename)) return cache.get(filename).exports;
  const generated = { exports: {} };
  cache.set(filename, generated);
  const source = fs.readFileSync(filename, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
  const localRequire = (specifier) => {
    if (!specifier.startsWith('.')) return require(specifier);
    const resolved = path.resolve(path.dirname(filename), specifier);
    if (fs.existsSync(resolved) && resolved.endsWith('.json')) return require(resolved);
    if (fs.existsSync(`${resolved}.ts`)) return loadTypeScript(`${resolved}.ts`);
    if (fs.existsSync(`${resolved}.json`)) return require(`${resolved}.json`);
    throw new Error(`Unresolved fixture import: ${specifier}`);
  };
  new Function('module', 'exports', 'require', compiled)(generated, generated.exports, localRequire);
  return generated.exports;
}
const generated = { exports: loadTypeScript(path.join(__dirname, '../src/app/api/generate+api.ts')) };
const { POST } = generated.exports;
const originalFetch = global.fetch;
const originalEnv = {
  EXPO_PUBLIC_SUPABASE_URL: process.env.EXPO_PUBLIC_SUPABASE_URL,
  EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY,
  SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
};
let profile = { role: 'student', primary_role: 'student', can_teach: false };
let profileStatus = 200;
let providerCalls = 0;
let providerFailures = 0;
let providerDocuments = [];
let previousRows = [];
let previousUnits = [];
let previousTopics = [];
let lastProviderPrompt = '';
let similarResources = [];
let failUsageWrites = false;
let failOptionalUsageReads = false;
const validPlan = { title: 'Greetings', objective: 'Greet a peer', success_criteria: ['Greet clearly', 'Respond appropriately'], warm_up: ['Recall a greeting', 'Practice a response'], main_activity: ['Role play'], guided_practice: ['Model a conversation'], practice_questions: ['What greeting fits?', 'How would you reply?'], reading_passage: 'A short dialogue between two peers.', core_material: { target_vocabulary: ['hello', 'goodbye', 'please'], gist_questions: ['Who is speaking?'], detail_questions: ['What did they say?'] } };
let providerDocument = validPlan;
const validToken = `header.${Buffer.from(JSON.stringify({ sub: '12345678-1234-1234-1234-123456789012' })).toString('base64url')}.signature`;
const request = (token = validToken, kind = 'plan') => new Request('https://classio.test/api/generate', {
  method: 'POST',
  headers: token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' },
  body: JSON.stringify({ kind, subject: 'Spanish', topic: 'Greetings', stage: 'adult_stage', level: 'A2', worksheetType: kind === 'worksheet' ? 'short_answer' : undefined }),
});

async function main() {
  try {
    process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://supabase.test';
    process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY = 'anon-key';
    process.env.OPENROUTER_API_KEY = 'server-only-key';
    process.env.SUPABASE_SERVICE_ROLE_KEY = 'fixture-service-key';
    global.fetch = async (url, options) => {
      const target = String(url);
      if (target.endsWith('/auth/v1/user')) return Response.json({ id: 'owner-id' });
      if (target.includes('/rest/v1/profiles')) {
        const parsed = new URL(target);
        assert.equal(parsed.searchParams.get('user_id'), 'eq.12345678-1234-1234-1234-123456789012');
        if (options.headers.Authorization === 'Bearer fixture-service-key') return Response.json([{ current_plan: 'free' }]);
        assert.equal(options.headers.Authorization, `Bearer ${validToken}`);
        return Response.json([profile], { status: profileStatus });
      }
      if (target.includes('/rest/v1/user_subscriptions')) return failOptionalUsageReads ? new Response(null, { status: 503 }) : Response.json([]);
      if (['lesson_plans', 'worksheets', 'quick_exams'].some((table) => target.includes(`/rest/v1/${table}`))) {
        const query = new URL(target);
        assert.equal(query.searchParams.get('limit'), '500');
        assert.equal(options.headers.Authorization, `Bearer ${validToken}`);
        return Response.json(similarResources);
      }
      if (target.includes('/rest/v1/plans')) return failOptionalUsageReads ? new Response(null, { status: 503 }) : Response.json([{ active: true, features_json: { ai_tools: true }, limits_json: { ai_generations: 10 } }]);
      if (target.includes('/rest/v1/rpc/classio_reserve_ai_generation')) {
        const payload = JSON.parse(options.body);
        assert.equal(payload.p_user_id, '12345678-1234-1234-1234-123456789012');
        assert.equal(payload.p_limit, 10);
        return failUsageWrites ? new Response(null, { status: 503 }) : Response.json({ allowed: true, used: 1 });
      }
      if (target.includes('/rest/v1/usage_tracking')) return options.method === 'POST' ? new Response(null, { status: failUsageWrites ? 503 : 201 }) : Response.json([{ ai_generations: 0 }]);
      if (target.includes('/rest/v1/ai_usage_logs')) return options.method === 'POST' ? new Response(null, { status: failUsageWrites ? 503 : 201 }) : failOptionalUsageReads ? new Response(null, { status: 503 }) : Response.json([]);
      if (target.includes('/rest/v1/learning_programs')) {
        const parsed = new URL(target);
        if (parsed.searchParams.get('select')?.includes('builder_config')) return Response.json([]);
        assert.equal(parsed.searchParams.get('user_id'), 'eq.12345678-1234-1234-1234-123456789012');
        assert.equal(options.headers.Authorization, `Bearer ${validToken}`);
        return Response.json(previousRows);
      }
      if (target.includes('/rest/v1/learning_program_units') || target.includes('/rest/v1/learning_program_topics')) {
        const parsed = new URL(target);
        assert.equal(parsed.searchParams.get('program_id'), 'eq.42');
        assert.equal(options.headers.Authorization, `Bearer ${validToken}`);
        return Response.json(target.includes('learning_program_units') ? previousUnits : previousTopics);
      }
      if (target.includes('openrouter.ai')) {
        providerCalls += 1;
        lastProviderPrompt = JSON.parse(options.body).messages[1].content;
        if (providerFailures > 0) { providerFailures -= 1; return Response.json({ error: 'temporary failure' }, { status: 503 }); }
        return Response.json({ choices: [{ message: { content: JSON.stringify(providerDocuments.shift() || providerDocument) } }], model: 'fixture-model' });
      }
      throw new Error(`Unexpected request: ${target}`);
    };
    assert.equal((await POST(request(''))).status, 403);
    const denied = await POST(request());
    assert.equal(denied.status, 403);
    assert.equal(denied.headers.get('cache-control'), 'private, no-store');
    assert.equal(providerCalls, 0);
    profile = { role: 'student', primary_role: 'student', can_teach: true };
    assert.equal((await POST(request())).status, 200);
    profile = { ...profile, account_status: 'suspended' };
    const suspended = await POST(request());
    assert.equal(suspended.status, 403);
    assert.equal((await suspended.json()).code, 'account_inactive');
    profile = { ...profile, account_status: 'active' };
    const objectiveRequest = new Request('https://classio.test/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plan', subject: 'Spanish', topic: 'Greetings', stage: 'adult_stage', level: 'A2', lessonPurpose: 'introduce_concept', objective: 'Students can greet a visitor politely.' }) });
    const objectiveResponse = await POST(objectiveRequest);
    assert.equal(objectiveResponse.status, 200);
    const objectivePayload = await objectiveResponse.json();
    assert.equal(objectivePayload.document.objective, 'Students can greet a visitor politely.');
    assert.equal(objectivePayload.model, 'ai');
    assert.equal(objectivePayload.provider, undefined);
    assert.match(lastProviderPrompt, /Teacher-selected lesson objective: Students can greet a visitor politely/);
    failUsageWrites = true;
    const originalConsoleError = console.error;
    const expectedWriteErrors = [];
    console.error = (...args) => { expectedWriteErrors.push(args); };
    try { assert.equal((await POST(request())).status, 503); }
    finally { failUsageWrites = false; console.error = originalConsoleError; }
    assert.equal(expectedWriteErrors.length, 1);
    failOptionalUsageReads = true;
    console.error = (...args) => { expectedWriteErrors.push(args); };
    try { assert.equal((await POST(request())).status, 200); }
    finally { failOptionalUsageReads = false; console.error = originalConsoleError; }
    similarResources = [{ id: 14, user_id: '12345678-1234-1234-1234-123456789012', is_public: false, title: 'Existing greetings', topic: 'Greetings', subject: 'Spanish', learner_stage: 'adult_stage', level_or_band: 'A2', lesson_purpose: 'introduce_concept' }];
    const providerCallsBeforeReuse = providerCalls;
    const reuseResult = await POST(new Request('https://classio.test/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plan', subject: 'Spanish', topic: 'Greetings', stage: 'adult_stage', level: 'A2', lessonPurpose: 'introduce_concept' }) }));
    assert.equal(reuseResult.status, 409);
    assert.equal((await reuseResult.json()).matches[0].id, '14');
    assert.equal(providerCalls, providerCallsBeforeReuse);
    similarResources = [];
    assert.equal((await POST(new Request('https://classio.test/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}` }, body: '[' }))).status, 400);
    profile = { role: 'teacher', primary_role: 'teacher', can_teach: false };
    assert.equal((await POST(request())).status, 403);
    profile = { role: 'teacher', primary_role: 'teacher', can_teach: null };
    assert.equal((await POST(request())).status, 200);
    const templateRequest = new Request('https://classio.expo.app/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plan', subject: 'Other', customSubject: 'Philosophy', topic: 'Ethics', stage: 'adult_stage', level: 'intermediate_band', planLanguage: 'en', lessonPurpose: 'review_topic', generationMode: 'template' }) });
    const callsBeforeTemplate = providerCalls;
    const templateResult = await POST(templateRequest);
    assert.equal(templateResult.status, 200);
    const templatePayload = await templateResult.json();
    assert.equal(templatePayload.model, 'template');
    assert.equal(templatePayload.document.title, 'Ethics');
    assert.equal(providerCalls, callsBeforeTemplate);
    for (const kind of ['worksheet', 'exam', 'program']) {
      const rejectedTemplate = await POST(new Request('https://classio.expo.app/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, subject: 'Spanish', topic: 'Travel', stage: 'adult_stage', level: 'A2', generationMode: 'template' }) }));
      assert.equal(rejectedTemplate.status, 400);
    }
    assert.equal(providerCalls, callsBeforeTemplate);
    const subjectTemplate = await POST(new Request('https://classio.expo.app/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plan', subject: 'Spanish', topic: 'Travel', stage: 'adult_stage', level: 'A2', planLanguage: 'en', lessonPurpose: 'introduce_concept', generationMode: 'template' }) }));
    assert.equal(subjectTemplate.status, 200);
    assert.equal((await subjectTemplate.json()).model, 'template');
    assert.equal(providerCalls, callsBeforeTemplate);
    providerDocument = { title: 'Incomplete plan' };
    const fallback = await POST(request());
    assert.equal(fallback.status, 200);
    const fallbackPayload = await fallback.json();
    assert.equal(fallbackPayload.model, 'template');
    assert.equal(fallbackPayload.fallbackReason, 'ai_unavailable');
    assert.equal(fallbackPayload.document.title, 'Spanish: Greetings');
    delete process.env.OPENROUTER_API_KEY;
    const disconnected = await POST(request());
    assert.equal(disconnected.status, 200);
    assert.equal((await disconnected.json()).fallbackReason, 'ai_unavailable');
    process.env.OPENROUTER_API_KEY = 'server-only-key';
    providerFailures = 2;
    const unavailable = await POST(request());
    assert.equal(unavailable.status, 200);
    assert.equal((await unavailable.json()).model, 'template');
    providerDocument = { title: 'Practice', worksheet_type: 'short_answer', instructions: 'Answer both questions.', questions: ['A?', 'B?'], answer_key: '' };
    assert.equal((await POST(request(validToken, 'worksheet'))).status, 502);
    providerDocument.answer_key = '1. A; 2. B';
    assert.equal((await POST(request(validToken, 'worksheet'))).status, 200);
    providerDocument.answer_key = ['1. A', '2. B'];
    const repairedWorksheet = await POST(request(validToken, 'worksheet'));
    assert.equal(repairedWorksheet.status, 200);
    assert.equal((await repairedWorksheet.json()).document.answer_key, 'A\nB');
    providerDocument = { title: 'Short exam', sections: [{ type: 'multiple_choice', title: 'Words', questions: ['A', 'B', 'C', 'D'].map((stem, index) => ({ stem, options: ['one', 'two', 'three'], correct_answer: `Answer ${index + 1}` })), answers: [] }] };
    const repairedExam = await POST(new Request('https://classio.expo.app/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'exam', subject: 'Spanish', topic: 'Words', stage: 'adult_stage', level: 'A2', examLength: 'short', exerciseTypes: ['multiple_choice'] }) }));
    assert.equal(repairedExam.status, 200);
    assert.deepEqual((await repairedExam.json()).document.answer_key.sections[0].answers, ['Answer 1', 'Answer 2', 'Answer 3', 'Answer 4']);
    providerDocument = validPlan;
    providerDocuments = [{ title: 'Incomplete plan' }, providerDocument];
    assert.equal((await POST(request())).status, 200);
    providerFailures = 1;
    assert.equal((await POST(request())).status, 200);
    const providerCallsBeforeProfileFailure = providerCalls;
    profileStatus = 503;
    assert.equal((await POST(request())).status, 503);
    assert.equal(providerCalls, providerCallsBeforeProfileFailure);
    profileStatus = 200;
    const programBody = { kind: 'program', subject: 'Spanish', topic: 'Travel', stage: 'adult_stage', level: 'B1', requestedUnits: 8, requestedLessons: 3, programTrack: 'exam_prep', examTarget: 'dele' };
    const programRequest = (extra) => new Request('https://classio.expo.app/api/generate', { method: 'POST', headers: { Authorization: `Bearer ${validToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ ...programBody, ...extra }) });
    assert.equal((await POST(programRequest({}))).status, 400);
    const skeleton = { title: 'DELE Travel', program_overview: 'Program progression', entry_profile: 'B1', exit_profile: 'B2', assessment_strategy: 'DELE tasks', resource_strategy: 'Exam practice', units: Array.from({ length: 8 }, (_, index) => ({ title: `Unit ${index + 1}`, overview: 'A focused unit', topics: Array.from({ length: 3 }, (_, topicIndex) => ({ title: `Topic ${index + 1}-${topicIndex + 1}`, lesson_focus: 'Interaction', lesson_purpose: 'practice_skill', student_summary: 'Practica' })) })) };
    providerDocument = skeleton;
    const skeletonResponse = await POST(programRequest({ programPhase: 'skeleton' }));
    assert.equal(skeletonResponse.status, 200);
    assert.equal((await skeletonResponse.json()).document.units.length, 8);
    assert.equal((await POST(programRequest({ programPhase: 'unit', programSkeleton: { title: 'Invalid' }, programUnitIndex: 0 }))).status, 400);
    providerDocument = { ...skeleton.units[0], unit_objectives: ['Communicate'], topics: skeleton.units[0].topics.map((topic) => ({ ...topic, learning_objectives: ['Use evidence'], success_criteria: ['Responds accurately'], student_can_do: ['Converse'], suggested_worksheet_types: ['reading_comprehension'], suggested_exam_exercise_types: ['short_answer'] })) };
    const unitResponse = await POST(programRequest({ programPhase: 'unit', programSkeleton: skeleton, programUnitIndex: 0 }));
    assert.equal(unitResponse.status, 200);
    assert.equal((await unitResponse.json()).document.topics.length, 3);
    providerDocument = { ...skeleton, program_overview: 'The program is designed for learners with practice through skills and classroom tasks.', student_summary: 'The learners practice the skills and work with the teacher.' };
    const wrongLanguage = await POST(programRequest({ programPhase: 'skeleton', planLanguage: 'es', language: 'es' }));
    assert.equal(wrongLanguage.status, 200);
    assert.equal((await wrongLanguage.json()).model, 'template');
    providerDocument = { title: 'Incomplete program' };
    const fallbackSkeletonResponse = await POST(programRequest({ programPhase: 'skeleton' }));
    assert.equal(fallbackSkeletonResponse.status, 200);
    const fallbackSkeleton = await fallbackSkeletonResponse.json();
    assert.equal(fallbackSkeleton.model, 'template');
    assert.equal(fallbackSkeleton.fallbackReason, 'ai_unavailable');
    assert.equal(fallbackSkeleton.document.units.length, 8);
    assert.equal(fallbackSkeleton.document.units[0].topics.length, 3);
    const fallbackUnitResponse = await POST(programRequest({ programPhase: 'unit', programSkeleton: fallbackSkeleton.document, programUnitIndex: 0 }));
    assert.equal(fallbackUnitResponse.status, 200);
    const fallbackUnit = await fallbackUnitResponse.json();
    assert.equal(fallbackUnit.model, 'template');
    assert.equal(fallbackUnit.document.topics[0].title, fallbackSkeleton.document.units[0].topics[0].title);
    delete process.env.OPENROUTER_API_KEY;
    const disconnectedProgram = await POST(programRequest({ programPhase: 'skeleton' }));
    assert.equal(disconnectedProgram.status, 200);
    assert.equal((await disconnectedProgram.json()).model, 'template');
    process.env.OPENROUTER_API_KEY = 'server-only-key';
    previousRows = [{ id: 42, title: 'Previous Spanish', subject: 'spanish', custom_subject_name: null, learner_stage: 'adult_stage', level_or_band: 'A2', status: 'active', program_data: { title: 'Previous Spanish', exit_profile: 'Learners can use connected everyday Spanish.', scope_and_sequence_rationale: 'Move from short dialogue to connected texts.', units: [{ unit_number: 1, title: 'Earlier unit', topics: [{ title: 'Greetings', learning_objectives: ['Greet someone'] }] }] } }];
    providerDocument = skeleton;
    const continuation = await POST(programRequest({ programPhase: 'skeleton', previousProgramId: '42' }));
    assert.equal(continuation.status, 200);
    assert.match(lastProviderPrompt, /Learners can use connected everyday Spanish/);
    assert.match(lastProviderPrompt, /Greetings/);
    previousTopics = [{ unit_number: 1, topic_number: 1, title: 'Updated greetings', learning_objectives: ['Use updated greetings'] }];
    const refreshedContinuation = await POST(programRequest({ programPhase: 'skeleton', previousProgramId: '42' }));
    assert.equal(refreshedContinuation.status, 200);
    assert.match(lastProviderPrompt, /Updated greetings/);
    previousTopics = [];
    previousRows = [{ ...previousRows[0], program_data: { ...previousRows[0].program_data, units: [{ unit_number: 1, topics: [{ title: 'Greetings' }] }] } }];
    assert.equal((await POST(programRequest({ programPhase: 'skeleton', previousProgramId: '42' }))).status, 400);
    previousTopics = [{ unit_number: 1, topic_number: 1, title: 'Revised greetings', learning_objectives: ['Greet someone after a revision'] }];
    assert.equal((await POST(programRequest({ programPhase: 'skeleton', previousProgramId: '42' }))).status, 200);
    assert.match(lastProviderPrompt, /Revised greetings/);
    previousTopics = [];
    previousRows = [];
    assert.equal((await POST(programRequest({ programPhase: 'skeleton', previousProgramId: '42' }))).status, 400);
  } finally {
    global.fetch = originalFetch;
    for (const [name, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[name]; else process.env[name] = value;
    }
  }
  process.stdout.write('Protected teaching generation fixtures passed.\n');
}
void main();
