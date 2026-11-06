-- Keep legal acceptance separate from page views and from optional consent.
-- Each later publication must be added with its reviewed hash before it can be accepted.
create table if not exists public.classio_legal_publications (
  slug text not null check (slug in ('terms', 'teacher-data')),
  language text not null check (language in ('en', 'es', 'tr')),
  version text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  effective_date date not null,
  active boolean not null default true,
  primary key (slug, language, version)
);
create unique index if not exists classio_legal_publications_one_active
  on public.classio_legal_publications (slug, language) where active;

insert into public.classio_legal_publications (slug, language, version, sha256, effective_date) values
  ('terms','en','2026-11-05.1','af675e118d08a82920f0eeb858e266e020c2aec7ee8fb6b5807e72b942aa30ea','2026-11-05'),
  ('terms','es','2026-11-05.1','a76503bb6f7db9f516ec113fba0e1499ab4b1651a0418ff1396d51c963a5d0d9','2026-11-05'),
  ('terms','tr','2026-11-05.1','dc969de963fb65dc0b384b3c909f1422a9f64295b68b7752733da2f45ee87c4f','2026-11-05'),
  ('teacher-data','en','2026-11-05.1','c90006395f35661fcac8fc36cd1debba80399cc4bfde6500c737d639050b5ef3','2026-11-05'),
  ('teacher-data','es','2026-11-05.1','b127dd947d9f3bcb476d83415e78ba0acfc6c923a8c0f67778c8f1045ef03e4d','2026-11-05'),
  ('teacher-data','tr','2026-11-05.1','c69497f13ab42e2f0940891bbe14ed94d1573d1bbf86976807bbfbae80e5e8b3','2026-11-05')
on conflict (slug, language, version) do nothing;

create table if not exists public.classio_legal_acceptances (
  user_id uuid not null references auth.users(id) on delete cascade,
  slug text not null check (slug in ('terms', 'teacher-data')),
  language text not null check (language in ('en', 'es', 'tr')),
  version text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  accepted_at timestamptz not null default now(),
  primary key (user_id, slug, version),
  foreign key (slug, language, version) references public.classio_legal_publications (slug, language, version)
);
create index if not exists classio_legal_acceptances_user_idx
  on public.classio_legal_acceptances (user_id, accepted_at desc);

alter table public.classio_legal_publications enable row level security;
alter table public.classio_legal_acceptances enable row level security;
revoke all on public.classio_legal_publications, public.classio_legal_acceptances from public, anon, authenticated;
grant select on public.classio_legal_publications, public.classio_legal_acceptances to authenticated;
create policy classio_legal_publications_read on public.classio_legal_publications
  for select to authenticated using (true);
create policy classio_legal_acceptances_read_own on public.classio_legal_acceptances
  for select to authenticated using (user_id = auth.uid());

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
    on conflict (user_id, slug, version) do nothing;
  if p_mode = 'teacher' then
    insert into public.classio_legal_acceptances (user_id, slug, language, version, sha256)
      values (v_user, 'teacher-data', p_language, p_version, v_teacher.sha256)
      on conflict (user_id, slug, version) do nothing;
  end if;
  return true;
end; $$;
revoke all on function public.classio_accept_legal_documents(text,text,text,text,text) from public, anon;
grant execute on function public.classio_accept_legal_documents(text,text,text,text,text) to authenticated;
