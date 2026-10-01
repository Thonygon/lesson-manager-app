-- Allow an authenticated teacher to request a revision for one of their own
-- learners' completed worksheet/exam attempts. The existing table policy only
-- permits student-originated inserts, so this narrowly scoped function validates
-- the assignment and attempt relationship before creating the request.

create or replace function public.classio_request_teacher_revision(
  p_assignment_id bigint,
  p_practice_session_id bigint
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_teacher_id uuid := auth.uid();
  v_assignment public.teacher_assignments%rowtype;
  v_existing public.teacher_review_requests%rowtype;
  v_review public.teacher_review_requests%rowtype;
  v_now timestamptz := now();
begin
  if v_teacher_id is null then
    raise exception 'Authentication required';
  end if;

  select * into v_assignment
  from public.teacher_assignments
  where id = p_assignment_id
    and teacher_id = v_teacher_id
    and assignment_type in ('worksheet', 'exam');

  if not found then
    raise exception 'Eligible assignment not found';
  end if;

  if not exists (
    select 1
    from public.teacher_assignment_attempts attempt
    where attempt.assignment_id = v_assignment.id
      and attempt.practice_session_id = p_practice_session_id
      and attempt.student_id = v_assignment.student_id
      and attempt.teacher_id = v_teacher_id
  ) then
    raise exception 'Practice attempt not found';
  end if;

  select * into v_existing
  from public.teacher_review_requests
  where teacher_id = v_teacher_id
    and practice_session_id = p_practice_session_id
  limit 1;

  if found then
    return jsonb_build_object(
      'id', v_existing.id,
      'status', v_existing.status,
      'existing', true
    );
  end if;

  insert into public.teacher_review_requests (
    teacher_id,
    student_id,
    subject_key,
    subject_label,
    practice_session_id,
    assignment_id,
    source_type,
    source_id,
    title,
    status,
    request_note,
    teacher_feedback,
    review_payload,
    requested_at,
    created_at,
    updated_at
  ) values (
    v_teacher_id,
    v_assignment.student_id,
    coalesce(v_assignment.subject_key, ''),
    coalesce(v_assignment.subject_label, ''),
    p_practice_session_id,
    v_assignment.id,
    coalesce(v_assignment.source_type, ''),
    v_assignment.source_record_id::text,
    coalesce(v_assignment.title, ''),
    'requested',
    '',
    '',
    jsonb_build_object('initiated_by', 'teacher'),
    v_now,
    v_now,
    v_now
  )
  returning * into v_review;

  return jsonb_build_object(
    'id', v_review.id,
    'status', v_review.status,
    'existing', false
  );
end;
$$;

revoke all on function public.classio_request_teacher_revision(bigint, bigint) from public;
grant execute on function public.classio_request_teacher_revision(bigint, bigint) to authenticated;
