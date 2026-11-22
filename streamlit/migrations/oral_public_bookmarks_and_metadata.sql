-- Extend public bookmarks to oral activities and keep oral document metadata
-- consistent with the resource columns. Existing bookmarks are untouched.
begin;

alter table public.classio_saved_public_resources
  drop constraint if exists classio_saved_public_resources_resource_kind_check;
alter table public.classio_saved_public_resources
  add constraint classio_saved_public_resources_resource_kind_check
  check (resource_kind in ('program', 'plan', 'worksheet', 'exam', 'video', 'oral_presentation'));

create or replace function public.classio_save_public_resource(p_kind text, p_resource_id text)
returns boolean
language plpgsql security definer set search_path = public, pg_temp
as $$
declare
  v_table text;
  v_visible boolean;
begin
  if auth.uid() is null then
    raise exception 'Authentication required' using errcode = '42501';
  end if;
  if not exists (
    select 1 from public.profiles
    where user_id = auth.uid()::text and coalesce(can_teach, false)
  ) then
    raise exception 'Teacher account required' using errcode = '42501';
  end if;
  if p_resource_id is null or length(p_resource_id) not between 1 and 80 or p_resource_id !~ '^[0-9]+$' then
    raise exception 'Invalid resource ID' using errcode = '22023';
  end if;
  v_table := case p_kind
    when 'program' then 'learning_programs'
    when 'plan' then 'lesson_plans'
    when 'worksheet' then 'worksheets'
    when 'exam' then 'quick_exams'
    when 'video' then 'videos'
    when 'oral_presentation' then 'oral_presentations'
  end;
  if v_table is null then
    raise exception 'Invalid resource kind' using errcode = '22023';
  end if;
  execute format(
    'select exists(select 1 from public.%I where id::text = $1 and is_public is true and coalesce(status, ''active'') <> ''archived'')',
    v_table
  ) into v_visible using p_resource_id;
  if not v_visible then
    raise exception 'Public resource unavailable' using errcode = 'P0002';
  end if;
  insert into public.classio_saved_public_resources (user_id, resource_kind, resource_id)
    values (auth.uid(), p_kind, p_resource_id)
    on conflict do nothing;
  return true;
end;
$$;

revoke all on function public.classio_save_public_resource(text, text) from public, anon;
grant execute on function public.classio_save_public_resource(text, text) to authenticated;

create or replace function public.classio_sync_oral_resource_metadata()
returns trigger language plpgsql set search_path = public, pg_temp as $$
begin
  if (new.title, new.subject, new.topic, new.learner_stage, new.level_or_band)
     is distinct from
     (old.title, old.subject, old.topic, old.learner_stage, old.level_or_band) then
    new.oral_data := new.oral_data || jsonb_build_object(
      'title', new.title,
      'subject', new.subject,
      'topic', new.topic,
      'learner_stage', new.learner_stage,
      'level_or_band', new.level_or_band
    );
  end if;
  return new;
end;
$$;

drop trigger if exists classio_sync_oral_resource_metadata on public.oral_presentations;
create trigger classio_sync_oral_resource_metadata
  before update of title, subject, topic, learner_stage, level_or_band
  on public.oral_presentations
  for each row execute function public.classio_sync_oral_resource_metadata();

commit;
