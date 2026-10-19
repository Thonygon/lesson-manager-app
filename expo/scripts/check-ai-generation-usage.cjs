const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const filename = path.join(__dirname, '../src/server/ai-generation-usage.ts');
const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', source)(moduleRef, moduleRef.exports);
const { checkAiGenerationUsage, logAiGeneration, incrementAiGenerationUsage } = moduleRef.exports;
const originalFetch = global.fetch;
const context = { base: 'https://supabase.test', serverKey: 'server-secret', userId: 'owner-id', kind: 'plan', profilePlan: 'free' };
let plan = { active: true, features_json: { ai_tools: true }, limits_json: { ai_generations: 10 } };
let used = 0;
let lastAt = null;
let counterUnavailable = false;
const writes = [];

async function main() {
  try {
    global.fetch = async (input, options) => {
      const url = new URL(String(input));
      assert.equal(options.headers.Authorization, 'Bearer server-secret');
      assert.equal(url.searchParams.get('user_id') || 'eq.owner-id', 'eq.owner-id');
      if (options.method === 'POST') { writes.push({ table: url.pathname.split('/').pop(), body: JSON.parse(options.body) }); return new Response(null, { status: 201 }); }
      if (url.pathname.endsWith('/user_subscriptions')) return Response.json([{ plan_id: 'teacher_pro', subscription_status: 'active', plans: plan }]);
      if (url.pathname.endsWith('/profiles')) return Response.json([{ current_plan: 'free' }]);
      if (url.pathname.endsWith('/plans')) return Response.json([plan]);
      if (url.pathname.endsWith('/usage_tracking')) return counterUnavailable ? Response.json({ message: 'counter unavailable' }, { status: 503 }) : Response.json([{ ai_generations: used }]);
      if (url.pathname.endsWith('/ai_usage_logs') && url.searchParams.get('status') === 'eq.success') return new Response('[]', { status: 200, headers: { 'content-range': `*/${used}` } });
      if (url.pathname.endsWith('/ai_usage_logs')) return Response.json(lastAt ? [{ created_at: lastAt }] : []);
      throw new Error(`Unexpected ${url.pathname}`);
    };
    assert.equal((await checkAiGenerationUsage(context, 20000)).allowed, true);
    plan = { ...plan, features_json: { ai_tools: false } };
    assert.equal((await checkAiGenerationUsage(context, 20000)).status, 403);
    plan = { ...plan, features_json: { ai_tools: true } };
    used = 10;
    assert.equal((await checkAiGenerationUsage(context, 20000)).status, 429);
    used = 3; lastAt = new Date(15000).toISOString();
    assert.equal((await checkAiGenerationUsage(context, 20000)).allowed, true);
    lastAt = null;
    counterUnavailable = true;
    const fromLogs = await checkAiGenerationUsage(context, 20000);
    assert.equal(fromLogs.allowed, true);
    assert.equal(fromLogs.source, 'logs');
    assert.equal(fromLogs.used, 3);
    counterUnavailable = false;
    await logAiGeneration(context, 'requested', { subject: 'Spanish' });
    await incrementAiGenerationUsage(context, 3);
    assert.equal(writes[0].table, 'ai_usage_logs');
    assert.equal(writes[0].body.user_id, 'owner-id');
    assert.deepEqual(writes[1], { table: 'usage_tracking', body: { user_id: 'owner-id', ai_generations: 4 } });
    const program = { ...context, kind: 'program' };
    assert.equal((await checkAiGenerationUsage(program)).allowed, true);
  } finally { global.fetch = originalFetch; }
  process.stdout.write('AI generation usage fixtures passed.\n');
}
void main();
