-- Review queue for repeated AI quality problems. It stores references and
-- categorical signals, never prompts, generated text or learner identifiers.
create table if not exists public.classio_ai_supervision_cases (
    id bigint generated always as identity primary key,
    case_key text not null unique check (length(case_key) between 3 and 240),
    source_kind text not null check (source_kind in ('generation_feedback', 'explorer_feedback', 'teacher_relevance', 'operator')),
    source_id text not null default '',
    operation_id uuid,
    resource_type text not null default '',
    resource_id text not null default '',
    reason text not null default '',
    severity text not null default 'low' check (severity in ('low', 'medium', 'high', 'critical')),
    status text not null default 'open' check (status in ('open', 'triaged', 'mitigating', 'resolved', 'dismissed')),
    occurrence_count integer not null default 1 check (occurrence_count > 0),
    owner_user_id uuid references auth.users(id) on delete set null,
    due_at timestamptz,
    resolution_code text check (resolution_code is null or resolution_code in ('model', 'prompt', 'heuristic', 'content', 'privacy', 'duplicate', 'other')),
    created_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    resolved_at timestamptz,
    check (status not in ('resolved', 'dismissed') or resolution_code is not null)
);

create index if not exists classio_ai_cases_open_due_idx
    on public.classio_ai_supervision_cases(status, due_at, last_seen_at desc);
alter table public.classio_ai_supervision_cases enable row level security;
revoke all on public.classio_ai_supervision_cases from public, anon, authenticated;
grant select on public.classio_ai_supervision_cases to authenticated;

drop policy if exists classio_ai_cases_staff_read on public.classio_ai_supervision_cases;
create policy classio_ai_cases_staff_read on public.classio_ai_supervision_cases
for select to authenticated using (
    exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
    or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')
);

create or replace function public.classio_queue_ai_supervision_case(
    p_case_key text, p_source_kind text, p_source_id text, p_operation_id uuid,
    p_resource_type text, p_resource_id text, p_reason text
) returns void language plpgsql security definer set search_path = '' as $$
begin
    if p_source_kind not in ('generation_feedback', 'explorer_feedback', 'teacher_relevance') then
        raise exception 'Invalid AI supervision source';
    end if;
    insert into public.classio_ai_supervision_cases
      (case_key, source_kind, source_id, operation_id, resource_type, resource_id, reason, due_at)
    values
      (left(p_case_key, 240), p_source_kind, left(p_source_id, 160), p_operation_id,
       left(p_resource_type, 40), left(p_resource_id, 80), left(p_reason, 40), now() + interval '7 days')
    on conflict (case_key) do update set
      occurrence_count = public.classio_ai_supervision_cases.occurrence_count + 1,
      severity = case when public.classio_ai_supervision_cases.occurrence_count >= 4 then 'high'
                      when public.classio_ai_supervision_cases.occurrence_count >= 2 then 'medium'
                      else public.classio_ai_supervision_cases.severity end,
      status = case when public.classio_ai_supervision_cases.status in ('resolved', 'dismissed') then 'open'
                    else public.classio_ai_supervision_cases.status end,
      due_at = case when public.classio_ai_supervision_cases.occurrence_count >= 4
                    then least(coalesce(public.classio_ai_supervision_cases.due_at, now() + interval '1 day'), now() + interval '1 day')
                    when public.classio_ai_supervision_cases.occurrence_count >= 2
                    then least(coalesce(public.classio_ai_supervision_cases.due_at, now() + interval '3 days'), now() + interval '3 days')
                    when public.classio_ai_supervision_cases.status in ('resolved', 'dismissed')
                    then now() + interval '7 days' else public.classio_ai_supervision_cases.due_at end,
      resolved_at = null,
      resolution_code = null,
      last_seen_at = now(), updated_at = now();
end;
$$;
revoke all on function public.classio_queue_ai_supervision_case(text,text,text,uuid,text,text,text) from public, anon, authenticated;

create or replace function public.classio_capture_ai_feedback_case()
returns trigger language plpgsql security definer set search_path = '' as $$
declare v_type text; v_id text;
begin
    if tg_table_name = 'classio_generation_intent_feedback_events' then
        if new.satisfied then return new; end if;
        select r.resource_type, r.resource_id into v_type, v_id
          from public.classio_generation_resources r where r.generation_id = new.generation_id;
        perform public.classio_queue_ai_supervision_case(
          'generation:' || new.generation_id::text, 'generation_feedback', new.id::text,
          new.generation_id, coalesce(v_type, ''), coalesce(v_id, ''), coalesce(new.reason, 'unsatisfied'));
    elsif tg_table_name = 'classio_teacher_relevance_feedback_events' then
        if new.action <> 'rejected' then return new; end if;
        select f.resource_type, f.resource_id into v_type, v_id
          from public.classio_teacher_relevance_feedback f where f.id = new.feedback_id;
        if v_type is not null then
          perform public.classio_queue_ai_supervision_case(
            'relevance:' || v_type || ':' || v_id || ':' || coalesce(new.reason, 'unknown'),
            'teacher_relevance', new.id::text, null, v_type, v_id, coalesce(new.reason, 'unknown'));
        end if;
    elsif tg_table_name = 'classio_explorer_generation_feedback' then
        if new.satisfied then return new; end if;
        if tg_op = 'UPDATE' and old.satisfied is false and old.reason is not distinct from new.reason then
            return new;
        end if;
        perform public.classio_queue_ai_supervision_case(
          'explorer:' || new.operation_id::text, 'explorer_feedback', new.operation_id::text,
          new.operation_id, '', '', coalesce(new.reason, 'unsatisfied'));
    end if;
    return new;
