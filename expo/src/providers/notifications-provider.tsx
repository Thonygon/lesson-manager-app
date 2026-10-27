/* eslint-disable react-hooks/set-state-in-effect */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { usePathname } from 'expo-router';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { AppState } from 'react-native';

import { useAuth } from '@/providers/auth-provider';
import { usePrivilegedAccess } from '@/providers/privileged-access-provider';
import { loadAppNotifications, type AppNotification } from '@/services/app-notifications';
import { DEFAULT_NOTIFICATION_PREFERENCES, notificationCategory, parseNotificationPreferences, type NotificationCategory, type NotificationPreferences } from '@/lib/notification-preferences';

const REFRESH_MS = 120000;
type NotificationState = {
  items: AppNotification[];
  unread: AppNotification[];
  preferences: NotificationPreferences;
  preferencesReady: boolean;
  setPreference: (category: NotificationCategory, enabled: boolean) => Promise<void>;
  markUnread: (key: string) => Promise<void>;
  loading: boolean;
  error: string;
  refresh: (force?: boolean) => Promise<void>;
  markRead: (key: string) => Promise<void>;
  publishPaymentAlerts: (items: { key: string; icon: string; title: string; body?: string; href: unknown }[]) => void;
};
const empty: NotificationState = { items: [], unread: [], preferences: DEFAULT_NOTIFICATION_PREFERENCES, preferencesReady: false, setPreference: async () => {}, markUnread: async () => {}, loading: false, error: '', refresh: async () => {}, markRead: async () => {}, publishPaymentAlerts: () => {} };
const Context = createContext<NotificationState>(empty);

export function NotificationsProvider({ children }: PropsWithChildren) {
  const { user, profile } = useAuth();
  const pathname = usePathname();
  const access = usePrivilegedAccess();
  const role = pathname === '/admin' && access.isAdmin ? 'admin'
    : pathname === '/developer-workspace' && access.canUseDeveloperWorkspace ? 'developer'
    : profile?.last_active_mode ?? profile?.primary_role ?? profile?.role ?? 'student';
  const userId = user?.id || '';
  const storageKey = `classio:notifications:read:v1:${userId}:${role}`;
  const preferencesKey = `classio:notifications:preferences:v1:${userId}:${role}`;
  const [items, setItems] = useState<AppNotification[]>([]);
  const [paymentAlerts, setPaymentAlerts] = useState<AppNotification[]>([]);
  const [readKeys, setReadKeys] = useState<string[]>([]);
  const [preferences, setPreferences] = useState<NotificationPreferences>(DEFAULT_NOTIFICATION_PREFERENCES);
  const [preferencesReady, setPreferencesReady] = useState(false);
  const readKeysRef = useRef<string[]>([]);
  const preferencesRef = useRef<NotificationPreferences>(DEFAULT_NOTIFICATION_PREFERENCES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const lastRefresh = useRef(0);
  const inFlight = useRef<Promise<void> | null>(null);
  const generation = useRef(0);
  const refresh = useCallback(async (force = false) => {
    if (!userId) return;
    if (inFlight.current) return inFlight.current;
    if (!force && Date.now() - lastRefresh.current < REFRESH_MS) return;
    const current = generation.current;
    const request = (async () => {
      setLoading(true);
      try {
        const next = await loadAppNotifications(userId, role);
        if (current !== generation.current) return;
        setItems(next);
        setError('');
        lastRefresh.current = Date.now();
      } catch (reason) {
        if (current === generation.current) setError(reason instanceof Error ? reason.message : 'Notifications could not be loaded.');
      } finally {
        if (current === generation.current) setLoading(false);
      }
    })();
    inFlight.current = request;
    try { await request; } finally { if (inFlight.current === request) inFlight.current = null; }
  }, [role, userId]);
  useEffect(() => {
    generation.current += 1;
    lastRefresh.current = 0;
    inFlight.current = null;
    setItems([]);
    setPaymentAlerts([]);
    readKeysRef.current = [];
    setReadKeys([]);
    preferencesRef.current = { ...DEFAULT_NOTIFICATION_PREFERENCES };
    setPreferences(preferencesRef.current);
    setPreferencesReady(false);
    if (!userId) return;
    let active = true;
    void Promise.all([AsyncStorage.getItem(storageKey), AsyncStorage.getItem(preferencesKey)]).then(([saved, storedPreferences]) => {
      if (!active) return;
      let parsed: unknown = [];
      try { parsed = saved ? JSON.parse(saved) : []; } catch { /* Ignore corrupt local read state. */ }
      readKeysRef.current = Array.isArray(parsed) ? parsed.filter((key): key is string => typeof key === 'string').slice(-500) : [];
      setReadKeys(readKeysRef.current);
      preferencesRef.current = parseNotificationPreferences(storedPreferences);
      setPreferences(preferencesRef.current);
    }).catch(() => {}).finally(() => { if (active) setPreferencesReady(true); });
    void refresh(true);
    return () => { active = false; };
  }, [preferencesKey, refresh, storageKey, userId]);
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => { if (state === 'active') void refresh(); });
    return () => subscription.remove();
  }, [refresh]);
  const markRead = useCallback(async (key: string) => {
    const next = [...new Set([...readKeysRef.current, key])].slice(-500);
    readKeysRef.current = next;
    setReadKeys(next);
    try { await AsyncStorage.setItem(storageKey, JSON.stringify(next)); } catch (reason) { console.warn('Notification read state could not be saved', reason); }
  }, [storageKey]);
  const markUnread = useCallback(async (key: string) => {
    const next = readKeysRef.current.filter((item) => item !== key);
    readKeysRef.current = next;
    setReadKeys(next);
    try { await AsyncStorage.setItem(storageKey, JSON.stringify(next)); } catch (reason) { console.warn('Notification read state could not be saved', reason); }
  }, [storageKey]);
  const setPreference = useCallback(async (category: NotificationCategory, enabled: boolean) => {
    const next = { ...preferencesRef.current, [category]: enabled };
    preferencesRef.current = next;
    setPreferences(next);
    try { await AsyncStorage.setItem(preferencesKey, JSON.stringify(next)); } catch (reason) { console.warn('Notification preferences could not be saved', reason); }
  }, [preferencesKey]);
  const publishPaymentAlerts = useCallback((source: { key: string; icon: string; title: string; body?: string; href: unknown }[]) => {
    const next = source.filter((item) => item.href === '/payments').map((item): AppNotification => ({ key: `teacher:payment:${item.key}:${item.title}`, icon: item.icon, titleKey: item.title, titleText: item.title, detail: item.body, href: '/payments' }));
    setPaymentAlerts((current) => current.map((item) => item.key).join('|') === next.map((item) => item.key).join('|') ? current : next);
  }, []);
  const allItems = useMemo(() => [...items, ...paymentAlerts].filter((item) => preferences[notificationCategory(item.key)]), [items, paymentAlerts, preferences]);
  const unread = useMemo(() => allItems.filter((item) => !readKeys.includes(item.key)), [allItems, readKeys]);
  const value = useMemo(() => ({ items: allItems, unread, preferences, preferencesReady, setPreference, markUnread, loading, error, refresh, markRead, publishPaymentAlerts }), [allItems, unread, preferences, preferencesReady, setPreference, markUnread, loading, error, refresh, markRead, publishPaymentAlerts]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export const useNotifications = () => useContext(Context);
