-- A teacher's Classio-only visibility preference for one Google event instance.
-- Keep it separate from the refreshed Google event cache so sync cannot undo it.
create table if not exists public.classio_google_calendar_hidden_events (
  user_id uuid not null references auth.users(id) on delete cascade,
  calendar_id text not null,
  event_id text not null,
  hidden_at timestamptz not null default now(),
  primary key (user_id, calendar_id, event_id),
  foreign key (user_id, calendar_id, event_id)
    references public.classio_google_calendar_events(user_id, calendar_id, event_id) on delete cascade
);
create index if not exists classio_google_calendar_hidden_events_recent_idx
  on public.classio_google_calendar_hidden_events(user_id, hidden_at desc);

alter table public.classio_google_calendar_hidden_events enable row level security;
revoke all on public.classio_google_calendar_hidden_events from public, anon, authenticated;
grant select on public.classio_google_calendar_hidden_events to authenticated;
grant all on public.classio_google_calendar_hidden_events to service_role;
create policy classio_google_calendar_hidden_events_owner_read
  on public.classio_google_calendar_hidden_events for select to authenticated
  using (user_id = auth.uid());
