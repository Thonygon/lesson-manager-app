import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { Button, Panel } from '@/components/ui';
import { useAuth } from '@/providers/auth-provider';
import { setActiveMode } from '@/services/classio-data';
import { colors } from '@/theme';
import { useAppPreferences, type AppLanguage, type ThemePreference } from '@/providers/app-preferences';

function Choice({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) { return <Pressable onPress={onPress} style={[styles.choice, active && styles.choiceActive]}><Text style={[styles.choiceText, active && styles.choiceTextActive]}>{label}</Text></Pressable>; }

export default function AccountScreen() {
  const { profile, user, refreshProfile, signOut } = useAuth();
  const { language, theme, setLanguage, setTheme, t } = useAppPreferences();
  const activeMode = profile?.last_active_mode ?? profile?.primary_role ?? profile?.role;
  const details = [
    [t('account.email'), profile?.email || user?.email],
    [t('account.displayName'), profile?.display_name],
    [t('account.primaryRole'), profile?.primary_role || profile?.role],
    [t('account.teacherAccess'), profile?.can_teach ? t('account.enabled') : t('account.notEnabled')],
    [t('account.studentAccess'), profile?.can_study ? t('account.enabled') : t('account.notEnabled')],
  ];
  return (
    <AppShell title={t('account.title')} eyebrow={t('account.eyebrow')}>
      <Panel style={styles.preferences}><Text style={styles.modeTitle}>{t('account.appearance')}</Text><Text style={styles.modeHelp}>{t('account.appearanceHelp')}</Text><Text style={styles.preferenceLabel}>{t('account.language')}</Text><View style={styles.choices}>{(['en', 'es', 'tr'] as AppLanguage[]).map((item) => <Choice key={item} active={language === item} label={t(`language.${item}`)} onPress={() => setLanguage(item)} />)}</View><Text style={styles.preferenceLabel}>{t('account.theme')}</Text><View style={styles.choices}>{(['auto', 'light', 'dark'] as ThemePreference[]).map((item) => <Choice key={item} active={theme === item} label={t(`theme.${item}`)} onPress={() => setTheme(item)} />)}</View></Panel>
      <Panel style={styles.card}>
        {details.map(([label, value]) => (
          <View key={label} style={styles.detail}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value || '—'}</Text></View>
        ))}
        {profile?.can_teach && profile?.can_study ? <View style={styles.modeSection}><Text style={styles.modeTitle}>{t('account.workspaceMode')}</Text><Text style={styles.modeHelp}>{t('account.workspaceHelp')}</Text><View style={styles.modeActions}><Button secondary={activeMode !== 'teacher'} onPress={() => void setActiveMode('teacher').then(refreshProfile)}>{t('account.teacher')}</Button><Button secondary={activeMode !== 'student'} onPress={() => void setActiveMode('student').then(refreshProfile)}>{t('account.student')}</Button></View></View> : null}
        <View style={styles.action}><Button secondary onPress={() => void signOut()}>{t('account.signOut')}</Button></View>
      </Panel>
    </AppShell>
  );
}

const styles = StyleSheet.create({
  card: { gap: 0, maxWidth: 680 }, preferences: { gap: 8, maxWidth: 680, marginBottom: 14 }, preferenceLabel: { color: colors.ink, fontSize: 11, fontWeight: '800', marginTop: 8 }, choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, choice: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, borderRadius: 999, paddingHorizontal: 14, paddingVertical: 9 }, choiceActive: { borderColor: colors.primary, backgroundColor: colors.primarySoft }, choiceText: { color: colors.muted, fontSize: 11, fontWeight: '800' }, choiceTextActive: { color: colors.primary },
  detail: { flexDirection: 'row', justifyContent: 'space-between', gap: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.line },
  label: { color: colors.muted, fontSize: 14 },
  value: { color: colors.ink, fontSize: 14, fontWeight: '700', textTransform: 'capitalize', textAlign: 'right' },
  action: { alignItems: 'flex-start', marginTop: 22 },
  modeSection: { marginTop: 22, padding: 16, borderRadius: 14, backgroundColor: colors.primarySoft },
  modeTitle: { color: colors.ink, fontSize: 15, fontWeight: '800' },
  modeHelp: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 4 },
  modeActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 9, marginTop: 12 },
});
