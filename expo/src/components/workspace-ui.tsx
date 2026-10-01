import { StyleSheet, Text, View } from 'react-native';

import { Disclosure, EmptyState, Pagination } from '@/components/ui';
import { colors } from '@/theme';

export function KpiGrid({ items }: { items: { label: string; value: string | number; detail?: string }[] }) {
  return <View style={styles.kpiGrid}>{items.map((item) => <View key={item.label} style={styles.kpi}><Text style={styles.kpiLabel}>{item.label}</Text><Text style={styles.kpiValue}>{item.value}</Text>{item.detail ? <Text style={styles.detail}>{item.detail}</Text> : null}</View>)}</View>;
}

export function Bars({ rows, emptyTitle, emptyBody }: { rows: [string, number][]; emptyTitle: string; emptyBody: string }) {
  if (!rows.length) return <EmptyState title={emptyTitle} body={emptyBody} />;
  const max = Math.max(...rows.map((row) => row[1]), 1);
  return <View style={styles.bars}>{rows.map(([label, value]) => <View key={label} style={styles.barRow}><View style={styles.barLabels}><Text numberOfLines={1} style={styles.barLabel}>{label}</Text><Text style={styles.barValue}>{value}</Text></View><View style={styles.track}><View style={[styles.fill, { width: `${Math.max(2, value / max * 100)}%` }]} /></View></View>)}</View>;
}

export function RecordList({
  rows,
  page,
  pageSize = 12,
  onPageChange,
  title,
  emptyTitle,
  emptyBody,
  describe,
  fields,
}: {
  rows: Record<string, unknown>[];
  page: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
  title?: string;
  emptyTitle: string;
  emptyBody: string;
  describe: (row: Record<string, unknown>) => { title: string; summary?: string };
  fields: { key: string; label: string; format?: (value: unknown, row: Record<string, unknown>) => string }[];
}) {
  if (!rows.length) return <EmptyState title={emptyTitle} body={emptyBody} />;
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pages);
  const visible = rows.slice((safePage - 1) * pageSize, safePage * pageSize);
  return <View style={styles.list}>{title ? <Text style={styles.sectionTitle}>{title}</Text> : null}{visible.map((row, index) => {
    const description = describe(row);
    const key = String(row.id ?? row.run_id ?? row.job_id ?? row.user_id ?? `${safePage}-${index}`);
    return <Disclosure key={key} title={description.title} summary={description.summary}><View style={styles.fields}>{fields.map((field) => {
      const text = field.format ? field.format(row[field.key], row) : display(row[field.key]);
      return <View key={field.key} style={styles.fieldRow}><Text style={styles.fieldLabel}>{field.label}</Text><Text selectable style={styles.fieldValue}>{text}</Text></View>;
    })}</View></Disclosure>;
  })}<Pagination page={safePage} totalPages={pages} totalItems={rows.length} onPageChange={onPageChange} /></View>;
}

export function SectionHeading({ title, body }: { title: string; body?: string }) {
  return <View style={styles.heading}><Text style={styles.sectionTitle}>{title}</Text>{body ? <Text style={styles.detail}>{body}</Text> : null}</View>;
}

export function WarningBox({ warnings, title }: { warnings: string[]; title: string }) {
  if (!warnings.length) return null;
  return <Disclosure title={title} summary={`${warnings.length}`}><View style={styles.fields}>{warnings.map((warning) => <Text selectable key={warning} style={styles.warning}>• {warning}</Text>)}</View></Disclosure>;
}

export function display(value: unknown) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? '✓' : '—';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

export function dateLabel(value: unknown) {
  if (!value) return '—';
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export function groupCount(rows: Record<string, unknown>[], field: string): [string, number][] {
  const grouped = new Map<string, number>();
  rows.forEach((row) => {
    const key = String(row[field] || 'Unspecified');
    grouped.set(key, (grouped.get(key) ?? 0) + 1);
  });
  return Array.from(grouped.entries()).sort((a, b) => b[1] - a[1]);
}

const styles = StyleSheet.create({
  kpiGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  kpi: { minWidth: 150, flexGrow: 1, flexBasis: 180, borderWidth: 1, borderColor: colors.line, borderRadius: 16, backgroundColor: colors.surface, padding: 18 },
  kpiLabel: { color: colors.muted, fontSize: 11, fontWeight: '800', letterSpacing: 0.4, textTransform: 'uppercase' },
  kpiValue: { color: colors.ink, fontSize: 28, fontWeight: '900', marginTop: 7 },
  detail: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: 5 },
  bars: { gap: 14 }, barRow: { gap: 6 }, barLabels: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 }, barLabel: { color: colors.ink, flex: 1, fontSize: 13, fontWeight: '700' }, barValue: { color: colors.muted, fontSize: 12, fontWeight: '800' }, track: { height: 8, borderRadius: 8, backgroundColor: colors.primarySoft, overflow: 'hidden' }, fill: { height: 8, borderRadius: 8, backgroundColor: colors.primary },
  list: { gap: 10 },
  heading: { gap: 3 }, sectionTitle: { color: colors.ink, fontSize: 19, fontWeight: '800' },
  fields: { gap: 10 }, fieldRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 14, paddingBottom: 9, borderBottomWidth: 1, borderBottomColor: colors.line }, fieldLabel: { width: 135, color: colors.muted, fontSize: 11, fontWeight: '800', textTransform: 'uppercase' }, fieldValue: { flex: 1, color: colors.ink, fontSize: 13, lineHeight: 19 },
  warning: { color: colors.warning, fontSize: 12, lineHeight: 18 },
});
