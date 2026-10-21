import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ActionFeedback, Button, Disclosure, Field, LoadingState, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { deletePricingItem, getPricingItems, type PricingItem, savePricingItem } from '@/services/classio-data';
import { colors } from '@/theme';

const CURRENCIES = ['TRY', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'CHF', 'JPY', 'BRL', 'MXN'];
type Modality = 'online' | 'offline';

function PricingSection({ modality, items, busy, onChanged }: { modality: Modality; items: PricingItem[]; busy: boolean; onChanged: (message: string) => Promise<void> }) {
  const { t } = useAppPreferences();
  const hourly = items.find((item) => item.modality === modality && item.kind === 'hourly');
  const packages = useMemo(() => items.filter((item) => item.modality === modality && item.kind === 'package').sort((a, b) => Number(a.hours || 0) - Number(b.hours || 0)), [items, modality]);
  const [hourlyPrice, setHourlyPrice] = useState(String(hourly?.price || 0));
  const [hourlyCurrency, setHourlyCurrency] = useState(hourly?.currency || 'TRY');
  const [editingId, setEditingId] = useState<string | number | null>(null);
  const [editHours, setEditHours] = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editCurrency, setEditCurrency] = useState('TRY');
  const [addHours, setAddHours] = useState('10');
  const [addPrice, setAddPrice] = useState('0');
  const [addCurrency, setAddCurrency] = useState('TRY');

  // Saved price changes replace the local edit fields.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setHourlyPrice(String(hourly?.price || 0)); setHourlyCurrency(hourly?.currency || 'TRY'); }, [hourly?.id, hourly?.price, hourly?.currency]);

  const validNumber = (value: string, minimum: number) => Number.isFinite(Number(value)) && Number(value) >= minimum;
  const saveHourly = async () => {
    if (!validNumber(hourlyPrice, 0)) return;
    await savePricingItem({ id: hourly?.id, modality, kind: 'hourly', hours: null, price: Number(hourlyPrice), currency: hourlyCurrency, active: true, sort_order: 0 });
    await onChanged(t('pricing.hourlySaved'));
  };
  const startEdit = (item: PricingItem) => { setEditingId(item.id ?? null); setEditHours(String(item.hours || 1)); setEditPrice(String(item.price || 0)); setEditCurrency(item.currency || 'TRY'); };
  const savePackage = async (item: PricingItem) => {
    if (!validNumber(editHours, 1) || !validNumber(editPrice, 0)) return;
    await savePricingItem({ ...item, hours: Number(editHours), price: Number(editPrice), currency: editCurrency });
    setEditingId(null); await onChanged(t('pricing.packageSaved'));
  };
  const addPackage = async () => {
    if (!validNumber(addHours, 1) || !validNumber(addPrice, 0)) return;
    await savePricingItem({ modality, kind: 'package', hours: Number(addHours), price: Number(addPrice), currency: addCurrency, active: true, sort_order: Number(addHours) });
    setAddHours('10'); setAddPrice('0'); await onChanged(t('pricing.packageAdded'));
  };

  return <View style={styles.section}>
    <Text style={styles.sectionTitle}>{modality === 'online' ? t('pricing.online') : t('pricing.offline')}</Text>
    <Text style={styles.caption}>{t('pricing.hourly')}</Text>
    <View style={styles.fieldRow}><View style={styles.currency}><SelectField label={t('pricing.currency')} value={hourlyCurrency} options={CURRENCIES.map((value) => ({ value, label: value }))} onChange={setHourlyCurrency} /></View><Field accessibilityLabel={t('pricing.price')} keyboardType="numeric" value={hourlyPrice} onChangeText={setHourlyPrice} style={styles.numberField} /><Button secondary disabled={busy || !validNumber(hourlyPrice, 0)} onPress={() => void saveHourly()}>{t('common.save')}</Button></View>
    <View style={styles.divider} />
    {!packages.length ? <Text style={styles.empty}>{t('pricing.noPackages')}</Text> : packages.map((item) => {
      const isEditing = editingId === item.id; const hours = Number(item.hours || 0); const perHour = hours ? Math.round(item.price / hours) : 0;
      return <Panel key={String(item.id)} style={styles.packageCard}><View style={styles.packageHeader}><View style={styles.packageCopy}><Text style={styles.packageTitle}>{hours} {t('pricing.hours')}</Text><Text style={styles.packageMeta}>≈ {item.currency} {perHour.toLocaleString()} {t('pricing.perHour')}</Text></View><Text style={styles.packagePrice}>{item.currency} {item.price.toLocaleString()}</Text><Button secondary onPress={() => isEditing ? setEditingId(null) : startEdit(item)}>{isEditing ? t('common.cancel') : t('common.edit')}</Button></View>{isEditing ? <View style={styles.editRow}><Field accessibilityLabel={t('pricing.hours')} keyboardType="numeric" value={editHours} onChangeText={setEditHours} style={styles.editField} /><View style={styles.editCurrency}><SelectField label={t('pricing.currency')} value={editCurrency} options={CURRENCIES.map((value) => ({ value, label: value }))} onChange={setEditCurrency} /></View><Field accessibilityLabel={t('pricing.price')} keyboardType="numeric" value={editPrice} onChangeText={setEditPrice} style={styles.editField} /><Button disabled={busy || !validNumber(editHours, 1) || !validNumber(editPrice, 0)} onPress={() => void savePackage(item)}>{t('common.save')}</Button><Button secondary disabled={busy} onPress={() => void deletePricingItem(item.id!).then(() => onChanged(t('pricing.packageDeleted')))}>{t('common.delete')}</Button></View> : null}</Panel>;
    })}
    <Text style={styles.addTitle}>{t('pricing.addPackage')}</Text>
    <View style={styles.editRow}><Field accessibilityLabel={t('pricing.hours')} keyboardType="numeric" value={addHours} onChangeText={setAddHours} style={styles.editField} /><View style={styles.editCurrency}><SelectField label={t('pricing.currency')} value={addCurrency} options={CURRENCIES.map((value) => ({ value, label: value }))} onChange={setAddCurrency} /></View><Field accessibilityLabel={t('pricing.price')} keyboardType="numeric" value={addPrice} onChangeText={setAddPrice} style={styles.editField} /><Button disabled={busy || !validNumber(addHours, 1) || !validNumber(addPrice, 0)} onPress={() => void addPackage()}>{t('pricing.add')}</Button></View>
  </View>;
}

