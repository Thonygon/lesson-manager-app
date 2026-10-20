import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { Field, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

type Facet = {
  key: string;
  label: string;
  value: string;
  allValue: string;
  allLabel: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
};

export function ResourceFilters({ query, onQueryChange, facets, count, searchLabel, searchPlaceholder }: {
  query: string;
  onQueryChange: (value: string) => void;
  facets: Facet[];
  count?: number;
  searchLabel?: string;
  searchPlaceholder?: string;
}) {
  const { t } = useAppPreferences();
  const narrow = useWindowDimensions().width < 560;
  return <View style={styles.wrap}>
    <View style={styles.searchRow}>
      <Field accessibilityLabel={searchLabel || t('resources.search')} placeholder={searchPlaceholder || t('resources.searchPlaceholder')} value={query} onChangeText={onQueryChange} style={[styles.searchField, narrow && styles.searchFieldNarrow]} />
      {typeof count === 'number' ? <Text style={styles.resultCount}>{t('resources.resultCount', { count })}</Text> : null}
    </View>
    <View style={styles.filterGrid}>{facets.map((facet) => <View key={facet.key} style={styles.filterCell}>
      <Text style={styles.filterLabel}>{facet.label}</Text>
      <SelectField label={facet.label} value={facet.value} options={[{ value: facet.allValue, label: facet.allLabel }, ...facet.options]} onChange={facet.onChange} />
    </View>)}</View>
  </View>;
}

const styles = StyleSheet.create({
  wrap: { marginTop: 12, marginBottom: 12 },
  searchRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 },
  searchField: { flex: 1, minWidth: 240 },
  searchFieldNarrow: { flexGrow: 0, flexShrink: 0, flexBasis: 'auto', width: '100%', minWidth: 0 },
  resultCount: { color: colors.muted, fontSize: 11, fontWeight: '800' },
  filterGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 12 },
  filterCell: { flex: 1, minWidth: 190, gap: 5 },
  filterLabel: { color: colors.ink, fontSize: 10, fontWeight: '800' },
});
