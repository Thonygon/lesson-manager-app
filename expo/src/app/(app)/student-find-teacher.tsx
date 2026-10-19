/* eslint-disable react-hooks/exhaustive-deps, react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react';
import { Image } from 'expo-image';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { AppShell } from '@/components/app-shell';
import { ResourceFilters } from '@/components/resource-filters';
import { ActionFeedback, Button, Disclosure, EmptyState, Field, LoadingState, Pagination, Panel } from '@/components/ui';
import { useAuth } from '@/providers/auth-provider';
import { useAppPreferences } from '@/providers/app-preferences';
import type { ClassioRecord } from '@/services/classio-data';
import { getCommunityProfiles, getStudentTeacherConnections, requestTeacherConnection, updateStudentConnection } from '@/services/student-data';
import { enableTeacherMode } from '@/services/profile';
import { colors } from '@/theme';
import { canonicalSubjectLabel } from '@/lib/subjects';

function values(row: ClassioRecord) { const primary = (Array.isArray(row.primary_subjects) ? row.primary_subjects as unknown[] : []).map(String).filter((value) => value && value !== 'other'); const custom = (Array.isArray(row.custom_subjects) ? row.custom_subjects as unknown[] : []).map(String).filter(Boolean); return [...new Set([...primary, ...custom])]; }
function languageCode(value: unknown) { const key = String(value || '').trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase(); return ['en', 'english', 'ingles', 'ingilizce'].includes(key) ? 'en' : ['es', 'spanish', 'espanol', 'ispanyolca'].includes(key) ? 'es' : ['tr', 'turkish', 'turco', 'turkce'].includes(key) ? 'tr' : ''; }
function languages(row: ClassioRecord): string[] { return [...new Set((Array.isArray(row.teaching_languages) ? row.teaching_languages as unknown[] : []).map(languageCode).filter(Boolean))]; }
const TEACHING_LANGUAGE_OPTIONS = ['en', 'es', 'tr'] as const;

function TeacherAvatar({ url, name }: { url: string; name: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  return url.trim() && !failed ? <Image source={{ uri: url.trim() }} style={styles.avatar} contentFit="cover" onError={() => setFailed(true)} accessibilityLabel={name} /> : <View style={styles.avatarFallback}><Text style={styles.avatarInitial}>{name.trim().charAt(0).toLocaleUpperCase() || '👤'}</Text></View>;
}

export default function StudentFindTeacherScreen() {
  const { t } = useAppPreferences(); const { profile, refreshProfile } = useAuth(); const [profiles, setProfiles] = useState<ClassioRecord[]>([]); const [links, setLinks] = useState<ClassioRecord[]>([]); const [query, setQuery] = useState(''); const [subject, setSubject] = useState('__all__'); const [selectedLanguage, setSelectedLanguage] = useState('__all__'); const [page, setPage] = useState(1); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [selected, setSelected] = useState<ClassioRecord | null>(null); const [requestSubjects, setRequestSubjects] = useState<string[]>([]); const [note, setNote] = useState(''); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error'); const [messageContext, setMessageContext] = useState<'request' | 'connection' | 'teacher'>('request'); const [confirmingLinkId, setConfirmingLinkId] = useState(''); const [confirmedEnd, setConfirmedEnd] = useState(false); const [enablingTeacher, setEnablingTeacher] = useState(false);
  const load = async () => { setLoading(true); try { const [rows, connections] = await Promise.all([getCommunityProfiles(), getStudentTeacherConnections()]); setProfiles(rows.filter((row) => Boolean(row.can_teach) || String(row.role || row.primary_role) === 'teacher')); setLinks(connections); setError(''); } catch (reason) { setError(reason instanceof Error ? reason.message : t('student.loadFailed')); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, [t]);
  const profileMap = useMemo(() => new Map(profiles.map((row) => [String(row.user_id), row])), [profiles]); const activeLinks = links.filter((row) => ['pending', 'active'].includes(String(row.status)));
  const languageFiltered = useMemo(() => profiles.filter((row) => selectedLanguage === '__all__' || languages(row).includes(selectedLanguage)), [profiles, selectedLanguage]);
  const subjects = useMemo(() => [...new Set(languageFiltered.flatMap(values))].sort(), [languageFiltered]);
  const visible = useMemo(() => { const needle = query.toLocaleLowerCase(); return languageFiltered.filter((row) => !activeLinks.some((link) => String(link.teacher_id) === String(row.user_id)) && (subject === '__all__' || values(row).includes(subject)) && (!needle || [row.display_name, row.username, row.country, ...values(row), ...languages(row)].join(' ').toLocaleLowerCase().includes(needle))); }, [languageFiltered, activeLinks, query, subject]);
  const pages = Math.max(1, Math.ceil(visible.length / 18)); const shown = visible.slice((Math.min(page, pages) - 1) * 18, Math.min(page, pages) * 18);
  const send = async () => { if (!selected) return; const requested = requestSubjects.filter((value) => values(selected).includes(value)); if (!requested.length) { setMessageContext('request'); setMessageTone('error'); return setMessage(t('student.subjectRequired')); } setMessageContext('request'); setBusy(true); setMessage(''); try { await requestTeacherConnection(String(selected.user_id), requested, note, t); setMessageTone('success'); setMessage(t('student.requestSent')); setSelected(null); setRequestSubjects([]); setNote(''); await load(); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.requestFailed')); } finally { setBusy(false); } };
  const closeLink = async (row: ClassioRecord) => { setBusy(true); try { await updateStudentConnection(String(row.id), String(row.status) === 'pending' ? 'withdrawn' : 'archived'); setMessageContext('connection'); setMessageTone('success'); setMessage(t(String(row.status) === 'pending' ? 'student.requestWithdrawn' : 'student.relationshipEnded')); setConfirmingLinkId(''); setConfirmedEnd(false); await load(); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('student.connectionUpdateFailed')); } finally { setBusy(false); } };
  const canTeach = profile?.can_teach === true || ['teacher', 'tutor'].includes(String(profile?.primary_role || profile?.role || ''));
  const becomeTeacher = async () => { setEnablingTeacher(true); setMessage(''); try { await enableTeacherMode(); await refreshProfile(); setMessageContext('teacher'); setMessageTone('success'); setMessage(t('student.becomeTeacherSuccess')); } catch { setMessageContext('teacher'); setMessageTone('error'); setMessage(t('student.becomeTeacherFailed')); } finally { setEnablingTeacher(false); } };
  return <AppShell title={t('student.findTeacher')} eyebrow={t('student.learningSpace')}>
    <Text style={styles.intro}>{t('student.findTeacherIntro')}</Text>
    {activeLinks.length ? <Disclosure title={t('student.myTeachers')} summary={t('student.connectionCount', { count: activeLinks.length })} defaultOpen><View style={styles.relationships}>{activeLinks.map((link) => { const teacher = profileMap.get(String(link.teacher_id)); const sourceSubjects = String(link.status) === 'active' && Array.isArray(link.active_subjects) ? link.active_subjects : link.requested_subjects; const requested = Array.isArray(sourceSubjects) ? (sourceSubjects as Record<string, unknown>[]).map((item) => canonicalSubjectLabel(item.subject_label || item.subject_key, t)).filter(Boolean) : []; const pending = String(link.status) === 'pending'; const confirming = confirmingLinkId === String(link.id); return <Panel key={String(link.id)} style={styles.relationship}><TeacherAvatar url={String(link.teacher_avatar_url || teacher?.avatar_url || '')} name={String(link.teacher_name || teacher?.display_name || teacher?.username || t('student.teacher'))} /><View style={styles.relationshipCopy}><Text style={styles.name}>{String(link.teacher_name || teacher?.display_name || teacher?.username || t('student.teacher'))}</Text><Text style={styles.meta}>{t(`student.connection.${String(link.status)}`)} · {requested.join(', ')}</Text></View><Button secondary disabled={busy} onPress={() => { if (pending) void closeLink(link); else { setConfirmingLinkId(confirming ? '' : String(link.id)); setConfirmedEnd(false); } }}>{pending ? t('student.withdrawRequest') : t('student.endConnection')}</Button>{confirming && !pending ? <View style={styles.confirmation}><Text style={styles.meta}>{t('student.endConnectionWarning')}</Text><Pressable accessibilityRole="checkbox" accessibilityState={{ checked: confirmedEnd }} onPress={() => setConfirmedEnd((current) => !current)}><Text style={styles.meta}>{confirmedEnd ? '☑' : '☐'} {t('student.confirmEndConnection')}</Text></Pressable><Button disabled={busy || !confirmedEnd} onPress={() => void closeLink(link)}>{t('student.confirmEndConnectionAction')}</Button></View> : null}</Panel>; })}</View></Disclosure> : null}{messageContext === 'connection' ? <ActionFeedback message={message} tone={messageTone} /> : null}
    <ResourceFilters query={query} onQueryChange={(value) => { setQuery(value); setPage(1); }} searchLabel={t('common.search')} searchPlaceholder={t('student.searchTeachers')} count={visible.length} facets={[{ key: 'language', label: t('profile.teachingLanguages'), value: selectedLanguage, allValue: '__all__', allLabel: t('common.all'), options: TEACHING_LANGUAGE_OPTIONS.map((value) => ({ value, label: t(`language.${value}`) })), onChange: (value) => { setSelectedLanguage(value); setSubject('__all__'); setPage(1); } }, { key: 'subject', label: t('community.subject'), value: subject, allValue: '__all__', allLabel: t('community.allSubjects'), options: subjects.map((value) => ({ value, label: canonicalSubjectLabel(value, t) })), onChange: (value) => { setSubject(value); setPage(1); } }]} />
    {messageContext === 'request' && !selected ? <ActionFeedback message={message} tone={messageTone} /> : null}
    {loading ? <LoadingState /> : error ? <EmptyState title={t('student.loadFailed')} body={error} /> : !shown.length ? <EmptyState title={t('student.noTeachers')} body={t('student.noTeachersBody')} /> : <View style={styles.grid}>{shown.map((row) => <Panel key={String(row.user_id)} style={styles.card}><View style={styles.profileHeader}><TeacherAvatar url={String(row.avatar_url || '')} name={String(row.display_name || row.username || t('community.member'))} /><View style={styles.profileDetails}><Text style={styles.name}>{String(row.display_name || row.username || t('community.member'))}</Text><Text style={styles.meta}>{[values(row).map((value) => canonicalSubjectLabel(value, t)).join(', '), languages(row).map((value) => t(`language.${value}`)).join(', '), row.country, row.education_level, `${String(row.active_student_count || 0)} ${t('community.active')}`].filter(Boolean).join(' · ')}</Text>{Boolean(row.show_community_contact) && String(row.email || '').trim() ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(`mailto:${encodeURIComponent(String(row.email).trim())}`)}><Text style={styles.contact}>✉️ {String(row.email).trim()}</Text></Pressable> : null}</View></View><Disclosure title={t('student.connect')} summary={selected?.user_id === row.user_id ? t('student.requestOpen') : t('student.connectHelp')}><Button secondary onPress={() => { setSelected(row); setRequestSubjects([]); setNote(''); }}>{t('student.chooseTeacher')}</Button>{selected?.user_id === row.user_id ? <View style={styles.form}><Text style={styles.label}>{t('student.requestSubjects')}</Text><View style={styles.chips}>{values(row).map((value) => { const chosen = requestSubjects.includes(value); return <Pressable key={value} accessibilityRole="checkbox" accessibilityState={{ checked: chosen }} accessibilityLabel={canonicalSubjectLabel(value, t)} onPress={() => setRequestSubjects((current) => chosen ? current.filter((item) => item !== value) : [...current, value])}><Text style={[styles.chip, chosen && styles.chipSelected]}>{canonicalSubjectLabel(value, t)}</Text></Pressable>; })}</View><Text style={styles.label}>{t('student.requestNote')}</Text><Field value={note} onChangeText={setNote} multiline numberOfLines={3} /><Button disabled={busy} onPress={() => void send()}>{busy ? t('common.saving') : t('student.sendRequest')}</Button></View> : null}</Disclosure></Panel>)}</View>}
    <Pagination page={Math.min(page, pages)} totalPages={pages} totalItems={visible.length} onPageChange={setPage} />
    {!canTeach ? <Panel style={styles.becomeTeacher}><View style={styles.becomeTeacherCopy}><Text style={styles.becomeTeacherTitle}>{t('student.becomeTeacherTitle')}</Text><Text style={styles.becomeTeacherBody}>{t('student.becomeTeacherBody')}</Text><Text style={styles.becomeTeacherCaption}>{t('student.becomeTeacherCaption')}</Text></View><Button disabled={enablingTeacher} onPress={() => void becomeTeacher()}>{enablingTeacher ? t('common.saving') : t('student.becomeTeacherAction')}</Button></Panel> : null}
  </AppShell>;
}

const styles = StyleSheet.create({
  intro: { color: colors.muted, fontSize: 15, lineHeight: 23, marginBottom: 14 },
  message: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 10, padding: 11, marginBottom: 12, fontSize: 11, fontWeight: '800' },
  relationships: { gap: 8 },
  relationship: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10, padding: 13 },
  relationshipCopy: { flex: 1, minWidth: 160 },
  confirmation: { width: '100%', gap: 8, paddingTop: 8 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 11 },
  card: { flexGrow: 1, flexBasis: 310, minWidth: 280 },
  profileHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: colors.primarySoft },
  avatarFallback: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primarySoft },
  avatarInitial: { color: colors.primary, fontSize: 22, fontWeight: '900' },
  profileDetails: { flex: 1 },
  contact: { color: colors.primary, fontSize: 11, marginTop: 5 },
  name: { color: colors.ink, fontSize: 16, fontWeight: '900' },
  meta: { color: colors.muted, fontSize: 10, lineHeight: 16, marginTop: 5 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { color: colors.ink, backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 12, overflow: 'hidden', paddingHorizontal: 12, paddingVertical: 9, fontSize: 11, fontWeight: '800', textTransform: 'capitalize' },
  chipSelected: { color: colors.inverse, backgroundColor: colors.primary, borderColor: colors.primary },
  form: { gap: 6, marginTop: 10 },
  label: { color: colors.ink, fontSize: 11, fontWeight: '800', marginTop: 4 },
  becomeTeacher: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginTop: 22 },
  becomeTeacherCopy: { flex: 1, minWidth: 240, gap: 6 },
  becomeTeacherTitle: { color: colors.ink, fontSize: 20, fontWeight: '900' },
  becomeTeacherBody: { color: colors.muted, fontSize: 12, lineHeight: 19 },
  becomeTeacherCaption: { color: colors.primary, fontSize: 11, fontWeight: '700' },
});
