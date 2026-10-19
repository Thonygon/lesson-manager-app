import { requireSupabase } from '@/lib/supabase';

export type BrandingSettings = {
  brandName: string;
  department: string;
  headerStyle: 'standard' | 'school';
  headerEnabled: boolean;
  footerEnabled: boolean;
  headerLogoUrl: string;
  footerImageUrl: string;
  font: string;
  fontSize: 'compact' | 'standard' | 'large' | 'exam_style';
};

export const DEFAULT_BRANDING: BrandingSettings = { brandName: '', department: '', headerStyle: 'standard', headerEnabled: false, footerEnabled: false, headerLogoUrl: '', footerImageUrl: '', font: 'dejavu', fontSize: 'standard' };
export const BRANDING_FONTS = ['dejavu', 'open_sans', 'yavuz', 'arial', 'calibri', 'times', 'comic_sans'];
export const BRANDING_SIZES = ['compact', 'standard', 'large', 'exam_style'] as const;

function fromRow(row: Record<string, unknown> | null): BrandingSettings {
  if (!row) return DEFAULT_BRANDING;
  return {
    brandName: String(row.brand_name || ''), department: String(row.department || ''),
    headerStyle: row.header_style === 'school' ? 'school' : 'standard',
    headerEnabled: row.header_enabled === true, footerEnabled: row.footer_enabled === true,
    headerLogoUrl: String(row.header_logo_url || ''), footerImageUrl: String(row.footer_image_url || ''),
    font: BRANDING_FONTS.includes(String(row.branding_font)) ? String(row.branding_font) : 'dejavu',
    fontSize: BRANDING_SIZES.includes(row.branding_font_size as BrandingSettings['fontSize']) ? row.branding_font_size as BrandingSettings['fontSize'] : 'standard',
  };
}

async function identity() {
  const client = requireSupabase();
  const { data, error } = await client.auth.getUser();
  if (error || !data.user) throw error ?? new Error('Your session has expired.');
  return { client, userId: data.user.id };
}

export async function getBrandingSettings(): Promise<BrandingSettings> {
  const { client, userId } = await identity();
  const { data, error } = await client.from('branding_settings').select('brand_name,department,header_style,header_enabled,footer_enabled,header_logo_url,footer_image_url,branding_font,branding_font_size').eq('user_id', userId).maybeSingle();
  if (error) throw error;
  return fromRow(data);
}

export async function hasCustomBranding(): Promise<boolean> {
  const settings = await getBrandingSettings();
  return settings.headerEnabled || settings.footerEnabled;
}

export async function saveBrandingSettings(settings: BrandingSettings): Promise<BrandingSettings> {
  const { client, userId } = await identity();
  const enabled = settings.headerEnabled || settings.footerEnabled;
  const value = enabled ? settings : DEFAULT_BRANDING;
  const payload = {
    user_id: userId, brand_name: value.brandName.trim().slice(0, 200), department: value.department.trim().slice(0, 200),
    header_style: value.headerStyle, header_enabled: value.headerEnabled, footer_enabled: value.footerEnabled,
    header_logo_url: value.headerLogoUrl, footer_image_url: value.footerImageUrl,
    branding_font: BRANDING_FONTS.includes(value.font) ? value.font : 'dejavu',
    branding_font_size: BRANDING_SIZES.includes(value.fontSize) ? value.fontSize : 'standard',
  };
  const { data: existing, error: lookupError } = await client.from('branding_settings').select('user_id').eq('user_id', userId).maybeSingle();
  if (lookupError) throw lookupError;
  const result = existing ? await client.from('branding_settings').update(payload).eq('user_id', userId) : await client.from('branding_settings').insert(payload);
  if (result.error) throw result.error;
  return fromRow(payload);
}

export async function cleanupBrandingImages(settings: BrandingSettings): Promise<void> {
  const { client, userId } = await identity();
  const { data, error } = await client.storage.from('branding').list(userId);
  if (error) return;
  const retained = [settings.headerLogoUrl, settings.footerImageUrl];
  const paths = (data || []).map((item) => `${userId}/${item.name}`).filter((path) => /\/(header|footer)_/.test(path) && !retained.some((url) => url.endsWith(path)));
  if (paths.length) await client.storage.from('branding').remove(paths);
}

export type BrandingImage = File | { name: string; type: string; size: number; data: Uint8Array };

export async function uploadBrandingImage(file: BrandingImage, type: 'header' | 'footer'): Promise<string> {
  if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 2 * 1024 * 1024 || file.size === 0) throw new Error('Choose a PNG or JPEG image smaller than 2 MB.');
  const { client, userId } = await identity();
  const path = `${userId}/${type}_${Date.now()}_${Math.random().toString(36).slice(2)}.${file.type === 'image/png' ? 'png' : 'jpg'}`;
  const body = 'data' in file ? file.data : file;
  const { error } = await client.storage.from('branding').upload(path, body, { contentType: file.type, upsert: false });
  if (error) throw error;
  return client.storage.from('branding').getPublicUrl(path).data.publicUrl;
}
