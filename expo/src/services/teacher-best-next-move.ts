import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Href } from 'expo-router';

import { canonicalSubjectLabel } from '@/lib/subjects';
import { requireSupabase } from '@/lib/supabase';
import { buildCalendarEvents, getCalendarWorkspace, type CalendarEvent } from '@/services/calendar-workspace';
import { getResourceLibrary } from '@/services/resource-library';
import type { PackageInsight, TeacherDataset } from '@/services/teacher-insights';

type Row = Record<string, unknown>;
const text = (value: unknown) => String(value ?? '').trim();
const norm = (value: unknown) => text(value).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const dayOffset = (date: Date, days: number) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
const toTime = (value: unknown) => { const time = new Date(text(value)).valueOf(); return Number.isFinite(time) ? time : 0; };

export type NextMoveKind = 'review' | 'practice' | 'overused' | 'renewal' | 'record_lesson' | 'material_gap' | 'practice_gap' | 'prepare_lesson' | 'assign_practice' | 'confirm_lesson' | 'plan_program';
export type TeacherNextMove = {
  id: string;
  kind: NextMoveKind;
  priority: number;
  icon: string;
  titleKey: string;
  reasonKey: string;
  actionKey: string;
  params: Record<string, string | number>;
  href: Href;
  dueAt?: number;
};
export type NextMoveTopic = {
  assignmentId: string;
  topicId: string;
  programId: string;
  studentId: string;
  student: string;
  title: string;
  subject: string;
  stage: string;
  level: string;
  targetDate: string;
  material: 'related' | 'no_clear_match' | 'unknown';
  practiceAvailable: boolean;
  planAvailable: boolean;
};
export type NextMoveContext = { topics: NextMoveTopic[]; events: CalendarEvent[]; pastEvents: CalendarEvent[]; coverageAvailable: boolean; complete: boolean };
export type NextMoveResult = { primary: TeacherNextMove | null; alternatives: TeacherNextMove[]; candidates: TeacherNextMove[]; postponedCount: number };

function dismissalKey(teacherId: string, now: Date) { return `classio:best-next-move:dismissed:${teacherId}:${dateKey(now)}`; }
export async function loadDismissedNextMoves(teacherId: string, now = new Date()): Promise<string[]> {
  if (!teacherId) return [];
  try { const value = JSON.parse(await AsyncStorage.getItem(dismissalKey(teacherId, now)) || '[]'); return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []; }
  catch { return []; }
}
export async function dismissNextMove(teacherId: string, id: string, now = new Date()): Promise<string[]> {
  const dismissed = [...new Set([...(await loadDismissedNextMoves(teacherId, now)), id])].slice(-100);
  if (teacherId) await AsyncStorage.setItem(dismissalKey(teacherId, now), JSON.stringify(dismissed));
  return dismissed;
}

function topicRelated(resource: { subject: string; topic: string; title: string; stage: string; level: string }, topic: NextMoveTopic) {
  const resourceSubject = norm(resource.subject);
  if (resourceSubject && norm(topic.subject) && resourceSubject !== norm(topic.subject)) return false;
  if (resource.stage && topic.stage && norm(resource.stage) !== norm(topic.stage)) return false;
  if (resource.level && topic.level && norm(resource.level) !== norm(topic.level)) return false;
  const target = norm(topic.title);
  const candidate = norm(`${resource.topic} ${resource.title}`);
  if (!target || !candidate) return false;
  if (candidate.includes(target) || target.includes(norm(resource.topic)) && norm(resource.topic).length >= 8) return true;
  const words = target.split(' ').filter((word) => word.length > 3);
  const matched = words.filter((word) => candidate.split(' ').includes(word)).length;
  return words.length >= 2 && matched / words.length >= 0.75;
}

