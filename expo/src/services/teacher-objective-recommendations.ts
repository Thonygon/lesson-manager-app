import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { programTopics } from '@/lib/learning-program-topics';
import { requireSupabase } from '@/lib/supabase';
import type { ClassioRecord } from '@/services/classio-data';
import type { StudentLearningWorkspace } from '@/services/teacher-students';

export type TeacherObjectiveRecommendation = {
  id: string; subject: string; topic: string; title: string; objective: string;
  priority: 'high' | 'medium' | 'next'; bucket: 'next_topic' | 'review' | 'pending_gap' | 'assignment';
  focus: 'needs_practice' | 'reteach' | 'reinforce' | 'stretch'; score: number;
  recentScore: number | null; attempts: number; programTitle: string; progressPercent: number | null;
  topicId?: number; programId?: number; programAssignmentId?: number; resolvedLowScoreSignature?: string; stage: string; level: string; lessonFocus: string; tool: 'plan' | 'worksheet' | 'exam';
};

type Signal = { score_gap: number; retry_pressure: number; status_pressure: number; recent_score: number | null; active_assignments: number; attempts: number };
type EventSummary = { count: number; assigned: number; started: number; completed: number; improved: number; last: string };
const BASE: Record<string, number> = {
  bias: -0.18, bucket_next_topic: 0.16, bucket_review: 0.24, bucket_pending_gap: 0.18,
  progress_gap: 0.34, overall_score_gap: 0.24, overall_retry_pressure: 0.18, overall_status_pressure: 0.26,
  topic_score_gap: 0.42, topic_retry_pressure: 0.28, topic_status_pressure: 0.26, needs_practice: 0.52,
  teacher_done: -0.22, student_done: 0.18, is_after_latest_completed: 0.22, is_before_latest_completed: 0.34,
  is_next_unfinished: 0.46, has_recent_low_score: 0.22, historical_event_density: 0.18,
  historical_assignment_rate: 0.28, historical_improvement_rate: 0.42,
};
const statusPressure: Record<string, number> = { overdue: 1, assigned: 0.9, started: 0.82, submitted: 0.7, graded: 0.28, completed: 0.2, cancelled: 0.05 };
const clamp = (value: number) => Math.max(0, Math.min(1, value));
const sigmoid = (value: number) => 1 / (1 + Math.exp(-Math.max(-30, Math.min(30, value))));
const tokens = (value: unknown) => new Set(String(value || '').toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').split(/[^\p{L}\p{N}]+/u).filter((part) => part.length >= 3));
const numericScore = (value: unknown) => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);

function signal(rows: ClassioRecord[], attemptsByAssignment: Map<string, ClassioRecord[]>, resolved: Set<string>): Signal {
  if (!rows.length) return { score_gap: 0.2, retry_pressure: 0.1, status_pressure: 0.25, recent_score: null, active_assignments: 0, attempts: 0 };
  const values = rows.map((row) => {
    const attempts = attemptsByAssignment.get(String(row.id)) || [];
    const latest = attempts[0];
    const score = numericScore(latest?.score_pct ?? row.score_pct);
    const timestamp = String(latest?.graded_at || latest?.created_at || row.graded_at || row.submitted_at || row.updated_at || row.created_at || '');
    const recent = Boolean(timestamp && Date.parse(timestamp) >= Date.now() - 30 * 86400000);
    const signature = latest?.id ? `assignment_attempt:${row.id}:${latest.id}` : '';
    const actionableScore = recent && (!signature || !resolved.has(signature)) ? score : null;
    const pressure = statusPressure[String(row.status || '').toLowerCase()] ?? 0.25;
    return { score, actionableScore, pressure, attempts: attempts.length };
  });
  return {
    score_gap: Math.max(...values.map((row) => row.actionableScore !== null ? clamp((82 - row.actionableScore) / 42) : row.score === null ? 0.35 : 0)),
    retry_pressure: Math.max(...values.map((row) => clamp((Math.max(row.attempts, 1) - 1) / 3))),
    status_pressure: Math.max(...values.map((row) => row.pressure)),
    recent_score: values.map((row) => row.actionableScore).filter((value): value is number => value !== null).reduce<number | null>((min, value) => min === null ? value : Math.min(min, value), null),
    active_assignments: values.filter((row) => row.pressure >= 0.7).length,
    attempts: Math.max(...values.map((row) => row.attempts)),
  };
}

