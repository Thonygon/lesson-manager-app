import { canonicalSubjectKey, canonicalSubjectLabel, type TranslationLookup } from '@/lib/subjects';

export function groupStudentRecommendations<T extends { subject: string; learningProgramAssignmentId?: number; programTeacherId?: string }>(
  rows: T[], teacherNames: Record<string, string> = {}, t?: TranslationLookup,
) {
  const groups = new Map<string, { key: string; subject: string; teacherId: string; rows: T[] }>();
  const counts = new Map<string, number>();
  for (const row of rows) {
    const subject = canonicalSubjectKey(row.subject);
    const key = row.learningProgramAssignmentId ? `assignment:${row.learningProgramAssignmentId}` : `subject:${subject}`;
    if (!groups.has(key)) {
      groups.set(key, { key, subject, teacherId: row.programTeacherId || '', rows: [] });
      counts.set(subject, (counts.get(subject) || 0) + 1);
    }
    const group = groups.get(key)!;
    if (!group.teacherId && row.programTeacherId) group.teacherId = row.programTeacherId;
    group.rows.push(row);
  }
  return [...groups.values()].map((group) => {
    const teacher = teacherNames[group.teacherId] || group.teacherId.slice(0, 8);
    const label = canonicalSubjectLabel(group.subject, t);
    return { key: group.key, label: (counts.get(group.subject) || 0) > 1 && teacher ? `${label} · ${teacher}` : label, rows: group.rows };
  });
}
