import { createElement } from 'react';
import { Platform } from 'react-native';

import { Field } from '@/components/ui';
import { colors } from '@/theme';

export function CalendarInput({ kind, label, value, onChange }: { kind: 'date' | 'time' | 'datetime-local'; label: string; value: string; onChange: (value: string) => void }) {
  if (Platform.OS !== 'web') return <Field accessibilityLabel={label} value={value} onChangeText={onChange} placeholder={kind === 'time' ? 'HH:MM' : kind === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DDTHH:MM'} />;
  return createElement('input', {
    type: kind,
    'aria-label': label,
    value,
    onChange: (event: { target: { value: string } }) => onChange(event.target.value),
    style: { width: '100%', minHeight: 48, boxSizing: 'border-box', border: `1px solid ${colors.line}`, borderRadius: 12, background: colors.surface, color: colors.ink, padding: '10px 14px', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif', fontSize: 16, fontWeight: 500, outlineColor: colors.primary, colorScheme: 'dark light' },
  });
}
