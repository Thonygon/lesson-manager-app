import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';

import { readPublicConfig } from '@/config/env';

export const publicConfig = readPublicConfig();

// Expo statically renders every route in Node before producing the browser bundle.
// AsyncStorage's web adapter requires `window`, so defer client construction during
// that server pass. The same module is evaluated again in the browser at runtime.
const canCreateClient = Platform.OS !== 'web' || typeof window !== 'undefined';

export const supabase = publicConfig && canCreateClient
  ? createClient(publicConfig.supabaseUrl, publicConfig.supabasePublishableKey, {
      auth: {
        storage: AsyncStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: Platform.OS === 'web',
      },
    })
  : null;

export function requireSupabase() {
  if (!supabase) {
    throw new Error('Supabase public configuration is missing. See expo/.env.example.');
  }
  return supabase;
}
