import { LEGAL_PUBLICATION } from '@/lib/legal-publication.generated';
import type { ClassioProfile } from '@/types/auth';

export type LegalAcceptance = { slug: string; version: string; language: string; sha256: string; accepted_at: string };

export function requiredLegalDocuments(mode: 'teacher' | 'student', language: 'en' | 'es' | 'tr') {
  const slugs = mode === 'teacher' ? ['terms', 'teacher-data'] : ['terms'];
  return slugs.map((slug) => {
    const document = LEGAL_PUBLICATION.documents.find((item) => item.slug === slug && item.language === language);
    if (!document) throw new Error(`Missing ${slug} publication for ${language}`);
    return document;
  });
}

/** Verify the exact documents reviewed for this first-login choice. */
export function hasRequiredLegalAcceptance(accepted: readonly LegalAcceptance[], mode: 'teacher' | 'student', language: 'en' | 'es' | 'tr') {
  return requiredLegalDocuments(mode, language).every((document) => accepted.some((entry) => entry.slug === document.slug
    && entry.language === language && entry.version === LEGAL_PUBLICATION.version && entry.sha256 === document.sha256));
}

export function legalModeForProfile(profile: ClassioProfile | null): 'teacher' | 'student' {
  if (profile?.role === 'school_admin') return 'teacher';
  if (profile?.last_active_mode === 'student') return 'student';
  if (profile?.last_active_mode === 'teacher') return 'teacher';
  return profile?.can_teach || profile?.role === 'teacher' ? 'teacher' : 'student';
}

export function hasCurrentLegalAcceptance(profile: ClassioProfile | null, accepted: readonly LegalAcceptance[]) {
  if (!profile) return false;
  const mode = legalModeForProfile(profile);
  const slugs = mode === 'teacher' ? ['terms', 'teacher-data'] : ['terms'];
  return slugs.every((slug) => accepted.some((entry) => entry.slug === slug
    && entry.version === LEGAL_PUBLICATION.version
    && LEGAL_PUBLICATION.documents.some((document) => document.slug === slug && document.language === entry.language && document.sha256 === entry.sha256)));
}
