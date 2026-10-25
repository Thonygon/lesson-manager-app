-- Repair progress buckets for teacher reviews committed before atomic refresh.
-- Source of truth: persisted completed sessions, answers and assignment scope.
-- Does not update answers, sessions, teacher payments, classes or profiles.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

do $$
declare
    v_session_id bigint;
    v_refreshed integer := 0;
begin
    if to_regprocedure('public.classio_refresh_teacher_review_progress(bigint)') is null then
        raise exception 'Atomic progress refresh migration is required';
    end if;
    for v_session_id in
        select distinct r.practice_session_id
        from public.teacher_review_requests r
        join public.practice_sessions s
          on s.id = r.practice_session_id and s.user_id = r.student_id
        where r.status = 'reviewed' and s.status = 'completed'
        order by r.practice_session_id
    loop
        perform public.classio_refresh_teacher_review_progress(v_session_id);
        v_refreshed := v_refreshed + 1;
    end loop;
    raise notice 'Refreshed progress for % reviewed sessions', v_refreshed;
end;
$$;
commit;
