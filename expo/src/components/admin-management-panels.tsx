import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Field, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { performAdminAction } from '@/services/admin-actions';
import { ANALYTICS_CURRENCIES, getAnalyticsExchangeRate } from '@/services/teacher-currency';
import { colors } from '@/theme';

type Row = Record<string, unknown>;
const id = (value: unknown) => String(value ?? '');
const number = (value: string) => Number(value.trim());
const PLAN_FEATURE_GROUPS = [
  ['teacher', ['dashboard_access','dashboard_insights','dashboard_reports','students_access','students_profile_tools','students_progress_tools','students_recommendations','lessons_access','payments_access','calendar_access','analytics_access','resources_access','community_access','videos_access']],
  ['smart', ['ai_tools','smart_tools_access','smart_tools_worksheets','smart_tools_exams','smart_tools_lesson_plans','smart_tools_learning_programs','smart_tools_goal_explorer','smart_tools_student_personalization']],
  ['student', ['student_home_access','student_home_recommendations','student_practice_access','student_practice_history','student_practice_progress','student_study_plan_access','student_assignments_access','student_find_teacher_access']],
  ['billing', ['pdf_export','word_export','premium_tools','pricing_access','account_access','school_admin','admin_console_access','subscription_controls']],
] as const;
const PLAN_FEATURE_KEYS = PLAN_FEATURE_GROUPS.flatMap(([, keys]) => [...keys]);
const PREMIUM_TOOL_CANDIDATES = ['dashboard_insights','dashboard_reports','students_progress_tools','students_recommendations','analytics_access','smart_tools_access','smart_tools_worksheets','smart_tools_exams','videos_access','smart_tools_lesson_plans','smart_tools_learning_programs','smart_tools_goal_explorer','smart_tools_student_personalization','pdf_export','word_export'];
function inferredPlanFeature(key: string, features: Row) {
  const premium = features.premium_tools === true, ai = features.ai_tools === true, pdf = features.pdf_export === true, school = features.school_admin === true;
  const defaults: Record<string, boolean> = {
    dashboard_access: true, dashboard_insights: true, dashboard_reports: pdf,
    students_access: true, students_profile_tools: true, students_progress_tools: premium || ai, students_recommendations: ai,
    lessons_access: true, payments_access: true, calendar_access: true, analytics_access: premium, resources_access: true, community_access: true, videos_access: true,
    smart_tools_access: ai, smart_tools_worksheets: ai, smart_tools_exams: ai, smart_tools_lesson_plans: ai, smart_tools_learning_programs: ai && premium,
    smart_tools_goal_explorer: ai, smart_tools_student_personalization: ai && premium,
    student_home_access: true, student_home_recommendations: ai || premium, student_practice_access: true, student_practice_history: true,
    student_practice_progress: true, student_study_plan_access: true, student_assignments_access: true, student_find_teacher_access: true,
    pricing_access: true, account_access: true, admin_console_access: school, subscription_controls: school, word_export: pdf,
  };
  return defaults[key] ?? false;
}
function inferredPremiumHighlight(key: string, features: Row) {
  const saved = features.premium_tool_highlights;
  if (Array.isArray(saved) && saved.length) return saved.includes(key);
  return features[key] === true || (features.premium_tools === true && ['dashboard_insights','students_progress_tools','students_recommendations','analytics_access','smart_tools_access','smart_tools_worksheets','smart_tools_exams','smart_tools_lesson_plans','smart_tools_learning_programs','smart_tools_goal_explorer','smart_tools_student_personalization'].includes(key));
}

const yesNo = (t: (key: string) => string) => [{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }];
const subscriptionStatusOptions = (t: (key: string) => string) => ['free', 'active', 'trialing', 'past_due', 'canceled', 'expired'].map((value) => ({ value, label: t(`admin.value.${value}`) }));
function ConfirmAction({ checked, onChange, label }: { checked: boolean; onChange: (value: boolean) => void; label: string }) {
  return <Pressable accessibilityRole="checkbox" accessibilityState={{ checked }} onPress={() => onChange(!checked)} style={styles.confirmRow}><Text style={styles.confirmMark}>{checked ? '☑' : '☐'}</Text><Text style={styles.confirmText}>{label}</Text></Pressable>;
}


