const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function compiled(relative, imports = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', relative), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', 'require', code)(moduleRef, moduleRef.exports, (name) => imports[name] || require(name));
  return moduleRef.exports;
}

const publication = compiled('src/lib/legal-publication.generated.ts');
const legal = compiled('src/lib/legal-acceptance.ts', { '@/lib/legal-publication.generated': publication });
assert.equal(legal.legalModeForProfile({ can_teach: true, role: 'teacher', last_active_mode: 'student' }), 'student');
assert.equal(legal.legalModeForProfile({ can_teach: true, role: 'teacher', last_active_mode: 'teacher' }), 'teacher');
assert.equal(legal.legalModeForProfile({ can_teach: true, role: 'school_admin', last_active_mode: 'student' }), 'teacher');
const terms = publication.LEGAL_PUBLICATION.documents.find((item) => item.slug === 'terms' && item.language === 'en');
const teacherData = publication.LEGAL_PUBLICATION.documents.find((item) => item.slug === 'teacher-data' && item.language === 'en');
const row = (document) => ({ slug: document.slug, language: document.language, version: publication.LEGAL_PUBLICATION.version, sha256: document.sha256, accepted_at: '2026-11-06T00:00:00Z' });

let acceptances = [];
let writes = 0;
const server = { from(table) {
  if (table === 'profiles') return {
    select() { return this; }, eq() { return this; },
    async maybeSingle() { return { data: null, error: null }; },
    async upsert() { writes += 1; return { error: null }; },
  };
  if (table === 'classio_legal_acceptances') return {
    select() { return this; }, eq() { return this; },
    then(resolve) { return Promise.resolve({ data: acceptances, error: null }).then(resolve); },
  };
  throw new Error(`Unexpected read of ${table}`);
} };
const route = compiled('src/app/api/choose-role+api.ts', {
  '@supabase/supabase-js': { createClient: (_url, key) => key === 'server-key' ? server : { auth: { getUser: async () => ({ data: { user: { id: 'actor', email: 'student@example.org' } }, error: null }) } } },
  '@/lib/legal-acceptance': legal,
});

const request = (mode, language = 'en') => new Request('https://classio.test/api/choose-role', {
  method: 'POST', headers: { Authorization: 'Bearer test-token', 'Content-Type': 'application/json' },
  body: JSON.stringify({ mode, language }),
});

async function main() {
  const names = ['SUPABASE_URL', 'SUPABASE_ANON_KEY', 'SUPABASE_SECRET_KEY'];
  const previous = Object.fromEntries(names.map((name) => [name, process.env[name]]));
  try {
    process.env.SUPABASE_URL = 'https://fixture.invalid';
    process.env.SUPABASE_ANON_KEY = 'public-key';
    process.env.SUPABASE_SECRET_KEY = 'server-key';
    const missingTerms = await route.POST(request('student'));
    assert.equal(missingTerms.status, 409);
    assert.equal((await missingTerms.json()).code, 'LEGAL_ACCEPTANCE_REQUIRED');
    assert.equal(writes, 0, 'missing terms must not activate a profile');
    acceptances = [row(terms)];
    assert.equal((await route.POST(request('student'))).status, 200);
    assert.equal((await route.POST(request('teacher'))).status, 409);
    assert.equal(writes, 1, 'student terms must not activate educator access');
    acceptances = [row(terms), row(teacherData)];
    assert.equal((await route.POST(request('teacher'))).status, 200);
    assert.equal(writes, 2);
    assert.equal((await route.POST(request('teacher', 'es'))).status, 409);
    acceptances = [{ ...row(terms), sha256: '0'.repeat(64) }, row(teacherData)];
    assert.equal((await route.POST(request('teacher'))).status, 409);
    assert.equal(writes, 2, 'wrong document hash must not activate a profile');
    process.stdout.write('Initial role legal gate passed.\n');
  } finally {
    for (const name of names) previous[name] === undefined ? delete process.env[name] : process.env[name] = previous[name];
  }
}
void main().catch((error) => { console.error(error); process.exitCode = 1; });
