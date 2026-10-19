import { useEffect, useMemo, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { ResourceShowcaseCard } from '@/components/resource-showcase-card';
import { ResourceFilters } from '@/components/resource-filters';
import { Button, EmptyState, LoadingState, Pagination, Panel, TabRail } from '@/components/ui';
import { canonicalSubjectKey, canonicalSubjectLabel } from '@/lib/subjects';
import { useAppPreferences } from '@/providers/app-preferences';
import type { ClassioRecord } from '@/services/classio-data';
import type { PublicResource } from '@/services/public-data';
import { getStudentAssignmentCardImages, getStudentTeacherConnections, getStudentWorkspace, type StudentWorkspace } from '@/services/student-data';
import { colors } from '@/theme';

type Kind = 'worksheet' | 'exam' | 'video';
type Filter = 'all' | 'not_started' | 'in_progress' | 'done';

function assignmentState(row: ClassioRecord, attempts: ClassioRecord[], drafts: ClassioRecord[]): Exclude<Filter, 'all'> {
  const status = String(row.status || 'assigned');
  if (row.assignment_type === 'video') return ['submitted', 'graded', 'completed'].includes(status) || attempts.length > 0 ? 'done' : 'not_started';
  if (['submitted', 'graded', 'completed', 'cancelled'].includes(status)) return 'done';
  if (status === 'started' || drafts.length > 0) return 'in_progress';
  return 'not_started';
}

function assignmentPreview(row: ClassioRecord, kind: Kind, imageUrl: string, teacherName: string, fallbackTitle: string, subject: string): PublicResource {
  return {
    id: String(row.id), kind, title: String(row.title || fallbackTitle),
    subject, topic: String(row.topic || ''),
    stage: '', level: '', author: teacherName, description: String(row.topic || ''),
    imageUrl, createdAt: String(row.assigned_at || row.created_at || ''), raw: row,
  };
}

function subjectLabels(value: unknown, t: (key: string) => string): string {
  if (!Array.isArray(value)) return '';
  return [...new Set(value.map((subject) => typeof subject === 'string' ? subject : subject && typeof subject === 'object' ? String((subject as ClassioRecord).subject_label || (subject as ClassioRecord).subject_key || '') : '').filter(Boolean).map((subject) => canonicalSubjectLabel(subject, t)))].join(', ');
}

export default function StudentAssignmentsScreen() {
  const { t } = useAppPreferences();
  const params = useLocalSearchParams<{ kind?: string; query?: string }>();
  const initialKind: Kind = params.kind === 'exam' || params.kind === 'video' ? params.kind : 'worksheet';
  const [workspace, setWorkspace] = useState<StudentWorkspace | null>(null);
  const [connections, setConnections] = useState<ClassioRecord[]>([]);
  const [kind, setKind] = useState<Kind>(initialKind);
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState(typeof params.query === 'string' ? params.query : '');
  const [scope, setScope] = useState('');
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState('');
  const [cardImages, setCardImages] = useState<Record<string, string>>({});
  const requestedPreviews = useRef(new Set<string>());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    void getStudentWorkspace('assignments').then((value) => { if (active) setWorkspace(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : t('student.loadFailed')); })
      .finally(() => { if (active) setLoading(false); });
    void getStudentTeacherConnections().then((value) => { if (active) setConnections(value); })
      .catch((reason) => console.warn('Student teacher connections unavailable on assignments', reason));
    return () => { active = false; };
  }, [t]);

  const rows = useMemo(() => workspace?.assignments ?? [], [workspace]);
  const attemptsByAssignment = useMemo(() => {
    const grouped = new Map<string, ClassioRecord[]>();
    for (const attempt of workspace?.attempts ?? []) {
      const id = String(attempt.assignment_id || '');
      grouped.set(id, [...(grouped.get(id) ?? []), attempt]);
    }
    return grouped;
  }, [workspace]);
  const draftsByAssignment = useMemo(() => {
    const grouped = new Map<string, ClassioRecord[]>();
    for (const row of rows) {
      const sourceIds = new Set([String(row.id), String(row.source_record_id || '')]);
      grouped.set(String(row.id), (workspace?.sessions ?? []).filter((session) => String(session.source_type) === String(row.assignment_type) && sourceIds.has(String(session.source_id))));
    }
    return grouped;
  }, [rows, workspace?.sessions]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return rows.filter((row) => String(row.assignment_type) === kind
      && (filter === 'all' || assignmentState(row, attemptsByAssignment.get(String(row.id)) ?? [], draftsByAssignment.get(String(row.id)) ?? []) === filter)
      && (!needle || [row.title, row.topic, row.subject_label, row.subject_key, row.teacher_note].join(' ').toLocaleLowerCase().includes(needle)));
  }, [attemptsByAssignment, draftsByAssignment, filter, kind, query, rows]);
  const groups = useMemo(() => {
    const grouped = new Map<string, { key: string; subject: string; teacher: string; rows: ClassioRecord[] }>();
    for (const row of filtered) {
      const subject = canonicalSubjectLabel(row.subject_label || row.subject_key || t('student.assignment'), t);
      const teacher = String(workspace?.teacherNames?.[String(row.teacher_id)] || '');
      const key = `${canonicalSubjectKey(row.subject_label || row.subject_key)}:${String(row.teacher_id || '')}`;
      const group = grouped.get(key) ?? { key, subject, teacher, rows: [] };
      group.rows.push(row); grouped.set(key, group);
    }
    const subjectCounts = new Map<string, number>();
    for (const group of grouped.values()) subjectCounts.set(group.subject, (subjectCounts.get(group.subject) ?? 0) + 1);
    return [...grouped.values()].map((group) => ({ ...group, label: subjectCounts.get(group.subject)! > 1 && group.teacher ? `${group.subject} · ${group.teacher}` : group.subject }));
  }, [filtered, t, workspace?.teacherNames]);
  const activeGroup = groups.find((group) => group.key === scope) ?? groups[0];
  const visible = useMemo(() => activeGroup?.rows ?? [], [activeGroup]);
  const pages = Math.max(1, Math.ceil(visible.length / 18));
  const currentPage = Math.min(page, pages);
  const shown = useMemo(() => visible.slice((currentPage - 1) * 18, currentPage * 18), [currentPage, visible]);

  useEffect(() => {
    const requested = requestedPreviews.current;
    const missing = shown.filter((row) => !requested.has(String(row.id)));
    if (!missing.length) return;
    missing.forEach((row) => requested.add(String(row.id)));
    let active = true;
    let settled = false;
    void getStudentAssignmentCardImages(missing).then((images) => {
      settled = true;
      if (active) setCardImages((current) => ({ ...current, ...images }));
    }).catch((reason) => {
      settled = true;
      missing.forEach((row) => requested.delete(String(row.id)));
      console.warn('Student assignment card images unavailable', reason);
    });
    return () => { active = false; if (!settled) missing.forEach((row) => requested.delete(String(row.id))); };
  }, [shown]);

  const chooseKind = (value: Kind) => { setKind(value); setScope(''); setQuery(''); setPage(1); setSelectedId(''); };
  const activeConnections = connections.filter((row) => String(row.status) === 'active');
  const pendingConnections = connections.filter((row) => String(row.status) === 'pending');
  return <AppShell title={t('student.assignments')} eyebrow={t('student.learningSpace')}>
    {activeConnections.length || pendingConnections.length ? <Panel style={styles.connections}>
      {activeConnections.length ? <View style={styles.connectionGroup}><Text style={styles.detailHeading}>{t('student.myTeachers')}</Text>{activeConnections.map((row) => <Text key={String(row.id)} style={styles.detailLine}>{String(row.teacher_name || t('student.teacher'))}{subjectLabels(row.active_subjects, t) ? ` · ${subjectLabels(row.active_subjects, t)}` : ''}</Text>)}</View> : null}
      {pendingConnections.length ? <View style={styles.connectionGroup}><Text style={styles.detailHeading}>{t('student.teacherRequestsPending')}</Text>{pendingConnections.map((row) => <Text key={String(row.id)} style={styles.detailLine}>{String(row.teacher_name || t('student.teacher'))}{subjectLabels(row.requested_subjects, t) ? ` · ${subjectLabels(row.requested_subjects, t)}` : ''}</Text>)}</View> : null}
    </Panel> : null}
    <TabRail accessibilityLabel={t('student.assignments')} value={kind} onChange={(value) => chooseKind(value as Kind)} items={[{ value: 'worksheet', label: `📋 ${t('student.worksheets')}` }, { value: 'exam', label: `🧪 ${t('student.exams')}` }, { value: 'video', label: `🎬 ${t('student.videos')}` }]} />
    <ResourceFilters query={query} onQueryChange={(value) => { setQuery(value); setPage(1); setScope(''); setSelectedId(''); }} searchLabel={t('common.search')} searchPlaceholder={t('student.searchAssignments')} count={filtered.length} facets={[{ key: 'status', label: t('students.filterStatus'), value: filter, allValue: 'all', allLabel: t('student.filter.all'), options: (['not_started', 'in_progress', 'done'] as const).map((value) => ({ value, label: t(`student.filter.${value}`) })), onChange: (value) => { setFilter(value as Filter); setPage(1); setScope(''); setSelectedId(''); } }]} />
    {groups.length > 1 ? <TabRail accessibilityLabel={t('student.assignments')} value={activeGroup.key} onChange={(value) => { setScope(value); setPage(1); setSelectedId(''); }} items={groups.map((group) => ({ value: group.key, label: `📚 ${group.label}` }))} /> : null}
    {loading ? <LoadingState /> : error ? <EmptyState title={t('student.loadFailed')} body={error} /> : !shown.length ? <EmptyState title={t('student.noAssignments')} body={t('student.noAssignmentsBody')} /> : <View style={styles.grid}>{shown.map((row) => {
      const id = String(row.id);
      const attempts = attemptsByAssignment.get(id) ?? [];
      const latest = attempts[0];
      const review = (workspace?.reviews ?? []).find((item) => String(item.assignment_id) === id);
      const draft = draftsByAssignment.get(id) ?? [];
      const status = assignmentState(row, attempts, draft);
      const teacher = String(workspace?.teacherNames?.[String(row.teacher_id)] || '');
      const archived = row.source_archived === true || String(row.source_archived) === 'true';
      const reviewSessionId = kind !== 'video' && status === 'done' ? String(attempts.find((attempt) => attempt.practice_session_id)?.practice_session_id || '') : '';
      const openPractice = () => router.push({ pathname: '/student-practice', params: { kind, assignmentId: id, returnTo: 'student-assignments', ...(reviewSessionId ? { reviewSessionId } : {}) } });
      const showDetails = status === 'done' || archived;
      return <View key={id} style={styles.resourceSlot}>
        <ResourceShowcaseCard compact item={assignmentPreview(row, kind, cardImages[id] || '', teacher, t('student.assignment'), canonicalSubjectLabel(row.subject_label || row.subject_key, t))} onPress={() => showDetails ? setSelectedId((current) => current === id ? '' : id) : openPractice()} eyebrow={draft.length ? `${t(`student.filter.${status}`)} · ${t('student.draftSaved')}` : t(`student.filter.${status}`)} description={String(row.topic || t('student.assignment'))} />
        {selectedId === id && showDetails ? <Panel style={styles.details}>
          <Text style={styles.detailHeading}>{t('student.details')}</Text>
          {teacher ? <Text style={styles.detailLine}>{t('student.assignmentTeacher')}: {teacher}</Text> : null}
          <Text style={styles.detailLine}>{t('student.assignmentSubject')}: {canonicalSubjectLabel(row.subject_label || row.subject_key, t)}</Text>
          <Text style={styles.detailLine}>{t('student.assignmentDue')}: {row.due_at ? new Date(String(row.due_at)).toLocaleDateString() : t('student.flexible')}</Text>
          {row.score_pct !== null && row.score_pct !== undefined ? <Text style={styles.detailLine}>{t('student.assignmentScore')}: {String(row.score_pct)}%</Text> : null}
          {latest ? <Text style={styles.attempt}>{t('student.latestAttempt', { number: Number(latest.attempt_number || 1), score: `${Number(latest.score_pct || 0)}%` })}</Text> : null}
          {review ? <Text style={styles.review}>{t(`student.reviewStatus.${String(review.status)}`)}{review.teacher_feedback ? ` · ${String(review.teacher_feedback)}` : ''}</Text> : null}
          {archived ? <Text style={styles.archived}>{t('student.assignmentArchived')}</Text> : <Button onPress={openPractice}>{kind === 'video' ? t('student.watch') : reviewSessionId ? t('student.reviewAnswers') : t('student.openAssignment')}</Button>}
        </Panel> : null}
      </View>;
    })}</View>}
    <Pagination page={currentPage} totalPages={pages} totalItems={visible.length} onPageChange={setPage} />
    {!loading && !error && !rows.length && !connections.length ? <Pressable accessibilityRole="button" accessibilityLabel={t('student.findTeacher')} onPress={() => router.push('/student-find-teacher')} style={({ pressed }) => [styles.findTeacherCard, pressed && styles.findTeacherPressed]}><View style={styles.findTeacherIcon}><Text style={styles.findTeacherEmoji}>🔍</Text></View><View style={styles.findTeacherCopy}><Text style={styles.findTeacherTitle}>{t('student.findTeacher')}</Text><Text style={styles.findTeacherBody}>{t('student.findTeacherBody')}</Text></View><Text style={styles.findTeacherArrow}>↗</Text></Pressable> : null}
  </AppShell>;
}

