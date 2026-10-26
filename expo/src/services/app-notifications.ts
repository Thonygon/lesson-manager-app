import type { Href } from 'expo-router';

import { requireSupabase } from '@/lib/supabase';

export type AppNotification = {
  key: string;
  icon: string;
  titleKey: string;
  titleText?: string;
  titleParams?: Record<string, string | number>;
  detail?: string;
  href: Href;
};

type Row = Record<string, unknown>;
const value = (item: unknown) => String(item ?? '');
const recent = (item: unknown, days: number) => {
  const time = Date.parse(value(item));
  return Number.isFinite(time) && time >= Date.now() - days * 86400000;
};

export async function loadAppNotifications(userId: string, role: string): Promise<AppNotification[]> {
  const client = requireSupabase();
  if (role === 'student') {
    const [assignmentResult, reviewResult, attemptResult] = await Promise.all([
      client.from('teacher_assignments').select('id,title,assignment_type,status,score_pct,due_at,assigned_at,created_at,graded_at,updated_at').eq('student_id', userId).neq('status', 'archived').order('created_at', { ascending: false }).limit(200),
      client.from('teacher_review_requests').select('id,assignment_id,practice_session_id,source_type,title,status,teacher_feedback,reviewed_at').eq('student_id', userId).eq('status', 'reviewed').order('reviewed_at', { ascending: false }).limit(50),
      client.from('teacher_assignment_attempts').select('assignment_id,practice_session_id,teacher_feedback,graded_at,created_at').eq('student_id', userId).in('status', ['graded', 'completed']).not('practice_session_id', 'is', null).order('graded_at', { ascending: false, nullsFirst: false }).limit(500),
    ]);
    if (assignmentResult.error || reviewResult.error || attemptResult.error) throw assignmentResult.error ?? reviewResult.error ?? attemptResult.error;
    const assignments = (assignmentResult.data ?? []) as Row[];
    const reviews = ((reviewResult.data ?? []) as Row[]).filter((row) => recent(row.reviewed_at, 14));
    const reviewedAssignments = new Set(reviews.map((row) => value(row.assignment_id)).filter(Boolean));
    const latestAttemptByAssignment = new Map<string, Row>();
    for (const row of (attemptResult.data ?? []) as Row[]) {
      const id = value(row.assignment_id);
      if (id && !latestAttemptByAssignment.has(id)) latestAttemptByAssignment.set(id, row);
    }
    const items: AppNotification[] = [];
    for (const row of assignments) {
      const id = value(row.id);
      const status = value(row.status);
      const due = Date.parse(value(row.due_at));
      const kind = value(row.assignment_type);
      const href: Href = kind === 'lesson_plan_topic'
        ? { pathname: '/student-lesson-topic' as never, params: { assignmentId: id } }
        : { pathname: '/student-practice', params: { assignmentId: id, kind: kind || 'worksheet', returnTo: 'student-assignments' } };
      const detail = value(row.title);
      if (['assigned', 'started', 'overdue'].includes(status) && Number.isFinite(due) && due < Date.now()) {
        items.push({ key: `student:overdue:${id}:${value(row.due_at)}`, icon: '⚠️', titleKey: 'student.notificationOverdue', titleParams: { count: 1 }, detail, href });
      } else if (['assigned', 'started'].includes(status) && Number.isFinite(due) && due <= Date.now() + 2 * 86400000) {
        items.push({ key: `student:due:${id}:${value(row.due_at)}`, icon: '⏰', titleKey: 'student.notificationDue', titleParams: { count: 1 }, detail, href });
      } else if (status === 'assigned' && recent(row.assigned_at || row.created_at, 7)) {
        items.push({ key: `student:new:${id}:${value(row.assigned_at || row.created_at)}`, icon: '🗂️', titleKey: 'student.notificationNew', titleParams: { count: 1 }, detail, href });
      }
      if (status === 'graded' && recent(row.graded_at, 14) && !reviewedAssignments.has(id)) {
        const attempt = latestAttemptByAssignment.get(id);
        const sessionId = value(attempt?.practice_session_id);
        const hasComment = Boolean(value(attempt?.teacher_feedback).trim());
        const notice = hasComment ? 'review' : 'grade';
        items.push({ key: `student:${hasComment ? 'comment' : 'graded'}:${id}:${value(row.graded_at)}`, icon: hasComment ? '💬' : '📊', titleKey: hasComment ? 'student.notificationComment' : 'student.notificationGraded', titleParams: { count: 1 }, detail, href: sessionId ? { pathname: '/student-practice', params: { reviewSessionId: sessionId, assignmentId: id, kind: kind || 'worksheet', notice, returnTo: 'student-assignments' } } : { pathname: '/student-practice', params: { assignmentId: id, kind: kind || 'worksheet', gradeScore: value(row.score_pct), notice, returnTo: 'student-assignments' } } });
      }
    }
    for (const row of reviews) {
      const assignment = assignments.find((item) => value(item.id) === value(row.assignment_id));
      const sessionId = value(row.practice_session_id);
      const assignmentId = value(row.assignment_id);
      if (!sessionId && !assignmentId) continue;
      const kind = value(assignment?.assignment_type || row.source_type) || 'worksheet';
      const reviewHref: Href = sessionId
        ? { pathname: '/student-practice', params: { reviewSessionId: sessionId, reviewId: value(row.id), ...(assignmentId ? { assignmentId } : {}), kind, notice: 'review', returnTo: assignmentId ? 'student-assignments' : 'student-home' } }
        : { pathname: '/student-practice', params: { assignmentId, kind, reviewId: value(row.id), notice: 'review', returnTo: 'student-assignments' } };
      items.push({ key: `student:review:${value(row.id)}:${value(row.reviewed_at)}`, icon: '💬', titleKey: 'student.notificationReview', titleParams: { count: 1 }, detail: value(assignment?.title || row.title), href: reviewHref });
    }
    return items;
  }
  if (role === 'teacher' || role === 'school_admin') {
    const [reviewResult, practiceResult] = await Promise.all([
      client.from('teacher_review_requests').select('id,student_id,assignment_id,status,requested_at').eq('teacher_id', userId).eq('status', 'requested').order('requested_at', { ascending: false }).limit(100),
      client.from('learning_program_progress').select('id,updated_at,program_assignment:learning_program_assignments!inner(student_user_id,teacher_id)').eq('program_assignment.teacher_id', userId).eq('teacher_done', true).eq('student_done', true).order('updated_at', { ascending: false }).limit(100),
    ]);
    if (reviewResult.error || practiceResult.error) throw reviewResult.error ?? practiceResult.error;
    const reviews = ((reviewResult.data ?? []) as Row[]).map((row): AppNotification => ({
      key: `teacher:review:${value(row.id)}:${value(row.requested_at)}`,
      icon: '📋', titleKey: 'dashboard.reviewNotification', titleParams: { count: 1 },
      href: { pathname: '/students', params: { section: 'progress', learningTab: 'reviews', student: value(row.student_id) } },
    }));
    const practice = ((practiceResult.data ?? []) as Row[]).map((row): AppNotification => {
      const assignment = Array.isArray(row.program_assignment) ? row.program_assignment[0] : row.program_assignment;
      const studentId = value((assignment as Row | undefined)?.student_user_id);
      return { key: `teacher:practice:${value(row.id)}:${value(row.updated_at)}`, icon: '🧩', titleKey: 'dashboard.practiceNotification', titleParams: { count: 1 }, href: { pathname: '/students', params: { section: 'progress', learningTab: 'programs', student: studentId } } };
    });
    return [...reviews, ...practice];
  }
  return [];
}
