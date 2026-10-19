import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'public, max-age=60' } });

export async function GET(request: Request) {
  const id = Number(new URL(request.url).searchParams.get('programId'));
  if (!Number.isSafeInteger(id) || id <= 0) return json({ videos: [] }, 400);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const key = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !key) return json({ videos: [] }, 503);
  try {
    const client = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: program, error: programError } = await client.from('learning_programs').select('id').eq('id', id).eq('is_public', true).neq('status', 'archived').maybeSingle();
    if (programError) throw programError;
    if (!program) return json({ videos: [] }, 404);
    const { data: links, error: linkError } = await client.from('learning_program_topic_videos').select('topic_id,video_id').eq('program_id', id).limit(300);
    if (linkError) throw linkError;
    const ids = [...new Set((links || []).map((link) => Number(link.video_id)).filter((value) => value > 0))];
    if (!ids.length) return json({ videos: [] });
    const { data: videos, error: videoError } = await client.from('videos').select('id,title,youtube_url,video_id').in('id', ids).eq('is_public', true).neq('status', 'archived');
    if (videoError) throw videoError;
    const lookup = new Map((videos || []).map((video) => [Number(video.id), video]));
    return json({ videos: (links || []).flatMap((link) => { const video = lookup.get(Number(link.video_id)); if (!video) return []; return [{ id: String(video.id), title: String(video.title || ''), topicId: String(link.topic_id), url: String(video.youtube_url || (video.video_id ? `https://www.youtube.com/watch?v=${video.video_id}` : '')) }]; }) });
  } catch { return json({ videos: [] }, 502); }
}