const styles = StyleSheet.create({
  connections: { gap: 12, marginBottom: 14 }, connectionGroup: { gap: 4 },
  findTeacherCard: { flexDirection: 'row', alignItems: 'center', gap: 13, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.violet, borderRadius: 18, padding: 16, marginTop: 22, overflow: 'hidden' },
  findTeacherPressed: { opacity: 0.76, transform: [{ translateY: -1 }] },
  findTeacherIcon: { width: 46, height: 46, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.violetSoft, borderWidth: 1, borderColor: colors.violet },
  findTeacherEmoji: { fontSize: 21 }, findTeacherCopy: { flex: 1 }, findTeacherTitle: { color: colors.ink, fontSize: 15, fontWeight: '900' }, findTeacherBody: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 3 }, findTeacherArrow: { color: colors.violet, fontSize: 23, fontWeight: '900' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 11 }, resourceSlot: { flexGrow: 1, flexBasis: 320, minWidth: 280, maxWidth: 530, gap: 8 }, details: { gap: 7 }, detailHeading: { color: colors.ink, fontSize: 12, fontWeight: '900' }, detailLine: { color: colors.muted, fontSize: 10, lineHeight: 17 }, attempt: { color: colors.success, fontSize: 10, fontWeight: '900' }, review: { color: colors.violet, fontSize: 10, lineHeight: 15, fontWeight: '700' }, archived: { color: colors.muted, fontSize: 10, fontWeight: '800', textAlign: 'center', padding: 10 },
});
