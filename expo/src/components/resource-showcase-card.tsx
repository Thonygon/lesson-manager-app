import { Image } from 'expo-image';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { PublicResource } from '@/services/public-data';
import { canonicalSubjectLabel } from '@/lib/subjects';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

const KIND_ICON: Record<PublicResource['kind'], string> = { program: '📚', plan: '📝', worksheet: '📋', exam: '🧪', video: '🎬' };

export function ResourceShowcaseCard({ item, onPress, description, eyebrow }: { item: PublicResource; onPress: () => void; description?: string; eyebrow?: string }) {
  const { t } = useAppPreferences();
  const stageKey = String(item.stage || '').toLowerCase().replace(/[\s-]+/g, '_');
  const stage = ['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage'].includes(stageKey) ? t(`profile.stage.${stageKey}`) : item.stage;
  return <Pressable accessibilityRole="button" accessibilityLabel={item.title} onPress={onPress} style={({ pressed, hovered }) => [styles.card, (pressed || hovered) && styles.hover]}>
    <View style={styles.visual}>{item.imageUrl ? <Image source={item.imageUrl} style={styles.image} contentFit="cover" transition={180} /> : <Text style={styles.icon}>{KIND_ICON[item.kind]}</Text>}</View>
    <View style={styles.copy}>{eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}<Text numberOfLines={2} style={styles.title}>{item.title}</Text><Text numberOfLines={2} style={styles.description}>{description || item.description || item.topic}</Text><Text style={styles.meta}>{[canonicalSubjectLabel(item.subject, t), stage, item.level].filter(Boolean).join(' · ')}</Text></View>
  </Pressable>;
}

const styles = StyleSheet.create({
  card: { flexGrow: 1, flexBasis: 320, minWidth: 280, maxWidth: 530, flexDirection: 'row', minHeight: 132, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 16, overflow: 'hidden' },
  hover: { borderColor: colors.primary, transform: [{ translateY: -2 }] },
  visual: { width: 132, minHeight: 132, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceSoft },
  image: { width: '100%', height: '100%' }, icon: { fontSize: 34 }, copy: { flex: 1, padding: 14 }, eyebrow: { color: colors.primary, fontSize: 8, fontWeight: '900', textTransform: 'uppercase', marginBottom: 4 }, title: { color: colors.ink, fontSize: 14, lineHeight: 18, fontWeight: '900' }, description: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 5 }, meta: { color: colors.primary, fontSize: 8, fontWeight: '800', textTransform: 'capitalize', marginTop: 'auto', paddingTop: 8 },
});
