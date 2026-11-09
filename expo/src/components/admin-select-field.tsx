import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { SelectField } from '@/components/ui';
import { colors } from '@/theme';

/** Administrative forms need persistent labels: a selected value is not a label. */
export function AdminSelectField(props: ComponentProps<typeof SelectField>) {
  return <View style={styles.wrap}>
    <Text style={styles.label}>{props.label}</Text>
    <SelectField {...props} />
  </View>;
}

const styles = StyleSheet.create({
  wrap: { gap: 5 },
  label: { color: colors.muted, fontSize: 11, fontWeight: '800' },
});
