-- Streamlit OIDC uses a server-only Supabase client, so auth.uid() is null.
-- Keep the authenticated Expo RPC unchanged; this service-only entry point
-- applies the same atomic review with the OIDC teacher ID verified by Streamlit.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

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

  update public.practice_answers answer
  set is_correct = case coalesce(p_overrides ->> answer.id::text, 'keep')
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
        graded_at = v_now,
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

revoke all on function public.classio_submit_teacher_review_oidc(bigint, jsonb, text, uuid)
    from public, anon, authenticated;
grant execute on function public.classio_submit_teacher_review_oidc(bigint, jsonb, text, uuid)
    to service_role;
commit;
