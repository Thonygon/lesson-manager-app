/* eslint-disable react-hooks/exhaustive-deps */
import { useEffect, useMemo, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { BulkLessonEditor } from '@/components/bulk-lesson-editor';
import { CalendarInput } from '@/components/calendar-input';
import { StudentSearchSelect } from '@/components/student-search-select';
import { ActionFeedback, Button, EditIconButton, EmptyState, Field, LoadingState, Pagination, Panel, SelectField, TabRail } from '@/components/ui';
import { useRecords } from '@/hooks/use-records';
import { isValidRecordDate, isValidUnitCount } from '@/lib/record-input-validation';
import { useAppPreferences } from '@/providers/app-preferences';
import { addLesson, deleteLesson, type ClassioRecord, updateLesson } from '@/services/classio-data';
import { colors } from '@/theme';

const SUBJECTS = ['English', 'Spanish', 'Mathematics', 'Science', 'Music', 'Study Skills', 'Other'];

function dateValue() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
}

function LessonRow({ record, onEdit }: { record: ClassioRecord; onEdit: () => void }) {
  const subject = String(record.subject_custom || record.subject || 'General');
  return <Panel style={styles.lessonRow}><View style={styles.dateBlock}><Text style={styles.dateDay}>{new Date(String(record.lesson_date)).toLocaleDateString(undefined, { day: '2-digit' })}</Text><Text style={styles.dateMonth}>{new Date(String(record.lesson_date)).toLocaleDateString(undefined, { month: 'short' }).toUpperCase()}</Text></View><View style={styles.rowMain}><Text style={styles.student}>{String(record.student || 'Student')}</Text><Text style={styles.meta}>{subject} · {String(record.modality || '—')} · {String(record.number_of_lesson || 1)} unit(s)</Text>{record.note ? <Text style={styles.note}>{String(record.note)}</Text> : null}</View><EditIconButton accessibilityLabel={`Edit lesson for ${String(record.student || 'student')}`} onPress={onEdit} /></Panel>;
}

