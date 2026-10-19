import { Image } from 'expo-image';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Disclosure } from '@/components/ui';
import { worksheetHasSource, worksheetReferencesSource } from '@/lib/worksheet-source';
import { resourceSections } from '@/services/document-exports';
import { colors } from '@/theme';

type Locale = 'en' | 'es' | 'tr';

const PRIVATE_HEADINGS: Record<Locale, string[]> = {
  en: ['Answer key', 'Teacher notes'],
  es: ['Clave de respuestas', 'Notas docentes'],
  tr: ['Cevap anahtarı', 'Öğretmen notları'],
};
const TYPE_LABELS: Record<Locale, Record<string, string>> = {
  en: { short_answer: 'Short answer', reading_comprehension: 'Reading comprehension', multiple_choice: 'Multiple choice', true_false: 'True or false', matching: 'Matching', fill_in_the_blanks: 'Fill in the blanks', error_correction: 'Error correction', word_search_vocab: 'Vocabulary word search' },
  es: { short_answer: 'Respuesta corta', reading_comprehension: 'Comprensión lectora', multiple_choice: 'Opción múltiple', true_false: 'Verdadero o falso', matching: 'Emparejar', fill_in_the_blanks: 'Completar espacios', error_correction: 'Corrección de errores', word_search_vocab: 'Sopa de letras' },
  tr: { short_answer: 'Kısa cevap', reading_comprehension: 'Okuduğunu anlama', multiple_choice: 'Çoktan seçmeli', true_false: 'Doğru veya yanlış', matching: 'Eşleştirme', fill_in_the_blanks: 'Boşluk doldurma', error_correction: 'Hata düzeltme', word_search_vocab: 'Kelime avı' },
};
const SOURCE_HEADINGS: Record<Locale, string[]> = { en: ['Reading passage', 'Source text'], es: ['Texto de lectura', 'Texto de apoyo'], tr: ['Okuma metni', 'Kaynak metin'] };
const VOCAB_HEADINGS: Record<Locale, string> = { en: 'Vocabulary bank', es: 'Banco de vocabulario', tr: 'Kelime havuzu' };
const MISSING_SOURCE: Record<Locale, string> = { en: 'The questions refer to a source text that is missing from this worksheet. Add it in the content editor before sharing or assigning it.', es: 'Las preguntas se refieren a un texto que falta en esta ficha. Añádelo en el editor antes de compartirla o asignarla.', tr: 'Sorular bu çalışma kağıdında bulunmayan bir metne atıfta bulunuyor. Paylaşmadan veya atamadan önce içerik düzenleyicisinde ekleyin.' };

export function WorksheetView({ detail, locale }: { detail: Record<string, unknown>; locale: Locale }) {
  const { width } = useWindowDimensions();
  const sections = resourceSections(detail, 'teacher', locale);
  const worksheet = detail.worksheet_json && typeof detail.worksheet_json === 'object' ? detail.worksheet_json as Record<string, unknown> : detail;
  const worksheetType = String(worksheet.worksheet_type || detail.worksheet_type || '');
  const missingSource = worksheetReferencesSource(worksheet) && !worksheetHasSource(worksheet);
  return <View style={styles.root}>{worksheetType ? <Text style={styles.typeLabel}>{TYPE_LABELS[locale][worksheetType] || worksheetType.replaceAll('_', ' ')}</Text> : null}{missingSource ? <View style={styles.warning}><Text style={styles.warningText}>{MISSING_SOURCE[locale]}</Text></View> : null}{sections.map((section, index) => {
    const privateSection = PRIVATE_HEADINGS[locale].includes(section.heading);
    const sourceSection = SOURCE_HEADINGS[locale].includes(section.heading);
    const vocabularySection = section.heading === VOCAB_HEADINGS[locale];
    const content = <View style={styles.body}>
      {section.visuals?.map((url, imageIndex) => <Image key={imageIndex} source={{ uri: url }} style={styles.visual} contentFit="contain" />)}
      {section.table ? section.table.map((row, rowIndex) => <View key={rowIndex} style={styles.tableRow}>{row.map((cell, cellIndex) => <Text key={cellIndex} style={styles.line}>{cell}</Text>)}</View>) : section.grid ? <WordSearchGrid grid={section.grid} watermark={section.watermark} answerCells={section.answerCells} availableWidth={width} /> : section.lines.map((line, lineIndex) => <Text key={lineIndex} style={[styles.line, sourceSection && styles.sourceLine, vocabularySection && styles.vocabularyLine]}>{line}</Text>)}
    </View>;
    return privateSection ? <Disclosure key={`${section.heading}-${index}`} title={section.heading} defaultOpen={false} style={styles.privateSection} titleStyle={styles.title}>{content}</Disclosure> : <View key={`${section.heading}-${index}`} style={[styles.section, sourceSection && styles.sourceSection, vocabularySection && styles.vocabularySection]}>{section.heading ? <Text style={[styles.title, sourceSection && styles.sourceTitle]}>{section.heading}</Text> : null}{content}</View>;
  })}</View>;
}