function eventSummaries(rows: ClassioRecord[]) {
  const summaries = new Map<string, EventSummary>();
  const resolved = new Set<string>();
  rows.forEach((row) => {
    const metadata = row.metadata && typeof row.metadata === 'object' && !Array.isArray(row.metadata) ? row.metadata as ClassioRecord : {};
    if (String(row.event_type) === 'teacher_marked_done' && metadata.resolved_low_score_signature) resolved.add(String(metadata.resolved_low_score_signature));
    const key = `${row.learning_program_assignment_id}:${row.learning_program_topic_id}:${row.recommendation_bucket}`;
    const item = summaries.get(key) || { count: 0, assigned: 0, started: 0, completed: 0, improved: 0, last: '' };
    item.count += 1;
    const type = String(row.event_type || '');
    if (type === 'assignment_created') item.assigned += 1;
    if (type === 'student_started') item.started += 1;
    if (type === 'student_completed' || type === 'teacher_marked_done') item.completed += 1;
    if (type === 'student_improved') item.improved += 1;
    if (!item.last) item.last = type;
    summaries.set(key, item);
  });
  return { summaries, resolved };
}

function features(bucket: string, gap: number, overall: Signal, topic: Signal, event: EventSummary | undefined, done: boolean, requested: boolean, after: boolean, before: boolean, next: boolean) {
  const count = Math.max(1, event?.count || 0);
  return {
    [`bucket_${bucket}`]: 1, progress_gap: gap, overall_score_gap: overall.score_gap,
    overall_retry_pressure: overall.retry_pressure, overall_status_pressure: overall.status_pressure,
    topic_score_gap: topic.score_gap, topic_retry_pressure: topic.retry_pressure, topic_status_pressure: topic.status_pressure,
    needs_practice: Number(requested), teacher_done: Number(done), student_done: Number(requested),
    is_after_latest_completed: Number(after), is_before_latest_completed: Number(before), is_next_unfinished: Number(next),
    has_recent_low_score: Number(topic.recent_score !== null && topic.recent_score < 75),
    historical_event_density: clamp(count / 6), historical_assignment_rate: clamp((event?.assigned || 0) / count),
    historical_improvement_rate: clamp((event?.improved || 0) / count),
  };
}

function fittedWeights(samples: { features: Record<string, number>; target: number }[]) {
  // The same regularized logistic objective used by the Python recommendation model.
  if (samples.length < 6) return BASE;
  const weights = { ...BASE };
  for (let step = 0; step < 140; step += 1) {
    const gradient: Record<string, number> = {};
    samples.forEach((sample) => {
      const values = { bias: 1, ...sample.features };
      const prediction = sigmoid(Object.entries(values).reduce((sum, [name, value]) => sum + (weights[name] || 0) * value, 0));
      Object.entries(values).forEach(([name, value]) => { gradient[name] = (gradient[name] || 0) + (prediction - sample.target) * value; });
    });
    Object.keys(weights).forEach((name) => { weights[name] -= 0.16 * ((gradient[name] || 0) / samples.length + (name === 'bias' ? 0 : 0.01 * weights[name])); });
  }
  return weights;
}

