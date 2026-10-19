import type { SupabaseClient } from '@supabase/supabase-js';

const PAGE_SIZE = 500;
const MAX_ROWS = 20000;

/** Read the full teacher history in bounded pages, or fail instead of returning a partial ledger. */
export async function readTeacherHistory(
  client: SupabaseClient,
  teacherId: string,
  table: 'classes' | 'payments',
  columns: string,
  dateColumn: 'lesson_date' | 'payment_date',
  student?: string,
): Promise<Record<string, unknown>[]> {
  const rows: Record<string, unknown>[] = [];
  for (let offset = 0; offset <= MAX_ROWS;) {
    let query = client.from(table).select(columns).eq('user_id', teacherId);
    if (student) query = query.eq('student', student);
    const { data, error } = await query
      .order(dateColumn, { ascending: false }).order('id', { ascending: false })
      .range(offset, offset + PAGE_SIZE - 1);
    if (error) throw error;
    const page = (data ?? []) as unknown as Record<string, unknown>[];
    if (!page.length) return rows;
    if (rows.length + page.length > MAX_ROWS) throw new Error(`${table} history exceeds the safe 20,000-row limit; analytics cannot be calculated from partial data.`);
    rows.push(...page);
    offset += page.length;
  }
  throw new Error(`${table} history could not be read completely.`);
}
