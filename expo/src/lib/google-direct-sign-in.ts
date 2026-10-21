const GOOGLE_SIGN_IN_STATE = 'classio-google-sign-in';

type PendingSignIn = { state: string; nonce: string };

function randomValue() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export async function beginDirectGoogleSignIn(): Promise<string | null> {
  const clientId = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) return 'Google sign-in is not configured.';
  if (typeof window === 'undefined' || !window.crypto?.subtle) return 'Google sign-in requires a secure browser connection.';

  const state = randomValue();
  const nonce = randomValue();
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(nonce));
  const hashedNonce = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  window.sessionStorage.setItem(GOOGLE_SIGN_IN_STATE, JSON.stringify({ state, nonce } satisfies PendingSignIn));

  const url = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  url.search = new URLSearchParams({
    client_id: clientId,
    redirect_uri: `${window.location.origin}/sign-in`,
    response_type: 'id_token',
    scope: 'openid email profile',
    nonce: hashedNonce,
    state,
    prompt: 'select_account',
  }).toString();
  window.location.assign(url.toString());
  return null;
}

export function takeDirectGoogleResponse(): { token?: string; nonce?: string; error?: string } | null {
  if (typeof window === 'undefined') return null;
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  if (!fragment.has('id_token') && !fragment.has('error')) return null;
  window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`);

  const stored = window.sessionStorage.getItem(GOOGLE_SIGN_IN_STATE);
  window.sessionStorage.removeItem(GOOGLE_SIGN_IN_STATE);
  if (!stored) return { error: 'Google sign-in could not be verified. Please try again.' };
  try {
    const pending = JSON.parse(stored) as PendingSignIn;
    if (!pending.state || !pending.nonce || pending.state !== fragment.get('state')) {
      return { error: 'Google sign-in could not be verified. Please try again.' };
    }
    if (fragment.has('error')) return { error: 'Google sign-in was cancelled or denied.' };
    const token = fragment.get('id_token');
    return token ? { token, nonce: pending.nonce } : { error: 'Google did not return a sign-in token.' };
  } catch {
    return { error: 'Google sign-in could not be verified. Please try again.' };
  }
}
