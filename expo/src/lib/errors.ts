export function messageOf(reason: unknown, fallback: string) {
  if (reason instanceof Error && reason.message.trim()) return reason.message;
  if (reason && typeof reason === 'object') {
    const row = reason as Record<string, unknown>;
    for (const key of ['message', 'details', 'hint', 'error_description', 'error']) {
      const value = row[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }
  }
  if (typeof reason === 'string' && reason.trim()) return reason.trim();
  return fallback;
}
