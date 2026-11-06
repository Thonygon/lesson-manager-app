-- Preserve each language-specific attestation for the same publication version.
-- Only the primary-key constraint changes; existing acceptance rows remain intact.
alter table public.classio_legal_acceptances
  drop constraint classio_legal_acceptances_pkey;
alter table public.classio_legal_acceptances
  add constraint classio_legal_acceptances_pkey
  primary key (user_id, slug, version, language);

create or replace function public.classio_accept_legal_documents(
  p_mode text, p_language text, p_version text, p_terms_sha256 text,
  p_teacher_data_sha256 text default null
) returns boolean language plpgsql security definer set search_path = '' as $$
declare
  v_user uuid := auth.uid();
  v_terms public.classio_legal_publications%rowtype;
  v_teacher public.classio_legal_publications%rowtype;
begin
  if v_user is null or p_mode not in ('teacher','student') or p_language not in ('en','es','tr') then
    raise exception 'Valid account, role and language required' using errcode = '42501';
  end if;
  select * into v_terms from public.classio_legal_publications
    where slug = 'terms' and language = p_language and version = p_version and active = true;
  if not found or v_terms.sha256 is distinct from p_terms_sha256 then
    raise exception 'Terms publication changed; reload before accepting' using errcode = '22023';
  end if;
  if p_mode = 'teacher' then
    select * into v_teacher from public.classio_legal_publications
      where slug = 'teacher-data' and language = p_language and version = p_version and active = true;
    if not found or v_teacher.sha256 is distinct from p_teacher_data_sha256 then
      raise exception 'Educator publication changed; reload before accepting' using errcode = '22023';
    end if;
  end if;
  insert into public.classio_legal_acceptances (user_id, slug, language, version, sha256)
    values (v_user, 'terms', p_language, p_version, v_terms.sha256)
    on conflict (user_id, slug, version, language) do nothing;
  if p_mode = 'teacher' then
    insert into public.classio_legal_acceptances (user_id, slug, language, version, sha256)
      values (v_user, 'teacher-data', p_language, p_version, v_teacher.sha256)
      on conflict (user_id, slug, version, language) do nothing;
  end if;
  return true;
end; $$;
