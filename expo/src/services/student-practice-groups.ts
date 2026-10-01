import { canonicalSubjectKey, canonicalSubjectLabel, type TranslationLookup } from '@/lib/subjects';
import type { ClassioRecord } from '@/services/classio-data';

export type PracticeSubjectGroup = { key: string; label: string; rows: ClassioRecord[] };

/** Mirrors Streamlit's subject + teacher grouping, preserving input order within each group. */
export function groupPracticeRows(
  rows: ClassioRecord[], scopeFor: (row: ClassioRecord) => { teacherId?: unknown; teacherName?: unknown },
  t?: TranslationLookup,
): PracticeSubjectGroup[] {
  const groups = new Map<string, PracticeSubjectGroup & { subject: string; teacherName: string }>();
  const counts = new Map<string, number>();
  for (const row of rows) {
    const rawSubject = String(row.subject || '').trim();
    if (!rawSubject) continue;
    const subject = canonicalSubjectKey(rawSubject);
    const scope = scopeFor(row);
    const teacherId = String(scope.teacherId || '').trim();
    const groupKey = `${subject}\u0000${teacherId}`;
    if (!groups.has(groupKey)) {
      groups.set(groupKey, { key: groupKey, label: '', rows: [], subject, teacherName: String(scope.teacherName || '').trim() });
      counts.set(subject, (counts.get(subject) || 0) + 1);
    }
    groups.get(groupKey)!.rows.push(row);
  }
  return [...groups.values()].sort((a, b) => a.key.localeCompare(b.key)).map((group) => {
    const teacher = group.teacherName || group.key.split('\u0000')[1].slice(0, 8);
    return {
      key: group.key,
      label: `📚 ${canonicalSubjectLabel(group.subject, t)}${(counts.get(group.subject) || 0) > 1 && teacher ? ` · ${teacher}` : ''}`,
      rows: group.rows,
    };
  });
}
