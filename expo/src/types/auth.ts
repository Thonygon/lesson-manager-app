import type { Session, User } from '@supabase/supabase-js';

export type ProductRole = 'admin' | 'teacher' | 'student' | 'school_admin';

export type ClassioProfile = {
  user_id: string;
  email: string | null;
  display_name: string | null;
  username: string | null;
  avatar_url: string | null;
  role: ProductRole;
  primary_role: ProductRole | null;
  can_teach: boolean;
  can_study: boolean;
  last_active_mode: ProductRole | null;
  onboarding_completed: boolean;
};

export type AuthState = {
  configured: boolean;
  loading: boolean;
  session: Session | null;
  user: User | null;
  profile: ClassioProfile | null;
  error: string | null;
};
