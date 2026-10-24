-- A video watch creates its session, progress and assignment attempt together.
-- The client supplies one UUID per playback so retries return the same session.
alter table public.practice_sessions add column if not exists watch_event_id uuid;
create unique index if not exists practice_sessions_watch_event_uq
    on public.practice_sessions(user_id, watch_event_id) where watch_event_id is not null;

create or replace function public.classio_record_student_video_watch(p_watch_event_id uuid, p_video jsonb)
returns bigint language plpgsql security definer set search_path = '' as $$
declare
    v_uid uuid := auth.uid();
    v_now timestamptz := now();
    v_existing bigint;
    v_video public.videos%rowtype;
    v_assignment public.teacher_assignments%rowtype;
    v_assignment_id bigint := nullif(p_video->>'assignment_id','')::bigint;
    v_scope text;
    v_progress public.practice_progress%rowtype;
    v_session_id bigint;
    v_attempt_no integer;
begin
    if v_uid is null or p_watch_event_id is null or jsonb_typeof(p_video) <> 'object'
       or (p_video->>'video_id') !~ '^[1-9][0-9]*$' then
        raise exception 'Invalid video watch' using errcode = '22023';
    end if;
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_uid::text, 314159));
    select id into v_existing from public.practice_sessions
     where user_id = v_uid and watch_event_id = p_watch_event_id;
    if found then return v_existing; end if;
    select * into v_video from public.videos where id = (p_video->>'video_id')::bigint;
    if not found then raise exception 'Video unavailable' using errcode = '42501'; end if;
    if v_assignment_id is not null then
        select * into v_assignment from public.teacher_assignments
         where id = v_assignment_id and student_id = v_uid for update;
        if not found or v_assignment.status = 'cancelled' or v_assignment.assignment_type <> 'video'
           or v_assignment.source_record_id is distinct from v_video.id::text
           or v_assignment.teacher_id is distinct from nullif(p_video->>'teacher_id','')::uuid then
            raise exception 'Video assignment unavailable' using errcode = '42501';
        end if;
    elsif not v_video.is_public and v_video.user_id <> v_uid then
        raise exception 'Video unavailable' using errcode = '42501';
    end if;
    v_scope := case when v_assignment_id is null then 'independent' else 'assignment:' || v_assignment_id end;
    insert into public.practice_sessions
        (user_id,watch_event_id,source_type,source_id,title,subject,topic,learner_stage,level,
         exercise_data,total_questions,correct_count,score_pct,xp_earned,best_streak,status,
         started_at,completed_at,created_at)
    values (v_uid,p_watch_event_id,'video',coalesce(v_assignment_id::text,v_video.id::text),
         v_video.title,v_video.subject,v_video.topic,v_video.learner_stage,v_video.level_or_band,
         pg_catalog.jsonb_build_object('source_type','video','source_id',v_video.id,'title',v_video.title,
           'subject',v_video.subject,'topic',v_video.topic,'level',v_video.level_or_band,
           'watch_url',coalesce(v_video.youtube_url,''),'engagement_type','video_watch'),
         1,0,0,6,1,'completed',v_now,v_now,v_now) returning id into v_session_id;
    select * into v_progress from public.practice_progress
     where user_id = v_uid and scope_key = v_scope and source_type = 'video'
       and subject = v_video.subject and topic = v_video.topic
       and exercise_type = 'video_watch' and level = v_video.level_or_band for update;
    if found then
        update public.practice_progress set total_attempted = v_progress.total_attempted + 1,
            total_xp = v_progress.total_xp + 6, best_streak = greatest(v_progress.best_streak,1),
            last_practiced = v_now where id = v_progress.id;
    else
        insert into public.practice_progress
            (user_id,scope_key,source_type,teacher_id,assignment_id,subject,topic,exercise_type,
             level,total_attempted,total_correct,accuracy_pct,total_xp,best_streak,last_practiced,created_at)
        values (v_uid,v_scope,'video',case when v_assignment_id is null then null else v_assignment.teacher_id end,
            v_assignment_id,v_video.subject,v_video.topic,'video_watch',v_video.level_or_band,
            1,0,0,6,1,v_now,v_now);
    end if;
    if v_assignment_id is not null then
        select coalesce(max(attempt_number),0) + 1 into v_attempt_no
          from public.teacher_assignment_attempts where assignment_id = v_assignment_id and student_id = v_uid;
        insert into public.teacher_assignment_attempts
            (assignment_id,teacher_id,student_id,practice_session_id,attempt_number,status,score_pct,
             total_questions,correct_count,submission_payload,started_at,submitted_at,graded_at,completed_at,created_at,updated_at)
        values (v_assignment_id,v_assignment.teacher_id,v_uid,v_session_id,v_attempt_no,'completed',100,
            1,1,pg_catalog.jsonb_build_object('source_type','video','source_id',v_video.id,
            'title',v_video.title,'watch_event','student_video_watch'),v_now,v_now,v_now,v_now,v_now,v_now);
        update public.teacher_assignments set status='completed',score_pct=100,total_questions=1,
            correct_count=1,opened_at=v_now,submitted_at=v_now,graded_at=v_now,
            completed_at=v_now,updated_at=v_now where id = v_assignment_id;
    end if;
    return v_session_id;
end;
$$;
revoke all on function public.classio_record_student_video_watch(uuid,jsonb) from public, anon;
grant execute on function public.classio_record_student_video_watch(uuid,jsonb) to authenticated;
