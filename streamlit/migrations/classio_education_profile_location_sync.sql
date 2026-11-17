-- Keep an already published card in sync with the account's country preference.
-- The initial normalization migration was applied separately; this follow-up is additive.
create or replace function public.classio_canonical_teaching_languages(p_values text[])
returns text[] language sql immutable set search_path = public, pg_temp as $$
  select coalesce(array_agg(language order by first_position), '{}'::text[])
  from (
    select language, min(position) first_position
    from (
      select case lower(btrim(value))
        when 'spa' then 'es' when 'spanish' then 'es' when 'español' then 'es' when 'espanol' then 'es'
        when 'ispanyolca' then 'es' when 'i̇spanyolca' then 'es'
        when 'eng' then 'en' when 'english' then 'en' when 'inglés' then 'en' when 'ingles' then 'en'
        when 'ingilizce' then 'en' when 'i̇ngilizce' then 'en'
        when 'tur' then 'tr' when 'turkish' then 'tr' when 'türkçe' then 'tr' when 'turkce' then 'tr'
        else lower(btrim(value)) end as language, position
      from unnest(coalesce(p_values, '{}'::text[])) with ordinality as item(value, position)
    ) normalized where language <> ''
    group by language
  ) unique_languages;
$$;

create or replace function public.classio_sync_teacher_public_country()
returns trigger language plpgsql security definer set search_path = public, pg_temp as $$
begin
  if new.country is distinct from old.country then
    update public.classio_teacher_public_profiles
       set country = left(coalesce(new.country, ''), 80), city = ''
     where teacher_id::text = new.user_id::text
       and country is distinct from left(coalesce(new.country, ''), 80);
  end if;
  return new;
end;
$$;

drop trigger if exists classio_sync_teacher_public_country on public.profiles;
create trigger classio_sync_teacher_public_country
after update of country on public.profiles
for each row execute function public.classio_sync_teacher_public_country();

update public.classio_teacher_public_profiles
set teaching_languages = public.classio_canonical_teaching_languages(teaching_languages)
where teaching_languages is distinct from public.classio_canonical_teaching_languages(teaching_languages);

update public.profiles
set teaching_languages = public.classio_canonical_teaching_languages(teaching_languages)
where teaching_languages is distinct from public.classio_canonical_teaching_languages(teaching_languages);
