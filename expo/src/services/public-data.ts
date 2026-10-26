import { requireSupabase } from '@/lib/supabase';
import { hostingApiUrl } from '@/lib/hosting-api-url';

export type PublicResourceKind = 'program' | 'plan' | 'worksheet' | 'exam' | 'video';

export type PublicResource = {
  id: string;
  kind: PublicResourceKind;
  title: string;
  subject: string;
  topic: string;
  stage: string;
  level: string;
  author: string;
  description: string;
  imageUrl: string;
  createdAt: string;
  raw: Record<string, unknown>;
};

const DEFINITIONS: Record<PublicResourceKind, { table: string; columns: string; order: string }> = {
  program: { table: 'learning_programs', columns: 'id,title,subject,custom_subject_name,learner_stage,level_or_band,program_overview,is_public,status,total_units,total_topics,created_at,updated_at', order: 'updated_at' },
  plan: { table: 'lesson_plans', columns: 'id,title,subject,topic,learner_stage,level_or_band,lesson_purpose,author_name,subject_display,is_public,status,created_at', order: 'created_at' },
  worksheet: { table: 'worksheets', columns: 'id,title,subject,topic,learner_stage,level_or_band,worksheet_type,source_type,plan_language,student_material_language,author_name,subject_display,is_public,status,created_at,updated_at', order: 'updated_at' },
  exam: { table: 'quick_exams', columns: 'id,title,subject,topic,learner_stage,level,exam_length,exercise_types,plan_language,student_material_language,is_public,status,created_at,updated_at', order: 'updated_at' },
  video: { table: 'videos', columns: 'id,title,subject,custom_subject_name,topic,description,video_id,youtube_url,thumbnail_url,learner_stage,level_or_band,student_material_language,is_public,status,created_at,updated_at', order: 'updated_at' },
};

function text(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

const DIRECT_IMAGE_KEYS = [
  'image_data_url', 'data_url', 'data_uri', 'dataUri', 'image_url', 'imageUrl',
  'thumbnail_url', 'thumbnailUrl', 'cover_image_url', 'coverImageUrl',
  'hero_image_url', 'heroImageUrl', 'src', 'url', 'uri',
];
const BASE64_IMAGE_KEYS = ['b64_json', 'image_base64', 'cover_image_base64', 'thumbnail_base64', 'base64'];
const NESTED_IMAGE_KEYS = [
  'cover_image', 'visual_support', 'hero_image', 'image', 'thumbnail', 'program_data',
  'program_json', 'plan_json', 'lesson_plan_json', 'worksheet_json', 'exam_data',
  'content_snapshot',
];
const IMAGE_ARRAY_KEYS = ['visual_supports', 'sections', 'activities', 'units', 'topics', 'items', 'images'];

/** Mirrors the Streamlit gallery's tolerant lookup so existing generated artwork is reused. */
export function extractResourceImageUrl(payload: unknown, depth = 0): string {
  if (!payload || depth > 7) return '';
  if (typeof payload === 'string') {
    const value = payload.trim();
    if (/^(data:image\/|https?:\/\/)/i.test(value)) return value;
    if (value.startsWith('{') || value.startsWith('[')) { try { return extractResourceImageUrl(JSON.parse(value), depth + 1); } catch { return ''; } }
    return '';
  }
  if (Array.isArray(payload)) {
    for (const item of payload) {
      const found = extractResourceImageUrl(item, depth + 1);
      if (found) return found;
    }
    return '';
  }
  if (typeof payload !== 'object') return '';
  const record = payload as Record<string, unknown>;
  for (const key of DIRECT_IMAGE_KEYS) {
    const found = extractResourceImageUrl(record[key], depth + 1);
    if (found) return found;
  }
  for (const key of BASE64_IMAGE_KEYS) {
    const value = text(record[key]);
    if (value) return value.startsWith('data:image/') ? value : `data:image/png;base64,${value}`;
  }
  for (const key of [...NESTED_IMAGE_KEYS, ...IMAGE_ARRAY_KEYS]) {
    const found = extractResourceImageUrl(record[key], depth + 1);
    if (found) return found;
  }
  return '';
}

function normalize(kind: PublicResourceKind, row: Record<string, unknown>): PublicResource {
  return {
    id: String(row.id ?? `${kind}-${Math.random()}`),
    kind,
    title: text(row.title) || 'Untitled resource',
    subject: text(row.subject_display) || text(row.custom_subject_name) || text(row.subject),
    topic: text(row.topic) || text(row.lesson_purpose),
    stage: text(row.learner_stage),
    level: text(row.level_or_band) || text(row.level),
    author: text(row.author_name),
    description:
      text(row.program_overview) || text(row.description) || text(row.lesson_purpose) || text(row.worksheet_type) || text(row.exam_length),
    imageUrl: extractResourceImageUrl(row),
    createdAt: text(row.created_at),
    raw: row,
  };
}

async function publicExamRows(id?: string): Promise<Record<string, unknown>[]> {
  const response = await fetch(hostingApiUrl(`/api/public-exams${id ? `?id=${encodeURIComponent(id)}` : ''}`));
  if (!response.ok) throw new Error(`Unable to load public exams (${response.status}).`);
  const payload = await response.json() as { exam?: Record<string, unknown>; exams?: Record<string, unknown>[] };
  return id ? payload.exam ? [payload.exam] : [] : payload.exams ?? [];
}

export async function getExplorerPublicExamPage(page: number, limit = 60): Promise<{ resources: PublicResource[]; hasMore: boolean }> {
  const response = await fetch(hostingApiUrl(`/api/public-exams?page=${page}&limit=${limit}`));
  if (!response.ok) throw new Error(`Unable to load public exams (${response.status}).`);
  const payload = await response.json() as { exams?: Record<string, unknown>[]; hasMore?: boolean };
  return { resources: (payload.exams ?? []).map((row) => normalize('exam', row)), hasMore: Boolean(payload.hasMore) };
}

export async function getPublicResources(kinds: PublicResourceKind[] = Object.keys(DEFINITIONS) as PublicResourceKind[], perKindLimit = 60): Promise<PublicResource[]> {
  const client = requireSupabase();
  const boundedLimit = Math.max(1, Math.min(120, Math.floor(perKindLimit) || 60));
  const results = await Promise.all(
    kinds.map(async (kind) => {
      if (kind === 'exam') {
        return (await publicExamRows()).slice(0, boundedLimit).map((row) => normalize(kind, row));
      }
      const definition = DEFINITIONS[kind];
      const request = client
        .from(definition.table)
        .select(definition.columns)
        .eq('is_public', true)
        .neq('status', 'archived')
        .order(definition.order, { ascending: false })
        .limit(boundedLimit);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const { data, error } = await request.abortSignal(controller.signal);
        if (error) throw new Error(`Unable to load ${kind} resources: ${error.message}`);
        return (data ?? []).map((row) => normalize(kind, row as unknown as Record<string, unknown>));
      } catch (reason) {
        if (controller.signal.aborted) throw new Error(`Timed out loading ${kind} resources.`);
        throw reason;
      } finally {
        clearTimeout(timeout);
      }
    }),
  );
  return results.flat();
}