export default function LessonsScreen() {
  const { t } = useAppPreferences();
  const params = useLocalSearchParams<{ student?: string; action?: string; date?: string }>();
  const lessons = useRecords('lessons');
  const students = useRecords('students');
  const packages = useRecords('payments');
  const [showForm, setShowForm] = useState(params.action === 'new' || Boolean(params.student));
  const [student, setStudent] = useState(params.student || '');
  const [lessonDate, setLessonDate] = useState(params.date && /^\d{4}-\d{2}-\d{2}$/.test(params.date) ? params.date : dateValue());
  const [units, setUnits] = useState('1');
  const [modality, setModality] = useState<'Online' | 'Offline'>('Online');
  const [subject, setSubject] = useState('English');
  const [customSubject, setCustomSubject] = useState('');
  const [note, setNote] = useState('');
  const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<ClassioRecord | null>(null); const [confirmDelete, setConfirmDelete] = useState(false); const [query, setQuery] = useState(''); const [year, setYear] = useState('All years'); const [page, setPage] = useState(1);
  const pendingChange = useRef<{ payload: string; requestId: string } | null>(null);
  const changeRequestKey = (value: object) => { const payload = JSON.stringify(value); if (pendingChange.current?.payload !== payload) pendingChange.current = { payload, requestId: crypto.randomUUID() }; return pendingChange.current.requestId; };
  const studentNames = students.records.map((record) => String(record.student || '')).filter(Boolean);
  const studentOptions = students.records.map((record) => ({ value: String(record.student || ''), label: String(record.student || ''), detail: [record.email, record.phone].filter(Boolean).join(' · ') }));
  const selectStudent = (name: string) => { setStudent(name); const recent = packages.records.find((row) => String(row.student || '') === name); if (!recent) return; setModality(String(recent.modality) === 'Offline' ? 'Offline' : 'Online'); setSubject(String(recent.subject || 'English')); setCustomSubject(String(recent.subject_custom || '')); };
  const initialAutofillApplied = useRef(false); useEffect(() => { if (!params.student || initialAutofillApplied.current || !packages.records.length) return; initialAutofillApplied.current = true; selectStudent(params.student); }, [packages.records, params.student]);
  const years = ['All years', ...Array.from(new Set(lessons.records.map((row) => String(row.lesson_date || '').slice(0, 4)).filter(Boolean))).sort().reverse()];
  const filtered = useMemo(() => { const needle = query.trim().toLowerCase(); return lessons.records.filter((record) => (year === 'All years' || String(record.lesson_date || '').startsWith(year)) && (!needle || [record.student, record.subject, record.subject_custom, record.modality, record.note].join(' ').toLowerCase().includes(needle))); }, [lessons.records, query, year]); const pages = Math.max(1, Math.ceil(filtered.length / 18)); const currentPage = Math.min(page, pages); const pageRows = filtered.slice((currentPage - 1) * 18, currentPage * 18);

  const clearForm = () => { pendingChange.current = null; setEditing(null); setStudent(''); setLessonDate(dateValue()); setUnits('1'); setModality('Online'); setSubject('English'); setCustomSubject(''); setNote(''); setConfirmDelete(false); setShowForm(false); };
  const edit = (record: ClassioRecord) => { pendingChange.current = null; setEditing(record); setStudent(String(record.student || '')); setLessonDate(String(record.lesson_date || '').slice(0, 10)); setUnits(String(record.number_of_lesson || 1)); setModality(String(record.modality) === 'Offline' ? 'Offline' : 'Online'); setSubject(String(record.subject || 'English')); setCustomSubject(String(record.subject_custom || '')); setNote(String(record.note || '')); setConfirmDelete(false); setShowForm(true); };

  const save = async () => {
    setMessageTone('error');
    const chosenStudent = student.trim();
    const unitCount = Number(units);
    if (!chosenStudent) return setMessage(t('lessons.chooseStudent'));
    if (!isValidRecordDate(lessonDate)) { setMessageTone('error'); return setMessage('Choose a valid lesson date.'); }
    if (!isValidUnitCount(unitCount, 10)) { setMessageTone('error'); return setMessage('Lesson units must be a whole number from 1 to 10.'); }
    if (subject === 'Other' && !customSubject.trim()) return setMessage('Enter the custom subject name.');
    setSaving(true); setMessage('');
    try {
      const input = { student: chosenStudent, lessonDate, units: unitCount, modality, subject, customSubject, note };
      if (editing) await updateLesson(String(editing.id), input, changeRequestKey({ action: 'update', id: editing.id, input })); else await addLesson(input, changeRequestKey({ action: 'add', input }));
      setMessageTone('success'); setMessage(editing ? 'Lesson updated.' : 'Lesson recorded. The dashboard and analytics will now include it.');
      clearForm();
      await lessons.refresh();
    } catch (error) {
      setMessageTone('error'); setMessage(error instanceof Error ? error.message : 'The lesson could not be saved.');
    } finally { setSaving(false); }
  };
  const remove = async () => { if (!editing) return; if (!confirmDelete) return setConfirmDelete(true); setSaving(true); try { await deleteLesson(String(editing.id), changeRequestKey({ action: 'delete', id: editing.id })); setMessageTone('success'); setMessage('Lesson deleted.'); clearForm(); await lessons.refresh(); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : 'The lesson could not be deleted.'); } finally { setSaving(false); } };

  return <AppShell title={t('pages.lessons')} eyebrow={t('pages.lessonsEyebrow')}>
    <View style={styles.hero}><View style={styles.heroCopy}><Text style={styles.intro}>Record attendance and keep a clear, searchable history of every lesson delivered.</Text></View><View style={styles.heroActions}><Button secondary onPress={() => router.push({ pathname: '/smart-tools', params: { tool: 'plan', subject: subject === 'Other' ? customSubject || 'General' : subject, topic: note, student: student || studentNames[0] || '' } })}>{t('lessons.planNext')}</Button><Button onPress={() => showForm ? clearForm() : setShowForm(true)}>{showForm ? 'Close form' : '+ Record lesson'}</Button></View></View>{!showForm ? <ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} /> : null}
    <View style={styles.workflowTabs}><TabRail accessibilityLabel={t('pages.lessons')} items={[{ value: 'add', label: `➕ ${t('lessons.recordAttendance')}` }, { value: 'history', label: `📋 ${t('lessons.viewHistory')}` }]} value={showForm ? 'add' : 'history'} onChange={(value) => value === 'add' ? setShowForm(true) : clearForm()} /></View>
    {showForm ? <Panel style={styles.form}><Text style={styles.formTitle}>{editing ? 'Edit lesson' : 'Record attendance'}</Text><Text style={styles.formHint}>Choose the student and describe the lesson that was delivered.</Text>
      <Text style={styles.label}>{t('lessons.student')}</Text>{students.loading ? <LoadingState /> : studentNames.length === 0 ? <EmptyState title={t('lessons.noStudents')} body={t('lessons.noStudentsBody')} /> : <StudentSearchSelect label={t('lessons.student')} value={student} options={studentOptions} placeholder={t('lessons.chooseStudent')} help={t('lessons.studentHelp')} onChange={selectStudent} />}
      <View style={styles.twoColumns}><View style={styles.column}><Text style={styles.label}>Lesson date</Text><CalendarInput kind="date" label="Lesson date" value={lessonDate} onChange={setLessonDate} /></View><View style={styles.column}><Text style={styles.label}>Units delivered</Text><Field accessibilityLabel="Lesson units" keyboardType="numeric" value={units} onChangeText={setUnits} /></View></View>
      <View style={styles.twoColumns}><View style={styles.column}><SelectField label="Modality" value={modality} options={[{ value: 'Online', label: 'Online' }, { value: 'Offline', label: 'In person' }]} onChange={(value) => setModality(value as 'Online' | 'Offline')} /></View><View style={styles.column}><SelectField label="Subject" value={subject} options={SUBJECTS.map((item) => ({ value: item, label: item }))} onChange={setSubject} /></View></View>
      {subject === 'Other' ? <><Text style={styles.label}>Custom subject</Text><Field value={customSubject} onChangeText={setCustomSubject} placeholder="Subject name" /></> : null}
      <Text style={styles.label}>Lesson note</Text><Field value={note} onChangeText={setNote} placeholder="What did you cover?" />
      <View style={styles.save}><Button disabled={saving || students.loading} onPress={() => void save()}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Save lesson'}</Button>{editing ? <Button secondary disabled={saving} onPress={() => void remove()}>{confirmDelete ? 'Confirm delete' : 'Delete lesson'}</Button> : null}{confirmDelete ? <Text style={styles.deleteWarning}>This permanently removes this lesson. Click Confirm delete to continue.</Text> : null}</View><ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={messageTone} />
    </Panel> : null}
    {!showForm ? <><View style={styles.sectionHeader}><View><Text style={styles.sectionTitle}>{t('lessons.viewHistory')}</Text><Text style={styles.sectionHint}>{lessons.records.length} recorded lesson{lessons.records.length === 1 ? '' : 's'}</Text></View><Button secondary onPress={() => void lessons.refresh()}>{t('common.refresh')}</Button></View><View style={styles.historyToolbar}><Field accessibilityLabel="Search lessons" placeholder="Search student, subject, modality, or note…" value={query} onChangeText={(value) => { setQuery(value); setPage(1); }} style={styles.search} /><View style={styles.yearFilter}><SelectField label={t('lessons.filterYear')} value={year} options={years.map((value) => ({ value, label: value === 'All years' ? t('lessons.allYears') : value }))} onChange={(value) => { setYear(value); setPage(1); }} /></View></View>
    {!lessons.loading && !lessons.error && pageRows.length ? <BulkLessonEditor rows={pageRows} onSaved={lessons.refresh} /> : null}
    {lessons.loading ? <LoadingState /> : lessons.error ? <EmptyState title="Lesson history could not be loaded" body={lessons.error} /> : filtered.length === 0 ? <EmptyState title="No matching lessons" body="Try another search or record a lesson." /> : <View style={styles.list}>{pageRows.map((record, index) => <LessonRow key={String(record.id || index)} record={record} onEdit={() => edit(record)} />)}</View>}<Pagination page={currentPage} totalPages={pages} totalItems={filtered.length} onPageChange={setPage} /></> : null}
  </AppShell>;
}

