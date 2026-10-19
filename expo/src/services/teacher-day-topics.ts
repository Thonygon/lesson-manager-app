import { requireSupabase } from '@/lib/supabase';

type Row = Record<string, unknown>;
const clean = (value: unknown) => String(value ?? '').trim();
const key = (value: unknown) => clean(value).toLocaleLowerCase();

export async function getTeacherDayTopics(teacherId: string, students: { name: string; userId?: string }[]): Promise<Record<string, string>> {
  const names = new Set(students.map((student) => key(student.name)).filter(Boolean));
  const users = new Set(students.map((student) => clean(student.userId)).filter(Boolean));
  if (!teacherId || (!names.size && !users.size)) return {};
  const client = requireSupabase();
  const assignmentsResult = await client.from('learning_program_assignments')
    .select('id,program_id,student_name,student_user_id,status,updated_at')
    .eq('teacher_id', teacherId).neq('status', 'archived')
    .order('updated_at', { ascending: false }).limit(200);
  if (assignmentsResult.error) throw assignmentsResult.error;
  const assignments = ((assignmentsResult.data ?? []) as Row[]).filter((row) => (users.has(clean(row.student_user_id)) || names.has(key(row.student_name))) && clean(row.status) !== 'completed');
  if (!assignments.length) return {};
  const assignmentIds = assignments.map((row) => row.id).filter(Boolean);
  const programIds = [...new Set(assignments.map((row) => row.program_id).filter(Boolean))];
  if (!programIds.length) return {};
  const [topicsResult, progressResult] = await Promise.all([
    client.from('learning_program_topics').select('id,program_id,unit_number,topic_number,title').in('program_id', programIds).order('unit_number').order('topic_number').limit(1000),
    client.from('learning_program_progress').select('assignment_id,topic_id,teacher_done').in('assignment_id', assignmentIds).limit(1000),
  ]);
  if (topicsResult.error || progressResult.error) throw topicsResult.error ?? progressResult.error;
  const topics = (topicsResult.data ?? []) as Row[];
  const completed = new Set(((progressResult.data ?? []) as Row[]).filter((row) => row.teacher_done === true).map((row) => `${clean(row.assignment_id)}:${clean(row.topic_id)}`));
  const result: Record<string, string> = {};
  for (const assignment of assignments) {
    const student = students.find((item) => item.userId && item.userId === clean(assignment.student_user_id)) || students.find((item) => key(item.name) === key(assignment.student_name));
    if (!student || result[key(student.name)]) continue;
    const next = topics.find((topic) => clean(topic.program_id) === clean(assignment.program_id) && !completed.has(`${clean(assignment.id)}:${clean(topic.id)}`));
    if (next?.title) result[key(student.name)] = clean(next.title);
  }
  return result;
}
