export type PasswordRecoveryLink =
  | { kind: 'session'; accessToken: string; refreshToken: string }
  | { kind: 'error'; description: string }
  | { kind: 'none' };

export function parsePasswordRecoveryLink(url: string): PasswordRecoveryLink {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.replace(/^\/+|\/+$/g, '');
    if (!path.endsWith('reset-password') && parsed.hostname !== 'reset-password') return { kind: 'none' };
    const fragment = new URLSearchParams(parsed.hash.replace(/^#/, ''));
    const parameter = (key: string) => fragment.get(key) || parsed.searchParams.get(key) || '';
    const description = parameter('error_description') || parameter('error');
    if (description) return { kind: 'error', description };
    if (parameter('type') !== 'recovery') return { kind: 'none' };
    const accessToken = parameter('access_token');
    const refreshToken = parameter('refresh_token');
    return accessToken && refreshToken
      ? { kind: 'session', accessToken, refreshToken }
      : { kind: 'error', description: 'Missing recovery credentials.' };
  } catch {
    return { kind: 'none' };
  }
}
