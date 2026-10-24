-- A cover's economic operation is linked in the same transaction as the
-- resource update. Regenerations retain their own operation rows.
create table if not exists public.classio_cover_generation_resources (
    operation_id uuid primary key references public.classio_ai_operations(operation_id) on delete cascade,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    resource_type text not null check (resource_type in ('plan', 'worksheet', 'exam')),
    resource_id text not null,
    linked_at timestamptz not null default now()
);
create index if not exists classio_cover_generation_resource_idx
    on public.classio_cover_generation_resources(resource_type, resource_id, linked_at desc);
alter table public.classio_cover_generation_resources enable row level security;
revoke all on public.classio_cover_generation_resources from public, anon, authenticated;
grant select, insert on public.classio_cover_generation_resources to service_role;

create or replace function public.classio_link_saved_cover_generation()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
    v_old_cover jsonb;
    v_cover jsonb;
    v_id uuid;
    v_operation public.classio_ai_operations%rowtype;
begin
    v_old_cover := (to_jsonb(OLD) -> TG_ARGV[0]) -> 'cover_image';
    v_cover := (to_jsonb(NEW) -> TG_ARGV[0]) -> 'cover_image';
    if v_cover is null or v_cover is not distinct from v_old_cover
       or nullif(v_cover->>'operation_id', '') is null then
        return NEW;
    end if;
    if auth.uid() is null or auth.uid() <> NEW.user_id::uuid then
        raise exception 'Cover owner mismatch' using errcode = '42501';
    end if;
    v_id := (v_cover->>'operation_id')::uuid;
    select * into v_operation from public.classio_ai_operations
      where operation_id = v_id for share;
    if not found or v_operation.actor_user_id <> NEW.user_id::uuid
       or v_operation.status <> 'success' or v_operation.source <> 'expo'
       or v_operation.modality <> 'image' or v_operation.feature_name <> TG_ARGV[2] then
        raise exception 'Cover generation operation unavailable' using errcode = '22023';
    end if;
    insert into public.classio_cover_generation_resources
      (operation_id, actor_user_id, resource_type, resource_id)
    values (v_id, NEW.user_id::uuid, TG_ARGV[1], NEW.id::text);
    return NEW;
end;
$$;

drop trigger if exists classio_link_lesson_plan_cover on public.lesson_plans;
create trigger classio_link_lesson_plan_cover after update of plan_json on public.lesson_plans
for each row execute function public.classio_link_saved_cover_generation('plan_json', 'plan', 'cover_plan');
drop trigger if exists classio_link_worksheet_cover on public.worksheets;
create trigger classio_link_worksheet_cover after update of worksheet_json on public.worksheets
for each row execute function public.classio_link_saved_cover_generation('worksheet_json', 'worksheet', 'cover_worksheet');
drop trigger if exists classio_link_quick_exam_cover on public.quick_exams;
create trigger classio_link_quick_exam_cover after update of exam_data on public.quick_exams
for each row execute function public.classio_link_saved_cover_generation('exam_data', 'exam', 'cover_exam');
