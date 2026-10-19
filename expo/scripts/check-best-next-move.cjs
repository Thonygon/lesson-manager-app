const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-best-next-move.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleExports = {};
const mockRequire = (id) => {
  if (id === '@/lib/subjects') return { canonicalSubjectLabel: (value) => value };
  if (id === '@react-native-async-storage/async-storage') return { default: {} };
  return {};
};
new Function('require', 'exports', compiled)(mockRequire, moduleExports);

const now = new Date('2026-10-19T09:00:00');
const empty = () => ({ students: [], lessons: [], payments: [], schedules: [], assignments: [], reviewRequests: [], practiceRequests: [], yearGoal: 0, goalCurrency: 'TRY' });
const context = () => ({ topics: [], events: [], pastEvents: [], coverageAvailable: true, complete: true });
const make = (data = empty(), ctx = context()) => moduleExports.buildTeacherNextMoves({ data, packages: [], inactiveStudents: [], context: ctx, now });

assert.equal(make().primary, null, 'A free day must not invent work.');
const data = empty();
data.students = [{ id: 7, student: 'Ada', linked_student_user_id: 'student-1' }];
data.reviewRequests = [{ id: 4, student_id: 'student-1', status: 'requested', requested_at: '2026-10-18T09:00:00' }];
data.practiceRequests = [{ id: 5, student_id: 'student-1', student_name: 'Ada', updated_at: '2026-10-19T07:00:00' }];
assert.equal(make(data).primary.kind, 'review', 'An open review wins over a practice request.');
const queued = make(data);
assert.equal(moduleExports.selectActiveNextMove(queued, 'practice:5').kind, 'practice', 'The visible move stays in place while it remains eligible.');
data.practiceRequests = [];
assert.equal(moduleExports.selectActiveNextMove(make(data), 'practice:5').kind, 'review', 'The next move appears after the active move is resolved.');
data.practiceRequests = [{ id: 5, student_id: 'student-1', student_name: 'Ada', updated_at: '2026-10-19T07:00:00' }];

const topic = { assignmentId: '1', topicId: '10', programId: '2', studentId: 'student-1', student: 'Ada', title: 'Greetings', subject: 'English', stage: 'adult_stage', level: 'A1', targetDate: '', material: 'no_clear_match', planAvailable: false, practiceAvailable: false };
const event = { key: 's-1-2026-10-20', student: 'Ada', date: '2026-10-20', time: '09:00', duration: 60, source: 'weekly', note: '' };
const material = make(data, { ...context(), topics: [topic], events: [event] });
assert.equal(material.primary.kind, 'review');
assert.ok(material.candidates.some((item) => item.kind === 'material_gap' && item.href.params.programTopicId === '10'));
const practice = make(empty(), { ...context(), topics: [{ ...topic, material: 'related', planAvailable: true }], events: [event] });
assert.equal(practice.primary.kind, 'practice_gap', 'An existing plan without exercises should suggest practice.');
const noLesson = make(empty(), { ...context(), topics: [topic] });
assert.equal(noLesson.primary.kind, 'plan_program');
assert.equal(noLesson.candidates.some((item) => item.kind === 'material_gap'), false, 'No imminent lesson means no urgent generation.');

const unrecorded = make(data, { ...context(), pastEvents: [{ ...event, date: '2026-10-18', key: 's-1-2026-10-18' }] });
assert.ok(unrecorded.candidates.some((item) => item.kind === 'record_lesson'));
data.lessons = [{ student: 'Ada', lesson_date: '2026-10-18' }];
assert.equal(make(data, { ...context(), pastEvents: [{ ...event, date: '2026-10-18', key: 's-1-2026-10-18' }] }).candidates.some((item) => item.kind === 'record_lesson'), false);

console.log('Best next move rules: 8 local checks passed.');
