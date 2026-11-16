-- Classio Education: public professional profiles are separate from private
-- account data. No existing profile is published by this migration.
create table if not exists public.classio_teacher_public_profiles (
  teacher_id uuid primary key references auth.users(id) on delete cascade,
  public_id uuid not null unique default gen_random_uuid(),
  professional_name text not null,
  headline text not null default '',
  biography text not null default '',
  subjects text[] not null default '{}',
  teaching_stages text[] not null default '{}',
  teaching_languages text[] not null default '{}',
  modalities text[] not null default '{}',
  country text not null default '',
  city text not null default '',
  education text not null default '',
  avatar_url text not null default '',
  contact_email text not null default '',
  contact_phone text not null default '',
  show_community_email boolean not null default false,
  show_community_phone boolean not null default false,
  show_web_email boolean not null default false,
  show_web_phone boolean not null default false,
  published_web boolean not null default false,
  publication_notice_version text,
  published_at timestamptz,
  withdrawn_at timestamptz,
  updated_at timestamptz not null default now(),
  constraint education_name_length check (char_length(professional_name) between 2 and 100),
  constraint education_headline_length check (char_length(headline) <= 160),
  constraint education_biography_length check (char_length(biography) <= 1500),
  constraint education_contact_email_length check (char_length(contact_email) <= 254),
  constraint education_avatar_https check (avatar_url = '' or avatar_url ~ '^https://[^[:space:]]+$'),
  constraint education_contact_email check (contact_email = '' or contact_email ~* '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
  constraint education_contact_phone check (contact_phone = '' or contact_phone ~ '^\+?[0-9]{6,15}$'),
  constraint education_modalities check (modalities <@ array['online','in_person']::text[])
);

create index if not exists classio_teacher_public_profiles_published_idx
  on public.classio_teacher_public_profiles (published_web, updated_at desc) where published_web;

alter table public.classio_teacher_public_profiles enable row level security;
revoke all on public.classio_teacher_public_profiles from public, anon, authenticated;
grant select on public.classio_teacher_public_profiles to authenticated;
drop policy if exists teacher_reads_own_public_profile on public.classio_teacher_public_profiles;
create policy teacher_reads_own_public_profile on public.classio_teacher_public_profiles
  for select to authenticated using (teacher_id = auth.uid());

create table if not exists public.classio_teacher_publication_events (
  id bigint generated always as identity primary key,
  teacher_id uuid not null references auth.users(id) on delete cascade,
  public_id uuid not null,
  action text not null check (action in ('save','publish','withdraw')),
  notice_version text not null,
  web_email boolean not null,
  web_phone boolean not null,
  community_email boolean not null,
  community_phone boolean not null,
  occurred_at timestamptz not null default now()
);
alter table public.classio_teacher_publication_events enable row level security;
revoke all on public.classio_teacher_publication_events from public, anon, authenticated;
grant select on public.classio_teacher_publication_events to authenticated;
drop policy if exists teacher_reads_own_publication_events on public.classio_teacher_publication_events;
create policy teacher_reads_own_publication_events on public.classio_teacher_publication_events
  for select to authenticated using (teacher_id = auth.uid());

create or replace function public.classio_save_teacher_public_profile(p_profile jsonb)
returns uuid language plpgsql security definer set search_path = public, pg_temp as $$
declare
  v_id uuid := auth.uid();
  v_public_id uuid;
  v_publish boolean := coalesce((p_profile->>'published_web')::boolean, false);
  v_notice text := 'classio-education-publication-2026-11-16.1';
  v_email text := lower(trim(coalesce(p_profile->>'contact_email', '')));
  v_phone text := trim(coalesce(p_profile->>'contact_phone', ''));
  v_web_email boolean := coalesce((p_profile->>'show_web_email')::boolean, false);
  v_web_phone boolean := coalesce((p_profile->>'show_web_phone')::boolean, false);
  v_community_email boolean := coalesce((p_profile->>'show_community_email')::boolean, false);
  v_community_phone boolean := coalesce((p_profile->>'show_community_phone')::boolean, false);
begin
  if p_profile is null or jsonb_typeof(p_profile) <> 'object' or pg_column_size(p_profile) > 12000
     or jsonb_typeof(coalesce(p_profile->'subjects','[]'::jsonb)) <> 'array'
     or jsonb_typeof(coalesce(p_profile->'teaching_stages','[]'::jsonb)) <> 'array'
     or jsonb_typeof(coalesce(p_profile->'teaching_languages','[]'::jsonb)) <> 'array'
     or jsonb_typeof(coalesce(p_profile->'modalities','[]'::jsonb)) <> 'array'
     or jsonb_array_length(coalesce(p_profile->'subjects','[]'::jsonb)) > 20
     or jsonb_array_length(coalesce(p_profile->'teaching_stages','[]'::jsonb)) > 8
     or jsonb_array_length(coalesce(p_profile->'teaching_languages','[]'::jsonb)) > 12
     or jsonb_array_length(coalesce(p_profile->'modalities','[]'::jsonb)) > 2 then
    raise exception 'Invalid teacher presentation' using errcode = '22023';
  end if;
  if v_id is null or not exists (
    select 1 from public.profiles p where p.user_id::text = v_id::text
      and (p.can_teach = true or p.role in ('teacher','tutor'))
      and coalesce(p.account_status, 'active') = 'active'
  ) then raise exception 'Teacher account required' using errcode = '42501'; end if;
  if v_publish and not exists (
    select 1 from public.profiles p where p.user_id::text = v_id::text and p.show_community_profile = true
  ) then raise exception 'Enable the Community profile before publishing on Classio Education' using errcode = '22023'; end if;
  if v_publish and (jsonb_array_length(coalesce(p_profile->'subjects','[]'::jsonb)) = 0
    or jsonb_array_length(coalesce(p_profile->'teaching_stages','[]'::jsonb)) = 0) then
    raise exception 'A subject and teaching stage are required for publication' using errcode = '22023';
  end if;
  if (v_web_email or v_community_email) and v_email = '' then
    raise exception 'A contact email is required when email sharing is enabled' using errcode = '22023';
  end if;
  if (v_web_phone or v_community_phone) and v_phone = '' then
    raise exception 'A contact phone is required when phone sharing is enabled' using errcode = '22023';
  end if;
  insert into public.classio_teacher_public_profiles as card (
    teacher_id, professional_name, headline, biography, subjects, teaching_stages,
    teaching_languages, modalities, country, city, education, avatar_url,
    contact_email, contact_phone, show_community_email, show_community_phone,
    show_web_email, show_web_phone, published_web, publication_notice_version,
    published_at, withdrawn_at, updated_at
  ) values (
    v_id, left(trim(coalesce(p_profile->>'professional_name', '')), 100),
    left(trim(coalesce(p_profile->>'headline', '')), 160),
    left(trim(coalesce(p_profile->>'biography', '')), 1500),
    coalesce((select array_agg(left(value, 80)) from jsonb_array_elements_text(coalesce(p_profile->'subjects','[]'::jsonb)) value where length(value) between 1 and 80), '{}'),
    coalesce((select array_agg(left(value, 50)) from jsonb_array_elements_text(coalesce(p_profile->'teaching_stages','[]'::jsonb)) value where length(value) between 1 and 50), '{}'),
    coalesce((select array_agg(left(value, 50)) from jsonb_array_elements_text(coalesce(p_profile->'teaching_languages','[]'::jsonb)) value where length(value) between 1 and 50), '{}'),
    coalesce((select array_agg(value) from jsonb_array_elements_text(coalesce(p_profile->'modalities','[]'::jsonb)) value), '{}'),
    left(trim(coalesce(p_profile->>'country', '')), 80), left(trim(coalesce(p_profile->>'city', '')), 80),
    left(trim(coalesce(p_profile->>'education', '')), 100),
    left(trim(coalesce(p_profile->>'avatar_url', '')), 500),
    v_email, v_phone, v_community_email, v_community_phone,
    v_web_email, v_web_phone, v_publish,
    case when v_publish then v_notice else null end,
    case when v_publish then now() else null end,
    case when v_publish then null else now() end, now()
  ) on conflict (teacher_id) do update set
    professional_name = excluded.professional_name, headline = excluded.headline,
    biography = excluded.biography, subjects = excluded.subjects,
    teaching_stages = excluded.teaching_stages, teaching_languages = excluded.teaching_languages,
    modalities = excluded.modalities, country = excluded.country, city = excluded.city,
    education = excluded.education, avatar_url = excluded.avatar_url,
    contact_email = excluded.contact_email, contact_phone = excluded.contact_phone,
    show_community_email = excluded.show_community_email,
    show_community_phone = excluded.show_community_phone,
    show_web_email = excluded.show_web_email, show_web_phone = excluded.show_web_phone,
    published_web = excluded.published_web,
    publication_notice_version = case when excluded.published_web then v_notice else card.publication_notice_version end,
    published_at = case when excluded.published_web then coalesce(card.published_at, now()) else card.published_at end,
    withdrawn_at = case when excluded.published_web then null
      when card.published_web then now() else card.withdrawn_at end,
    updated_at = now()
  returning public_id into v_public_id;
  insert into public.classio_teacher_publication_events
    (teacher_id, public_id, action, notice_version, web_email, web_phone, community_email, community_phone)
  values (v_id, v_public_id, case when v_publish then 'publish' else 'withdraw' end,
    v_notice, v_web_email, v_web_phone, v_community_email, v_community_phone);
  return v_public_id;
end;
$$;
revoke all on function public.classio_save_teacher_public_profile(jsonb) from public, anon;
grant execute on function public.classio_save_teacher_public_profile(jsonb) to authenticated;

create or replace function public.classio_teacher_public_card(p_public_id uuid)
returns jsonb language sql stable security definer set search_path = public, pg_temp as $$
  select jsonb_build_object(
    'public_id', c.public_id, 'name', c.professional_name, 'headline', c.headline,
    'biography', c.biography, 'subjects', c.subjects, 'stages', c.teaching_stages,
    'languages', c.teaching_languages, 'modalities', c.modalities,
    'country', c.country, 'city', c.city, 'education', c.education,
    'avatar_url', c.avatar_url,
    'email', case when c.show_web_email then c.contact_email else null end,
    'phone', case when c.show_web_phone then c.contact_phone else null end
  ) from public.classio_teacher_public_profiles c
  join public.profiles p on p.user_id::text = c.teacher_id::text
  where c.public_id = p_public_id and c.published_web
    and p.show_community_profile = true and (p.can_teach = true or p.role in ('teacher','tutor'))
    and coalesce(p.account_status, 'active') = 'active';
$$;
revoke all on function public.classio_teacher_public_card(uuid) from public;
grant execute on function public.classio_teacher_public_card(uuid) to anon, authenticated;

create or replace function public.classio_list_teacher_public_cards(
  p_stage text default null, p_subject text default null, p_language text default null,
  p_query text default null, p_limit integer default 18, p_offset integer default 0
) returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare v_items jsonb; v_total integer; v_subjects jsonb;
begin
  if p_limit not between 1 and 24 or p_offset not between 0 and 10000
     or length(coalesce(p_query,'')) > 80 then
    raise exception 'Invalid directory filter' using errcode = '22023';
  end if;
  with matched as (
    select c.public_id, c.updated_at from public.classio_teacher_public_profiles c
    join public.profiles p on p.user_id::text = c.teacher_id::text
    where c.published_web and p.show_community_profile = true
      and (p.can_teach = true or p.role in ('teacher','tutor'))
      and coalesce(p.account_status, 'active') = 'active'
      and (p_stage is null or (case p_stage
        when 'kids' then c.teaching_stages && array['early_primary','upper_primary']::text[]
        when 'teens' then c.teaching_stages && array['lower_secondary','upper_secondary']::text[]
        when 'adults' then 'adult_stage' = any(c.teaching_stages)
        else p_stage = any(c.teaching_stages) end))
      and (p_subject is null or p_subject = any(c.subjects))
      and (p_language is null or p_language = any(c.teaching_languages))
      and (p_query is null or c.professional_name ilike '%' || p_query || '%'
           or c.headline ilike '%' || p_query || '%')
  )
  select count(*) into v_total from matched;
  select coalesce(jsonb_agg(public.classio_teacher_public_card(page.public_id)), '[]'::jsonb)
    into v_items from (
      select c.public_id from public.classio_teacher_public_profiles c
      join public.profiles p on p.user_id::text = c.teacher_id::text
      where c.published_web and p.show_community_profile = true
        and (p.can_teach = true or p.role in ('teacher','tutor'))
        and coalesce(p.account_status, 'active') = 'active'
        and (p_stage is null or (case p_stage
          when 'kids' then c.teaching_stages && array['early_primary','upper_primary']::text[]
          when 'teens' then c.teaching_stages && array['lower_secondary','upper_secondary']::text[]
          when 'adults' then 'adult_stage' = any(c.teaching_stages)
          else p_stage = any(c.teaching_stages) end))
        and (p_subject is null or p_subject = any(c.subjects))
        and (p_language is null or p_language = any(c.teaching_languages))
        and (p_query is null or c.professional_name ilike '%' || p_query || '%'
             or c.headline ilike '%' || p_query || '%')
      order by c.updated_at desc, c.public_id limit p_limit offset p_offset
    ) page;
  select coalesce(jsonb_agg(s.subject), '[]'::jsonb) into v_subjects from (
    select distinct subjects.value as subject from public.classio_teacher_public_profiles c
    join public.profiles p on p.user_id::text = c.teacher_id::text
    cross join lateral unnest(c.subjects) as subjects(value)
    where c.published_web and p.show_community_profile = true
      and (p.can_teach = true or p.role in ('teacher','tutor'))
      and coalesce(p.account_status, 'active') = 'active'
    order by subject limit 100
  ) s;
  return jsonb_build_object('items', v_items, 'total', v_total, 'subjects', v_subjects);
end;
$$;
revoke all on function public.classio_list_teacher_public_cards(text,text,text,text,integer,integer) from public;
grant execute on function public.classio_list_teacher_public_cards(text,text,text,text,integer,integer) to anon, authenticated;

create or replace function public.classio_resolve_teacher_public_id(p_public_id uuid)
returns uuid language sql stable security definer set search_path = public, pg_temp as $$
  select c.teacher_id from public.classio_teacher_public_profiles c
  join public.profiles p on p.user_id::text = c.teacher_id::text
  where auth.uid() is not null and c.public_id = p_public_id and c.published_web
    and p.show_community_profile = true and (p.can_teach = true or p.role in ('teacher','tutor'))
    and coalesce(p.account_status, 'active') = 'active';
$$;
revoke all on function public.classio_resolve_teacher_public_id(uuid) from public, anon;
grant execute on function public.classio_resolve_teacher_public_id(uuid) to authenticated;

create or replace function public.classio_community_teacher_contacts(p_teacher_ids text[])
returns jsonb language sql stable security definer set search_path = public, pg_temp as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'teacher_id', p.user_id,
    'email', case when c.teacher_id is null and p.show_community_contact then p.email
                  when c.show_community_email then c.contact_email else null end,
    'phone', case when c.show_community_phone then c.contact_phone else null end
  )), '[]'::jsonb)
  from public.profiles p
  left join public.classio_teacher_public_profiles c on c.teacher_id::text = p.user_id::text
  where auth.uid() is not null and p.user_id::text = any(coalesce(p_teacher_ids,'{}'::text[]))
    and cardinality(coalesce(p_teacher_ids,'{}'::text[])) between 1 and 100
    and p.show_community_profile = true and (p.can_teach = true or p.role in ('teacher','tutor'))
    and coalesce(p.account_status,'active') = 'active';