const styles = StyleSheet.create({
  hero: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16, marginBottom: 14 }, heroCopy: { flex: 1, minWidth: 260 }, heroActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, intro: { color: colors.muted, fontSize: 16, lineHeight: 24, maxWidth: 700 }, message: { color: colors.primary, fontSize: 13, fontWeight: '700', marginTop: 8 }, workflowTabs: { marginBottom: 22 },
  form: { gap: 8, marginBottom: 28, padding: 24 }, formTitle: { color: colors.ink, fontSize: 22, fontWeight: '800' }, formHint: { color: colors.muted, fontSize: 14, marginBottom: 6 }, label: { color: colors.ink, fontSize: 12, fontWeight: '800', marginTop: 10 }, choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, choice: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 999, paddingHorizontal: 13, paddingVertical: 8 }, choiceActive: { backgroundColor: colors.primary, borderColor: colors.primary }, choiceText: { color: colors.muted, fontSize: 12, fontWeight: '700' }, choiceTextActive: { color: colors.inverse },
  twoColumns: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, column: { flex: 1, minWidth: 220, gap: 7 }, save: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, alignSelf: 'flex-start', marginTop: 12 }, deleteWarning: { color: colors.danger, fontSize: 10, maxWidth: 300 }, sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 }, sectionTitle: { color: colors.ink, fontSize: 20, fontWeight: '800' }, sectionHint: { color: colors.subtle, fontSize: 12, marginTop: 3 }, historyToolbar: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, alignItems: 'flex-start', marginBottom: 12 }, search: { flex: 1, minWidth: 260 }, yearFilter: { width: 170, minWidth: 150 }, list: { gap: 9 }, pagination: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: 16 }, pageText: { color: colors.muted, fontSize: 10 },
  lessonRow: { flexDirection: 'row', alignItems: 'center', gap: 15, paddingVertical: 14 }, dateBlock: { width: 48, height: 52, backgroundColor: colors.primarySoft, borderRadius: 12, alignItems: 'center', justifyContent: 'center' }, dateDay: { color: colors.primary, fontSize: 18, fontWeight: '900' }, dateMonth: { color: colors.primary, fontSize: 9, fontWeight: '800' }, rowMain: { flex: 1, minWidth: 0 }, student: { color: colors.ink, fontSize: 15, fontWeight: '800' }, meta: { color: colors.muted, fontSize: 12, marginTop: 4 }, note: { color: colors.subtle, fontSize: 12, marginTop: 5 },
});
