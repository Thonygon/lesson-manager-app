const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/route-access.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', compiled)(loaded, loaded.exports);
const { requiresRoleSelection, activeFace, authorizedDestination, helpWorkspacePath, privilegedDeepLinkToRestore } = loaded.exports;

assert.equal(requiresRoleSelection(null), true);
assert.equal(requiresRoleSelection({ role: 'teacher', login_count: 0 }), true);
assert.equal(requiresRoleSelection({ role: 'student', login_count: 1 }), false);
assert.equal(requiresRoleSelection({ role: 'student', login_count: 0, onboarding_completed: true }), false);
assert.equal(requiresRoleSelection({ role: 'admin', login_count: 0 }), false);
assert.equal(activeFace({ role: 'student', primary_role: 'student', last_active_mode: null }), 'student');
assert.equal(activeFace({ role: 'teacher', primary_role: 'teacher', last_active_mode: 'student' }), 'student');
assert.equal(authorizedDestination('/admin-accounts', { role: 'teacher' }, { loading: false, isAdmin: false, canUseDeveloperWorkspace: false }), '/home');
assert.equal(authorizedDestination('/admin-accounts', { role: 'admin' }, { loading: false, isAdmin: true, canUseDeveloperWorkspace: true }), null);
assert.equal(helpWorkspacePath('/help', '/admin-accounts', { isAdmin: true, canUseDeveloperWorkspace: true }), '/admin-accounts');
assert.equal(privilegedDeepLinkToRestore('/admin?tab=overview', '/help', { role: 'admin' }, { loading: false, isAdmin: true, canUseDeveloperWorkspace: true }), '/admin?tab=overview');
assert.equal(privilegedDeepLinkToRestore('/admin', '/admin', { role: 'admin' }, { loading: false, isAdmin: true, canUseDeveloperWorkspace: true }), null);
assert.equal(privilegedDeepLinkToRestore('/admin', '/help', { role: 'teacher' }, { loading: false, isAdmin: false, canUseDeveloperWorkspace: false }), null);
assert.equal(privilegedDeepLinkToRestore('/developer-workspace', '/help', { role: 'teacher' }, { loading: false, isAdmin: false, canUseDeveloperWorkspace: true }), '/developer-workspace');
assert.equal(privilegedDeepLinkToRestore('/help', '/admin', { role: 'admin' }, { loading: false, isAdmin: true, canUseDeveloperWorkspace: true }), null);
process.stdout.write('Role entry routing fixture passed.\n');
