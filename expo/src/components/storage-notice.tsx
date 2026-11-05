import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { STORAGE_NOTICE_VERSION, storageNoticeUrl } from '@/lib/privacy-notices';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';

const KEY = 'classio.storageNoticeSeen';

export function StorageNotice() {
  const { language, t } = useAppPreferences();
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
    <View accessibilityLiveRegion="polite" style={styles.banner}>
      <Text style={styles.message}>{t('legal.storageNotice')}</Text>
      <View style={styles.actions}>
        <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(storageNoticeUrl(language))}><Text style={styles.link}>{t('legal.storageDetails')}</Text></Pressable>
        <Pressable accessibilityRole="button" onPress={dismiss} style={styles.dismiss}><Text style={styles.dismissText}>{t('legal.storageDismiss')}</Text></Pressable>
      </View>
    </View>
  </View>;
}

const styles = StyleSheet.create({
  position: { position: 'absolute', left: 12, right: 12, bottom: 12, zIndex: 100, alignItems: 'center' },
  banner: { width: '100%', maxWidth: 720, backgroundColor: colors.surface, borderColor: colors.lineStrong, borderWidth: 1, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 12, shadowColor: colors.shadow, shadowOpacity: 0.18, shadowRadius: 12, elevation: 8, gap: 10 },
  message: { color: colors.ink, fontSize: 13, lineHeight: 19 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: 18 },
  link: { color: colors.primary, fontSize: 12, fontWeight: '700', paddingVertical: 8 },
  dismiss: { backgroundColor: colors.primary, paddingHorizontal: 15, paddingVertical: 9, borderRadius: 8 },
  dismissText: { color: colors.inverse, fontSize: 12, fontWeight: '800' },
});
