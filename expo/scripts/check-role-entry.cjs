const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/route-access.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const { requiresRoleSelection, activeFace } = loaded.exports;

assert.equal(requiresRoleSelection(null), true);
assert.equal(requiresRoleSelection({ role: 'teacher', login_count: 0 }), true);
assert.equal(requiresRoleSelection({ role: 'student', login_count: 1 }), false);
assert.equal(requiresRoleSelection({ role: 'student', login_count: 0, onboarding_completed: true }), false);
assert.equal(requiresRoleSelection({ role: 'admin', login_count: 0 }), false);
assert.equal(activeFace({ role: 'student', primary_role: 'student', last_active_mode: null }), 'student');
assert.equal(activeFace({ role: 'teacher', primary_role: 'teacher', last_active_mode: 'student' }), 'student');
process.stdout.write('Role entry routing fixture passed.\n');
