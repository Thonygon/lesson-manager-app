const json = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'private, no-store' } });

export async function POST(request: Request) {
  try {
    const token = (request.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
    const base = (process.env.EXPO_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || '').replace(/\/$/, '');
    const anon = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || '';
    const key = process.env.GEMINI_API_KEY || '';
    if (!token) return json({ error: 'Sign in to generate an image.' }, 401);
    if (!base || !anon || !key) return json({ error: 'Image generation is not configured.' }, 503);
    const body = await request.json() as { id?: string; kind?: 'plan' | 'worksheet' | 'exam' };
    const planId = String(body.id ?? '').trim();
    if (!planId || planId.length > 100 || !/^[a-zA-Z0-9-]+$/.test(planId)) return json({ error: 'Invalid lesson plan.' }, 400);
    const kind = body.kind === 'worksheet' || body.kind === 'exam' ? body.kind : 'plan';
    const table = kind === 'worksheet' ? 'worksheets' : kind === 'exam' ? 'quick_exams' : 'lesson_plans';
    const payloadColumn = kind === 'worksheet' ? 'worksheet_json' : kind === 'exam' ? 'exam_data' : 'plan_json';
    const levelColumn = kind === 'exam' ? 'level' : 'level_or_band';
    const headers = { apikey: anon, Authorization: `Bearer ${token}`, Accept: 'application/json' };
    const auth = await fetch(`${base}/auth/v1/user`, { headers, cache: 'no-store' });
    if (!auth.ok) return json({ error: 'Your session has expired.' }, 401);
    const user = await auth.json() as { id?: string };
    if (!user.id) return json({ error: 'Your session has expired.' }, 401);
    const url = new URL(`${base}/rest/v1/${table}`);
    url.searchParams.set('select', `id,user_id,title,subject,topic,learner_stage,${levelColumn},${payloadColumn}`);
    url.searchParams.set('id', `eq.${planId}`);
    url.searchParams.set('user_id', `eq.${user.id}`);
    url.searchParams.set('limit', '1');
    const lookup = await fetch(url, { headers, cache: 'no-store' });
    if (!lookup.ok) return json({ error: 'This lesson plan could not be loaded.' }, 503);
    const rows = await lookup.json() as Record<string, unknown>[];
    const row = rows[0];
    if (!row) return json({ error: 'Only the owner can generate an image.' }, 403);
    const plan = row[payloadColumn] && typeof row[payloadColumn] === 'object' ? row[payloadColumn] as Record<string, unknown> : {};
    const prompt = `Asset type: Classio ${kind === 'worksheet' ? 'worksheet' : kind === 'exam' ? 'exam' : 'lesson plan'} gallery cover image. Title/context: ${String(row.title || plan.title || '').slice(0, 200)}. Subject: ${String(row.subject || '').slice(0, 80)}. Topic: ${String(row.topic || '').slice(0, 120)}. Learner stage: ${String(row.learner_stage || '').slice(0, 80)}. Level/band: ${String(row[levelColumn] || '').slice(0, 40)}. Wide 16:9 modern educational illustration, one clear age-appropriate teaching scene, polished resource-library cover. Absolutely no text, letters, numbers, captions, logos, labels, or watermarks.`;
    const model = process.env.GEMINI_IMAGE_MODEL || 'gemini-3.1-flash-image-preview';
    const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(key)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }) });
    if (!response.ok) return json({ error: 'Classio could not generate the image right now.' }, 503);
    const result = await response.json() as { candidates?: { content?: { parts?: { inlineData?: { mimeType?: string; data?: string } }[] } }[] };
    const image = result.candidates?.flatMap((candidate) => candidate.content?.parts || []).find((part) => part.inlineData?.data)?.inlineData;
    if (!image?.data) return json({ error: 'The image provider returned no image.' }, 503);
    return json({ cover_image: { generator: 'classio_ai_resource_cover_v1', image_data_url: `data:${image.mimeType || 'image/png'};base64,${image.data}`, image_prompt: prompt, resource_type: kind === 'worksheet' ? 'Worksheet' : kind === 'exam' ? 'Exam' : 'Lesson plan' } });
  } catch { return json({ error: 'Classio could not generate the image.' }, 500); }
}
