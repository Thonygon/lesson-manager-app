import { Pressable, StyleSheet, Text } from 'react-native';

import { colors } from '@/theme';

export function BackLink({ label, onPress }: { label: string; onPress: () => void }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress} style={styles.link}>
    <Text style={styles.text}>← {label}</Text>
  </Pressable>;
}

const styles = StyleSheet.create({
  link: { alignSelf: 'flex-start', marginBottom: 18 },
  text: { color: colors.primary, fontSize: 13, fontWeight: '800' },
});
