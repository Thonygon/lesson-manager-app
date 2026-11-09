import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Field, LoadingState, Panel, Pagination } from '@/components/ui';
import { AdminSelectField as SelectField } from '@/components/admin-select-field';
import { AdminAccountResetPanel } from '@/components/admin-account-reset-panel';
import { AdminConsumptionPanel } from '@/components/admin-consumption-panel';
import { dateLabel, KpiGrid } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { performAdminAction } from '@/services/admin-actions';
import { getAdminConsumption, searchAdminAccounts } from '@/services/admin-consumption';
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
  const [usageRevision, setUsageRevision] = useState(0);
  const reloadAccount = async () => { await reload(); setUsageRevision((current) => current + 1); };
  const hasStaffRole = staffRoles.some((staff) => text(staff.user_id) === text(row.user_id) && staff.is_active === true);
  const modes = [...(canTeach ? ['teacher'] : []), ...(canStudy ? ['student'] : []), ...(role === 'admin' ? ['admin'] : []), ...(role === 'admin' || hasStaffRole ? ['developer_workspace'] : [])];
  const selectedMode = modes.includes(activeMode) ? activeMode : modes[0] || '';
  const yesNo = [{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }];
  const save = async () => {
    setBusy(true); setMessage('');
    try {
      await performAdminAction({ action: 'user_update', userId: row.user_id, name, email, role, canTeach, canStudy, activeMode: selectedMode, accountStatus, planId, subscriptionStatus, notes, reason }, language);
      await reloadAccount();
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
      <View style={styles.field}><SelectField label={t('admin.plan')} value={planId} options={plans.map((plan) => ({ value: text(plan.id), label: text(plan.name || plan.id) }))} onChange={(value) => { setPlanId(value); setSubscriptionStatus(value === 'free' ? 'free' : 'active'); }} /></View>
      <View style={styles.field}><SelectField label={t('admin.subscriptionStatus')} value={subscriptionStatus} options={['free', 'active', 'trialing', 'past_due', 'canceled', 'expired'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setSubscriptionStatus} /></View>
    </View>
    <Text style={styles.help}>{t('admin.accountFieldsHelp')}</Text>
    <Text style={styles.label}>{t('admin.notes')}</Text><Field accessibilityLabel={t('admin.notes')} value={notes} onChangeText={setNotes} multiline numberOfLines={3} />
    <Text style={styles.label}>{t('admin.reason')}</Text><Field accessibilityLabel={t('admin.reason')} value={reason} onChangeText={setReason} placeholder={t('admin.reasonRequired')} />
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: confirmed }} onPress={() => setConfirmed(!confirmed)} style={styles.confirm}><Text style={styles.mark}>{confirmed ? '☑' : '☐'}</Text><Text style={styles.confirmText}>{t('admin.confirmUserEdit')}</Text></Pressable>
    <Button disabled={busy || !confirmed || !reason.trim() || !selectedMode || !email.trim()} onPress={() => void save()}>{busy ? t('common.saving') : t('admin.saveAccess')}</Button>
    <ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={tone} />
  </Panel><AdminConsumptionPanel userId={text(row.user_id)} plans={plans} refreshRevision={usageRevision} /><AdminAccountResetPanel userId={text(row.user_id)} initialNotes={text(row.admin_notes)} reload={reloadAccount} /></View>;
}

