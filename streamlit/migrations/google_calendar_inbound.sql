-- Google events are external calendar data. They are never inserted into
-- schedules, calendar_overrides, classes, or payments by a background sync.
create table if not exists public.classio_google_calendar_sources (
  user_id uuid not null references auth.users(id) on delete cascade,
  calendar_id text not null check (length(calendar_id) between 1 and 320),
  display_name text not null default '' check (length(display_name) <= 160),
  enabled boolean not null default true,
  last_sync_at timestamptz,
  created_at timestamptz not null default now(),
  primary key (user_id, calendar_id)
);

create table if not exists public.classio_google_calendar_events (
  user_id uuid not null references auth.users(id) on delete cascade,
  calendar_id text not null check (length(calendar_id) between 1 and 320),
  event_id text not null check (length(event_id) between 1 and 320),
  title text not null default '' check (length(title) <= 300),
  start_at timestamptz,
  end_at timestamptz,
  date_key text not null default '' check (date_key = '' or date_key ~ '^\d{4}-\d{2}-\d{2}$'),
  all_day boolean not null default false,
  status text not null default 'confirmed' check (status in ('confirmed', 'tentative', 'cancelled')),
  google_updated_at timestamptz,
  etag text not null default '' check (length(etag) <= 240),
  html_link text not null default '' check (length(html_link) <= 1200),
  recurring_event_id text not null default '' check (length(recurring_event_id) <= 320),
  original_start_time text not null default '' check (length(original_start_time) <= 80),
  refreshed_at timestamptz not null default now(),
  primary key (user_id, calendar_id, event_id),
  foreign key (user_id, calendar_id)
    references public.classio_google_calendar_sources(user_id, calendar_id) on delete cascade
);
create index if not exists classio_google_calendar_events_range_idx
  on public.classio_google_calendar_events(user_id, start_at, end_at)
  where status <> 'cancelled';

create table if not exists public.classio_google_calendar_imports (
  user_id uuid not null references auth.users(id) on delete cascade,
  calendar_id text not null,
  event_id text not null,
  student_id bigint not null references public.students(id) on delete cascade,
  imported_at timestamptz not null default now(),
  primary key (user_id, calendar_id, event_id),
  foreign key (user_id, calendar_id, event_id)
    references public.classio_google_calendar_events(user_id, calendar_id, event_id) on delete cascade
);
create index if not exists classio_google_calendar_imports_student_idx
  on public.classio_google_calendar_imports(user_id, student_id);

alter table public.classio_google_calendar_sources enable row level security;
alter table public.classio_google_calendar_events enable row level security;
alter table public.classio_google_calendar_imports enable row level security;
revoke all on public.classio_google_calendar_sources, public.classio_google_calendar_events, public.classio_google_calendar_imports from public, anon, authenticated;
grant select on public.classio_google_calendar_sources, public.classio_google_calendar_events, public.classio_google_calendar_imports to authenticated;
grant all on public.classio_google_calendar_sources, public.classio_google_calendar_events, public.classio_google_calendar_imports to service_role;
create policy classio_google_calendar_sources_owner_read on public.classio_google_calendar_sources
  for select to authenticated using (user_id = auth.uid());
create policy classio_google_calendar_events_owner_read on public.classio_google_calendar_events
  for select to authenticated using (user_id = auth.uid());
create policy classio_google_calendar_imports_owner_read on public.classio_google_calendar_imports
  for select to authenticated using (user_id = auth.uid());

-- Token access for the Expo integration stays on the server. Copy legacy
-- tokens without deleting them: the existing Streamlit Calendar still reads
-- profiles.gcal_tokens during the transition.
create table if not exists public.classio_google_calendar_credentials (
  user_id uuid primary key references auth.users(id) on delete cascade,
  tokens jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.classio_google_calendar_credentials enable row level security;
revoke all on public.classio_google_calendar_credentials from public, anon, authenticated;
grant all on public.classio_google_calendar_credentials to service_role;
insert into public.classio_google_calendar_credentials(user_id, tokens)
select p.user_id::uuid,
  case when jsonb_typeof(p.gcal_tokens) = 'string' then (p.gcal_tokens #>> '{}')::jsonb else p.gcal_tokens end
from public.profiles p
where p.gcal_tokens is not null and p.user_id::text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
on conflict (user_id) do nothing;
