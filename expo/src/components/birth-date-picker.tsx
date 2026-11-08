import { createElement, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { SelectField } from '@/components/ui';
import { colors } from '@/theme';

export function validBirthDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  const today = new Date();
  return year >= 1900 && date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day
    && date.getTime() <= new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
}

type Props = { value: string; onChange: (value: string) => void; onIncompleteChange: (incomplete: boolean) => void; label: string; language: string; clearLabel: string; yearLabel: string; monthLabel: string; dayLabel: string };

export function BirthDatePicker({ value, onChange, onIncompleteChange, label, language, clearLabel, yearLabel, monthLabel, dayLabel }: Props) {
  const [partial, setPartial] = useState({ year: '', month: '', day: '' });
  const [year, month, day] = value ? value.split('-') : [partial.year, partial.month, partial.day];
  const today = new Date();
  const max = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  if (Platform.OS === 'web') return <View style={styles.webRow}>{createElement('input', {
    type: 'date', value, min: '1900-01-01', max, 'aria-label': label,
    onChange: (event: { target: { value: string } }) => { onIncompleteChange(false); onChange(event.target.value); },
    style: { boxSizing: 'border-box', width: '100%', minHeight: 48, padding: '0 14px', borderRadius: 12, border: `1px solid ${colors.line}`, backgroundColor: colors.surface, color: colors.ink, fontSize: 16 },
  })}{value ? <Pressable accessibilityRole="button" accessibilityLabel={clearLabel} onPress={() => { onIncompleteChange(false); onChange(''); }}><Text style={styles.clear}>{clearLabel}</Text></Pressable> : null}</View>;

  const update = (part: 'year' | 'month' | 'day', selected: string) => {
    const next = { year, month, day, [part]: selected };
    if (part !== 'day' && next.year && next.month && Number(next.day) > new Date(Number(next.year), Number(next.month), 0).getDate()) next.day = '';
    setPartial(next);
    const candidate = next.year && next.month && next.day ? `${next.year}-${next.month}-${next.day}` : '';
    onIncompleteChange(Boolean(next.year || next.month || next.day) && !validBirthDate(candidate));
    onChange(candidate && validBirthDate(candidate) ? candidate : '');
  };
  const yearOptions = Array.from({ length: today.getFullYear() - 1899 }, (_, index) => String(today.getFullYear() - index));
  const monthNames = Array.from({ length: 12 }, (_, index) => new Intl.DateTimeFormat(language, { month: 'long' }).format(new Date(2024, index, 1)));
  const days = year && month ? new Date(Number(year), Number(month), 0).getDate() : 31;
  return <View style={styles.nativeRow}>
    <View style={styles.nativeField}><SelectField label={dayLabel} value={day} onChange={(next) => update('day', next)} options={[{ value: '', label: dayLabel }, ...Array.from({ length: days }, (_, index) => ({ value: String(index + 1).padStart(2, '0'), label: String(index + 1) }))]} /></View>
    <View style={styles.nativeField}><SelectField label={monthLabel} value={month} onChange={(next) => update('month', next)} options={[{ value: '', label: monthLabel }, ...monthNames.map((name, index) => ({ value: String(index + 1).padStart(2, '0'), label: name }))]} /></View>
    <View style={styles.nativeField}><SelectField label={yearLabel} value={year} onChange={(next) => update('year', next)} options={[{ value: '', label: yearLabel }, ...yearOptions.map((item) => ({ value: item, label: item }))]} /></View>
    {year || month || day ? <Pressable accessibilityRole="button" accessibilityLabel={clearLabel} onPress={() => { setPartial({ year: '', month: '', day: '' }); onIncompleteChange(false); onChange(''); }}><Text style={styles.clear}>{clearLabel}</Text></Pressable> : null}
  </View>;
}

const styles = StyleSheet.create({ webRow: { gap: 4 }, nativeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, nativeField: { minWidth: 90, flexGrow: 1 }, clear: { color: colors.primary, fontSize: 12, fontWeight: '700', paddingVertical: 8 } });
