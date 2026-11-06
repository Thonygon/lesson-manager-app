-- Extend the existing private support queue without changing or deleting reports.
alter table public.classio_help_tickets
  add column if not exists privacy_scope text;

alter table public.classio_help_tickets
  drop constraint if exists classio_help_tickets_kind_check;
alter table public.classio_help_tickets
  add constraint classio_help_tickets_kind_check
  check (kind in ('bug', 'idea', 'accessibility', 'other', 'privacy_rights', 'security_incident'));

alter table public.classio_help_tickets
  add constraint classio_help_tickets_privacy_scope_check
  check (
    (kind = 'privacy_rights' and privacy_scope in ('access', 'rectification', 'erasure', 'restriction', 'portability', 'objection', 'other'))
    or (kind <> 'privacy_rights' and privacy_scope is null)
  );

-- Keep reports for the same queue/RLS; this index makes the urgent intake visible
-- even when the general queue contains many recent product reports.
create index if not exists classio_help_tickets_sensitive_queue_idx
  on public.classio_help_tickets (kind, status, created_at desc)
  where kind in ('privacy_rights', 'security_incident');
