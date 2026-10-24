-- Repair the live cover RPC without rewriting its applied migration.
-- Dynamic EXECUTE does not change PL/pgSQL FOUND.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '60s';

create or replace function public.classio_save_generated_cover(
    p_resource_type text, p_resource_id text, p_operation_id uuid, p_cover jsonb
) returns void language plpgsql security definer set search_path = '' as $$
declare
    v_table text;
    v_document_column text;
    v_feature text;
    v_owner uuid;
    v_resource_rows integer;
    v_operation public.classio_ai_operations%rowtype;
    v_existing public.classio_cover_generation_resources%rowtype;
    v_current_operation text;
begin
    if auth.uid() is null then
        raise exception 'Authentication required' using errcode = '42501';
    end if;
    if p_resource_type = 'plan' then
        v_table := 'lesson_plans'; v_document_column := 'plan_json'; v_feature := 'cover_plan';
    elsif p_resource_type = 'worksheet' then
        v_table := 'worksheets'; v_document_column := 'worksheet_json'; v_feature := 'cover_worksheet';
    elsif p_resource_type = 'exam' then
        v_table := 'quick_exams'; v_document_column := 'exam_data'; v_feature := 'cover_exam';
    else
        raise exception 'Invalid resource type' using errcode = '22023';
    end if;
    if p_resource_id is null or length(p_resource_id) > 100
       or p_resource_id !~ '^[a-zA-Z0-9-]+$'
       or p_operation_id is null
       or jsonb_typeof(p_cover) is distinct from 'object'
       or p_cover->>'generator' is distinct from 'classio_ai_resource_cover_v1'
       or p_cover->>'operation_id' is distinct from p_operation_id::text
       or coalesce(p_cover->>'image_data_url', '') !~ '^data:image/(png|jpeg|webp);base64,'
       or length(p_cover->>'image_data_url') > 14000000 then
        raise exception 'Invalid cover payload' using errcode = '22023';
    end if;

    -- Lock the resource first, then the operation. Other edits committed before
    -- this point remain intact because only the cover key is changed below.
    execute format(
        'select user_id::uuid, %I->''cover_image''->>''operation_id'' from public.%I where id::text = $1 for update',
        v_document_column, v_table
    ) into v_owner, v_current_operation using p_resource_id;
    get diagnostics v_resource_rows = row_count;
    if v_resource_rows <> 1 or v_owner is distinct from auth.uid() then
        raise exception 'Resource ownership required' using errcode = '42501';
    end if;
    select * into v_operation from public.classio_ai_operations
      where operation_id = p_operation_id for update;
    if not found or v_operation.actor_user_id is distinct from auth.uid()
       or v_operation.status <> 'success' or v_operation.source <> 'expo'
       or v_operation.modality <> 'image' or v_operation.feature_name <> v_feature then
        raise exception 'Cover generation operation unavailable' using errcode = '22023';
    end if;
    select * into v_existing from public.classio_cover_generation_resources
      where operation_id = p_operation_id;
    if found then
        if v_existing.resource_type = p_resource_type
           and v_existing.resource_id = p_resource_id
           and v_current_operation = p_operation_id::text then
            return; -- A response lost after commit can be retried safely.
        end if;
        raise exception 'Cover generation already linked' using errcode = '23505';
    end if;

    execute format(
        'update public.%I set %I = jsonb_set(coalesce(%I::jsonb, ''{}''::jsonb), ''{cover_image}'', $1, true)%s where id::text = $2',
        v_table, v_document_column, v_document_column,
        case when p_resource_type = 'plan' then '' else ', updated_at = now()' end
    ) using p_cover, p_resource_id;
    -- The AFTER UPDATE trigger validates the new cover and inserts the link.
    -- Its exception rolls back this document change as well.
end;
$$;
commit;
