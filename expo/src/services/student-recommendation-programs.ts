import { canonicalSubjectKey } from '@/lib/subjects';
import type { ClassioRecord } from '@/services/classio-data';
import type { StudentWorkspace } from '@/services/student-data';

const text = (value: unknown) => String(value || '').trim();
const number = (value: unknown) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : 0; };
const truthy = (value: unknown) => value === true || ['1', 'true', 'yes', 'on'].includes(text(value).toLocaleLowerCase());

export function studentTopicTokens(...values: unknown[]) {
  const tokens = new Set<string>();
  for (const value of values) {
    for (const raw of text(value).replaceAll('/', ' ').replaceAll('-', ' ').split(/\s+/)) {
      const cleaned = [...raw.toLocaleLowerCase()].filter((character) => /[\p{L}\p{N}]/u.test(character)).join('');
      if (cleaned.length >= 3) tokens.add(cleaned);
    }
  }
  return tokens;
}

export type ProgramTopicScope = { topicId: number; tokens: Set<string>; isComplete: boolean; position: number };
export type ProgramScope = {
  learningProgramAssignmentId: number;
  programId: number;
  teacherId: string;
  subjectDisplay: string;
  level: string;
  topics: ProgramTopicScope[];
};
export type StudentProgramSignals = {
  subjects: Set<string>;
  subjectLevels: Record<string, string>;
  subjectStages: Record<string, string>;
  activeTopicIds: Set<number>;
  nextTopicIds: Set<number>;
  pendingTopicIds: Set<number>;
  reviewTopicIds: Set<number>;
  nextTopicTitles: string[];
  topicTokens: Set<string>;
  nextTopicTokens: Set<string>;
  pendingTopicTokens: Set<string>;
  reviewTopicTokens: Set<string>;
  worksheetTypes: Set<string>;
  examTypes: Set<string>;
  programScopes: Record<string, ProgramScope[]>;
};

function addAll(target: Set<string>, source: Set<string>) { for (const value of source) target.add(value); }
function list(value: unknown) { return Array.isArray(value) ? value.map(text).filter(Boolean) : []; }
function programOf(row: ClassioRecord) { return row.program && typeof row.program === 'object' ? row.program as ClassioRecord : {}; }

export function buildStudentProgramSignals(workspace: Pick<StudentWorkspace, 'programs' | 'topics' | 'progress'>): StudentProgramSignals {
  const signals: StudentProgramSignals = {
    subjects: new Set(), subjectLevels: {}, subjectStages: {}, activeTopicIds: new Set(), nextTopicIds: new Set(),
    pendingTopicIds: new Set(), reviewTopicIds: new Set(), nextTopicTitles: [], topicTokens: new Set(),
    nextTopicTokens: new Set(), pendingTopicTokens: new Set(), reviewTopicTokens: new Set(),
    worksheetTypes: new Set(), examTypes: new Set(), programScopes: {},
  };
  const latest = new Map<string, { assignment: ClassioRecord; sequence: number; stamp: string }>();
  for (const assignment of workspace.programs) {
    const program = programOf(assignment);
    const rawSubject = text(program.subject || assignment.subject_key);
    if (!rawSubject) continue;
    const subject = canonicalSubjectKey(rawSubject);
    const teacherId = text(assignment.teacher_id);
    const key = `${subject}:${teacherId}`;
    const sequence = number(program.sequence_order || assignment.sequence_order);
    const stamp = text(assignment.updated_at || assignment.assigned_at || program.updated_at || program.created_at);
    const current = latest.get(key);
    if (!current || sequence > current.sequence || (sequence === current.sequence && stamp > current.stamp)) latest.set(key, { assignment, sequence, stamp });
  }
  for (const { assignment } of latest.values()) {
    const program = programOf(assignment);
    const subject = canonicalSubjectKey(program.subject || assignment.subject_key);
    signals.subjects.add(subject);
    const level = text(program.level_or_band || assignment.level_or_band);
    const stage = text(program.learner_stage || assignment.learner_stage);
    if (level && !signals.subjectLevels[subject]) signals.subjectLevels[subject] = level;
    if (stage && !signals.subjectStages[subject]) signals.subjectStages[subject] = stage;
    const programId = number(assignment.program_id);
    const assignmentId = number(assignment.id);
    const topics = workspace.topics.filter((topic) => number(topic.program_id) === programId).sort((a, b) => number(a.unit_number) - number(b.unit_number) || number(a.topic_number) - number(b.topic_number));
    const progress = new Map(workspace.progress.filter((row) => number(row.assignment_id) === assignmentId).map((row) => [number(row.topic_id), row]));
    const latestCompleted = topics.reduce((position, topic, index) => truthy(progress.get(number(topic.id))?.teacher_done) ? index + 1 : position, 0);
    const scopeTopics: ProgramTopicScope[] = [];
    let nextAdded = false;
    topics.forEach((topic, index) => {
      const topicId = number(topic.id);
      const state = progress.get(topicId) || {};
      const complete = truthy(state.teacher_done);
      const title = text(topic.title);
      const summary = text(topic.student_summary || topic.lesson_focus || topic.subtopic);
      const tokens = studentTopicTokens(title, summary);
      if (topicId > 0) scopeTopics.push({ topicId, tokens, isComplete: complete, position: index + 1 });
      if (complete && truthy(state.student_done)) { addAll(signals.reviewTopicTokens, tokens); if (topicId > 0) signals.reviewTopicIds.add(topicId); }
      if (!complete && latestCompleted > 0 && index + 1 < latestCompleted) { addAll(signals.pendingTopicTokens, tokens); if (topicId > 0) signals.pendingTopicIds.add(topicId); }
      if (complete) return;
      if (topicId > 0) signals.activeTopicIds.add(topicId);
      if (title) signals.nextTopicTitles.push(title);
      addAll(signals.topicTokens, tokens);
      if (!nextAdded) { addAll(signals.nextTopicTokens, tokens); if (topicId > 0) signals.nextTopicIds.add(topicId); nextAdded = true; }
      if (!title) return;
      for (const value of list(topic.suggested_worksheet_types)) signals.worksheetTypes.add(value);
      for (const value of list(topic.suggested_exam_exercise_types)) signals.examTypes.add(value);
    });
    (signals.programScopes[subject] ||= []).push({ learningProgramAssignmentId: assignmentId, programId, teacherId: text(assignment.teacher_id), subjectDisplay: text(program.subject_display || program.subject), level, topics: scopeTopics });
  }
  return signals;
}
