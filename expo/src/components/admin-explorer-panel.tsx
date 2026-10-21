import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ExamView } from '@/components/exam-view';
import { LessonPlanView } from '@/components/lesson-plan-view';
import { WorksheetView } from '@/components/worksheet-view';
import { ResourceEditor } from '@/components/resource-editor';
import { ActionFeedback, Button, Field, Pagination, Panel, SelectField, TabRail } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { loadAdminExplorerMove, performAdminAction } from '@/services/admin-actions';
import { colors } from '@/theme';
import { KpiGrid } from '@/components/workspace-ui';
import { canonicalSubjectLabel } from '@/lib/subjects';

type Row = Record<string, unknown>;
const string = (value: unknown) => String(value ?? '').trim();
export function AdminExplorerPanel({ moves, profiles, reload }: { moves: Row[]; profiles: Row[]; reload: () => Promise<void> }) {
  const { t, language } = useAppPreferences();
  const [status, setStatus] = useState('pending'), [kind, setKind] = useState('all'), [search, setSearch] = useState(''), [page, setPage] = useState(1);
  const pageSize = 18;
  const [selected, setSelected] = useState(''), [preview, setPreview] = useState<Row | null>(null), [previewError, setPreviewError] = useState(''), [previewBusy, setPreviewBusy] = useState(false);
  const [target, setTarget] = useState(''), [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [tone, setTone] = useState<'success' | 'error'>('error');
  const kinds = [...new Set(moves.map((row) => string(row.resource_type)).filter(Boolean))];
  const filtered = useMemo(() => moves.filter((row) => (status === 'all' || row.status === status) && (kind === 'all' || row.resource_type === kind) && (!search.trim() || [row.title, row.topic, row.subject, row.id, row.preview_text, row.anonymous_session_id].some((value) => string(value).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())))), [moves, status, kind, search]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice((Math.min(page, pages) - 1) * pageSize, Math.min(page, pages) * pageSize);
  const open = async (id: string) => {
    setSelected(id); setPreview(null); setPreviewError(''); setMessage(''); setPreviewBusy(true);
    try { setPreview(await loadAdminExplorerMove(id, language)); }
    catch (error) { setPreviewError(error instanceof Error ? error.message : t('admin.previewFailed')); }
    finally { setPreviewBusy(false); }
  };
  const run = async (action: 'explorer_publish' | 'explorer_assign' | 'explorer_archive' | 'explorer_edit', document?: Record<string, unknown>) => {
    if (busy || !selected) return;
    if (!reason.trim()) { setTone('error'); setMessage(t('admin.reasonRequired')); return; }
    setBusy(true); setMessage('');
    try { await performAdminAction({ action, moveId: selected, userId: target, reason, document }, language); await reload(); setTone('success'); setMessage(t('admin.actionSaved')); setPreview(await loadAdminExplorerMove(selected, language)); }
    catch (error) { setTone('error'); setMessage(error instanceof Error ? error.message : t('admin.actionFailed')); }
    finally { setBusy(false); }
  };
  const detail = preview?.payload_json && typeof preview.payload_json === 'object' && !Array.isArray(preview.payload_json) ? preview.payload_json as Row : {};
  return <View style={styles.stack}>
    <KpiGrid items={[{ label: t('admin.explorerTotal'), value: moves.length }, ...['pending', 'published', 'solved', 'archived'].map((value) => ({ label: t(`admin.value.${value}`), value: moves.filter((row) => row.status === value).length }))]} />
    <Panel style={styles.filters}><Text style={styles.title}>{t('admin.explorerQueue')}</Text><Text style={styles.help}>{t('admin.explorerQueueHelp')}</Text><TabRail accessibilityLabel={t('admin.status')} value={status} onChange={(value) => { setStatus(value); setPage(1); setSelected(''); setPreview(null); }} items={['pending', 'published', 'solved', 'archived', 'all'].map((value) => ({ value, label: value === 'all' ? t('admin.allStatuses') : t(`admin.value.${value}`) }))} /><View style={styles.filterRow}><View style={styles.filter}><Field accessibilityLabel={t('admin.searchMoves')} value={search} onChangeText={(value) => { setSearch(value); setPage(1); setSelected(''); setPreview(null); }} placeholder={t('admin.searchMoves')} /></View><View style={styles.filter}><SelectField label={t('admin.resourceType')} value={kind} options={[{ value: 'all', label: t('admin.allTypes') }, ...kinds.map((value) => ({ value, label: t(`admin.value.${value}`) }))]} onChange={(value) => { setKind(value); setPage(1); setSelected(''); setPreview(null); }} /></View></View><View style={styles.filterRow}><Text style={styles.help}>{t('admin.resultCount', { count: filtered.length })}</Text><Button secondary onPress={() => void reload()}>{t('admin.refresh')}</Button></View></Panel>
    <View style={styles.cardGrid}>{visible.map((row) => <Pressable key={string(row.id)} accessibilityRole="button" onPress={() => void open(string(row.id))} style={[styles.card, selected === string(row.id) && styles.cardSelected]}><Text style={styles.badge}>{t(`admin.value.${string(row.status)}`)}</Text><Text style={styles.cardTitle}>{string(row.title || row.topic || row.id)}</Text><Text style={styles.cardMeta}>{t(`admin.value.${string(row.resource_type)}`)} · {row.subject ? canonicalSubjectLabel(string(row.subject), t) : '—'}</Text>{row.preview_text ? <Text style={styles.help} numberOfLines={2}>{string(row.preview_text)}</Text> : null}<Text style={styles.cardAction}>{t('admin.inspectMove')} →</Text></Pressable>)}</View>
    {!filtered.length ? <Panel><Text style={styles.help}>{t('admin.noExplorer')}</Text></Panel> : <Pagination page={Math.min(page, pages)} totalPages={pages} totalItems={filtered.length} onPageChange={setPage} />}
    {selected ? <Panel style={styles.preview}><Text style={styles.title}>{t('admin.explorerPreview')}</Text>{previewBusy ? <Text style={styles.help}>{t('common.loading')}</Text> : previewError ? <ActionFeedback message={previewError} tone="error" /> : preview ? <><Text style={styles.help}>{string(preview.title)} · {t(`admin.value.${string(preview.status)}`)}</Text>{preview.resource_type === 'lesson_plan' ? <LessonPlanView detail={{ plan_json: detail }} locale={language} /> : preview.resource_type === 'worksheet' ? <WorksheetView detail={{ worksheet_json: detail, worksheet_type: (preview.meta_json as Row)?.worksheet_type }} locale={language} /> : preview.resource_type === 'exam' ? <ExamView detail={{ exam_data: detail.exam_data || detail, answer_key: detail.answer_key }} locale={language} /> : <Text style={styles.help}>{t('admin.unsupportedPreview')}</Text>}{['pending', 'solved'].includes(string(preview.status)) ? <ResourceEditor key={selected + String(preview.updated_at || '')} document={detail} examMode={preview.resource_type === 'exam'} worksheetType={string((preview.meta_json as Row)?.worksheet_type)} onApply={(document) => void run('explorer_edit', document)} /> : null}<Field accessibilityLabel={t('admin.reason')} value={reason} onChangeText={setReason} placeholder={t('admin.reasonRequired')} /><SelectField label={t('admin.assignTarget')} value={target} options={[{ value: '', label: t('admin.chooseAccount') }, ...profiles.map((row) => ({ value: string(row.user_id), label: string(row.email || row.display_name || row.user_id) }))]} onChange={setTarget} /><View style={styles.actions}>{preview.status === 'pending' ? <Button disabled={busy || !reason.trim()} onPress={() => void run('explorer_publish')}>{t('admin.publishMove')}</Button> : null}{['pending', 'solved'].includes(string(preview.status)) ? <Button secondary disabled={busy || !reason.trim() || !target} onPress={() => void run('explorer_assign')}>{t('admin.assignMove')}</Button> : null}{preview.status !== 'archived' ? <Button secondary disabled={busy || !reason.trim()} onPress={() => void run('explorer_archive')}>{t('admin.archiveMove')}</Button> : null}</View><ActionFeedback message={message} tone={tone} /></> : null}</Panel> : null}
  </View>;
}
const styles = StyleSheet.create({ stack: { gap: 14 }, filters: { gap: 11 }, title: { color: colors.ink, fontSize: 18, fontWeight: '900' }, help: { color: colors.muted, fontSize: 11, lineHeight: 17 }, filterRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, filter: { flex: 1, minWidth: 210 }, cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, card: { flexGrow: 1, flexBasis: 260, padding: 17, borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 16, backgroundColor: colors.surface }, cardSelected: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, badge: { color: colors.primary, fontSize: 10, fontWeight: '900', textTransform: 'uppercase' }, cardTitle: { color: colors.ink, fontSize: 15, fontWeight: '900', marginTop: 7 }, cardMeta: { color: colors.muted, fontSize: 11, marginTop: 6 }, cardAction: { color: colors.primary, fontSize: 11, fontWeight: '900', marginTop: 11 }, preview: { gap: 12 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 } });
