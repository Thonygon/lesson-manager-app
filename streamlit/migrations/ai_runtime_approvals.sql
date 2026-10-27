-- Explicit human approval of the exact provider/model/prompt release used by
-- each generation surface. No API key, prompt text or learner data is stored.
create table if not exists public.classio_ai_runtime_approvals (
    surface text not null check (surface in ('expo_text', 'expo_image', 'streamlit_text', 'streamlit_image')),
    provider text not null check (provider in ('openrouter', 'gemini', 'openai')),
    model text not null check (length(model) between 1 and 160),
    prompt_version text not null check (length(prompt_version) between 1 and 100),
    status text not null check (status in ('approved', 'retired')),
    reviewed_by uuid not null references auth.users(id),
    review_reason text not null check (length(review_reason) between 8 and 500),
    reviewed_at timestamptz not null default now(),
    primary key (surface, provider, model, prompt_version)
);
alter table public.classio_ai_runtime_approvals enable row level security;
revoke all on public.classio_ai_runtime_approvals from public, anon, authenticated;
grant select on public.classio_ai_runtime_approvals to authenticated;
grant select on public.classio_ai_runtime_approvals to service_role;

drop policy if exists classio_ai_approvals_staff_read on public.classio_ai_runtime_approvals;
create policy classio_ai_approvals_staff_read on public.classio_ai_runtime_approvals
for select to authenticated using (
    exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
    or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')
);

create table if not exists public.classio_ai_runtime_approval_events (
    id bigint generated always as identity primary key,
    surface text not null,
    provider text not null,
    model text not null,
    prompt_version text not null,
    previous_status text,
    new_status text not null,
    reviewed_by uuid not null references auth.users(id),
    review_reason text not null,
    created_at timestamptz not null default now()
);
alter table public.classio_ai_runtime_approval_events enable row level security;
revoke all on public.classio_ai_runtime_approval_events from public, anon, authenticated;
grant select on public.classio_ai_runtime_approval_events to authenticated;
drop policy if exists classio_ai_approval_events_staff_read on public.classio_ai_runtime_approval_events;
create policy classio_ai_approval_events_staff_read on public.classio_ai_runtime_approval_events
for select to authenticated using (
    exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
    or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')
);

create or replace function public.classio_review_ai_runtime(
    p_surface text, p_provider text, p_model text, p_prompt_version text,
    p_status text, p_reason text
) returns boolean language plpgsql security definer set search_path = '' as $$
declare v_previous text;
begin
    if not (exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key = 'developer')
      or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')) then
        raise exception 'AI runtime approval permission required' using errcode = '42501';
    end if;
    if p_surface not in ('expo_text', 'expo_image', 'streamlit_text', 'streamlit_image')
       or p_provider not in ('openrouter', 'gemini', 'openai')
       or p_status not in ('approved', 'retired')
       or length(trim(coalesce(p_model, ''))) not between 1 and 160
       or length(trim(coalesce(p_prompt_version, ''))) not between 1 and 100
       or length(trim(coalesce(p_reason, ''))) not between 8 and 500 then
        raise exception 'Invalid AI runtime approval';
    end if;
    select status into v_previous from public.classio_ai_runtime_approvals
      where surface = p_surface and provider = p_provider and model = trim(p_model)
        and prompt_version = trim(p_prompt_version) for update;
    insert into public.classio_ai_runtime_approvals
      (surface, provider, model, prompt_version, status, reviewed_by, review_reason)
    values (p_surface, p_provider, trim(p_model), trim(p_prompt_version), p_status, auth.uid(), trim(p_reason))
    on conflict (surface, provider, model, prompt_version) do update set
      status = excluded.status, reviewed_by = excluded.reviewed_by,
      review_reason = excluded.review_reason, reviewed_at = now();
    insert into public.classio_ai_runtime_approval_events
      (surface, provider, model, prompt_version, previous_status, new_status, reviewed_by, review_reason)
    values (p_surface, p_provider, trim(p_model), trim(p_prompt_version), v_previous, p_status, auth.uid(), trim(p_reason));
    return true;
end;
$$;
revoke all on function public.classio_review_ai_runtime(text,text,text,text,text,text) from public, anon;
grant execute on function public.classio_review_ai_runtime(text,text,text,text,text,text) to authenticated;
