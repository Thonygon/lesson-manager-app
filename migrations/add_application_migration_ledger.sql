-- Application-managed migration ledger used by scripts/check_migrations.py.

create table if not exists public.app_schema_migrations (
    name text primary key check (name ~ '^[a-z0-9][a-z0-9_]*\.sql$'),
    checksum text not null check (checksum ~ '^[0-9a-f]{64}$'),
    release_version text not null default 'unknown',
    applied_by text,
    applied_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_app_schema_migrations_applied_at
    on public.app_schema_migrations (applied_at desc);

alter table public.app_schema_migrations enable row level security;

drop policy if exists "app schema migrations staff read" on public.app_schema_migrations;
create policy "app schema migrations staff read"
    on public.app_schema_migrations
    for select
    using (
        exists (
            select 1
            from public.user_staff_roles
            where user_staff_roles.user_id = auth.uid()
              and user_staff_roles.role_key in ('developer', 'data_scientist')
              and user_staff_roles.is_active = true
        )
    );

revoke insert, update, delete on public.app_schema_migrations from authenticated;
grant select on public.app_schema_migrations to authenticated;
