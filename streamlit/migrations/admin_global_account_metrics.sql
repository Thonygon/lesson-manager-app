-- Aggregate the full account population in Postgres; never derive platform KPIs
-- from the 500 most recently loaded support cards.
create or replace function public.classio_admin_global_account_metrics()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'commercial_plan_access', (
      select count(*) from public.profiles p
      where lower(coalesce(p.current_plan, '')) not in ('', 'free', 'beta_lifetime')
        and lower(coalesce(p.subscription_status, '')) in ('active', 'trialing', 'past_due')
    ),
    'new_30_days', (select count(*) from public.profiles where created_at >= now() - interval '30 days'),
    'suspended', (select count(*) from public.profiles where account_status = 'suspended'),
    'signup_months', (
      select coalesce(jsonb_agg(jsonb_build_array(month, total) order by month), '[]'::jsonb)
      from (select to_char(date_trunc('month', created_at at time zone 'UTC'), 'YYYY-MM') as month,
                   count(*) as total
            from public.profiles
            where created_at >= date_trunc('month', now() at time zone 'UTC') - interval '11 months'
            group by 1) x
    ),
    'plan_mix', (
      select coalesce(jsonb_agg(jsonb_build_array(plan, total) order by total desc, plan), '[]'::jsonb)
      from (select coalesce(nullif(current_plan, ''), 'unspecified') as plan, count(*) as total
            from public.profiles group by 1) x
    ),
    'status_mix', (
      select coalesce(jsonb_agg(jsonb_build_array(status, total) order by total desc, status), '[]'::jsonb)
      from (select coalesce(nullif(subscription_status, ''), 'unspecified') as status, count(*) as total
            from public.user_subscriptions group by 1) x
    )
  );
$$;
revoke all on function public.classio_admin_global_account_metrics() from public, anon, authenticated;
grant execute on function public.classio_admin_global_account_metrics() to service_role;
