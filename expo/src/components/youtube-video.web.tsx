import { createElement } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useYoutubeAvailability } from '@/lib/youtube-availability';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

export function YoutubeVideo({ videoId, title }: { videoId: string; title: string }) {
  const { t } = useAppPreferences();
  const availability = useYoutubeAvailability(videoId);
  if (availability === 'unavailable') return <View accessibilityRole="alert" style={styles.unavailable}><Text style={styles.unavailableText}>{t('resources.youtubeNoLongerAvailable')}</Text></View>;
  return <View style={styles.frame}>
    {createElement('iframe', { title, src: `https://www.youtube-nocookie.com/embed/${videoId}?rel=0`, allow: 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; web-share', allowFullScreen: true, loading: 'lazy', referrerPolicy: 'strict-origin-when-cross-origin', style: { width: '100%', height: '100%', border: 0 } })}
  </View>;
}

const styles = StyleSheet.create({ frame: { width: '100%', aspectRatio: 16 / 9, overflow: 'hidden', borderRadius: 14 }, unavailable: { padding: 20, borderRadius: 14, borderWidth: 1, borderColor: colors.lineStrong, backgroundColor: colors.surfaceSoft }, unavailableText: { color: colors.ink, lineHeight: 22 } });
