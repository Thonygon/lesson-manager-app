import type { Session } from '@supabase/supabase-js';
import { createContext, type PropsWithChildren, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { authSessionTransition } from '@/lib/auth-session-transition';
import { supabase } from '@/lib/supabase';
import type { AuthState, ClassioProfile } from '@/types/auth';

type AuthContextValue = AuthState & {
  refreshProfile: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<string | null>;
  signInWithMagicLink: (email: string) => Promise<string | null>;
  signInWithGoogle: () => Promise<string | null>;
  signInWithGoogleIdToken: (token: string, nonce: string) => Promise<string | null>;
  signUp: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
};

const initialState: AuthState = {
  // Keep the server-rendered and first browser render identical. The browser
  // marks Supabase configured after hydration, when storage is available.
  // Loading must start true: on a cold tab resume the persisted Supabase
  // session is asynchronous. A false value briefly rendered /sign-in, whose
  // authenticated redirect then discarded the requested route for /home.
  configured: false,
  loading: true,
  session: null,
  user: null,
  profile: null,
  error: null,
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadProfile(session: Session | null): Promise<ClassioProfile | null> {
  if (!supabase || !session?.user.id) {
    return null;
  }

  const { data, error } = await supabase
    .from('profiles')
    .select(
      'user_id,email,display_name,username,avatar_url,role,primary_role,can_teach,can_study,last_active_mode,onboarding_completed,login_count',
    )
    .eq('user_id', session.user.id)
    .maybeSingle();

  if (error) {
    throw error;
  }

  return data as ClassioProfile | null;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<AuthState>(initialState);
  const stateRef = useRef<AuthState>(initialState);
  const profileRequest = useRef(0);

  const commitState = useCallback((next: AuthState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const applySession = useCallback(async (session: Session | null, refreshProfile = false) => {
    const transition = authSessionTransition(stateRef.current, session, refreshProfile);
    commitState(transition.state);
    if (!transition.loadProfile) {
      if (!session) profileRequest.current += 1;
      return;
    }
    const request = ++profileRequest.current;
    try {
      const profile = await loadProfile(session);
      if (request !== profileRequest.current) return;
      commitState({ ...stateRef.current, loading: false, profile });
    } catch (error) {
      if (request !== profileRequest.current) return;
      commitState({ ...stateRef.current,
        loading: false,
        profile: null,
        error: error instanceof Error ? error.message : 'Unable to load the Classio profile.',
      });
    }
  }, [commitState]);

  useEffect(() => {
    if (!supabase) {
      commitState({ ...stateRef.current, configured: false, loading: false });
      return;
    }

    // INITIAL_SESSION resolves persisted auth once. Repeating getSession here
    // races that event and can discard a route reached during restoration.
    let active = true;
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      // Supabase invokes this callback while its auth lock is held. Defer the
      // profile query so sign-in can settle before we read from the client.
      setTimeout(() => { if (active) void applySession(session, event === 'USER_UPDATED'); }, 0);
    });
    return () => { active = false; profileRequest.current += 1; data.subscription.unsubscribe(); };
  }, [applySession, commitState]);

  const refreshProfile = useCallback(async () => applySession(stateRef.current.session, true), [applySession]);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) return 'Supabase is not configured.';
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim().toLowerCase(), password });
    return error?.message ?? null;
  }, []);

  const signInWithMagicLink = useCallback(async (email: string) => {
    if (!supabase) return 'Supabase is not configured.';
    const emailRedirectTo = typeof window === 'undefined' ? undefined : `${window.location.origin}/home`;
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim().toLowerCase(),
      options: { emailRedirectTo, shouldCreateUser: false },
    });
    return error?.message ?? null;
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabase) return 'Supabase is not configured.';
    const emailRedirectTo = typeof window === 'undefined' ? undefined : `${window.location.origin}/home`;
    const { error } = await supabase.auth.signUp({
      email: email.trim().toLowerCase(),
      password,
      options: { emailRedirectTo },
    });
    return error?.message ?? null;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!supabase) return 'Supabase is not configured.';
    const redirectTo = typeof window === 'undefined' ? undefined : `${window.location.origin}/home`;
    const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo } });
    return error?.message ?? null;
  }, []);

  const signInWithGoogleIdToken = useCallback(async (token: string, nonce: string) => {
    if (!supabase) return 'Supabase is not configured.';
    const { error } = await supabase.auth.signInWithIdToken({ provider: 'google', token, nonce });
    return error?.message ?? null;
  }, []);

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, refreshProfile, signIn, signInWithMagicLink, signInWithGoogle, signInWithGoogleIdToken, signUp, signOut }),
    [refreshProfile, signIn, signInWithMagicLink, signInWithGoogle, signInWithGoogleIdToken, signOut, signUp, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider.');
  return value;
}
