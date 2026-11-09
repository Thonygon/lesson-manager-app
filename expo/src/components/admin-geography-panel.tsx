import { useEffect, useState } from 'react';
import { ImageBackground, StyleSheet, Text, View } from 'react-native';
import points from '@/lib/admin-country-points.json';
import { getAdminGeography, type CountryVisits } from '@/services/admin-consumption';
import { useAppPreferences } from '@/providers/app-preferences';
import { colors } from '@/theme';
import { LoadingState, Panel } from '@/components/ui';
import { SectionHeading } from '@/components/workspace-ui';

function countryName(code: string, language: string): string {
  if (code === 'ZZ') return code;
  try { return new Intl.DisplayNames([language], { type: 'region' }).of(code) || code; } catch { return code; }
}

export function AdminGeographyPanel() {
  const { t, language } = useAppPreferences();
  const [countries, setCountries] = useState<CountryVisits[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { let active = true; void getAdminGeography().then((result) => { if (active) setCountries(result.countries); }).catch(() => { if (active) setError(true); }); return () => { active = false; }; }, []);
  const located = (countries || []).filter((row) => row.code in points);
  const total = (countries || []).reduce((sum, row) => sum + row.sessions, 0);
  return <Panel style={styles.panel}>
    <SectionHeading title={t('admin.visitMap')} body={t('admin.visitMapHelp')} />
    {error ? <Text style={styles.muted}>{t('admin.visitMapUnavailable')}</Text> : countries === null ? <LoadingState /> : <>
      <Text style={styles.total}>{total} {t('admin.visitSessions')}</Text>
      <ImageBackground source={require('../../assets/images/admin-world-map.png')} resizeMode="stretch" style={styles.map} imageStyle={styles.image} accessibilityLabel={t('admin.visitMap')}>
        {located.slice(0, 35).map((row) => { const point = points[row.code as keyof typeof points]; return <View key={row.code} style={[styles.dot, { left: `${point.x}%`, top: `${point.y}%` }]} accessibilityLabel={`${countryName(row.code, language)}: ${row.sessions}`} />; })}
      </ImageBackground>
      {countries.length ? <View style={styles.legend}>{countries.slice(0, 8).map((row) => <View key={row.code} style={styles.legendRow}><Text style={styles.country}>{countryName(row.code, language)}</Text><Text style={styles.count}>{row.sessions}</Text></View>)}</View> : <Text style={styles.muted}>{t('admin.visitMapEmpty')}</Text>}
      <Text style={styles.muted}>{t('admin.visitMapCaveat')}</Text>
    </>}
  </Panel>;
}

const styles = StyleSheet.create({ panel: { gap: 12 }, total: { color: colors.ink, fontWeight: '800', fontSize: 17 }, map: { width: '100%', aspectRatio: 1400 / 620, position: 'relative' }, image: { borderRadius: 12 }, dot: { position: 'absolute', width: 9, height: 9, borderRadius: 5, backgroundColor: colors.primary, borderWidth: 2, borderColor: '#FFFFFF' }, legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, legendRow: { minWidth: 135, flexGrow: 1, flexBasis: 155, flexDirection: 'row', justifyContent: 'space-between', backgroundColor: colors.surface, padding: 8, borderRadius: 8 }, country: { color: colors.ink, fontSize: 12 }, count: { color: colors.primary, fontSize: 12, fontWeight: '800' }, muted: { color: colors.muted, fontSize: 12, lineHeight: 18 } });