/** Explorer keeps available categories visible when one public query fails. */
export async function getExplorerPublicResources(perKindLimit = 60): Promise<{ resources: PublicResource[]; failedKinds: PublicResourceKind[]; examHasMore: boolean }> {
  const kinds = Object.keys(DEFINITIONS) as PublicResourceKind[];
  const results = await Promise.allSettled(kinds.map((kind) => kind === 'exam' ? getExplorerPublicExamPage(1, perKindLimit) : getPublicResources([kind], perKindLimit).then((resources) => ({ resources, hasMore: false }))));
  const examResult = results[kinds.indexOf('exam')];
  return {
    resources: results.flatMap((result) => result.status === 'fulfilled' ? result.value.resources : []),
    failedKinds: kinds.filter((_, index) => results[index].status === 'rejected'),
    examHasMore: examResult.status === 'fulfilled' && examResult.value.hasMore,
  };
}

export async function getPublicResourceDetail(kind: PublicResourceKind, id: string): Promise<PublicResource> {
  if (kind === 'exam') {
    const [row] = await publicExamRows(id);
    if (!row) throw new Error('This public resource is no longer available.');
    return normalize(kind, row);
  }
  const definition = DEFINITIONS[kind];
  const client = requireSupabase();
  const { data, error } = await client.from(definition.table).select('*').eq('id', id).eq('is_public', true).neq('status', 'archived').maybeSingle();
  if (error) throw error;
  if (!data) throw new Error('This public resource is no longer available.');
  if (kind !== 'program') return normalize(kind, data as unknown as Record<string, unknown>);
  const [unitResult, topicResult] = await Promise.all([
    client.from('learning_program_units').select('*').eq('program_id', id).order('unit_number'),
    client.from('learning_program_topics').select('*').eq('program_id', id).order('unit_number').order('topic_number'),
  ]);
  if (unitResult.error || topicResult.error) throw unitResult.error ?? topicResult.error;
  return normalize(kind, { ...(data as Record<string, unknown>), units: unitResult.data ?? [], topics: topicResult.data ?? [] });
}

export async function getPublicResourcePreviewImages(kind: PublicResourceKind, ids: string[]): Promise<Record<string, string>> {
  if (!ids.length || kind === 'video') return {};
  if (kind === 'exam') return {};
  const payloadColumn: Record<Exclude<PublicResourceKind, 'video'>, string> = { program: 'program_data', plan: 'plan_json', worksheet: 'worksheet_json', exam: 'exam_data' };
  const { data, error } = await requireSupabase().from(DEFINITIONS[kind].table).select(`id,${payloadColumn[kind]}`).in('id', ids).eq('is_public', true);
  if (error) return {};
  return Object.fromEntries(((data ?? []) as unknown as Record<string, unknown>[]).flatMap((row) => { const imageUrl = extractResourceImageUrl(row); return imageUrl ? [[String(row.id), imageUrl]] : []; }));
}
