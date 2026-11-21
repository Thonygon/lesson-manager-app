/** A bounded, public metadata check. Never send account or learner data to YouTube. */
export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get('id') || '';
  if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return Response.json({ status: 'unavailable' }, { status: 400 });
  try {
    const url = `https://www.youtube.com/oembed?url=${encodeURIComponent(`https://www.youtube.com/watch?v=${id}`)}&format=json`;
    const response = await fetch(url, { signal: AbortSignal.timeout(5000), headers: { Accept: 'application/json' } });
    const status = response.ok ? 'available' : response.status === 404 ? 'unavailable' : 'unknown';
    return Response.json({ status }, { headers: { 'Cache-Control': status === 'unknown' ? 'public, max-age=30' : 'public, max-age=300' } });
  } catch {
    // Network or provider failures must not falsely label a playable video removed.
    return Response.json({ status: 'unknown' }, { headers: { 'Cache-Control': 'public, max-age=30' } });
  }
}
