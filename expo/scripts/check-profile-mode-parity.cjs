const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/profile.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, (name) => name === '@/lib/supabase' ? { requireSupabase: () => { throw new Error('No database access in the mode fixture.'); } } : require(name));
const { profileModeSaveFields } = moduleRef.exports;

assert.deepEqual(profileModeSaveFields({ role: 'teacher', primary_role: 'teacher', can_teach: true, can_study: true, last_active_mode: 'teacher' }, 'student'), {
  role: 'teacher', primary_role: 'teacher', can_teach: true, can_study: true, last_active_mode: 'student',
});
assert.deepEqual(profileModeSaveFields({ role: 'student', primary_role: 'student', can_teach: false, can_study: true }, 'teacher'), {
  role: 'student', primary_role: 'student', can_teach: true, can_study: true, last_active_mode: 'teacher',
});
assert.deepEqual(profileModeSaveFields({ role: 'admin', primary_role: 'teacher', can_teach: true, can_study: false }, 'student'), {
  role: 'admin', primary_role: 'teacher', can_teach: true, can_study: true, last_active_mode: 'student',
});
assert.deepEqual(profileModeSaveFields({ role: 'teacher', primary_role: 'teacher', can_teach: false, can_study: false }, 'student'), {
  role: 'teacher', primary_role: 'teacher', can_teach: false, can_study: true, last_active_mode: 'student',
});
process.stdout.write('Profile mode capability preservation fixtures passed.\n');
