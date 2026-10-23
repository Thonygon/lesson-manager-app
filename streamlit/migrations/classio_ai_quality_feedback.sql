-- Human feedback is kept separate from economic telemetry and payment records.
-- Only trusted application servers may write these tables. No prompt, generated
-- document, student name, or free-form teacher text is stored here.

create table if not exists public.classio_generation_intent_feedback (
    generation_id uuid primary key,
    operation_id uuid unique references public.classio_ai_operations(operation_id) on delete set null,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    source text not null check (source in ('expo', 'streamlit')),
    feature_name text not null check (length(feature_name) between 1 and 80),
    generation_mode text not null check (generation_mode in ('ai', 'template', 'fallback')),
    prompt_version text not null default '',
    model_name text not null default '',
    resource_type text not null default '',
    resource_id text not null default '',
    feedback_surface text not null default 'generation_preview' check (feedback_surface in ('generation_preview', 'resource_page')),
    satisfied boolean,
    reason text check (reason is null or reason in ('content', 'level', 'format', 'other')),
    shown_at timestamptz not null default now(),
    answered_at timestamptz,
    updated_at timestamptz not null default now(),
    check (satisfied is not true or reason is null)
);

create index if not exists classio_generation_intent_feedback_actor_idx
    on public.classio_generation_intent_feedback(actor_user_id, shown_at desc);

create table if not exists public.classio_generation_intent_feedback_events (
    id bigint generated always as identity primary key,
    generation_id uuid not null references public.classio_ai_operations(operation_id) on delete cascade,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    feedback_surface text not null check (feedback_surface in ('generation_preview', 'resource_page')),
    satisfied boolean not null,
    reason text check (reason is null or reason in ('content', 'level', 'format', 'other')),
    created_at timestamptz not null default now(),
    check (satisfied is not true or reason is null)
);
create index if not exists classio_generation_intent_feedback_events_generation_idx
    on public.classio_generation_intent_feedback_events(generation_id, created_at desc);

-- Link a generated document to its library row. Content edits permanently
-- retire the original generation from the satisfaction question.
create table if not exists public.classio_generation_resources (
    generation_id uuid primary key references public.classio_ai_operations(operation_id) on delete cascade,
    actor_user_id uuid not null references auth.users(id) on delete cascade,
    resource_type text not null check (resource_type in ('plan', 'worksheet', 'exam', 'program')),
    resource_id text not null,
    edited_at timestamptz,
    created_at timestamptz not null default now(),
    unique (resource_type, resource_id)
);

create or replace function public.classio_generation_substantive_content(value jsonb)
returns jsonb language plpgsql immutable as $$
declare
    result jsonb;
begin
    if jsonb_typeof(value) = 'object' then
        select coalesce(jsonb_object_agg(key, public.classio_generation_substantive_content(item)), '{}'::jsonb)
          into result
          from jsonb_each(value) as fields(key, item)
         where key not in ('cover_image', 'visual_supports', 'visual_support', '_visual_support_status', 'image_data_url', 'image_base64', 'image_prompt');
        return result;
    elsif jsonb_typeof(value) = 'array' then
        select coalesce(jsonb_agg(public.classio_generation_substantive_content(item) order by ord), '[]'::jsonb)
          into result
          from jsonb_array_elements(value) with ordinality as items(item, ord);
        return result;
    end if;
    return value;
end;
$$;

create or replace function public.classio_retire_generation_feedback_on_content_edit()
returns trigger language plpgsql security definer set search_path = public as $$
declare
    resource_kind text := TG_ARGV[0];
    document_column text := TG_ARGV[1];
    old_document jsonb;
    new_document jsonb;
begin
    old_document := to_jsonb(OLD)->document_column;
    new_document := to_jsonb(NEW)->document_column;
    if public.classio_generation_substantive_content(old_document) is distinct from public.classio_generation_substantive_content(new_document)
       and (resource_kind <> 'program' or (OLD.status = 'active' and NEW.status = 'active')) then
        update public.classio_generation_resources
           set edited_at = coalesce(edited_at, now())
         where resource_type = resource_kind and resource_id = NEW.id::text;
    end if;
    return NEW;
