import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Field, SelectField } from '@/components/ui';
import { RecordList } from '@/components/workspace-ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

type Row = Record<string, unknown>;
type Props = {
  rows: Row[];
  title?: string;
  emptyTitle: string;
  emptyBody: string;
  describe: (row: Row) => { title: string; summary?: string };
  fields: { key: string; label: string; format?: (value: unknown, row: Row) => string }[];
  filterKey: string;
  filterLabel: string;
  filterValueLabel?: (value: string) => string;
  searchKeys?: string[];
};

const raw = (value: unknown) => value == null ? '' : String(value);

export function PrivilegedRecordList({ rows, title, emptyTitle, emptyBody, describe, fields, filterKey, filterLabel, filterValueLabel, searchKeys }: Props) {
  const { t } = useAppPreferences();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const options = useMemo(() => [...new Set(rows.map((row) => raw(row[filterKey]).trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b)), [rows, filterKey]);
  const selectedFilter = filter === 'all' || options.includes(filter) ? filter : 'all';
  const optionLabel = (value: string) => { const key = `admin.value.${value.toLocaleLowerCase()}`; const translated = t(key); return filterValueLabel?.(value) || (translated === key ? value.replaceAll('_', ' ') : translated); };
  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return rows.filter((row) => (selectedFilter === 'all' || raw(row[filterKey]) === selectedFilter) && (!needle || (searchKeys?.length ? searchKeys.map((key) => row[key]) : Object.values(row)).some((value) => value != null && typeof value !== 'object' && raw(value).toLocaleLowerCase().includes(needle))));
  }, [rows, selectedFilter, search, searchKeys, filterKey]);
  return <View style={styles.stack}>
    <View style={styles.filters}>
      <View style={styles.search}><Field accessibilityLabel={`${t('common.search')} ${title || emptyTitle}`} placeholder={t('common.search')} value={search} onChangeText={(value) => { setSearch(value); setPage(1); }} /></View>
      <View style={styles.filter}><SelectField label={filterLabel} value={selectedFilter} options={[{ value: 'all', label: t('common.all') }, ...options.map((value) => ({ value, label: optionLabel(value) }))]} onChange={(value) => { setFilter(value); setPage(1); }} /></View>
    </View>
    <Text style={styles.count}>{t('admin.resultCount', { count: filtered.length })}</Text>
    <RecordList rows={filtered} page={page} pageSize={18} onPageChange={setPage} title={title} emptyTitle={emptyTitle} emptyBody={emptyBody} describe={describe} fields={fields} />
  </View>;
}

const styles = StyleSheet.create({ stack: { gap: 10 }, filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 }, search: { flexGrow: 2, flexBasis: 220 }, filter: { flexGrow: 1, flexBasis: 170 }, count: { color: colors.muted, fontSize: 11, fontWeight: '700' } });
