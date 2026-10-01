import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Disclosure, Field } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

type PathPart = string | number;
type EditableField = { path: PathPart[]; kind: 'scalar' | 'list'; value: string; original: unknown };

const SKIP_KEYS = new Set(['visual_support', 'visual_supports', '_visual_support_status', 'cover_image', 'avatar_url', 'image_url', 'image', 'text_blocks', 'text_kind']);
const isScalar = (value: unknown) => value === null || ['string', 'number', 'boolean'].includes(typeof value);

function collectFields(value: unknown, path: PathPart[] = []): EditableField[] {
  if (path.length && SKIP_KEYS.has(String(path[path.length - 1]))) return [];
  if (Array.isArray(value)) {
    if (value.every(isScalar)) return [{ path, kind: 'list', value: value.filter((item) => String(item ?? '').trim()).map(String).join('\n'), original: value }];
    return value.flatMap((item, index) => collectFields(item, [...path, index]));
  }
  if (value && typeof value === 'object') return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => collectFields(child, [...path, key]));
  return path.length ? [{ path, kind: 'scalar', value: value === null || value === undefined ? '' : String(value), original: value }] : [];
}

function setAtPath(root: Record<string, unknown>, field: EditableField, raw: string) {
  let parent: any = root;
  field.path.slice(0, -1).forEach((part) => { parent = parent[part]; });
  const key = field.path[field.path.length - 1];
  let value: unknown = raw;
  if (field.kind === 'list') value = raw.split('\n').map((line) => line.trim()).filter(Boolean);
  else if (typeof field.original === 'boolean') value = ['1', 'true', 'yes', 'on'].includes(raw.trim().toLocaleLowerCase());
  else if (typeof field.original === 'number') value = Number.isFinite(Number(raw)) ? Number(raw) : field.original;
  else if (field.original === null && !raw.trim()) value = null;
  parent[key] = value;
}

function pathLabel(path: PathPart[]) {
  return path.map((part) => typeof part === 'number' ? String(part + 1) : part.replaceAll('_', ' ')).join(' › ');
}

export function ResourceEditor({ document, onApply }: { document: Record<string, unknown>; onApply: (document: Record<string, unknown>) => void }) {
  const { t } = useAppPreferences();
  const fields = useMemo(() => collectFields(document), [document]);
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(fields.map((field) => [JSON.stringify(field.path), field.value])));
  const apply = () => {
    const updated = JSON.parse(JSON.stringify(document)) as Record<string, unknown>;
    fields.forEach((field) => setAtPath(updated, field, values[JSON.stringify(field.path)] ?? field.value));
    onApply(updated);
  };
  return <Disclosure title={t('smart.editorTitle')} summary={t('smart.editorHelp')} style={styles.editor}>
    <View style={styles.fields}>{fields.map((field) => { const key = JSON.stringify(field.path); const multiline = field.kind === 'list' || String(field.original ?? '').length > 80; return <View key={key} style={styles.field}><Text style={styles.label}>{pathLabel(field.path)}</Text><Field value={values[key] ?? field.value} onChangeText={(value) => setValues((current) => ({ ...current, [key]: value }))} multiline={multiline} numberOfLines={multiline ? 4 : 1} style={multiline ? styles.multiline : undefined} /></View>; })}</View>
    <View style={styles.action}><Button onPress={apply}>{t('smart.applyEdits')}</Button></View>
  </Disclosure>;
}

const styles = StyleSheet.create({ editor: { marginTop: 12 }, fields: { gap: 10 }, field: { gap: 5 }, label: { color: colors.muted, fontSize: 10, fontWeight: '800', textTransform: 'capitalize' }, multiline: { minHeight: 92, paddingTop: 12, textAlignVertical: 'top' }, action: { alignSelf: 'flex-start', marginTop: 14 } });
