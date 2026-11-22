-- Oral presentations extend the existing assignment/attempt ledger. Apply once
-- after add_video_library.sql and link_saved_generation_in_resource_insert.sql.
begin;

create table if not exists public.oral_presentations (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(btrim(title)) between 3 and 180),
  subject text not null default '', subject_family text not null default 'general',
  topic text not null default '', learner_stage text not null default '',
  level_or_band text not null default '', exercise_type text not null default '',
  plan_language text not null default 'en', student_material_language text not null default 'en',
  oral_data jsonb not null check (jsonb_typeof(oral_data) = 'object'),
  generation_operation_id uuid references public.classio_ai_operations(operation_id),
  is_public boolean not null default false,
  status text not null default 'active' check (status in ('active','archived')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index if not exists oral_presentations_generation_operation_uq
  on public.oral_presentations(generation_operation_id) where generation_operation_id is not null;
create index if not exists oral_presentations_owner_idx on public.oral_presentations(user_id, updated_at desc);
create index if not exists oral_presentations_public_idx on public.oral_presentations(is_public, status, created_at desc);
drop trigger if exists oral_presentations_updated_at on public.oral_presentations;
create trigger oral_presentations_updated_at before update on public.oral_presentations
  for each row execute function public.classio_set_updated_at();
alter table public.oral_presentations enable row level security;
grant select, insert, update, delete on public.oral_presentations to authenticated;
grant select on public.oral_presentations to anon;
grant usage, select on sequence public.oral_presentations_id_seq to authenticated;
drop policy if exists oral_presentations_read on public.oral_presentations;
create policy oral_presentations_read on public.oral_presentations for select to authenticated
  using (user_id = auth.uid() or (is_public and status = 'active'));
drop policy if exists oral_presentations_public_read on public.oral_presentations;
create policy oral_presentations_public_read on public.oral_presentations for select to anon
  using (is_public and status = 'active');
drop policy if exists oral_presentations_owner_insert on public.oral_presentations;
create policy oral_presentations_owner_insert on public.oral_presentations for insert to authenticated
  with check (user_id = auth.uid());
drop policy if exists oral_presentations_owner_update on public.oral_presentations;
create policy oral_presentations_owner_update on public.oral_presentations for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists oral_presentations_owner_delete on public.oral_presentations;
create policy oral_presentations_owner_delete on public.oral_presentations for delete to authenticated
  using (user_id = auth.uid());

-- The account-erasure RPC marks the profile deleted without deleting auth.users.
-- Remove this new resource family when that transaction reaches its final step.
create or replace function public.classio_erase_oral_resources_for_deleted_profile()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.account_status = 'deleted' and old.account_status is distinct from 'deleted' then
    delete from public.oral_presentations where user_id = new.user_id::uuid;
  end if;
  return new;
end; $$;
drop trigger if exists classio_erase_oral_resources_for_deleted_profile on public.profiles;
create trigger classio_erase_oral_resources_for_deleted_profile after update of account_status on public.profiles
  for each row execute function public.classio_erase_oral_resources_for_deleted_profile();

-- The same validated generation operation can be linked to an oral resource.
alter table public.classio_generation_resources
  drop constraint if exists classio_generation_resources_resource_type_check;
alter table public.classio_generation_resources
  add constraint classio_generation_resources_resource_type_check
  check (resource_type in ('plan','worksheet','exam','program','oral_presentation'));
drop trigger if exists classio_link_oral_generation on public.oral_presentations;
create trigger classio_link_oral_generation after insert on public.oral_presentations
  for each row execute function public.classio_link_saved_generation_on_insert('oral_presentation','generate_oral_presentation');
drop trigger if exists classio_lock_oral_generation on public.oral_presentations;
create trigger classio_lock_oral_generation before update of generation_operation_id on public.oral_presentations
  for each row execute function public.classio_prevent_generation_operation_reassignment();

alter table public.teacher_assignments drop constraint if exists teacher_assignments_assignment_type_check;
alter table public.teacher_assignments add constraint teacher_assignments_assignment_type_check
  check (assignment_type in ('worksheet','exam','lesson_plan_topic','video','oral_presentation'));
alter table public.teacher_assignments drop constraint if exists teacher_assignments_source_type_check;
alter table public.teacher_assignments add constraint teacher_assignments_source_type_check
  check (source_type in ('worksheet_builder','exam_builder','lesson_plan_builder','video_library','oral_presentation_builder'));
alter table public.teacher_assignment_attempts drop constraint if exists teacher_assignment_attempts_status_check;
alter table public.teacher_assignment_attempts add constraint teacher_assignment_attempts_status_check
  check (status in ('started','submitted','graded','completed','abandoned'));

create table if not exists public.classio_oral_recordings (
  id uuid primary key default gen_random_uuid(),
  attempt_id bigint not null unique references public.teacher_assignment_attempts(id) on delete cascade,
  assignment_id bigint not null references public.teacher_assignments(id) on delete cascade,
  student_id uuid not null references auth.users(id) on delete cascade,
  teacher_id uuid not null references auth.users(id) on delete cascade,
  object_path text not null unique,
  mime_type text not null check (mime_type in ('audio/webm','audio/mp4','audio/mpeg','audio/wav','audio/x-m4a')),
  byte_size integer check (byte_size between 1 and 15728640),
  duration_seconds integer check (duration_seconds between 1 and 600),
  audio_notice_version text not null,
  audio_notice_language text not null check (audio_notice_language in ('en','es','tr')),
  audio_acknowledged_at timestamptz not null,
  status text not null default 'uploading' check (status in ('uploading','submitted','expired','cleanup_failed')),
  submitted_at timestamptz, expires_at timestamptz,
  deleted_at timestamptz, cleanup_attempts integer not null default 0,
  cleanup_error text, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  check ((status = 'uploading' and submitted_at is null and expires_at is null) or
         (submitted_at is not null and expires_at is not null) or
         (status in ('expired','cleanup_failed') and submitted_at is null and expires_at is null))
);
create index if not exists classio_oral_recordings_expiry_idx on public.classio_oral_recordings(expires_at)
  where deleted_at is null;
create index if not exists classio_oral_recordings_teacher_idx on public.classio_oral_recordings(teacher_id, status, submitted_at desc);
-- An account or assignment purge cascades through attempts. Preserve only the
-- object path in a service-only queue so the Storage API can remove the blob.
create table if not exists public.classio_oral_audio_deletion_jobs (
  id uuid primary key default gen_random_uuid(),
  object_path text not null unique,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  attempts integer not null default 0,
  last_error text
);
alter table public.classio_oral_audio_deletion_jobs enable row level security;
revoke all on public.classio_oral_audio_deletion_jobs from public,anon,authenticated;
grant select,insert,update on public.classio_oral_audio_deletion_jobs to service_role;
create or replace function public.classio_queue_deleted_oral_audio()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.deleted_at is null then
    insert into public.classio_oral_audio_deletion_jobs(object_path)
      values (old.object_path) on conflict (object_path) do nothing;
  end if;
  return old;
end; $$;
drop trigger if exists classio_queue_deleted_oral_audio on public.classio_oral_recordings;
create trigger classio_queue_deleted_oral_audio before delete on public.classio_oral_recordings
  for each row execute function public.classio_queue_deleted_oral_audio();
alter table public.classio_oral_recordings enable row level security;
revoke all on public.classio_oral_recordings from public, anon, authenticated;
grant select on public.classio_oral_recordings to authenticated;
drop policy if exists classio_oral_recordings_participants on public.classio_oral_recordings;
create policy classio_oral_recordings_participants on public.classio_oral_recordings for select to authenticated
  using (student_id = auth.uid() or (teacher_id = auth.uid() and exists (
    select 1 from public.teacher_assignments a join public.teacher_student_links l on l.id=a.link_id
      where a.id=classio_oral_recordings.assignment_id
        and l.teacher_id=classio_oral_recordings.teacher_id
        and l.student_id=classio_oral_recordings.student_id and l.status='active'
  )));

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values ('classio-oral-audio','classio-oral-audio',false,15728640,
        array['audio/webm','audio/mp4','audio/mpeg','audio/wav','audio/x-m4a'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
drop policy if exists classio_oral_audio_upload on storage.objects;
create policy classio_oral_audio_upload on storage.objects for insert to authenticated
with check (bucket_id = 'classio-oral-audio' and exists (
  select 1 from public.classio_oral_recordings r where r.object_path = name
    and r.student_id = auth.uid() and r.status = 'uploading'
    and r.created_at > now() - interval '2 hours'
));
drop policy if exists classio_oral_audio_read on storage.objects;
create policy classio_oral_audio_read on storage.objects for select to authenticated
using (bucket_id = 'classio-oral-audio' and exists (
  select 1 from public.classio_oral_recordings r where r.object_path = name
    and r.deleted_at is null and (r.student_id = auth.uid() or (r.teacher_id = auth.uid() and exists (
      select 1 from public.teacher_assignments a join public.teacher_student_links l on l.id=a.link_id
        where a.id=r.assignment_id and l.teacher_id=r.teacher_id and l.student_id=r.student_id and l.status='active'
    )))
    and (r.status = 'uploading' and r.student_id = auth.uid() and r.created_at > now() - interval '2 hours'
      or r.status in ('submitted','cleanup_failed') and r.expires_at > now())
));

-- An oral attempt is written only through these security-definer RPCs. Other
-- assignment types retain their existing policies and client behavior.
create or replace function public.classio_guard_oral_attempt()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if exists (select 1 from public.teacher_assignments a
             where a.id = new.assignment_id and a.assignment_type = 'oral_presentation')
     and current_setting('classio.oral_rpc', true) is distinct from 'authorized' then
    raise exception 'Oral attempts require the authorized workflow' using errcode = '42501';
  end if;
  return new;
end; $$;
drop trigger if exists classio_guard_oral_attempt on public.teacher_assignment_attempts;
create trigger classio_guard_oral_attempt before insert or update on public.teacher_assignment_attempts
  for each row execute function public.classio_guard_oral_attempt();

-- An oral task must carry the teacher's explicit authorization attestation.
create or replace function public.classio_require_oral_assignment_authorization()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.assignment_type = 'oral_presentation' then
    if new.source_type <> 'oral_presentation_builder' or
       jsonb_typeof(new.content_snapshot->'oral_data') is distinct from 'object' then
      raise exception 'A valid oral resource snapshot is required' using errcode='22023';
    end if;
    if (new.content_snapshot->>'audio_authorization_acknowledged') is distinct from 'true' then
      raise exception 'Teacher authorization for the oral assignment is required' using errcode='22023';
    end if;
  end if;
  return new;
end; $$;
drop trigger if exists classio_require_oral_assignment_authorization on public.teacher_assignments;
create trigger classio_require_oral_assignment_authorization before insert on public.teacher_assignments
  for each row execute function public.classio_require_oral_assignment_authorization();

-- Existing assignment RLS lets a learner update their own row. Oral grades
-- and submission state must instead come from the dedicated RPCs.
create or replace function public.classio_guard_oral_assignment()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.assignment_type = 'oral_presentation' and (
      new.assignment_type is distinct from old.assignment_type or
      new.source_type is distinct from old.source_type or
      new.source_record_id is distinct from old.source_record_id or
      new.teacher_id is distinct from old.teacher_id or
      new.student_id is distinct from old.student_id or
      new.link_id is distinct from old.link_id or
      new.content_snapshot is distinct from old.content_snapshot) then
    raise exception 'Oral assignment snapshot and participants are immutable' using errcode = '42501';
  end if;
  if old.assignment_type = 'oral_presentation' and auth.uid() = old.student_id
     and current_setting('classio.oral_rpc', true) is distinct from 'authorized'
     and (to_jsonb(new) - 'viewed_at' - 'opened_at' - 'updated_at')
      is distinct from (to_jsonb(old) - 'viewed_at' - 'opened_at' - 'updated_at') then
    raise exception 'Oral assignments require the authorized workflow' using errcode = '42501';
  end if;
  if old.assignment_type = 'oral_presentation' and auth.uid() = old.teacher_id
     and current_setting('classio.oral_rpc', true) is distinct from 'authorized'
     and (new.score_pct is distinct from old.score_pct or new.graded_at is distinct from old.graded_at
       or new.completed_at is distinct from old.completed_at
       or (new.status is distinct from old.status and new.status <> 'archived')) then
    raise exception 'Oral assessment requires the review workflow' using errcode = '42501';
  end if;
  return new;
end; $$;
drop trigger if exists classio_guard_oral_assignment on public.teacher_assignments;
create trigger classio_guard_oral_assignment before update on public.teacher_assignments
  for each row execute function public.classio_guard_oral_assignment();

create or replace function public.classio_begin_oral_submission(p_assignment_id bigint, p_mime text,
  p_notice_version text, p_notice_language text, p_acknowledged boolean)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_assignment public.teacher_assignments%rowtype;
        v_attempt public.teacher_assignment_attempts%rowtype;
        v_recording public.classio_oral_recordings%rowtype;
        v_extension text; v_number integer;
begin
  if auth.uid() is null then raise exception 'Authentication required' using errcode='42501'; end if;
  if p_acknowledged is distinct from true or coalesce(p_notice_version,'') !~ '^20[0-9]{2}-[0-9]{2}-[0-9]{2}\.[0-9]+$'
     or coalesce(p_notice_language,'') not in ('en','es','tr') then
    raise exception 'Audio notice acknowledgment required' using errcode='22023';
  end if;
  select * into v_assignment from public.teacher_assignments where id=p_assignment_id for update;
  if not found or v_assignment.student_id <> auth.uid() or v_assignment.assignment_type <> 'oral_presentation'
     or v_assignment.status not in ('assigned','started') then
    raise exception 'Oral assignment unavailable' using errcode='42501';
  end if;
  if not exists (select 1 from public.teacher_student_links l where l.id=v_assignment.link_id
                 and l.teacher_id=v_assignment.teacher_id and l.student_id=auth.uid() and l.status='active') then
    raise exception 'Teacher connection inactive' using errcode='42501';
  end if;
  v_extension := case p_mime when 'audio/webm' then '.webm' when 'audio/mp4' then '.m4a'
    when 'audio/x-m4a' then '.m4a' when 'audio/mpeg' then '.mp3' when 'audio/wav' then '.wav' else null end;
  if v_extension is null then raise exception 'Unsupported audio format' using errcode='22023'; end if;
  select * into v_attempt from public.teacher_assignment_attempts
    where assignment_id=p_assignment_id and student_id=auth.uid() and status='started'
    order by id desc limit 1 for update;
  if found then
    select * into v_recording from public.classio_oral_recordings where attempt_id=v_attempt.id;
    if v_recording.id is not null and v_recording.mime_type=p_mime and v_recording.created_at > now()-interval '2 hours' then
      return jsonb_build_object('attempt_id',v_attempt.id,'recording_id',v_recording.id,'path',v_recording.object_path);
    end if;
    if v_recording.created_at > now()-interval '2 hours' then
      raise exception 'An upload is still in progress' using errcode='22023';
    end if;
    perform set_config('classio.oral_rpc','authorized',true);
    update public.teacher_assignment_attempts set status='abandoned',updated_at=now() where id=v_attempt.id;
  end if;
  select coalesce(max(attempt_number),0)+1 into v_number from public.teacher_assignment_attempts where assignment_id=p_assignment_id;
  perform set_config('classio.oral_rpc','authorized',true);
  insert into public.teacher_assignment_attempts(assignment_id,teacher_id,student_id,attempt_number,status,started_at)
    values (p_assignment_id,v_assignment.teacher_id,auth.uid(),v_number,'started',now()) returning * into v_attempt;
  insert into public.classio_oral_recordings(attempt_id,assignment_id,student_id,teacher_id,object_path,mime_type,
    audio_notice_version,audio_notice_language,audio_acknowledged_at)
    values (v_attempt.id,p_assignment_id,auth.uid(),v_assignment.teacher_id,
      auth.uid()::text||'/'||v_attempt.id::text||'/'||gen_random_uuid()::text||v_extension,p_mime,
      p_notice_version,p_notice_language,now())
    returning * into v_recording;
  update public.teacher_assignments set status='started',opened_at=coalesce(opened_at,now()) where id=p_assignment_id;
  return jsonb_build_object('attempt_id',v_attempt.id,'recording_id',v_recording.id,'path',v_recording.object_path);
end; $$;
revoke all on function public.classio_begin_oral_submission(bigint,text,text,text,boolean) from public,anon;
grant execute on function public.classio_begin_oral_submission(bigint,text,text,text,boolean) to authenticated;

create or replace function public.classio_submit_oral_recording(p_recording_id uuid, p_duration_seconds integer)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_recording public.classio_oral_recordings%rowtype;
        v_assignment public.teacher_assignments%rowtype;
        v_object storage.objects%rowtype; v_size bigint; v_mime text; v_max integer;
begin
  select * into v_recording from public.classio_oral_recordings where id=p_recording_id for update;
  if not found or v_recording.student_id <> auth.uid() then raise exception 'Recording unavailable' using errcode='42501'; end if;
  if v_recording.status='submitted' then return jsonb_build_object('attempt_id',v_recording.attempt_id,'status','submitted'); end if;
  select * into v_assignment from public.teacher_assignments where id=v_recording.assignment_id for update;
  if not exists (select 1 from public.teacher_student_links l where l.id=v_assignment.link_id
                 and l.teacher_id=v_assignment.teacher_id and l.student_id=v_recording.student_id and l.status='active') then
    raise exception 'Teacher connection inactive' using errcode='42501';
  end if;
  if v_recording.status<>'uploading' or v_assignment.status<>'started' or v_recording.created_at < now()-interval '2 hours' then
    raise exception 'Upload expired; start again' using errcode='22023';
  end if;
  v_max := coalesce((v_assignment.content_snapshot->'oral_data'->>'max_duration_seconds')::integer,180);
  if p_duration_seconds < 1 or p_duration_seconds > least(v_max,600) then raise exception 'Recording duration is outside the allowed range' using errcode='22023'; end if;
  select * into v_object from storage.objects where bucket_id='classio-oral-audio' and name=v_recording.object_path;
  if not found then raise exception 'Audio upload has not completed' using errcode='22023'; end if;
  v_size := (v_object.metadata->>'size')::bigint;
  v_mime := lower(split_part(coalesce(v_object.metadata->>'mimetype',''),';',1));
  if v_size is null or v_size < 1 or v_size > 15728640 or v_mime <> v_recording.mime_type then
    raise exception 'Audio size or type is invalid' using errcode='22023';
  end if;
  update public.classio_oral_recordings set byte_size=v_size::integer,duration_seconds=p_duration_seconds,
    status='submitted',submitted_at=now(),expires_at=now()+interval '30 days',updated_at=now()
    where id=p_recording_id;
  perform set_config('classio.oral_rpc','authorized',true);
  update public.teacher_assignment_attempts set status='submitted',submitted_at=now(),updated_at=now()
    where id=v_recording.attempt_id;
  update public.teacher_assignments set status='submitted',submitted_at=now(),updated_at=now()
    where id=v_recording.assignment_id;
  return jsonb_build_object('attempt_id',v_recording.attempt_id,'status','submitted');
end; $$;
revoke all on function public.classio_submit_oral_recording(uuid,integer) from public,anon;
grant execute on function public.classio_submit_oral_recording(uuid,integer) to authenticated;

create or replace function public.classio_review_oral_submission(p_attempt_id bigint, p_scores jsonb, p_feedback text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare v_attempt public.teacher_assignment_attempts%rowtype;
        v_assignment public.teacher_assignments%rowtype;
        v_rubric jsonb; v_criterion jsonb; v_score numeric; v_max numeric:=0; v_total numeric:=0;
        v_key text; v_count integer:=0; v_pct numeric;
begin
  select * into v_attempt from public.teacher_assignment_attempts where id=p_attempt_id for update;
  if not found or v_attempt.teacher_id <> auth.uid() or v_attempt.status <> 'submitted' then
    raise exception 'Oral submission unavailable for review' using errcode='42501';
  end if;
  select * into v_assignment from public.teacher_assignments where id=v_attempt.assignment_id for update;
  if v_assignment.assignment_type <> 'oral_presentation' then raise exception 'Wrong assignment type' using errcode='22023'; end if;
  if not exists (select 1 from public.teacher_student_links l where l.id=v_assignment.link_id
    and l.teacher_id=v_assignment.teacher_id and l.student_id=v_assignment.student_id and l.status='active') then
    raise exception 'Teacher connection inactive' using errcode='42501';
  end if;
  if not exists (select 1 from public.classio_oral_recordings r where r.attempt_id=p_attempt_id
    and r.status='submitted' and r.deleted_at is null and r.expires_at>now()) then
    raise exception 'The audio is no longer available for review' using errcode='22023';
  end if;
  v_rubric := v_assignment.content_snapshot->'oral_data'->'rubric';
  if jsonb_typeof(v_rubric) <> 'array' or jsonb_array_length(v_rubric) not between 2 and 8
     or jsonb_typeof(p_scores) <> 'object' or char_length(coalesce(p_feedback,'')) > 2000 then
    raise exception 'Invalid rubric or feedback' using errcode='22023';
  end if;
  for v_criterion in select value from jsonb_array_elements(v_rubric) loop
    v_key := v_criterion->>'id';
    if v_key is null or not p_scores ? v_key or (v_criterion->>'max_score') !~ '^([1-9]|1[0-9]|20)$'
       or (p_scores->>v_key) !~ '^[0-9]+(\.[0-9])?$' then
      raise exception 'Every criterion needs a valid score' using errcode='22023';
    end if;
    v_score := (p_scores->>v_key)::numeric;
    if v_score > (v_criterion->>'max_score')::numeric then raise exception 'Score exceeds rubric maximum' using errcode='22023'; end if;
    v_total := v_total+v_score; v_max := v_max+(v_criterion->>'max_score')::numeric; v_count:=v_count+1;
  end loop;
  if (select count(*) from jsonb_object_keys(p_scores)) <> v_count then raise exception 'Unexpected rubric criterion' using errcode='22023'; end if;
  v_pct := round(100*v_total/nullif(v_max,0),1);
  perform set_config('classio.oral_rpc','authorized',true);
  update public.teacher_assignment_attempts set status='graded',score_pct=v_pct,
    submission_payload=jsonb_build_object('rubric_scores',p_scores,'rubric',v_rubric),
    teacher_feedback=coalesce(p_feedback,''),graded_at=now(),completed_at=now(),updated_at=now()
    where id=p_attempt_id;
  update public.teacher_assignments set status='graded',score_pct=v_pct,graded_at=now(),completed_at=now(),updated_at=now()
    where id=v_attempt.assignment_id;
  return jsonb_build_object('score_pct',v_pct,'attempt_id',p_attempt_id);
end; $$;
revoke all on function public.classio_review_oral_submission(bigint,jsonb,text) from public,anon;
grant execute on function public.classio_review_oral_submission(bigint,jsonb,text) to authenticated;

create or replace function public.classio_retry_oral_assignment(p_assignment_id bigint)
returns void language plpgsql security definer set search_path = '' as $$
declare v_assignment public.teacher_assignments%rowtype;
begin
  select * into v_assignment from public.teacher_assignments where id=p_assignment_id for update;
  if not found or v_assignment.teacher_id<>auth.uid() or v_assignment.assignment_type<>'oral_presentation'
     or v_assignment.status<>'graded' then raise exception 'Reviewed oral assignment required' using errcode='42501'; end if;
  if not exists (select 1 from public.teacher_student_links l where l.id=v_assignment.link_id
    and l.teacher_id=v_assignment.teacher_id and l.student_id=v_assignment.student_id and l.status='active') then
    raise exception 'Teacher connection inactive' using errcode='42501';
  end if;
  perform set_config('classio.oral_rpc','authorized',true);
  update public.teacher_assignments set status='assigned',score_pct=null,submitted_at=null,graded_at=null,
    completed_at=null,updated_at=now() where id=p_assignment_id;
end; $$;
revoke all on function public.classio_retry_oral_assignment(bigint) from public,anon;
grant execute on function public.classio_retry_oral_assignment(bigint) to authenticated;

-- Service-role cleanup worker uses these two RPCs. Access stops at expires_at,
-- even if the Storage API is temporarily unavailable.
create or replace function public.classio_oral_cleanup_queue(p_limit integer default 100)
returns table(id uuid, object_path text) language sql security definer set search_path = '' as $$
  select q.id,q.object_path from (
    select r.id,r.object_path,coalesce(r.expires_at,r.created_at) as due_at
      from public.classio_oral_recordings r
      where r.deleted_at is null and (r.expires_at <= now() or
        (r.status in ('uploading','cleanup_failed') and r.submitted_at is null
          and r.created_at <= now()-interval '1 day'))
    union all
    select j.id,j.object_path,j.created_at
      from public.classio_oral_audio_deletion_jobs j where j.deleted_at is null
  ) q order by q.due_at limit least(greatest(p_limit,1),100);
$$;
revoke all on function public.classio_oral_cleanup_queue(integer) from public,anon,authenticated;
grant execute on function public.classio_oral_cleanup_queue(integer) to service_role;
create or replace function public.classio_oral_cleanup_result(p_id uuid,p_success boolean,p_error text default null)
returns void language plpgsql security definer set search_path = '' as $$
begin
  update public.classio_oral_recordings set status=case when p_success then 'expired' else 'cleanup_failed' end,
    deleted_at=case when p_success then now() else null end,
    cleanup_attempts=cleanup_attempts+1,cleanup_error=case when p_success then null else left(coalesce(p_error,'unknown'),300) end,
    updated_at=now() where id=p_id and deleted_at is null;
  update public.classio_oral_audio_deletion_jobs set deleted_at=case when p_success then now() else null end,
    attempts=attempts+1,last_error=case when p_success then null else left(coalesce(p_error,'unknown'),300) end
    where id=p_id and deleted_at is null;
end; $$;
revoke all on function public.classio_oral_cleanup_result(uuid,boolean,text) from public,anon,authenticated;
grant execute on function public.classio_oral_cleanup_result(uuid,boolean,text) to service_role;

commit;
