-- ============================================================
-- CLASSIO — RLS policies for subscriptions, usage, and admin data
-- Assumes Supabase Auth JWT subject matches profiles.user_id.
-- Service-role backend/webhook clients bypass RLS for Stripe event processing.
-- ============================================================

alter table plans enable row level security;
alter table user_subscriptions enable row level security;
alter table payment_events enable row level security;
alter table usage_tracking enable row level security;
alter table admin_overrides enable row level security;

create or replace function public.is_classio_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from profiles
        where user_id = auth.uid()::text
          and role = 'admin'
    );
$$;

-- Plans can be read by any authenticated user; only admins can mutate in-app.
drop policy if exists "plans_read_authenticated" on plans;
create policy "plans_read_authenticated" on plans
for select to authenticated
using (active = true or public.is_classio_admin());

drop policy if exists "plans_admin_all" on plans;
create policy "plans_admin_all" on plans
for all to authenticated
using (public.is_classio_admin())
with check (public.is_classio_admin());

-- Users can read their own subscription; admins can read/write all.
drop policy if exists "subscriptions_read_own_or_admin" on user_subscriptions;
create policy "subscriptions_read_own_or_admin" on user_subscriptions
for select to authenticated
using (user_id = auth.uid()::text or public.is_classio_admin());

drop policy if exists "subscriptions_admin_all" on user_subscriptions;
create policy "subscriptions_admin_all" on user_subscriptions
for all to authenticated
using (public.is_classio_admin())
with check (public.is_classio_admin());

-- Users can read their own usage. App writes should go through guarded backend/server code.
drop policy if exists "usage_read_own_or_admin" on usage_tracking;
create policy "usage_read_own_or_admin" on usage_tracking
for select to authenticated
using (user_id = auth.uid()::text or public.is_classio_admin());

drop policy if exists "usage_admin_all" on usage_tracking;
create policy "usage_admin_all" on usage_tracking
for all to authenticated
using (public.is_classio_admin())
with check (public.is_classio_admin());

-- Payment event payloads can include customer/billing metadata: admin-only.
drop policy if exists "payment_events_admin_only" on payment_events;
create policy "payment_events_admin_only" on payment_events
for all to authenticated
using (public.is_classio_admin())
with check (public.is_classio_admin());

-- Admin overrides are internal audit records.
drop policy if exists "admin_overrides_admin_only" on admin_overrides;
create policy "admin_overrides_admin_only" on admin_overrides
for all to authenticated
using (public.is_classio_admin())
with check (public.is_classio_admin());