export function PricingEditor() {
  const { t } = useAppPreferences(); const [items, setItems] = useState<PricingItem[]>([]); const [loading, setLoading] = useState(false); const [busy, setBusy] = useState(false); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'success' | 'error'>('error');
  const load = async () => { setLoading(true); try { setItems(await getPricingItems()); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('pricing.loadFailed')); } finally { setLoading(false); } };
  // Load the editor data on mount through the shared refresh function.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, []);
  const changed = async (nextMessage: string) => { setBusy(true); try { setItems(await getPricingItems()); setMessageTone('success'); setMessage(nextMessage); } catch (reason) { setMessageTone('error'); setMessage(reason instanceof Error ? reason.message : t('pricing.saveFailed')); } finally { setBusy(false); } };
  const hasPrice = items.some((item) => item.price > 0);
  return <Disclosure title={t('pricing.title')} summary={t('pricing.summary')} style={styles.disclosure}>{loading ? <LoadingState /> : <View style={styles.editor}>{!hasPrice ? <Text style={styles.hint}>⚠️ {t('pricing.hint')}</Text> : null}<PricingSection modality="online" items={items} busy={busy} onChanged={changed} /><View style={styles.bigDivider} /><PricingSection modality="offline" items={items} busy={busy} onChanged={changed} /><ActionFeedback message={message} tone={messageTone} /></View>}</Disclosure>;
}

const styles = StyleSheet.create({
  disclosure: { marginBottom: 16 }, editor: { gap: 12 }, section: { gap: 10 }, sectionTitle: { color: colors.ink, fontSize: 18, fontWeight: '900' }, caption: { color: colors.muted, fontSize: 12 }, fieldRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'flex-start' }, currency: { minWidth: 125, flex: 1 }, numberField: { minWidth: 130, flex: 1 }, divider: { height: 1, backgroundColor: colors.line, marginVertical: 4 }, bigDivider: { height: 1, backgroundColor: colors.lineStrong, marginVertical: 6 }, empty: { color: colors.muted, fontSize: 12 }, packageCard: { padding: 12, borderRadius: 12 }, packageHeader: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 }, packageCopy: { minWidth: 130, flex: 1 }, packageTitle: { color: colors.ink, fontSize: 14, fontWeight: '900' }, packageMeta: { color: colors.muted, fontSize: 10, marginTop: 2 }, packagePrice: { color: colors.ink, fontSize: 15, fontWeight: '900' }, editRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'flex-start', marginTop: 9 }, editField: { minWidth: 100, flex: 1 }, editCurrency: { minWidth: 115, flex: 1 }, addTitle: { color: colors.ink, fontSize: 13, fontWeight: '900', marginTop: 5 }, message: { color: colors.primary, backgroundColor: colors.primarySoft, borderRadius: 10, padding: 10, fontSize: 11, fontWeight: '800' }, hint: { color: colors.warning, backgroundColor: colors.warningSoft, borderRadius: 10, padding: 10, fontSize: 11, fontWeight: '700' },
});
