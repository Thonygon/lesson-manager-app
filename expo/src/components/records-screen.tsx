import { StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { Button, EmptyState, LoadingState, Panel } from '@/components/ui';
import { useRecords } from '@/hooks/use-records';
import type { ClassioRecord, ListKey } from '@/services/classio-data';
import { colors } from '@/theme';

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  const text = String(value);
  return /^\d{4}-\d\d-\d\d/.test(text) ? new Date(text).toLocaleDateString() : text;
}

function RecordRow({ record }: { record: ClassioRecord }) {
  const entries = Object.entries(record).filter(([key]) => key !== 'id').slice(0, 5);
  return (
    <Panel style={styles.row}>
      {entries.map(([key, value], index) => (
        <View key={key} style={[styles.cell, index === 0 && styles.primaryCell]}>
          <Text style={styles.label}>{key.replaceAll('_', ' ')}</Text>
          <Text numberOfLines={2} style={[styles.value, index === 0 && styles.primaryValue]}>{displayValue(value)}</Text>
        </View>
      ))}
    </Panel>
  );
}

export function RecordsScreen({ listKey, title, description }: { listKey: ListKey; title: string; description: string }) {
  const { records, loading, error, refresh } = useRecords(listKey);
  return (
    <AppShell title={title} eyebrow="CLASSIO WORKSPACE">
      <Text style={styles.description}>{description}</Text>
      {loading ? <LoadingState /> : error ? (
        <EmptyState title="This view could not be loaded" body={`${error} Check this table's Row Level Security policy before production.`} action={<Button onPress={() => void refresh()}>Try again</Button>} />
      ) : records.length === 0 ? (
        <EmptyState title={`No ${title.toLowerCase()} yet`} body="This live view is connected and the current account has no visible records." />
      ) : (
        <View style={styles.list}>{records.map((record, index) => <RecordRow key={String(record.id ?? index)} record={record} />)}</View>
      )}
    </AppShell>
  );
}

const styles = StyleSheet.create({
  description: { color: colors.muted, fontSize: 16, lineHeight: 24, marginBottom: 22, maxWidth: 720 },
  list: { gap: 10 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, paddingVertical: 15 },
  cell: { minWidth: 110, flex: 1 },
  primaryCell: { minWidth: 190, flex: 1.5 },
  label: { color: colors.subtle, fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 5 },
  value: { color: colors.muted, fontSize: 14, lineHeight: 19 },
  primaryValue: { color: colors.ink, fontWeight: '700' },
});

