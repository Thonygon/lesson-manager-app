-- Follow-up to practice_pending_review.sql, which is already applied.
-- Preserve weighted word-search units and the assignment completion date.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

create or replace function public.classio_review_word_search_units(
  p_expected text, p_student text, p_fallback_correct boolean
) returns integer[] language plpgsql immutable set search_path = '' as $$
declare
  v_expected jsonb;
  v_student jsonb;
  v_total integer;
  v_correct integer;
begin
  v_expected := p_expected::jsonb;
  v_student := p_student::jsonb;
  if jsonb_typeof(v_expected) <> 'array' or jsonb_typeof(v_student) <> 'array' then
    return array[1, case when p_fallback_correct then 1 else 0 end];
  end if;
  select count(*)::integer,
         count(*) filter (where exists (
           select 1 from jsonb_array_elements_text(v_student) found(word)
           where pg_catalog.upper(pg_catalog.regexp_replace(found.word, '[[:space:]]+', '', 'g')) = expected.word
         ))::integer
    into v_total, v_correct
  from (select distinct pg_catalog.upper(pg_catalog.regexp_replace(word, '[[:space:]]+', '', 'g')) as word
        from jsonb_array_elements_text(v_expected) items(word)) expected;
  if v_total < 1 then
    return array[1, case when p_fallback_correct then 1 else 0 end];
  end if;
  return array[v_total, v_correct];
exception when others then
  return array[1, case when p_fallback_correct then 1 else 0 end];
end;
$$;
revoke all on function public.classio_review_word_search_units(text,text,boolean)
  from public, anon, authenticated;

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
  v_answer public.practice_answers%rowtype;
  v_decision text;
  v_units integer[];
  v_base integer;
  v_target integer;
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

  -- Session totals include each word in a word search, while the answer
  -- table has only one row for that entire search. Apply review decisions as
  -- deltas to the persisted weighted score rather than recounting rows.
  v_total := v_session.total_questions;
  v_correct := v_session.correct_count;
  for v_answer in select * from public.practice_answers
      where session_id = v_session.id and user_id = v_review.student_id loop
    v_decision := coalesce(p_overrides ->> v_answer.id::text, 'keep');
    if v_decision not in ('correct', 'incorrect') then continue; end if;
    if v_answer.exercise_type = 'word_search_vocab' then
      v_units := public.classio_review_word_search_units(
        v_answer.correct_answer, v_answer.student_answer, v_answer.is_correct);
      v_base := case when v_answer.evaluation_status = 'teacher_reviewed'
        then case when v_answer.is_correct then v_units[1] else 0 end
        else v_units[2] end;
      v_target := case when v_decision = 'correct' then v_units[1] else 0 end;
    else
      v_base := case when v_answer.is_correct then 1 else 0 end;
      v_target := case when v_decision = 'correct' then 1 else 0 end;
    end if;
    v_correct := v_correct + v_target - v_base;
  end loop;
  if v_total < 1 or v_correct < 0 or v_correct > v_total then
    raise exception 'Invalid weighted review result' using errcode = '22023';
  end if;
  v_score := round((v_correct::numeric / v_total::numeric) * 100, 1);

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
        graded_at = v_now, completed_at = coalesce(completed_at, v_now),
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
  v_answer public.practice_answers%rowtype;
  v_decision text;
  v_units integer[];
  v_base integer;
  v_target integer;
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

  -- Session totals include each word in a word search, while the answer
  -- table has only one row for that entire search. Apply review decisions as
  -- deltas to the persisted weighted score rather than recounting rows.
  v_total := v_session.total_questions;
  v_correct := v_session.correct_count;
  for v_answer in select * from public.practice_answers
      where session_id = v_session.id and user_id = v_review.student_id loop
    v_decision := coalesce(p_overrides ->> v_answer.id::text, 'keep');
    if v_decision not in ('correct', 'incorrect') then continue; end if;
    if v_answer.exercise_type = 'word_search_vocab' then
      v_units := public.classio_review_word_search_units(
        v_answer.correct_answer, v_answer.student_answer, v_answer.is_correct);
      v_base := case when v_answer.evaluation_status = 'teacher_reviewed'
        then case when v_answer.is_correct then v_units[1] else 0 end
        else v_units[2] end;
      v_target := case when v_decision = 'correct' then v_units[1] else 0 end;
    else
      v_base := case when v_answer.is_correct then 1 else 0 end;
      v_target := case when v_decision = 'correct' then 1 else 0 end;
    end if;
    v_correct := v_correct + v_target - v_base;
  end loop;
  if v_total < 1 or v_correct < 0 or v_correct > v_total then
    raise exception 'Invalid weighted review result' using errcode = '22023';
  end if;
  v_score := round((v_correct::numeric / v_total::numeric) * 100, 1);

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
        graded_at = v_now, completed_at = coalesce(completed_at, v_now),
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


revoke all on function public.classio_submit_teacher_review(bigint,jsonb,text) from public;
grant execute on function public.classio_submit_teacher_review(bigint,jsonb,text) to authenticated;
revoke all on function public.classio_submit_teacher_review_oidc(bigint,jsonb,text,uuid)
  from public, anon, authenticated;
grant execute on function public.classio_submit_teacher_review_oidc(bigint,jsonb,text,uuid) to service_role;
commit;
