import { Image } from 'expo-image';
import { StyleSheet, Text, View } from 'react-native';

import { Disclosure } from '@/components/ui';
import { resourceSections } from '@/services/document-exports';
import { colors } from '@/theme';

type Locale = 'en' | 'es' | 'tr';

const SECTION_ICONS = ['◈', '▤', '◎', '▦'];

export function LessonPlanView({ detail, locale }: { detail: Record<string, unknown>; locale: Locale }) {
  const sections = resourceSections(detail, 'full', locale);
  return <View style={styles.root}>
    {sections.map((section, index) => <Disclosure key={`${section.heading}-${index}`} title={`${SECTION_ICONS[index] || '▫'} ${section.heading}`} defaultOpen={index === 0} style={styles.section} titleStyle={styles.sectionTitle}>
      <View style={styles.sectionBody}>
        {section.visuals?.map((url, imageIndex) => <Image key={imageIndex} source={{ uri: url }} style={styles.visual} contentFit="contain" />)}
        {section.lines.map((line, lineIndex) => {
          const isLabel = section.subheadings?.includes(line);
          return <Text key={lineIndex} style={isLabel ? styles.label : styles.line}>{line}</Text>;
        })}
      </View>
    </Disclosure>)}
  </View>;
}

const styles = StyleSheet.create({
  root: { gap: 10 },
  section: { borderRadius: 14 },
  sectionTitle: { color: colors.primary, fontSize: 15 },
  sectionBody: { gap: 7 },
  label: { color: colors.ink, fontSize: 13, fontWeight: '800', marginTop: 8 },
  line: { color: colors.inkSecondary, fontSize: 13, lineHeight: 20 },
  visual: { width: '100%', height: 240 },
});
