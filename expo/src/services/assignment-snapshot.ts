/** Store enough structure to reopen an assigned activity when the source is private. */
export function buildAssignmentSnapshot(value: unknown, depth = 0): unknown {
  if (depth > 16) return undefined;
  if (typeof value === 'string') return value.startsWith('data:') || value.length > 100000 ? undefined : value;
  if (Array.isArray(value)) return value.slice(0, 500).map((item) => buildAssignmentSnapshot(item, depth + 1)).filter((item) => item !== undefined);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const normalized = key.toLowerCase();
    if (normalized.includes('base64') || normalized.includes('image_data') || normalized.includes('thumbnail')) return [];
    const safe = buildAssignmentSnapshot(child, depth + 1);
    return safe === undefined ? [] : [[key, safe]];
  }));
  return value;
}
