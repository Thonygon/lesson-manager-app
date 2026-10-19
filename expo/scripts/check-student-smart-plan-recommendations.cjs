const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function loadSource(relativePath, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, (name) => aliases[name] || require(name));
  return module.exports;
}

const subjects = loadSource('src/lib/subjects.ts');
const { selectSmartPlanResources } = loadSource('src/services/student-smart-plan-recommendations.ts', { '@/lib/subjects': subjects });
const { selectSmartPlanTaskTemplates, localSmartPlanDay, smartPlanGoalOptions, smartPlanWeeklyFocus, syncSmartPlanRewards } = loadSource('src/services/student-smart-plan-tasks.ts');
assert.deepEqual(smartPlanGoalOptions('mathematics').slice(0, 3), ['mental_math_fluency', 'problem_solving', 'equation_confidence']);
assert.ok(smartPlanGoalOptions('other').includes('rhythm_practice'));
assert.deepEqual(smartPlanWeeklyFocus('general_practice'), ['general_practice', 'review_mistakes', 'exam_preparation', 'exam_preparation', 'review_mistakes']);
assert.deepEqual(selectSmartPlanTaskTemplates('english', 'improve_speaking', 20).map((row) => row.category), ['speaking', 'vocabulary', 'reading', 'grammar']);
assert.deepEqual(selectSmartPlanTaskTemplates('mathematics', 'exam_preparation', 15).map((row) => row.titleKey), ['taskProblems', 'taskMentalMath', 'taskFormula']);
assert.equal(selectSmartPlanTaskTemplates('science', 'review_mistakes', 45).length, 5);
assert.equal(selectSmartPlanTaskTemplates('music', 'rhythm_practice', 45).at(-1).titleKey, 'taskTheory');
assert.equal(selectSmartPlanTaskTemplates('other', 'general_practice', 60).at(-1).minutes, 17);
assert.equal(localSmartPlanDay(new Date(2026, 9, 12, 23, 45)), '2026-10-12');
const taskA = { id: 'a', xp: 10, done: false }; const taskB = { id: 'b', xp: 15, done: false };
const firstTask = syncSmartPlanRewards({ points: 0, streak: 0 }, [taskA, taskB], [{ ...taskA, done: true }, taskB], '2026-10-12');
assert.deepEqual(firstTask, { points: 10, streak: 0, lastCompletionDate: '' });
const completedDay = syncSmartPlanRewards(firstTask, [{ ...taskA, done: true }, taskB], [{ ...taskA, done: true }, { ...taskB, done: true }], '2026-10-12');
assert.deepEqual(completedDay, { points: 45, streak: 1, lastCompletionDate: '2026-10-12' });
assert.deepEqual(syncSmartPlanRewards(completedDay, [{ ...taskA, done: true }, { ...taskB, done: true }], [{ ...taskA, done: true }, taskB], '2026-10-12'), { points: 10, streak: 0, lastCompletionDate: '' });
assert.deepEqual(syncSmartPlanRewards({ points: 45, streak: 1, lastCompletionDate: '2026-10-12' }, [taskA, taskB], [{ ...taskA, done: true }, { ...taskB, done: true }], '2026-10-13'), { points: 90, streak: 2, lastCompletionDate: '2026-10-13' });
const resources = [
  { id: '1', kind: 'worksheet', subject: 'Science', topic: 'Fractions', title: 'Fractions practice', description: '' },
  { id: '2', kind: 'worksheet', subject: 'Mathematics', topic: 'Fractions', title: 'Fraction exercises', description: '' },
  { id: '3', kind: 'exam', subject: 'Maths', topic: 'Fractions', title: 'Fraction test', description: '' },
  { id: '4', kind: 'video', subject: 'Mathematics', topic: 'Geometry', title: 'Shapes', description: '' },
];

assert.deepEqual(selectSmartPlanResources(resources, 'mathematics', [{ title: 'Fractions' }]).map((row) => row.id), ['2', '3']);
assert.deepEqual(selectSmartPlanResources(resources, 'mathematics', [{ title: 'Fractions' }], 2, 'exam_preparation').map((row) => row.id), ['3', '2']);
assert.deepEqual(selectSmartPlanResources(resources, 'mathematics', [{ title: 'Fractions' }], 1).map((row) => row.id), ['2']);
assert.deepEqual(selectSmartPlanResources(resources, 'mathematics', []).map((row) => row.id), []);
console.log('Student Smart Plan recommendation fixtures passed.');
