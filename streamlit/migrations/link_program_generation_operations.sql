-- A program is assembled from one skeleton operation and one operation per generated unit.
-- Keep every operation, including later unit regenerations, rather than overwriting a single ID.
create table if not exists public.classio_program_generation_operations (
    operation_id uuid primary key references public.classio_ai_operations(operation_id) on delete cascade,
    program_id bigint not null references public.learning_programs(id) on delete cascade,
    unit_number integer,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    linked_at timestamptz not null default now(),
    check (unit_number is null or unit_number > 0)
);
create index if not exists classio_program_generation_operations_program_idx
    on public.classio_program_generation_operations(program_id, unit_number, linked_at desc);
alter table public.classio_program_generation_operations enable row level security;
revoke all on public.classio_program_generation_operations from anon, authenticated;
grant select, insert, update, delete on public.classio_program_generation_operations to service_role;

alter table public.learning_program_units add column if not exists generation_operation_id uuid
    references public.classio_ai_operations(operation_id);

create or replace function public.classio_link_program_generation_operation()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
    v_operation_id uuid;
    v_operation public.classio_ai_operations%rowtype;
    v_owner uuid;
    v_program_id bigint;
    v_unit integer;
begin
    if TG_TABLE_NAME = 'learning_programs' then
        if coalesce(NEW.builder_config->>'expo_native','false') <> 'true' then return NEW; end if;
        if nullif(NEW.builder_config->>'generation_id','') is null then return NEW; end if;
        v_operation_id := (NEW.builder_config->>'generation_id')::uuid;
        v_program_id := NEW.id;
        v_owner := NEW.user_id::uuid;
        v_unit := null;
    else
        if NEW.generation_operation_id is null or
           (TG_OP = 'UPDATE' and NEW.generation_operation_id is not distinct from OLD.generation_operation_id) then
            return NEW;
        end if;
        v_operation_id := NEW.generation_operation_id;
        v_program_id := NEW.program_id;
        v_unit := NEW.unit_number;
        select user_id::uuid into v_owner from public.learning_programs where id = v_program_id;
    end if;
    if auth.uid() is null or auth.uid() <> v_owner then
        raise exception 'Program generation owner mismatch' using errcode = '42501';
    end if;
    select * into v_operation from public.classio_ai_operations
      where operation_id = v_operation_id for share;
    if not found or v_operation.actor_user_id <> v_owner or v_operation.status <> 'success'
       or v_operation.source <> 'expo' or v_operation.modality <> 'text'
       or v_operation.feature_name <> 'generate_program' then
        raise exception 'Program generation operation unavailable' using errcode = '22023';
    end if;
    insert into public.classio_program_generation_operations
        (operation_id,program_id,unit_number,actor_user_id)
    values (v_operation_id,v_program_id,v_unit,v_owner);
    return NEW;
end;
$$;

drop trigger if exists classio_link_program_skeleton on public.learning_programs;
create trigger classio_link_program_skeleton after insert on public.learning_programs
for each row execute function public.classio_link_program_generation_operation();
drop trigger if exists classio_link_program_unit on public.learning_program_units;
create trigger classio_link_program_unit after update of generation_operation_id on public.learning_program_units
for each row execute function public.classio_link_program_generation_operation();
