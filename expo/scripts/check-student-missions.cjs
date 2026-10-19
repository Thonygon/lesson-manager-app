const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function load(relativePath, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, (name) => aliases[name] || require(name));
  return module.exports;
}

const subjects = load('src/lib/subjects.ts');
const recommendations = load('src/services/student-smart-plan-recommendations.ts', { '@/lib/subjects': subjects });
const semantic = load('src/services/student-recommendation-semantic.ts');
const missions = load('src/services/student-smart-plan-missions.ts', {
  '@/services/student-smart-plan-recommendations': recommendations,
  '@/services/student-recommendation-ranking': { scoreStudentRecommendationCandidates: (rows) => rows.map((resource) => ({ resource })) },
  '@/services/student-recommendation-safety': { buildStudentRecommendationEligibility: () => () => true },
  '@/services/student-recommendation-semantic': semantic,
});
const exclusions = load('src/services/student-recommendation-exclusions.ts');
const resources = [
  { id: '11', kind: 'worksheet', subject: 'Spanish', title: 'Ordering at a restaurant', topic: 'Ordering at a restaurant', description: '' },
  { id: '12', kind: 'exam', subject: 'Spanish', title: 'Restaurant exam', topic: 'Ordering at a restaurant', description: '' },
  { id: '13', kind: 'worksheet', subject: 'Spanish', title: 'Restaurant vocabulary', topic: 'Food vocabulary', description: 'Ordering at a restaurant' },
];
const selected = missions.smartPlanMissionResources(resources, 'spanish', { title: 'Ordering at a Restaurant' }, 'general_practice');
assert.deepEqual(selected.map((row) => row.id), ['11', '12']);
assert.ok(missions.missionTopicFit({ title: 'Tema 1: Ordering at a Restaurant' }, resources[0]) >= 0.6);
assert.ok(missions.missionTopicFit({ title: 'Tema 1: Ordering at a Restaurant' }, resources[2]) < 0.6);
const workspace = {
  assignments: [{ id: 71, assignment_type: 'worksheet', source_record_id: 11, status: 'assigned' }],
  sessions: [{ source_type: 'worksheet', source_id: 71, status: 'completed', score_pct: 85 }, { source_type: 'exam', source_id: 12, status: 'completed', score_pct: 60 }],
};
assert.ok(exclusions.recommendationExcludedIds(workspace).has('worksheet:11'));
assert.ok(exclusions.recommendationExcludedIds(workspace).has('exam:12'));
const passed = missions.passedMissionResourceIds(workspace);
assert.ok(passed.has('worksheet:11'));
assert.ok(!passed.has('exam:12'));
assert.equal(missions.smartPlanMissionComplete(selected, passed), false);
workspace.sessions[1].score_pct = 72;
assert.equal(missions.smartPlanMissionComplete(selected, missions.passedMissionResourceIds(workspace)), true);
assert.equal(missions.smartPlanMissionComplete([], passed), false);
console.log('Student mission and completed-resource fixtures passed.');
