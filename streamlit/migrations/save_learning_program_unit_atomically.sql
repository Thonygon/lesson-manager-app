-- Keep a manually edited unit, its topic rows, and the program document in
-- one transaction. The caller supplies the complete ordered topic list.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '30s';

create function public.classio_save_learning_program_unit(
    p_program_id bigint, p_unit_id bigint, p_changes jsonb
) returns void language plpgsql security definer set search_path = '' as $$
declare
    v_program public.learning_programs%rowtype;
    v_unit public.learning_program_units%rowtype;
    v_document jsonb;
    v_units jsonb;
    v_unit_document jsonb;
    v_topics jsonb;
    v_change jsonb;
    v_topic_id bigint;
    v_topic_number integer;
    v_seen bigint[] := '{}'::bigint[];
begin
    if auth.uid() is null or jsonb_typeof(p_changes) is distinct from 'object'
       or nullif(trim(p_changes->>'title'), '') is null
       or jsonb_typeof(p_changes->'unitObjectives') is distinct from 'array'
       or jsonb_typeof(p_changes->'deliveryNotes') is distinct from 'array'
       or jsonb_typeof(p_changes->'topicChanges') is distinct from 'array' then
        raise exception 'Invalid unit edit' using errcode = '22023';
    end if;
    select * into v_program from public.learning_programs
      where id = p_program_id and user_id = auth.uid()::text and status <> 'archived'
      for update;
    if not found then
        raise exception 'Program ownership required' using errcode = '42501';
    end if;
    select * into v_unit from public.learning_program_units
      where id = p_unit_id and program_id = p_program_id for update;
    if not found then
        raise exception 'Unit not found' using errcode = '22023';
    end if;
    v_document := v_program.program_data;
    v_units := v_document->'units';
    if jsonb_typeof(v_units) is distinct from 'array'
       or v_unit.unit_number < 1 or jsonb_array_length(v_units) < v_unit.unit_number then
        raise exception 'Program document does not contain the unit' using errcode = '22023';
    end if;
    v_unit_document := v_units->(v_unit.unit_number - 1);
    v_topics := v_unit_document->'topics';
    if jsonb_typeof(v_topics) is distinct from 'array'
       or jsonb_array_length(v_topics) <> jsonb_array_length(p_changes->'topicChanges') then
        raise exception 'Unit topic list is incomplete' using errcode = '22023';
    end if;

    update public.learning_program_units set
      title = trim(p_changes->>'title'),
      overview = coalesce(trim(p_changes->>'overview'), ''),
      unit_objectives = p_changes->'unitObjectives',
      updated_at = now()
    where id = p_unit_id;

    for v_change in select value from jsonb_array_elements(p_changes->'topicChanges') loop
        if jsonb_typeof(v_change) is distinct from 'object'
           or coalesce(v_change->>'id', '') !~ '^[0-9]+$'
           or nullif(trim(v_change->>'title'), '') is null then
            raise exception 'Invalid topic edit' using errcode = '22023';
        end if;
        v_topic_id := (v_change->>'id')::bigint;
        if v_topic_id = any(v_seen) then
            raise exception 'Duplicate topic edit' using errcode = '22023';
        end if;
        v_seen := array_append(v_seen, v_topic_id);
        update public.learning_program_topics set
          title = trim(v_change->>'title'),
          subtopic = coalesce(trim(v_change->>'subtopic'), ''),
          student_summary = coalesce(trim(v_change->>'studentSummary'), ''),
          updated_at = now()
        where id = v_topic_id and unit_id = p_unit_id and program_id = p_program_id
        returning topic_number into v_topic_number;
        if not found or v_topic_number < 1 or v_topic_number > jsonb_array_length(v_topics) then
            raise exception 'Topic does not belong to the unit' using errcode = '22023';
        end if;
        v_topics := jsonb_set(v_topics, array[(v_topic_number - 1)::text],
          (v_topics->(v_topic_number - 1)) || jsonb_build_object(
            'title', trim(v_change->>'title'),
            'subtopic', coalesce(trim(v_change->>'subtopic'), ''),
            'student_summary', coalesce(trim(v_change->>'studentSummary'), '')
          ), false);
    end loop;
    if (select count(*) from public.learning_program_topics
        where unit_id = p_unit_id and program_id = p_program_id) <> cardinality(v_seen) then
        raise exception 'Unit topic list is incomplete' using errcode = '22023';
    end if;
    v_unit_document := v_unit_document || jsonb_build_object(
      'title', trim(p_changes->>'title'),
      'overview', coalesce(trim(p_changes->>'overview'), ''),
      'unit_objectives', p_changes->'unitObjectives',
      'delivery_notes', p_changes->'deliveryNotes',
      'topics', v_topics
    );
    update public.learning_programs set
      program_data = jsonb_set(v_document, array['units', (v_unit.unit_number - 1)::text], v_unit_document, false),
      updated_at = now()
    where id = p_program_id;
end;
$$;
revoke all on function public.classio_save_learning_program_unit(bigint, bigint, jsonb) from public, anon;
grant execute on function public.classio_save_learning_program_unit(bigint, bigint, jsonb) to authenticated;
commit;
