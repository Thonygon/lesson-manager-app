import type { StudentWorkspace } from '@/services/student-data';

const RESOURCE_KINDS = new Set(['worksheet', 'exam', 'video']);
const FINALIZED_ASSIGNMENT_STATUSES = new Set(['submitted', 'graded', 'completed', 'cancelled', 'archived']);

export function recommendationExcludedIds(workspace: StudentWorkspace | null): Set<string> {
  const excluded = new Set<string>();
  const assignmentsById = new Map((workspace?.assignments ?? []).map((row) => [String(row.id || ''), row]));
  for (const session of workspace?.sessions ?? []) {
    const kind = String(session.source_type || '').trim();
    const id = String(session.source_id || '').trim();
    if (String(session.status || '').toLocaleLowerCase() !== 'completed' || !RESOURCE_KINDS.has(kind) || !id) continue;
    excluded.add(`${kind}:${id}`);
    const assignedResource = assignmentsById.get(id);
    if (assignedResource && String(assignedResource.assignment_type || '').trim() === kind) {
      const resourceId = String(assignedResource.source_record_id || '').trim();
      if (resourceId) excluded.add(`${kind}:${resourceId}`);
    }
  }
  for (const assignment of workspace?.assignments ?? []) {
    const kind = String(assignment.assignment_type || '').trim();
    const id = String(assignment.source_record_id || '').trim();
    const status = String(assignment.status || '').trim().toLocaleLowerCase();
    if (RESOURCE_KINDS.has(kind) && id && FINALIZED_ASSIGNMENT_STATUSES.has(status)) excluded.add(`${kind}:${id}`);
  }
  return excluded;
}