function WordSearchGrid({ grid, watermark, answerCells, availableWidth }: { grid: string[][]; watermark?: string; answerCells?: [number, number][]; availableWidth: number }) {
  const columns = Math.max(1, ...grid.map((row) => row.length));
  const cell = Math.min(36, Math.max(15, availableWidth - 76) / columns);
  const solved = new Set(answerCells?.map(([row, column]) => `${row}:${column}`));
  return <View style={[styles.grid, { width: columns * cell, height: grid.length * cell }]}>
    {watermark ? <Image source={{ uri: watermark }} style={styles.gridWatermark} contentFit="contain" /> : null}
    {grid.map((row, rowIndex) => <View key={rowIndex} style={styles.gridRow}>{row.map((letter, columnIndex) => { const hit = solved.has(`${rowIndex}:${columnIndex}`); return <View key={columnIndex} style={[styles.gridCell, hit && styles.answerCell, { width: cell, height: cell }]}><Text style={[styles.gridLetter, hit && styles.answerLetter, { fontSize: Math.max(9, Math.min(16, cell * 0.5)) }]}>{letter}</Text></View>; })}</View>)}
  </View>;
}

const styles = StyleSheet.create({
  root: { gap: 11 },
  typeLabel: { alignSelf: 'flex-start', color: colors.primary, backgroundColor: colors.primarySoft, fontSize: 13, fontWeight: '800', paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999 },
  warning: { borderWidth: 1, borderColor: colors.warning, backgroundColor: colors.warningSoft, borderRadius: 14, padding: 14 },
  warningText: { color: colors.warning, fontSize: 13, lineHeight: 20 },
  section: { borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 14, padding: 16, gap: 10, backgroundColor: colors.surface },
  sourceSection: { borderColor: colors.violet, backgroundColor: colors.violetSoft },
  vocabularySection: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  sourceTitle: { color: colors.violet },
  sourceLine: { color: colors.violet },
  vocabularyLine: { color: colors.primary },
  privateSection: { borderRadius: 14 },
  title: { color: colors.primary, fontSize: 15, fontWeight: '800' },
  body: { gap: 7 },
  line: { color: colors.inkSecondary, fontSize: 13, lineHeight: 20, flex: 1 },
  visual: { width: '100%', height: 240 },
  tableRow: { flexDirection: 'row', gap: 10, paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: colors.line },
  grid: { position: 'relative', alignSelf: 'center', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', borderRadius: 10, backgroundColor: colors.surface },
  gridWatermark: { position: 'absolute', width: '100%', height: '100%', opacity: 0.12 },
  gridRow: { flexDirection: 'row' },
  gridCell: { alignItems: 'center', justifyContent: 'center', borderWidth: 0.5, borderColor: colors.line },
  gridLetter: { color: colors.ink, fontWeight: '800', textAlign: 'center' },
  answerCell: { backgroundColor: colors.primarySoft, borderColor: colors.primary, borderWidth: 1 },
  answerLetter: { color: colors.primary },
});
