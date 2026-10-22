-- Teacher-entered receipts and lessons are bookkeeping records, not Classio charges.
-- Each mutation and its package-date recalculation share one transaction.
create table if not exists public.classio_teacher_ledger_requests (
    user_id uuid not null,
    request_id uuid not null,
    payload_hash text not null,
    result jsonb,
    created_at timestamptz not null default now(),
    primary key (user_id, request_id)
);
alter table public.classio_teacher_ledger_requests enable row level security;
revoke all on public.classio_teacher_ledger_requests from public, anon, authenticated;
create index if not exists classio_teacher_ledger_requests_created_at_idx
    on public.classio_teacher_ledger_requests(created_at);
create index if not exists classio_manual_payment_requests_created_at_idx
    on public.classio_manual_payment_requests(created_at);

create or replace function public.classio_recalculate_teacher_packages(p_user_id text, p_student text)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
    v_package record;
    v_lesson record;
    v_used integer;
    v_purchased integer;
    v_expiry date;
    v_updated integer := 0;
    v_mismatches integer := 0;
begin
    if p_user_id is null or p_user_id !~ '^[0-9a-fA-F-]{36}$'
       or (auth.role() <> 'service_role' and auth.uid()::text is distinct from p_user_id) then
        raise exception 'Teacher ownership required' using errcode = '42501';
    end if;
    if nullif(trim(coalesce(p_student,'')), '') is null then
        raise exception 'Student required' using errcode = '22023';
    end if;
    perform pg_advisory_xact_lock(hashtextextended(p_user_id || ':' || p_student, 0));
    for v_package in
        select id, number_of_lesson, lesson_adjustment_units,
               coalesce(package_start_date::date, payment_date::date) as start_on,
               lead(coalesce(package_start_date::date, payment_date::date)) over (
                   order by coalesce(package_start_date::date, payment_date::date), payment_date::date, id
               ) as next_start_on
        from public.payments
        where user_id = p_user_id::uuid and student = p_student
        order by coalesce(package_start_date::date, payment_date::date), payment_date::date, id
    loop
        v_purchased := greatest(0, coalesce(v_package.number_of_lesson,0)
                                  + coalesce(v_package.lesson_adjustment_units,0));
        v_used := 0;
        v_expiry := null;
        if v_package.start_on is not null and v_purchased > 0 then
            for v_lesson in
                select lesson_date::date as lesson_on, number_of_lesson, note
                from public.classes
                where user_id = p_user_id::uuid and student = p_student
                  and lesson_date::date >= v_package.start_on
                  and (v_package.next_start_on is null or lesson_date::date < v_package.next_start_on)
                order by lesson_date::date, id
            loop
                if upper(coalesce(v_lesson.note,'')) not like '%[FREE]%'
                   and upper(coalesce(v_lesson.note,'')) not like '%[DEMO]%'
                   and upper(coalesce(v_lesson.note,'')) not like '%[DONT COUNT]%'
                   and upper(coalesce(v_lesson.note,'')) not like '%[DON''T COUNT]%' then
                    v_used := v_used + greatest(0, coalesce(v_lesson.number_of_lesson,0));
                end if;
                if v_expiry is null and v_used >= v_purchased then
                    v_expiry := v_lesson.lesson_on;
                end if;
            end loop;
        end if;
        if v_used > v_purchased then v_mismatches := v_mismatches + 1; end if;
        update public.payments
        set package_start_date = v_package.start_on, package_expiry_date = v_expiry
        where id = v_package.id and user_id = p_user_id::uuid
          and (package_start_date::date is distinct from v_package.start_on
               or package_expiry_date::date is distinct from v_expiry);
        if found then v_updated := v_updated + 1; end if;
    end loop;
    return jsonb_build_object('updated', v_updated, 'mismatches', v_mismatches);
end;
$$;
revoke all on function public.classio_recalculate_teacher_packages(text,text) from public, anon;
grant execute on function public.classio_recalculate_teacher_packages(text,text) to authenticated, service_role;

