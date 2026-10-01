import type { ClassioRecord } from '@/services/classio-data';

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const key = (value: unknown) => String(value ?? '').trim().toLocaleLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
const id = (value: unknown) => String(value ?? '').trim();
const topicId = (value: unknown) => Number(value) || 0;

export function assignmentTopicReferenceTarget(score: unknown, status: unknown) {
  const state = key(status);
  const normalizedScore = clamp((Number(score) || 0) / 100);
  if (state === 'graded' || state === 'completed') return 0.38 + 0.62 * normalizedScore;
  if (state === 'submitted' || state === 'started') return 0.44;
  if (state === 'assigned' || state === 'overdue') return 0.28;
  return 0.18;
}

const eventTargets: Record<string, number> = {
  prefill: 0.2, resource_opened: 0.32, resource_assigned: 0.55,
  assignment_created: 0.74, teacher_marked_done: 0.78,
  student_started: 0.84, student_completed: 0.92, student_improved: 1,
};

/** Python's explicit topic-resource model over student-visible reference rows. */
export function buildStudentTopicAlignment(assignments: ClassioRecord[] = [], events: ClassioRecord[] = [], videoLinks: ClassioRecord[] = [], now = Date.now()) {
  const cutoff = now - 180 * 24 * 60 * 60 * 1000;
  const pairs = new Map<string, number[]>();
  const kindTopics = new Map<string, number[]>();
  const resourceTopics = new Map<string, Set<number>>();
  const directPairs = new Set<string>();
  const add = (kind: string, resource: string, topic: number, target: number, kindTarget = target) => {
    const resourceKey = `${kind}:${resource}`;
    const pairKey = `${resourceKey}:${topic}`;
    const kindTopicKey = `${kind}:${topic}`;
    pairs.set(pairKey, [...(pairs.get(pairKey) || []), target]);
    kindTopics.set(kindTopicKey, [...(kindTopics.get(kindTopicKey) || []), kindTarget]);
    const topics = resourceTopics.get(resourceKey) || new Set<number>();
    topics.add(topic);
    resourceTopics.set(resourceKey, topics);
  };
  for (const row of assignments) {
    const updatedAt = Date.parse(String(row.updated_at || ''));
    if (Number.isFinite(updatedAt) && updatedAt < cutoff) continue;
    const rawKind = key(row.assignment_type);
    const kind = rawKind === 'lesson_plan_topic' ? 'plan' : rawKind;
    const resource = id(row.source_record_id);
    const topic = topicId(row.learning_program_topic_id);
    if (!kind || !resource || ['0', 'None', 'nan'].includes(resource) || topic <= 0 || key(row.status) === 'archived') continue;
    add(kind, resource, topic, assignmentTopicReferenceTarget(row.score_pct, row.status));
  }
  for (const row of events) {
    const createdAt = Date.parse(String(row.created_at || ''));
    if (Number.isFinite(createdAt) && createdAt < cutoff) continue;
    const kind = key(row.resource_kind);
    const resource = id(row.resource_record_id);
    const topic = topicId(row.learning_program_topic_id);
    if (!kind || !resource || ['0', 'None', 'nan'].includes(resource) || topic <= 0) continue;
    add(kind, resource, topic, Math.max(eventTargets[key(row.event_type)] ?? 0.1, clamp(Number(row.event_weight) || 0)));
  }
  for (const row of videoLinks) {
    const resource = id(row.video_id);
    const topic = topicId(row.topic_id);
    if (!resource || topic <= 0) continue;
    const signature = `video:${resource}:${topic}`;
    directPairs.add(signature);
    add('video', resource, topic, 1, 0.96);
  }
  return (kindValue: unknown, resourceValue: unknown, topicIds: Iterable<number>) => {
    const kind = key(kindValue);
    const resourceKey = `${kind}:${id(resourceValue)}`;
    let explicitTopicMatch = 0;
    let explicitTopicSupport = 0;
    let topicKindPrior = 0;
    let directTopicLink = 0;
    for (const topic of topicIds) {
      if (directPairs.has(`${resourceKey}:${topic}`)) directTopicLink = 1;
      const samples = pairs.get(`${resourceKey}:${topic}`) || [];
      const kindSamples = kindTopics.get(`${kind}:${topic}`) || [];
      if (samples.length) explicitTopicMatch = Math.max(explicitTopicMatch, samples.reduce((a, b) => a + b, 0) / samples.length);
      explicitTopicSupport = Math.max(explicitTopicSupport, clamp(samples.length / 4));
      if (kindSamples.length) topicKindPrior = Math.max(topicKindPrior, kindSamples.reduce((a, b) => a + b, 0) / kindSamples.length);
    }
    const span = resourceTopics.get(resourceKey)?.size || 0;
    return {
      explicitTopicMatch, explicitTopicSupport, topicKindPrior,
      topicMatchAmbiguity: explicitTopicMatch < 0.45 && !directTopicLink ? clamp(Math.max(0, span - 1) / 4) : 0,
      directTopicLink,
    };
  };
}
