import type { StudentWorkspace } from '@/services/student-data';

const RESOURCE_KINDS = new Set(['worksheet', 'exam', 'video']);
const FINALIZED_ASSIGNMENT_STATUSES = new Set(['submitted', 'graded', 'completed', 'cancelled', 'archived']);

export function recommendationExcludedIds(workspace: StudentWorkspace | null): Set<string> {
  const excluded = new Set<string>();
  for (const session of workspace?.sessions ?? []) {
    const kind = String(session.source_type || '').trim();
    const id = String(session.source_id || '').trim();
    if (session.status === 'completed' && RESOURCE_KINDS.has(kind) && id) excluded.add(`${kind}:${id}`);
  }
  for (const assignment of workspace?.assignments ?? []) {
    const kind = String(assignment.assignment_type || '').trim();
    const id = String(assignment.source_record_id || '').trim();
    const status = String(assignment.status || '').trim().toLocaleLowerCase();
    if (RESOURCE_KINDS.has(kind) && id && FINALIZED_ASSIGNMENT_STATUSES.has(status)) excluded.add(`${kind}:${id}`);
  }
  return excluded;
}