function useAction(reload: () => Promise<void>) {
  const { t, language } = useAppPreferences();
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [tone, setTone] = useState<'success' | 'error'>('error');
  const run = async (input: Record<string, unknown>) => {
    if (busy) return;
    setBusy(true); setMessage('');
    try { await performAdminAction(input, language); await reload(); setTone('success'); const successKey = `admin.success.${String(input.action || '')}`; setMessage(t(successKey) === successKey ? t('admin.actionSaved') : t(successKey)); }
    catch (reason) { setTone('error'); setMessage(reason instanceof Error ? reason.message : t('admin.actionFailed')); }
    finally { setBusy(false); }
  };
  return { busy, message, tone, run, clear: () => setMessage('') };
}

export function AdminAccountPanel({ profiles, plans, reload }: { profiles: Row[]; plans: Row[]; reload: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const createAction = useAction(reload), statusAction = useAction(reload);
  const [email, setEmail] = useState(''), [name, setName] = useState(''), [role, setRole] = useState('teacher');
  const [canTeach, setCanTeach] = useState(true), [canStudy, setCanStudy] = useState(false);
  const [staffRole, setStaffRole] = useState(''), [activeMode, setActiveMode] = useState('teacher');
  const [plan, setPlan] = useState('free'), [subscriptionStatus, setSubscriptionStatus] = useState('free');
  const [accountStatus, setAccountStatus] = useState('active'), [notes, setNotes] = useState('');
  const [createReason, setCreateReason] = useState(''), [confirmCreate, setConfirmCreate] = useState(false);
  const [userId, setUserId] = useState(''), [status, setStatus] = useState('active'), [reason, setReason] = useState(''), [confirmStatus, setConfirmStatus] = useState(false);
  const users = profiles.map((row) => ({ value: id(row.user_id), label: id(row.email || row.display_name || row.user_id) }));
  const activeModes = [...(canTeach ? ['teacher'] : []), ...(canStudy ? ['student'] : []), ...(role === 'admin' ? ['admin'] : []), ...(role === 'admin' || staffRole ? ['developer_workspace'] : [])];
  const selectedMode = activeModes.includes(activeMode) ? activeMode : activeModes[0] || '';
  const changeRole = (value: string) => { const teaching = value !== 'student'; setRole(value); setCanTeach(teaching); setCanStudy(!teaching); setActiveMode(teaching ? 'teacher' : 'student'); };
  return <View style={styles.stack}>
    <Panel style={styles.panel}>
      <Text style={styles.title}>{t('admin.createAccount')}</Text>
      <Text style={styles.help}>{t('admin.createAccountHelp')}</Text>
      <View style={styles.grid}>
        <View style={styles.field}><Text style={styles.fieldLabel}>{t('common.email')}</Text><Field accessibilityLabel={t('common.email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder={t('common.email')} /></View>
        <View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.displayName')}</Text><Field accessibilityLabel={t('admin.displayName')} value={name} onChangeText={setName} placeholder={t('admin.displayName')} /></View>
        <View style={styles.field}><SelectField label={t('admin.role')} value={role} options={['teacher', 'student', 'school_admin', 'admin'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={changeRole} /></View>
        <View style={styles.field}><SelectField label={t('admin.teachingAccess')} value={canTeach ? 'yes' : 'no'} options={yesNo(t)} onChange={(value) => setCanTeach(value === 'yes')} /></View>
        <View style={styles.field}><SelectField label={t('admin.studyAccess')} value={canStudy ? 'yes' : 'no'} options={yesNo(t)} onChange={(value) => setCanStudy(value === 'yes')} /></View>
        <View style={styles.field}><SelectField label={t('admin.initialStaffRole')} value={staffRole} options={[{ value: '', label: t('admin.noStaffRole') }, ...['developer', 'data_scientist'].map((value) => ({ value, label: t(`admin.value.${value}`) }))]} onChange={setStaffRole} /></View>
        <View style={styles.field}><SelectField label={t('admin.defaultMode')} value={selectedMode} options={activeModes.map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setActiveMode} /></View>
        <View style={styles.field}><SelectField label={t('admin.plan')} value={plan} options={plans.filter((row) => row.active !== false).map((row) => ({ value: id(row.id), label: id(row.name || row.id) }))} onChange={(value) => { setPlan(value); setSubscriptionStatus(value === 'free' ? 'free' : 'active'); }} /></View>
        <View style={styles.field}><SelectField label={t('admin.subscriptionStatus')} value={subscriptionStatus} options={subscriptionStatusOptions(t)} onChange={setSubscriptionStatus} /></View>
        <View style={styles.field}><SelectField label={t('admin.accountStatus')} value={accountStatus} options={['active', 'suspended'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setAccountStatus} /></View>
      </View>
      <Text style={styles.fieldLabel}>{t('admin.notes')}</Text><Field accessibilityLabel={t('admin.notes')} value={notes} onChangeText={setNotes} placeholder={t('admin.notes')} multiline numberOfLines={3} />
      <Text style={styles.fieldLabel}>{t('admin.reason')}</Text><Field accessibilityLabel={t('admin.reason')} value={createReason} onChangeText={setCreateReason} placeholder={t('admin.reasonRequired')} />
      <ConfirmAction checked={confirmCreate} onChange={setConfirmCreate} label={t('admin.confirmCreate')} />
      <View style={styles.actions}><Button disabled={createAction.busy || !email.trim() || !createReason.trim() || !selectedMode || !confirmCreate} onPress={() => void createAction.run({ action: 'account_create', email, name, role, canTeach, canStudy, staffRole, activeMode: selectedMode, planId: plan, subscriptionStatus, accountStatus, notes, reason: createReason })}>{t('admin.sendInvite')}</Button></View>
      <ActionFeedback message={createAction.message} tone={createAction.tone} />
    </Panel>
    <Panel style={styles.panel}>
      <Text style={styles.title}>{t('admin.accountStatusTitle')}</Text>
      <SelectField label={t('admin.account')} value={userId} options={[{ value: '', label: t('admin.chooseAccount') }, ...users]} onChange={(value) => { setUserId(value); setStatus(id(profiles.find((row) => id(row.user_id) === value)?.account_status || 'active')); setConfirmStatus(false); statusAction.clear(); }} />
      <SelectField label={t('admin.accountStatus')} value={status} options={['active', 'suspended'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setStatus} />
      <Field accessibilityLabel={t('admin.reason')} value={reason} onChangeText={setReason} placeholder={t('admin.reasonRequired')} />
      <ConfirmAction checked={confirmStatus} onChange={setConfirmStatus} label={t('admin.confirmAccountAction')} />
      <View style={styles.actions}><Button disabled={statusAction.busy || !userId || !reason.trim() || !confirmStatus} onPress={() => void statusAction.run({ action: 'account_status', userId, status, reason })}>{t('admin.updateStatus')}</Button><Button secondary disabled={statusAction.busy || !userId || !reason.trim() || !confirmStatus} onPress={() => void statusAction.run({ action: 'reset_usage', userId, reason })}>{t('admin.resetUsage')}</Button></View>
      <ActionFeedback message={statusAction.message} tone={statusAction.tone} />
    </Panel>
  </View>;
}

export function AdminStaffPanel({ profiles, assignments, reload }: { profiles: Row[]; assignments: Row[]; reload: () => Promise<void> }) {
  const { t } = useAppPreferences(); const action = useAction(reload);
  const [userId, setUserId] = useState(''), [role, setRole] = useState('developer'), [reason, setReason] = useState('');
  const [search, setSearch] = useState(''), [confirmAssign, setConfirmAssign] = useState(false), [confirmRevoke, setConfirmRevoke] = useState(false);
  const filteredProfiles = profiles.filter((row) => !search.trim() || [row.display_name, row.email, row.user_id].some((value) => id(value).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())));
  const selected = profiles.find((row) => id(row.user_id) === userId);
  const active = assignments.filter((row) => row.is_active === true && id(row.user_id) === userId);
  return <Panel style={styles.panel}>
    <Text style={styles.title}>{t('admin.staffManagement')}</Text><Text style={styles.help}>{t('admin.staffManagementHelp')}</Text>
    <View style={styles.grid}><View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.searchUsers')}</Text><Field accessibilityLabel={t('admin.searchUsers')} value={search} onChangeText={setSearch} /></View><View style={styles.field}><SelectField label={t('admin.account')} value={userId} options={[{ value: '', label: t('admin.chooseAccount') }, ...filteredProfiles.map((row) => ({ value: id(row.user_id), label: id(row.display_name || row.email || row.user_id) }))]} onChange={(value) => { setUserId(value); setConfirmAssign(false); setConfirmRevoke(false); action.clear(); }} /></View></View>
    {selected ? <><View style={styles.grid}><View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.role')}</Text><Text style={styles.help}>{t(`admin.value.${id(selected.role)}`)}</Text></View><View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.primaryRole')}</Text><Text style={styles.help}>{t(`admin.value.${id(selected.primary_role || selected.role)}`)}</Text></View><View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.activeStaffRoles')}</Text><Text style={styles.help}>{active.length ? active.map((row) => t(`admin.value.${id(row.role_key)}`)).join(', ') : t('admin.noStaffRole')}</Text></View></View>
      <Text style={styles.subheading}>{t('admin.assignStaff')}</Text><SelectField label={t('admin.role')} value={role} options={['developer', 'data_scientist'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={setRole} /><Field accessibilityLabel={t('admin.reason')} value={reason} onChangeText={setReason} placeholder={t('admin.reasonRequired')} /><ConfirmAction checked={confirmAssign} onChange={setConfirmAssign} label={t('admin.confirmStaffAssign')} /><View style={styles.actions}><Button disabled={action.busy || !reason.trim() || !confirmAssign} onPress={() => { void action.run({ action: 'staff_assign', userId, role, reason }); setConfirmAssign(false); }}>{t('admin.assignStaff')}</Button></View>
      {active.length ? <><Text style={styles.subheading}>{t('admin.activeStaffRoles')}</Text><ConfirmAction checked={confirmRevoke} onChange={setConfirmRevoke} label={t('admin.confirmStaffRevoke')} />{active.map((row) => <View key={id(row.id)} style={styles.assignment}><View><Text style={styles.assignmentLabel}>{t(`admin.value.${id(row.role_key)}`)}</Text><Text style={styles.help}>{id(row.assignment_reason)} · {id(row.assigned_at)}</Text></View><Button secondary disabled={action.busy || !reason.trim() || !confirmRevoke} onPress={() => { void action.run({ action: 'staff_revoke', assignmentId: row.id, reason }); setConfirmRevoke(false); }}>{t('admin.revokeStaff')}</Button></View>)}</> : null}</> : null}
    <ActionFeedback message={action.message} tone={action.tone} />
  </Panel>;
}

export function AdminPlanPanel({ plans, reload }: { plans: Row[]; reload: () => Promise<void> }) {
  const { t } = useAppPreferences();
  const [selected, setSelected] = useState(id(plans[0]?.id));
  const plan = selected === '__new__' ? { id: '', name: '', price: null, billing_interval: 'month', active: true, features_json: {}, limits_json: {} } : plans.find((row) => id(row.id) === selected) || plans[0];
  if (!plan) return null;
  return <AdminPlanEditor key={id(plan.id)} plan={plan} plans={plans} selected={selected} onSelect={setSelected} reload={reload} t={t} />;
}
function AdminPlanEditor({ plan, plans, selected, onSelect, reload, t }: { plan: Row; plans: Row[]; selected: string; onSelect: (value: string) => void; reload: () => Promise<void>; t: (key: string) => string }) {
  const action = useAction(reload);
  const [planId, setPlanId] = useState(id(plan.id)), [name, setName] = useState(id(plan.name)), [price, setPrice] = useState(plan.price == null ? '' : String(Number(plan.price) / 100));
  const baseUsdPrice = useRef(plan.price == null ? 0 : Number(plan.price) / 100);
  const [customPricing, setCustomPricing] = useState(plan.price == null);
  const [interval, setInterval] = useState(id(plan.billing_interval || 'month')), [active, setActive] = useState(plan.active !== false);
  const initialLimits = plan.limits_json && typeof plan.limits_json === 'object' ? plan.limits_json as Row : {};
  const [limits, setLimits] = useState<Record<string, string>>(Object.fromEntries(['ai_generations', 'pdf_exports', 'word_exports', 'students_count', 'classes_count'].map((key) => [key, id(initialLimits[key] || '0')])));
  const initialFeatures = plan.features_json && typeof plan.features_json === 'object' ? plan.features_json as Row : {};
  const [features, setFeatures] = useState<Record<string, boolean>>(Object.fromEntries(PLAN_FEATURE_KEYS.map((key) => [key, key in initialFeatures ? initialFeatures[key] === true : inferredPlanFeature(key, initialFeatures)])));
  const [premium, setPremium] = useState<Record<string, boolean>>(Object.fromEntries(PREMIUM_TOOL_CANDIDATES.map((key) => [key, inferredPremiumHighlight(key, initialFeatures)])));
  const [reason, setReason] = useState(''), [validation, setValidation] = useState(''), [confirmPlan, setConfirmPlan] = useState(false);
  const [previewCurrency, setPreviewCurrency] = useState('USD'), [previewRate, setPreviewRate] = useState<number | null>(1), [previewError, setPreviewError] = useState(false);
  useEffect(() => { const controller = new AbortController(); if (previewCurrency === 'USD') { setPrice(baseUsdPrice.current.toFixed(2)); setPreviewRate(1); return; } getAnalyticsExchangeRate('USD', previewCurrency, controller.signal).then((rate) => { if (!controller.signal.aborted) { setPrice((baseUsdPrice.current * rate).toFixed(2)); setPreviewRate(rate); setPreviewError(false); } }).catch(() => { if (!controller.signal.aborted) { setPreviewRate(null); setPreviewError(true); } }); return () => controller.abort(); }, [previewCurrency]);
  const changePrice = (value: string) => { setPrice(value); const amount = number(value); if (Number.isFinite(amount) && previewRate && previewRate > 0) baseUsdPrice.current = amount / previewRate; };
  const save = () => {
    if (!confirmPlan) { setValidation(t('admin.confirmPlanRequired')); return; }
    const amount = customPricing ? null : number(price);
    if (!planId.trim() || !name.trim() || (!customPricing && (!price.trim() || !previewRate || amount == null || !Number.isFinite(amount) || amount < 0)) || Object.values(limits).some((value) => !/^\d+$/.test(value.trim()))) { setValidation(t('admin.planInvalid')); return; }
    setValidation('');
    void action.run({ action: 'plan_save', reason, plan: { id: planId.trim(), name: name.trim(), price: amount == null ? null : Math.round(baseUsdPrice.current * 100), billing_interval: interval, active, features_json: { ...initialFeatures, ...features, premium_tool_highlights: PREMIUM_TOOL_CANDIDATES.filter((key) => premium[key]) }, limits_json: Object.fromEntries(Object.entries(limits).map(([key, value]) => [key, Number(value)])) } });
  };
  return <Panel style={styles.panel}><Text style={styles.title}>{t('admin.planEditor')}</Text><Text style={styles.help}>{t('admin.planEditorHelp')}</Text><SelectField label={t('admin.plan')} value={selected} options={[...plans.map((row) => ({ value: id(row.id), label: id(row.name || row.id) })), { value: '__new__', label: t('admin.newPlan') }]} onChange={onSelect} /><View style={styles.grid}><View style={styles.field}><Field accessibilityLabel={t('admin.planId')} value={planId} onChangeText={setPlanId} placeholder={t('admin.planId')} /></View><View style={styles.field}><Field accessibilityLabel={t('admin.planName')} value={name} onChangeText={setName} placeholder={t('admin.planName')} /></View><View style={styles.field}><SelectField label={t('admin.customPricing')} value={customPricing ? 'yes' : 'no'} options={yesNo(t)} onChange={(value) => setCustomPricing(value === 'yes')} /></View><View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.planPriceCurrency').replace('{currency}', previewCurrency)}</Text><Field accessibilityLabel={t('admin.planPriceCurrency').replace('{currency}', previewCurrency)} value={price} onChangeText={changePrice} keyboardType="decimal-pad" editable={!customPricing && previewRate != null} /></View><View style={styles.field}><SelectField label={t('admin.billingInterval')} value={interval} options={['month', 'year', 'lifetime', 'custom'].map((value) => ({ value, label: t(`admin.interval.${value}`) }))} onChange={setInterval} /></View><View style={styles.field}><SelectField label={t('admin.status')} value={active ? 'active' : 'inactive'} options={['active', 'inactive'].map((value) => ({ value, label: t(`admin.value.${value}`) }))} onChange={(value) => setActive(value === 'active')} /></View></View><View style={styles.grid}><View style={styles.field}><SelectField label={t('admin.previewCurrency')} value={previewCurrency} options={ANALYTICS_CURRENCIES.map((value) => ({ value, label: value }))} onChange={(value) => { setPreviewCurrency(value); setPreviewRate(value === 'USD' ? 1 : null); setPreviewError(false); }} /></View><View style={styles.field}><Text style={styles.fieldLabel}>{t('admin.pricePreview')}</Text><Text style={styles.previewAmount}>{customPricing ? t('admin.customPrice') : previewError ? t('admin.exchangeFailed') : previewRate == null ? t('admin.exchangeLoading') : `${previewCurrency} ${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`}</Text></View></View><View style={styles.planPreview}><Text style={styles.previewEyebrow}>{t('admin.livePreview')}</Text><Text style={styles.previewTitle}>{name.trim() || planId.trim() || t('admin.newPlan')}</Text><Text style={styles.previewAmount}>{!customPricing && price.trim() && previewRate != null ? `${previewCurrency} ${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : t('admin.customPrice')}</Text><Text style={styles.help}>{t(`admin.interval.${interval}`)} · {active ? t('admin.value.active') : t('admin.value.inactive')} · {Object.values(features).filter(Boolean).length} {t('admin.enabledFeatures')}</Text></View><Text style={styles.subheading}>{t('admin.planLimits')}</Text><View style={styles.grid}>{Object.entries(limits).map(([key, value]) => <View key={key} style={styles.field}><Text style={styles.fieldLabel}>{t(`admin.limit.${key}`)}</Text><Field accessibilityLabel={t(`admin.limit.${key}`)} value={value} onChangeText={(next) => setLimits((current) => ({ ...current, [key]: next }))} keyboardType="number-pad" /></View>)}</View><Text style={styles.subheading}>{t('admin.planFeatures')}</Text>{PLAN_FEATURE_GROUPS.map(([group, keys]) => <View key={group} style={styles.featureGroup}><Text style={styles.groupTitle}>{t(`admin.featureGroup.${group}`)}</Text><View style={styles.grid}>{keys.map((key) => <View key={key} style={styles.field}><SelectField label={t(`admin.feature.${key}`)} value={features[key] ? 'yes' : 'no'} options={[{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }]} onChange={(next) => setFeatures((current) => ({ ...current, [key]: next === 'yes' }))} /></View>)}</View></View>)}<Text style={styles.subheading}>{t('admin.premiumHighlights')}</Text><View style={styles.grid}>{PREMIUM_TOOL_CANDIDATES.map((key) => <View key={key} style={styles.field}><SelectField label={t(`admin.feature.${key}`)} value={premium[key] ? 'yes' : 'no'} options={[{ value: 'yes', label: t('admin.value.yes') }, { value: 'no', label: t('admin.value.no') }]} onChange={(next) => setPremium((current) => ({ ...current, [key]: next === 'yes' }))} /></View>)}</View><Field accessibilityLabel={t('admin.reason')} value={reason} onChangeText={setReason} placeholder={t('admin.reasonOptional')} /><ConfirmAction checked={confirmPlan} onChange={setConfirmPlan} label={t('admin.confirmPlan')} /><View style={styles.actions}><Button disabled={action.busy || !confirmPlan} onPress={save}>{t('admin.savePlan')}</Button></View>{validation ? <ActionFeedback message={validation} tone="error" /> : null}<ActionFeedback message={action.message} tone={action.tone} /></Panel>;
}

const styles = StyleSheet.create({ stack: { gap: 16 }, panel: { gap: 12 }, title: { color: colors.ink, fontSize: 18, fontWeight: '900' }, subheading: { color: colors.ink, fontSize: 14, fontWeight: '900', marginTop: 8 }, featureGroup: { gap: 8, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line }, groupTitle: { color: colors.primary, fontSize: 12, fontWeight: '900' }, previewAmount: { color: colors.primary, fontSize: 18, fontWeight: '900', marginTop: 8 }, planPreview: { borderWidth: 1, borderColor: colors.line, borderRadius: 14, backgroundColor: colors.surfaceSoft, padding: 16, gap: 4 }, previewEyebrow: { color: colors.primary, fontSize: 10, fontWeight: '900', letterSpacing: 1 }, previewTitle: { color: colors.ink, fontSize: 17, fontWeight: '900' }, help: { color: colors.muted, fontSize: 11, lineHeight: 17 }, grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 }, field: { flexGrow: 1, flexBasis: 220, minWidth: 180 }, fieldLabel: { color: colors.muted, fontSize: 10, fontWeight: '800', marginBottom: 5 }, actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, confirmRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 5 }, confirmMark: { color: colors.primary, fontSize: 20 }, confirmText: { color: colors.ink, fontSize: 11, lineHeight: 17, flexShrink: 1 }, assignment: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.line }, assignmentLabel: { color: colors.ink, fontSize: 12, fontWeight: '800' } });
