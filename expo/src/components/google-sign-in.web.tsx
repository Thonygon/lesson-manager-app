import { useEffect, useRef } from 'react';

import { useAppPreferences } from '@/providers/app-preferences';

type CredentialResponse = { credential?: string };
type GoogleIdentity = {
  initialize: (options: { client_id: string; callback: (response: CredentialResponse) => void; nonce: string }) => void;
  renderButton: (element: HTMLElement, options: { theme: string; size: string; text: string; shape: string; width: number }) => void;
};

declare global { interface Window { google?: { accounts?: { id?: GoogleIdentity } } } }

function loadGoogleIdentity(): Promise<GoogleIdentity> {
  const existing = window.google?.accounts?.id;
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve, reject) => {
    const script = document.querySelector<HTMLScriptElement>('script[data-classio-google-identity]') || document.createElement('script');
    const ready = () => window.google?.accounts?.id ? resolve(window.google.accounts.id) : reject(new Error('Google sign-in could not load.'));
    script.addEventListener('load', ready, { once: true });
    script.addEventListener('error', () => reject(new Error('Google sign-in could not load.')), { once: true });
    if (!script.parentNode) {
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.dataset.classioGoogleIdentity = 'true';
      document.head.appendChild(script);
    }
  });
}

async function noncePair(): Promise<{ raw: string; hashed: string }> {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const raw = btoa(String.fromCharCode(...bytes));
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
  const hashed = Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('');
  return { raw, hashed };
}

export function GoogleSignIn({ disabled, onCredential, onError }: { disabled: boolean; label: string; onPress: () => void; onCredential?: (token: string, nonce: string) => void; onError?: (message: string) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useAppPreferences();
  useEffect(() => {
    let active = true;
    let observer: ResizeObserver | undefined;
    const clientId = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId) { onError?.('Google sign-in is not configured.'); return; }
    void Promise.all([loadGoogleIdentity(), noncePair()]).then(([identity, nonce]) => {
      if (!active || !host.current) return;
      identity.initialize({ client_id: clientId, nonce: nonce.hashed, callback: (response) => {
        if (!active) return;
        if (!response.credential) { onError?.('Google did not return a sign-in credential.'); return; }
        onCredential?.(response.credential, nonce.raw);
      } });
      let renderedWidth = 0;
      const render = () => {
        if (!active || !host.current) return;
        const width = Math.min(400, Math.floor(host.current.clientWidth));
        if (!width || width === renderedWidth) return;
        renderedWidth = width;
        host.current.replaceChildren();
        identity.renderButton(host.current, { theme: resolvedTheme === 'dark' ? 'filled_black' : 'outline', size: 'large', text: 'continue_with', shape: 'rectangular', width });
      };
      observer = new ResizeObserver(render);
      observer.observe(host.current);
      render();
    }).catch((error) => { if (active) onError?.(error instanceof Error ? error.message : 'Google sign-in could not load.'); });
    return () => { active = false; observer?.disconnect(); };
  }, [onCredential, onError, resolvedTheme]);
  return <div aria-disabled={disabled} ref={host} style={{ display: 'flex', justifyContent: 'center', width: '100%', minHeight: 44, opacity: disabled ? 0.5 : 1, pointerEvents: disabled ? 'none' : 'auto' }} />;
}
