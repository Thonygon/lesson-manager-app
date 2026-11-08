import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

/** Keep the passage available beside every answer without occupying the small screen. */
export function SourceTextReference({ text }: { text: string }) {
  const { t } = useAppPreferences();
  const [open, setOpen] = useState(false);
  return <>
    <Pressable accessibilityRole="button" accessibilityLabel={t('student.openPassage')} hitSlop={8} onPress={() => setOpen(true)} style={styles.trigger}>
      <Text style={styles.triggerText}>▤</Text>
    </Pressable>
    <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} accessibilityLabel={t('common.close')} onPress={() => setOpen(false)} />
        <View accessibilityViewIsModal accessibilityLabel={t('student.readingPassage')} style={styles.dialog}>
          <View style={styles.header}>
            <Text accessibilityRole="header" style={styles.title}>{t('student.readingPassage')}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={t('common.close')} onPress={() => setOpen(false)} hitSlop={12}><Text style={styles.close}>×</Text></Pressable>
          </View>
          <ScrollView nestedScrollEnabled style={styles.scroll} contentContainerStyle={styles.scrollContent}>
            <Text selectable style={styles.body}>{text}</Text>
          </ScrollView>
        </View>
      </View>
    </Modal>
  </>;
}

const styles = StyleSheet.create({
  trigger: { position: 'absolute', top: 11, right: 13, zIndex: 1, width: 28, height: 28, alignItems: 'center', justifyContent: 'center', borderColor: colors.line, borderWidth: 1, borderRadius: 7, backgroundColor: colors.surface },
  triggerText: { color: colors.primary, fontSize: 16, fontWeight: '700', lineHeight: 20 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.54)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  dialog: { width: '100%', maxWidth: 720, maxHeight: '85%', backgroundColor: colors.surface, borderRadius: 18, padding: 20 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 12 },
  title: { color: colors.ink, fontSize: 18, fontWeight: '800', flex: 1 },
  close: { color: colors.muted, fontSize: 28, lineHeight: 32 },
  scroll: { flexGrow: 0 }, scrollContent: { paddingBottom: 12 },
  body: { color: colors.ink, fontSize: 16, lineHeight: 26 },
});
