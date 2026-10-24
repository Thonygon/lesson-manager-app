-- A generated unit and its flattened rows must become visible together.
-- Lock the program and merge only the target unit so concurrent edits to other
-- units are not overwritten by the stale generation preview.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '30s';

create function public.classio_program_unit_ready_for_sync(p_unit jsonb)
returns boolean language plpgsql immutable set search_path = '' as $$
declare
    v_topic jsonb;
    v_key text;
    v_value jsonb;
    v_populated boolean;
begin
    if jsonb_typeof(p_unit->'topics') is distinct from 'array'
       or jsonb_array_length(p_unit->'topics') = 0 then return false; end if;
    for v_topic in select value from jsonb_array_elements(p_unit->'topics') loop
        v_populated := false;
        foreach v_key in array array[
            'learning_objectives', 'success_criteria', 'student_can_do',
            'suggested_worksheet_types', 'suggested_exam_exercise_types',
            'homework_idea', 'teacher_notes'
        ] loop
            v_value := v_topic->v_key;
            if jsonb_typeof(v_value) = 'array' then
                v_populated := jsonb_array_length(v_value) > 0;
            elsif jsonb_typeof(v_value) = 'string' then
                v_populated := btrim(v_value #>> '{}') <> '';
            end if;
            if v_populated then exit; end if;
        end loop;
        if not v_populated then return false; end if;
    end loop;
    return true;
end;
$$;
revoke all on function public.classio_program_unit_ready_for_sync(jsonb) from public, anon, authenticated;

create function public.classio_sync_generated_program_unit(
    p_program_id bigint, p_unit_number integer, p_unit jsonb,
    p_unit_row jsonb, p_topic_rows jsonb, p_generation_id uuid
) returns jsonb language plpgsql security definer set search_path = '' as $$
declare
    v_program public.learning_programs%rowtype;
    v_unit public.learning_program_units%rowtype;
    v_document jsonb;
    v_units jsonb;
    v_topic_row jsonb;
    v_topic_count integer;
    v_updated integer;
    v_index integer;
    v_complete boolean := true;
    v_document_unit jsonb;
begin
    if auth.uid() is null or p_unit_number is null or p_unit_number < 1
       or jsonb_typeof(p_unit) is distinct from 'object'
       or jsonb_typeof(p_unit_row) is distinct from 'object'
       or jsonb_typeof(p_topic_rows) is distinct from 'array'
       or jsonb_typeof(p_unit->'topics') is distinct from 'array'
       or nullif(btrim(p_unit->>'title'), '') is null
       or p_unit_row->>'title' is distinct from p_unit->>'title' then
        raise exception 'Invalid generated unit' using errcode = '22023';
    end if;
    select * into v_program from public.learning_programs
      where id = p_program_id and user_id = auth.uid()::text and status <> 'archived'
      for update;
    if not found then
        raise exception 'Program ownership required' using errcode = '42501';
    end if;
    select * into v_unit from public.learning_program_units
      where program_id = p_program_id and unit_number = p_unit_number for update;
    if not found then
        raise exception 'Program unit not found' using errcode = '22023';
    end if;
    v_units := v_program.program_data->'units';
    if jsonb_typeof(v_units) is distinct from 'array'
       or jsonb_array_length(v_units) < p_unit_number
       or (p_unit->>'unit_number')::integer is distinct from p_unit_number
       or (p_unit_row->>'unit_number')::integer is distinct from p_unit_number then
        raise exception 'Generated unit does not match the program' using errcode = '22023';
    end if;
    v_topic_count := jsonb_array_length(p_unit->'topics');
    if v_topic_count = 0 or jsonb_array_length(p_topic_rows) <> v_topic_count
       or (select count(*) from public.learning_program_topics
           where program_id = p_program_id and unit_id = v_unit.id) <> v_topic_count then
        raise exception 'Generated topic list is incomplete' using errcode = '22023';
    end if;
    if p_generation_id is null then
        raise exception 'Generation operation required' using errcode = '22023';
    end if;
    for v_index in 0..v_topic_count - 1 loop
        v_topic_row := p_topic_rows->v_index;
        if jsonb_typeof(v_topic_row) is distinct from 'object'
           or (v_topic_row->>'unit_number')::integer is distinct from p_unit_number
           or (v_topic_row->>'topic_number')::integer is distinct from v_index + 1
           or nullif(btrim(v_topic_row->>'title'), '') is null then
            raise exception 'Invalid generated topic' using errcode = '22023';
        end if;
        update public.learning_program_topics set
          title = v_topic_row->>'title',
          subtopic = coalesce(v_topic_row->>'subtopic', ''),
          lesson_focus = coalesce(v_topic_row->>'lesson_focus', ''),
          lesson_purpose = coalesce(v_topic_row->>'lesson_purpose', 'introduce_concept'),
          learning_objectives = coalesce(v_topic_row->'learning_objectives', '[]'::jsonb),
          success_criteria = coalesce(v_topic_row->'success_criteria', '[]'::jsonb),
          student_can_do = coalesce(v_topic_row->'student_can_do', '[]'::jsonb),
          suggested_worksheet_types = coalesce(v_topic_row->'suggested_worksheet_types', '[]'::jsonb),
          suggested_exam_exercise_types = coalesce(v_topic_row->'suggested_exam_exercise_types', '[]'::jsonb),
          homework_idea = coalesce(v_topic_row->>'homework_idea', ''),
          teacher_notes = coalesce(v_topic_row->>'teacher_notes', ''),
          student_summary = coalesce(v_topic_row->>'student_summary', ''),
          estimated_lessons = (v_topic_row->>'estimated_lessons')::integer,
          updated_at = now()
        where program_id = p_program_id and unit_id = v_unit.id
          and topic_number = v_index + 1;
        get diagnostics v_updated = row_count;
        if v_updated <> 1 then
            raise exception 'Saved topic is missing' using errcode = '22023';
        end if;
    end loop;
    update public.learning_program_units set
      title = p_unit_row->>'title',
      overview = coalesce(p_unit_row->>'overview', ''),
      unit_objectives = coalesce(p_unit_row->'unit_objectives', '[]'::jsonb),
      recommended_lesson_purposes = coalesce(p_unit_row->'recommended_lesson_purposes', '[]'::jsonb),
      recommended_worksheet_types = coalesce(p_unit_row->'recommended_worksheet_types', '[]'::jsonb),
      recommended_exam_exercise_types = coalesce(p_unit_row->'recommended_exam_exercise_types', '[]'::jsonb),
      estimated_lessons = (p_unit_row->>'estimated_lessons')::integer,
      generation_operation_id = p_generation_id,
      updated_at = now()
    where id = v_unit.id;
    -- The existing generation-link trigger validates the operation and keeps
    -- every regeneration in the economic event history. Its failure rolls back
    -- all topic and program changes above.
    v_document := jsonb_set(v_program.program_data,
      array['units', (p_unit_number - 1)::text], p_unit, false);
    for v_document_unit in select value from jsonb_array_elements(v_document->'units') loop
        if not public.classio_program_unit_ready_for_sync(v_document_unit) then
            v_complete := false;
            exit;
        end if;
    end loop;
    update public.learning_programs set
      program_data = v_document,
      status = case when v_complete then 'active' else 'draft' end,
      is_public = case when v_complete then is_public else false end,
      visibility = case when v_complete then visibility else 'private' end,
      updated_at = now()
    where id = p_program_id;
    return v_document;
end;
$$;
revoke all on function public.classio_sync_generated_program_unit(bigint, integer, jsonb, jsonb, jsonb, uuid) from public, anon;
grant execute on function public.classio_sync_generated_program_unit(bigint, integer, jsonb, jsonb, jsonb, uuid) to authenticated;
commit;
