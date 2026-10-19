import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useAppPreferences, type AppLanguage, type ThemePreference } from '@/providers/app-preferences';
import { colors } from '@/theme';

const LANGUAGES: { key: AppLanguage; short: string }[] = [
  { key: 'en', short: 'EN' },
  { key: 'es', short: 'ES' },
  { key: 'tr', short: 'TR' },
];
const THEMES: { key: ThemePreference; icon: string }[] = [
  { key: 'auto', icon: '◐' },
  { key: 'light', icon: '☀' },
  { key: 'dark', icon: '☾' },
];

export function PreferenceSwitcher({ compact = false, sidebar = false }: { compact?: boolean; sidebar?: boolean }) {
  const { language, setLanguage, theme, setTheme, t } = useAppPreferences();

  return (
    <View style={[styles.wrapper, compact && styles.wrapperCompact, sidebar && styles.wrapperSidebar]}>
      <View style={sidebar && styles.sidebarRow}>
        {sidebar ? <Text style={styles.sidebarLabel}>{t('account.language')}</Text> : null}
        <View accessibilityLabel={t('account.language')} style={styles.group}>
          {LANGUAGES.map((item) => (
            <Pressable
              accessibilityLabel={t(`language.${item.key}`)}
              accessibilityRole="button"
              accessibilityState={{ selected: language === item.key }}
              key={item.key}
              onPress={() => setLanguage(item.key)}
              style={[styles.option, language === item.key && styles.optionActive]}
            >
              <Text style={[styles.optionText, language === item.key && styles.optionTextActive]}>{item.short}</Text>
            </Pressable>
          ))}
        </View>
      </View>
      <View style={sidebar && styles.sidebarRow}>
        {sidebar ? <Text style={styles.sidebarLabel}>{t('account.theme')}</Text> : null}
        <View accessibilityLabel={t('account.theme')} style={styles.group}>
          {THEMES.map((item) => (
            <Pressable
              accessibilityLabel={t(`theme.${item.key}`)}
              accessibilityRole="button"
              accessibilityState={{ selected: theme === item.key }}
              key={item.key}
              onPress={() => setTheme(item.key)}
              style={[styles.option, theme === item.key && styles.optionActive]}
            >
              <Text style={[styles.optionText, styles.themeIcon, theme === item.key && styles.optionTextActive]}>{item.icon}</Text>
            </Pressable>
          ))}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { flexDirection: 'row', flexWrap: 'wrap', gap: 7, alignItems: 'center', justifyContent: 'flex-end' },
  wrapperCompact: { justifyContent: 'flex-start' },
  wrapperSidebar: { width: '100%', flexDirection: 'column', alignItems: 'stretch', gap: 8 },
  sidebarRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 6 },
  sidebarLabel: { color: colors.muted, fontSize: 11, fontWeight: '700', flexShrink: 1 },
  group: { flexDirection: 'row', borderWidth: 1, borderColor: colors.line, borderRadius: 10, backgroundColor: colors.surface, padding: 3 },
  option: { minWidth: 31, minHeight: 30, borderRadius: 7, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 7 },
  optionActive: { backgroundColor: colors.primary },
  optionText: { color: colors.muted, fontSize: 9, fontWeight: '900', letterSpacing: 0.4 },
  optionTextActive: { color: colors.inverse },
  themeIcon: { fontSize: 13, letterSpacing: 0 },
});
