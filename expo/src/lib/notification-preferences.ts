export type NotificationCategory = 'assignments' | 'reviews' | 'payments';
export type NotificationPreferences = Record<NotificationCategory, boolean>;
export const DEFAULT_NOTIFICATION_PREFERENCES: NotificationPreferences = { assignments: true, reviews: true, payments: true };

export function parseNotificationPreferences(raw: string | null): NotificationPreferences {
  if (!raw) return { ...DEFAULT_NOTIFICATION_PREFERENCES };
  try {
    const value = JSON.parse(raw) as Partial<NotificationPreferences>;
    if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...DEFAULT_NOTIFICATION_PREFERENCES };
    return {
      assignments: typeof value.assignments === 'boolean' ? value.assignments : true,
      reviews: typeof value.reviews === 'boolean' ? value.reviews : true,
      payments: typeof value.payments === 'boolean' ? value.payments : true,
    };
  } catch { return { ...DEFAULT_NOTIFICATION_PREFERENCES }; }
}

export function notificationCategory(key: string): NotificationCategory {
  if (key.startsWith('teacher:payment:')) return 'payments';
  if (key.startsWith('teacher:') || key.startsWith('student:review:')) return 'reviews';
  return 'assignments';
}
