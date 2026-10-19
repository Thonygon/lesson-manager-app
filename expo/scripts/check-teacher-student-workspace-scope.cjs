const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-students.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const calls = [];
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'teacher-1' } }, error: null }) },
  from(table) {
    const call = { table, filters: [], limit: 0 }; calls.push(call);
    const query = {
      select: () => query,
      eq: (column, value) => { call.filters.push([column, value]); return query; },
      order: () => query,
      limit: (value) => { call.limit = value; return Promise.resolve({ data: [], error: null }); },
    };
    return query;
  },
};
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  if (name === '@/lib/subjects') return { canonicalSubjectKey: (value) => value, canonicalSubjectLabel: (value) => value };
  return require(name);
});

(async () => {
  const { getStudentLearningWorkspace } = loaded.exports;
  const workspace = await getStudentLearningWorkspace('  Ana  ', 'student-1');
  assert.deepEqual(workspace, { assignments: [], attempts: [], reviews: [], programs: [], progress: [], topics: [] });
  assert.deepEqual(calls.map(({ table, filters }) => [table, filters]), [
    ['teacher_assignments', [['teacher_id', 'teacher-1'], ['student_id', 'student-1']]],
    ['teacher_review_requests', [['teacher_id', 'teacher-1'], ['student_id', 'student-1']]],
    ['learning_program_assignments', [['teacher_id', 'teacher-1'], ['student_user_id', 'student-1']]],
    ['learning_program_assignments', [['teacher_id', 'teacher-1'], ['student_name', 'Ana']]],
  ]);
  assert.ok(calls.every((call) => call.limit > 0 && call.limit <= 2000));
  calls.length = 0;
  await getStudentLearningWorkspace('Ana');
  assert.deepEqual(calls.map((call) => call.table), ['learning_program_assignments']);
  assert.deepEqual(calls[0].filters, [['teacher_id', 'teacher-1'], ['student_name', 'Ana']]);
  process.stdout.write('Teacher student-workspace scoped reads fixture passed.\n');
})().catch((error) => { console.error(error); process.exitCode = 1; });
