import { pressableActive } from "@/lib/pressable-state";
import { Image } from 'expo-image';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { PublicResource } from '@/services/public-data';
import { canonicalSubjectLabel } from '@/lib/subjects';
import { learnerStageLabel } from '@/lib/learner-stages';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

type ShowcaseResource = Omit<PublicResource, 'kind'> & { kind: PublicResource['kind'] | 'professional' };
const KIND_ICON: Record<ShowcaseResource['kind'], string> = { program: '📚', plan: '📝', worksheet: '📋', exam: '🧪', video: '🎬', professional: '💼' };

function displayResourceDescription(value: string, t: (key: string) => string) { const code = value.trim(); if (!/^[a-z][a-z0-9_]*$/i.test(code)) return value; for (const key of [`resources.term.${code.toLowerCase()}`, `student.exercise.${code.toLowerCase()}`]) { const translated = t(key); if (translated !== key) return translated; } return code.includes('_') ? code.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase()) : value; }

export function ResourceShowcaseCard({ item, onPress, description, eyebrow, compact = false, assigned = false, done = false }: { item: ShowcaseResource; onPress: () => void; description?: string; eyebrow?: string; compact?: boolean; assigned?: boolean; done?: boolean }) {
  const { t } = useAppPreferences();
  const stage = learnerStageLabel(item.stage, t);
  return <Pressable accessibilityRole="button" accessibilityLabel={[item.title, assigned ? t('students.recommendationAssigned') : '', done ? t('students.recommendationDoneProactively') : ''].filter(Boolean).join(', ')} onPress={onPress} style={(state) => [styles.card, compact && styles.compact, pressableActive(state) && styles.hover]}>
    <View style={styles.visual}>{item.imageUrl ? <Image source={item.imageUrl} style={styles.image} contentFit="cover" transition={180} /> : <Text style={styles.icon}>{KIND_ICON[item.kind]}</Text>}</View>
    <View style={styles.copy}>{assigned || done ? <View style={styles.badges}>{assigned ? <Text style={styles.assignedBadge}>{t('students.recommendationAssigned')}</Text> : null}{done ? <Text style={styles.doneBadge}>{t('students.recommendationDoneProactively')}</Text> : null}</View> : null}{eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}<Text numberOfLines={2} style={styles.title}>{item.title}</Text><Text numberOfLines={assigned || done ? 1 : 2} style={styles.description}>{displayResourceDescription(description || item.description || item.topic, t)}</Text><Text style={styles.meta}>{[canonicalSubjectLabel(item.subject, t), stage, item.level].filter(Boolean).join(' · ')}</Text></View>
  </Pressable>;
}

const styles = StyleSheet.create({
  card: { flexGrow: 1, flexBasis: 320, minWidth: 280, maxWidth: 530, flexDirection: 'row', minHeight: 132, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: 16, overflow: 'hidden' },
  compact: { width: '100%', height: 132, minWidth: 0, flexGrow: 0, flexBasis: 'auto' },
  hover: { borderColor: colors.primary, transform: [{ translateY: -2 }] },
  visual: { width: 132, minHeight: 132, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceSoft },
  image: { width: '100%', height: '100%' }, icon: { fontSize: 34 }, copy: { flex: 1, padding: 14 }, badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 5 }, assignedBadge: { color: colors.primary, backgroundColor: colors.primarySoft, fontSize: 9, fontWeight: '900', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5 }, doneBadge: { color: colors.success, backgroundColor: colors.successSoft, fontSize: 9, fontWeight: '900', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5 }, eyebrow: { color: colors.primary, fontSize: 8, fontWeight: '900', textTransform: 'uppercase', marginBottom: 4 }, title: { color: colors.ink, fontSize: 14, lineHeight: 18, fontWeight: '900' }, description: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 5 }, meta: { color: colors.primary, fontSize: 8, fontWeight: '800', textTransform: 'capitalize', marginTop: 'auto', paddingTop: 8 },
});
