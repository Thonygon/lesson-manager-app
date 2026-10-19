export const assignmentTypeKey = (value: unknown) => `assignmentLabels.type.${String(value || 'worksheet')}`;
export const assignmentStatusKey = (value: unknown) => `assignmentLabels.status.${String(value || 'assigned')}`;

export const exerciseTypeKey = (value: unknown) => `assignmentLabels.exercise.${String(value || '').toLowerCase().replaceAll(' ', '_')}`;
export function exerciseTypeLabel(value: unknown, t: (key: string) => string) {
  const code = String(value || '').trim().toLowerCase().replaceAll(' ', '_').replace('fill_in_the_blanks', 'fill_in_blank');
  const local = exerciseTypeKey(code);
  if (t(local) !== local) return t(local);
  const student = `student.exercise.${code}`;
  return t(student) !== student ? t(student) : code.replaceAll('_', ' ');
}
