import { useMemo, useState } from 'react';
import { View } from 'react-native';

import { Field, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';

type StudentOption = { value: string; label: string; detail?: string };

export function StudentSearchSelect({ label, value, options, placeholder, help, onChange }: {
  label: string;
  value: string;
  options: StudentOption[];
  placeholder?: string;
  help?: string;
  onChange: (value: string) => void;
}) {
  const { t } = useAppPreferences();
  const [search, setSearch] = useState('');
  const visibleOptions = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    return needle ? options.filter((option) => `${option.label} ${option.detail || ''}`.toLocaleLowerCase().includes(needle)) : options;
  }, [options, search]);
  const selectedValue = visibleOptions.some((option) => option.value === value) ? value : search.trim() ? visibleOptions[0]?.value || '' : '';
  const updateSearch = (next: string) => {
    setSearch(next);
    const needle = next.trim().toLocaleLowerCase();
    if (!needle) return;
    const matches = options.filter((option) => `${option.label} ${option.detail || ''}`.toLocaleLowerCase().includes(needle));
    const nextValue = matches.some((option) => option.value === value) ? value : matches[0]?.value || '';
    if (nextValue !== value) onChange(nextValue);
  };

  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: 10 }}>
    <View style={{ flex: 1, minWidth: 220 }}><Field accessibilityLabel={t('dashboard.searchStudents')} placeholder={t('dashboard.searchStudents')} value={search} onChangeText={updateSearch} /></View>
    <View style={{ flex: 1, minWidth: 220 }}><SelectField label={label} value={selectedValue} options={visibleOptions} placeholder={placeholder} help={help} onChange={onChange} /></View>
  </View>;
}
