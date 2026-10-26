import { createElement } from 'react';
import { StyleSheet, View } from 'react-native';

export function YoutubeVideo({ videoId, title }: { videoId: string; title: string }) {
  return <View style={styles.frame}>
    {createElement('iframe', { title, src: `https://www.youtube-nocookie.com/embed/${videoId}?rel=0`, allow: 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share', allowFullScreen: true, loading: 'lazy', referrerPolicy: 'strict-origin-when-cross-origin', style: { width: '100%', height: '100%', border: 0 } })}
  </View>;
}

const styles = StyleSheet.create({ frame: { width: '100%', aspectRatio: 16 / 9, overflow: 'hidden', borderRadius: 14 } });
