import type { AppNotification } from '@/services/app-notifications';

export type SystemNotificationPermission = 'default' | 'granted' | 'denied' | 'unsupported';
let chimeContext: AudioContext | null = null;

function primeClassioChime() {
  try {
    chimeContext ||= new window.AudioContext();
    if (chimeContext.state === 'suspended') void chimeContext.resume();
  } catch { /* Sound is optional when a browser blocks audio. */ }
}

export function prepareClassioChime() {
  if (systemNotificationPermission() !== 'granted') return () => {};
  window.addEventListener('pointerdown', primeClassioChime, { once: true });
  return () => window.removeEventListener('pointerdown', primeClassioChime);
}

export function systemNotificationPermission(): SystemNotificationPermission {
  if (typeof window === 'undefined' || !('Notification' in window) || !('serviceWorker' in navigator)) return 'unsupported';
  return Notification.permission;
}

export async function requestSystemNotificationPermission(): Promise<SystemNotificationPermission> {
  const current = systemNotificationPermission();
  if (current === 'unsupported' || current === 'denied') return current;
  if (current === 'granted') {
    primeClassioChime();
    await navigator.serviceWorker.register('/classio-notifications-sw.js');
    return 'granted';
  }
  // The browser prompt must be initiated by the user's click, before an await.
  const permissionRequest = Notification.requestPermission();
  primeClassioChime();
  const permission = await permissionRequest;
  if (permission === 'granted') await navigator.serviceWorker.register('/classio-notifications-sw.js');
  return permission;
}

function notificationPath(href: AppNotification['href']): string {
  if (typeof href === 'string') return href.startsWith('/') && !href.startsWith('//') && !href.includes('\\') ? href : '/';
  const path = String(href.pathname || '/');
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) return '/';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(href.params || {})) {
    if (value != null) params.set(key, String(value));
  }
  return `${path}${params.size ? `?${params}` : ''}`;
}

function playClassioChime() {
  try {
    if (!chimeContext || chimeContext.state !== 'running') return;
    const context = chimeContext;
    const start = context.currentTime;
    for (const [offset, frequency] of [[0, 660], [0.14, 880]] as const) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start + offset);
      gain.gain.exponentialRampToValueAtTime(0.09, start + offset + 0.025);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + 0.22);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(start + offset);
      oscillator.stop(start + offset + 0.23);
    }
  } catch { /* Browser audio policy may block foreground sound. */ }
}

export async function showSystemNotification(item: AppNotification, title: string): Promise<void> {
  if (systemNotificationPermission() !== 'granted') return;
  await navigator.serviceWorker.register('/classio-notifications-sw.js');
  const registration = await navigator.serviceWorker.ready;
  await registration.showNotification(title, {
    icon: '/logo_classio_light.png',
    tag: item.key,
    data: { path: notificationPath(item.href) },
  });
  if (document.visibilityState === 'visible') playClassioChime();
}
