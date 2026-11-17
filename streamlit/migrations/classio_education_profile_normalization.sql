-- Canonical teaching languages and profile-derived country for the public directory.
-- This does not touch student, lesson, or payment records.
create or replace function public.classio_canonical_teaching_languages(p_values text[])
returns text[] language sql immutable set search_path = public, pg_temp as $$
  select coalesce(array_agg(language order by first_position), '{}'::text[])
  from (
    select language, min(position) first_position
    from (
      select case lower(btrim(value))
        when 'spa' then 'es' when 'spanish' then 'es' when 'español' then 'es' when 'espanol' then 'es'
        when 'eng' then 'en' when 'english' then 'en' when 'inglés' then 'en' when 'ingles' then 'en'
        when 'tur' then 'tr' when 'turkish' then 'tr' when 'türkçe' then 'tr' when 'turkce' then 'tr'
        else lower(btrim(value)) end as language, position
      from unnest(coalesce(p_values, '{}'::text[])) with ordinality as item(value, position)
    ) normalized where language <> ''
    group by language
  ) unique_languages;
$$;

create or replace function public.classio_guard_teacher_public_location()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
begin
  new.teaching_languages := public.classio_canonical_teaching_languages(new.teaching_languages);
  select left(coalesce(p.country, ''), 80) into new.country
  from public.profiles p where p.user_id::text = new.teacher_id::text;
  new.country := coalesce(new.country, '');
  -- City has no structured account preference; do not publish a second free-text location.
  new.city := '';
  return new;
end;
$$;

drop trigger if exists classio_guard_teacher_public_location on public.classio_teacher_public_profiles;
create trigger classio_guard_teacher_public_location
before insert or update on public.classio_teacher_public_profiles
for each row execute function public.classio_guard_teacher_public_location();

update public.classio_teacher_public_profiles
set teaching_languages = public.classio_canonical_teaching_languages(teaching_languages),
    country = coalesce((select left(p.country, 80) from public.profiles p where p.user_id::text = teacher_id::text), ''),
    city = ''
where teaching_languages is distinct from public.classio_canonical_teaching_languages(teaching_languages)
   or city <> ''
   or country is distinct from coalesce((select left(p.country, 80) from public.profiles p where p.user_id::text = teacher_id::text), '');

update public.profiles
set teaching_languages = public.classio_canonical_teaching_languages(teaching_languages)
where teaching_languages is distinct from public.classio_canonical_teaching_languages(teaching_languages);