function collectObjectiveCandidates(workspace: StudentLearningWorkspace, allPrograms = false) {
  const assignments = workspace.assignments.filter((row) => !['archived', 'cancelled'].includes(String(row.status)) && String(row.assignment_type) !== 'lesson_plan_topic');
  const attemptsByAssignment = new Map<string, ClassioRecord[]>();
  workspace.attempts.forEach((row) => { const key = String(row.assignment_id); attemptsByAssignment.set(key, [...(attemptsByAssignment.get(key) || []), row]); });
  const bySubject = new Map<string, ClassioRecord[]>();
  assignments.forEach((row) => { const key = canonicalSubjectKey(row.subject_key || row.subject_label); bySubject.set(key, [...(bySubject.get(key) || []), row]); });
  const { summaries: events, resolved } = eventSummaries(workspace.recommendationEvents);
  const overall = signal(assignments, attemptsByAssignment, resolved);
  const candidates: { item: TeacherObjectiveRecommendation; heuristic: number; features: Record<string, number>; target: number }[] = [];
  const currentPrograms = new Map<string, ClassioRecord>();
  workspace.programs.filter((row) => String(row.status) !== 'archived').forEach((row) => {
    const program = (row.program || {}) as ClassioRecord;
    const subjectKey = canonicalSubjectKey(program.custom_subject_name || program.subject);
    const prior = currentPrograms.get(subjectKey);
    const order = (item: ClassioRecord) => { const data = (item.program || {}) as ClassioRecord; return `${String(data.sequence_order || item.sequence_order || 0).padStart(8, '0')}:${String(item.updated_at || item.assigned_at || data.updated_at || data.created_at || '')}`; };
    if (!prior || order(row) > order(prior)) currentPrograms.set(subjectKey, row);
  });
  (allPrograms ? workspace.programs.filter((row) => String(row.status) !== 'archived') : [...currentPrograms.values()]).forEach((assignment) => {
    const program = (assignment.program || {}) as ClassioRecord;
    const subjectKey = canonicalSubjectKey(program.custom_subject_name || program.subject);
    const subject = canonicalSubjectLabel(program.custom_subject_name || program.subject);
    const rows = bySubject.get(subjectKey) || [];
    const programSignal = rows.length ? signal(rows, attemptsByAssignment, resolved) : overall;
    const topics = programTopics(program, workspace.topics.filter((row) => String(row.program_id) === String(assignment.program_id)));
    if (!topics.length) return;
    const progress = new Map(workspace.progress.filter((row) => String(row.assignment_id) === String(assignment.id)).map((row) => [String(row.topic_id), row]));
    const latestDone = topics.reduce((last, topic, index) => progress.get(String(topic.id))?.teacher_done ? index : last, -1);
    const doneCount = topics.filter((topic) => progress.get(String(topic.id))?.teacher_done).length;
    const gap = clamp(1 - doneCount / topics.length);
    let nextTaken = false; let pendingTaken = false;
    const candidateStart = candidates.length;
    topics.forEach((topic, index) => {
      const state = progress.get(String(topic.id)); const done = Boolean(state?.teacher_done); const requested = done && Boolean(state?.student_done);
      const query = tokens([topic.title, topic.lesson_focus, topic.student_summary].filter(Boolean).join(' '));
      const topicRows = rows.filter((row) => { const rowTitle = String(row.topic || row.title || '').toLocaleLowerCase(); const title = String(topic.title || '').toLocaleLowerCase(); const other = tokens(rowTitle); return Boolean(title && rowTitle === title) || [...query].filter((token) => other.has(token)).length >= 2; });
      const topicSignal = signal(topicRows, attemptsByAssignment, resolved);
      const lowScoreRow = topicSignal.recent_score === null ? undefined : topicRows.find((row) => numericScore((attemptsByAssignment.get(String(row.id)) || [])[0]?.score_pct ?? row.score_pct) === topicSignal.recent_score);
      const lowScoreAttempt = lowScoreRow ? (attemptsByAssignment.get(String(lowScoreRow.id)) || [])[0] : undefined;
      const bucket = done ? 'review' : index < latestDone ? 'pending_gap' : 'next_topic';
      if (bucket === 'next_topic' && nextTaken && !allPrograms) return;
      if (bucket === 'pending_gap' && pendingTaken && !allPrograms) return;
      if (bucket === 'next_topic') nextTaken = true;
      if (bucket === 'pending_gap') pendingTaken = true;
      if (bucket === 'review' && !requested && topicSignal.score_gap < 0.18 && topicSignal.retry_pressure < 0.34 && !allPrograms) return;
      const event = events.get(`${assignment.id}:${topic.id}:${bucket}`);
      if (bucket === 'review' && event?.improved && !requested && topicSignal.recent_score === null && !allPrograms) return;
      const context = features(bucket, gap, programSignal, topicSignal, event, done, requested, index > latestDone, index < latestDone, bucket === 'next_topic');
      const target = event?.improved ? 1 : event?.completed ? 0.9 : event?.started ? 0.78 : event?.assigned ? 0.64 : event?.count ? 0.28 : 0.18;
      let heuristic = bucket === 'review' ? Math.max(requested ? 0.98 : 0, topicSignal.recent_score === null ? 0 : 0.74 + clamp((78 - topicSignal.recent_score) / 45), 0.58 + 0.24 * topicSignal.score_gap + 0.12 * topicSignal.retry_pressure + 0.06 * topicSignal.status_pressure) : bucket === 'pending_gap' ? 0.68 + 0.18 * gap + 0.14 * programSignal.status_pressure : 0.62 + 0.18 * gap + 0.12 * programSignal.status_pressure + 0.08 * topicSignal.retry_pressure;
      if (event && ['teacher_marked_done', 'assignment_created'].includes(event.last)) heuristic -= bucket === 'review' ? 0.12 : 0.16;
      if (bucket === 'review' && event?.improved && !requested) heuristic -= 0.34;
      const focus = requested ? 'needs_practice' : bucket === 'review' ? 'reteach' : bucket === 'next_topic' && programSignal.score_gap < 0.26 ? 'stretch' : 'reinforce';
      candidates.push({ item: {
        id: `program-${assignment.id}-${topic.id}-${bucket}`, subject, topic: String(topic.title || program.title || ''), title: String(topic.title || program.title || ''),
        objective: String(topic.student_summary || topic.lesson_focus || ''), priority: requested || bucket === 'review' ? 'high' : bucket === 'next_topic' ? 'next' : 'medium', bucket,
        focus, score: 0, recentScore: topicSignal.recent_score, attempts: topicSignal.attempts, programTitle: String(program.title || ''), progressPercent: Math.round(100 * doneCount / topics.length),
        topicId: Number(topic.id) || undefined, programId: Number(assignment.program_id) || undefined, programAssignmentId: Number(assignment.id) || undefined, resolvedLowScoreSignature: lowScoreAttempt?.id ? `assignment_attempt:${lowScoreRow?.id}:${lowScoreAttempt.id}` : undefined, stage: String(program.learner_stage || ''), level: String(program.level_or_band || ''), lessonFocus: String(topic.lesson_focus || ''), tool: bucket === 'next_topic' ? 'plan' : 'worksheet',
      }, heuristic, features: context, target });
    });
    // Streamlit recommends only the strongest review objective for each current program.
    const reviewCandidates = candidates.slice(candidateStart).filter((candidate) => candidate.item.bucket === 'review').sort((a, b) => b.heuristic - a.heuristic);
    if (reviewCandidates.length > 1 && !allPrograms) {
      const winner = reviewCandidates[0];
      for (let index = candidates.length - 1; index >= candidateStart; index -= 1) if (candidates[index].item.bucket === 'review' && candidates[index] !== winner) candidates.splice(index, 1);
    }
  });
  return { candidates, assignments, attemptsByAssignment, resolved };
}

