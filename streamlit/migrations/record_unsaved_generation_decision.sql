-- An absent resource link is ambiguous. Record only an explicit decision made
-- after a successful Expo text generation; leave abandoned tabs as unknown.
create table if not exists public.classio_unsaved_generation_decisions (
    operation_id uuid primary key references public.classio_ai_operations(operation_id) on delete cascade,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    decision text not null check (decision = 'discarded_by_teacher'),
    decided_at timestamptz not null default now(),
    schema_version smallint not null default 1 check (schema_version = 1)
);
create index if not exists classio_unsaved_generation_actor_idx
    on public.classio_unsaved_generation_decisions(actor_user_id, decided_at desc);
alter table public.classio_unsaved_generation_decisions enable row level security;
revoke all on public.classio_unsaved_generation_decisions from public, anon, authenticated;
grant select, insert on public.classio_unsaved_generation_decisions to service_role;

create or replace function public.classio_record_unsaved_generation_decision(p_operation_id uuid)
returns void language plpgsql security definer set search_path = '' as $$
declare
    v_operation public.classio_ai_operations%rowtype;
begin
    if auth.uid() is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;
    select * into v_operation from public.classio_ai_operations
      where operation_id = p_operation_id for update;
    if not found or v_operation.actor_user_id <> auth.uid()
       or v_operation.source <> 'expo' or v_operation.modality <> 'text'
       or v_operation.status <> 'success'
       or v_operation.feature_name not in ('generate_plan', 'generate_worksheet', 'generate_exam') then
        raise exception 'Generation operation unavailable' using errcode = '42501';
    end if;
    if exists (select 1 from public.classio_generation_resources where generation_id = p_operation_id)
       or exists (select 1 from public.lesson_plans where generation_operation_id = p_operation_id)
       or exists (select 1 from public.worksheets where generation_operation_id = p_operation_id)
       or exists (select 1 from public.quick_exams where generation_operation_id = p_operation_id) then
        raise exception 'Saved generations cannot be discarded' using errcode = '22023';
    end if;
    insert into public.classio_unsaved_generation_decisions
      (operation_id, actor_user_id, decision)
    values (p_operation_id, auth.uid(), 'discarded_by_teacher')
    on conflict (operation_id) do nothing;
end;
$$;
revoke all on function public.classio_record_unsaved_generation_decision(uuid) from public, anon;
grant execute on function public.classio_record_unsaved_generation_decision(uuid) to authenticated, service_role;

-- Saving after a recorded discard is rejected inside the insert transaction.
create or replace function public.classio_guard_discarded_generation_save()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    -- Serialize with the decision RPC so a concurrent save cannot pass while
    -- the decision is still uncommitted.
    if NEW.generation_operation_id is not null then
        perform 1 from public.classio_ai_operations
        where operation_id = NEW.generation_operation_id for update;
    end if;
    if NEW.generation_operation_id is not null and exists (
        select 1 from public.classio_unsaved_generation_decisions
        where operation_id = NEW.generation_operation_id
    ) then
        raise exception 'Discarded generation cannot be saved' using errcode = '22023';
    end if;
    return NEW;
end;
$$;
drop trigger if exists classio_guard_discarded_plan on public.lesson_plans;
create trigger classio_guard_discarded_plan before insert on public.lesson_plans
for each row execute function public.classio_guard_discarded_generation_save();
drop trigger if exists classio_guard_discarded_worksheet on public.worksheets;
create trigger classio_guard_discarded_worksheet before insert on public.worksheets
for each row execute function public.classio_guard_discarded_generation_save();
drop trigger if exists classio_guard_discarded_exam on public.quick_exams;
create trigger classio_guard_discarded_exam before insert on public.quick_exams
for each row execute function public.classio_guard_discarded_generation_save();
