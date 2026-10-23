-- Economic telemetry records metadata only: no prompts, responses or student content.
-- These events are separate from short-lived ai_usage_logs and from teacher payments.
create table if not exists public.classio_ai_operations (
    operation_id uuid primary key,
    actor_user_id uuid references auth.users(id) on delete set null,
    source text not null check (source in ('expo', 'streamlit')),
    feature_name text not null check (length(feature_name) between 1 and 80),
    modality text not null check (modality in ('text', 'image')),
    status text not null default 'started' check (status in ('started', 'success', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    error_kind text,
    schema_version smallint not null default 1 check (schema_version = 1),
    check (finished_at is null or finished_at >= started_at),
    check (error_kind is null or length(error_kind) <= 80)
);

create table if not exists public.classio_provider_attempts (
    attempt_id uuid primary key,
    operation_id uuid not null references public.classio_ai_operations(operation_id) on delete cascade,
    attempt_no smallint not null check (attempt_no between 1 and 100),
    provider text not null check (provider in ('openrouter', 'gemini', 'openai')),
    model_requested text not null check (length(model_requested) between 1 and 160),
    model_reported text,
    modality text not null check (modality in ('text', 'image')),
    status text not null default 'started' check (status in ('started', 'success', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    http_status smallint check (http_status between 100 and 599),
    provider_request_id text,
    input_tokens integer check (input_tokens >= 0),
    output_tokens integer check (output_tokens >= 0),
    cached_input_tokens integer check (cached_input_tokens >= 0),
    reasoning_tokens integer check (reasoning_tokens >= 0),
    image_count smallint check (image_count >= 0),
    image_size_requested text,
    image_resolution text,
    usage_observed boolean not null default false,
    usage_json jsonb not null default '{}'::jsonb check (jsonb_typeof(usage_json) = 'object'),
    error_kind text,
    schema_version smallint not null default 1 check (schema_version = 1),
    unique (operation_id, attempt_no),
    check (finished_at is null or finished_at >= started_at),
    check (model_reported is null or length(model_reported) <= 160),
    check (provider_request_id is null or length(provider_request_id) <= 160),
    check (image_resolution is null or length(image_resolution) <= 40),
    check (image_size_requested is null or length(image_size_requested) <= 40),
    check (error_kind is null or length(error_kind) <= 80)
);

create index if not exists classio_ai_operations_started_at_idx on public.classio_ai_operations(started_at desc);
create index if not exists classio_ai_operations_actor_started_idx on public.classio_ai_operations(actor_user_id, started_at desc);
create index if not exists classio_provider_attempts_started_at_idx on public.classio_provider_attempts(started_at desc);
create index if not exists classio_provider_attempts_operation_idx on public.classio_provider_attempts(operation_id, attempt_no);

alter table public.classio_ai_operations enable row level security;
alter table public.classio_provider_attempts enable row level security;
revoke all on public.classio_ai_operations, public.classio_provider_attempts from public, anon, authenticated;
grant select, insert, update on public.classio_ai_operations, public.classio_provider_attempts to service_role;