end;
$$;

drop trigger if exists classio_generation_plan_edited on public.lesson_plans;
create trigger classio_generation_plan_edited after update of plan_json on public.lesson_plans
for each row execute function public.classio_retire_generation_feedback_on_content_edit('plan', 'plan_json');
drop trigger if exists classio_generation_worksheet_edited on public.worksheets;
create trigger classio_generation_worksheet_edited after update of worksheet_json on public.worksheets
for each row execute function public.classio_retire_generation_feedback_on_content_edit('worksheet', 'worksheet_json');
drop trigger if exists classio_generation_exam_edited on public.quick_exams;
create trigger classio_generation_exam_edited after update of exam_data on public.quick_exams
for each row execute function public.classio_retire_generation_feedback_on_content_edit('exam', 'exam_data');
drop trigger if exists classio_generation_program_edited on public.learning_programs;
create trigger classio_generation_program_edited after update of program_data on public.learning_programs
for each row execute function public.classio_retire_generation_feedback_on_content_edit('program', 'program_data');

create table if not exists public.classio_teacher_relevance_feedback (
    id bigint generated always as identity primary key,
    teacher_id uuid not null references auth.users(id) on delete cascade,
    student_id text not null default '',
    context_key text not null check (length(context_key) between 1 and 500),
    exposure_id text not null references public.resource_exposures(exposure_id) on delete cascade,
    resource_type text not null check (resource_type in ('plan', 'worksheet', 'exam', 'video')),
    resource_id text not null,
    resource_is_public boolean not null default false,
    resource_updated_at timestamptz,
    topic_id bigint,
    recommendation_id text not null default '',
    reason text check (reason is null or reason in ('wrong_topic', 'student_unfit')),
    active boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (teacher_id, context_key),
    check (active = false or reason is not null)
);

create index if not exists classio_teacher_relevance_feedback_student_idx
    on public.classio_teacher_relevance_feedback(teacher_id, student_id, active);
create index if not exists classio_teacher_relevance_feedback_resource_idx
    on public.classio_teacher_relevance_feedback(resource_type, resource_id, active);

create table if not exists public.classio_teacher_relevance_feedback_events (
    id bigint generated always as identity primary key,
    feedback_id bigint not null references public.classio_teacher_relevance_feedback(id) on delete cascade,
    exposure_id text not null,
    teacher_id uuid not null references auth.users(id) on delete cascade,
    action text not null check (action in ('rejected', 'undone')),
    reason text check (reason is null or reason in ('wrong_topic', 'student_unfit')),
    created_at timestamptz not null default now()
);

create index if not exists classio_teacher_relevance_feedback_events_feedback_idx
    on public.classio_teacher_relevance_feedback_events(feedback_id, created_at desc);

alter table public.classio_generation_intent_feedback enable row level security;
alter table public.classio_generation_intent_feedback_events enable row level security;
alter table public.classio_generation_resources enable row level security;
alter table public.classio_teacher_relevance_feedback enable row level security;
alter table public.classio_teacher_relevance_feedback_events enable row level security;
revoke all on public.classio_generation_intent_feedback,
    public.classio_generation_intent_feedback_events,
    public.classio_generation_resources,
    public.classio_teacher_relevance_feedback,
    public.classio_teacher_relevance_feedback_events from public, anon, authenticated;
grant select, insert, update on public.classio_generation_intent_feedback,
    public.classio_generation_resources,
    public.classio_teacher_relevance_feedback to service_role;
grant select, insert on public.classio_teacher_relevance_feedback_events to service_role;
grant select, insert on public.classio_generation_intent_feedback_events to service_role;
grant usage, select on sequence public.classio_teacher_relevance_feedback_id_seq,
    public.classio_teacher_relevance_feedback_events_id_seq,
    public.classio_generation_intent_feedback_events_id_seq to service_role;
revoke all on function public.classio_generation_substantive_content(jsonb) from public, anon, authenticated;
revoke all on function public.classio_retire_generation_feedback_on_content_edit() from public, anon, authenticated;
