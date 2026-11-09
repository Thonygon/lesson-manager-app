-- Keep legacy rows intact; new Expo submissions mark unmatched free text as
-- pending so an uncertain heuristic never becomes a final mark.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';
alter table public.practice_answers add column if not exists evaluation_status text not null default 'auto_incorrect';
alter table public.practice_sessions add column if not exists evaluated_count integer not null default 0;
alter table public.practice_sessions add column if not exists pending_count integer not null default 0;
alter table public.practice_sessions add column if not exists evaluation_status text not null default 'final';

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
    v_pending integer;
    v_evaluated integer;
    v_evaluation text;
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
    v_pending := coalesce((p_result->>'pending_count')::integer, 0);
    v_evaluated := coalesce((p_result->>'evaluated_count')::integer, v_answer_count);
    v_evaluation := coalesce(p_result->>'evaluation_status', 'final');
    v_group_count := jsonb_array_length(coalesce(p_result->'progress', '[]'::jsonb));
    if v_answer_count > 500 or v_group_count > 50 or v_answer_count < 1
       or (v_group_count < 1 and v_pending = 0)
       or v_pending < 0 or v_evaluated < 0 or v_pending + v_evaluated <> v_answer_count
       or v_evaluation not in ('final', 'pending_teacher', 'unassessed')
       or (v_evaluation = 'final' and v_pending <> 0)
       or (v_evaluation = 'pending_teacher' and nullif(p_result->>'assignment_id','') is null)
       or (v_evaluation <> 'final' and v_pending = 0) or p_result->>'total' is null or p_result->>'correct' is null
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
    if v_pending <> (
        select count(*) from jsonb_array_elements(p_result->'answers') as answer(value)
        where answer.value->>'evaluation_status' in ('pending_review','unassessed')
    ) or exists (
        select 1 from jsonb_array_elements(p_result->'answers') as answer(value)
        where coalesce(answer.value->>'evaluation_status','auto_incorrect')
          not in ('auto_correct','auto_incorrect','pending_review','unassessed')
          or (answer.value->>'evaluation_status' in ('pending_review','unassessed')
              and coalesce((answer.value->>'is_correct')::boolean,false))
    ) then
        raise exception 'Invalid response evaluation states' using errcode = '22023';
    end if;
    update public.practice_sessions set
        exercise_data = coalesce(p_result->'exercise_data', v_session.exercise_data),
        total_questions = (p_result->>'total')::integer,
        correct_count = (p_result->>'correct')::integer,
        score_pct = (p_result->>'score')::numeric,
        xp_earned = (p_result->>'xp')::integer,
        best_streak = (p_result->>'best_streak')::integer,
        evaluated_count = v_evaluated, pending_count = v_pending,
        evaluation_status = v_evaluation, status = 'completed', completed_at = v_now
    where id = v_session.id;
    delete from public.practice_answers where session_id = v_session.id and user_id = v_uid;
    for v_answer in select value from jsonb_array_elements(p_result->'answers') loop
        insert into public.practice_answers
            (session_id,user_id,exercise_idx,question_idx,exercise_type,student_answer,correct_answer,is_correct,evaluation_status,answered_at)
        values (
            v_session.id,v_uid,(v_answer->>'exercise_index')::integer,
            (v_answer->>'question_index')::integer,v_answer->>'exercise_type',
            coalesce(v_answer->>'student_answer',''),coalesce(v_answer->>'correct_answer',''),
            coalesce((v_answer->>'is_correct')::boolean,false),
            coalesce(v_answer->>'evaluation_status', 'auto_incorrect'),v_now
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
        values (v_assignment.id,v_assignment.teacher_id,v_uid,v_session.id,v_attempt_no,
            case when v_pending > 0 then 'submitted' else 'graded' end,
            case when v_pending > 0 then null else (p_result->>'score')::numeric end,
            (p_result->>'total')::integer,(p_result->>'correct')::integer,
            jsonb_build_object('result',p_result->'graded','source_type',v_session.source_type,
                'source_id',p_result->>'material_source_id','title',v_session.title),
            v_now,v_now,case when v_pending > 0 then null else v_now end,
            case when v_pending > 0 then null else v_now end,v_now,v_now);
        update public.teacher_assignments set
            status=case when v_pending > 0 then 'submitted' else 'graded' end,
            score_pct=case when v_pending > 0 then null else (p_result->>'score')::numeric end,
            total_questions=(p_result->>'total')::integer,correct_count=(p_result->>'correct')::integer,
            opened_at=v_now,submitted_at=v_now,
            graded_at=case when v_pending > 0 then null else v_now end,
            completed_at=case when v_pending > 0 then null else v_now end,updated_at=v_now
        where id=v_assignment.id;
        if v_pending > 0 then
            insert into public.teacher_review_requests
              (teacher_id,student_id,subject_key,subject_label,practice_session_id,assignment_id,
               source_type,source_id,title,status,request_note,requested_at,updated_at)
            values (v_assignment.teacher_id,v_uid,v_assignment.subject_key,v_assignment.subject_label,
              v_session.id,v_assignment.id,v_session.source_type,p_result->>'material_source_id',
              v_session.title,'requested','',v_now,v_now)
            on conflict (teacher_id,practice_session_id) do nothing;
        end if;
    end if;
    return v_session.id;
end;
$$;

revoke all on function public.classio_complete_student_practice(bigint,jsonb) from public, anon;
grant execute on function public.classio_complete_student_practice(bigint,jsonb) to authenticated;

create or replace function public.classio_submit_teacher_review(
  p_review_id bigint,
  p_overrides jsonb default '{}'::jsonb,
  p_teacher_feedback text default ''
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_teacher_id uuid := auth.uid();
  v_review public.teacher_review_requests%rowtype;
  v_session public.practice_sessions%rowtype;
  v_total integer := 0;
  v_correct integer := 0;
  v_score numeric(5,1) := 0;
  v_now timestamptz := now();
  v_feedback text := left(trim(coalesce(p_teacher_feedback, '')), 5000);
begin
  if v_teacher_id is null then
    raise exception 'Authentication required';
  end if;

  if jsonb_typeof(coalesce(p_overrides, '{}'::jsonb)) <> 'object' then
    raise exception 'Answer overrides must be a JSON object';
  end if;

  select * into v_review
  from public.teacher_review_requests
  where id = p_review_id and teacher_id = v_teacher_id
  for update;

  if not found then
    raise exception 'Review request not found';
  end if;

  select * into v_session
  from public.practice_sessions
  where id = v_review.practice_session_id and user_id = v_review.student_id
  for update;

  if not found then
    raise exception 'Practice session not found';
  end if;

  if exists (select 1 from public.practice_answers a
      where a.session_id = v_session.id and a.user_id = v_review.student_id
        and a.evaluation_status in ('pending_review','unassessed')
        and coalesce(p_overrides ->> a.id::text, '') not in ('correct','incorrect')) then
    raise exception 'Decide every unassessed response before publishing the score' using errcode = '22023';
  end if;

  update public.practice_answers answer
  set evaluation_status = case
        when p_overrides ->> answer.id::text in ('correct','incorrect') then 'teacher_reviewed'
        else answer.evaluation_status end,
      is_correct = case coalesce(p_overrides ->> answer.id::text, 'keep')
    when 'correct' then true
    when 'incorrect' then false
    else answer.is_correct
  end
  where answer.session_id = v_session.id and answer.user_id = v_review.student_id;

  select count(*)::integer, count(*) filter (where is_correct)::integer
  into v_total, v_correct
  from public.practice_answers
  where session_id = v_session.id and user_id = v_review.student_id;

  v_score := case when v_total > 0 then round((v_correct::numeric / v_total::numeric) * 100, 1) else 0 end;

  update public.practice_sessions
  set correct_count = v_correct,
      total_questions = v_total,
      score_pct = v_score,
      evaluated_count = v_total, pending_count = 0, evaluation_status = 'final',
      completed_at = coalesce(completed_at, v_now)
  where id = v_session.id and user_id = v_review.student_id;

  update public.teacher_review_requests
  set status = 'reviewed',
      teacher_feedback = v_feedback,
      override_score_pct = v_score,
      review_payload = jsonb_build_object('answer_overrides', coalesce(p_overrides, '{}'::jsonb)),
      reviewed_at = v_now,
      updated_at = v_now
  where id = v_review.id and teacher_id = v_teacher_id;

  if v_review.assignment_id is not null then
    update public.teacher_assignments
    set status = 'graded',
        score_pct = v_score,
        correct_count = v_correct,
        total_questions = v_total,
        teacher_note = case when v_feedback <> '' then v_feedback else teacher_note end,
        graded_at = v_now,
        updated_at = v_now
    where id = v_review.assignment_id and teacher_id = v_teacher_id;

    update public.teacher_assignment_attempts
    set status = 'graded',
        score_pct = v_score,
        correct_count = v_correct,
        total_questions = v_total,
        teacher_feedback = v_feedback,
        graded_at = v_now, completed_at = v_now,
        updated_at = v_now
    where assignment_id = v_review.assignment_id
      and practice_session_id = v_session.id
      and student_id = v_review.student_id
      and teacher_id = v_teacher_id;
  end if;

  return jsonb_build_object(
    'review_id', v_review.id,
    'assignment_id', v_review.assignment_id,
    'correct_count', v_correct,
    'total_questions', v_total,
    'score_pct', v_score,
    'reviewed_at', v_now
  );
end;
$$;


create or replace function public.classio_submit_teacher_review_oidc(
  p_review_id bigint,
  p_overrides jsonb default '{}'::jsonb,
  p_teacher_feedback text default '',
  p_teacher_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_teacher_id uuid := p_teacher_id;
  v_review public.teacher_review_requests%rowtype;
  v_session public.practice_sessions%rowtype;
  v_total integer := 0;
  v_correct integer := 0;
  v_score numeric(5,1) := 0;
  v_now timestamptz := now();
  v_feedback text := left(trim(coalesce(p_teacher_feedback, '')), 5000);
begin
  if auth.role() <> 'service_role' or v_teacher_id is null then
    raise exception 'Authentication required';
  end if;

  if jsonb_typeof(coalesce(p_overrides, '{}'::jsonb)) <> 'object' then
    raise exception 'Answer overrides must be a JSON object';
  end if;

  select * into v_review
  from public.teacher_review_requests
  where id = p_review_id and teacher_id = v_teacher_id
  for update;

  if not found then
    raise exception 'Review request not found';
  end if;

  select * into v_session
  from public.practice_sessions
  where id = v_review.practice_session_id and user_id = v_review.student_id
  for update;

  if not found then
    raise exception 'Practice session not found';
  end if;

  if exists (select 1 from public.practice_answers a
      where a.session_id = v_session.id and a.user_id = v_review.student_id
        and a.evaluation_status in ('pending_review','unassessed')
        and coalesce(p_overrides ->> a.id::text, '') not in ('correct','incorrect')) then
    raise exception 'Decide every unassessed response before publishing the score' using errcode = '22023';
  end if;

  update public.practice_answers answer
  set evaluation_status = case
        when p_overrides ->> answer.id::text in ('correct','incorrect') then 'teacher_reviewed'
        else answer.evaluation_status end,
      is_correct = case coalesce(p_overrides ->> answer.id::text, 'keep')
    when 'correct' then true
    when 'incorrect' then false
    else answer.is_correct
  end
  where answer.session_id = v_session.id and answer.user_id = v_review.student_id;

  select count(*)::integer, count(*) filter (where is_correct)::integer
  into v_total, v_correct
  from public.practice_answers
  where session_id = v_session.id and user_id = v_review.student_id;

  v_score := case when v_total > 0 then round((v_correct::numeric / v_total::numeric) * 100, 1) else 0 end;

  update public.practice_sessions
  set correct_count = v_correct,
      total_questions = v_total,
      score_pct = v_score,
      evaluated_count = v_total, pending_count = 0, evaluation_status = 'final',
      completed_at = coalesce(completed_at, v_now)
  where id = v_session.id and user_id = v_review.student_id;

  update public.teacher_review_requests
  set status = 'reviewed',
      teacher_feedback = v_feedback,
      override_score_pct = v_score,
      review_payload = jsonb_build_object('answer_overrides', coalesce(p_overrides, '{}'::jsonb)),
      reviewed_at = v_now,
      updated_at = v_now
  where id = v_review.id and teacher_id = v_teacher_id;

  if v_review.assignment_id is not null then
    update public.teacher_assignments
    set status = 'graded',
        score_pct = v_score,
        correct_count = v_correct,
        total_questions = v_total,
        teacher_note = case when v_feedback <> '' then v_feedback else teacher_note end,
        graded_at = v_now,
        updated_at = v_now
    where id = v_review.assignment_id and teacher_id = v_teacher_id;

    update public.teacher_assignment_attempts
    set status = 'graded',
        score_pct = v_score,
        correct_count = v_correct,
        total_questions = v_total,
        teacher_feedback = v_feedback,
        graded_at = v_now, completed_at = v_now,
        updated_at = v_now
    where assignment_id = v_review.assignment_id
      and practice_session_id = v_session.id
      and student_id = v_review.student_id
      and teacher_id = v_teacher_id;
  end if;

  return jsonb_build_object(
    'review_id', v_review.id,
    'assignment_id', v_review.assignment_id,
    'correct_count', v_correct,
    'total_questions', v_total,
    'score_pct', v_score,
    'reviewed_at', v_now
  );
end;
$$;


revoke all on function public.classio_submit_teacher_review(bigint, jsonb, text) from public;
grant execute on function public.classio_submit_teacher_review(bigint, jsonb, text) to authenticated;
revoke all on function public.classio_submit_teacher_review_oidc(bigint, jsonb, text, uuid) from public, anon, authenticated;
grant execute on function public.classio_submit_teacher_review_oidc(bigint, jsonb, text, uuid) to service_role;
create or replace function public.classio_teacher_review_detail(p_review_id bigint)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_teacher_id uuid := auth.uid();
  v_review public.teacher_review_requests%rowtype;
  v_session public.practice_sessions%rowtype;
  v_answers jsonb;
begin
  if v_teacher_id is null then
    raise exception 'Authentication required';
  end if;

  select * into v_review
  from public.teacher_review_requests
  where id = p_review_id and teacher_id = v_teacher_id;

  if not found then
    raise exception 'Review request not found';
  end if;

  select * into v_session
  from public.practice_sessions
  where id = v_review.practice_session_id and user_id = v_review.student_id;

  if not found then
    raise exception 'Practice session not found';
  end if;

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', answer.id,
        'exercise_idx', answer.exercise_idx,
        'question_idx', answer.question_idx,
        'exercise_type', answer.exercise_type,
        'student_answer', answer.student_answer,
        'correct_answer', answer.correct_answer,
        'is_correct', answer.is_correct,
        'evaluation_status', answer.evaluation_status,
        'answered_at', answer.answered_at
      ) order by answer.exercise_idx, answer.question_idx, answer.id
    ),
    '[]'::jsonb
  ) into v_answers
  from public.practice_answers answer
  where answer.session_id = v_session.id and answer.user_id = v_review.student_id;

  return jsonb_build_object(
    'review', to_jsonb(v_review),
    'session', jsonb_set(to_jsonb(v_session) - 'exercise_data', '{exercise_data}', coalesce(v_session.exercise_data, '{}'::jsonb) - 'draft_answers'),
    'answers', v_answers
  );
end;
$$;


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

    -- Preserve the serialized bucket refresh used by the current production RPC.
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        pg_catalog.jsonb_build_array(v_session.user_id, v_scope,
            v_session.source_type, v_session.subject, v_session.topic,
            v_session.level)::text, 0));

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
               and a.evaluation_status not in ('pending_review','unassessed')
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

revoke all on function public.classio_refresh_teacher_review_progress(bigint) from public, anon, authenticated, service_role;
revoke all on function public.classio_teacher_review_detail(bigint) from public;
grant execute on function public.classio_teacher_review_detail(bigint) to authenticated;
commit;
