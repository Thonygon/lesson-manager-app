-- A corrected answer key updates the student's answers, score, aggregates and
-- assignment attempt together. Student responses and answer IDs are retained.
-- Only the trusted server may call this after checking resource ownership.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '30s';

create function public.classio_apply_practice_regrade(
    p_session_id bigint, p_payload jsonb
) returns boolean language plpgsql security definer set search_path = '' as $$
declare
    v_session public.practice_sessions%rowtype;
    v_answer jsonb;
    v_change jsonb;
    v_answer_id bigint;
    v_seen bigint[] := '{}'::bigint[];
    v_reviewed boolean;
    v_assignment_id bigint;
    v_scope text;
    v_progress public.practice_progress%rowtype;
    v_attempt public.teacher_assignment_attempts%rowtype;
    v_total integer;
    v_correct integer;
    v_score numeric;
    v_xp integer;
    v_streak integer;
    v_exercise_data jsonb;
    v_type text;
    v_attempted_delta integer;
    v_correct_delta integer;
    v_xp_delta integer;
    v_new_attempted integer;
    v_new_correct integer;
begin
    if auth.role() <> 'service_role' or jsonb_typeof(p_payload) is distinct from 'object'
       or jsonb_typeof(p_payload->'answers') is distinct from 'array'
       or jsonb_typeof(p_payload->'progressChanges') is distinct from 'array'
       or jsonb_typeof(p_payload->'exerciseData') is distinct from 'object' then
        raise exception 'Trusted regrade payload required' using errcode = '42501';
    end if;
    select * into v_session from public.practice_sessions
      where id = p_session_id and status = 'completed' for update;
    if not found then
        raise exception 'Completed practice session not found' using errcode = '22023';
    end if;
    if v_session.source_type not in ('worksheet', 'exam') then
        raise exception 'Unsupported practice type' using errcode = '22023';
    end if;
    if jsonb_array_length(p_payload->'answers') <>
       (select count(*) from public.practice_answers where session_id = p_session_id) then
        raise exception 'Question structure changed; manual review required' using errcode = '22023';
    end if;
    select exists (
      select 1 from public.teacher_review_requests
      where practice_session_id = p_session_id and status = 'reviewed'
    ) into v_reviewed;
    v_exercise_data := p_payload->'exerciseData';
    for v_answer in select value from jsonb_array_elements(p_payload->'answers') loop
        if coalesce(v_answer->>'id', '') !~ '^[0-9]+$'
           or jsonb_typeof(v_answer->'isCorrect') is distinct from 'boolean' then
            raise exception 'Invalid graded answer' using errcode = '22023';
        end if;
        v_answer_id := (v_answer->>'id')::bigint;
        if v_answer_id = any(v_seen) then
            raise exception 'Duplicate graded answer' using errcode = '22023';
        end if;
        v_seen := array_append(v_seen, v_answer_id);
        update public.practice_answers set
          exercise_type = coalesce(v_answer->>'exerciseType', ''),
          correct_answer = coalesce(v_answer->>'correctAnswer', ''),
          is_correct = case when v_reviewed then is_correct else (v_answer->>'isCorrect')::boolean end
        where id = v_answer_id and session_id = p_session_id and user_id = v_session.user_id;
        if not found then
            raise exception 'Graded answer does not belong to session' using errcode = '22023';
        end if;
    end loop;
    if v_reviewed then
        update public.practice_sessions set exercise_data = v_exercise_data
        where id = p_session_id;
        return false;
    end if;
    v_total := (p_payload->>'total')::integer;
    v_correct := (p_payload->>'correct')::integer;
    v_score := (p_payload->>'score')::numeric;
    v_xp := (p_payload->>'xp')::integer;
    v_streak := (p_payload->>'bestStreak')::integer;
    if v_total is null or v_total < 1 or v_correct is null or v_correct < 0 or v_correct > v_total
       or v_score is null or v_score < 0 or v_score > 100
       or v_xp is null or v_xp < 0 or v_streak is null or v_streak < 0 then
        raise exception 'Invalid regraded score' using errcode = '22023';
    end if;
    select assignment_id into v_assignment_id
      from public.teacher_assignment_attempts
      where practice_session_id = p_session_id and student_id = v_session.user_id
      order by id desc limit 1;
    v_scope := case when v_assignment_id is null then 'independent'
                    else 'assignment:' || v_assignment_id::text end;
    for v_change in select value from jsonb_array_elements(p_payload->'progressChanges') loop
        v_type := coalesce(v_change->>'exerciseType', '');
        v_attempted_delta := (v_change->>'attempted')::integer;
        v_correct_delta := (v_change->>'correct')::integer;
        v_xp_delta := (v_change->>'xp')::integer;
        if v_type = '' or v_attempted_delta is null or v_correct_delta is null or v_xp_delta is null then
            raise exception 'Invalid progress change' using errcode = '22023';
        end if;
        select * into v_progress from public.practice_progress
          where user_id = v_session.user_id and scope_key = v_scope
            and source_type = v_session.source_type and subject = v_session.subject
            and topic = v_session.topic and exercise_type = v_type and level = v_session.level
          for update;
        if found then
            v_new_attempted := greatest(0, v_progress.total_attempted + v_attempted_delta);
            v_new_correct := greatest(0, least(v_new_attempted, v_progress.total_correct + v_correct_delta));
            update public.practice_progress set
              total_attempted = v_new_attempted,
              total_correct = v_new_correct,
              accuracy_pct = case when v_new_attempted = 0 then 0
                                  else round(100.0 * v_new_correct / v_new_attempted, 1) end,
              total_xp = greatest(0, v_progress.total_xp + v_xp_delta)
            where id = v_progress.id;
        elsif v_attempted_delta > 0 then
            insert into public.practice_progress
              (user_id, scope_key, source_type, teacher_id, assignment_id,
               subject, topic, exercise_type, level, total_attempted, total_correct,
               accuracy_pct, total_xp, best_streak, last_practiced)
            select v_session.user_id, v_scope, v_session.source_type, a.teacher_id,
              v_assignment_id, v_session.subject, v_session.topic, v_type, v_session.level,
              v_attempted_delta, greatest(0, least(v_attempted_delta, v_correct_delta)),
              round(100.0 * greatest(0, least(v_attempted_delta, v_correct_delta)) / v_attempted_delta, 1),
              greatest(0, v_xp_delta), v_streak, coalesce(v_session.completed_at, now())
            from (select 1) seed
            left join public.teacher_assignments a on a.id = v_assignment_id;
        end if;
    end loop;
    update public.practice_sessions set
      exercise_data = v_exercise_data, total_questions = v_total,
      correct_count = v_correct, score_pct = v_score, xp_earned = v_xp,
      best_streak = v_streak
    where id = p_session_id;
    for v_attempt in select * from public.teacher_assignment_attempts
      where practice_session_id = p_session_id and student_id = v_session.user_id
      for update loop
        update public.teacher_assignment_attempts set
          score_pct = v_score, total_questions = v_total, correct_count = v_correct,
          submission_payload = jsonb_set(
            coalesce(v_attempt.submission_payload::jsonb, '{}'::jsonb), '{result}',
            coalesce(v_attempt.submission_payload::jsonb->'result', '{}'::jsonb)
              || jsonb_build_object('total', v_total, 'correct', v_correct,
                 'score', v_score, 'xp', v_xp, 'bestStreak', v_streak), true)
        where id = v_attempt.id;
        if v_attempt.id = (
          select id from public.teacher_assignment_attempts
          where assignment_id = v_attempt.assignment_id
          order by created_at desc, id desc limit 1
        ) then
            update public.teacher_assignments set
              score_pct = v_score, total_questions = v_total, correct_count = v_correct
            where id = v_attempt.assignment_id and student_id = v_session.user_id;
        end if;
    end loop;
    return true;
end;
$$;
revoke all on function public.classio_apply_practice_regrade(bigint, jsonb) from public, anon, authenticated;
grant execute on function public.classio_apply_practice_regrade(bigint, jsonb) to service_role;
commit;