export function AdminUserEditor({ profiles, plans, staffRoles, reload }: { profiles: Row[]; plans: Row[]; staffRoles: Row[]; reload: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const [userId, setUserId] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [remoteMatches, setRemoteMatches] = useState<Row[]>([]);
  const [remoteAccount, setRemoteAccount] = useState<Row | null>(null);
  const [remoteStaff, setRemoteStaff] = useState<Row[]>([]);
  const [remoteError, setRemoteError] = useState('');
  useEffect(() => {
    const query = search.trim();
    if (query.length < 2) return;
    let active = true;
    const timer = setTimeout(() => { void searchAdminAccounts(query).then((rows) => { if (active) setRemoteMatches(rows); }).catch(() => { if (active) setRemoteMatches([]); }); }, 300);
    return () => { active = false; clearTimeout(timer); };
  }, [search]);
  useEffect(() => {
    if (!userId || profiles.some((row) => text(row.user_id) === userId)) return;
    let active = true;
    void getAdminConsumption(userId).then((detail) => { if (active) { setRemoteAccount(detail.account); setRemoteStaff(detail.staffRoles); setRemoteError(''); } }).catch(() => { if (active) { setRemoteAccount(null); setRemoteError(t('admin.usageUnavailable')); } });
    return () => { active = false; };
  }, [profiles, t, userId]);
  const local = profiles.filter((row) => !search.trim() || [row.display_name, row.email, row.user_id].some((value) => text(value).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())));
  const matching = [...local, ...remoteMatches.filter((row) => !local.some((item) => text(item.user_id) === text(row.user_id)))];
  const pageSize = 18;
  const totalPages = Math.max(1, Math.ceil(matching.length / pageSize));
  const visible = matching.slice((Math.min(page, totalPages) - 1) * pageSize, Math.min(page, totalPages) * pageSize);
  const selected = profiles.find((row) => text(row.user_id) === userId) || (remoteAccount && text(remoteAccount.user_id) === userId ? remoteAccount : null);
  const reloadSelected = async () => {
    await reload();
    if (userId && !profiles.some((row) => text(row.user_id) === userId)) {
      const detail = await getAdminConsumption(userId);
      setRemoteAccount(detail.account);
      setRemoteStaff(detail.staffRoles);
    }
  };
  if (userId) return <View style={styles.stack}>
    <View><Button secondary onPress={() => { setUserId(''); setRemoteAccount(null); setRemoteError(''); }}>{t('admin.backToAccounts')}</Button></View>
    {selected ? <Editor key={userId} row={selected} plans={plans} staffRoles={remoteAccount ? remoteStaff : staffRoles} reload={reloadSelected} /> : remoteError ? <Text style={styles.help}>{remoteError}</Text> : <LoadingState />}
  </View>;
  return <View style={styles.stack}>
    <View><Text style={styles.label}>{t('admin.searchAccounts')}</Text><Field accessibilityLabel={t('admin.searchAccounts')} value={search} onChangeText={(value) => { setSearch(value); setPage(1); setUserId(''); setRemoteMatches([]); setRemoteAccount(null); setRemoteStaff([]); setRemoteError(''); }} placeholder={t('admin.searchAccounts')} /></View>
    {!matching.length ? <Text style={styles.help}>{t('admin.noAccountsBody')}</Text> : <>
      <View style={styles.cards}>{visible.map((row) => {
        const id = text(row.user_id);
        return <Pressable key={id} accessibilityRole="button" accessibilityLabel={`${t('admin.openAccount')}: ${text(row.display_name || row.email || id)}`} onPress={() => { setUserId(id); setRemoteAccount(null); setRemoteStaff([]); setRemoteError(''); }} style={styles.card}>
          <Text style={styles.cardTitle}>{text(row.display_name || row.email || id)}</Text>
          <Text style={styles.cardBody}>{text(row.email)}</Text>
          <Text style={styles.cardMeta}>{t(`admin.value.${text(row.role || 'teacher')}`)} · {text(plans.find((plan) => text(plan.id) === text(row.current_plan))?.name || row.current_plan || '—')} · {t(`admin.value.${text(row.account_status || 'active')}`)}</Text>
        </Pressable>;
      })}</View>
      <Pagination page={Math.min(page, totalPages)} totalPages={totalPages} totalItems={matching.length} onPageChange={setPage} />
    </>}
  </View>;
}

const styles = StyleSheet.create({ stack: { gap: 12 }, panel: { gap: 12 }, title: { color: colors.ink, fontSize: 18, fontWeight: '900' }, help: { color: colors.muted, fontSize: 12, lineHeight: 18 }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, field: { flexGrow: 1, flexBasis: 220, minWidth: 180 }, label: { color: colors.muted, fontSize: 11, fontWeight: '800', marginBottom: 5 }, cards: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, card: { flexBasis: 250, flexGrow: 1, minWidth: 220, borderWidth: 1, borderColor: colors.line, borderRadius: 16, backgroundColor: colors.surface, padding: 16, gap: 5 }, cardTitle: { color: colors.ink, fontSize: 16, fontWeight: '900' }, cardBody: { color: colors.muted, fontSize: 12 }, cardMeta: { color: colors.primary, fontSize: 11, fontWeight: '700' }, confirm: { flexDirection: 'row', alignItems: 'center', gap: 10 }, mark: { color: colors.primary, fontSize: 21 }, confirmText: { color: colors.ink, fontSize: 12, flexShrink: 1 } });
