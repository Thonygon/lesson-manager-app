export function youtubeVideoId(value: string) {
  const raw = value.trim();
  try {
    const url = new URL(raw);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return '';
    if (!['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'www.youtube-nocookie.com', 'youtu.be', 'www.youtu.be'].includes(host)) return '';
    const id = host.endsWith('youtu.be') ? url.pathname.slice(1) : url.pathname === '/watch' ? url.searchParams.get('v') || '' : /^\/(embed|shorts)\//.test(url.pathname) ? url.pathname.split('/')[2] || '' : '';
    return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : '';
  } catch { return ''; }
}

export function publicVideoId(videoId: unknown, url: unknown) {
  const stored = String(videoId || '').trim();
  return /^[A-Za-z0-9_-]{11}$/.test(stored) ? stored : youtubeVideoId(String(url || ''));
}
