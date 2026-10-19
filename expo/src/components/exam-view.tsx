import { Image } from 'expo-image';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Disclosure } from '@/components/ui';
import { resourceSections } from '@/services/document-exports';
import { colors } from '@/theme';

type Locale = 'en' | 'es' | 'tr';
const COPY = {
  en: { answers: 'Answer key', instructions: 'Instructions', source: 'Source text', vocabulary: 'Vocabulary bank' },
  es: { answers: 'Clave de respuestas', instructions: 'Instrucciones', source: 'Texto de apoyo', vocabulary: 'Banco de vocabulario' },
  tr: { answers: 'Cevap anahtarı', instructions: 'Yönergeler', source: 'Kaynak metin', vocabulary: 'Kelime havuzu' },
};
const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];

/** One printable exam view, with the teacher's answer key closed by default. */
export function ExamView({ detail, locale, showAnswers = true }: { detail: Record<string, unknown>; locale: Locale; showAnswers?: boolean }) {
  const { width } = useWindowDimensions();
  const exam = Object.keys(record(detail.exam_data)).length ? record(detail.exam_data) : detail;
  const rawSections = list(exam.sections).map(record).filter((section) => Object.keys(section).length);
  const sections = resourceSections(detail, 'student', locale);
  const answerSections = showAnswers ? resourceSections(detail, 'answers', locale) : [];
  const copy = COPY[locale];
  let examSectionIndex = 0;
  return <View style={styles.root}>
    {sections.map((section, index) => {
      const isInstructions = section.heading.toLowerCase() === 'instructions';
      const source = isInstructions ? {} : rawSections[examSectionIndex++] || {};
      const sourceText = String(source.source_text || '').trim();
      const vocabulary = list(source.vocabulary_bank).map(String).filter(Boolean);
      const vocabularyLine = vocabulary.join('  ·  ');
      const body = <View style={styles.body}>
        {section.visuals?.map((url, imageIndex) => <Image key={imageIndex} source={{ uri: url }} style={styles.visual} contentFit="contain" />)}
        {section.lines.map((line, lineIndex) => {
          const sourceLine = Boolean(sourceText && line.length > 12 && sourceText.includes(line.trim()));
          const vocabLine = Boolean(vocabularyLine && line.includes(vocabularyLine));
          return <Text key={lineIndex} style={[styles.line, sourceLine && styles.sourceLine, vocabLine && styles.vocabularyLine]}>{line}</Text>;
        })}
        {section.table?.map((row, rowIndex) => <View key={rowIndex} style={styles.tableRow}>{row.map((cell, cellIndex) => <Text key={cellIndex} style={styles.line}>{cell}</Text>)}</View>)}
        {section.grid ? <Grid grid={section.grid} width={width} watermark={section.watermark} /> : null}
      </View>;
      return <View key={`${section.heading}-${index}`} style={[styles.section, isInstructions && styles.instructionSection]}>
        <Text style={styles.heading}>{isInstructions ? copy.instructions : section.heading}</Text>
        {sourceText ? <Text style={styles.assetLabel}>{copy.source}</Text> : null}
        {vocabulary.length ? <Text style={styles.vocabularyLabel}>{copy.vocabulary}</Text> : null}
        {body}
      </View>;
    })}
    {answerSections.length ? <Disclosure title={copy.answers} defaultOpen={false} style={styles.answers} titleStyle={styles.heading}>
      <View style={styles.answerBody}>{answerSections.map((section, index) => <View key={`${section.heading}-${index}`} style={styles.answerGroup}><Text style={styles.answerTitle}>{section.heading}</Text>{section.lines.map((line, lineIndex) => <Text key={lineIndex} style={styles.line}>{line}</Text>)}</View>)}</View>
    </Disclosure> : null}
  </View>;
}

function Grid({ grid, width, watermark }: { grid: string[][]; width: number; watermark?: string }) {
  const columns = Math.max(1, ...grid.map((row) => row.length));
  const size = Math.min(34, Math.max(14, width - 90) / columns);
  return <View style={[styles.grid, { width: columns * size, height: grid.length * size }]}>
    {watermark ? <Image source={{ uri: watermark }} style={styles.watermark} contentFit="contain" /> : null}
    {grid.map((row, rowIndex) => <View key={rowIndex} style={styles.gridRow}>{row.map((letter, columnIndex) => <Text key={columnIndex} style={[styles.gridCell, { width: size, height: size, lineHeight: size - 2, fontSize: Math.min(15, size * 0.5) }]}>{letter}</Text>)}</View>)}
  </View>;
}

const styles = StyleSheet.create({
  root: { gap: 12 }, section: { backgroundColor: colors.surface, borderColor: colors.lineStrong, borderWidth: 1, borderRadius: 15, padding: 16, gap: 10 }, instructionSection: { backgroundColor: colors.primarySoft },
  heading: { color: colors.primary, fontSize: 16, fontWeight: '900' }, body: { gap: 8 }, line: { color: colors.inkSecondary, fontSize: 13, lineHeight: 21, flexShrink: 1 },
  sourceLine: { color: colors.violet, backgroundColor: colors.violetSoft, borderRadius: 8, padding: 6 }, vocabularyLine: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 8, padding: 6 },
  assetLabel: { color: colors.violet, fontSize: 11, fontWeight: '800' }, vocabularyLabel: { color: colors.primary, fontSize: 11, fontWeight: '800' },
  visual: { width: '100%', height: 230 }, tableRow: { flexDirection: 'row', gap: 10, borderBottomWidth: 1, borderBottomColor: colors.line, paddingVertical: 6 },
  answers: { borderRadius: 15 }, answerBody: { gap: 14 }, answerGroup: { gap: 5 }, answerTitle: { color: colors.primary, fontWeight: '800', fontSize: 13 },
  grid: { position: 'relative', alignSelf: 'center', alignItems: 'center', borderRadius: 10, overflow: 'hidden', backgroundColor: colors.surface }, watermark: { position: 'absolute', width: '100%', height: '100%', opacity: 0.12 }, gridRow: { flexDirection: 'row' }, gridCell: { color: colors.ink, textAlign: 'center', fontWeight: '800', borderWidth: 0.5, borderColor: colors.line },
});
