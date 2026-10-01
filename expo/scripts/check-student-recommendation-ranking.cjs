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
const need = loadSource('src/services/student-recommendation-need.ts', { '@/lib/subjects': subjects });
const programs = loadSource('src/services/student-recommendation-programs.ts', { '@/lib/subjects': subjects });
const assignments = loadSource('src/services/student-recommendation-assignments.ts', { '@/services/student-recommendation-programs': programs });
const behavior = loadSource('src/services/student-recommendation-assignment-behavior.ts', { '@/services/student-recommendation-programs': programs });
const semantic = loadSource('src/services/student-recommendation-semantic.ts');
const topicAlignment = loadSource('src/services/student-recommendation-topic-alignment.ts');
const safety = loadSource('src/services/student-recommendation-safety.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-need': need,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-topic-alignment': topicAlignment,
});
const { rankStudentRecommendations, scoreStudentRecommendationCandidates, studentRecommendationReasons, primaryStudentRecommendationReason, scopeAdjustedStudentRecommendationScore, studentStretchRecommendationBoost, studentRecommendationStageFit, studentRecommendationSubjectFocus } = loadSource('src/services/student-recommendation-ranking.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-need': need,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-assignments': assignments,
  '@/services/student-recommendation-assignment-behavior': behavior,
  '@/services/student-recommendation-semantic': semantic,
  '@/services/student-recommendation-safety': safety,
  '@/services/student-recommendation-topic-alignment': topicAlignment,
});
const match = topicAlignment.buildStudentTopicAlignment([
  { assignment_type: 'worksheet', source_record_id: '2', learning_program_topic_id: 7, status: 'completed', score_pct: 80 },
  { assignment_type: 'worksheet', source_record_id: '2', learning_program_topic_id: 7, status: 'assigned' },
  { assignment_type: 'worksheet', source_record_id: '2', learning_program_topic_id: 8, status: 'started' },
]);
const matched = match('worksheet', '2', [7]);
assert.ok(Math.abs(matched.explicitTopicMatch - 0.578) < 1e-12);
assert.ok(Math.abs(matched.topicKindPrior - 0.578) < 1e-12);
assert.equal(matched.explicitTopicSupport, 0.5);
assert.equal(matched.topicMatchAmbiguity, 0);
assert.equal(matched.directTopicLink, 0);
assert.equal(match('worksheet', '2', [9]).topicMatchAmbiguity, 0.25);
const enriched = topicAlignment.buildStudentTopicAlignment([], [
  { resource_kind: 'worksheet', resource_record_id: 2, learning_program_topic_id: 7, event_type: 'student_completed', event_weight: 0.2 },
  { resource_kind: 'worksheet', resource_record_id: 2, learning_program_topic_id: 7, event_type: 'resource_opened', event_weight: 0.8 },
], [{ topic_id: 7, video_id: 20 }, { topic_id: 8, video_id: 20 }]);
assert.ok(Math.abs(enriched('worksheet', 2, [7]).explicitTopicMatch - 0.86) < 1e-12);
assert.equal(enriched('worksheet', 2, [7]).explicitTopicSupport, 0.5);
assert.equal(enriched('video', 20, [7]).directTopicLink, 1);
assert.equal(enriched('video', 20, [9]).topicMatchAmbiguity, 0.25);
const normalizedEvent = topicAlignment.buildStudentTopicAlignment([], [
  { resource_kind: 'WorkSheet', resource_record_id: 3, learning_program_topic_id: 7, event_type: 'Student Completed', event_weight: 0 },
  { resource_kind: 'worksheet', resource_record_id: 3, learning_program_topic_id: 7, event_type: 'student-completed', event_weight: 0 },
]);
assert.equal(normalizedEvent('worksheet', 3, [7]).explicitTopicMatch, 0.92);
assert.equal(topicAlignment.assignmentTopicReferenceTarget(80, 'completed!'), 0.876);
const aged = topicAlignment.buildStudentTopicAlignment([
  { assignment_type: 'worksheet', source_record_id: 2, learning_program_topic_id: 7, status: 'completed', score_pct: 100, updated_at: '2025-01-01T00:00:00Z' },
  { assignment_type: 'worksheet', source_record_id: 2, learning_program_topic_id: 7, status: 'assigned', updated_at: '2026-09-01T00:00:00Z' },
], [], [], Date.parse('2026-09-27T00:00:00Z'));
assert.equal(aged('worksheet', 2, [7]).explicitTopicMatch, 0.28);
const now = Date.parse('2026-09-27T00:00:00Z');
const recency = topicAlignment.buildStudentTopicAlignment([
  { assignment_type: 'worksheet', source_record_id: 2, learning_program_topic_id: 7, status: 'completed', score_pct: 100, updated_at: '2026-01-01T00:00:00Z' },
  { assignment_type: 'worksheet', source_record_id: 2, learning_program_topic_id: 7, status: 'assigned', updated_at: '2026-09-26T00:00:00Z' },
], [], [], now);
assert.equal(recency('worksheet', 2, [7]).explicitTopicMatch, 0.28);
const resource = (id, topic) => ({ id, kind: 'worksheet', subject: 'english', topic, title: topic, level: 'A1', stage: 'early_primary', raw: { worksheet_type: 'gap_fill' } });
const workspace = {
  assignments: [{ id: 1, assignment_type: 'worksheet', source_record_id: 2, status: 'assigned', topic: 'Fractions', title: 'Fractions' }],
  practiceProgress: [{ subject: 'english', topic: 'Fractions', exercise_type: 'gap_fill', total_attempted: 4, accuracy_pct: 40, level: 'A1', learner_stage: 'early_primary' }],
  programs: [{ id: 5, program_id: 6, teacher_id: 'teacher', program: { subject: 'english', level_or_band: 'A1' } }],
  topics: [{ id: 7, program_id: 6, unit_number: 1, topic_number: 1, title: 'Fractions' }],
  progress: [],
};
const unrelated = resource('1', 'Ancient poetry');
const matching = resource('2', 'Fractions');
assert.deepEqual(rankStudentRecommendations([unrelated, matching], workspace).map((item) => item.id), ['2', '1']);
assert.deepEqual(rankStudentRecommendations([matching, { ...matching, id: '3', subject: 'math' }], workspace).map((item) => item.id), ['2']);
const coldStart = { ...workspace, assignments: [], practiceProgress: [], programs: [], topics: [], progress: [] };
assert.deepEqual(rankStudentRecommendations([{ ...matching, id: '4', level: 'B2' }, matching], coldStart).map((item) => item.id), ['2']);
assert.deepEqual(rankStudentRecommendations([unrelated, unrelated], workspace), [unrelated, unrelated]);
assert.deepEqual(rankStudentRecommendations([matching], null), []);
const video = (id, topic) => ({ ...resource(id, topic), kind: 'video', raw: {} });
const videoWorkspace = {
  ...workspace,
  assignments: [{ id: 9, assignment_type: 'video', source_record_id: '20', status: 'assigned', topic: 'Fractions', title: 'Fractions' }],
};
assert.deepEqual(rankStudentRecommendations([video('21', 'Ancient poetry'), video('20', 'Fractions')], videoWorkspace).map((item) => item.id), ['20', '21']);
const scope = { level: 'A1', topics: [
  { tokens: new Set(['fractions']), isComplete: false },
  { tokens: new Set(['poetry']), isComplete: true },
] };
assert.ok(Math.abs(scopeAdjustedStudentRecommendationScore(matching, 1, scope) - 1.0873333333333333) < 1e-12);
assert.ok(Math.abs(scopeAdjustedStudentRecommendationScore(unrelated, 1, scope) - 1.054) < 1e-12);
assert.ok(Math.abs(scopeAdjustedStudentRecommendationScore({ ...matching, level: 'B1' }, 1, scope) - 1.0393333333333334) < 1e-12);
assert.equal(studentStretchRecommendationBoost(false, 1, 1), 0);
assert.equal(studentStretchRecommendationBoost(true, 0.82, 0), 0.10);
assert.equal(studentStretchRecommendationBoost(true, 0.82, 0.34), 0.12);
assert.equal(studentRecommendationStageFit('primary_upper', 'upper_primary'), 1);
assert.equal(studentRecommendationStageFit('middle_school', 'early_primary'), 0.35);
assert.equal(studentRecommendationStageFit('', 'adult'), 0.65);
assert.equal(studentRecommendationSubjectFocus(0, false, 0, true), 0.8);
assert.equal(studentRecommendationSubjectFocus(0, false, 0, false), 0.45);
assert.equal(studentRecommendationSubjectFocus(0, true, 2, false), 0.96);
assert.equal(studentRecommendationSubjectFocus(0, true, 6, true), 0.92);
assert.equal(studentRecommendationSubjectFocus(0.2, true, 6, false), 1);
assert.equal(studentRecommendationSubjectFocus(0.2, false, 6, true, true), 0.2);
const explanation = { kind: 'video', topic: 'Fractions', subject: 'Mathematics', assignedActive: true, assignedUnseen: true, directTopicLink: 1, topicNeed: 0.8, subjectNeed: 0.8 };
assert.deepEqual(primaryStudentRecommendationReason(explanation), { key: 'student.materialReason.teacherAssignedReview', params: { topic: 'Fractions' } });
assert.equal(primaryStudentRecommendationReason({ ...explanation, kind: 'worksheet' }).key, 'student.materialReason.teacherAssigned');
assert.equal(primaryStudentRecommendationReason({ ...explanation, assignedActive: false, assignedUnseen: false }).key, 'student.materialReason.programTopic');
assert.equal(primaryStudentRecommendationReason({ ...explanation, assignedActive: false, assignedUnseen: false, directTopicLink: 0 }).key, 'student.materialReason.revisitTopic');
assert.equal(primaryStudentRecommendationReason({ ...explanation, assignedActive: false, assignedUnseen: false, directTopicLink: 0, topicNeed: 0 }).key, 'student.materialReason.subjectSupport');
assert.equal(primaryStudentRecommendationReason({ ...explanation, assignedActive: false, assignedUnseen: false, directTopicLink: 0, topicNeed: 0, subjectNeed: 0 }).key, 'student.materialReason.balanced');
const neutral = { ...explanation, assignedActive: false, assignedUnseen: false, directTopicLink: 0, topicNeed: 0, subjectNeed: 0 };
assert.equal(primaryStudentRecommendationReason({ ...neutral, exerciseNeed: 0.6, exerciseType: 'fill_in_blank', nextTopicOverlap: 0.8 }).key, 'student.materialReason.exerciseSupport');
assert.equal(primaryStudentRecommendationReason({ ...neutral, nextTopicOverlap: 0.34, reviewTopicOverlap: 0.9 }).key, 'student.materialReason.programTopic');
assert.equal(primaryStudentRecommendationReason({ ...neutral, reviewTopicOverlap: 0.34 }).key, 'student.materialReason.revisitTopic');
assert.equal(primaryStudentRecommendationReason({ ...neutral, programTypeFit: 1, exerciseType: 'matching' }).key, 'student.materialReason.programStyle');
assert.equal(primaryStudentRecommendationReason({ ...neutral, levelFit: 1, level: 'A1', semanticAffinity: 1 }).key, 'student.materialReason.levelFit');
assert.equal(primaryStudentRecommendationReason({ ...neutral, stretchBoost: 0.1, level: 'A2' }).key, 'student.materialReason.levelStretch');
assert.deepEqual(studentRecommendationReasons({ ...explanation, exerciseNeed: 0.8, exerciseType: 'gap_fill' }).map((reason) => reason.key), [
  'student.materialReason.teacherAssignedReview', 'student.materialReason.programTopic', 'student.materialReason.revisitTopic',
]);
assert.deepEqual(studentRecommendationReasons({ ...neutral, nextTopicOverlap: 0.5, reviewTopicOverlap: 0.5, levelFit: 1, level: 'A1', semanticAffinity: 1 }).map((reason) => reason.key), [
  'student.materialReason.programTopic', 'student.materialReason.levelFit', 'student.materialReason.revisitTopic',
]);
assert.equal(scoreStudentRecommendationCandidates([matching], workspace)[0].reasons[0].key, 'student.materialReason.teacherAssigned');
process.stdout.write('Student recommendation-ranking fixtures passed.\n');