export function buildTeacherObjectiveSamples(workspace: StudentLearningWorkspace) {
  return collectObjectiveCandidates(workspace, true).candidates.map(({ features: row, target }) => ({ features: row, target }));
}

export function buildTeacherObjectiveRecommendations(workspace: StudentLearningWorkspace, trainedWeights?: Record<string, number>): TeacherObjectiveRecommendation[] {
  const { candidates, assignments, attemptsByAssignment, resolved } = collectObjectiveCandidates(workspace);
  const weights = trainedWeights || fittedWeights(candidates.map(({ features: row, target }) => ({ features: row, target })));
  const ranked = candidates.map(({ item, heuristic, features: row }) => ({ ...item, score: 0.58 * heuristic + 0.42 * sigmoid(Object.entries({ bias: 1, ...row }).reduce((sum, [name, value]) => sum + (weights[name] || 0) * value, 0)) }));
  if (!ranked.length) assignments.forEach((row) => {
    const current = signal([row], attemptsByAssignment, resolved);
    const score = 0.65 * current.score_gap + 0.35 * current.status_pressure;
    ranked.push({ id: `assignment-${row.id}`, subject: canonicalSubjectLabel(row.subject_label || row.subject_key), topic: String(row.topic || row.title || ''), title: String(row.topic || row.title || ''), objective: String(row.title || ''), priority: score >= 0.6 ? 'high' : 'medium', bucket: 'assignment', focus: current.score_gap >= 0.35 ? 'reteach' : 'reinforce', score, recentScore: current.recent_score, attempts: current.attempts, programTitle: '', progressPercent: null, stage: '', level: '', lessonFocus: '', tool: 'worksheet' });
  });
  const seen = new Set<string>();
  return ranked.sort((a, b) => b.score - a.score).filter((item) => { const key = `${canonicalSubjectKey(item.subject)}:${item.title.toLocaleLowerCase()}`; if (seen.has(key)) return false; seen.add(key); return true; }).slice(0, 3);
}

const objectiveModelCache = new Map<string, { expires: number; promise: Promise<Record<string, number>> }>();

