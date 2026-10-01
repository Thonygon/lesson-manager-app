# Classio Supabase Disk IO Audit

## Root Causes Found

- Streamlit reruns were re-executing the same read-heavy loader functions without enough cache coverage.
- Several hot pages were using generic full-row table loads even when they only needed a narrow set of columns.
- The admin page was aggregating recent activity with cross-user scans even though it only needed data for the visible profile set.
- Calendar override sync updates were missing an explicit `user_id` scope in the follow-up update path.
- Some high-risk recommendation and ML history loaders still read large historical datasets and remain the main follow-up area.

## Highest-Risk Queries Audited

| File | Function | Table(s) | Issue | Risk | Status |
| --- | --- | --- | --- | --- | --- |
| `helpers/recommendation_models.py` | `_load_topic_resource_reference_rows` | `teacher_assignments`, `learning_program_recommendation_events`, `learning_program_topic_videos` | Large history scans with high limits | High | Not changed yet |
| `app_pages/admin.py` | `_fetch_recent_app_activity` | `profiles`, `user_activity_log`, `practice_sessions`, `practice_progress`, `teacher_review_requests` | Cross-user reads on every admin rerun | High | Scoped to visible users |
| `app_pages/admin.py` | `_fetch_subscriptions` | `user_subscriptions` | Broad subscription scan | Medium | Scoped to visible users and narrowed columns |
| `helpers/dashboard.py` | `rebuild_dashboard` | `classes`, `payments` | Full-row downloads used for dashboard summaries | High | Narrowed to required columns |
| `app_pages/app_page_dashboard.py` | `render_dashboard` | `classes`, `payments` | Same as above on dashboard page render | High | Narrowed to required columns |
| `app_pages/app_page_analytics.py` | `render_analytics` | `classes`, `payments` | Same as above on analytics page render | High | Narrowed to required columns |
| `helpers/analytics.py` | `build_income_analytics` | `payments` | Full-row payment loads for summary calculations | Medium | Narrowed to required columns |
| `helpers/teacher_student_integration.py` | `load_active_linked_students_for_teacher` | `teacher_student_links`, `teacher_student_subjects`, `profiles` | Repeated uncached linked-student reads | Medium | Cached and narrowed columns |
| `helpers/schedule.py` | `_load_schedules_cached`, `_load_overrides_cached` | `schedules`, `calendar_overrides` | Generic full-row loads | Medium | Narrowed to required columns |
| `app_pages/app_page_calendar.py` | Google Calendar sync update paths | `calendar_overrides` | Follow-up update missing explicit tenant scope | Medium | Scoped by `user_id` |

## Inventory Notes

The repository-wide query audit focused on these operation classes:

- Generic `.select("*")` loaders in `core/database.py`, `helpers/teacher_student_integration.py`, `helpers/schedule.py`, `app_pages/admin.py`, `helpers/learning_programs.py`, and service modules.
- Cached Streamlit readers in dashboard, analytics, schedule, practice, recommendation, and teacher/student integration paths.
- Broad activity and subscription readers in admin surfaces.
- Recommendation, ML, and practice history loaders that can still move large result sets.

## Changes Made

### 1. Central filtered loader and diagnostics

- Added `load_table_filtered(...)` in `core/database.py`.
- Extended `_load_table_cached(...)` to support explicit columns, filter tuples, and ordering.
- Added opt-in diagnostics behind `CLASSIO_DB_DIAGNOSTICS=true`.
- Diagnostics log function name, source table, elapsed time, and returned row count for executed queries.

### 2. Linked-student rerun reduction

- Added `@st.cache_data(ttl=90)` to `_load_active_linked_students_for_teacher_cached(...)`.
- Registered the cached loader with the existing cache registry so writes still invalidate it via `clear_app_caches()`.
- Replaced wildcard selects with explicit columns for `teacher_student_links` and `teacher_student_subjects`.

### 3. Dashboard and analytics row-width reduction

- Replaced generic `load_table(...)` calls with `load_table_filtered(...)` in:
  - `helpers/dashboard.py`
  - `app_pages/app_page_dashboard.py`
  - `app_pages/app_page_analytics.py`
  - `helpers/analytics.py`
- Limited these readers to the columns actually consumed by dashboard and analytics computations.

### 4. Admin cross-user scan reduction

- Scoped `_fetch_subscriptions(...)` to the currently visible `user_id` set.
- Scoped `_fetch_recent_app_activity(...)` to the same visible `user_id` set.
- Kept existing caching while reducing unnecessary row transfers.

### 5. Calendar and schedule tightening

- Replaced generic schedule and override loaders with explicit-column loads in `helpers/schedule.py`.
- Added `user_id` scoping to the Google Calendar sync follow-up updates in `app_pages/app_page_calendar.py`.

## Before / After

These are query-shape improvements measured from code paths, not from production data.

| Area | Before | After |
| --- | --- | --- |
| Linked students loader | 3 live queries per call path (`links`, `subjects`, `profiles`) on repeated page use | 3 live queries on cold cache, then cache reuse for 90s and targeted invalidation after writes |
| Dashboard readers | 2 full-row table reads (`classes`, `payments`) | 2 explicit-column reads with only the fields used for dashboard calculations |
| Analytics readers | 2 full-row table reads plus payment analytics using full payment rows | 2 explicit-column reads plus payment analytics using 6 required payment columns |
| Admin subscriptions | Broad `user_subscriptions` scan up to 500 rows | Visible-user scoped subscription read with 6 required columns |
| Admin recent activity | 4 broad cross-user activity queries + profile activity query | Same number of queries, but all scoped to visible `user_id` values |
| Calendar follow-up override update | Student/date update without explicit tenant filter | Student/date update plus `user_id` filter |

## Files Changed

- `core/database.py`
- `helpers/teacher_student_integration.py`
- `helpers/analytics.py`
- `helpers/dashboard.py`
- `helpers/schedule.py`
- `app_pages/app_page_dashboard.py`
- `app_pages/app_page_analytics.py`
- `app_pages/app_page_calendar.py`
- `app_pages/admin.py`
- `migrations/add_supabase_io_indexes.sql`
- `tests/test_database_query_filters.py`

## Remaining Follow-Up

- `helpers/recommendation_models.py` still contains the heaviest historical reads and should be the next optimization target.
- `helpers/learning_programs.py` and some admin analytics frames still use broader wildcard reads than necessary.
- The app still performs some history-style computations in pandas after loading raw rows; these are candidates for Supabase RPCs or materialized summaries if query volume remains high after this pass.

## Manual Supabase Dashboard Checks Recommended

- Confirm `classes`, `payments`, `calendar_overrides`, and `user_activity_log` dominate read IO less often after deployment.
- Check slow query and index usage for the new composite indexes before and after migration.
- Watch cache hit behavior in the app while `CLASSIO_DB_DIAGNOSTICS=true` is enabled in a non-production environment.
- Review recommendation-model query volume separately because that path remains the largest unoptimized reader.

## When More Compute Might Still Be Legitimate

- Only after the remaining recommendation and ML history loaders are reduced or moved to aggregated SQL/RPC results.
- Only if Supabase metrics still show sustained high read latency or IOPS saturation under normal concurrent usage after these code-path fixes and index rollout.