export async function loadTeacherNextMoveContext(teacherId: string, now = new Date()): Promise<NextMoveContext> {
  if (!teacherId) return { topics: [], events: [], pastEvents: [], coverageAvailable: false, complete: false };
  const client = requireSupabase();
  const [assignmentResult, calendarResult, libraryResult] = await Promise.allSettled([
    client.from('learning_program_assignments').select('id,program_id,student_user_id,student_name,status,target_completion_on,updated_at').eq('teacher_id', teacherId).neq('status', 'archived').order('updated_at', { ascending: false }).limit(300),
    getCalendarWorkspace(),
    getResourceLibrary('mine'),
  ]);
  const calendar = calendarResult.status === 'fulfilled' ? calendarResult.value : null;
  const allEvents = calendar ? buildCalendarEvents(calendar, dateKey(dayOffset(now, -7)), dateKey(dayOffset(now, 30))) : [];
  const events = allEvents.filter((event) => {
    const at = new Date(`${event.date}T${event.time || '00:00'}:00`).valueOf();
    return at >= now.valueOf();
  });
  const pastEvents = allEvents.filter((event) => event.date < dateKey(now));
  if (assignmentResult.status !== 'fulfilled' || assignmentResult.value.error) return { topics: [], events, pastEvents, coverageAvailable: false, complete: false };
  const assignments = ((assignmentResult.value.data ?? []) as Row[]).filter((row) => text(row.status) !== 'completed');
  const programIds = [...new Set(assignments.map((row) => Number(row.program_id)).filter((id) => Number.isInteger(id) && id > 0))];
  if (!programIds.length) return { topics: [], events, pastEvents, coverageAvailable: libraryResult.status === 'fulfilled' && !libraryResult.value.unavailable.length, complete: Boolean(calendar) };
  const [programsResult, topicsResult, progressResult] = await Promise.all([
    client.from('learning_programs').select('id,subject,custom_subject_name,learner_stage,level_or_band,status').in('id', programIds).neq('status', 'archived').limit(300),
    client.from('learning_program_topics').select('id,program_id,unit_number,topic_number,title,lesson_focus').in('program_id', programIds).order('unit_number').order('topic_number').limit(2000),
    client.from('learning_program_progress').select('assignment_id,topic_id,teacher_done').in('assignment_id', assignments.map((row) => Number(row.id))).limit(3000),
  ]);
  if (programsResult.error || topicsResult.error || progressResult.error) return { topics: [], events, pastEvents, coverageAvailable: false, complete: false };
  const programs = new Map(((programsResult.data ?? []) as Row[]).map((row) => [text(row.id), row]));
  const topicRows = (topicsResult.data ?? []) as Row[];
  const completed = new Set(((progressResult.data ?? []) as Row[]).filter((row) => row.teacher_done === true).map((row) => `${text(row.assignment_id)}:${text(row.topic_id)}`));
  const library = libraryResult.status === 'fulfilled' ? libraryResult.value : null;
  const cappedKind = library && ['plan', 'worksheet', 'exam', 'video'].some((kind) => library.resources.filter((resource) => resource.kind === kind).length >= 1000);
  const completeCoverage = Boolean(library && !library.unavailable.length && !cappedKind && topicRows.length < 2000 && assignments.length < 300);
  const resources = library?.resources.filter((row) => row.kind !== 'program') ?? [];
  const topics: NextMoveTopic[] = [];
  for (const assignment of assignments) {
    const program = programs.get(text(assignment.program_id));
    if (!program) continue;
    const next = topicRows.find((row) => text(row.program_id) === text(assignment.program_id) && !completed.has(`${text(assignment.id)}:${text(row.id)}`));
    if (!next) continue;
    const candidate: NextMoveTopic = {
      assignmentId: text(assignment.id), topicId: text(next.id), programId: text(assignment.program_id), studentId: text(assignment.student_user_id), student: text(assignment.student_name),
      title: text(next.title || next.lesson_focus), subject: canonicalSubjectLabel(text(program.custom_subject_name || program.subject)), stage: text(program.learner_stage), level: text(program.level_or_band), targetDate: text(assignment.target_completion_on).slice(0, 10), material: 'unknown', practiceAvailable: false, planAvailable: false,
    };
    if (!candidate.title) continue;
    const related = resources.filter((row) => topicRelated(row, candidate));
    candidate.material = related.length ? 'related' : completeCoverage ? 'no_clear_match' : 'unknown';
    candidate.practiceAvailable = related.some((row) => row.kind === 'worksheet' || row.kind === 'exam');
    candidate.planAvailable = related.some((row) => row.kind === 'plan');
    topics.push(candidate);
  }
  return { topics, events, pastEvents, coverageAvailable: completeCoverage, complete: Boolean(calendar && library && !library.unavailable.length && !cappedKind && topicRows.length < 2000 && assignments.length < 300) };
}

