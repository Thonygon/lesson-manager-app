import type { ClassioRecord } from '@/services/classio-data';

const text = (value: unknown) => typeof value === 'string' || typeof value === 'number' ? String(value).trim() : '';

// Older programs can contain a second copy of a unit's topics with new topic
// numbers. Keep the first row (and its stable ID used by assignments/progress).
export function uniqueProgramTopics(rows: ClassioRecord[]): ClassioRecord[] {
  const seen = new Set<string>();
  return rows.filter((topic) => {
    const title = text(topic.title).normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ');
    if (!title) return true;
    const key = `${Number(topic.unit_number || 0)}:${title}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function programTopics(program: ClassioRecord, rows: ClassioRecord[]): ClassioRecord[] {
  const ordered = [...rows].sort((a, b) => Number(a.unit_number || 0) - Number(b.unit_number || 0) || Number(a.topic_number || 0) - Number(b.topic_number || 0));
  // Streamlit attaches a topic only when its foreign-key unit and denormalized
  // unit number agree. Legacy rows can otherwise appear under the wrong unit.
  const hasUnitMetadata = ordered.some((topic) => topic.unit && typeof topic.unit === 'object' && !Array.isArray(topic.unit));
  const valid = uniqueProgramTopics(!hasUnitMetadata ? ordered : ordered.filter((topic) => {
    const unit = topic.unit && typeof topic.unit === 'object' && !Array.isArray(topic.unit) ? topic.unit as ClassioRecord : null;
    return unit && text(unit.id) === text(topic.unit_id) && text(unit.program_id) === text(topic.program_id) && Number(unit.unit_number) === Number(topic.unit_number);
  }));
  const document = program.program_data && typeof program.program_data === 'object' && !Array.isArray(program.program_data) ? program.program_data as ClassioRecord : {};
  const documentUnits = Array.isArray(document.units) ? document.units.filter((unit): unit is ClassioRecord => Boolean(unit && typeof unit === 'object' && !Array.isArray(unit))) : [];
  if (!documentUnits.some((unit) => Array.isArray(unit.topics) && unit.topics.length)) return valid;
  const seenUnits = new Set<number>();
  const merged: ClassioRecord[] = [];
  for (const [unitIndex, unit] of documentUnits.entries()) {
    const unitNumber = Number(unit.unit_number || unitIndex + 1);
    seenUnits.add(unitNumber);
    const baseTopics = valid.filter((topic) => Number(topic.unit_number) === unitNumber);
    const enrichedTopics = uniqueProgramTopics(Array.isArray(unit.topics) ? unit.topics.filter((topic): topic is ClassioRecord => Boolean(topic && typeof topic === 'object' && !Array.isArray(topic))).map((topic) => ({ ...topic, unit_number: unitNumber })) : []);
    if (!enrichedTopics.length) { merged.push(...baseTopics); continue; }
    // Python's _merge_program_unit(..., prefer_enriched_topics=True) uses the
    // document's topic count and overlays its text onto positional DB rows.
    enrichedTopics.forEach((topic, index) => {
      const base = baseTopics[index] ?? {};
      merged.push({ ...base, ...topic, id: base.id || topic.topic_id || `${text(program.id)}:${unitNumber}:${index + 1}`, program_id: base.program_id || program.id, unit_id: base.unit_id || unit.unit_id, unit_number: unitNumber, topic_number: index + 1 });
    });
  }
  merged.push(...valid.filter((topic) => !seenUnits.has(Number(topic.unit_number))));
  return uniqueProgramTopics(merged);
}
