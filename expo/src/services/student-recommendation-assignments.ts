import type { ClassioRecord } from '@/services/classio-data';
import { studentTopicTokens } from '@/services/student-recommendation-programs';

const text = (value: unknown) => String(value || '').trim();
const number = (value: unknown) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; };
const finalizedStatuses = new Set(['submitted', 'graded', 'completed', 'cancelled', 'archived']);
const resourceTypes = new Set(['worksheet', 'exam', 'video']);

export type ResourceAssignmentSignal = {
  assignmentId: number;
  status: string;
  attemptCount: number;
  teacherName: string;
  teacherNote: string;
  topic: string;
  title: string;
  learningProgramAssignmentId: number;
  learningProgramTopicId: number;
  isCompleted: boolean;
  isUnseen: boolean;
};

export function resourceAssignmentKey(type: string, sourceRecordId: string | number) {
  return `${type}:${sourceRecordId}`;
}

export function buildStudentAssignmentSignals(assignments: ClassioRecord[], teacherNames: Record<string, string> = {}) {
  const resourceAssignments = new Map<string, ResourceAssignmentSignal>();
  const activeAssignedTopicTokens = new Set<string>();
  const unseenVideoTopicTokens = new Set<string>();
  for (const row of assignments) {
    const type = text(row.assignment_type);
    if (!resourceTypes.has(type)) continue;
    const sourceId = text(row.source_record_id);
    if (!sourceId || ['0', 'None', 'nan'].includes(sourceId)) continue;
    const status = text(row.status).toLocaleLowerCase();
    // Streamlit's assignment-signal query does not include attempt_count; missing values resolve to zero.
    const attemptCount = number(row.attempt_count);
    const topic = text(row.topic || row.title);
    const title = text(row.title);
    const teacherNote = text(row.teacher_note);
    const isCompleted = finalizedStatuses.has(status) || (type === 'video' && attemptCount > 0);
    const isUnseen = type === 'video' && attemptCount <= 0 && ['assigned', 'started', 'overdue'].includes(status);
    const key = resourceAssignmentKey(type, sourceId);
    const existing = resourceAssignments.get(key);
    if (!existing || (existing.isCompleted && !isCompleted)) {
      resourceAssignments.set(key, {
        assignmentId: number(row.id), status, attemptCount, teacherName: teacherNames[text(row.teacher_id)] || '',
        teacherNote, topic, title, learningProgramAssignmentId: number(row.learning_program_assignment_id),
        learningProgramTopicId: number(row.learning_program_topic_id), isCompleted, isUnseen,
      });
    }
    if (!isCompleted) for (const token of studentTopicTokens(topic, title, teacherNote)) activeAssignedTopicTokens.add(token);
    if (isUnseen) for (const token of studentTopicTokens(topic, title, teacherNote)) unseenVideoTopicTokens.add(token);
  }
  return { resourceAssignments, activeAssignedTopicTokens, unseenVideoTopicTokens };
}
