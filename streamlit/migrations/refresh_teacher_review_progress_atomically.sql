-- Recompute the affected practice-progress buckets inside the same transaction
-- as a teacher review. Keep the historical migrations and their checksums intact.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

create or replace function public.classio_refresh_teacher_review_progress(p_session_id bigint)
returns void language plpgsql security definer set search_path = '' as $$
declare
    v_session public.practice_sessions%rowtype;
    v_assignment_id bigint;
    v_teacher_id uuid;
    v_program_assignment_id bigint;
    v_scope text;
    v_type text;
    v_attempted integer;
    v_correct integer;
    v_xp integer;
    v_best_streak integer;
    v_last_practiced timestamptz;
    v_created_at timestamptz;
begin
    select * into v_session from public.practice_sessions
      where id = p_session_id and status = 'completed' for update;
    if not found then
        raise exception 'Completed practice session required' using errcode = '22023';
    end if;

    select assignment_id, teacher_id into v_assignment_id, v_teacher_id
      from public.teacher_assignment_attempts
      where practice_session_id = p_session_id and student_id = v_session.user_id
      order by id desc limit 1;
    if v_assignment_id is not null then
        select learning_program_assignment_id into v_program_assignment_id
          from public.teacher_assignments
          where id = v_assignment_id and student_id = v_session.user_id;
    end if;
    v_scope := case when v_assignment_id is null then 'independent'
                    else 'assignment:' || v_assignment_id::text end;

    for v_type in select distinct exercise_type from public.practice_answers
      where session_id = p_session_id and user_id = v_session.user_id loop
        with scoped as (
            select s.id, s.xp_earned, s.best_streak, s.completed_at, s.created_at,
                   a.exercise_type, a.is_correct
              from public.practice_sessions s
              join public.practice_answers a
                on a.session_id = s.id and a.user_id = s.user_id
              left join lateral (
                  select assignment_id from public.teacher_assignment_attempts t
                   where t.practice_session_id = s.id and t.student_id = s.user_id
                   order by t.id desc limit 1
              ) attempt on true
             where s.user_id = v_session.user_id and s.status = 'completed'
               and s.source_type = v_session.source_type
               and s.subject = v_session.subject and s.topic = v_session.topic
               and s.level = v_session.level
               and attempt.assignment_id is not distinct from v_assignment_id
        ), type_stats as (
            select id, exercise_type, max(xp_earned) as session_xp,
                   max(best_streak) as session_best_streak,
                   max(completed_at) as completed_at, max(created_at) as created_at,
                   count(*)::integer as attempted,
                   count(*) filter (where is_correct)::integer as correct
              from scoped group by id, exercise_type
        ), session_stats as (
            select id, sum(correct)::integer as total_correct,
                   count(*)::integer as type_count
              from type_stats group by id
        )
        select coalesce(sum(t.attempted), 0)::integer,
               coalesce(sum(t.correct), 0)::integer,
               coalesce(sum(case
                   when t.session_xp <> 0 and ss.total_correct > 0
                     then round(t.session_xp::numeric * t.correct / ss.total_correct)
                   when t.session_xp <> 0 and ss.type_count > 0
                     then round(t.session_xp::numeric / ss.type_count)
                   else 0 end), 0)::integer,
               coalesce(max(t.session_best_streak), 0)::integer,
               max(coalesce(t.completed_at, t.created_at)), min(t.created_at)
          into v_attempted, v_correct, v_xp, v_best_streak,
               v_last_practiced, v_created_at
          from type_stats t join session_stats ss using (id)
         where t.exercise_type = v_type;

        if v_attempted < 1 then
            raise exception 'Practice progress source missing' using errcode = '22023';
        end if;
        insert into public.practice_progress
            (user_id, scope_key, source_type, teacher_id, assignment_id,
             learning_program_assignment_id, subject, topic, exercise_type, level,
             total_attempted, total_correct, accuracy_pct, total_xp, best_streak,
             last_practiced, created_at)
        values (v_session.user_id, v_scope, v_session.source_type, v_teacher_id,
                v_assignment_id, v_program_assignment_id, v_session.subject,
                v_session.topic, v_type, v_session.level, v_attempted, v_correct,
                round(100.0 * v_correct / v_attempted, 1), v_xp, v_best_streak,
                v_last_practiced, coalesce(v_created_at, now()))
        on conflict (user_id, scope_key, source_type, subject, topic, exercise_type, level)
        do update set total_attempted = excluded.total_attempted,
                      total_correct = excluded.total_correct,
                      accuracy_pct = excluded.accuracy_pct,
                      total_xp = excluded.total_xp,
                      best_streak = excluded.best_streak,
                      last_practiced = excluded.last_practiced,
                      teacher_id = excluded.teacher_id,
                      assignment_id = excluded.assignment_id,
                      learning_program_assignment_id = excluded.learning_program_assignment_id;
    end loop;
end;
$$;
revoke all on function public.classio_refresh_teacher_review_progress(bigint)
    from public, anon, authenticated, service_role;

-- Deferred execution sees the final answer values even when an older client
-- performs several writes in one transaction. A refresh failure aborts the review.
create or replace function public.classio_teacher_review_progress_trigger()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    perform public.classio_refresh_teacher_review_progress(new.practice_session_id);
    return new;
end;
$$;
revoke all on function public.classio_teacher_review_progress_trigger()
    from public, anon, authenticated, service_role;

create constraint trigger classio_teacher_review_progress_commit
    after update on public.teacher_review_requests
    deferrable initially deferred
    for each row when (new.status = 'reviewed')
    execute function public.classio_teacher_review_progress_trigger();
commit;
