-- ============================================================
-- CLASSIO — Saved resource edit timestamps
-- Adds updated_at tracking to worksheets and quick exams so edits
-- can be ordered and audited consistently with other resource types.
-- ============================================================

create or replace function classio_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

alter table if exists worksheets
    add column if not exists updated_at timestamptz not null default timezone('utc', now());

alter table if exists quick_exams
    add column if not exists updated_at timestamptz not null default timezone('utc', now());

update worksheets
set updated_at = coalesce(created_at, timezone('utc', now()))
where updated_at is null;

update quick_exams
set updated_at = coalesce(created_at, timezone('utc', now()))
where updated_at is null;

drop trigger if exists trg_worksheets_updated_at on worksheets;
create trigger trg_worksheets_updated_at
before update on worksheets
for each row execute function classio_set_updated_at();

drop trigger if exists trg_quick_exams_updated_at on quick_exams;
create trigger trg_quick_exams_updated_at
before update on quick_exams
for each row execute function classio_set_updated_at();

create index if not exists idx_worksheets_user_updated_at
    on worksheets(user_id, updated_at desc);

create index if not exists idx_quick_exams_user_updated_at
    on quick_exams(user_id, updated_at desc);

create index if not exists idx_worksheets_public_active_updated_at
    on worksheets(updated_at desc)
    where is_public = true and status = 'active';

create index if not exists idx_quick_exams_public_active_updated_at
    on quick_exams(updated_at desc)
    where is_public = true and status = 'active';
