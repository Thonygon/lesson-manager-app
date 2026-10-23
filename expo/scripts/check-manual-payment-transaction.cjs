const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const service = fs.readFileSync(path.join(__dirname, '../src/services/classio-data.ts'), 'utf8');
const screen = fs.readFileSync(path.join(__dirname, '../src/app/(app)/payments.tsx'), 'utf8');
const sql = fs.readFileSync(path.join(__dirname, '../../streamlit/migrations/teacher_ledger_mutations_transaction.sql'), 'utf8');
const streamlitService = fs.readFileSync(path.join(__dirname, '../../streamlit/core/database.py'), 'utf8');
const streamlitAdd = streamlitService.split('def add_payment(')[1].split('def delete_row(')[0];
const add = service.split('export async function addPayment(')[1].split('export async function updatePayment(')[0];

assert.match(add, /mutateTeacherLedger\('payment', 'add', null,/);
assert.doesNotMatch(add, /from\('payments'\)\.insert/);
assert.doesNotMatch(add, /classio_add_manual_payment/);
assert.match(add, /}, requestId\);/);
assert.match(service, /rpc\('classio_mutate_teacher_ledger'/);
assert.match(screen, /pendingPayment\.current\?\.payload !== payload/);
assert.match(screen, /addPayment\(input, paymentRequestKey\(input\)\)/);
assert.match(sql, /primary key \(user_id, request_id\)/i);
assert.match(sql, /pg_advisory_xact_lock/);
assert.match(sql, /insert into public\.payments/);
assert.match(sql, /insert into public\.students/);
assert.match(sql, /values \(p_user_id::uuid,v_new_student\)/);
assert.match(sql, /public\.classio_recalculate_teacher_packages\(p_user_id,v_student\)/);
assert.match(sql, /update public\.payments/);
assert.match(sql, /v_saved\.result is not null then return/);
assert.match(streamlitAdd, /_mutate_teacher_ledger\("payment", "add", None, payload, request_id=request_id\)/);
assert.doesNotMatch(streamlitAdd, /sb\.table\("payments"\)\.insert/);
const compiled = ts.transpileModule(service, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const calls = [];
let rpcError = null;
const client = {
  auth: { getUser: async () => ({ data: { user: { id: 'owner-id' } }, error: null }) },
  rpc: async (name, args) => { calls.push({ name, args }); return { data: { id: 9, replayed: calls.length > 1 }, error: rpcError }; },
  from: () => { throw new Error('Payment insert must not write directly to a table.'); },
};
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase: () => client };
  if (name === '@/lib/record-input-validation') return { isValidRecordDate: () => true, isValidUnitCount: () => true, isValidUnitAdjustment: () => true };
  if (name === '@/services/teacher-history-pagination') return { readTeacherHistory: () => [] };
  throw new Error(`Unexpected import ${name}`);
});

async function main() {
  const input = { student: ' S07-A ', lessonUnits: 2, paymentDate: '2026-10-22', paidAmount: 100, currency: 'TRY', modality: 'Online', subject: 'English' };
  await moduleRef.exports.addPayment(input, 'same-request-id');
  await moduleRef.exports.addPayment(input, 'same-request-id');
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[0], calls[1]);
  assert.equal(calls[0].name, 'classio_mutate_teacher_ledger');
  assert.deepEqual(calls[0].args, {
    p_user_id: 'owner-id', p_request_id: 'same-request-id', p_entity: 'payment', p_action: 'add', p_row_id: null,
    p_payload: { student: 'S07-A', number_of_lesson: 2, payment_date: '2026-10-22', paid_amount: 100, currency: 'TRY', modality: 'Online', subject: 'English', subject_custom: null, package_start_date: '2026-10-22' },
  });
  rpcError = new Error('transaction rolled back');
  await assert.rejects(moduleRef.exports.addPayment(input, 'new-request-id'), /transaction rolled back/);
  console.log('Expo and Streamlit payment inserts use the transactional teacher ledger RPC and reuse request keys.');
}
void main();
