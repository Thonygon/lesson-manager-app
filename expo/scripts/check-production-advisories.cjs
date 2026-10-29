#!/usr/bin/env node
// Fail on new high/critical production advisories while reporting existing Expo-chain debt.
const { spawnSync } = require('node:child_process');

const baseline = new Set([
  'GHSA-qhr7-859c-m2p7', 'GHSA-6j4f-fj2g-mc7p', 'GHSA-86w9-cpqp-85rv',
  'GHSA-68fv-2mgg-jv7q', 'GHSA-pqg4-j6r4-53mv', 'GHSA-cg2g-xh64-v4q7',
  'GHSA-mrv2-3pqr-j5jr', 'GHSA-mrhx-c7xc-m3w5',
]);
const result = spawnSync('pnpm', ['audit', '--prod', '--json'], { encoding: 'utf8', maxBuffer: 12 * 1024 * 1024, timeout: 120000 });
if (result.error) throw result.error;
let report;
try { report = JSON.parse(result.stdout); } catch { throw new Error(`pnpm audit returned no valid report: ${result.stderr || result.stdout}`); }
if (report.error || !report.advisories || !report.metadata?.vulnerabilities) {
  throw new Error(`pnpm audit unavailable: ${report.error?.message || 'missing advisory data'}`);
}
const serious = Object.values(report.advisories).filter((item) => ['high', 'critical'].includes(item.severity));
const currentIds = new Set(serious.map((item) => item.github_advisory_id));
const newlyReported = serious.filter((item) => !baseline.has(item.github_advisory_id));
const resolved = [...baseline].filter((id) => !currentIds.has(id));
for (const item of serious) process.stdout.write(`${item.severity.toUpperCase()} ${item.github_advisory_id} ${item.module_name} ${baseline.has(item.github_advisory_id) ? '(existing)' : '(NEW)'}\n`);
if (resolved.length) process.stdout.write(`Resolved baseline IDs (remove from script): ${resolved.join(', ')}\n`);
if (newlyReported.length) process.exitCode = 1;
