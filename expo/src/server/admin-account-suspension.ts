import type { SupabaseClient } from '@supabase/supabase-js';

export type AccountStatus = 'active' | 'suspended';

async function setAuthBan(server: SupabaseClient, userId: string, status: AccountStatus): Promise<void> {
  // Supabase Auth rejects new sign-ins while banned. The database migration
  // independently revokes refresh sessions and denies surviving access JWTs.
  const { error } = await server.auth.admin.updateUserById(userId, {
    ban_duration: status === 'suspended' ? '876000h' : 'none',
  });
  if (error) throw error;
}

/** Keep failures closed when Auth and Postgres cannot commit atomically. */
export async function changeAccountStatus(
  server: SupabaseClient,
  userId: string,
  previous: AccountStatus,
  next: AccountStatus,
  save: () => Promise<void>,
): Promise<void> {
  if (previous === next) {
    // Reconcile Auth in either direction after a partial failure or concurrent
    // status change. Reapplying the desired ban state is idempotent.
    await setAuthBan(server, userId, next);
    await save();
    return;
  }
  await setAuthBan(server, userId, next);
  try { await save(); }
  catch (error) {
    // Keep the prior Auth state if the database transaction did not commit.
    try { await setAuthBan(server, userId, previous); }
    catch (rollbackError) { console.error('Account status Auth rollback failed', rollbackError); }
    throw error;
  }
}

export async function syncNewAccountSuspension(server: SupabaseClient, userId: string, status: AccountStatus): Promise<void> {
  if (status === 'suspended') await setAuthBan(server, userId, status);
}
