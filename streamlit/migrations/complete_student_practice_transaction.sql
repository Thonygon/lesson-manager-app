-- Completing a worksheet/exam must either persist every derived row or none.
-- The existing draft session is the idempotency key for a retried submission.
create or replace function public.classio_complete_student_practice(
    p_session_id bigint,
    p_result jsonb
) returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_uid uuid := auth.uid();
    v_session public.practice_sessions%rowtype;
    v_assignment public.teacher_assignments%rowtype;
    v_answer jsonb;
    v_group jsonb;
    v_progress public.practice_progress%rowtype;
    v_answer_count integer;
    v_group_count integer;
    v_attempt_no integer;
    v_now timestamptz := now();
    v_attempted integer;
    v_correct integer;
    v_xp integer;
    v_total_attempted integer;
    v_total_correct integer;
    v_scope text;
begin
    if v_uid is null or p_session_id is null or jsonb_typeof(p_result) <> 'object' then
        raise exception 'Invalid practice completion' using errcode = '22023';
    end if;
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(v_uid::text, 314159));
    select * into v_session from public.practice_sessions
    where id = p_session_id and user_id = v_uid for update;
    if not found then
        raise exception 'Practice draft not found' using errcode = '42501';
    end if;
    if v_session.status = 'completed' then
        return v_session.id;
    end if;
    if v_session.status <> 'in_progress' or v_session.source_type not in ('worksheet', 'exam') then
        raise exception 'Practice draft cannot be completed' using errcode = '22023';
    end if;
    v_answer_count := jsonb_array_length(coalesce(p_result->'answers', '[]'::jsonb));
    v_group_count := jsonb_array_length(coalesce(p_result->'progress', '[]'::jsonb));
    if v_answer_count > 500 or v_group_count > 50 or v_answer_count < 1
       or v_group_count < 1 or p_result->>'total' is null or p_result->>'correct' is null
       or p_result->>'score' is null or p_result->>'xp' is null
       or p_result->>'best_streak' is null
       or (p_result->>'total')::integer not between 1 and 500
       or (p_result->>'correct')::integer not between 0 and (p_result->>'total')::integer
       or (p_result->>'score')::numeric not between 0 and 100
       or (p_result->>'xp')::integer not between 0 and 100000
       or (p_result->>'best_streak')::integer not between 0 and 500 then
        raise exception 'Invalid practice result' using errcode = '22023';
    end if;
    if p_result->>'source_type' is distinct from v_session.source_type
       or p_result->>'source_id' is distinct from v_session.source_id then
        raise exception 'Practice source changed' using errcode = '22023';
    end if;
    if nullif(p_result->>'assignment_id','') is distinct from
       nullif(v_session.exercise_data->>'assignment_id','') then
        raise exception 'Practice assignment changed' using errcode = '22023';
    end if;
    update public.practice_sessions set
        exercise_data = coalesce(p_result->'exercise_data', v_session.exercise_data),
        total_questions = (p_result->>'total')::integer,
        correct_count = (p_result->>'correct')::integer,
        score_pct = (p_result->>'score')::numeric,
        xp_earned = (p_result->>'xp')::integer,
        best_streak = (p_result->>'best_streak')::integer,
        status = 'completed', completed_at = v_now
    where id = v_session.id;
    delete from public.practice_answers where session_id = v_session.id and user_id = v_uid;
    for v_answer in select value from jsonb_array_elements(p_result->'answers') loop
        insert into public.practice_answers
            (session_id,user_id,exercise_idx,question_idx,exercise_type,student_answer,correct_answer,is_correct,answered_at)
        values (
            v_session.id,v_uid,(v_answer->>'exercise_index')::integer,
            (v_answer->>'question_index')::integer,v_answer->>'exercise_type',
            coalesce(v_answer->>'student_answer',''),coalesce(v_answer->>'correct_answer',''),
            coalesce((v_answer->>'is_correct')::boolean,false),v_now
        );
    end loop;
    v_scope := case when nullif(p_result->>'assignment_id','') is null then 'independent'
                    else 'assignment:' || (p_result->>'assignment_id') end;
    for v_group in select value from jsonb_array_elements(p_result->'progress') loop
        v_attempted := (v_group->>'attempted')::integer;
        v_correct := (v_group->>'correct')::integer;
        v_xp := (v_group->>'xp')::integer;
        if v_attempted not between 1 and 500 or v_correct not between 0 and v_attempted
           or v_xp not between 0 and 100000 or length(v_group->>'exercise_type') > 100 then
            raise exception 'Invalid practice progress' using errcode = '22023';
        end if;
        select * into v_progress from public.practice_progress
        where user_id = v_uid and scope_key = v_scope and source_type = v_session.source_type
          and subject = v_session.subject and topic = v_session.topic
          and exercise_type = v_group->>'exercise_type' and level = v_session.level
        for update;
        if found then
            v_total_attempted := v_progress.total_attempted + v_attempted;
            v_total_correct := v_progress.total_correct + v_correct;
            update public.practice_progress set
                total_attempted = v_total_attempted,total_correct = v_total_correct,
                accuracy_pct = round(100.0 * v_total_correct / greatest(v_total_attempted,1),1),
                total_xp = v_progress.total_xp + v_xp,
                best_streak = greatest(v_progress.best_streak,(p_result->>'best_streak')::integer),
                last_practiced = v_now
            where id = v_progress.id;
        else
            insert into public.practice_progress
                (user_id,scope_key,source_type,teacher_id,assignment_id,learning_program_assignment_id,
                 subject,topic,exercise_type,level,total_attempted,total_correct,accuracy_pct,total_xp,best_streak,last_practiced)
            values (
                v_uid,v_scope,v_session.source_type,nullif(p_result->>'teacher_id','')::uuid,
                nullif(p_result->>'assignment_id','')::bigint,
                nullif(p_result->>'learning_program_assignment_id','')::bigint,
                v_session.subject,v_session.topic,v_group->>'exercise_type',v_session.level,
                v_attempted,v_correct,round(100.0 * v_correct / v_attempted,1),v_xp,
                (p_result->>'best_streak')::integer,v_now
            );
        end if;
    end loop;
    if nullif(p_result->>'assignment_id','') is not null then
        select * into v_assignment from public.teacher_assignments
        where id = (p_result->>'assignment_id')::bigint and student_id = v_uid for update;
        if not found or v_assignment.status = 'cancelled'
           or v_assignment.teacher_id is distinct from nullif(p_result->>'teacher_id','')::uuid then
            raise exception 'Assignment is unavailable for this learner' using errcode = '42501';
        end if;
        select coalesce(max(attempt_number),0) + 1 into v_attempt_no
        from public.teacher_assignment_attempts where assignment_id = v_assignment.id and student_id = v_uid;
        insert into public.teacher_assignment_attempts
            (assignment_id,teacher_id,student_id,practice_session_id,attempt_number,status,score_pct,
             total_questions,correct_count,submission_payload,started_at,submitted_at,graded_at,completed_at,created_at,updated_at)
        values (v_assignment.id,v_assignment.teacher_id,v_uid,v_session.id,v_attempt_no,'graded',
            (p_result->>'score')::numeric,(p_result->>'total')::integer,(p_result->>'correct')::integer,
            jsonb_build_object('result',p_result->'graded','source_type',v_session.source_type,
                'source_id',p_result->>'material_source_id','title',v_session.title),
            v_now,v_now,v_now,v_now,v_now,v_now);
        update public.teacher_assignments set status='graded',score_pct=(p_result->>'score')::numeric,
            total_questions=(p_result->>'total')::integer,correct_count=(p_result->>'correct')::integer,
            opened_at=v_now,submitted_at=v_now,graded_at=v_now,completed_at=v_now,updated_at=v_now
        where id=v_assignment.id;
    end if;
    return v_session.id;
end;
$$;

revoke all on function public.classio_complete_student_practice(bigint,jsonb) from public, anon;
grant execute on function public.classio_complete_student_practice(bigint,jsonb) to authenticated;
