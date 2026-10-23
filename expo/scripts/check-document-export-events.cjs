const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/document-export-events.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
let session = { access_token: 'user-token' };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => ({ auth: { getSession: async () => ({ data: { session }, error: null }) } }) };
  throw new Error(`Unexpected import: ${name}`);
});
const { recordedDocumentExport } = loaded.exports;

async function main() {
  const originalFetch = global.fetch;
  const events = [];
  let prepared = 0;
  try {
    global.fetch = async (_url, options) => {
      assert.equal(options.headers.Authorization, 'Bearer user-token');
      events.push(JSON.parse(options.body));
      return Response.json({ eventId: events.at(-1).eventId });
    };
    await recordedDocumentExport('pdf', 'worksheet', 'student', async () => { prepared += 1; });
    assert.equal(prepared, 1);
    assert.deepEqual(events.map(({ action, status }) => [action, status]), [['start', undefined], ['finish', 'handoff_requested']]);
    assert.equal(events[0].eventId, events[1].eventId);
    assert.doesNotMatch(JSON.stringify(events), /student_name|prompt|filename|private-content/);
    global.fetch = async () => new Response(null, { status: 503 });
    await assert.rejects(recordedDocumentExport('docx', 'exam', 'answers', async () => { prepared += 1; }), /could not be recorded/);
    assert.equal(prepared, 1, 'a failed start must prevent file preparation');
    session = null;
    await recordedDocumentExport('pdf', 'lesson_plan', 'full', async () => { prepared += 1; });
    assert.equal(prepared, 2, 'public downloads remain available without an account');
  } finally { global.fetch = originalFetch; }
  const routeSource = fs.readFileSync(path.join(__dirname, '../src/app/api/document-export-event+api.ts'), 'utf8');
  const routeCompiled = ts.transpileModule(routeSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const route = { exports: {} };
  const databaseWrites = [];
  new Function('module', 'exports', 'require', routeCompiled)(route, route.exports, (name) => {
    if (name !== '@supabase/supabase-js') throw new Error(`Unexpected import: ${name}`);
    return { createClient: (_url, key) => key === 'anon-key'
      ? { auth: { getUser: async () => ({ data: { user: { id: '00000000-0000-4000-8000-000000000001' } }, error: null }) } }
      : { from: (table) => ({
        insert: async (payload) => { databaseWrites.push({ table, action: 'insert', payload }); return { error: null }; },
        update: (payload) => {
          const filters = [];
          return { eq(column, value) { filters.push([column, value]); return this; }, async select() { databaseWrites.push({ table, action: 'update', payload, filters }); return { data: [{ event_id: 'ok' }], error: null }; } };
        },
      }) } };
  });
  const oldEnv = [process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY, process.env.SUPABASE_SECRET_KEY];
  process.env.SUPABASE_URL = 'https://supabase.test'; process.env.SUPABASE_ANON_KEY = 'anon-key'; process.env.SUPABASE_SECRET_KEY = 'server-key';
  try {
    const eventId = '00000000-0000-4000-8000-000000000002';
    const request = (body, authenticated = true) => new Request('https://classio.test/api/document-export-event', { method: 'POST', headers: { ...(authenticated ? { Authorization: 'Bearer user-token' } : {}), 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    assert.equal((await route.exports.POST(request({ action: 'start', eventId, format: 'pdf', documentKind: 'student_history', variant: 'full' }, false))).status, 401);
    assert.equal((await route.exports.POST(request({ action: 'start', eventId, format: 'pdf', documentKind: 'student_history', variant: 'full', filename: 'private.pdf' }))).status, 201);
    assert.equal((await route.exports.POST(request({ action: 'finish', eventId, status: 'handoff_requested' }))).status, 200);
    assert.equal(databaseWrites.length, 2);
    assert.equal(databaseWrites[0].payload.actor_user_id, '00000000-0000-4000-8000-000000000001');
    assert.equal(databaseWrites[0].payload.filename, undefined);
    assert.deepEqual(databaseWrites[1].filters.slice(1), [['actor_user_id', '00000000-0000-4000-8000-000000000001'], ['source', 'expo'], ['status', 'started']]);
  } finally {
    [process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY, process.env.SUPABASE_SECRET_KEY] = oldEnv;
  }
  console.log('Document export requests are correlated, metadata-only and fail closed for signed-in users.');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
