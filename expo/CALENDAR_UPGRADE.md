# Calendar upgrade

## Existing Classio data

The Streamlit calendar stores weekly lessons in `schedules`, one-time changes in `calendar_overrides`, and student pauses in `student_schedule_freezes`. The teacher dashboard and analytics also read these records. Expo continues to use the same tables and schedule-edit RPC so a calendar change appears in the rest of Classio without copying records. The Python Google Calendar helper only attempted one-time event sync and stored OAuth tokens in `profiles.gcal_tokens`.

## Expo interaction

- Day, week, and month views share previous, next, today, date, and student controls.
- The month view becomes a readable agenda on a narrow screen.
- "New lesson" creates a one-time or repeating lesson. "Move or cancel a lesson" prompts the teacher to select an existing event in the day or week agenda; its editor clearly offers move or cancel for that occurrence. The original student and date remain fixed so the change stays attached to the correct lesson. A link in that editor opens the repeating schedule when a series change is intended. The schedule list also edits recurring series, with entire-series or future-only scope.
- Selecting a lesson opens its editor in a dialog. The small close icon, Escape/back action, or a tap outside the dialog dismisses the editor without saving. Switching from an occurrence to its repeating schedule keeps the editor visible.
- A recurring lesson can be created on multiple weekdays in one save. This inserts the selected `schedules` rows in a single Supabase request. The existing schedule table has one weekday per row.
- One-time lessons, moves, cancellations, and pauses continue to feed the teacher dashboard through `buildCalendarEvents`.
- Native browser date and time controls replace free-form date entry on Expo web and use the same system font as Classio's other fields; native Expo keeps text entry until a native date picker is added.

## Google Calendar

The server endpoints `/api/google-calendar` and `/api/google-calendar-callback` handle OAuth with the `calendar.events` scope. Tokens remain in the existing `profiles.gcal_tokens` column. OAuth credentials and the state-signing secret stay on the EAS server, never in the web bundle.

Sync is intentionally one-way and user initiated: Classio → the teacher's primary Google Calendar. It exports weekly series, one-time events, moves, cancellations, and active pauses. Classio marks its own Google events with private metadata, compares content hashes before updates, and removes only stale events marked as Classio-owned. Repeated sync does not recreate unchanged lessons or resend their invitations. Existing one-time events with a `gcal_event_id` are updated in place when possible.

Set `GOOGLE_CAL_CLIENT_ID`, `GOOGLE_CAL_CLIENT_SECRET`, `GOOGLE_CAL_STATE_SECRET`, and `GOOGLE_CAL_REDIRECT_URI` in the EAS Hosting environment. The OAuth client's authorized redirect URI must be `https://app.masterclassio.com/api/google-calendar-callback`. The Google Calendar panel reports that server setup is needed until these are available. Connecting and syncing require a signed-in teacher and should be verified by the account owner.
Use the same Google OAuth client as Streamlit if existing refresh tokens should continue working. If a different client is used, teachers must reconnect once in Expo.

## Current data boundary

The existing `calendar_overrides` schema identifies a changed occurrence by student and original date. A one-time lesson on a day that already has that student's weekly lesson is interpreted as a replacement, following the Python behavior. Supporting an *additional* simultaneous lesson on that same day needs a scoped occurrence identifier in the database and in all calendar consumers; it should be migrated together so dashboard and calendar remain consistent.
