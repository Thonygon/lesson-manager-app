-- The teacher grades the exact attempt snapshot, including archived assignments.
-- The RPC already verifies teacher ownership of the review and student/session match.
-- Authenticated teacher review APIs shared by the Streamlit and Expo clients.
-- Detail reads and grading writes are scoped to auth.uid(); the write path is
-- one transaction so a partial score cannot leak across related tables.

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

