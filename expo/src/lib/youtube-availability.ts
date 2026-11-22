import { useEffect, useState } from 'react';
import { hostingApiUrl } from '@/lib/hosting-api-url';

type VideoAvailability = 'checking' | 'available' | 'unavailable' | 'unknown';
const cache = new Map<string, { status: VideoAvailability; until: number }>();

export function useYoutubeAvailability(videoId: string): VideoAvailability {
  const [result, setResult] = useState<{ id: string; status: VideoAvailability }>({ id: '', status: 'checking' });
  const valid = /^[A-Za-z0-9_-]{11}$/.test(videoId);
  const status = !valid ? 'unavailable' : result.id === videoId ? result.status : 'checking';
  useEffect(() => {
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) return;
    const existing = cache.get(videoId);
    if (existing && existing.until > Date.now()) {
      void Promise.resolve().then(() => setResult({ id: videoId, status: existing.status }));
      return;
    }
    let active = true;
    const controller = new AbortController();
    void fetch(hostingApiUrl(`/api/video-availability?id=${encodeURIComponent(videoId)}`), { signal: controller.signal })
      .then(async (response) => response.ok ? await response.json() as { status?: string } : { status: 'unknown' })
      .then((body) => {
        const next: VideoAvailability = body.status === 'available' || body.status === 'unavailable' ? body.status : 'unknown';
        cache.set(videoId, { status: next, until: Date.now() + (next === 'unknown' ? 30_000 : 300_000) });
        if (active) setResult({ id: videoId, status: next });
      }).catch(() => { if (active) setResult({ id: videoId, status: 'unknown' }); });
    return () => { active = false; controller.abort(); };
  }, [videoId]);
  return status;
}
