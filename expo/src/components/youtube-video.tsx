import { StyleSheet, Text, View } from 'react-native';
import { WebView } from 'react-native-webview';
import { useYoutubeAvailability } from '@/lib/youtube-availability';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

export function YoutubeVideo({ videoId, title }: { videoId: string; title: string }) {
  const { t } = useAppPreferences();
  const availability = useYoutubeAvailability(videoId);
  if (availability === 'unavailable') return <View accessibilityRole="alert" style={styles.unavailable}><Text style={styles.unavailableText}>{t('resources.youtubeNoLongerAvailable')}</Text></View>;
  return <View accessibilityLabel={title} style={styles.frame}>
    <WebView source={{ uri: `https://www.youtube-nocookie.com/embed/${videoId}?rel=0` }} allowsFullscreenVideo javaScriptEnabled domStorageEnabled style={styles.webview} />
  </View>;
}

const styles = StyleSheet.create({ frame: { width: '100%', aspectRatio: 16 / 9, overflow: 'hidden', borderRadius: 14 }, webview: { flex: 1 }, unavailable: { padding: 20, borderRadius: 14, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surfaceSoft }, unavailableText: { color: colors.ink, lineHeight: 22 } });
