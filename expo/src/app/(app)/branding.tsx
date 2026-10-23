import { createElement, useEffect, useState } from 'react';
import { Image, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppShell } from '@/components/app-shell';
import { ActionFeedback, Button, Field, LoadingState, Panel, SelectField } from '@/components/ui';
import { useAppPreferences } from '@/providers/app-preferences';
import { BRANDING_FONTS, BRANDING_SIZES, cleanupBrandingImages, DEFAULT_BRANDING, getBrandingSettings, saveBrandingSettings, uploadBrandingImage, type BrandingImage, type BrandingSettings } from '@/services/branding';
import { colors } from '@/theme';

function ImagePicker({ label, url, file, onFile, onRemove }: { label: string; url: string; file: BrandingImage | null; onFile: (file: BrandingImage) => void; onRemove: () => void }) {
  const { t } = useAppPreferences();
  const pickNative = async () => {
    const picker = await import('expo-image-picker');
    const result = await picker.launchImageLibraryAsync({ mediaTypes: ['images'], base64: true, quality: 1 });
    const asset = result.assets?.[0];
    if (!asset?.base64) return;
    const source = asset.base64;
    const bytes = new Uint8Array(Math.floor(source.length * 3 / 4));
    let length = 0;
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let buffer = 0; let bits = 0;
    for (const character of source) { if (character === '=') break; const value = alphabet.indexOf(character); if (value < 0) continue; buffer = (buffer << 6) | value; bits += 6; if (bits >= 8) { bits -= 8; bytes[length++] = (buffer >> bits) & 255; } }
    onFile({ name: asset.fileName || 'branding-image.jpg', type: asset.mimeType === 'image/png' ? 'image/png' : 'image/jpeg', size: length, data: bytes.slice(0, length) });
  };
  return <View style={styles.imageControl}><Text style={styles.label}>{label}</Text>{url ? <View style={styles.imageRow}><Image source={{ uri: url }} resizeMode="contain" style={styles.brandImage} /><Button secondary onPress={onRemove}>{t('branding.remove')}</Button></View> : null}{Platform.OS === 'web' ? createElement('input', { type: 'file', accept: 'image/png,image/jpeg', 'aria-label': label, onChange: (event: { target: { files?: FileList; value: string } }) => { const file = event.target.files?.[0]; if (file) onFile(file); event.target.value = ''; }, style: { color: colors.ink, maxWidth: '100%' } }) : <Button secondary onPress={() => void pickNative()}>{t('branding.upload')}</Button>}<Text style={styles.hint}>{file ? file.name : t('branding.upload')}</Text></View>;
}

