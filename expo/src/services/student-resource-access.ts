import { requireSupabase } from '@/lib/supabase';
import { getPublicResources, type PublicResource } from '@/services/public-data';

type PlanRow = { id: string; active?: boolean; features_json?: Record<string, unknown> | null };
type SubscriptionRow = { plan_id?: string | null; manual_override?: boolean | null; subscription_status?: string | null };

export function studentVideoAccess(
  plans: PlanRow[], subscription: SubscriptionRow | null, profilePlan: string | null,
): boolean {
  const subscribed = Boolean(subscription?.manual_override)
    || ['active', 'trialing'].includes(String(subscription?.subscription_status || '').toLowerCase());
  const planId = subscribed ? subscription?.plan_id || 'free' : profilePlan || 'free';
  const plan = plans.find((row) => row.id === planId && row.active !== false);
  if (!plan && planId !== 'free') return false;
  const features = plan?.features_json || (plan ? {} : { videos_access: true });
  return Object.prototype.hasOwnProperty.call(features, 'videos_access')
    ? Boolean(features.videos_access) : true;
}

export async function getStudentPublicPracticeResources(): Promise<PublicResource[]> {
  const client = requireSupabase();
  const { data: auth, error: authError } = await client.auth.getUser();
  if (authError || !auth.user) throw authError ?? new Error('Your session has expired.');
  const uid = auth.user.id;
  const [plans, subscription, profile] = await Promise.all([
    client.from('plans').select('id,active,features_json').eq('active', true).limit(50),
    client.from('user_subscriptions').select('plan_id,manual_override,subscription_status').eq('user_id', uid).limit(1).maybeSingle(),
    client.from('profiles').select('current_plan').eq('user_id', uid).limit(1).maybeSingle(),
  ]);
  const error = plans.error ?? subscription.error ?? profile.error;
  if (error) throw error;
  const videosAllowed = studentVideoAccess(
    (plans.data ?? []) as PlanRow[], subscription.data as SubscriptionRow | null,
    String(profile.data?.current_plan || 'free'),
  );
  return getPublicResources(videosAllowed ? ['worksheet', 'exam', 'video'] : ['worksheet', 'exam'], 120);
}
