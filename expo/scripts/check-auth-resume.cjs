const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/auth-session-transition.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, require);
const { authSessionTransition } = moduleRef.exports;

const user = { id: 'teacher-1' };
const profile = { user_id: 'teacher-1', role: 'teacher', last_active_mode: 'teacher' };
const active = { configured: true, loading: false, session: { user, access_token: 'old' }, user, profile, error: null };

const refresh = authSessionTransition(active, { user: { id: 'teacher-1' }, access_token: 'new' });
assert.equal(refresh.state.loading, false, 'refresh must leave the protected stack mounted');
assert.equal(refresh.state.profile, profile, 'refresh must preserve the current profile and route access');
assert.equal(refresh.state.session.access_token, 'new');
assert.equal(refresh.loadProfile, false, 'token refresh must not fetch the profile again');

const explicit = authSessionTransition(active, active.session, true);
assert.equal(explicit.state.loading, false);
assert.equal(explicit.loadProfile, true, 'explicit role or profile refresh must still reload profile');

const switched = authSessionTransition(active, { user: { id: 'student-2' } });
assert.equal(switched.state.loading, true);
assert.equal(switched.state.profile, null, 'another account must not see the prior profile');
assert.equal(switched.loadProfile, true);

const signedOut = authSessionTransition(active, null);
assert.equal(signedOut.state.loading, false);
assert.equal(signedOut.state.user, null);
assert.equal(signedOut.state.profile, null);
assert.equal(signedOut.loadProfile, false);

const restored = authSessionTransition({ ...signedOut.state, loading: true }, active.session);
assert.equal(restored.state.loading, true, 'cold restoration must wait for profile authorization');
assert.equal(restored.loadProfile, true);

console.log('Auth resume fixtures passed');
