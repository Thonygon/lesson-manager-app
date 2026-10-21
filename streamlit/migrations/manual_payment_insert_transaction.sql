-- A manual class-package payment and all affected expiry dates commit together.
-- The request key makes a retry after an uncertain network response safe.
create table if not exists public.classio_manual_payment_requests (
    user_id text not null,
    request_id uuid not null,
    payload_hash text not null,
    payment_id bigint,
    created_at timestamptz not null default now(),
    primary key (user_id, request_id)
);
alter table public.classio_manual_payment_requests enable row level security;
revoke all on public.classio_manual_payment_requests from public, anon, authenticated;
grant select, insert, update on public.classio_manual_payment_requests to service_role;

create or replace function public.classio_add_manual_payment(
    p_user_id text,
    p_request_id uuid,
    p_payment jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_student text := trim(coalesce(p_payment->>'student',''));
    v_payment_date date;
    v_start_date date;
    v_units integer;
    v_amount numeric;
    v_payment_id bigint;
    v_saved public.classio_manual_payment_requests%rowtype;
    v_package record;
    v_lesson record;
    v_used integer;
    v_purchased integer;
    v_expiry date;
    v_updated integer := 0;
    v_mismatches integer := 0;
begin
    if auth.role() <> 'service_role' and auth.uid()::text is distinct from p_user_id then
        raise exception 'Payment owner required' using errcode = '42501';
    end if;
    if p_request_id is null or p_payment is null or jsonb_typeof(p_payment) <> 'object'
       or v_student = '' or length(v_student) > 300
       or coalesce(p_payment->>'modality','') not in ('Online','Offline')
       or trim(coalesce(p_payment->>'subject','')) = '' then
        raise exception 'Invalid payment input' using errcode = '22023';
    end if;
    v_payment_date := (p_payment->>'payment_date')::date;
    v_start_date := coalesce(nullif(p_payment->>'package_start_date','')::date, v_payment_date);
    v_units := (p_payment->>'number_of_lesson')::integer;
    v_amount := (p_payment->>'paid_amount')::numeric;
    if v_payment_date is null or v_start_date is null or v_units is null or v_units not between 1 and 500
       or v_amount < 0 or v_amount is null
       or trim(coalesce(p_payment->>'currency','')) = '' then
        raise exception 'Invalid payment amount or units' using errcode = '22023';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(p_user_id || ':' || v_student, 0));
    insert into public.classio_manual_payment_requests(user_id, request_id, payload_hash)
    values (p_user_id, p_request_id, md5(p_payment::text))
    on conflict (user_id, request_id) do nothing;
    select * into v_saved from public.classio_manual_payment_requests
    where user_id = p_user_id and request_id = p_request_id for update;
    if v_saved.payload_hash <> md5(p_payment::text) then
        raise exception 'Request key was reused for another payment' using errcode = '22023';
    end if;
    if v_saved.payment_id is not null then
        return jsonb_build_object('payment_id', v_saved.payment_id, 'replayed', true,
                                  'updated', 0, 'mismatches', 0);
    end if;

    if not exists (select 1 from public.students where user_id = p_user_id and student = v_student) then
        insert into public.students(user_id, student) values (p_user_id, v_student);
    end if;

    insert into public.payments(user_id, student, number_of_lesson, payment_date,
                                paid_amount, currency, modality, subject, subject_custom,
                                package_start_date, package_expiry_date,
                                lesson_adjustment_units, package_normalized,
                                normalized_note, normalized_at)
    values (p_user_id, v_student, v_units, v_payment_date, v_amount,
            trim(coalesce(p_payment->>'currency','')),
            p_payment->>'modality', p_payment->>'subject',
            nullif(trim(coalesce(p_payment->>'subject_custom','')),''),
            v_start_date, null, 0, false, '', null)
    returning id into v_payment_id;

    for v_package in
        select id, number_of_lesson, lesson_adjustment_units,
               coalesce(package_start_date::date, payment_date::date) as start_on,
               lead(coalesce(package_start_date::date, payment_date::date)) over (
                   order by coalesce(package_start_date::date, payment_date::date), payment_date::date, id
               ) as next_start_on
        from public.payments
        where user_id = p_user_id and student = v_student
        order by coalesce(package_start_date::date, payment_date::date), payment_date::date, id
    loop
        v_purchased := greatest(0, coalesce(v_package.number_of_lesson,0)
                                  + coalesce(v_package.lesson_adjustment_units,0));
        v_used := 0;
        v_expiry := null;
        if v_purchased > 0 then
            for v_lesson in
                select lesson_date::date as lesson_on, number_of_lesson, note
                from public.classes
                where user_id = p_user_id and student = v_student
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
        where id = v_package.id and user_id = p_user_id
          and (package_start_date::date is distinct from v_package.start_on
               or package_expiry_date::date is distinct from v_expiry);
        if found then v_updated := v_updated + 1; end if;
    end loop;

    update public.classio_manual_payment_requests set payment_id = v_payment_id
    where user_id = p_user_id and request_id = p_request_id;
    return jsonb_build_object('payment_id', v_payment_id, 'replayed', false,
                              'updated', v_updated, 'mismatches', v_mismatches);
end;
$$;
revoke all on function public.classio_add_manual_payment(text,uuid,jsonb) from public, anon;
grant execute on function public.classio_add_manual_payment(text,uuid,jsonb) to authenticated;
