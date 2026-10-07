const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const vm = require('node:vm');

const cache = new Map();
function load(file) {
  if (file.endsWith('.json')) return JSON.parse(fs.readFileSync(file, 'utf8'));
  if (cache.has(file)) return cache.get(file);
  const moduleExports = {}; cache.set(file, moduleExports);
  const source = fs.readFileSync(file, 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
  const localRequire = (specifier) => {
    const resolved = path.resolve(path.dirname(file), specifier);
    if (resolved.endsWith('.json') && fs.existsSync(resolved)) return load(resolved);
    if (fs.existsSync(`${resolved}.ts`)) return load(`${resolved}.ts`);
    if (fs.existsSync(`${resolved}.json`)) return load(`${resolved}.json`);
    throw new Error(`Unresolved import ${specifier}`);
  };
  vm.runInNewContext(compiled, { exports: moduleExports, require: localRequire });
  return moduleExports;
}
const moduleExports = load(path.resolve(__dirname, '../src/server/program-generation.ts'));
const fallback = load(path.resolve(__dirname, '../src/server/program-fallback.ts'));
const context = { subject: 'spanish', subjectKey: 'spanish', topic: 'Travel', stage: 'adult_stage', level: 'B1', units: 2, lessonsPerUnit: 2, planLanguage: 'en', studentLanguage: 'es', nativeLanguage: 'tr', programTrack: 'exam_prep', examTarget: 'dele', notes: 'Focus on interaction' };
const skeleton = { title: 'DELE Travel', program_overview: 'Progression', entry_profile: 'B1 entry', exit_profile: 'B2 exit', assessment_strategy: 'Practice DELE', resource_strategy: 'Exam tasks', units: [1, 2].map((number) => ({ title: `Unit ${number}`, overview: `Overview ${number}`, topics: [1, 2].map((topicNumber) => ({ title: `Topic ${number}-${topicNumber}`, lesson_focus: 'Interaction', lesson_purpose: 'practice_skill', student_summary: 'Practica el diálogo' })) })) };
assert.equal(moduleExports.programSkeletonIssues(skeleton, 2, 2).length, 0);
assert.ok(moduleExports.programSkeletonIssues({ ...skeleton, units: [skeleton.units[0]] }, 2, 2).length);
assert.ok(moduleExports.programSkeletonIssues({ ...skeleton, units: [skeleton.units[0], skeleton.units[0]] }, 2, 2).length);
const skeletonPrompt = moduleExports.programSkeletonPrompts(context);
assert.match(skeletonPrompt.user, /requested_units": 2/);
assert.match(skeletonPrompt.user, /exam_prep_target": "dele"/);
assert.match(skeletonPrompt.user, /student_native_language": "tr"/);
assert.match(skeletonPrompt.user, /subject_progression_profile/);
assert.match(skeletonPrompt.user, /program_track_guidance/);
const unitPrompt = moduleExports.programUnitPrompts(context, skeleton, 0);
assert.match(unitPrompt.user, /Unit 1/);
assert.doesNotMatch(unitPrompt.user, /Unit 2/);
const unit = { ...skeleton.units[0], unit_objectives: ['Communicate'], topics: skeleton.units[0].topics.map((topic) => ({ ...topic, learning_objectives: ['Use forms'], success_criteria: ['Can respond'], student_can_do: ['Can converse'], suggested_worksheet_types: ['reading_comprehension'], suggested_exam_exercise_types: ['short_answer'] })) };
assert.equal(moduleExports.programUnitIssues(unit, skeleton.units[0]).length, 0);
assert.ok(moduleExports.programUnitIssues({ ...unit, topics: [unit.topics[0]] }, skeleton.units[0]).length);
assert.ok(moduleExports.programUnitIssues({ ...unit, topics: [{ ...unit.topics[0], title: 'Changed' }, unit.topics[1]] }, skeleton.units[0]).length);
for (const language of ['en', 'es', 'tr']) {
  const starter = fallback.programFallback({ subject: 'spanish', subjectKey: 'spanish', stage: 'adult_stage', level: 'B1', units: 3, lessonsPerUnit: 2, planLanguage: language });
  assert.equal(moduleExports.programSkeletonIssues(starter, 3, 2).length, 0, `fallback skeleton ${language}`);
  const merged = fallback.fallbackProgramUnit(starter, starter, 1);
  assert.equal(moduleExports.programUnitIssues(merged, starter.units[1]).length, 0, `fallback unit ${language}`);
  assert.equal(merged.topics[0].title, starter.units[1].topics[0].title);
}
console.log('Program skeleton and unit phase fixtures passed.');
