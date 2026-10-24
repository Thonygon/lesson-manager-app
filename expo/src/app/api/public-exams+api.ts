import { createClient } from '@supabase/supabase-js';

const columns = 'id,title,subject,topic,learner_stage,level,exam_length,exercise_types,plan_language,student_material_language,is_public,status,created_at,updated_at';
const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'public, max-age=60' } });

export async function GET(request: Request) {
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const key = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !key) return json({ error: 'Public exams are unavailable.' }, 503);

  const params = new URL(request.url).searchParams;
  const id = params.get('id');
  const page = Number(params.get('page') || 1);
  const limit = Number(params.get('limit') || 120);
  if (id && !/^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[1-9]\d*)$/i.test(id)) {
    return json({ error: 'Invalid exam ID.' }, 400);
  }
  if (!id && (!Number.isSafeInteger(page) || page < 1 || page > 10000 || !Number.isSafeInteger(limit) || limit < 1 || limit > 120)) {
    return json({ error: 'Invalid exam page.' }, 400);
  }
  try {
    const client = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
    const query = client.from('quick_exams').select(id ? `${columns},exam_data,answer_key` : columns).eq('is_public', true).neq('status', 'archived');
    if (id) {
      const { data, error } = await query.eq('id', id).maybeSingle();
      if (error) throw error;
      return data ? json({ exam: data }) : json({ error: 'Exam not found.' }, 404);
    }
    const offset = (page - 1) * limit;
    const { data, error } = await query.order('updated_at', { ascending: false }).order('id', { ascending: false }).range(offset, offset + limit);
    if (error) throw error;
    return json({ exams: (data ?? []).slice(0, limit), hasMore: (data ?? []).length > limit, page });
  } catch (error) {
    console.error('Public exam load failed', error);
    return json({ error: 'Public exams could not be loaded.' }, 502);
  }
}
