import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useAppPreferences } from '@/providers/app-preferences';
import type { SmartToolKind } from '@/services/smart-tools';
import { colors } from '@/theme';

const TOOLS: { key: SmartToolKind; icon: string; titleKey: string; bodyKey: string }[] = [
  { key: 'plan', icon: '📝', titleKey: 'smart.plan', bodyKey: 'smart.planBody' },
  { key: 'worksheet', icon: '📋', titleKey: 'smart.worksheet', bodyKey: 'smart.worksheetBody' },
  { key: 'exam', icon: '🧪', titleKey: 'smart.exam', bodyKey: 'smart.examBody' },
  { key: 'oral_presentation', icon: '🎙️', titleKey: 'oral.title', bodyKey: 'oral.toolBody' },
  { key: 'program', icon: '📚', titleKey: 'smart.program', bodyKey: 'smart.programBody' },
];

export { TOOLS };

export function SmartToolTabs({ active, onSelect }: { active: SmartToolKind; onSelect: (kind: SmartToolKind) => void }) {
  const { t } = useAppPreferences();
  const scroll = useRef<ScrollView>(null);
  const [offset, setOffset] = useState(0);
  const [viewport, setViewport] = useState(0);
  const [content, setContent] = useState(0);
  const maxOffset = Math.max(0, content - viewport);
  useEffect(() => {
    if (!viewport || !content) return;
    const index = TOOLS.findIndex((tool) => tool.key === active);
    scroll.current?.scrollTo({ x: Math.max(0, Math.min(maxOffset, index * 244 - viewport / 2 + 117)), animated: false });
  }, [active, content, maxOffset, viewport]);
  const move = (direction: -1 | 1) => scroll.current?.scrollTo({ x: Math.max(0, Math.min(maxOffset, offset + direction * 244)), animated: true });
  return <View style={styles.root}>
    <View style={styles.arrows}>
      <Pressable accessibilityRole="button" accessibilityLabel={t('common.previous')} accessibilityState={{ disabled: offset <= 2 }} disabled={offset <= 2} onPress={() => move(-1)} style={[styles.arrow, offset <= 2 && styles.arrowDisabled]}><Text style={styles.arrowGlyph}>←</Text></Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel={t('common.next')} accessibilityState={{ disabled: offset >= maxOffset - 2 }} disabled={offset >= maxOffset - 2} onPress={() => move(1)} style={[styles.arrow, offset >= maxOffset - 2 && styles.arrowDisabled]}><Text style={styles.arrowGlyph}>→</Text></Pressable>
    </View>
    <ScrollView ref={scroll} horizontal showsHorizontalScrollIndicator={false} onLayout={(event) => setViewport(event.nativeEvent.layout.width)} onContentSizeChange={(width) => setContent(width)} onScroll={(event) => setOffset(event.nativeEvent.contentOffset.x)} scrollEventThrottle={32} contentContainerStyle={styles.tabs}>
      {TOOLS.map((tool) => <Pressable accessibilityRole="tab" accessibilityState={{ selected: active === tool.key }} key={tool.key} onPress={() => onSelect(tool.key)} style={[styles.tab, active === tool.key && styles.tabActive]}><Text style={styles.icon}>{tool.icon}</Text><View style={styles.copy}><Text style={[styles.title, active === tool.key && styles.titleActive]}>{t(tool.titleKey)}</Text><Text style={[styles.body, active === tool.key && styles.bodyActive]}>{t(tool.bodyKey)}</Text></View></Pressable>)}
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({
  root: { marginBottom: 2 }, arrows: { flexDirection: 'row', justifyContent: 'flex-end', gap: 7, marginBottom: 9 },
  arrow: { width: 42, height: 42, alignItems: 'center', justifyContent: 'center', borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  arrowDisabled: { opacity: 0.38 }, arrowGlyph: { color: colors.primary, fontSize: 22, lineHeight: 26, fontWeight: '700' },
  tabs: { gap: 9, paddingBottom: 17 }, tab: { width: 235, minHeight: 92, padding: 13, borderRadius: 15, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  tabActive: { backgroundColor: colors.primary, borderColor: colors.primary }, icon: { fontSize: 22 }, copy: { flex: 1 },
  title: { color: colors.ink, fontSize: 13, fontWeight: '900' }, titleActive: { color: colors.inverse },
  body: { color: colors.muted, fontSize: 9, lineHeight: 14, marginTop: 4 }, bodyActive: { color: colors.inverseMuted },
});
