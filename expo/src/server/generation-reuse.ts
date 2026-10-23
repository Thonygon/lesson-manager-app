export type GenerationKind = 'plan' | 'worksheet' | 'exam' | 'program';
export type GenerationMatch = { id: string; kind: GenerationKind; title: string; topic: string; source: 'own' | 'community'; bucket: 'very_close' | 'close' | 'related'; score: number };
type SearchInput = { kind: GenerationKind; subject: string; topic: string; stage: string; level: string; lessonPurpose?: string; worksheetType?: string; exerciseTypes?: string[]; programTrack?: string; examTarget?: string };
type StoredRow = Record<string, unknown>;

const sources: Record<GenerationKind, { table: string; level: string; subtype: string; fields: string }> = {
  plan: { table: 'lesson_plans', level: 'level_or_band', subtype: 'lesson_purpose', fields: 'id,user_id,is_public,status,title,topic,subject,learner_stage,level_or_band,lesson_purpose' },
  worksheet: { table: 'worksheets', level: 'level_or_band', subtype: 'worksheet_type', fields: 'id,user_id,is_public,status,title,topic,subject,learner_stage,level_or_band,worksheet_type' },
  exam: { table: 'quick_exams', level: 'level', subtype: 'exercise_types', fields: 'id,user_id,is_public,status,title,topic,subject,learner_stage,level,exercise_types' },
  program: { table: 'learning_programs', level: 'level_or_band', subtype: '', fields: 'id,user_id,is_public,status,title,subject,learner_stage,level_or_band,builder_config' },
};
const normalize = (value: unknown) => String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[_\W]+/g, ' ').trim();
const tokens = (value: unknown) => new Set(normalize(value).split(' ').filter((token) => token.length > 2));
function topicFit(left: string, right: string) {
  const a = normalize(left); const b = normalize(right);
  if (!a || !b) return 0;
  if (a === b) return 1;
  const x = tokens(a); const y = tokens(b);
  const overlap = [...x].filter((item) => y.has(item)).length;
  return Math.max(a.includes(b) || b.includes(a) ? 0.78 : 0, overlap / Math.max(1, Math.min(x.size, y.size)));
}
export function classifyGenerationMatch(input: SearchInput, row: StoredRow, ownerId: string): GenerationMatch | null {
  const source = sources[input.kind];
  if (!source || normalize(row.status) === 'archived' || normalize(row.subject) !== normalize(input.subject) || normalize(row.learner_stage) !== normalize(input.stage)) return null;
  const programTopic = row.builder_config && typeof row.builder_config === 'object' ? (row.builder_config as StoredRow).topic : '';
  const config = row.builder_config && typeof row.builder_config === 'object' ? row.builder_config as StoredRow : {};
  const sameTrack = normalize(config.program_track || 'general_language') === normalize(input.programTrack || 'general_language');
  const sameTarget = normalize(config.exam_prep_target || config.exam_target || '') === normalize(input.examTarget || '');
  const levelMatch = normalize(row[source.level]) === normalize(input.level);
  if (input.kind === 'program' && (!levelMatch || !sameTrack || !sameTarget)) return null;
  const fit = input.kind === 'program' && !input.topic.trim() ? sameTrack && sameTarget ? 1 : 0 : topicFit(input.topic, String(row.topic || programTopic || row.title || ''));
  if (fit < 0.5) return null;
  const subtypeMatch = input.kind === 'program' ? true : input.kind === 'exam'
    ? (input.exerciseTypes || []).some((value) => Array.isArray(row.exercise_types) && row.exercise_types.some((stored) => normalize(stored) === normalize(value)))
    : normalize(row[source.subtype]) === normalize(input.kind === 'plan' ? input.lessonPurpose : input.worksheetType);
  const score = fit + (levelMatch ? 0.15 : 0) + (subtypeMatch ? 0.15 : 0);
  const id = String(row.id || '').trim();
  if (!/^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[1-9]\d*)$/i.test(id)) return null;
  const bucket = fit >= 0.95 && levelMatch && subtypeMatch ? 'very_close' : fit >= 0.7 && (levelMatch || subtypeMatch) ? 'close' : 'related';
  return { id, kind: input.kind, title: String(row.title || ''), topic: String(row.topic || programTopic || ''), source: row.user_id === ownerId ? 'own' : 'community', bucket, score };
}

export async function findGenerationMatches(base: string, key: string, token: string, ownerId: string, input: SearchInput): Promise<GenerationMatch[]> {
  const source = sources[input.kind];
  if (!source) return [];
  if (!base || !key) throw new Error('Existing resources could not be checked.');
  const query = new URL(`${base.replace(/\/$/, '')}/rest/v1/${source.table}`);
  query.searchParams.set('select', source.fields);
  query.searchParams.set('subject', `ilike.${input.subject.replace(/[%*,()]/g, '')}`);
  query.searchParams.set('or', ownerId ? `(user_id.eq.${ownerId},is_public.eq.true)` : '(is_public.eq.true)');
  query.searchParams.set('order', 'created_at.desc');
  query.searchParams.set('limit', '500');
  const headers: Record<string, string> = { apikey: key, Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const getRows = async (url: URL) => {
    const response = await fetch(url, { headers });
    if (!response.ok) throw new Error('Existing resources could not be checked.');
    const rows = await response.json() as StoredRow[];
    if (!Array.isArray(rows)) throw new Error('Existing resources could not be checked.');
    return rows;
  };
  const uniqueRows = await getRows(query);
  const priority = { very_close: 0, close: 1, related: 2 };
  return uniqueRows.map((row) => classifyGenerationMatch(input, row, ownerId)).filter((row): row is GenerationMatch => Boolean(row))
    .sort((a, b) => priority[a.bucket] - priority[b.bucket] || (a.source === b.source ? b.score - a.score : a.source === 'own' ? -1 : 1)).slice(0, 3);
}
