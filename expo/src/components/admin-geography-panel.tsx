import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, Easing, ImageBackground, Platform, StyleSheet, Text, View } from 'react-native';
import points from '@/lib/admin-country-points.json';
import { getAdminGeography, type CountryVisits } from '@/services/admin-consumption';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import { LoadingState, Panel } from '@/components/ui';
import { SectionHeading } from '@/components/workspace-ui';

function countryName(code: string, language: string, unknown: string): string {
  if (code === 'ZZ') return unknown;
  try { return new Intl.DisplayNames([language], { type: 'region' }).of(code) || code; } catch { return code; }
}

function CountryDot({ name, sessions, recent, x, y }: { name: string; sessions: number; recent: boolean; x: number; y: number }) {
  const [pulse] = useState(() => new Animated.Value(0));
  const [reduceMotion, setReduceMotion] = useState(true);
  useEffect(() => { let active = true; void AccessibilityInfo.isReduceMotionEnabled().then((value) => { if (active) setReduceMotion(value); }); return () => { active = false; }; }, []);
  useEffect(() => {
    if (!recent || reduceMotion) return;
    const animation = Animated.loop(Animated.timing(pulse, { toValue: 1, duration: 1900, easing: Easing.out(Easing.quad), useNativeDriver: Platform.OS !== 'web' }));
    animation.start();
    return () => { animation.stop(); pulse.setValue(0); };
  }, [pulse, recent, reduceMotion]);
  return <View style={[styles.marker, { left: `${x}%`, top: `${y}%` }]} accessibilityLabel={`${name}: ${sessions}`}>
    {recent && !reduceMotion ? <Animated.View style={[styles.pulse, { opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.8, 0] }), transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 3] }) }] }]} /> : null}
    <View style={[styles.dot, recent && styles.recentDot]} />
  </View>;
}

export function AdminGeographyPanel() {
  const { t, language } = useAppPreferences();
  const [countries, setCountries] = useState<CountryVisits[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { let active = true; const refresh = () => { void getAdminGeography().then((result) => { if (active) { setCountries(result.countries); setError(false); } }).catch(() => { if (active) setError(true); }); }; refresh(); const timer = setInterval(refresh, 60_000); return () => { active = false; clearInterval(timer); }; }, []);
  const located = (countries || []).filter((row) => row.code in points);
  const total = (countries || []).reduce((sum, row) => sum + row.sessions, 0);
  return <Panel style={styles.panel}>
    <SectionHeading title={t('admin.visitMap')} body={t('admin.visitMapHelp')} />
    {error ? <Text style={styles.muted}>{t('admin.visitMapUnavailable')}</Text> : countries === null ? <LoadingState /> : <>
      <Text style={styles.total}>{total} {t('admin.visitSessions')}</Text>
      <ImageBackground source={require('../../assets/images/admin-world-map.png')} resizeMode="stretch" style={styles.map} imageStyle={styles.image} accessibilityLabel={t('admin.visitMap')}>
        {located.slice(0, 35).map((row) => { const point = points[row.code as keyof typeof points]; return <CountryDot key={row.code} name={countryName(row.code, language, t('admin.unknownCountry'))} sessions={row.sessions} recent={Boolean(row.recentSessions)} x={point.x} y={point.y} />; })}
      </ImageBackground>
      {countries.length ? <View style={styles.legend}>{countries.slice(0, 8).map((row) => <View key={row.code} style={styles.legendRow}><Text style={styles.country}>{countryName(row.code, language, t('admin.unknownCountry'))}</Text><Text style={styles.count}>{row.sessions}</Text></View>)}</View> : <Text style={styles.muted}>{t('admin.visitMapEmpty')}</Text>}
      <Text style={styles.muted}>{t('admin.visitMapCaveat')}</Text>
    </>}
  </Panel>;
}

const styles = StyleSheet.create({ panel: { gap: 12 }, total: { color: colors.ink, fontWeight: '800', fontSize: 17 }, map: { width: '100%', aspectRatio: 1400 / 620, position: 'relative' }, image: { borderRadius: 12 }, marker: { position: 'absolute', width: 14, height: 14, alignItems: 'center', justifyContent: 'center' }, pulse: { position: 'absolute', width: 13, height: 13, borderRadius: 7, backgroundColor: colors.primary }, dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: colors.primary, borderWidth: 2, borderColor: '#FFFFFF' }, recentDot: { backgroundColor: colors.success }, legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, legendRow: { minWidth: 135, flexGrow: 1, flexBasis: 155, flexDirection: 'row', justifyContent: 'space-between', backgroundColor: colors.surface, padding: 8, borderRadius: 8 }, country: { color: colors.ink, fontSize: 12 }, count: { color: colors.primary, fontSize: 12, fontWeight: '800' }, muted: { color: colors.muted, fontSize: 12, lineHeight: 18 } });
