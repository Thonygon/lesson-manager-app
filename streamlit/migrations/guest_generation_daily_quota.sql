-- Guest quota uses keyed hashes of proxy IP and opaque cookie. No raw IP is stored.
create table if not exists public.classio_guest_generation_daily (
    identity_hash text not null,
    usage_date date not null,
    used integer not null default 0 check (used >= 0),
    created_at timestamptz not null default now(),
    primary key (identity_hash, usage_date)
);
alter table public.classio_guest_generation_daily
    add column if not exists created_at timestamptz not null default now();
create index if not exists classio_guest_generation_daily_created_at_idx
    on public.classio_guest_generation_daily(created_at);
revoke all on public.classio_guest_generation_daily from public, anon, authenticated;
grant select, insert, update on public.classio_guest_generation_daily to service_role;

create or replace function public.classio_reserve_guest_generation(p_ip_hash text, p_cookie_hash text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_day date := (now() at time zone 'UTC')::date;
    v_hash text;
    v_used integer;
    v_max integer := 0;
begin
    if auth.role() <> 'service_role' then
        raise exception 'Service role required' using errcode = '42501';
    end if;
    if p_ip_hash !~ '^[a-f0-9]{64}$' or p_cookie_hash !~ '^[a-f0-9]{64}$' then
        raise exception 'Invalid guest identity' using errcode = '22023';
    end if;

    -- Lock both rows in a stable order to serialize concurrent attempts.
    for v_hash in select distinct hash from (values (p_ip_hash), (p_cookie_hash)) as identities(hash) order by hash loop
        insert into public.classio_guest_generation_daily(identity_hash, usage_date, used)
        values (v_hash, v_day, 0)
        on conflict (identity_hash, usage_date) do nothing;
        select used into v_used from public.classio_guest_generation_daily
        where identity_hash = v_hash and usage_date = v_day for update;
        v_max := greatest(v_max, v_used);
    end loop;
    if v_max >= 3 then
        return jsonb_build_object('allowed', false, 'used', v_max);
    end if;
    update public.classio_guest_generation_daily set used = used + 1
    where usage_date = v_day and identity_hash in (p_ip_hash, p_cookie_hash);
    return jsonb_build_object('allowed', true, 'used', v_max + 1);
end;
$$;
revoke all on function public.classio_reserve_guest_generation(text, text) from public, anon, authenticated;
grant execute on function public.classio_reserve_guest_generation(text, text) to service_role;

-- Supabase Cron removes rows after 48 hours. The hourly sweep means deletion
-- occurs within the following hour; no cleanup work is added to generation.
create extension if not exists pg_cron with schema extensions;
select cron.schedule(
    'classio-guest-quota-48h',
    '0 * * * *',
    $$delete from public.classio_guest_generation_daily where created_at < now() - interval '48 hours'$$
);
