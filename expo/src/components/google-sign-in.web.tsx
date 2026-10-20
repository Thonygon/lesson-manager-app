import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/theme';

export function GoogleSignIn({ disabled, label, onPress }: { disabled: boolean; label: string; onPress: () => void }) {
  return <Pressable
    accessibilityRole="button"
    accessibilityLabel={label}
    disabled={disabled}
    onPress={onPress}
    style={({ pressed }) => [styles.button, (pressed || disabled) && styles.dimmed]}
  >
    <View style={styles.content}>
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 48 48" style={{ flexShrink: 0 }}>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.25 5.48-4.76 7.18l7.73 6C44.42 38.03 46.98 31.7 46.98 24.55z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24s.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.91-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.18 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
    <Text style={styles.label}>{label}</Text>
    </View>
  </Pressable>;
}

const styles = StyleSheet.create({
  button: { width: '100%', minHeight: 46, paddingHorizontal: 18, borderWidth: 1, borderColor: colors.line, borderRadius: 12, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  content: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  label: { color: colors.ink, fontSize: 15, fontWeight: '700', textAlign: 'center', flexShrink: 1 },
  dimmed: { opacity: 0.55 },
});
