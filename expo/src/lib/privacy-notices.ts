import type { AppLanguage } from '@/providers/app-preferences';

export type PrivacyAudience = 'website' | 'app' | 'students';

export const PRIVACY_NOTICE_VERSION = '2026-11-04.1';
export const STORAGE_NOTICE_VERSION = '2026-11-05.2';

export function privacyNoticeUrl(language: AppLanguage, audience: PrivacyAudience): string {
  return `https://masterclassio.com/privacy/${language}/${audience}/`;
}

export function storageNoticeUrl(language: AppLanguage): string {
  return `https://masterclassio.com/cookies/${language}/`;
}
