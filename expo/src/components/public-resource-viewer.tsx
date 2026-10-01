import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { Panel } from '@/components/ui';
import { publicExploreCopy } from '@/lib/public-explore-copy';
import { getPublicResourceDetail, type PublicResource } from '@/services/public-data';
import { materialFromPublic } from '@/services/student-practice';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

const INTERNAL = new Set(['id', 'user_id', 'created_at', 'updated_at', 'is_public', 'status', 'builder_config', 'plan_json', 'worksheet_json', 'exam_data', 'program_data', 'answer_key', 'units', 'topics', 'thumbnail_url', 'video_id', 'youtube_url']);
function label(key: string) { return key.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function printable(value: unknown, depth = 0): string {
  if (depth > 7 || value == null || value === '') return '';
  if (typeof value === 'string') return value.startsWith('data:') ? '' : value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => printable(item, depth + 1)).filter(Boolean).join('\n');
  return Object.entries(value as Record<string, unknown>).filter(([key]) => !INTERNAL.has(key) && !/image|base64|prompt/i.test(key)).map(([key, child]) => { const body = printable(child, depth + 1); return body ? `${label(key)}\n${body}` : ''; }).filter(Boolean).join('\n\n');
}
function valueView(name: string, value: unknown, depth = 0): ReactNode {
  if (depth > 6 || value == null || value === '' || INTERNAL.has(name) || /image|base64|prompt/i.test(name)) return null;
  if (typeof value === 'string' && value.startsWith('data:')) return null;
  if (Array.isArray(value)) return <View key={name} style={styles.group}><Text style={styles.groupTitle}>{label(name)}</Text>{value.map((item, index) => <View key={`${name}-${index}`} style={styles.listItem}>{typeof item === 'object' && item !== null ? Object.entries(item as Record<string, unknown>).map(([key, child]) => valueView(key, child, depth + 1)) : <Text style={styles.body}>• {String(item)}</Text>}</View>)}</View>;
  if (typeof value === 'object') return <View key={name} style={styles.group}><Text style={styles.groupTitle}>{label(name)}</Text>{Object.entries(value as Record<string, unknown>).map(([key, child]) => valueView(key, child, depth + 1))}</View>;
  return <View key={name} style={styles.line}><Text style={styles.label}>{label(name)}</Text><Text style={styles.body}>{String(value)}</Text></View>;
}
function resourcePayload(resource: PublicResource): Record<string, unknown> {
  const raw = resource.raw;
  const payloadKey = resource.kind === 'plan' ? 'plan_json' : resource.kind === 'worksheet' ? 'worksheet_json' : resource.kind === 'exam' ? 'exam_data' : 'program_data';
  const payload = raw[payloadKey];
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) return payload as Record<string, unknown>;
  if (typeof payload === 'string') { try { const parsed = JSON.parse(payload); if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed; } catch { /* use fields below */ } }
  return raw;
}
function escapeHtml(value: string) { return value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char] || char); }
function printResource(resource: PublicResource) {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return;
  const child = window.open('', '_blank');
  if (!child) return;
  child.opener = null;
  const body = resource.kind === 'program' ? [resource.description, printable(resource.raw.program_data), printable(resource.raw.units), printable(resource.raw.topics)].filter(Boolean).join('\n\n') : printable(resourcePayload(resource));
  child.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(resource.title)}</title><style>body{font:15px/1.6 system-ui,sans-serif;color:#172033;max-width:850px;margin:40px auto;padding:0 24px}h1{font-size:30px;line-height:1.15}small{color:#64748b}pre{white-space:pre-wrap;font:inherit}img{max-width:100%;border-radius:12px}@media print{body{margin:0;max-width:none}}</style></head><body><small>CLASSIO · ${escapeHtml(resource.subject)} · ${escapeHtml(resource.level)}</small><h1>${escapeHtml(resource.title)}</h1>${resource.imageUrl && /^https?:|^data:image\//i.test(resource.imageUrl) ? `<img src="${escapeHtml(resource.imageUrl)}" alt="">` : ''}<pre>${escapeHtml(body)}</pre><script>window.addEventListener('load',()=>window.print())<\/script></body></html>`);
  child.document.close();
}