export function buildTeacherNextMoves(input: { data: TeacherDataset; packages: PackageInsight[]; inactiveStudents: string[]; context: NextMoveContext; now?: Date; dismissed?: string[] }): NextMoveResult {
  const { data, packages, context } = input;
  const now = input.now ?? new Date();
  const inactive = new Set(input.inactiveStudents.map(norm));
  const dismissed = new Set(input.dismissed ?? []);
  const studentsById = new Map(data.students.map((row) => [text(row.linked_student_user_id), text(row.student)]));
  const activeStudent = (name: string) => Boolean(name) && !inactive.has(norm(name));
  const actions: TeacherNextMove[] = [];
  const add = (action: TeacherNextMove) => { actions.push(action); };
  for (const review of data.reviewRequests.filter((row) => text(row.status) === 'requested')) {
    const studentId = text(review.student_id); const student = studentsById.get(studentId) || '';
    if (!activeStudent(student)) continue;
    add({ id: `review:${text(review.id)}`, kind: 'review', priority: 10, icon: '📋', titleKey: 'bestMove.reviewTitle', reasonKey: 'bestMove.reviewReason', actionKey: 'bestMove.reviewAction', params: { student }, href: { pathname: '/students', params: { section: 'progress', learningTab: 'reviews', student: studentId } }, dueAt: toTime(review.requested_at) });
  }
  for (const request of data.practiceRequests) {
    const studentId = text(request.student_id); const student = studentsById.get(studentId) || text(request.student_name);
    if (!activeStudent(student) || !studentId) continue;
    add({ id: `practice:${text(request.id)}`, kind: 'practice', priority: 20, icon: '🧩', titleKey: 'bestMove.practiceTitle', reasonKey: 'bestMove.practiceReason', actionKey: 'bestMove.practiceAction', params: { student }, href: { pathname: '/students', params: { section: 'progress', learningTab: 'programs', student: studentId } }, dueAt: toTime(request.updated_at) });
  }
  for (const pkg of packages.filter((row) => activeStudent(row.student) && row.status !== 'active')) {
    const overused = pkg.status === 'overused';
    add({ id: `package:${norm(pkg.student)}:${pkg.paymentDate}`, kind: overused ? 'overused' : 'renewal', priority: overused ? 25 : pkg.status === 'due_now' ? 40 : 75, icon: overused ? '⚠️' : '💳', titleKey: overused ? 'bestMove.overusedTitle' : 'bestMove.renewalTitle', reasonKey: overused ? 'bestMove.overusedReason' : 'bestMove.renewalReason', actionKey: 'bestMove.packageAction', params: { student: pkg.student, units: Math.abs(pkg.remaining) }, href: { pathname: '/students', params: { section: 'profile', student: text(data.students.find((row) => norm(row.student) === norm(pkg.student))?.id || pkg.student) } }, dueAt: toTime(pkg.estimatedFinishDate) });
  }
  const earliestUnrecorded = dateKey(dayOffset(now, -3));
  for (const event of context.pastEvents.filter((row) => row.date >= earliestUnrecorded)) {
    if (!activeStudent(event.student) || data.lessons.some((lesson) => norm(lesson.student) === norm(event.student) && text(lesson.lesson_date).slice(0, 10) === event.date)) continue;
    add({ id: `record:${event.key}`, kind: 'record_lesson', priority: 35, icon: '📝', titleKey: 'bestMove.recordTitle', reasonKey: 'bestMove.recordReason', actionKey: 'bestMove.recordAction', params: { student: event.student, date: event.date }, href: { pathname: '/lessons', params: { action: 'new', student: event.student, date: event.date } }, dueAt: new Date(`${event.date}T${event.time || '00:00'}:00`).valueOf() });
  }
  const firstLesson = context.events.find((event) => activeStudent(event.student));
  const firstLessonAt = firstLesson ? new Date(`${firstLesson.date}T${firstLesson.time || '00:00'}:00`).valueOf() : 0;
  const hoursUntilLesson = firstLessonAt ? (firstLessonAt - now.valueOf()) / 3600000 : Infinity;
  const orderedTopics = [...context.topics].filter((row) => activeStudent(row.student)).sort((a, b) => {
    const aLesson = context.events.find((event) => norm(event.student) === norm(a.student));
    const bLesson = context.events.find((event) => norm(event.student) === norm(b.student));
    return text(aLesson?.date).localeCompare(text(bLesson?.date)) || text(aLesson?.time).localeCompare(text(bLesson?.time)) || a.student.localeCompare(b.student);
  });
  for (const topic of orderedTopics.slice(0, 8)) {
    const lesson = context.events.find((event) => norm(event.student) === norm(topic.student));
    const lessonAt = lesson ? new Date(`${lesson.date}T${lesson.time || '00:00'}:00`).valueOf() : 0;
    const hoursAway = lessonAt ? (lessonAt - now.valueOf()) / 3600000 : Infinity;
    if (topic.material === 'no_clear_match' && lesson && hoursAway <= 168) {
      add({ id: `material:${topic.assignmentId}:${topic.topicId}`, kind: 'material_gap', priority: hoursAway <= 24 ? 15 : hoursAway <= 48 ? 30 : 55, icon: '✨', titleKey: 'bestMove.materialTitle', reasonKey: 'bestMove.materialReason', actionKey: 'bestMove.materialAction', params: { student: topic.student, topic: topic.title }, href: { pathname: '/smart-tools', params: { tool: 'plan', programId: topic.programId, programTopicId: topic.topicId, student: topic.student } }, dueAt: lessonAt });
    } else if (topic.material === 'related' && topic.planAvailable && !topic.practiceAvailable && lesson && hoursAway <= 168) {
      add({ id: `practice-gap:${topic.assignmentId}:${topic.topicId}`, kind: 'practice_gap', priority: hoursAway <= 48 ? 48 : 68, icon: '✏️', titleKey: 'bestMove.practiceGapTitle', reasonKey: 'bestMove.practiceGapReason', actionKey: 'bestMove.practiceGapAction', params: { student: topic.student, topic: topic.title }, href: { pathname: '/smart-tools', params: { tool: 'worksheet', programId: topic.programId, programTopicId: topic.topicId, student: topic.student } }, dueAt: lessonAt });
    } else if (topic.material === 'related' && lesson && hoursAway <= 48) {
      add({ id: `prepare:${topic.assignmentId}:${topic.topicId}`, kind: 'prepare_lesson', priority: 50, icon: '📚', titleKey: 'bestMove.prepareTitle', reasonKey: 'bestMove.prepareReason', actionKey: 'bestMove.prepareAction', params: { student: topic.student, topic: topic.title }, href: { pathname: '/students', params: { section: 'progress', learningTab: 'programs', student: topic.studentId } }, dueAt: lessonAt });
    }
    const alreadyAssigned = data.assignments.some((row) => text(row.student_id) === topic.studentId && text(row.learning_program_topic_id) === topic.topicId && text(row.status) !== 'archived');
    if (topic.practiceAvailable && !alreadyAssigned && lesson && hoursAway <= 168) {
      add({ id: `assign:${topic.assignmentId}:${topic.topicId}`, kind: 'assign_practice', priority: 70, icon: '✏️', titleKey: 'bestMove.assignTitle', reasonKey: 'bestMove.assignReason', actionKey: 'bestMove.assignAction', params: { student: topic.student, topic: topic.title }, href: { pathname: '/students', params: { section: 'progress', learningTab: 'recommendations', student: topic.studentId } }, dueAt: lessonAt });
    }
  }
  if (firstLesson && hoursUntilLesson <= 24 && hoursUntilLesson >= 1) {
    add({ id: `confirm:${firstLesson.key}`, kind: 'confirm_lesson', priority: 65, icon: '🗓️', titleKey: 'bestMove.confirmTitle', reasonKey: 'bestMove.confirmReason', actionKey: 'bestMove.confirmAction', params: { student: firstLesson.student, time: firstLesson.time }, href: '/calendar', dueAt: firstLessonAt });
  }
  if (!actions.length && context.topics.length && !context.events.length) {
    const topic = orderedTopics[0];
    if (topic) add({ id: `program:${topic.assignmentId}:${topic.topicId}`, kind: 'plan_program', priority: 90, icon: '📚', titleKey: 'bestMove.programTitle', reasonKey: 'bestMove.programReason', actionKey: 'bestMove.programAction', params: { topic: topic.title }, href: { pathname: '/students', params: { section: 'progress', learningTab: 'programs', student: topic.studentId } } });
  }
  const allUnique = [...new Map(actions.map((action) => [action.id, action])).values()];
  const unique = allUnique.filter((action) => !dismissed.has(action.id)).sort((a, b) => a.priority - b.priority || (a.dueAt || Infinity) - (b.dueAt || Infinity) || a.id.localeCompare(b.id));
  const primary = unique[0] ?? null;
  const seen = new Set(primary ? [primary.kind] : []);
  const alternatives = unique.filter((action) => {
    if (action.id === primary?.id || seen.has(action.kind)) return false;
    seen.add(action.kind);
    return true;
  }).slice(0, 2);
  return { primary, alternatives, candidates: unique, postponedCount: allUnique.length - unique.length };
}
