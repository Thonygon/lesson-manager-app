-- Recommendation and ML history optimization helpers.
-- Review and apply manually in Supabase after validating the query plans.

create or replace function public.classio_recommendation_event_summary(
    p_teacher_id text default null,
    p_student_id text default null,
    p_assignment_ids bigint[] default null,
    p_since timestamptz default null,
    p_row_limit integer default 500
)
returns table(
    learning_program_assignment_id bigint,
    learning_program_topic_id bigint,
    recommendation_bucket text,
    event_count bigint,
    last_event_type text,
    last_event_at timestamptz,
    latest_score numeric,
    improved_count bigint,
    assigned_count bigint,
    teacher_marked_done_count bigint,
    resource_kinds text[]
)
language sql
security invoker
set search_path = public
as $$
with filtered as (
    select
        e.learning_program_assignment_id,
        e.learning_program_topic_id,
        e.recommendation_bucket,
        e.event_type,
        e.resource_kind,
        e.metadata,
        e.created_at
    from public.learning_program_recommendation_events e
    where (p_teacher_id is null or e.teacher_id = p_teacher_id)
      and (p_student_id is null or e.student_id = p_student_id)
      and (p_since is null or e.created_at >= p_since)
      and (
          p_assignment_ids is null
          or cardinality(p_assignment_ids) = 0
          or e.learning_program_assignment_id = any(p_assignment_ids)
      )
    order by e.created_at desc
    limit greatest(1, least(coalesce(p_row_limit, 500), 5000))
)
select
    filtered.learning_program_assignment_id,
    filtered.learning_program_topic_id,
    filtered.recommendation_bucket,
    count(*)::bigint as event_count,
    (array_agg(filtered.event_type order by filtered.created_at desc))[1] as last_event_type,
    max(filtered.created_at) as last_event_at,
    (
        array_remove(
            array_agg(nullif(trim(coalesce(filtered.metadata ->> 'score_pct', '')), '') order by filtered.created_at desc),
            null
        )
    )[1]::numeric as latest_score,
    count(*) filter (where filtered.event_type = 'student_improved')::bigint as improved_count,
    count(*) filter (where filtered.event_type = 'assignment_created')::bigint as assigned_count,
    count(*) filter (where filtered.event_type = 'teacher_marked_done')::bigint as teacher_marked_done_count,
    coalesce(
        array_agg(distinct nullif(trim(filtered.resource_kind), ''))
            filter (where nullif(trim(filtered.resource_kind), '') is not null),
        array[]::text[]
    ) as resource_kinds
from filtered
group by
    filtered.learning_program_assignment_id,
    filtered.learning_program_topic_id,
    filtered.recommendation_bucket;
$$;

create index if not exists idx_teacher_assignments_teacher_topic_updated_at
    on public.teacher_assignments (teacher_id, learning_program_topic_id, updated_at desc)
    where source_record_id is not null
      and learning_program_topic_id is not null
      and status <> 'archived';

create index if not exists idx_teacher_assignments_student_topic_updated_at
    on public.teacher_assignments (student_id, learning_program_topic_id, updated_at desc)
    where source_record_id is not null
      and learning_program_topic_id is not null
      and status <> 'archived';

create index if not exists idx_learning_program_recommendation_events_teacher_topic_created_at
    on public.learning_program_recommendation_events (teacher_id, learning_program_topic_id, created_at desc)
    where resource_record_id is not null
      and learning_program_topic_id is not null;

create index if not exists idx_learning_program_recommendation_events_student_topic_created_at
    on public.learning_program_recommendation_events (student_id, learning_program_topic_id, created_at desc)
    where resource_record_id is not null
      and learning_program_topic_id is not null;

create index if not exists idx_learning_program_topic_videos_teacher_created_at
    on public.learning_program_topic_videos (teacher_id, created_at desc);

create index if not exists idx_user_activity_log_user_activity_created_at
    on public.user_activity_log (user_id, activity_type, created_at desc);
