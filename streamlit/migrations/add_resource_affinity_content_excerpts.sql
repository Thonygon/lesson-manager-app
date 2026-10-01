-- Optional support view for Experiment 3.
-- Purpose: expose bounded text excerpts for resource affinity without sending
-- large worksheet/exam JSON payloads to the application runtime.
--
-- This is read-only support for analysis. It excludes answer keys, solutions,
-- images/media/base64/url-like fields, and returns short text fragments only.

create or replace function public.classio_resource_affinity_json_excerpt(
    payload jsonb,
    max_fragments integer default 12,
    fragment_chars integer default 160,
    total_chars integer default 1400
)
returns text
language sql
stable
as $$
with recursive walk(path, value, depth) as (
    select array[]::text[], payload, 0
    where payload is not null
    union all
    select
        case
            when child.kind = 'object' then walk.path || child.key
            else walk.path
        end as path,
        child.value,
        walk.depth + 1
    from walk
    cross join lateral (
        select
            'object'::text as kind,
            obj.key,
            obj.value,
            null::bigint as ord
        from jsonb_each(
            case when jsonb_typeof(walk.value) = 'object' then walk.value else '{}'::jsonb end
        ) as obj(key, value)

        union all

        select
            'array'::text as kind,
            ''::text as key,
            arr.value,
            arr.ord
        from jsonb_array_elements(
            case when jsonb_typeof(walk.value) = 'array' then walk.value else '[]'::jsonb end
        ) with ordinality as arr(value, ord)
        where arr.ord <= 30
    ) as child
    where walk.depth < 8
      and not exists (
          select 1
          from unnest(
              case
                  when child.kind = 'object' then walk.path || child.key
                  else walk.path
              end
          ) as key_part
          where lower(key_part) ~ '(answer|answer_key|correct|solution|explanation|image|image_url|image_base64|base64|svg|audio|video|file|url)'
      )
),
preferred_scalars as (
    select
        left(regexp_replace(value #>> '{}', '\s+', ' ', 'g'), fragment_chars) as fragment
    from walk
    where jsonb_typeof(value) in ('string', 'number')
      and exists (
          select 1
          from unnest(path) as key_part
          where lower(key_part) ~ '(instruction|prompt|question|stem|option|choice|passage|reading|text|sentence|paragraph|word|vocabulary|dialogue|task|activity)'
      )
      and length(value #>> '{}') > 0
      and value #>> '{}' !~* '(data:image|base64|<svg|ivborw0kggo|/9j/|https?://)'
    limit greatest(1, max_fragments)
),
bounded as (
    select string_agg(fragment, ' ') as excerpt
    from preferred_scalars
)
select left(coalesce(excerpt, ''), greatest(1, total_chars))
from bounded;
$$;

create or replace view public.resource_affinity_content_excerpts as
select
    'worksheet'::text as resource_type,
    worksheets.id::text as resource_id,
    excerpt.content_excerpt,
    'sanitized_worksheet_json_view'::text as content_excerpt_source,
    length(excerpt.content_excerpt) as content_excerpt_char_count
from public.worksheets
cross join lateral (
    select public.classio_resource_affinity_json_excerpt(worksheets.worksheet_json::jsonb) as content_excerpt
) as excerpt
where worksheet_json is not null
  and excerpt.content_excerpt <> ''

union all

select
    'exam'::text as resource_type,
    quick_exams.id::text as resource_id,
    excerpt.content_excerpt,
    'sanitized_exam_data_view'::text as content_excerpt_source,
    length(excerpt.content_excerpt) as content_excerpt_char_count
from public.quick_exams
cross join lateral (
    select public.classio_resource_affinity_json_excerpt(quick_exams.exam_data::jsonb) as content_excerpt
) as excerpt
where exam_data is not null
  and excerpt.content_excerpt <> '';

alter view public.resource_affinity_content_excerpts
set (security_invoker = true);
