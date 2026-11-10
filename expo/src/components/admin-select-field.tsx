import type { ComponentProps } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { HelpIcon, SelectField } from '@/components/ui';
import { colors } from '@/theme';

/** Administrative forms need persistent labels: a selected value is not a label. */
export function AdminSelectField({ info, ...props }: ComponentProps<typeof SelectField> & { info?: string }) {
  return <View style={styles.wrap}>
    <View style={styles.heading}><Text style={styles.label}>{props.label}</Text>{info ? <HelpIcon title={props.label}>{info}</HelpIcon> : null}</View>
    <SelectField {...props} />
  </View>;
}

const styles = StyleSheet.create({
  wrap: { gap: 5 },
  heading: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  label: { color: colors.muted, fontSize: 11, fontWeight: '800' },
});
