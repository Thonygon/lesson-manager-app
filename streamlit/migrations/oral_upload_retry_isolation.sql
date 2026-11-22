-- Each submission request receives a fresh upload path. A failed prior request
-- cannot cause a newly recorded answer to be replaced with an older blob.
begin;

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
    -- A retry may be a newly recorded file. Never hand back a prior blob merely
    -- because the MIME matches. Queue the old object for physical deletion.
    delete from public.classio_oral_recordings where attempt_id=v_attempt.id;
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

create or replace function public.classio_guard_oral_recording_submission()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.status = 'submitted' and old.status is distinct from 'submitted'
     and not exists (
       select 1 from public.teacher_assignment_attempts a
       where a.id = new.attempt_id and a.status = 'started'
     ) then
    raise exception 'Oral attempt is no longer active' using errcode = '22023';
  end if;
  return new;
end; $$;

drop trigger if exists classio_guard_oral_recording_submission on public.classio_oral_recordings;
create trigger classio_guard_oral_recording_submission
  before update of status on public.classio_oral_recordings
  for each row execute function public.classio_guard_oral_recording_submission();

commit;
