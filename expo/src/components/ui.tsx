import { useState, type PropsWithChildren, type ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, type TextInputProps, View } from 'react-native';

import { colors } from '@/theme';
import { useAppPreferences } from '@/providers/app-preferences';

export function Button({ children, onPress, disabled = false, secondary = false }: PropsWithChildren<{
  onPress: () => void;
  disabled?: boolean;
  secondary?: boolean;
}>) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.button, secondary && styles.buttonSecondary, (pressed || disabled) && styles.buttonDimmed]}
    >
      <Text style={[styles.buttonText, secondary && styles.buttonTextSecondary]}>{children}</Text>
    </Pressable>
  );
}

export function Field(props: TextInputProps) {
  return <TextInput {...props} placeholderTextColor={colors.subtle} style={[styles.field, props.style]} />;
}

export function Panel({ children, style }: PropsWithChildren<{ style?: object }>) {
  return <View style={[styles.panel, style]}>{children}</View>;
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <Panel style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyBody}>{body}</Text>
      {action}
    </Panel>
  );
}

export function LoadingState() {
  const { t } = useAppPreferences();
  return <View style={styles.loading}><ActivityIndicator color={colors.primary} /><Text style={styles.emptyBody}>{t('common.loading')}</Text></View>;
}

export function Pagination({ page, totalPages, totalItems, onPageChange }: { page: number; totalPages: number; totalItems?: number; onPageChange: (page: number) => void }) {
  const { t } = useAppPreferences();
  if (totalPages <= 1) return null;
  return <View style={styles.pagination}><Button secondary disabled={page <= 1} onPress={() => onPageChange(page - 1)}>{t('common.previous')}</Button><Text accessibilityRole="text" style={styles.pageText}>{t('common.pageOf', { page, pages: totalPages })}{typeof totalItems === 'number' ? ` · ${t('common.items', { count: totalItems })}` : ''}</Text><Button secondary disabled={page >= totalPages} onPress={() => onPageChange(page + 1)}>{t('common.next')}</Button></View>;
}

export type TabRailItem<T extends string> = { value: T; label: string };

export function TabRail<T extends string>({ items, value, onChange, accessibilityLabel }: { items: TabRailItem<T>[]; value: T; onChange: (value: T) => void; accessibilityLabel?: string }) {
  return <ScrollView accessibilityRole="tablist" accessibilityLabel={accessibilityLabel} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabRail}>{items.map((item) => { const active = item.value === value; return <Pressable key={item.value} accessibilityRole="tab" accessibilityState={{ selected: active }} onPress={() => onChange(item.value)} style={[styles.tab, active && styles.tabActive]}><Text style={[styles.tabText, active && styles.tabTextActive]}>{item.label}</Text></Pressable>; })}</ScrollView>;
}

export function Disclosure({ title, summary, defaultOpen = false, children, style }: PropsWithChildren<{ title: string; summary?: string; defaultOpen?: boolean; style?: object }>) {
  const [open, setOpen] = useState(defaultOpen);
  return <View style={[styles.disclosure, style]}><Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((current) => !current)} style={styles.disclosureHeader}><View style={styles.disclosureCopy}><Text style={styles.disclosureTitle}>{title}</Text>{summary ? <Text numberOfLines={open ? 3 : 1} style={styles.disclosureSummary}>{summary}</Text> : null}</View><Text style={styles.disclosureArrow}>{open ? '−' : '+'}</Text></Pressable>{open ? <View style={styles.disclosureBody}>{children}</View> : null}</View>;
}