export default function BrandingScreen() {
  const { t } = useAppPreferences();
  const [settings, setSettings] = useState<BrandingSettings>(DEFAULT_BRANDING);
  const [customEnabled, setCustomEnabled] = useState(false);
  const [headerFile, setHeaderFile] = useState<BrandingImage | null>(null);
  const [footerFile, setFooterFile] = useState<BrandingImage | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [tone, setTone] = useState<'success' | 'error'>('error');
  const enabled = customEnabled;
  useEffect(() => { void getBrandingSettings().then((loaded) => { setSettings(loaded); setCustomEnabled(loaded.headerEnabled || loaded.footerEnabled); }).catch(() => { setTone('error'); setMessage(t('branding.loadFailed')); }).finally(() => setLoading(false)); }, [t]);
  const change = (patch: Partial<BrandingSettings>) => { setSettings((current) => ({ ...current, ...patch })); setMessage(''); };
  const chooseFile = (file: BrandingImage, type: 'header' | 'footer') => { if (!['image/png', 'image/jpeg'].includes(file.type) || !file.size || file.size > 2 * 1024 * 1024) { setTone('error'); setMessage(t('branding.upload')); return; } if (type === 'header') setHeaderFile(file); else setFooterFile(file); setMessage(''); };
  const save = async () => {
    setSaving(true); setMessage('');
    try {
      const next = enabled ? { ...settings, headerEnabled: true, footerEnabled: true } : { ...DEFAULT_BRANDING };
      if (enabled && headerFile) next.headerLogoUrl = await uploadBrandingImage(headerFile, 'header');
      if (enabled && footerFile) next.footerImageUrl = await uploadBrandingImage(footerFile, 'footer');
      const saved = await saveBrandingSettings(next);
      void cleanupBrandingImages(saved);
      setSettings(saved); setCustomEnabled(saved.headerEnabled || saved.footerEnabled); setHeaderFile(null); setFooterFile(null); setTone('success'); setMessage(t('branding.saved'));
    } catch { setTone('error'); setMessage(t('branding.failed')); } finally { setSaving(false); }
  };
  if (loading) return <AppShell title={t('branding.title')} eyebrow={t('branding.eyebrow')}><LoadingState /></AppShell>;
  return <AppShell title={t('branding.title')} eyebrow={t('branding.eyebrow')}>
    <Text style={styles.intro}>{t('branding.intro')}</Text>
    <View style={styles.layout}>
      <View style={styles.controls}>
        <Panel style={styles.panel}><Pressable accessibilityRole="switch" accessibilityState={{ checked: enabled }} onPress={() => { setCustomEnabled(!enabled); setMessage(''); }} style={styles.switchRow}><View style={styles.switchCopy}><Text style={styles.title}>{t('branding.enable')}</Text><Text style={styles.hint}>{t(enabled ? 'branding.private' : 'branding.default')}</Text></View><View style={[styles.switch, enabled && styles.switchOn]}><View style={[styles.knob, enabled && styles.knobOn]} /></View></Pressable></Panel>
        {enabled ? <><Panel style={styles.panel}><Text style={styles.title}>{t('branding.identity')}</Text><Field accessibilityLabel={t('branding.brandName')} value={settings.brandName} onChangeText={(brandName) => change({ brandName: brandName.slice(0, 200) })} placeholder={t('branding.brandName')} /><Field accessibilityLabel={t('branding.department')} value={settings.department} onChangeText={(department) => change({ department: department.slice(0, 200) })} placeholder={t('branding.department')} /></Panel>
        <Panel style={styles.panel}><Text style={styles.title}>{t('branding.layout')}</Text><SelectField label={t('branding.headerStyle')} value={settings.headerStyle} options={[{ value: 'standard', label: t('branding.standard') }, { value: 'school', label: t('branding.school') }]} onChange={(headerStyle) => change({ headerStyle: headerStyle as BrandingSettings['headerStyle'] })} /><SelectField label={t('branding.font')} value={settings.font} options={BRANDING_FONTS.map((font) => ({ value: font, label: font === 'dejavu' ? 'DejaVu Sans' : font === 'open_sans' ? 'Open Sans' : font === 'yavuz' ? 'Yavuz Bağış' : font === 'times' ? 'Times New Roman' : font === 'comic_sans' ? 'Comic Sans MS' : font[0].toUpperCase() + font.slice(1) }))} onChange={(font) => change({ font })} /><SelectField label={t('branding.size')} value={settings.fontSize} options={BRANDING_SIZES.map((size) => ({ value: size, label: t(`branding.${size}`) }))} onChange={(fontSize) => change({ fontSize: fontSize as BrandingSettings['fontSize'] })} /></Panel>
        <Panel style={styles.panel}><Text style={styles.title}>{t('branding.headerLogo')}</Text><ImagePicker label={t('branding.headerLogo')} url={settings.headerLogoUrl} file={headerFile} onFile={(file) => chooseFile(file, 'header')} onRemove={() => { setHeaderFile(null); change({ headerLogoUrl: '' }); }} /><ImagePicker label={t('branding.footerImage')} url={settings.footerImageUrl} file={footerFile} onFile={(file) => chooseFile(file, 'footer')} onRemove={() => { setFooterFile(null); change({ footerImageUrl: '' }); }} /></Panel></> : null}
        <View style={styles.actions}><Button disabled={saving} onPress={() => void save()}>{saving ? t('common.saving') : t('branding.save')}</Button><ActionFeedback message={message} onDismiss={(shown) => setMessage((current) => current === shown ? '' : current)} tone={tone} /></View>
      </View>
      <Panel style={styles.preview}><Text style={styles.title}>{t('branding.preview')}</Text><View style={styles.paper}>{enabled && settings.headerLogoUrl ? <Image source={{ uri: settings.headerLogoUrl }} resizeMode="contain" style={styles.previewLogo} /> : !enabled ? <Image source={require('../../../assets/images/classio-logo.png')} resizeMode="contain" style={styles.previewLogo} /> : null}<Text style={[styles.previewBrand, settings.headerStyle === 'school' && styles.center]}>{enabled ? settings.brandName || 'Classio' : 'Classio'}</Text>{enabled && settings.department ? <Text style={[styles.previewSub, settings.headerStyle === 'school' && styles.center]}>{settings.department}</Text> : null}<View style={styles.rule} /><Text style={styles.previewTitle}>{t('branding.sample')}</Text>{settings.headerStyle === 'school' && enabled ? <Text style={styles.previewSub}>__________________   ·   __________________</Text> : null}<View style={styles.sampleLine} /><View style={[styles.sampleLine, { width: '72%' }]} /><View style={[styles.sampleLine, { width: '88%' }]} /><View style={styles.previewFooter}>{enabled && settings.footerImageUrl ? <Image source={{ uri: settings.footerImageUrl }} resizeMode="contain" style={styles.footerPreview} /> : <Text style={styles.previewSub}>{enabled ? settings.brandName || 'Classio' : 'Classio'}</Text>}<Text style={styles.previewSub}>1</Text></View></View></Panel>
    </View>
  </AppShell>;
}

