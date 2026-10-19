import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { EmptyState } from '@/components/ui';
import { colors } from '@/theme';

export function AdminBars({ rows, emptyTitle, emptyBody }: { rows: [string, number][]; emptyTitle: string; emptyBody: string }) {
  if (!rows.length) return <EmptyState title={emptyTitle} body={emptyBody} />;
  const max = Math.max(1, ...rows.map((row) => row[1]));
  return <View style={styles.bars}>{rows.slice(0, 12).map(([label, value], index) => <View key={label} style={styles.row}><View style={styles.labels}><Text numberOfLines={1} style={styles.label}>{label}</Text><Text style={styles.value}>{value.toLocaleString()}</Text></View><View style={styles.track}><View style={[styles.fill, { width: `${value <= 0 ? 0 : Math.max(2, value / max * 100)}%`, backgroundColor: index === 0 ? colors.primary : index % 2 ? colors.violet : colors.success }]} /></View></View>)}</View>;
}

export function AdminTrend({ rows, emptyTitle, emptyBody }: { rows: [string, number][]; emptyTitle: string; emptyBody: string }) {
  if (!rows.length) return <EmptyState title={emptyTitle} body={emptyBody} />;
  const max = Math.max(1, ...rows.map((row) => row[1]));
  return <ScrollView horizontal showsHorizontalScrollIndicator={false}><View style={[styles.trend, { width: Math.max(340, rows.length * 48) }]}>{rows.map(([label, value], index) => <View key={label} style={styles.trendItem}><Text style={styles.trendValue}>{value}</Text><View style={styles.column}><View style={[styles.columnFill, { height: `${Math.max(3, value / max * 100)}%`, backgroundColor: index === rows.length - 1 ? colors.primary : colors.violet }]} /></View><Text style={styles.trendLabel}>{label}</Text></View>)}</View></ScrollView>;
}

const styles = StyleSheet.create({
  bars: { gap: 14, marginTop: 18 }, row: { gap: 6 }, labels: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 }, label: { color: colors.ink, fontSize: 12, fontWeight: '800', flex: 1 }, value: { color: colors.muted, fontSize: 11, fontWeight: '900' }, track: { height: 9, borderRadius: 9, backgroundColor: colors.primarySoft, overflow: 'hidden' }, fill: { height: '100%', borderRadius: 9 },
  trend: { flexDirection: 'row', alignItems: 'flex-end', gap: 9, minHeight: 190, marginTop: 16 }, trendItem: { flex: 1, minWidth: 27, alignItems: 'center', gap: 6 }, trendValue: { color: colors.ink, fontSize: 10, fontWeight: '900' }, column: { height: 135, width: '100%', justifyContent: 'flex-end', backgroundColor: colors.primarySoft, borderRadius: 8, overflow: 'hidden' }, columnFill: { width: '100%', borderRadius: 8 }, trendLabel: { color: colors.muted, fontSize: 9, textAlign: 'center' },
});