create or replace function public.classio_mutate_teacher_ledger(
    p_user_id text, p_request_id uuid, p_entity text, p_action text,
    p_row_id bigint, p_payload jsonb
)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
    v_old_student text;
    v_new_student text;
    v_student text;
    v_hash text;
    v_saved public.classio_teacher_ledger_requests%rowtype;
    v_row record;
    v_result jsonb;
    v_recalc jsonb;
    v_updated integer := 0;
    v_mismatches integer := 0;
begin
    if p_user_id is null or p_user_id !~ '^[0-9a-fA-F-]{36}$'
       or (auth.role() <> 'service_role' and auth.uid()::text is distinct from p_user_id) then
        raise exception 'Teacher ownership required' using errcode = '42501';
    end if;
    if p_request_id is null or p_entity is null or p_entity not in ('class','payment')
       or p_action is null or p_action not in ('add','update','delete')
       or (p_action <> 'add' and (p_row_id is null or p_row_id <= 0))
       or (p_action <> 'delete' and (p_payload is null or jsonb_typeof(p_payload) <> 'object')) then
        raise exception 'Invalid ledger change' using errcode = '22023';
    end if;
    if p_action <> 'delete' and exists (
        select 1 from jsonb_object_keys(p_payload) as k(key)
        where (p_entity = 'class' and key not in
               ('student','lesson_date','number_of_lesson','modality','subject','subject_custom','note'))
           or (p_entity = 'payment' and key not in
               ('student','payment_date','number_of_lesson','paid_amount','currency',
                'modality','subject','subject_custom','package_start_date',
                'package_expiry_date','lesson_adjustment_units','package_normalized',
                'normalized_note'))
    ) then
        raise exception 'Unsupported ledger field' using errcode = '22023';
    end if;

    v_hash := md5(jsonb_build_object('entity',p_entity,'action',p_action,
                                     'row_id',p_row_id,'payload',p_payload)::text);
    insert into public.classio_teacher_ledger_requests(user_id,request_id,payload_hash)
    values (p_user_id::uuid,p_request_id,v_hash)
    on conflict (user_id,request_id) do nothing;
    select * into v_saved from public.classio_teacher_ledger_requests
    where user_id = p_user_id::uuid and request_id = p_request_id for update;
    if v_saved.payload_hash <> v_hash then
        raise exception 'Request key reused for another ledger change' using errcode = '22023';
    end if;
    if v_saved.result is not null then return v_saved.result || jsonb_build_object('replayed',true); end if;

    -- Lock the affected student ledgers in stable order, including both names on a move.
    if p_action <> 'add' then
        if p_entity = 'class' then
            select student into v_old_student from public.classes
            where id = p_row_id and user_id = p_user_id::uuid;
        else
            select student into v_old_student from public.payments
            where id = p_row_id and user_id = p_user_id::uuid;
        end if;
        if not found then raise exception 'Ledger row unavailable' using errcode = '22023'; end if;
    end if;
    v_new_student := case when p_action = 'delete' then v_old_student
                     else trim(coalesce(p_payload->>'student', v_old_student, '')) end;
    if nullif(v_new_student,'') is null or length(v_new_student) > 300 then
        raise exception 'Student required' using errcode = '22023';
    end if;
    for v_student in select distinct s from (values (v_old_student),(v_new_student)) as names(s)
                     where s is not null order by s loop
        perform pg_advisory_xact_lock(hashtextextended(p_user_id || ':' || v_student, 0));
    end loop;
    -- A row may have moved while locks were acquired; fail safely and let the caller reload.
    if p_action <> 'add' then
        if p_entity = 'class' then
            perform 1 from public.classes where id = p_row_id and user_id = p_user_id::uuid
                and student = v_old_student for update;
        else
            perform 1 from public.payments where id = p_row_id and user_id = p_user_id::uuid
                and student = v_old_student for update;
        end if;
        if not found then raise exception 'Ledger row changed; reload and retry' using errcode = '40001'; end if;
    end if;

    if p_entity = 'class' and p_action = 'add' then
        if not exists (select 1 from public.students
                       where user_id = p_user_id::uuid and student = v_new_student) then
            insert into public.students(user_id,student) values (p_user_id::uuid,v_new_student);
        end if;
        insert into public.classes(user_id,student,lesson_date,number_of_lesson,
                                   modality,subject,subject_custom,note)
        values (p_user_id::uuid,v_new_student,(p_payload->>'lesson_date')::date,
                (p_payload->>'number_of_lesson')::integer,p_payload->>'modality',
                p_payload->>'subject',p_payload->>'subject_custom',p_payload->>'note')
        returning * into v_row;
    elsif p_entity = 'payment' and p_action = 'add' then
        if not exists (select 1 from public.students
                       where user_id = p_user_id::uuid and student = v_new_student) then
            insert into public.students(user_id,student) values (p_user_id::uuid,v_new_student);
        end if;
        insert into public.payments(user_id,student,payment_date,number_of_lesson,
                                    paid_amount,currency,modality,subject,subject_custom,
                                    package_start_date,package_expiry_date,
                                    lesson_adjustment_units,package_normalized,normalized_note,normalized_at)
        values (p_user_id::uuid,v_new_student,(p_payload->>'payment_date')::date,
                (p_payload->>'number_of_lesson')::integer,(p_payload->>'paid_amount')::numeric,
                p_payload->>'currency',p_payload->>'modality',p_payload->>'subject',
                p_payload->>'subject_custom',
                coalesce((p_payload->>'package_start_date')::date,(p_payload->>'payment_date')::date),
                (p_payload->>'package_expiry_date')::date,
                coalesce((p_payload->>'lesson_adjustment_units')::integer,0),
                coalesce((p_payload->>'package_normalized')::boolean,false),
                coalesce(p_payload->>'normalized_note',''),
                case when coalesce((p_payload->>'package_normalized')::boolean,false)
                          or coalesce(p_payload->>'normalized_note','') <> '' then now() else null end)
        returning * into v_row;
    elsif p_entity = 'class' and p_action = 'update' then
        update public.classes c set
            student = v_new_student,
            lesson_date = case when p_payload ? 'lesson_date' then (p_payload->>'lesson_date')::date else c.lesson_date end,
            number_of_lesson = case when p_payload ? 'number_of_lesson' then (p_payload->>'number_of_lesson')::integer else c.number_of_lesson end,
            modality = case when p_payload ? 'modality' then p_payload->>'modality' else c.modality end,
            subject = case when p_payload ? 'subject' then p_payload->>'subject' else c.subject end,
            subject_custom = case when p_payload ? 'subject_custom' then p_payload->>'subject_custom' else c.subject_custom end,
            note = case when p_payload ? 'note' then p_payload->>'note' else c.note end
        where c.id = p_row_id and c.user_id = p_user_id::uuid returning * into v_row;
    elsif p_entity = 'payment' and p_action = 'update' then
        update public.payments p set
            student = v_new_student,
            payment_date = case when p_payload ? 'payment_date' then (p_payload->>'payment_date')::date else p.payment_date end,
            number_of_lesson = case when p_payload ? 'number_of_lesson' then (p_payload->>'number_of_lesson')::integer else p.number_of_lesson end,
            paid_amount = case when p_payload ? 'paid_amount' then (p_payload->>'paid_amount')::numeric else p.paid_amount end,
            currency = case when p_payload ? 'currency' then p_payload->>'currency' else p.currency end,
            modality = case when p_payload ? 'modality' then p_payload->>'modality' else p.modality end,
            subject = case when p_payload ? 'subject' then p_payload->>'subject' else p.subject end,
            subject_custom = case when p_payload ? 'subject_custom' then p_payload->>'subject_custom' else p.subject_custom end,
            package_start_date = case when p_payload ? 'package_start_date' then (p_payload->>'package_start_date')::date else p.package_start_date end,
            package_expiry_date = case when p_payload ? 'package_expiry_date' then (p_payload->>'package_expiry_date')::date else p.package_expiry_date end,
            lesson_adjustment_units = case when p_payload ? 'lesson_adjustment_units' then (p_payload->>'lesson_adjustment_units')::integer else p.lesson_adjustment_units end,
            package_normalized = case when p_payload ? 'package_normalized' then (p_payload->>'package_normalized')::boolean else p.package_normalized end,
            normalized_note = case when p_payload ? 'normalized_note' then p_payload->>'normalized_note' else p.normalized_note end,
            normalized_at = case when p_payload ? 'package_normalized' or p_payload ? 'normalized_note'
                then case when coalesce((p_payload->>'package_normalized')::boolean,p.package_normalized,false)
                           or coalesce(p_payload->>'normalized_note',p.normalized_note,'') <> ''
                          then now() else null end else p.normalized_at end
        where p.id = p_row_id and p.user_id = p_user_id::uuid returning * into v_row;
    elsif p_entity = 'class' then
        delete from public.classes where id = p_row_id and user_id = p_user_id::uuid returning * into v_row;
    else
        delete from public.payments where id = p_row_id and user_id = p_user_id::uuid returning * into v_row;
    end if;
    if not found then raise exception 'Ledger row unavailable' using errcode = '22023'; end if;
    if p_action <> 'delete' then
        if p_entity = 'class' then
            if v_row.lesson_date is null or v_row.number_of_lesson is null
               or v_row.number_of_lesson not between 1 and 10
               or coalesce(v_row.modality,'') not in ('Online','Offline') then
                raise exception 'Invalid lesson' using errcode = '22023';
            end if;
        else
            if v_row.payment_date is null or v_row.number_of_lesson is null
               or v_row.number_of_lesson not between 1 and 500
               or v_row.paid_amount is null or v_row.paid_amount < 0
               or nullif(trim(v_row.currency),'') is null
               or nullif(trim(v_row.subject),'') is null
               or (v_row.package_expiry_date is not null
                   and v_row.package_expiry_date::date
                       < coalesce(v_row.package_start_date::date,v_row.payment_date::date))
               or coalesce(v_row.modality,'') not in ('Online','Offline') then
                raise exception 'Invalid receipt' using errcode = '22023';
            end if;
        end if;
    end if;
    for v_student in select distinct s from (values (v_old_student),(v_new_student)) as names(s)
                     where s is not null order by s loop
        v_recalc := public.classio_recalculate_teacher_packages(p_user_id,v_student);
        v_updated := v_updated + coalesce((v_recalc->>'updated')::integer,0);
        v_mismatches := v_mismatches + coalesce((v_recalc->>'mismatches')::integer,0);
    end loop;
    v_result := jsonb_build_object('id',v_row.id,'updated',v_updated,
                                   'mismatches',v_mismatches,'replayed',false);
    update public.classio_teacher_ledger_requests set result = v_result
    where user_id = p_user_id::uuid and request_id = p_request_id;
    return v_result;
end;
$$;
revoke all on function public.classio_mutate_teacher_ledger(text,uuid,text,text,bigint,jsonb) from public, anon;
grant execute on function public.classio_mutate_teacher_ledger(text,uuid,text,text,bigint,jsonb) to authenticated, service_role;

-- Request identifiers and hashes are retained for 90 days; receipts and lessons remain.
create extension if not exists pg_cron with schema extensions;
select cron.schedule(
    'classio-teacher-ledger-requests-90d',
    '30 3 * * *',
    $$delete from public.classio_teacher_ledger_requests where created_at < now() - interval '90 days';
      delete from public.classio_manual_payment_requests where created_at < now() - interval '90 days'$$
);
