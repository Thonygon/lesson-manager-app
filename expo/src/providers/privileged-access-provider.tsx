/* eslint-disable react-hooks/set-state-in-effect */
import { createContext, type PropsWithChildren, useContext, useEffect, useMemo, useState } from 'react';

import { supabase } from '@/lib/supabase';
import { useAuth } from '@/providers/auth-provider';

export type StaffRole = 'developer' | 'data_scientist';

type PrivilegedAccess = {
  loading: boolean;
  isAdmin: boolean;
  canUseDeveloperWorkspace: boolean;
  staffRoles: StaffRole[];
};

const emptyAccess: PrivilegedAccess = {
  loading: true,
  isAdmin: false,
  canUseDeveloperWorkspace: false,
  staffRoles: [],
};

const PrivilegedAccessContext = createContext<PrivilegedAccess>(emptyAccess);

export function PrivilegedAccessProvider({ children }: PropsWithChildren) {
  const { loading: authLoading, user, profile } = useAuth();
  const [staffRoles, setStaffRoles] = useState<StaffRole[]>([]);
  const [loading, setLoading] = useState(true);
  const isAdmin = profile?.role === 'admin';
  const userId = user?.id;

  useEffect(() => {
    let active = true;
    if (authLoading) return;
    if (!userId || !supabase) {
      setStaffRoles([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    void supabase
      .from('user_staff_roles')
      .select('role_key')
      .eq('user_id', userId)
      .eq('is_active', true)
      .then(({ data }) => {
        if (!active) return;
        const roles = (data ?? [])
          .map((row) => String(row.role_key))
          .filter((role): role is StaffRole => role === 'developer' || role === 'data_scientist');
        setStaffRoles(Array.from(new Set(roles)));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authLoading, userId]);

  const value = useMemo<PrivilegedAccess>(() => ({
    loading: authLoading || loading,
    isAdmin,
    canUseDeveloperWorkspace: isAdmin || staffRoles.length > 0,
    staffRoles,
  }), [authLoading, isAdmin, loading, staffRoles]);

  return <PrivilegedAccessContext.Provider value={value}>{children}</PrivilegedAccessContext.Provider>;
}

export function usePrivilegedAccess() {
  return useContext(PrivilegedAccessContext);
}
