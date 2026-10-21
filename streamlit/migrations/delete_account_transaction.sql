-- One RPC call is one PostgreSQL transaction. A failed statement rolls back
-- the full deletion, including the profile status change.
create or replace function public.classio_delete_account_data(p_user_id text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_table text;
    v_column text;
    v_type text;
begin
    if p_user_id is null or p_user_id !~ '^[0-9a-fA-F-]{36}$'
       or (auth.role() <> 'service_role' and auth.uid()::text is distinct from p_user_id) then
        raise exception 'Account ownership required' using errcode = '42501';
    end if;
    if not exists (select 1 from public.profiles where user_id = p_user_id) then
        raise exception 'Profile not found' using errcode = '22023';
    end if;

    -- Child rows first. Payments and administrative audit records are deliberately
    -- retained intact until a retention policy is defined.
    for v_table, v_column in
        select * from (values
            ('teacher_assignment_attempts','teacher_id'), ('teacher_assignment_attempts','student_id'),
            ('teacher_review_requests','teacher_id'), ('teacher_review_requests','student_id'),
            ('teacher_assignments','teacher_id'), ('teacher_assignments','student_id'),
            ('teacher_student_subjects','teacher_id'), ('teacher_student_subjects','student_id'),
            ('teacher_student_links','teacher_id'), ('teacher_student_links','student_id'),
            ('learning_program_assignments','teacher_id'), ('learning_program_assignments','student_user_id'),
            ('learning_program_topic_videos','teacher_id'),
            ('practice_answers','user_id'), ('practice_sessions','user_id'), ('practice_progress','user_id'),
            ('student_schedule_freezes','user_id'),
            ('resource_exposure_events','teacher_id'), ('resource_exposure_events','student_id'), ('resource_exposure_events','viewer_user_id'),
            ('resource_exposures','teacher_id'), ('resource_exposures','student_id'), ('resource_exposures','viewer_user_id'),
            ('learning_program_recommendation_events','teacher_id'), ('learning_program_recommendation_events','student_id'),
            ('classes','user_id'), ('students','user_id'), ('schedules','user_id'),
            ('calendar_overrides','user_id'), ('pricing_items','user_id'), ('app_settings','user_id'),
            ('ai_usage_logs','user_id'), ('user_activity_log','user_id'), ('professional_profiles','user_id'),
            ('user_staff_roles','user_id')
        ) as targets(table_name, column_name)
    loop
        if to_regclass(format('public.%I', v_table)) is null then continue; end if;
        select data_type into v_type from information_schema.columns
        where table_schema = 'public' and table_name = v_table and column_name = v_column;
        if v_type is null then continue; end if;
        if v_type = 'uuid' then
            execute format('delete from public.%I where %I = $1::uuid', v_table, v_column) using p_user_id;
        else
            execute format('delete from public.%I where %I = $1', v_table, v_column) using p_user_id;
        end if;
    end loop;

    for v_table in select unnest(array['lesson_plans','learning_programs','worksheets','quick_exams','videos']) loop
        if to_regclass(format('public.%I', v_table)) is null then continue; end if;
        execute format('delete from public.%I where user_id = $1 and (is_public is distinct from true or status = ''archived'')', v_table) using p_user_id;
        if v_table <> 'learning_programs' then
            execute format('update public.%I set author_name = ''Classio'' where user_id = $1 and is_public = true and status <> ''archived''', v_table) using p_user_id;
        end if;
    end loop;

    update public.profiles set account_status = 'deleted', deleted_at = now(),
        display_name = null, avatar_url = null, phone_number = null,
        show_community_profile = false, show_community_contact = false,
        onboarding_completed = false, login_count = 0, active_student_count = 0
    where user_id = p_user_id;
    return true;
end;
$$;
revoke all on function public.classio_delete_account_data(text) from public, anon;
grant execute on function public.classio_delete_account_data(text) to authenticated, service_role;
