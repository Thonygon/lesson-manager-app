import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Field, Panel, SelectField, TabRail } from '@/components/ui';
import { publicExploreCopy } from '@/lib/public-explore-copy';
import { useAppPreferences } from '@/providers/app-preferences';
import type { SmartToolKind } from '@/services/smart-tools';
import { colors } from '@/theme';

type Kind = SmartToolKind;
const kinds: Kind[] = ['plan', 'worksheet', 'exam', 'program'];
const typeOptions = ['multiple_choice', 'short_answer', 'true_false', 'fill_in_blank', 'matching'];
function readable(value: string) { return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function DocumentView({ value }: { value: unknown }) {
  if (value == null || value === '') return null;
  if (Array.isArray(value)) return <View style={styles.documentGroup}>{value.map((item, index) => <DocumentView key={index} value={item} />)}</View>;
  if (typeof value === 'object') return <View style={styles.documentGroup}>{Object.entries(value as Record<string, unknown>).filter(([key]) => !/prompt|base64|image_data/i.test(key)).map(([key, child]) => <View key={key} style={styles.documentLine}><Text style={styles.documentLabel}>{readable(key)}</Text><DocumentView value={child} /></View>)}</View>;
  return <Text style={styles.documentText}>{String(value)}</Text>;
}
export function PublicSmartTool({ initial, onClose }: { initial: Kind; onClose: () => void }) {
  const { language } = useAppPreferences(); const copy = publicExploreCopy(language);
  const [kind, setKind] = useState<Kind>(initial); const [subject, setSubject] = useState('english'); const [stage, setStage] = useState('secondary'); const [level, setLevel] = useState('A2'); const [topic, setTopic] = useState(''); const [worksheetType, setWorksheetType] = useState('multiple_choice'); const [examLength, setExamLength] = useState('short'); const [lessonPurpose, setLessonPurpose] = useState('introduce_concept'); const [notes, setNotes] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [document, setDocument] = useState<Record<string, unknown> | null>(null); const [used, setUsed] = useState<Kind[]>([]);
  const select = (label: string, value: string, options: string[], onChange: (value: string) => void) => <View style={styles.fieldCell}><Text style={styles.label}>{label}</Text><SelectField label={label} value={value} onChange={onChange} options={options.map((option) => ({ value: option, label: readable(option) }))} /></View>;
  async function generate() {
    if (!topic.trim()) { setError(copy.toolRequired); return; }
    if (kind === 'program') { router.push('/sign-in'); return; }
    setBusy(true); setError(''); setDocument(null);
    try {
      const response = await fetch('/api/generate', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, subject, topic: topic.trim(), stage, level, language, planLanguage: language, lessonPurpose, worksheetType, examLength, exerciseTypes: ['multiple_choice', 'short_answer', 'true_false'], notes, duration: '45 minutes', generationMode: 'AI' }) });
      const payload = await response.json() as { document?: Record<string, unknown>; error?: string };
      if (!response.ok || !payload.document) throw new Error(payload.error || copy.toolError);
      setDocument(payload.document); setUsed((current) => current.includes(kind) ? current : [...current, kind]);
    } catch (failure) { setError(failure instanceof Error ? failure.message : copy.toolError); } finally { setBusy(false); }
  }
  return <Panel style={styles.shell}>
    <View style={styles.header}><View style={styles.headerCopy}><Text style={styles.kicker}>{copy.toolLimit}</Text><Text style={styles.title}>{copy.toolPreview}</Text></View><Pressable accessibilityRole="button" onPress={onClose} style={styles.close}><Text style={styles.closeText}>✕</Text></Pressable></View>
    <TabRail items={kinds.map((value) => ({ value, label: readable(value) }))} value={kind} onChange={(value) => { setKind(value); setDocument(null); setError(''); }} />
    <View style={styles.grid}>{select(copy.toolSubject, subject, ['english', 'spanish', 'mathematics', 'science', 'music', 'study_skills'], setSubject)}{select(copy.toolStage, stage, ['lower_primary', 'upper_primary', 'secondary', 'adult'], setStage)}<View style={styles.fieldCell}><Text style={styles.label}>{copy.toolLevel}</Text><Field value={level} onChangeText={setLevel} /></View><View style={styles.fieldCell}><Text style={styles.label}>{copy.toolTopic}</Text><Field value={topic} onChangeText={setTopic} placeholder={copy.toolTopic} /></View>{kind === 'worksheet' ? select(copy.toolType, worksheetType, typeOptions, setWorksheetType) : null}{kind === 'exam' ? select(copy.toolLength, examLength, ['short', 'medium', 'long'], setExamLength) : null}{kind === 'plan' ? select(copy.toolPurpose, lessonPurpose, ['introduce_concept', 'practice', 'review', 'assessment'], setLessonPurpose) : null}<View style={styles.fieldCell}><Text style={styles.label}>{copy.toolNotes}</Text><Field value={notes} onChangeText={setNotes} placeholder={copy.toolNotes} /></View></View>
    {kind === 'program' ? <Text style={styles.muted}>{copy.toolProgramNote}</Text> : used.includes(kind) ? <Text style={styles.muted}>{copy.toolUsed}</Text> : null}
    {error ? <Text style={styles.error}>{error}</Text> : null}
    <Pressable accessibilityRole="button" disabled={busy || (kind !== 'program' && used.includes(kind))} onPress={() => void generate()} style={[styles.action, busy && styles.disabled]}><Text style={styles.actionText}>{busy ? copy.toolGenerating : kind === 'program' ? copy.toolProgramContinue : copy.toolGenerate}</Text></Pressable>
    {document ? <View style={styles.result}><Text style={styles.resultTitle}>{copy.toolPreview}</Text><DocumentView value={document} /><Pressable accessibilityRole="button" onPress={() => router.push('/sign-in')} style={styles.save}><Text style={styles.saveText}>{copy.toolSave} →</Text></Pressable></View> : null}
  </Panel>;
}
const styles = StyleSheet.create({ shell: { gap: 18, borderRadius: 22, borderColor: colors.lineStrong, padding: 24 }, header: { flexDirection: 'row', gap: 14 }, headerCopy: { flex: 1 }, kicker: { color: colors.primary, fontSize: 11, fontWeight: '800' }, title: { color: colors.ink, fontSize: 22, fontWeight: '900', marginTop: 5 }, close: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center', borderRadius: 17, backgroundColor: colors.surfaceSoft }, closeText: { color: colors.ink, fontWeight: '900' }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 }, fieldCell: { flexBasis: '45%', flexGrow: 1, minWidth: 180, gap: 6 }, label: { color: colors.inkSecondary, fontSize: 12, fontWeight: '800' }, muted: { color: colors.muted, fontSize: 13 }, error: { color: colors.danger, fontWeight: '700' }, action: { alignSelf: 'flex-start', paddingHorizontal: 18, paddingVertical: 12, backgroundColor: colors.primary, borderRadius: 11 }, disabled: { opacity: 0.5 }, actionText: { color: colors.inverse, fontWeight: '900' }, result: { gap: 12, padding: 18, backgroundColor: colors.surfaceSoft, borderRadius: 16 }, resultTitle: { color: colors.ink, fontSize: 18, fontWeight: '900' }, documentGroup: { gap: 9 }, documentLine: { paddingLeft: 11, borderLeftWidth: 2, borderLeftColor: colors.lineStrong, gap: 3 }, documentLabel: { color: colors.primary, fontSize: 12, fontWeight: '800' }, documentText: { color: colors.inkSecondary, fontSize: 13, lineHeight: 20 }, save: { alignSelf: 'flex-start', paddingVertical: 9 }, saveText: { color: colors.primary, fontWeight: '800' } });