export function PublicResourceViewer({ selected, onClose, onPractice }: { selected: PublicResource; onClose: () => void; onPractice: (resource: PublicResource) => void }) {
  const { language } = useAppPreferences();
  const copy = publicExploreCopy(language);
  const [resource, setResource] = useState<PublicResource | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { let active = true; setResource(null); setError(''); void getPublicResourceDetail(selected.kind, selected.id).then((value) => { if (active) setResource(value); }).catch(() => { if (active) setError(copy.unavailable); }); return () => { active = false; }; }, [selected.kind, selected.id, copy.unavailable]);
  const practice = useMemo(() => resource ? materialFromPublic(resource) : null, [resource]);
  const payload = resource ? resourcePayload(resource) : null;
  const videoUrl = resource && resource.kind === 'video' ? String(resource.raw.youtube_url || '') : '';
  return <Panel style={styles.shell}>
    <View style={styles.header}><View style={styles.headerCopy}><Text style={styles.kicker}>{copy.contents.toUpperCase()}</Text><Text style={styles.title}>{selected.title}</Text><Text style={styles.meta}>{[selected.subject, selected.stage.replaceAll('_', ' '), selected.level, selected.author].filter(Boolean).join(' · ')}</Text></View><Pressable accessibilityRole="button" onPress={onClose} style={styles.close}><Text style={styles.closeText}>✕</Text></Pressable></View>
    {error ? <Text style={styles.error}>{error}</Text> : !resource ? <Text style={styles.body}>{copy.loading}</Text> : <>
      {resource.description ? <Text style={styles.intro}>{resource.description}</Text> : null}
      <View style={styles.actions}><Pressable accessibilityRole="button" onPress={() => printResource(resource)} style={styles.action}><Text style={styles.actionText}>🖨 {copy.print}</Text></Pressable>{practice?.questions.length ? <Pressable accessibilityRole="button" onPress={() => onPractice(resource)} style={styles.action}><Text style={styles.actionText}>✦ {copy.practice}</Text></Pressable> : null}{videoUrl ? <Pressable accessibilityRole="button" onPress={() => void Linking.openURL(videoUrl)} style={styles.action}><Text style={styles.actionText}>▶ {copy.video}</Text></Pressable> : null}</View>
      {resource.kind === 'program' ? <View style={styles.content}><Text style={styles.groupTitle}>{copy.structure}</Text>{Array.isArray(resource.raw.units) ? (resource.raw.units as Record<string, unknown>[]).map((unit, index) => <View key={String(unit.id || index)} style={styles.unit}><Text style={styles.unitTitle}>{copy.unit} {String(unit.unit_number || index + 1)} · {String(unit.title || '')}</Text>{unit.unit_summary ? <Text style={styles.body}>{String(unit.unit_summary)}</Text> : null}{(Array.isArray(resource.raw.topics) ? resource.raw.topics as Record<string, unknown>[] : []).filter((topic) => Number(topic.unit_number) === Number(unit.unit_number || index + 1)).map((topic, topicIndex) => <View key={String(topic.id || topicIndex)} style={styles.topic}><Text style={styles.label}>{copy.topic} {String(topic.topic_number || topicIndex + 1)} · {String(topic.title || '')}</Text>{topic.student_summary || topic.lesson_focus ? <Text style={styles.body}>{String(topic.student_summary || topic.lesson_focus)}</Text> : null}</View>)}</View>) : null}{resource.raw.program_data ? valueView('program', resource.raw.program_data) : null}</View> : <View style={styles.content}>{payload ? Object.entries(payload).map(([key, value]) => valueView(key, value)) : null}</View>}
    </>}
  </Panel>;
}

const styles = StyleSheet.create({ shell: { borderRadius: 22, padding: 24, gap: 18, borderWidth: 1, borderColor: colors.lineStrong }, header: { flexDirection: 'row', alignItems: 'flex-start', gap: 14 }, headerCopy: { flex: 1 }, kicker: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, title: { color: colors.ink, fontSize: 25, lineHeight: 31, fontWeight: '900', marginTop: 5 }, meta: { color: colors.muted, fontSize: 12, marginTop: 7 }, close: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceSoft }, closeText: { color: colors.ink, fontWeight: '900' }, intro: { color: colors.muted, lineHeight: 23, fontSize: 14 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 9 }, action: { borderRadius: 11, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.primarySoft, paddingHorizontal: 14, paddingVertical: 10 }, actionText: { color: colors.primary, fontSize: 12, fontWeight: '800' }, content: { gap: 16 }, group: { padding: 15, borderRadius: 14, backgroundColor: colors.surfaceSoft, gap: 8 }, groupTitle: { color: colors.ink, fontSize: 16, fontWeight: '900' }, line: { gap: 4, marginBottom: 8 }, label: { color: colors.inkSecondary, fontSize: 12, fontWeight: '800' }, body: { color: colors.inkSecondary, fontSize: 13, lineHeight: 20 }, listItem: { paddingLeft: 12, borderLeftWidth: 2, borderLeftColor: colors.lineStrong, marginTop: 5 }, unit: { padding: 16, borderRadius: 14, backgroundColor: colors.surfaceSoft, gap: 8 }, unitTitle: { color: colors.ink, fontSize: 15, fontWeight: '800' }, topic: { paddingLeft: 14, borderLeftWidth: 2, borderLeftColor: colors.primary, gap: 5 }, error: { color: colors.danger, fontWeight: '700' } });
