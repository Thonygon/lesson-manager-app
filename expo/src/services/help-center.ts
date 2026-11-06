import { requireSupabase } from '@/lib/supabase';

export const HELP_SCREENSHOT_BUCKET = 'classio-help-screenshots';
export const HELP_SCREENSHOT_LIMIT = 5 * 1024 * 1024;
export type HelpKind = 'bug' | 'idea' | 'accessibility' | 'other' | 'privacy_rights' | 'security_incident';
export type PrivacyScope = 'access' | 'rectification' | 'erasure' | 'restriction' | 'portability' | 'objection' | 'other';
const PRIVACY_SCOPES: PrivacyScope[] = ['access', 'rectification', 'erasure', 'restriction', 'portability', 'objection', 'other'];
export type HelpStatus = 'open' | 'triaged' | 'in_progress' | 'resolved' | 'closed';
export type HelpScreenshot = File | { name: string; type: string; size: number; data: Uint8Array };
export type HelpTicket = {
  id: string;
  ticket_number: number;
  reporter_id: string;
  kind: HelpKind;
  privacy_scope: PrivacyScope | null;
  title: string;
  description: string;
  page_path: string;
  screenshot_mime: string | null;
  status: HelpStatus;
  response: string | null;
  created_at: string;
  updated_at: string;
};

function validImageBytes(bytes: Uint8Array, mime: string): boolean {
  if (mime === 'image/png') return bytes.length >= 8 && [137, 80, 78, 71, 13, 10, 26, 10].every((byte, index) => bytes[index] === byte);
  if (mime === 'image/jpeg') return bytes.length >= 4 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255 && bytes[bytes.length - 2] === 255 && bytes[bytes.length - 1] === 217;
  return false;
}

export async function checkedHelpScreenshot(file: HelpScreenshot): Promise<{ bytes: Uint8Array; mime: 'image/png' | 'image/jpeg' }> {
  if (!['image/png', 'image/jpeg'].includes(file.type) || file.size < 8 || file.size > HELP_SCREENSHOT_LIMIT) throw new Error('help.invalidImage');
  const bytes = 'data' in file ? file.data : new Uint8Array(await file.arrayBuffer());
  if (bytes.length !== file.size || !validImageBytes(bytes, file.type)) throw new Error('help.invalidImage');
  return { bytes, mime: file.type as 'image/png' | 'image/jpeg' };
}

function screenshotPath(ticket: Pick<HelpTicket, 'id' | 'reporter_id' | 'screenshot_mime'>): string | null {
  const extension = ticket.screenshot_mime === 'image/png' ? 'png' : ticket.screenshot_mime === 'image/jpeg' ? 'jpg' : null;
  return extension ? `${ticket.reporter_id}/${ticket.id}.${extension}` : null;
}

export async function submitHelpTicket(input: { kind: HelpKind; privacyScope?: PrivacyScope | null; title: string; description: string; pagePath: string; screenshot?: HelpScreenshot | null }) {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw new Error('help.signInRequired');
  const title = input.title.trim();
  const description = input.description.trim();
  if (title.length < 5 || title.length > 120 || description.length < 15 || description.length > 4000) throw new Error('help.invalidDescription');
  if (input.kind === 'privacy_rights' && !PRIVACY_SCOPES.includes(input.privacyScope as PrivacyScope)) throw new Error('help.privacyScopeRequired');
  const screenshot = input.screenshot ? await checkedHelpScreenshot(input.screenshot) : null;
  const pagePath = input.pagePath.trim().startsWith('/') ? input.pagePath.trim().slice(0, 300) : '/help';
  const { data, error } = await client.from('classio_help_tickets').insert({ reporter_id: auth.user.id, kind: input.kind, privacy_scope: input.kind === 'privacy_rights' ? input.privacyScope : null, title, description, page_path: pagePath, screenshot_mime: screenshot?.mime ?? null }).select('id,ticket_number,reporter_id,screenshot_mime').single();
  if (error?.code === 'P0001') throw new Error('help.rateLimited');
  if (error || !data) throw error || new Error('help.submitFailed');
  let screenshotUploaded = !screenshot;
  const path = screenshotPath(data);
  if (screenshot && path) {
    const upload = await client.storage.from(HELP_SCREENSHOT_BUCKET).upload(path, screenshot.bytes, { contentType: screenshot.mime, upsert: false });
    screenshotUploaded = !upload.error;
  }
  return { number: Number(data.ticket_number), screenshotUploaded };
}

export async function myHelpTickets(focusId?: string): Promise<HelpTicket[]> {
  const client = requireSupabase();
  const { data: auth } = await client.auth.getUser();
  if (!auth.user) return [];
  const { data, error } = await client.from('classio_help_tickets').select('id,ticket_number,reporter_id,kind,privacy_scope,title,description,page_path,screenshot_mime,status,response,created_at,updated_at').eq('reporter_id', auth.user.id).order('created_at', { ascending: false }).limit(30);
  if (error) throw error;
  const tickets = (data || []) as HelpTicket[];
  if (focusId && !tickets.some((ticket) => ticket.id === focusId)) {
    const focused = await myHelpTicket(focusId);
    if (focused) tickets.unshift(focused);
  }
  return tickets;
}

export async function myHelpTicket(id: string): Promise<HelpTicket | null> {
  const client = requireSupabase();
  const { data: auth } = await client.auth.getUser();
  if (!auth.user) return null;
  const { data, error } = await client.from('classio_help_tickets').select('id,ticket_number,reporter_id,kind,privacy_scope,title,description,page_path,screenshot_mime,status,response,created_at,updated_at').eq('id', id).eq('reporter_id', auth.user.id).maybeSingle();
  if (error) throw error;
  return data as HelpTicket | null;
}

export async function purgeOwnHelpScreenshots(userId: string): Promise<void> {
  const client = requireSupabase();
  const bucket = client.storage.from(HELP_SCREENSHOT_BUCKET);
  for (;;) {
    const { data, error } = await bucket.list(userId, { limit: 100 });
    if (error) throw error;
    const paths = (data || []).filter((item) => item.name && item.id).map((item) => `${userId}/${item.name}`);
    if (!paths.length) return;
    const removed = await bucket.remove(paths);
    if (removed.error) throw removed.error;
  }
}

export async function updateHelpTicket(id: string, status: HelpStatus, response: string): Promise<void> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw new Error('help.signInRequired');
  const { data, error } = await client.from('classio_help_tickets').update({ status, response: response.trim().slice(0, 2000) || null, handled_by: auth.user.id }).eq('id', id).select('id').single();
  if (error || !data) throw error || new Error('help.developer.saveFailed');
}

export async function helpScreenshotUrl(ticket: Pick<HelpTicket, 'id' | 'reporter_id' | 'screenshot_mime'>): Promise<string | null> {
  const path = screenshotPath(ticket);
  if (!path) return null;
  const { data, error } = await requireSupabase().storage.from(HELP_SCREENSHOT_BUCKET).createSignedUrl(path, 60);
  if (error) throw error;
  return data?.signedUrl || null;
}