export async function loadTeacherObjectiveModel(): Promise<Record<string, number>> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser(); const teacherId = auth.user?.id;
  if (authError || !teacherId) throw authError ?? new Error('Your session has expired.');
  const cached = objectiveModelCache.get(teacherId);
  if (cached && cached.expires > Date.now()) return cached.promise;
  const promise = (async () => {
    const cutoff = new Date(Date.now() - 180 * 86400000).toISOString();
    const programResult = await client.from('learning_program_assignments').select('id,program_id,student_user_id,roster_student_id,status,assigned_at,updated_at').eq('teacher_id', teacherId).neq('status', 'archived').order('updated_at', { ascending: false }).limit(240);
    if (programResult.error) throw programResult.error;
    const programAssignments = (programResult.data ?? []) as ClassioRecord[];
    if (!programAssignments.length) return BASE;
    const [assignmentResult, attemptResult, eventResult] = await Promise.all([
      client.from('teacher_assignments').select('id,student_id,title,topic,subject_key,subject_label,assignment_type,status,score_pct,created_at,updated_at,submitted_at,graded_at').eq('teacher_id', teacherId).neq('status', 'archived').order('created_at', { ascending: false }).limit(1200),
      client.from('teacher_assignment_attempts').select('id,assignment_id,score_pct,created_at,graded_at').eq('teacher_id', teacherId).order('created_at', { ascending: false }).limit(1200),
      client.from('learning_program_recommendation_events').select('student_id,learning_program_assignment_id,learning_program_topic_id,recommendation_bucket,event_type,metadata,created_at').eq('teacher_id', teacherId).gte('created_at', cutoff).order('created_at', { ascending: false }).limit(1500),
    ]);
    if (assignmentResult.error || attemptResult.error || eventResult.error) throw assignmentResult.error ?? attemptResult.error ?? eventResult.error;
    const programIds = [...new Set(programAssignments.map((row) => Number(row.program_id)).filter((id) => id > 0))];
    const assignmentIds = programAssignments.map((row) => Number(row.id)).filter((id) => id > 0);
    if (!programIds.length || !assignmentIds.length) return BASE;
    const [programs, topics, progress] = await Promise.all([
      client.from('learning_programs').select('id,title,subject,custom_subject_name,learner_stage,level_or_band,sequence_order,updated_at,created_at').in('id', programIds),
      client.from('learning_program_topics').select('id,program_id,unit_id,unit_number,topic_number,title,lesson_focus,student_summary,unit:learning_program_units!learning_program_topics_unit_id_fkey(id,program_id,unit_number)').in('program_id', programIds).order('unit_number').order('topic_number'),
      client.from('learning_program_progress').select('assignment_id,topic_id,teacher_done,student_done').in('assignment_id', assignmentIds),
    ]);
    if (programs.error || topics.error || progress.error) throw programs.error ?? topics.error ?? progress.error;
    const programMap = new Map(((programs.data ?? []) as ClassioRecord[]).map((row) => [String(row.id), row]));
    const assignments = (assignmentResult.data ?? []) as ClassioRecord[];
    const attempts = (attemptResult.data ?? []) as ClassioRecord[];
    const allEvents = (eventResult.data ?? []) as ClassioRecord[];
    const allProgress = (progress.data ?? []) as ClassioRecord[];
    const allTopics = (topics.data ?? []) as ClassioRecord[];
    const samples = programAssignments.flatMap((row) => {
      const studentId = String(row.student_user_id || (row.roster_student_id ? `roster:${row.roster_student_id}` : ''));
      if (!studentId) return [];
      const workspace: StudentLearningWorkspace = {
        assignments: assignments.filter((item) => String(item.student_id) === studentId),
        attempts, reviews: [],
        programs: [{ ...row, program: programMap.get(String(row.program_id)) || {} }],
        progress: allProgress.filter((item) => String(item.assignment_id) === String(row.id)),
        topics: allTopics.filter((item) => String(item.program_id) === String(row.program_id)),
        recommendationEvents: allEvents.filter((item) => String(item.student_id) === studentId),
      };
      return buildTeacherObjectiveSamples(workspace);
    });
    return fittedWeights(samples);
  })().catch((reason) => { objectiveModelCache.delete(teacherId); throw reason; });
  objectiveModelCache.set(teacherId, { expires: Date.now() + 600000, promise });
  return promise;
}
