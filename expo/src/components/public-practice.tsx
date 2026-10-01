import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Field, Panel, TabRail } from '@/components/ui';
import demoTranslations from '@/lib/public-demo-data.json';
import { fillExploreCopy, publicExploreCopy } from '@/lib/public-explore-copy';
import { useAppPreferences } from '@/providers/app-preferences';
import { gradePractice, type PracticeMaterial, type PracticeQuestion } from '@/services/student-practice';
import { colors } from '@/theme';

type DemoId = 'mc' | 'tf' | 'math';
const demoIds: DemoId[] = ['mc', 'tf', 'math'];
function demoMaterial(language: 'en' | 'es' | 'tr', id: DemoId): PracticeMaterial {
  const copy = demoTranslations[language] as Record<string, string>;
  const prefix = `demo_${id}_`;
  const title = copy[`${prefix}title`];
  const type = id === 'mc' ? 'multiple_choice' : id === 'tf' ? 'true_false' : 'short_answer';
  const answers = id === 'tf' ? ['True', 'False', 'True', 'True', 'False'] : id === 'math' ? ['3', '4', '2', '5', '14'] : [];
  const questions: PracticeQuestion[] = Array.from({ length: 5 }, (_, index) => ({
    prompt: copy[`${prefix}q${index + 1}${id === 'mc' ? '_stem' : ''}`],
    options: id === 'mc' ? Array.from({ length: 4 }, (_, option) => copy[`${prefix}q${index + 1}_opt_${option + 1}`]) : id === 'tf' ? ['True', 'False'] : [],
    answer: id === 'mc' ? copy[`${prefix}q${index + 1}_answer`] : answers[index],
    exerciseIndex: 0, questionIndex: index, exerciseType: type, sectionTitle: copy[`${prefix}section_title`], instructions: copy[`${prefix}instructions`], sourceText: '',
  }));
  return { title, sourceType: 'worksheet', sourceId: `demo_${id}`, subject: id === 'mc' ? 'english' : id === 'tf' ? 'science' : 'mathematics', topic: copy[`${prefix}section_title`], stage: 'lower_primary', level: 'A1', raw: {}, questions };
}
export function PublicPractice({ material, onClose, onComplete }: { material?: PracticeMaterial | null; onClose?: () => void; onComplete?: (id: DemoId) => void }) {
  const { language } = useAppPreferences();
  const copy = publicExploreCopy(language);
  const [demoId, setDemoId] = useState<DemoId>('mc');
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [done, setDone] = useState<DemoId[]>([]);
  const active = useMemo(() => material ?? demoMaterial(language, demoId), [material, language, demoId]);
  const result = submitted ? gradePractice(active, answers) : null;
  const labels = [copy.demoOne, copy.demoTwo, copy.demoThree];
  function submit() { setSubmitted(true); if (!material) { setDone((current) => current.includes(demoId) ? current : [...current, demoId]); onComplete?.(demoId); } }
  function choose(id: DemoId) { setDemoId(id); setAnswers({}); setSubmitted(false); }
  return <Panel style={styles.shell}>
    <View style={styles.header}><View style={styles.heading}><Text style={styles.kicker}>{copy.demoEyebrow}</Text><Text style={styles.title}>{material ? material.title : copy.demoTitle}</Text><Text style={styles.body}>{material ? material.topic : copy.demoBody}</Text></View>{onClose ? <Pressable accessibilityRole="button" onPress={onClose} style={styles.close}><Text style={styles.closeText}>✕</Text></Pressable> : null}</View>
    {!material ? <><TabRail items={demoIds.map((id, index) => ({ value: id, label: labels[index] }))} value={demoId} onChange={choose} /><Text style={styles.progress}>{fillExploreCopy(copy.demoProgress, { done: done.length, total: 3 })}</Text></> : null}
    {active.questions.map((question, index) => <View key={`${active.sourceId}-${index}`} style={styles.question}><Text style={styles.questionTitle}>{index + 1}. {question.prompt}</Text>{question.options.length ? <View style={styles.options}>{question.options.map((option) => <Pressable key={option} accessibilityRole="button" accessibilityState={{ selected: answers[String(index)] === option }} disabled={submitted} onPress={() => setAnswers((current) => ({ ...current, [index]: option }))} style={[styles.option, answers[String(index)] === option && styles.optionSelected]}><Text style={[styles.optionText, answers[String(index)] === option && styles.optionTextSelected]}>{option}</Text></Pressable>)}</View> : <Field editable={!submitted} value={answers[String(index)] || ''} onChangeText={(value) => setAnswers((current) => ({ ...current, [index]: value }))} placeholder={copy.demoStart} />}{result ? <Text style={[styles.feedback, result.rows[index].isCorrect ? styles.correct : styles.incorrect]}>{result.rows[index].isCorrect ? '✓' : `↳ ${question.answer}`}</Text> : null}</View>)}
    {result ? <View style={styles.result}><Text style={styles.resultText}>{fillExploreCopy(copy.demoScore, { correct: result.correct, total: result.total })}</Text><Pressable accessibilityRole="button" onPress={() => { setAnswers({}); setSubmitted(false); }} style={styles.action}><Text style={styles.actionText}>{copy.demoAgain}</Text></Pressable></View> : <Pressable accessibilityRole="button" onPress={submit} style={styles.action}><Text style={styles.actionText}>{copy.demoSubmit}</Text></Pressable>}
  </Panel>;
}
const styles = StyleSheet.create({ shell: { borderRadius: 22, padding: 24, gap: 18, borderColor: colors.lineStrong }, header: { flexDirection: 'row', gap: 14 }, heading: { flex: 1 }, kicker: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, title: { color: colors.ink, fontSize: 24, fontWeight: '900', marginTop: 6 }, body: { color: colors.muted, lineHeight: 21, marginTop: 7 }, close: { width: 34, height: 34, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceSoft, borderRadius: 17 }, closeText: { color: colors.ink, fontWeight: '900' }, progress: { color: colors.primary, fontWeight: '800', fontSize: 12 }, question: { backgroundColor: colors.surfaceSoft, borderRadius: 14, padding: 17, gap: 12 }, questionTitle: { color: colors.ink, fontSize: 15, fontWeight: '800' }, options: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, option: { borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 10, paddingVertical: 9, paddingHorizontal: 13, backgroundColor: colors.surface }, optionSelected: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, optionText: { color: colors.inkSecondary, fontWeight: '700' }, optionTextSelected: { color: colors.primary }, feedback: { fontWeight: '800' }, correct: { color: colors.success }, incorrect: { color: colors.orange }, result: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 14 }, resultText: { color: colors.ink, fontWeight: '900', fontSize: 17 }, action: { alignSelf: 'flex-start', backgroundColor: colors.primary, borderRadius: 11, paddingHorizontal: 18, paddingVertical: 12 }, actionText: { color: colors.inverse, fontWeight: '800' } });
