import { StyleSheet, Text, View } from 'react-native';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

/** Explains provider payload and the limits of automatic identifier removal. */
export function AiDataNotice({ context = 'generation' }: { context?: 'generation' | 'refine' | 'cover' }) {
  const { t } = useAppPreferences();
  return <View style={styles.panel}>
    <Text style={styles.notice}>{t(context === 'refine' ? 'smart.aiRefineNotice' : context === 'cover' ? 'smart.aiCoverNotice' : 'smart.aiDataNotice')}</Text>
    <Text style={styles.limit}>{t('smart.aiRedactionLimit')}</Text>
  </View>;
}

const styles = StyleSheet.create({
  panel: { gap: 4, padding: 10, borderWidth: 1, borderColor: colors.line, borderRadius: 12, backgroundColor: colors.surfaceSoft },
  notice: { color: colors.inkSecondary, fontSize: 11, lineHeight: 17 },
  limit: { color: colors.muted, fontSize: 10, lineHeight: 15 },
});
