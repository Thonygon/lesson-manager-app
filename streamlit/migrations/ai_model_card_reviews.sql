-- Versioned human review of model cards. This stores operational metadata,
-- never prompts, learner content, payment records, classes or profiles.
create table if not exists public.classio_model_card_reviews (
    component_id text not null check (length(component_id) between 3 and 100),
    model_version text not null check (length(model_version) between 1 and 120),
    status text not null check (status in ('reviewed', 'retired')),
    reviewed_by uuid not null references auth.users(id),
    reviewed_at timestamptz not null default now(),
    review_reason text not null check (length(review_reason) between 8 and 500),
    primary key (component_id, model_version)
);

create table if not exists public.classio_model_card_review_events (
    id bigint generated always as identity primary key,
    component_id text not null,
    model_version text not null,
    previous_status text,
    new_status text not null check (new_status in ('reviewed', 'retired')),
    reviewed_by uuid not null references auth.users(id),
    review_reason text not null,
    created_at timestamptz not null default now()
);
create index if not exists classio_model_card_review_events_version_idx
    on public.classio_model_card_review_events(component_id, model_version, created_at desc);

alter table public.classio_model_card_reviews enable row level security;
alter table public.classio_model_card_review_events enable row level security;
revoke all on public.classio_model_card_reviews, public.classio_model_card_review_events from public, anon, authenticated;
grant select on public.classio_model_card_reviews, public.classio_model_card_review_events to authenticated;
grant select, insert, update on public.classio_model_card_reviews to service_role;
grant select, insert on public.classio_model_card_review_events to service_role;
grant usage, select on sequence public.classio_model_card_review_events_id_seq to service_role;

drop policy if exists classio_model_card_reviews_staff_read on public.classio_model_card_reviews;
create policy classio_model_card_reviews_staff_read on public.classio_model_card_reviews
for select to authenticated using (
    exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
    or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')
);
drop policy if exists classio_model_card_review_events_staff_read on public.classio_model_card_review_events;
create policy classio_model_card_review_events_staff_read on public.classio_model_card_review_events
for select to authenticated using (
    exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
    or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')
);

create or replace function public.classio_review_model_card(
    p_component_id text, p_model_version text, p_status text, p_reason text
) returns boolean language plpgsql security definer set search_path = '' as $$
declare v_previous text;
begin
    if not (exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key = 'developer')
      or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')) then
        raise exception 'Model review permission required' using errcode = '42501';
    end if;
    if coalesce(p_component_id, '') !~ '^[a-z][a-z0-9_]{2,99}$'
       or length(trim(coalesce(p_model_version, ''))) not between 1 and 120
       or p_status not in ('reviewed', 'retired')
       or length(trim(coalesce(p_reason, ''))) not between 8 and 500 then
        raise exception 'Invalid model card review' using errcode = '22023';
    end if;
    select status into v_previous from public.classio_model_card_reviews
      where component_id = p_component_id and model_version = trim(p_model_version) for update;
    insert into public.classio_model_card_reviews
      (component_id, model_version, status, reviewed_by, review_reason)
    values (p_component_id, trim(p_model_version), p_status, auth.uid(), trim(p_reason))
    on conflict (component_id, model_version) do update set
      status = excluded.status, reviewed_by = excluded.reviewed_by,
      review_reason = excluded.review_reason, reviewed_at = now();
    insert into public.classio_model_card_review_events
      (component_id, model_version, previous_status, new_status, reviewed_by, review_reason)
    values (p_component_id, trim(p_model_version), v_previous, p_status, auth.uid(), trim(p_reason));
    return true;
end;
$$;
revoke all on function public.classio_review_model_card(text,text,text,text) from public, anon;
grant execute on function public.classio_review_model_card(text,text,text,text) to authenticated;
