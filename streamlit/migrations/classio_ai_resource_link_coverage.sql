-- Coverage starts when resource links became atomic in Expo. An unlinked
-- operation may reflect a teacher who chose not to save; it is not a failure.
create or replace view public.classio_ai_resource_link_coverage as
select
    o.feature_name,
    count(*)::bigint as successful_operations,
    count(r.generation_id)::bigint as linked_resources,
    count(*) filter (where r.generation_id is null)::bigint as unlinked_operations,
    max(o.finished_at) as latest_finished_at
from public.classio_ai_operations o
left join public.classio_generation_resources r on r.generation_id = o.operation_id
where o.source = 'expo'
  and o.actor_user_id is not null
  and o.modality = 'text'
  and o.status = 'success'
  and o.feature_name in ('generate_plan', 'generate_worksheet', 'generate_exam')
  and o.started_at >= (
      select applied_at from public.app_schema_migrations
      where name = 'link_saved_generation_in_resource_insert.sql'
  )
group by o.feature_name;

revoke all on public.classio_ai_resource_link_coverage from public, anon, authenticated;
grant select on public.classio_ai_resource_link_coverage to service_role;
