type PublicConfig = {
  supabaseUrl: string;
  supabasePublishableKey: string;
  classioApiUrl: string | null;
};

function decodeJwtRole(token: string): string | null {
  if (!token.startsWith('eyJ')) {
    return null;
  }

  try {
    const payload = token.split('.')[1];
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = globalThis.atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '='));
    return String(JSON.parse(json).role || '');
  } catch {
    return null;
  }
}

function validatePublishableKey(key: string): string {
  if (key.startsWith('sb_secret_') || decodeJwtRole(key) === 'service_role') {
    throw new Error('Expo cannot use a Supabase secret or service-role key. Configure a publishable/anonymous key.');
  }
  return key;
}

export function readPublicConfig(): PublicConfig | null {
  const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL?.trim() || '';
  const rawKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() || '';

  if (!supabaseUrl || !rawKey) {
    return null;
  }

  try {
    const parsedUrl = new URL(supabaseUrl);
    if (parsedUrl.protocol !== 'https:') {
      throw new Error('Supabase URL must use HTTPS.');
    }
  } catch {
    throw new Error('EXPO_PUBLIC_SUPABASE_URL must be a valid HTTPS URL.');
  }

  return {
    supabaseUrl,
    supabasePublishableKey: validatePublishableKey(rawKey),
    classioApiUrl: process.env.EXPO_PUBLIC_CLASSIO_API_URL?.trim() || null,
  };
}