end;
$$;
revoke all on function public.classio_capture_ai_feedback_case() from public, anon, authenticated;

drop trigger if exists classio_generation_feedback_supervision on public.classio_generation_intent_feedback_events;
create trigger classio_generation_feedback_supervision after insert on public.classio_generation_intent_feedback_events
for each row execute function public.classio_capture_ai_feedback_case();
drop trigger if exists classio_relevance_feedback_supervision on public.classio_teacher_relevance_feedback_events;
create trigger classio_relevance_feedback_supervision after insert on public.classio_teacher_relevance_feedback_events
for each row execute function public.classio_capture_ai_feedback_case();
drop trigger if exists classio_explorer_feedback_supervision on public.classio_explorer_generation_feedback;
create trigger classio_explorer_feedback_supervision after insert or update of satisfied, reason
on public.classio_explorer_generation_feedback
for each row execute function public.classio_capture_ai_feedback_case();

create or replace function public.classio_update_ai_supervision_case(
    p_id bigint, p_status text, p_owner_user_id uuid, p_due_at timestamptz, p_resolution_code text
) returns boolean language plpgsql security definer set search_path = '' as $$
begin
    if not (exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
          and r.is_active and r.role_key = 'developer')
      or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')) then
        raise exception 'AI supervision permission required' using errcode = '42501';
    end if;
    if p_status not in ('open', 'triaged', 'mitigating', 'resolved', 'dismissed')
       or (p_status in ('resolved', 'dismissed')) <> (p_resolution_code is not null)
       or (p_status not in ('resolved', 'dismissed') and p_due_at is null) then
        raise exception 'Invalid AI supervision state';
    end if;
    if p_owner_user_id is not null and not exists (
      select 1 from public.user_staff_roles r where r.user_id = p_owner_user_id
        and r.is_active and r.role_key in ('developer', 'data_scientist')
    ) then raise exception 'AI supervision owner must be active staff'; end if;
    update public.classio_ai_supervision_cases set status = p_status,
      owner_user_id = p_owner_user_id, due_at = p_due_at,
      resolution_code = p_resolution_code,
      resolved_at = case when p_status in ('resolved', 'dismissed') then now() else null end,
      updated_at = now()
    where id = p_id;
    return found;
end;
$$;
revoke all on function public.classio_update_ai_supervision_case(bigint,text,uuid,timestamptz,text) from public, anon;
grant execute on function public.classio_update_ai_supervision_case(bigint,text,uuid,timestamptz,text) to authenticated;

-- Staff may escalate a suspected privacy, safety or quality incident without
-- entering free text that could contain learner data.
create or replace function public.classio_report_ai_supervision_case(
    p_reason text, p_severity text, p_resource_type text, p_resource_id text, p_operation_id uuid
) returns bigint language plpgsql security definer set search_path = '' as $$
declare v_id bigint;
begin
    if not (exists (select 1 from public.user_staff_roles r where r.user_id = auth.uid()
      and r.is_active and r.role_key in ('developer', 'data_scientist'))
      or exists (select 1 from public.profiles p where p.user_id = auth.uid()::text and p.role = 'admin')) then
        raise exception 'AI supervision permission required' using errcode = '42501';
    end if;
    if p_reason not in ('privacy', 'unsafe_content', 'wrong_answer', 'model_failure', 'other')
      or p_severity not in ('low', 'medium', 'high', 'critical')
      or length(coalesce(p_resource_type, '')) > 40
      or length(coalesce(p_resource_id, '')) > 80
      or coalesce(p_resource_id, '') ~ '[^A-Za-z0-9_-]' then
        raise exception 'Invalid AI supervision report';
    end if;
    insert into public.classio_ai_supervision_cases
      (case_key, source_kind, source_id, operation_id, resource_type, resource_id,
       reason, severity, owner_user_id, due_at)
    values ('operator:' || gen_random_uuid()::text, 'operator', auth.uid()::text, p_operation_id,
      coalesce(p_resource_type, ''), coalesce(p_resource_id, ''), p_reason, p_severity,
      auth.uid(), now() + case when p_severity = 'critical' then interval '4 hours'
                              when p_severity = 'high' then interval '1 day'
                              else interval '7 days' end)
    returning id into v_id;
    return v_id;
end;
$$;
revoke all on function public.classio_report_ai_supervision_case(text,text,text,text,uuid) from public, anon;
grant execute on function public.classio_report_ai_supervision_case(text,text,text,text,uuid) to authenticated;
