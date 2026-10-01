import type { Session } from '@supabase/supabase-js';

import type { AuthState } from '@/types/auth';

export function authSessionTransition(current: AuthState, session: Session | null, refreshProfile = false) {
  if (!session) {
    return {
      state: { ...current, configured: true, loading: false, session: null, user: null, profile: null, error: null },
      loadProfile: false,
    };
  }

  const sameUser = current.user?.id === session.user.id;
  return {
    state: {
      ...current,
      configured: true,
      loading: sameUser ? current.loading : true,
      session,
      user: session.user,
      profile: sameUser ? current.profile : null,
      error: null,
    },
    loadProfile: refreshProfile || !sameUser || !current.profile,
  };
}