$$;
revoke all on function public.classio_community_teacher_contacts(text[]) from public, anon;
grant execute on function public.classio_community_teacher_contacts(text[]) to authenticated;

-- Existing account erasure anonymises profiles without deleting auth.users.
-- This trigger removes the public publication and its consent history as well.
create or replace function public.classio_remove_deleted_teacher_public_profile()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
declare v_card public.classio_teacher_public_profiles%rowtype;
begin
  if new.account_status = 'deleted' and old.account_status is distinct from 'deleted' then
    delete from public.classio_teacher_publication_events where teacher_id::text = new.user_id::text;
    delete from public.classio_teacher_public_profiles where teacher_id::text = new.user_id::text;
  elsif (new.show_community_profile is not true or coalesce(new.account_status,'active') <> 'active')
    and (old.show_community_profile is distinct from new.show_community_profile
         or old.account_status is distinct from new.account_status) then
    update public.classio_teacher_public_profiles set published_web = false,
      withdrawn_at = now(), updated_at = now()
    where teacher_id::text = new.user_id::text and published_web
    returning * into v_card;
    if found then
      insert into public.classio_teacher_publication_events
        (teacher_id,public_id,action,notice_version,web_email,web_phone,community_email,community_phone)
      values (v_card.teacher_id,v_card.public_id,'withdraw',coalesce(v_card.publication_notice_version,'classio-education-publication-2026-11-16.1'),
        v_card.show_web_email,v_card.show_web_phone,v_card.show_community_email,v_card.show_community_phone);
    end if;
  end if;
  return new;
end;
$$;
drop trigger if exists classio_remove_deleted_teacher_public_profile on public.profiles;
create trigger classio_remove_deleted_teacher_public_profile
  after update of account_status, show_community_profile on public.profiles for each row
  execute function public.classio_remove_deleted_teacher_public_profile();