const styles = StyleSheet.create({ intro: { color: colors.muted, fontSize: 15, lineHeight: 23, marginBottom: 19 }, layout: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: 15 }, controls: { flex: 1, minWidth: 300, gap: 13 }, panel: { gap: 13, padding: 20 }, title: { color: colors.ink, fontSize: 16, fontWeight: '900' }, hint: { color: colors.muted, fontSize: 11, lineHeight: 18 }, label: { color: colors.ink, fontSize: 11, fontWeight: '800' }, switchRow: { flexDirection: 'row', alignItems: 'center', gap: 14 }, switchCopy: { flex: 1, gap: 5 }, switch: { width: 44, height: 25, borderRadius: 99, padding: 3, backgroundColor: colors.line }, switchOn: { backgroundColor: colors.primary }, knob: { width: 19, height: 19, borderRadius: 10, backgroundColor: '#fff' }, knobOn: { alignSelf: 'flex-end' }, imageControl: { gap: 7 }, imageRow: { flexDirection: 'row', alignItems: 'center', gap: 12 }, brandImage: { width: 105, height: 58 }, actions: { gap: 8, alignItems: 'flex-start' }, preview: { flex: 1, minWidth: 290, gap: 15, padding: 20 }, paper: { minHeight: 420, padding: 24, backgroundColor: '#fff', borderRadius: 12, borderWidth: 1, borderColor: colors.line }, previewLogo: { width: 86, height: 55, marginBottom: 7 }, previewBrand: { color: '#1D4ED8', fontSize: 18, fontWeight: '900' }, previewSub: { color: '#64748B', fontSize: 10, marginTop: 5 }, center: { textAlign: 'center' }, rule: { height: 2, backgroundColor: '#3B82F6', marginVertical: 15 }, previewTitle: { color: '#0F172A', fontSize: 18, fontWeight: '800', marginBottom: 18 }, sampleLine: { height: 7, width: '100%', backgroundColor: '#E2E8F0', borderRadius: 8, marginBottom: 14 }, previewFooter: { marginTop: 'auto', borderTopWidth: 1, borderTopColor: '#CBD5E1', paddingTop: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, footerPreview: { width: 140, height: 33 } });
