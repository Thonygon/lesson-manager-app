const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
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
const ml = loadSource('src/services/student-recommendation-ml.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-topic-alignment': topicAlignment,
});
const pythonReferenceWeights = ml.fitStudentRecommendationModel([
  { features: { kind_exam: 1, subject_in_program: 1 }, target: 0.85 },
  { features: { kind_video: 1, subject_in_program: 0 }, target: 0.2 },
], { bias: -0.12, subject_in_program: 0.7 });
assert.ok(Math.abs(pythonReferenceWeights.bias - (-0.3505856630317891)) < 1e-10);
assert.ok(Math.abs(pythonReferenceWeights.kind_exam - 0.6659583412038833) < 1e-10);
assert.ok(Math.abs(pythonReferenceWeights.kind_video - (-0.8622561398202854)) < 1e-10);
assert.ok(Math.abs(ml.scoreStudentRecommendationModel(pythonReferenceWeights, { kind_exam: 1, subject_in_program: 1 }) - 0.8235739082193868) < 1e-10);
const calibrationSamples = [0.8, 0.3, 0.75, 0.25, 0.78, 0.2, 0.3, 0.8]
  .map((target, index) => ({ timestamp: String(index), target, features: { kind_worksheet: 1, subject_in_program: 1, topic_need: 0.5 } }));
