-- Separate repeated recommendation renders into stable exposure cycles.

alter table if exists public.resource_exposures
    add column if not exists cycle_id text not null default '';

create index if not exists idx_resource_exposures_viewer_surface_cycle
    on public.resource_exposures (viewer_user_id, surface, cycle_id, shown_at desc);
