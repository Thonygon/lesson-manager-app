-- The resource row and its economic/feedback generation link commit together.
-- Only a successful operation owned by the inserting teacher may be attached.
alter table public.lesson_plans
    add column if not exists generation_operation_id uuid references public.classio_ai_operations(operation_id);
alter table public.worksheets
    add column if not exists generation_operation_id uuid references public.classio_ai_operations(operation_id);
alter table public.quick_exams
    add column if not exists generation_operation_id uuid references public.classio_ai_operations(operation_id);

create unique index if not exists lesson_plans_generation_operation_id_uq
    on public.lesson_plans(generation_operation_id) where generation_operation_id is not null;
create unique index if not exists worksheets_generation_operation_id_uq
    on public.worksheets(generation_operation_id) where generation_operation_id is not null;
create unique index if not exists quick_exams_generation_operation_id_uq
    on public.quick_exams(generation_operation_id) where generation_operation_id is not null;

create or replace function public.classio_link_saved_generation_on_insert()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_operation public.classio_ai_operations%rowtype;
begin
    if NEW.generation_operation_id is null then
        return NEW;
    end if;
    if auth.uid() is null or auth.uid() <> NEW.user_id::uuid then
        raise exception 'Generation owner does not match the resource owner' using errcode = '42501';
    end if;
    select * into v_operation from public.classio_ai_operations
    where operation_id = NEW.generation_operation_id for share;
    if not found or v_operation.actor_user_id <> NEW.user_id::uuid
       or v_operation.status <> 'success' or v_operation.source <> 'expo'
       or v_operation.modality <> 'text'
       or v_operation.feature_name <> TG_ARGV[1] then
        raise exception 'Generation operation cannot be linked to this resource' using errcode = '22023';
    end if;
    insert into public.classio_generation_resources
        (generation_id, actor_user_id, resource_type, resource_id)
    values (NEW.generation_operation_id, NEW.user_id::uuid, TG_ARGV[0], NEW.id::text);
    return NEW;
end;
$$;

create or replace function public.classio_prevent_generation_operation_reassignment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if NEW.generation_operation_id is distinct from OLD.generation_operation_id then
        raise exception 'A saved generation link cannot be reassigned' using errcode = '22023';
    end if;
    return NEW;
end;
$$;

drop trigger if exists classio_link_lesson_plan_generation on public.lesson_plans;
create trigger classio_link_lesson_plan_generation after insert on public.lesson_plans
for each row execute function public.classio_link_saved_generation_on_insert('plan', 'generate_plan');
drop trigger if exists classio_lock_lesson_plan_generation on public.lesson_plans;
create trigger classio_lock_lesson_plan_generation before update of generation_operation_id on public.lesson_plans
for each row execute function public.classio_prevent_generation_operation_reassignment();

drop trigger if exists classio_link_worksheet_generation on public.worksheets;
create trigger classio_link_worksheet_generation after insert on public.worksheets
for each row execute function public.classio_link_saved_generation_on_insert('worksheet', 'generate_worksheet');
drop trigger if exists classio_lock_worksheet_generation on public.worksheets;
create trigger classio_lock_worksheet_generation before update of generation_operation_id on public.worksheets
for each row execute function public.classio_prevent_generation_operation_reassignment();

drop trigger if exists classio_link_quick_exam_generation on public.quick_exams;
create trigger classio_link_quick_exam_generation after insert on public.quick_exams
for each row execute function public.classio_link_saved_generation_on_insert('exam', 'generate_exam');
drop trigger if exists classio_lock_quick_exam_generation on public.quick_exams;
create trigger classio_lock_quick_exam_generation before update of generation_operation_id on public.quick_exams
for each row execute function public.classio_prevent_generation_operation_reassignment();
