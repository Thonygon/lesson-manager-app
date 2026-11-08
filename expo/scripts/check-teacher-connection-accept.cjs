const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const schema = fs.readFileSync(path.join(__dirname, '../../streamlit/migrations/add_student_link_bridge.sql'), 'utf8');
const allowed = new Set([...schema.match(/check \(student_source in \(([^)]+)\)\)/i)[1].matchAll(/'([^']+)'/g)].map((match) => match[1]));
const source = fs.readFileSync(path.join(__dirname, '../src/services/teacher-students.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const matchSource = fs.readFileSync(path.join(__dirname, '../src/lib/roster-match.ts'), 'utf8');
const matchCompiled = ts.transpileModule(matchSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const matchModule = { exports: {} };
new Function('module', 'exports', matchCompiled)(matchModule, matchModule.exports);
let client;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  if (name === '@/lib/subjects') return { canonicalSubjectKey: (value) => value, canonicalSubjectLabel: (value) => value };
  if (name === '@/lib/roster-match') return matchModule.exports;
  if (name === '@/lib/hosting-api-url') return { hostingApiUrl: (value) => value };
  return require(name);
});

function fakeClient(roster = [], rejectInsert = false) {
  const state = { link: { id: 19, teacher_id: 'teacher-1', student_id: 'student-1', status: 'pending' }, scopes: [], roster };
  const result = (table, action, payload, filters) => {
    if (table === 'teacher_student_links') {
      if (Object.entries(filters).some(([key, value]) => state.link[key] !== value)) return { data: null, error: null };
      if (action === 'update') Object.assign(state.link, payload);
      return { data: { id: state.link.id }, error: null };
    }
    if (table === 'students') {
      if (action === 'select' && !filters.id && !filters.linked_student_user_id) return { data: state.roster.filter((item) => Object.entries(filters).every(([key, value]) => String(item[key]) === String(value))).map((item) => ({ ...item })), error: null };
      const row = state.roster.find((item) => Object.entries(filters).every(([key, value]) => String(item[key]) === String(value)));
      if (action === 'update' && row) {
        if (!allowed.has(payload.student_source)) return { data: null, error: new Error('students_student_source_check') };
        Object.assign(row, payload);
      }
      return { data: row ? { ...row } : null, error: null };
    }
    if (table === 'teacher_student_subjects' && action === 'update') {
      state.scopes.filter((item) => Object.entries(filters).every(([key, value]) => item[key] === value)).forEach((item) => Object.assign(item, payload));
      return { error: null };
    }
    throw new Error(`Unexpected query: ${table} ${action}`);
  };
  client = {
    auth: { getUser: async () => ({ data: { user: { id: 'teacher-1' } }, error: null }), getSession: async () => ({ data: { session: { access_token: 'valid-token' } }, error: null }) },
    rpc: async (name, args) => {
      assert.equal(name, 'classio_transfer_teacher_student_roster_link');
      const old = state.roster.find((item) => item.linked_student_user_id === 'student-1' && String(item.id) !== String(args.p_target_roster_id));
      const target = state.roster.find((item) => String(item.id) === String(args.p_target_roster_id));
      if (old) old.linked_student_user_id = null;
      target.linked_student_user_id = 'student-1';
      target.student_source = 'classio_linked_existing';
      return { data: old?.id || null, error: null };
    },
    from(table) {
      let action = 'select'; let payload; const filters = {};
      const query = {
        select: () => query,
        update: (value) => { action = 'update'; payload = value; return query; },
        eq: (key, value) => { filters[key] = value; return query; },
        limit: () => query,
        maybeSingle: async () => result(table, action, payload, filters),
        then: (resolve, reject) => Promise.resolve(result(table, action, payload, filters)).then(resolve, reject),
      };
      if (table === 'teacher_student_subjects') query.upsert = async (rows) => { state.scopes = rows.map((item) => ({ ...item })); return { error: null }; };
      if (table === 'students') query.insert = async (row) => {
        if (rejectInsert) return { error: new Error('insert failed') };
        if (!allowed.has(row.student_source)) return { error: new Error('students_student_source_check') };
        state.roster.push({ id: 44, ...row }); return { error: null };
      };
      return query;
    },
  };
  return state;
}

const connection = { id: 19, student_id: 'student-1', student_name: 'Student', student_email: '', requested_subjects: ['English'] };
globalThis.fetch = async (_url, init) => {
  assert.equal(String(JSON.parse(init.body).linkIds[0]), '19');
  assert.equal(init.headers.Authorization, 'Bearer valid-token');
  return { ok: true, json: async () => ({ identities: { 19: { name: 'Real Student', email: 'student@example.test', phone: '' } } }) };
};
(async () => {
  let state = fakeClient();
  await loaded.exports.respondToTeacherConnection(connection, true);
  assert.equal(state.link.status, 'active');
  assert.equal(state.scopes[0].status, 'active');
  assert.equal(state.roster[0].student_source, 'classio_link');
  assert.equal(state.roster[0].student, 'Real Student');
  assert.equal(state.roster[0].email, 'student@example.test');

  state = fakeClient([{ id: 7, user_id: 'teacher-1', student: 'Student', email: 'student@example.test', student_source: 'manual', linked_student_user_id: null }]);
  await loaded.exports.respondToTeacherConnection(connection, true, ['English'], '7');
  assert.equal(state.roster[0].student_source, 'classio_linked_existing');
  assert.equal(state.roster[0].linked_student_user_id, 'student-1');

  state = fakeClient([
    { id: 109, user_id: 'teacher-1', student: 'Student', email: '', student_source: 'classio_link', linked_student_user_id: 'student-1' },
    { id: 100, user_id: 'teacher-1', student: 'Real Student', email: 'student@example.test', student_source: 'manual', linked_student_user_id: null },
  ]);
  await loaded.exports.respondToTeacherConnection(connection, true, ['English'], '100');
  assert.equal(state.roster.length, 2, 'the placeholder remains preserved for safe review');
  assert.equal(state.roster[0].linked_student_user_id, null);
  assert.equal(state.roster[1].linked_student_user_id, 'student-1');

  state = fakeClient([{ id: 8, user_id: 'teacher-1', student: 'Student', email: 'student@example.test', student_source: 'manual', linked_student_user_id: null }]);
  await loaded.exports.respondToTeacherConnection(connection, true, ['English']);
  assert.equal(state.roster.length, 1, 'an email match must reuse the existing roster row');
  assert.equal(state.roster[0].linked_student_user_id, 'student-1');

  state = fakeClient([], true);
  await assert.rejects(loaded.exports.respondToTeacherConnection(connection, true), /insert failed/);
  assert.equal(state.link.status, 'pending');
  assert.equal(state.scopes[0].status, 'archived');
  console.log('Teacher connection acceptance and schema source contract passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
