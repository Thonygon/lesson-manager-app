-- Oral generation quality feedback and export telemetry use the same controls
-- as the other Smart Tools. Existing reports and events are preserved.
alter table public.classio_document_export_events
  drop constraint if exists classio_document_export_events_document_kind_check;
alter table public.classio_document_export_events
  add constraint classio_document_export_events_document_kind_check
  check (document_kind in (
    'lesson_plan', 'worksheet', 'exam', 'oral_presentation',
    'cv', 'cover_letter', 'student_report', 'student_history',
    'dashboard_report', 'other'
  ));

drop trigger if exists classio_generation_oral_edited on public.oral_presentations;
create trigger classio_generation_oral_edited
after update of oral_data on public.oral_presentations
for each row execute function public.classio_retire_generation_feedback_on_content_edit('oral_presentation', 'oral_data');
