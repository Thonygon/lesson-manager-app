export const ORAL_AUDIO_REVIEW_WARNING_DAYS = 5;

export function oralAudioExpiresSoon(expiresAt: unknown, now = Date.now()): boolean {
  const expiry = Date.parse(String(expiresAt || ''));
  return Number.isFinite(expiry) && expiry > now && expiry <= now + ORAL_AUDIO_REVIEW_WARNING_DAYS * 86400000;
}