export function SelectField({ label, value, options, placeholder, help, onChange }: { label: string; value: string; options: { value: string; label: string; detail?: string }[]; placeholder?: string; help?: string; onChange: (value: string) => void }) {
  const [open, setOpen] = useState(false); const selected = options.find((item) => item.value === value);
  return <View style={styles.selectWrap}><Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ expanded: open }} onPress={() => setOpen((current) => !current)} style={[styles.selectButton, open && styles.selectButtonOpen]}><View style={styles.selectCopy}><Text style={[styles.selectValue, !selected && styles.selectPlaceholder]}>{selected?.label || placeholder || label}</Text>{selected?.detail ? <Text numberOfLines={1} style={styles.selectDetail}>{selected.detail}</Text> : null}</View><Text style={styles.selectArrow}>{open ? '▴' : '▾'}</Text></Pressable>{help ? <Text style={styles.selectHelp}>{help}</Text> : null}{open ? <ScrollView nestedScrollEnabled style={styles.selectMenu} contentContainerStyle={styles.selectMenuContent}>{options.map((item) => <Pressable key={item.value} accessibilityRole="menuitem" onPress={() => { onChange(item.value); setOpen(false); }} style={[styles.selectOption, item.value === value && styles.selectOptionActive]}><Text style={[styles.selectOptionText, item.value === value && styles.selectOptionTextActive]}>{item.label}</Text>{item.detail ? <Text style={styles.selectOptionDetail}>{item.detail}</Text> : null}</Pressable>)}</ScrollView> : null}</View>;
}

const styles = StyleSheet.create({
  button: { minHeight: 46, borderRadius: 12, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primary },
  buttonSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  buttonDimmed: { opacity: 0.55 },
  buttonText: { color: colors.inverse, fontSize: 15, fontWeight: '700' },
  buttonTextSecondary: { color: colors.ink },
  field: { minHeight: 48, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, paddingHorizontal: 14, color: colors.ink, fontSize: 16 },
  panel: { borderWidth: 1, borderColor: colors.line, borderRadius: 18, backgroundColor: colors.surface, padding: 20 },
  empty: { alignItems: 'flex-start', gap: 8 },
  emptyTitle: { color: colors.ink, fontSize: 17, fontWeight: '700' },
  emptyBody: { color: colors.muted, fontSize: 14, lineHeight: 21 },
  loading: { minHeight: 180, alignItems: 'center', justifyContent: 'center', gap: 12 },
  pagination: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: 18 },
  pageText: { color: colors.muted, fontSize: 12, fontWeight: '700', minWidth: 120, textAlign: 'center' },
  tabRail: { flexDirection: 'row', alignItems: 'stretch', minWidth: '100%', borderBottomWidth: 1, borderBottomColor: colors.line, paddingHorizontal: 2 },
  tab: { minHeight: 46, justifyContent: 'center', borderBottomWidth: 3, borderBottomColor: 'transparent', paddingHorizontal: 16, paddingTop: 5, marginBottom: -1 },
  tabActive: { borderBottomColor: colors.primary },
  tabText: { color: colors.muted, fontSize: 13, fontWeight: '700' },
  tabTextActive: { color: colors.ink, fontWeight: '900' },
  disclosure: { borderWidth: 1, borderColor: colors.line, borderRadius: 15, backgroundColor: colors.surface, overflow: 'hidden' }, disclosureHeader: { minHeight: 54, flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 12 }, disclosureCopy: { flex: 1 }, disclosureTitle: { color: colors.ink, fontSize: 14, fontWeight: '800' }, disclosureSummary: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 2 }, disclosureArrow: { color: colors.primary, fontSize: 22, fontWeight: '500' }, disclosureBody: { borderTopWidth: 1, borderTopColor: colors.line, padding: 16 },
  selectWrap: { position: 'relative', gap: 5 }, selectButton: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, paddingHorizontal: 14, paddingVertical: 9 }, selectButtonOpen: { borderColor: colors.primary }, selectCopy: { flex: 1 }, selectValue: { color: colors.ink, fontSize: 15, fontWeight: '700' }, selectPlaceholder: { color: colors.subtle, fontWeight: '500' }, selectDetail: { color: colors.muted, fontSize: 10, marginTop: 2 }, selectArrow: { color: colors.primary, fontSize: 13, fontWeight: '900' }, selectHelp: { color: colors.subtle, fontSize: 10, lineHeight: 15 }, selectMenu: { maxHeight: 250, borderWidth: 1, borderColor: colors.lineStrong, borderRadius: 12, backgroundColor: colors.surface }, selectMenuContent: { padding: 5 }, selectOption: { borderRadius: 9, paddingHorizontal: 11, paddingVertical: 10 }, selectOptionActive: { backgroundColor: colors.primarySoft }, selectOptionText: { color: colors.ink, fontSize: 13, fontWeight: '700' }, selectOptionTextActive: { color: colors.primary }, selectOptionDetail: { color: colors.muted, fontSize: 9, marginTop: 2 },
});
