const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function loadSource(relativePath, aliases = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(module, module.exports, (name) => aliases[name] || require(name));
  return module.exports;
}

const subjects = loadSource('src/lib/subjects.ts');
const need = loadSource('src/services/student-recommendation-need.ts', { '@/lib/subjects': subjects });
const programs = loadSource('src/services/student-recommendation-programs.ts', { '@/lib/subjects': subjects });
const topicAlignment = loadSource('src/services/student-recommendation-topic-alignment.ts');
const { buildStudentRecommendationSafety, buildStudentRecommendationEligibility, evaluateStudentRecommendationPolicy } = loadSource('src/services/student-recommendation-safety.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-need': need,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-topic-alignment': topicAlignment,
});
const resource = (level, stage = '') => ({ kind: 'worksheet', subject: 'english', level, stage });
const workspace = (progress = [], programs = []) => ({ practiceProgress: progress, programs });

assert.equal(buildStudentRecommendationSafety(null)(resource('A1')), false);
assert.equal(buildStudentRecommendationSafety(workspace())(resource('A1')), true);
assert.equal(buildStudentRecommendationSafety(workspace())(resource('A2')), false);
assert.equal(buildStudentRecommendationSafety(workspace())(resource('beginner_band')), true);
assert.equal(buildStudentRecommendationSafety(workspace())(resource('advanced_band')), false);
assert.equal(buildStudentRecommendationSafety(workspace([{ subject: 'english', total_attempted: 3 }]))(resource('A2')), true);
assert.equal(buildStudentRecommendationSafety(workspace([], [{ program: { subject: 'english' } }]))(resource('A2')), true);
const staged = workspace([{ subject: 'english', learner_stage: 'early_primary', total_attempted: 5 }]);
assert.equal(buildStudentRecommendationSafety(staged)(resource('A1', 'upper_primary')), true);
assert.equal(buildStudentRecommendationSafety(staged)(resource('A1', 'lower_secondary')), false);
assert.equal(buildStudentRecommendationSafety(staged)(resource('A1', 'adult_stage')), false);

const profile = (overrides = {}) => ({ subjectAttempts: {}, subjectLevel: {}, subjectStage: {}, defaultStage: '', programSubjects: [], programLevels: {}, programStages: {}, ...overrides });
const signals = (overrides = {}) => ({ accuracy: 0, topicNeed: 0, ...overrides });
assert.equal(evaluateStudentRecommendationPolicy(resource('A2'), profile(), signals()).allowed, false);
assert.equal(evaluateStudentRecommendationPolicy(resource('A2'), profile({ subjectAttempts: { english: 3 } }), signals()).allowed, true);
const enrolled = profile({ programSubjects: ['english'], programLevels: { english: 'A1' }, subjectAttempts: { english: 5 } });
assert.equal(evaluateStudentRecommendationPolicy({ ...resource('A1'), subject: 'spanish' }, enrolled, signals()).allowed, false);
assert.equal(evaluateStudentRecommendationPolicy(resource('B1'), enrolled, signals()).allowed, false);
assert.equal(evaluateStudentRecommendationPolicy(resource('A1'), enrolled, signals()).allowed, true);
assert.equal(evaluateStudentRecommendationPolicy(resource('A2'), enrolled, signals({ accuracy: 0.85, topicNeed: 0.2, nextTopicOverlap: 0.5 })).stretchAllowed, true);
assert.equal(evaluateStudentRecommendationPolicy(resource('A2'), enrolled, signals({ accuracy: 0.81, topicNeed: 0.2, nextTopicOverlap: 0.5 })).allowed, false);
assert.equal(evaluateStudentRecommendationPolicy(resource('A1', 'lower_secondary'), profile({ subjectStage: { english: 'early_primary' } }), signals()).allowed, false);

const fullWorkspace = (progress = [], programRows = [], topicRows = []) => ({
  practiceProgress: progress, programs: programRows, topics: topicRows, progress: [],
});
const programRows = [{ id: 8, program_id: 4, teacher_id: 'teacher', program: { subject: 'english', level_or_band: 'A1' } }];
assert.equal(buildStudentRecommendationEligibility(null)(resource('A1')), false);
assert.equal(buildStudentRecommendationEligibility(fullWorkspace())(resource('A1')), true);
assert.equal(buildStudentRecommendationEligibility(fullWorkspace())(resource('A2')), false);
assert.equal(buildStudentRecommendationEligibility(fullWorkspace([], programRows))({ ...resource('A1'), subject: 'spanish' }), false);
assert.equal(buildStudentRecommendationEligibility(fullWorkspace([], programRows))(resource('B1')), false);
const practiced = [{ subject: 'english', topic: 'grammar', total_attempted: 6, accuracy_pct: 90, level: 'A1' }];
assert.equal(buildStudentRecommendationEligibility(fullWorkspace(practiced, programRows))(resource('A2')), false);
const aligned = fullWorkspace(practiced, programRows, [{ id: 3, program_id: 4, title: 'Future perfect grammar' }]);
assert.equal(buildStudentRecommendationEligibility(aligned)({ ...resource('A2'), title: 'Future perfect grammar', topic: 'future perfect' }), true);

const linked = { ...aligned, recommendationEvents: [], topicVideoLinks: [{ topic_id: 3, video_id: 20 }] };
const stretchVideo = { id: 20, kind: 'video', subject: 'english', level: 'A2', stage: '', title: 'Unrelated video', topic: '', raw: {} };
assert.equal(buildStudentRecommendationEligibility(aligned)(stretchVideo), false);
assert.equal(buildStudentRecommendationEligibility(linked)(stretchVideo), true);
const updatedReference = { ...aligned, assignments: [], alignmentAssignments: [
  { assignment_type: 'video', source_record_id: 20, learning_program_topic_id: 3, status: 'graded', score_pct: 100 },
] };
assert.equal(buildStudentRecommendationEligibility(updatedReference)(stretchVideo), true);

process.stdout.write('Student recommendation safety fixtures passed.\n');
