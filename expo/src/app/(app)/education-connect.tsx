import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { ActionFeedback, Button, Panel } from '@/components/ui';
import { clearEducationIntent, currentEducationIntent, educationIntentFromParams, rememberEducationIntent } from '@/lib/education-intent';
import { useAppPreferences } from '@/providers/app-preferences';
import { useAuth } from '@/providers/auth-provider';
import { activateProfileWorkspaceMode } from '@/services/profile';
import { resolvePublicTeacher } from '@/services/teacher-public-profile';
import { colors } from '@/theme';

export default function EducationConnectScreen() {
  const params = useLocalSearchParams<{ publicId?: string; subject?: string }>();
  const { t } = useAppPreferences();
  const { profile, refreshProfile } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const intent = educationIntentFromParams(params.publicId, params.subject) || currentEducationIntent();
  useEffect(() => { if (params.publicId) rememberEducationIntent(params.publicId, params.subject); }, [params.publicId, params.subject]);
  const continueToTeacher = async () => {
    if (!intent || busy) return;
    setBusy(true); setError('');
    try {
      const teacherId = await resolvePublicTeacher(intent.publicId);
      if (!teacherId) throw new Error(t('education.teacherUnavailable'));
      if (String(profile?.last_active_mode || profile?.primary_role || profile?.role) !== 'student') {
        await activateProfileWorkspaceMode('student');
        await refreshProfile();
      }
      clearEducationIntent();
      router.replace({ pathname: '/student-find-teacher', params: { teacher: teacherId, subject: intent.subject } });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('education.teacherUnavailable'));
    } finally { setBusy(false); }
  };
  return <AppShell title={t('education.connectTitle')} eyebrow="Classio Education">
    <Panel style={styles.panel}>
      <Text style={styles.body}>{t('education.connectBody')}</Text>
      {!intent ? <Text style={styles.body}>{t('education.teacherUnavailable')}</Text> : <Button disabled={busy} onPress={() => void continueToTeacher()}>{busy ? t('common.loading') : t('education.continueToTeacher')}</Button>}
      <ActionFeedback message={error} tone="error" onDismiss={(shown) => setError((current) => current === shown ? '' : current)} />
    </Panel>
  </AppShell>;
}

const styles = StyleSheet.create({ panel: { gap: 16 }, body: { color: colors.ink, fontSize: 14, lineHeight: 22 } });