assert.ok(Math.abs(ml.studentRecommendationBlendWeight(calibrationSamples) - 0.53) < 1e-12);
assert.equal(ml.studentRecommendationBlendWeight(calibrationSamples.slice(0, 5)), 0.42);
const safety = loadSource('src/services/student-recommendation-safety.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-need': need,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-topic-alignment': topicAlignment,
  '@/services/student-recommendation-ml': ml,
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
  '@/services/student-recommendation-ml': ml,
});
const selection = loadSource('src/services/student-recommendation-selection.ts', {
  '@/lib/subjects': subjects,
  '@/services/student-recommendation-programs': programs,
  '@/services/student-recommendation-assignments': assignments,
  '@/services/student-recommendation-ranking': { scopeAdjustedStudentRecommendationScore },
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
const learnedWorkspace = {
  ...workspace,
  sessions: [{ source_type: 'worksheet', subject: 'english', topic: 'Fractions', level: 'A1', score_pct: 90, created_at: '2026-09-26T00:00:00Z' }],
  assignments: [{ ...workspace.assignments[0], subject_key: 'english', score_pct: 80, status: 'graded', updated_at: '2026-09-26T00:00:00Z' }],
};
assert.deepEqual([...programs.studentTopicTokens('Fractions, Decimals_and Percentages')], ['fractions', 'decimals', 'and', 'percentages']);
const historySignals = ml.buildStudentMlHistorySignals({
  programs: [{ program: { subject: 'science', level_or_band: 'B2' } }],
  sessions: [
    { source_type: 'worksheet', subject: 'Mathematics', topic: 'Fractions, decimals', level: 'A1', created_at: '2026-09-26T00:00:00Z' },
    { source_type: 'exam', subject: 'Mathematics', topic: 'Percentages', level: 'A1', created_at: '2026-09-25T00:00:00Z' },
    { source_type: 'exam', subject: 'Science', topic: 'Old topic', level: 'B2', created_at: '2025-01-01T00:00:00Z' },
  ],
  assignments: [{ assignment_type: 'worksheet', subject_key: 'Science', topic: 'Screen only', learning_program_topic_id: 20, status: 'assigned', updated_at: '2026-09-24T00:00:00Z' }],
  mlHistoryAssignments: [{ assignment_type: 'worksheet', subject_key: 'English', topic: 'Grammar', learning_program_topic_id: 19, status: 'assigned', updated_at: '2026-09-24T00:00:00Z' }],
}, now);
assert.deepEqual([...historySignals.subjects], ['mathematics', 'english']);
assert.equal(historySignals.subjectLevels.mathematics, 'A1');
assert.equal(historySignals.subjectLevels.science, undefined);
assert.deepEqual([...historySignals.topicTokens], ['fractions', 'decimals', 'percentages', 'grammar']);
assert.deepEqual([...historySignals.activeTopicIds], [19]);
const learned = ml.buildStudentRecommendationModel(learnedWorkspace, now);
assert.equal(learned.sampleCount, 2);
assert.notEqual(learned.weights.kind_worksheet, 0);
const otherPracticeTypes = {
  ...learnedWorkspace,
  sessions: Array.from({ length: 6 }, (_, index) => ({ source_type: 'speaking', subject: 'english', topic: 'Conversation', level: 'A1', score_pct: 80, created_at: `2026-09-${String(20 + index).padStart(2, '0')}T00:00:00Z` })),
  mlHistoryAssignments: [],
};
const otherTypeModel = ml.buildStudentRecommendationModel(otherPracticeTypes, now);
assert.equal(otherTypeModel.sampleCount, 6);
assert.equal(otherTypeModel.blendWeight, 0.42);
assert.notEqual(otherTypeModel.weights.kind_speaking, 0);
const noProgramHistory = { programs: [], topics: [], progress: [], assignments: [], alignmentAssignments: [], recommendationEvents: [], recommendationFeedback: [], topicVideoLinks: [], sessions: [{ source_type: 'worksheet', subject: 'English', topic: 'Past tense', level: 'A1', score_pct: 80, created_at: '2026-09-26T00:00:00Z' }] };
const liveWithoutProgram = ml.buildStudentRecommendationModel(noProgramHistory, now, 'live');
const historyWithoutProgram = ml.buildStudentRecommendationModel(noProgramHistory, now, 'history');
assert.notEqual(liveWithoutProgram.weights.subject_in_program, historyWithoutProgram.weights.subject_in_program);
const crossLanguageSessions = [
  ['worksheet', 'English', 'Past tense', 'A1', 80, 1],
  ['exam', 'English', 'Past tense', 'A1', 60, 2],
  ['speaking', 'English', 'Conversation', 'A1', 100, 3],
  ['video', 'Math', 'Fractions', 'B1', 40, 4],
  ['speaking', 'English', 'Conversation', 'A1', 75, 5],
  ['worksheet', 'Math', 'Fractions', 'B1', 90, 6],
].map(([source_type, subject, topic, level, score_pct, day]) => ({ source_type, subject, topic, level, score_pct, created_at: `2026-10-${String(day).padStart(2, '0')}T00:00:00Z` }));
const crossLanguageFeedback = ['student_recommendation_impression', 'student_recommendation_open'].map((activity_type, index) => ({
  activity_type, created_at: `2026-10-0${index + 7}T00:00:00Z`,
  meta_json: { resource_kind: 'worksheet', subject: 'English', topic: 'Past tense', level: 'A1', ml_score: 0.6, ml_blend_weight: 0.42 },
}));
// Frozen from Streamlit's build_student_recommendation_model and summarize_student_recommendation_samples.
const crossLanguageModel = ml.buildStudentRecommendationModel({
  sessions: crossLanguageSessions, assignments: [], alignmentAssignments: [], recommendationEvents: [],
  topicVideoLinks: [], recommendationFeedback: crossLanguageFeedback,
}, Date.parse('2026-10-12T00:00:00Z'), 'history');
const pythonWeights = {
  bias: 0.001416309939549351, kind_worksheet: -0.1898248099391893,
  kind_exam: -0.0004086024985820497, kind_video: -0.29133883929416343,
  kind_speaking: 0.5938446571781146, subject_in_program: 0.6716926353377805,
  level_fit: 0.4718996960907802, topic_in_program: -0.22398782005037643,
  semantic_affinity: 0.35163557307472054, topic_need: -0.06592897233317202,
};
for (const [feature, expected] of Object.entries(pythonWeights))
  assert.ok(Math.abs(crossLanguageModel.weights[feature] - expected) < 1e-10, `${feature}: ${crossLanguageModel.weights[feature]} vs ${expected}`);
assert.equal(crossLanguageModel.sampleCount, 8);
assert.ok(Math.abs(crossLanguageModel.blendWeight - 0.6) < 1e-12);
assert.ok(Math.abs(ml.scoreStudentRecommendationModel(crossLanguageModel.weights, {
  kind_worksheet: 1, subject_in_program: 1, level_fit: 1, topic_in_program: 2 / 3, topic_need: 0.6,
}) - 0.6827202339411054) < 1e-10);
const coldWorkspace = { assignments: [], alignmentAssignments: [], sessions: [], practiceProgress: [], programs: [], progress: [], topics: [], recommendationEvents: [], recommendationFeedback: [], topicVideoLinks: [], primarySubjects: [] };
const coldCandidates = [
  { id: '1', kind: 'worksheet', title: 'Past tense worksheet', subject: 'English', topic: 'Past tense', stage: '', level: 'A1', raw: { worksheet_type: 'gap_fill' } },
  { id: '2', kind: 'worksheet', title: 'Fractions worksheet', subject: 'Math', topic: 'Fractions', stage: '', level: 'A1', raw: { worksheet_type: 'gap_fill' } },
];
const coldScores = scoreStudentRecommendationCandidates(coldCandidates, coldWorkspace);
assert.ok(Math.abs(coldScores[0].score - 0.5997811227017058) < 1e-10, `cold score: ${coldScores[0].score}`);
assert.ok(Math.abs(coldScores[1].score - 0.591148376645503) < 1e-10, `cold score: ${coldScores[1].score}`);
const coldPythonInput = { candidates: coldCandidates.map((candidate, index) => ({
  kind: candidate.kind, ml_score: coldScores[index].mlScore,
  row: { id: candidate.id, title: candidate.title, subject: candidate.subject, topic: candidate.topic,
    level_or_band: candidate.level, learner_stage: candidate.stage, worksheet_type: candidate.raw.worksheet_type },
})) };
const coldPythonScores = JSON.parse(execFileSync(path.join(__dirname, '../../.venv/bin/python'),
  [path.join(__dirname, 'python-student-score-reference.py')], { input: JSON.stringify(coldPythonInput), encoding: 'utf8', maxBuffer: 1024 * 1024 }));
coldScores.forEach(({ score }, index) => assert.ok(Math.abs(score - coldPythonScores[index]) < 1e-9,
  `Python/Expo cold score ${index}: ${coldPythonScores[index]} vs ${score}`));
const programOnlyWorkspace = { ...coldWorkspace,
  programs: [{ id: 11, program_id: 12, teacher_id: 'teacher', program: { subject: 'english', level_or_band: 'A1' } }],
  topics: [{ id: 21, program_id: 12, unit_number: 1, topic_number: 1, title: 'Past tense' }],
};
const programCandidates = [
  { ...coldCandidates[0], id: '11' },
  { ...coldCandidates[0], id: '12', title: 'Everyday conversation', topic: 'Conversation', raw: { worksheet_type: 'speaking' } },
];
const programScores = scoreStudentRecommendationCandidates(programCandidates, programOnlyWorkspace);
const programSignals = programs.buildStudentProgramSignals(programOnlyWorkspace);
const programPythonInput = {
  candidates: programCandidates.map((candidate, index) => ({ kind: candidate.kind, ml_score: programScores[index].mlScore,
    row: { id: candidate.id, title: candidate.title, subject: candidate.subject, topic: candidate.topic,
      level_or_band: candidate.level, learner_stage: candidate.stage, worksheet_type: candidate.raw.worksheet_type } })),
  program_signals: {
    subjects: [...programSignals.subjects], subject_levels: programSignals.subjectLevels,
    subject_stages: programSignals.subjectStages, active_topic_ids: [...programSignals.activeTopicIds],
    next_topic_ids: [...programSignals.nextTopicIds], pending_topic_ids: [...programSignals.pendingTopicIds],
    review_topic_ids: [...programSignals.reviewTopicIds], topic_tokens: [...programSignals.topicTokens],
    next_topic_tokens: [...programSignals.nextTopicTokens], pending_topic_tokens: [...programSignals.pendingTopicTokens],
    review_topic_tokens: [...programSignals.reviewTopicTokens], next_topics: programSignals.nextTopicTitles,
    worksheet_types: [...programSignals.worksheetTypes], exam_types: [...programSignals.examTypes],
  },
};
const programPythonScores = JSON.parse(execFileSync(path.join(__dirname, '../../.venv/bin/python'),
  [path.join(__dirname, 'python-student-score-reference.py')], { input: JSON.stringify(programPythonInput), encoding: 'utf8', maxBuffer: 1024 * 1024 }));
programScores.forEach(({ score }, index) => assert.ok(Math.abs(score - programPythonScores[index]) < 1e-9,
  `Python/Expo program score ${index}: ${programPythonScores[index]} vs ${score}`));
const liveModelWorkspace = { ...programOnlyWorkspace,
  sessions: [
    { source_type: 'worksheet', subject: 'English', topic: 'Past tense', level: 'A1', score_pct: 80, created_at: '2026-10-08T00:00:00Z' },
    { source_type: 'exam', subject: 'English', topic: 'Past tense', level: 'A1', score_pct: 60, created_at: '2026-10-09T00:00:00Z' },
    { source_type: 'video', subject: 'English', topic: 'Conversation', level: 'A1', score_pct: 90, created_at: '2026-10-10T00:00:00Z' },
  ],
  mlHistoryAssignments: [{ assignment_type: 'worksheet', subject_key: 'English', topic: 'Past tense',
    status: 'graded', score_pct: 80, source_record_id: 99, updated_at: '2026-10-11T00:00:00Z' }],
  alignmentAssignments: [], recommendationEvents: [], topicVideoLinks: [],
  recommendationFeedback: [
    { activity_type: 'student_recommendation_impression', created_at: '2026-10-11T01:00:00Z',
      meta_json: { resource_kind: 'worksheet', subject: 'English', topic: 'Past tense', level: 'A1', ml_score: 0.6, ml_blend_weight: 0.42 } },
    { activity_type: 'student_recommendation_open', created_at: '2026-10-11T02:00:00Z',
      meta_json: { resource_kind: 'worksheet', subject: 'English', topic: 'Past tense', level: 'A1', ml_score: 0.7, ml_blend_weight: 0.42 } },
  ],
};
const liveModel = ml.buildStudentRecommendationModel(liveModelWorkspace, Date.parse('2026-10-12T00:00:00Z'), 'live');
const livePythonWeights = JSON.parse(execFileSync(path.join(__dirname, '../../.venv/bin/python'),
  [path.join(__dirname, 'python-student-live-model-reference.py')], { input: JSON.stringify({
    sessions: liveModelWorkspace.sessions, assignments: liveModelWorkspace.mlHistoryAssignments,
    feedback: liveModelWorkspace.recommendationFeedback,
    program_signals: { subjects: [...programSignals.subjects], subject_levels: programSignals.subjectLevels,
      topic_tokens: [...programSignals.topicTokens], active_topic_ids: [...programSignals.activeTopicIds] },
  }), encoding: 'utf8', maxBuffer: 1024 * 1024 }));
assert.equal(liveModel.sampleCount, 6);
for (const [feature, expected] of Object.entries(livePythonWeights))
  assert.ok(Math.abs((liveModel.weights[feature] || 0) - expected) < 1e-9,
    `Python/Expo live weight ${feature}: ${expected} vs ${liveModel.weights[feature]}`);
const practiceWorkspace = { ...programOnlyWorkspace, practiceProgress: [{
  subject: 'english', topic: 'Past tense', exercise_type: 'gap_fill', accuracy_pct: 45,
  total_attempted: 4, level: 'A1', learner_stage: 'adult', last_practiced: '2026-10-12T00:00:00Z',
}] };
const practiceScores = scoreStudentRecommendationCandidates(programCandidates, practiceWorkspace);
const practiceNeed = need.buildStudentNeedProfile(practiceWorkspace.practiceProgress);
const practicePythonInput = { ...programPythonInput,
  candidates: programPythonInput.candidates.map((candidate, index) => ({ ...candidate, ml_score: practiceScores[index].mlScore })),
  profile_overrides: {
    subject_need: practiceNeed.subjectNeed, topic_need: practiceNeed.topicNeed, exercise_need: practiceNeed.exerciseNeed,
    subject_attempts: practiceNeed.subjectAttempts, subject_level: practiceNeed.subjectLevel,
    subject_stage: practiceNeed.subjectStage, default_stage: practiceNeed.defaultStage,
    overall_accuracy: practiceNeed.overallAccuracy,
  },
};
const practicePythonScores = JSON.parse(execFileSync(path.join(__dirname, '../../.venv/bin/python'),
  [path.join(__dirname, 'python-student-score-reference.py')], { input: JSON.stringify(practicePythonInput), encoding: 'utf8', maxBuffer: 1024 * 1024 }));
practiceScores.forEach(({ score }, index) => assert.ok(Math.abs(score - practicePythonScores[index]) < 1e-9,
  `Python/Expo practice score ${index}: ${practicePythonScores[index]} vs ${score}`));
const assignedPracticeWorkspace = { ...practiceWorkspace, assignments: [{
  id: 44, assignment_type: 'worksheet', source_record_id: '11', status: 'assigned',
  subject_key: 'english', topic: 'Past tense', title: 'Past tense practice',
}] };
const assignedScores = scoreStudentRecommendationCandidates(programCandidates, assignedPracticeWorkspace);
const assignmentSignals = assignments.buildStudentAssignmentSignals(assignedPracticeWorkspace.assignments);
const assignmentBehavior = behavior.buildStudentAssignmentBehavior(assignedPracticeWorkspace.assignments);
const assignedPythonInput = { ...practicePythonInput,
  candidates: practicePythonInput.candidates.map((candidate, index) => ({ ...candidate, ml_score: assignedScores[index].mlScore })),
  assignment_signals: {
    resource_assignments: [...assignmentSignals.resourceAssignments].map(([key, value]) => ({
      kind: key.split(':')[0], id: key.split(':').slice(1).join(':'), is_completed: value.isCompleted, is_unseen: value.isUnseen,
    })),
    active_assigned_topic_tokens: [...assignmentSignals.activeAssignedTopicTokens],
    unseen_video_topic_tokens: [...assignmentSignals.unseenVideoTopicTokens],
  },
  assignment_behavior: {
    kind_success: assignmentBehavior.kindSuccess, kind_completion: assignmentBehavior.kindCompletion,
    topic_success: assignmentBehavior.topicSuccess, recent_teacher_topics: [...assignmentBehavior.recentTeacherTopics],
  },
};
const assignedPythonScores = JSON.parse(execFileSync(path.join(__dirname, '../../.venv/bin/python'),
  [path.join(__dirname, 'python-student-score-reference.py')], { input: JSON.stringify(assignedPythonInput), encoding: 'utf8', maxBuffer: 1024 * 1024 }));
assignedScores.forEach(({ score }, index) => assert.ok(Math.abs(score - assignedPythonScores[index]) < 1e-9,
  `Python/Expo assigned score ${index}: ${assignedPythonScores[index]} vs ${score}`));
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
assert.equal(primaryStudentRecommendationReason({ ...neutral, mlScore: 0.72, semanticAffinity: 1 }).key, 'student.materialReason.mlFit');
assert.deepEqual(studentRecommendationReasons({ ...explanation, exerciseNeed: 0.8, exerciseType: 'gap_fill' }).map((reason) => reason.key), [
  'student.materialReason.teacherAssignedReview', 'student.materialReason.programTopic', 'student.materialReason.revisitTopic',
]);
assert.deepEqual(studentRecommendationReasons({ ...neutral, nextTopicOverlap: 0.5, reviewTopicOverlap: 0.5, levelFit: 1, level: 'A1', semanticAffinity: 1 }).map((reason) => reason.key), [
  'student.materialReason.programTopic', 'student.materialReason.levelFit', 'student.materialReason.revisitTopic',
]);
assert.equal(scoreStudentRecommendationCandidates([matching], workspace)[0].reasons[0].key, 'student.materialReason.teacherAssigned');
const scoredCard = scoreStudentRecommendationCandidates([matching], workspace)[0];
assert.ok(scoredCard.mlScore >= 0 && scoredCard.mlScore <= 1);
assert.equal(scoredCard.mlBlendWeight, 0.42);
const selectedCard = selection.selectScoredStudentRecommendations([scoredCard], workspace)[0];
assert.equal(selectedCard.mlScore, scoredCard.mlScore);
assert.equal(selectedCard.mlBlendWeight, scoredCard.mlBlendWeight);
assert.ok(Number.isFinite(selectedCard.recommendationScore));
process.stdout.write('Student recommendation-ranking fixtures passed.\n');
