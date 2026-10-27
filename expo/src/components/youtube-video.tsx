import { StyleSheet, View } from 'react-native';
import { WebView } from 'react-native-webview';

export function YoutubeVideo({ videoId, title }: { videoId: string; title: string }) {
  return <View accessibilityLabel={title} style={styles.frame}>
    <WebView source={{ uri: `https://www.youtube-nocookie.com/embed/${videoId}?rel=0` }} allowsFullscreenVideo javaScriptEnabled domStorageEnabled style={styles.webview} />
  </View>;
}

const styles = StyleSheet.create({ frame: { width: '100%', aspectRatio: 16 / 9, overflow: 'hidden', borderRadius: 14 }, webview: { flex: 1 } });
