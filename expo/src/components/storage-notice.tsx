import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { STORAGE_NOTICE_VERSION, storageNoticeUrl } from '@/lib/privacy-notices';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

const KEY = 'classio.storageNoticeSeen';

export function StorageNotice() {
  const { language, resolvedTheme, t } = useAppPreferences();
  const dark = resolvedTheme === 'dark';
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let active = true;
    void AsyncStorage.getItem(KEY).then((seen) => {
      if (active) setVisible(seen !== STORAGE_NOTICE_VERSION);
    }).catch(() => { if (active) setVisible(true); });
    return () => { active = false; };
  }, []);

  if (!visible) return null;

  const dismiss = () => {
    setVisible(false);
    // This records notice display, never consent. Essential storage is already in use.
    void AsyncStorage.setItem(KEY, STORAGE_NOTICE_VERSION).catch(() => undefined);
  };

  return <View pointerEvents="box-none" style={styles.position}>
    <View nativeID="classio-storage-notice-card" accessibilityLiveRegion="polite" style={[styles.banner, dark && styles.bannerDark]}>
      <Text style={[styles.message, dark && styles.messageDark]}>{t('legal.storageNotice')}</Text>
      <View style={styles.actions}>
        <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(storageNoticeUrl(language))}><Text style={[styles.link, dark && styles.linkDark]}>{t('legal.storageDetails')}</Text></Pressable>
        <Pressable accessibilityRole="button" onPress={dismiss} style={[styles.dismiss, dark && styles.dismissDark]}><Text style={[styles.dismissText, dark && styles.dismissTextDark]}>{t('legal.storageDismiss')}</Text></Pressable>
      </View>
    </View>
  </View>;
}

const styles = StyleSheet.create({
  position: { position: 'absolute', left: 12, right: 12, bottom: 12, zIndex: 100, alignItems: 'center' },
  banner: { width: '100%', maxWidth: 720, backgroundColor: colors.surface, borderColor: colors.lineStrong, borderWidth: 1, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12, shadowColor: colors.shadow, shadowOpacity: 0.18, shadowRadius: 12, elevation: 8, gap: 10 },
  bannerDark: { backgroundColor: '#111C2E', borderColor: '#475569' },
  message: { color: colors.ink, fontSize: 13, lineHeight: 19 },
  messageDark: { color: '#F8FAFC' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 18 },
  link: { color: colors.primary, fontSize: 12, fontWeight: '700', paddingVertical: 8 },
  linkDark: { color: '#93C5FD' },
  dismiss: { backgroundColor: colors.primary, paddingHorizontal: 15, paddingVertical: 9, borderRadius: 8 },
  dismissDark: { backgroundColor: '#60A5FA' },
  dismissText: { color: colors.inverse, fontSize: 12, fontWeight: '800' },
  dismissTextDark: { color: '#08111F' },
});
