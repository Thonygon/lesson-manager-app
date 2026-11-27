const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function load(relativePath, requireModule = () => ({})) {
  const source = fs.readFileSync(path.join(__dirname, '..', relativePath), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const moduleRef = { exports: {} };
  new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, requireModule);
  return moduleRef.exports;
}

const { inboundDateRange, eventOverlapsLocalRange } = load('src/server/google-calendar-inbound.ts');
const { mergeGoogleCalendarEvents, googleEventMatchesClassioLesson } = load('src/services/calendar-workspace.ts');
assert.deepEqual(inboundDateRange('2026-11-01', '2026-11-30'), { first: '2026-11-01T00:00:00.000Z', lastExclusive: '2026-12-01T00:00:00.000Z' });
assert.throws(() => inboundDateRange('2026-02-30', '2026-03-01'), /valid|63 days/);
assert.throws(() => inboundDateRange('2026-01-01', '2026-04-01'), /63 days/);
assert.equal(eventOverlapsLocalRange({ start_at: '2026-11-26T22:00:00Z', end_at: '2026-11-26T23:00:00Z', all_day: false, date_key: '' }, '2026-11-27', '2026-11-27', 'Australia/Brisbane'), true, 'UTC+10 morning event belongs to the selected local day');
assert.equal(eventOverlapsLocalRange({ start_at: '2026-11-28T06:00:00Z', end_at: '2026-11-28T07:00:00Z', all_day: false, date_key: '' }, '2026-11-27', '2026-11-27', 'America/Los_Angeles'), true, 'UTC-8 evening event belongs to the selected local day');
assert.equal(eventOverlapsLocalRange({ start_at: '2026-11-28T06:00:00Z', end_at: '2026-11-28T07:00:00Z', all_day: false, date_key: '' }, '2026-11-28', '2026-11-28', 'America/Los_Angeles'), false, 'the same event must not spill into the next local day');
assert.equal(eventOverlapsLocalRange({ start_at: '2026-11-27T00:00:00Z', end_at: '2026-11-28T00:00:00Z', all_day: true, date_key: '2026-11-27' }, '2026-11-28', '2026-11-28', 'Australia/Brisbane'), false, 'all-day end dates are exclusive');

const classio = [{ key: 'local', student: 'Alice', date: '2026-11-27', time: '10:00', duration: 60, source: 'weekly', note: '' }];
const google = [
  { calendarId: 'primary', id: 'overlap', title: 'Google lesson', startAt: '2026-11-27T10:00:00Z', endAt: '2026-11-27T11:00:00Z', allDay: false, dateKey: '', status: 'confirmed', htmlLink: '', studentId: 1, student: 'Alice', etag: '' },
  { calendarId: 'primary', id: 'day', title: 'Holiday', startAt: '2026-11-27T00:00:00Z', endAt: '2026-11-28T00:00:00Z', allDay: true, dateKey: '2026-11-27', status: 'confirmed', htmlLink: '', studentId: null, student: '', etag: '' },
];
const events = mergeGoogleCalendarEvents(classio, google, '2026-11-27', '2026-11-28');
assert.equal(events.filter((event) => event.date === '2026-11-27').length, 3, 'overlapping events must remain separate');
assert.equal(events.filter((event) => event.date === '2026-11-28').length, 0, 'exclusive midnight end must not render the next day');
assert.equal(events.filter((event) => event.source === 'google').length, 2);
assert.equal(classio.length, 1, 'external events must not change Classio schedules');
const localStart = new Date('2026-11-27T10:00:00');
const localGoogle = { ...google[0], startAt: localStart.toISOString(), endAt: new Date(localStart.getTime() + 60 * 60_000).toISOString() };
assert.equal(googleEventMatchesClassioLesson(classio, localGoogle, 'Alice'), true, 'same student and local start time should warn');
assert.equal(googleEventMatchesClassioLesson(classio, localGoogle, 'Bob'), false, 'another student is not a duplicate');
assert.equal(googleEventMatchesClassioLesson(classio, { ...localGoogle, startAt: new Date(localStart.getTime() + 15 * 60_000).toISOString() }, 'Alice'), false, 'overlap alone should not warn');
assert.equal(googleEventMatchesClassioLesson(classio, { ...localGoogle, allDay: true }, 'Alice'), false, 'all-day events cannot become linked lessons');
const writes = [];
process.env.SUPABASE_URL = 'https://fixture.example';
process.env.SUPABASE_SECRET_KEY = 'fixture-key';
const db = { from(table) { return {
  upsert(payload) { writes.push([table, 'upsert', payload]); return Promise.resolve({ error: null }); },
  delete() { return { eq(column, value) { writes.push([table, 'delete', column, value]); return Promise.resolve({ error: null }); } }; },
  update(payload) { return { eq(column, value) { writes.push([table, 'update', payload, column, value]); return Promise.resolve({ error: null }); } }; },
}; } };
const { saveTokens } = load('src/server/google-calendar.ts', (name) => name === '@supabase/supabase-js' ? { createClient: () => db } : require(name));
(async () => {
  const tokens = { token: 'access', refresh_token: 'refresh', expires_at: 1800000000000 };
  await saveTokens('fixture-user', tokens);
  assert.equal(writes[0][0], 'classio_google_calendar_credentials');
  assert.equal(writes[1][0], 'profiles');
  assert.deepEqual(JSON.parse(writes[1][2].gcal_tokens), tokens, 'Streamlit must receive Expo credentials');
  await saveTokens('fixture-user', null);
  assert.equal(writes[2][1], 'delete');
  assert.equal(writes[3][2].gcal_tokens, null, 'disconnect must clear legacy credentials');
  console.log('Google Calendar inbound fixtures passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });
