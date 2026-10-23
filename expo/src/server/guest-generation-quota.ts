const COOKIE_NAME = 'classio_guest_id';

async function digest(value: string, secret: string) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const bytes = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value)));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export async function reserveGuestGeneration(request: Request, config: { base: string; serverKey: string; secret: string }) {
  if (!config.base || !config.serverKey || !config.secret) throw new Error('Guest quota is not configured.');
  // EAS Hosting supplies X-Real-IP. Do not trust client-supplied forwarding chains.
  const ip = request.headers.get('x-real-ip')?.trim() || '';
  if (!ip || ip.length > 64 || !/^[a-fA-F0-9:.]+$/.test(ip)) throw new Error('Client IP is unavailable.');
  const existing = request.headers.get('cookie')?.match(/(?:^|;\s*)classio_guest_id=([a-f0-9]{64})/i)?.[1]?.toLowerCase();
  const cookieId = existing || Array.from(crypto.getRandomValues(new Uint8Array(32)), (byte) => byte.toString(16).padStart(2, '0')).join('');
  const [ipHash, cookieHash] = await Promise.all([digest(`ip:${ip}`, config.secret), digest(`cookie:${cookieId}`, config.secret)]);
  const response = await fetch(`${config.base.replace(/\/$/, '')}/rest/v1/rpc/classio_reserve_guest_generation`, {
    method: 'POST',
    headers: { apikey: config.serverKey, Authorization: `Bearer ${config.serverKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ p_ip_hash: ipHash, p_cookie_hash: cookieHash }),
  });
  if (!response.ok) throw new Error(`Guest quota reservation failed (${response.status}).`);
  const result = await response.json() as { allowed?: boolean; used?: number };
  if (typeof result.allowed !== 'boolean') throw new Error('Guest quota returned an invalid response.');
  return { allowed: result.allowed, used: Number(result.used || 0), cookie: `${COOKIE_NAME}=${cookieId}; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Lax` };
}
