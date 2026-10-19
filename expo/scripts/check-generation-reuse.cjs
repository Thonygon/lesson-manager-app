const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/server/generation-reuse.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', compiled)(moduleRef, moduleRef.exports);
const { classifyGenerationMatch, findGenerationMatches } = moduleRef.exports;

const base = { id: '61ecf6c5-334b-44a9-b2d7-0a2f2ebdb437', user_id: 'teacher-1', is_public: false, title: 'Past tense practice', subject: 'Spanish', topic: 'Past tense', learner_stage: 'adult_stage', level_or_band: 'A2', worksheet_type: 'short_answer' };
const input = { kind: 'worksheet', subject: 'Spanish', topic: 'Past tense', stage: 'adult_stage', level: 'A2', worksheetType: 'short_answer' };
assert.equal(classifyGenerationMatch(input, base, 'teacher-1').bucket, 'very_close');
assert.equal(classifyGenerationMatch(input, base, 'teacher-1').id, base.id);
assert.equal(classifyGenerationMatch({ kind: 'plan', subject: 'spanish', topic: 'Saludos y presentaciones', stage: 'adult_stage', level: 'A1', lessonPurpose: 'introduce_concept' }, { ...base, title: 'Saludos y Presentaciones Básicas', topic: 'Saludos y presentaciones', learner_stage: 'adult_stage', level_or_band: 'A1', lesson_purpose: 'introduce_concept' }, 'teacher-1').bucket, 'very_close');
assert.equal(classifyGenerationMatch({ kind: 'exam', subject: 'Spanish', topic: 'Past tense', stage: 'adult_stage', level: 'A2', exerciseTypes: ['multiple_choice'] }, { ...base, level: 'A2', exercise_types: ['multiple_choice'] }, 'teacher-1').bucket, 'very_close');
assert.equal(classifyGenerationMatch({ kind: 'program', subject: 'Spanish', topic: 'Spanish foundations', stage: 'adult_stage', level: 'A2' }, { ...base, topic: undefined, title: 'Spanish foundations', builder_config: { topic: 'Spanish foundations' } }, 'teacher-1').bucket, 'very_close');
assert.equal(classifyGenerationMatch(input, { ...base, subject: 'Mathematics' }, 'teacher-1'), null);
assert.equal(classifyGenerationMatch(input, { ...base, learner_stage: 'upper_primary' }, 'teacher-1'), null);
assert.equal(classifyGenerationMatch(input, { ...base, topic: 'Pronunciation' }, 'teacher-1'), null);
assert.equal(classifyGenerationMatch(input, { ...base, level_or_band: 'C2', worksheet_type: 'multiple_choice' }, 'teacher-1').bucket, 'related');

const originalFetch = global.fetch;
global.fetch = async (url, options) => {
  const query = new URL(url);
  assert.equal(query.pathname, '/rest/v1/worksheets');
  assert.equal(query.searchParams.get('limit'), '500');
  assert.equal(query.searchParams.get('or'), '(is_public.eq.true)');
  assert.equal(options.headers.Authorization, undefined);
  return Response.json([{ ...base, user_id: 'other', is_public: true }]);
};
findGenerationMatches('https://supabase.test', 'publishable-key', '', '', input).then((matches) => {
  assert.equal(matches.length, 1);
  assert.equal(matches[0].source, 'community');
  process.stdout.write('Generation reuse fixtures passed.\n');
}).finally(() => { global.fetch = originalFetch; });
