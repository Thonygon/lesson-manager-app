import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Field, Panel, SelectField } from '@/components/ui';
import { AdminAccountResetPanel } from '@/components/admin-account-reset-panel';
import { dateLabel, KpiGrid } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { performAdminAction } from '@/services/admin-actions';
import { colors } from '@/theme';

type Row = Record<string, unknown>;
const text = (value: unknown) => String(value ?? '');

function Editor({ row, plans, staffRoles, reload }: { row: Row; plans: Row[]; staffRoles: Row[]; reload: () => Promise<void> }) {
  const { t, language } = useAppPreferences();
  const [name, setName] = useState(text(row.display_name));
  const [email, setEmail] = useState(text(row.email));
  const [role, setRole] = useState(text(row.role || 'teacher'));
  const [canTeach, setCanTeach] = useState(row.can_teach == null ? ['teacher', 'school_admin', 'admin'].includes(text(row.role)) : row.can_teach === true);
  const [canStudy, setCanStudy] = useState(row.can_study == null ? text(row.role) === 'student' : row.can_study === true);
  const [activeMode, setActiveMode] = useState(text(row.last_active_mode || 'teacher'));
  const [accountStatus, setAccountStatus] = useState(text(row.account_status || 'active'));
  const [planId, setPlanId] = useState(text(row.current_plan || 'free'));
  const [subscriptionStatus, setSubscriptionStatus] = useState(text(row.subscription_status || 'free').replace('cancelled', 'canceled'));
  const [notes, setNotes] = useState(text(row.admin_notes));
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [tone, setTone] = useState<'success' | 'error'>('error');
  const hasStaffRole = staffRoles.some((staff) => text(staff.user_id) === text(row.user_id) && staff.is_active === true);
  const modes = [...(canTeach ? ['teacher'] : []), ...(canStudy ? ['student'] : []), ...(role === 'admin' ? ['admin'] : []), ...(role === 'admin' || hasStaffRole ? ['developer_workspace'] : [])];
  const selectedMode = modes.includes(activeMode) ? activeMode : modes[0] || '';
  const yesNo = [{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }];
  const save = async () => {
    setBusy(true); setMessage('');
    try {
      await performAdminAction({ action: 'user_update', userId: row.user_id, name, email, role, canTeach, canStudy, activeMode: selectedMode, accountStatus, planId, subscriptionStatus, notes, reason }, language);
      await reload();
      setTone('success'); setMessage(t('admin.userUpdated')); setConfirmed(false);
    } catch (error) { setTone('error'); setMessage(error instanceof Error ? error.message : t('admin.actionFailed')); }
    finally { setBusy(false); }
  };
  return <View style={styles.stack}><Panel style={styles.panel}>
    <Text style={styles.title}>{t('admin.userEditor')}</Text>
    <Text style={styles.help}>{t('admin.userEditorHelp')}</Text>
    <KpiGrid items={[{ label: t('admin.logins'), value: Number(row.login_count || 0) }, { label: t('admin.activeStudents'), value: Number(row.active_student_count || 0) }, { label: t('admin.lastLogin'), value: dateLabel(row.last_used_at) }]} />
    <View style={styles.grid}>
      <View style={styles.field}><Text style={styles.label}>{t('admin.displayName')}</Text><Field accessibilityLabel={t('admin.displayName')} value={name} onChangeText={setName} /></View>
      <View style={styles.field}><Text style={styles.label}>{t('common.email')}</Text><Field accessibilityLabel={t('common.email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" /></View>
      <View style={styles.field}><SelectField label={t('admin.role')} value={role} options={['teacher', 'student', 'school_admin', 'admin'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setRole} /></View>
      <View style={styles.field}><SelectField label={t('admin.teachingAccess')} value={canTeach ? 'yes' : 'no'} options={yesNo} onChange={(value) => setCanTeach(value === 'yes')} /></View>
      <View style={styles.field}><SelectField label={t('admin.studyAccess')} value={canStudy ? 'yes' : 'no'} options={yesNo} onChange={(value) => setCanStudy(value === 'yes')} /></View>
      <View style={styles.field}><SelectField label={t('admin.defaultMode')} value={selectedMode} options={modes.map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setActiveMode} /></View>
      <View style={styles.field}><SelectField label={t('admin.accountStatus')} value={accountStatus} options={['active', 'suspended'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setAccountStatus} /></View>
      <View style={styles.field}><SelectField label={t('admin.plan')} value={planId} options={plans.map((plan) => ({ value: text(plan.id), label: text(plan.name || plan.id) }))} onChange={setPlanId} /></View>
      <View style={styles.field}><SelectField label={t('admin.subscriptionStatus')} value={subscriptionStatus} options={['free', 'active', 'trialing', 'past_due', 'canceled', 'expired'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setSubscriptionStatus} /></View>
    </View>
    <Text style={styles.label}>{t('admin.notes')}</Text><Field accessibilityLabel={t('admin.notes')} value={notes} onChangeText={setNotes} multiline numberOfLines={3} />
    <Text style={styles.label}>{t('admin.reason')}</Text><Field accessibilityLabel={t('admin.reason')} value={reason} onChangeText={setReason} placeholder={t('admin.reasonRequired')} />
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: confirmed }} onPress={() => setConfirmed(!confirmed)} style={styles.confirm}><Text style={styles.mark}>{confirmed ? '☑' : '☐'}</Text><Text style={styles.confirmText}>{t('admin.confirmUserEdit')}</Text></Pressable>
    <Button disabled={busy || !confirmed || !reason.trim() || !selectedMode || !email.trim()} onPress={() => void save()}>{busy ? t('common.saving') : t('admin.saveAccess')}</Button>
    <ActionFeedback message={message} tone={tone} />
  </Panel><AdminAccountResetPanel userId={text(row.user_id)} initialNotes={text(row.admin_notes)} reload={reload} /></View>;
}

export function AdminUserEditor({ profiles, plans, staffRoles, reload }: { profiles: Row[]; plans: Row[]; staffRoles: Row[]; reload: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const [userId, setUserId] = useState('');
  const [search, setSearch] = useState('');
  const matching = profiles.filter((row) => !search.trim() || [row.display_name, row.email, row.user_id].some((value) => text(value).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())));
  const selected = profiles.find((row) => text(row.user_id) === userId);
  return <View style={styles.stack}>
    <View style={styles.grid}><View style={styles.field}><Text style={styles.label}>{t('admin.searchUsers')}</Text><Field accessibilityLabel={t('admin.searchUsers')} value={search} onChangeText={(value) => { setSearch(value); const needle = value.trim().toLocaleLowerCase(); if (needle) { const first = profiles.find((row) => [row.display_name, row.email, row.user_id].some((item) => text(item).toLocaleLowerCase().includes(needle))); setUserId(first ? text(first.user_id) : ''); } }} placeholder={t('admin.searchUsers')} /></View><View style={styles.field}><SelectField label={t('admin.selectUserToEdit')} value={userId} options={[{ value: '', label: t('admin.chooseAccount') }, ...matching.map((row) => ({ value: text(row.user_id), label: text(row.display_name || row.email || row.user_id) }))]} onChange={setUserId} /></View></View>
    {!matching.length ? <Text style={styles.help}>{t('admin.noAccountsBody')}</Text> : null}
    {selected ? <Editor key={userId} row={selected} plans={plans} staffRoles={staffRoles} reload={reload} /> : null}
  </View>;
}

const styles = StyleSheet.create({ stack: { gap: 12 }, panel: { gap: 12 }, title: { color: colors.ink, fontSize: 18, fontWeight: '900' }, help: { color: colors.muted, fontSize: 12, lineHeight: 18 }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, field: { flexGrow: 1, flexBasis: 220, minWidth: 180 }, label: { color: colors.muted, fontSize: 11, fontWeight: '800' }, confirm: { flexDirection: 'row', alignItems: 'center', gap: 10 }, mark: { color: colors.primary, fontSize: 21 }, confirmText: { color: colors.ink, fontSize: 12, flexShrink: 1 } });
