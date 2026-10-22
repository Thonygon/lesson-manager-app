const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const service = fs.readFileSync(path.join(__dirname, '../src/services/classio-data.ts'), 'utf8');
const screen = fs.readFileSync(path.join(__dirname, '../src/app/(app)/payments.tsx'), 'utf8');
const sql = fs.readFileSync(path.join(__dirname, '../../streamlit/migrations/manual_payment_insert_transaction.sql'), 'utf8');
const streamlitService = fs.readFileSync(path.join(__dirname, '../../streamlit/core/database.py'), 'utf8');
const streamlitAdd = streamlitService.split('def add_payment(')[1].split('def delete_row(')[0];
const add = service.split('export async function addPayment(')[1].split('export async function updatePayment(')[0];

assert.match(add, /rpc\('classio_add_manual_payment'/);
assert.doesNotMatch(add, /from\('payments'\)\.insert/);
assert.doesNotMatch(add, /recalculatePackageDates/);
assert.match(screen, /pendingPayment\.current\?\.payload !== payload/);
assert.match(screen, /addPayment\(input, paymentRequestKey\(input\)\)/);
assert.match(sql, /primary key \(user_id, request_id\)/i);
assert.match(sql, /pg_advisory_xact_lock/);
assert.match(sql, /insert into public\.payments/);
assert.match(sql, /insert into public\.students/);
assert.match(sql, /values \(p_user_id::uuid, v_student\)/);
assert.match(sql, /where user_id = p_user_id::uuid and student = v_student/);
assert.match(sql, /update public\.payments/);
assert.match(sql, /v_saved\.payment_id is not null/);
assert.doesNotMatch(sql, /payload jsonb not null/i);
assert.match(streamlitAdd, /sb\.rpc\("classio_add_manual_payment"/);
assert.doesNotMatch(streamlitAdd, /sb\.table\("payments"\)\.insert/);
console.log('Manual payment inserts use one transactional RPC and reuse the request key on retry.');
