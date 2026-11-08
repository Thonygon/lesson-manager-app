export type RosterMatch = 'linked' | 'email' | 'phone' | 'name';
export type RosterCandidate = { id: string; student: string; email: string; phone: string; match: RosterMatch };
export type RosterRow = { id: string | number; student?: string | null; email?: string | null; phone?: string | null; linked_student_user_id?: string | null };

const normalized = (value: unknown) => String(value || '').trim().normalize('NFKC').replace(/\s+/g, ' ').toLocaleLowerCase();
const phoneDigits = (value: unknown) => String(value || '').replace(/\D/g, '');

export function rosterCandidates(rows: RosterRow[], student: { id: string; name: string; email?: string; phone?: string }): RosterCandidate[] {
  const email = normalized(student.email);
  const name = normalized(student.name);
  const phone = phoneDigits(student.phone);
  return rows.flatMap((row) => {
    if (row.linked_student_user_id && String(row.linked_student_user_id) !== student.id) return [];
    const match: RosterMatch | null = row.linked_student_user_id === student.id ? 'linked'
      : email && normalized(row.email) === email ? 'email'
      : phone.length >= 7 && phoneDigits(row.phone) === phone ? 'phone'
      : name && normalized(row.student) === name ? 'name' : null;
    return match ? [{ id: String(row.id), student: String(row.student || 'Student'), email: String(row.email || ''), phone: String(row.phone || ''), match }] : [];
  }).sort((a, b) => ['email', 'phone', 'name', 'linked'].indexOf(a.match) - ['email', 'phone', 'name', 'linked'].indexOf(b.match));
}
