-- Account-level, server-only usage evidence. Calendar buckets use UTC and
-- exclude the current (unfinished) month. No prompt or student content leaves
-- the database through this function.
create or replace function public.classio_admin_account_usage_detail(p_user_id uuid)
returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare v_result jsonb;
begin
  if auth.role() is distinct from 'service_role' then
    raise exception 'Service role required' using errcode = '42501';
  end if;
  if p_user_id is null then
    raise exception 'User required' using errcode = '22023';
  end if;

  with boundaries as (
    select date_trunc('month', now() at time zone 'UTC') at time zone 'UTC' as month_start,
           date_trunc('year', now() at time zone 'UTC') at time zone 'UTC' as year_start
  ), closed_months as (
    select (b.month_start - make_interval(months => n)) as from_time,
           (b.month_start - make_interval(months => n - 1)) as to_time
    from boundaries b cross join generate_series(1, 12) as n
  ), month_rows as (
    select to_char(m.from_time at time zone 'UTC', 'YYYY-MM') as month,
      (select count(*) from public.classio_smart_tool_quota_charges c
       where c.user_id = p_user_id and c.charged_at >= m.from_time and c.charged_at < m.to_time) as delivered_resources,
      (select count(*) from public.classio_ai_operations o
       where o.actor_user_id = p_user_id and o.started_at >= m.from_time and o.started_at < m.to_time) as ai_operations,
      (select count(*) from public.classio_document_export_events e
       where e.actor_user_id = p_user_id and e.started_at >= m.from_time and e.started_at < m.to_time
         and e.format = 'pdf' and e.status = 'handoff_requested') as pdf_handoffs,
      (select count(*) from public.classio_document_export_events e
       where e.actor_user_id = p_user_id and e.started_at >= m.from_time and e.started_at < m.to_time
         and e.format = 'docx' and e.status = 'handoff_requested') as word_handoffs
    from closed_months m
  ), token_periods as (
    select p.label,
      coalesce(sum(a.input_tokens) filter (where a.usage_observed), 0) as input_tokens,
      coalesce(sum(a.output_tokens) filter (where a.usage_observed), 0) as output_tokens,
      coalesce(sum(a.cached_input_tokens) filter (where a.usage_observed), 0) as cached_input_tokens,
      count(a.attempt_id) filter (where a.usage_observed and (a.input_tokens is not null or a.output_tokens is not null)) as reported_attempts,
      count(a.attempt_id) filter (where not a.usage_observed or (a.input_tokens is null and a.output_tokens is null)) as unreported_attempts
    from (select 'month'::text as label, b.month_start as from_time from boundaries b
          union all select 'year', b.year_start from boundaries b
          union all select 'all', '-infinity'::timestamptz) p
    left join (
      select attempt.attempt_id, attempt.started_at, attempt.input_tokens, attempt.output_tokens,
             attempt.cached_input_tokens, attempt.usage_observed
      from public.classio_provider_attempts attempt
      join public.classio_ai_operations operation on operation.operation_id = attempt.operation_id
      where operation.actor_user_id = p_user_id
    ) a on a.started_at >= p.from_time
    group by p.label
  )
  select jsonb_build_object(
    'timezone', 'UTC',
    'closed_months', (select coalesce(jsonb_agg(to_jsonb(m) order by m.month desc), '[]'::jsonb) from month_rows m),
    'token_periods', (select coalesce(jsonb_agg(to_jsonb(t) order by case t.label when 'month' then 1 when 'year' then 2 else 3 end), '[]'::jsonb) from token_periods t)
  ) into v_result;
  return v_result;
end;
$$;
revoke all on function public.classio_admin_account_usage_detail(uuid) from public, anon, authenticated;
grant execute on function public.classio_admin_account_usage_detail(uuid) to service_role;
