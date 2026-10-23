# Streamlit to Expo migration

**Current audit routing:** use the [single audit register](docs/AUDITORIAS_ESTADO_2026-10-22.md) and the [active parity checklist](CLASSIO_EXPO_PARITY_CHECKLIST.md). The migration table and run contract below record earlier phases; some `Planned` and staging statuses predate later code and production deployments. Security issues belong to the [technology audit](docs/CLASSIO_TECHNOLOGY_AUDIT.md), and billing/teacher-ledger integrity to the [financial audit](financial_analysis/README.md).

## Goal

Replace the Streamlit UI with an Expo Router application without exposing privileged credentials or removing the known-good deployment before feature parity is proven.

## Repository contract

```text
streamlit/  Python application, server-only integrations, migrations, tests, reports
expo/       Expo Router web/native application and EAS deployment configuration
```

The Streamlit directory remains independently deployable. The Expo directory is linked to `@classio/classio` and exports to EAS Hosting.

## Security boundary

The Expo bundle may contain only public application configuration:

- Supabase project URL
- Supabase anonymous or publishable key
- public application URLs

The following must never be compiled into Expo:

- Supabase service-role or secret key
- OpenAI, Gemini, or OpenRouter keys
- Stripe secret key or webhook signing secret
- Google OAuth client secret or stored refresh tokens
- privileged admin operations

Those operations remain in Python or move to authenticated server functions. Every browser-facing Supabase operation must be protected by Row Level Security and use the authenticated user's JWT.

## Migration slices

| Capability | Expo target | Server boundary | Status |
| --- | --- | --- | --- |
| Marketing and application shell | Expo Router | None | Complete |
| Supabase session and role routing | Expo Router | Supabase Auth/RLS | Implemented on staging; authenticated role QA pending |
| Teacher dashboard | Expo Router | Supabase RLS | Metrics, recent lessons, assignments, schedule, and quick actions implemented |
| Students and teacher linking | Expo Router | Supabase RLS/RPC | Searchable directory and manual creation implemented; linking mutations planned |
| Lessons, schedules, payments ledger | Expo Router | Supabase RLS | Lesson/payment history and weekly schedule implemented; financial mutations planned |
| Student assignments and practice | Expo Router | Supabase RLS/RPC | Assignment list implemented; practice planned |
| Resource library | Expo Router | Supabase Storage/RLS | Lesson-plan list implemented; editing/storage planned |
| AI worksheet/exam/lesson/program generation | Expo Router UI | Protected Python API | Planned |
| Stripe checkout and portal | Expo Router UI | Protected server API/webhooks | Planned |
| Google Calendar OAuth | Expo Router UI | Protected server OAuth callback | Planned |
| Reports, DOCX/PDF, ML experiments | Expo Router UI | Python jobs/artifact API | Planned |
| Admin and developer workspaces | Expo Router UI | Privileged server API | Planned |

## Rollout rules

1. Deploy every migration slice to an immutable EAS preview.
2. Test teacher, student, admin, and anonymous access separately.
3. Verify RLS with the anonymous and authenticated keys; never test client flows with service-role credentials.
4. Keep the Streamlit deployment available throughout migration.
5. Promote an Expo build to production only after the parity matrix has no blocking gaps and rollback has been exercised.

## Required EAS environment

Configure these variables for the EAS deployment environment used by the web export:

```text
EXPO_PUBLIC_SUPABASE_URL
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY
EXPO_PUBLIC_CLASSIO_API_URL  # optional until the protected API exists
```

The publishable key must be a Supabase `sb_publishable_...` key or legacy anonymous key. The Expo configuration rejects secret and service-role credentials. Add the deployed EAS URL to Supabase Authentication URL Configuration and, before enabling Google login, to the provider's permitted redirect URLs.

## Current Expo deployment target

- Target: `https://classio.expo.app` (production hostname; do not deploy new work to the former staging alias)
- Build variables: EAS `preview` until the same variables are provisioned in EAS `production`
- Authentication: password, account confirmation, and passwordless email links for existing users
- Google sign-in: intentionally hidden because the Supabase Google provider is not enabled
- Supabase email-auth Site URL: Expo staging dashboard
- Streamlit deployment: retained independently for rollback and protected server-only workflows

## Definition of complete

The Expo migration is complete only when all currently used Streamlit workflows are available, authorization-equivalent, covered by automated tests, exercised against staging data, and the server-only integrations have monitored production endpoints.

## Recurring parity work contract

Use `CLASSIO_EXPO_PARITY_CHECKLIST.md` for current gaps and acceptance; `CLASSIO_PARITY_AUDIT_2026-09-22.md` is dated evidence. At the start of each run, inspect the current diff, the checklist, and the single audit register; preserve work already in progress. Treat `streamlit/` as the behavioral source of truth for parity comparisons. The production Streamlit deployment remains in use.

For each slice:

1. Select one unresolved workflow, prioritizing broken data or authorization, then shared logic, then user-facing differences. Inventory its Python route, helper, service, validation, defaults, permissions, database queries and mutations, generated outputs, and existing tests. Trace the matching Expo route, service, and server boundary. Record any missing behavior in the checklist before claiming parity.
2. Port the behavior into `expo/` in a reviewable slice. Preserve input validation, edge cases, role and ownership checks, error handling, data shape compatibility, and EN/ES/TR strings. Keep privileged keys and operations on authenticated server routes; never put secrets in the public bundle.
3. Verify with local fixtures and relevant Expo typecheck, lint, or build checks. Prefer fixtures, mocks, and local data. If live Supabase verification is necessary, use a small, bounded, user-owned staging flow with explicit filters and pagination. No table-wide scans, bulk writes, mass backfills, load tests, or production schema changes as part of an unattended run. Stop on rate limits, slow queries, or unexpected errors.
4. Update the parity ledger with source paths, Expo paths, exact behavior verified, remaining gaps, and the next slice. A checked item requires working behavior and local verification; staging verification is recorded separately. Do not infer completeness from a screen or button being present.

Prioritize the remaining work in this order: data integrity and access controls; shared error handling and translation; student recommendation and practice equivalence; student grouping, notifications, and teacher requests; teacher payments, analytics, calendar, professional tools, and branding; protected admin/billing workflows; then full role, locale, device, accessibility, and legacy-payload acceptance. Re-audit all Python routes, helpers, services, and tests against Expo before declaring the migration complete, including ML feature construction, AI generation inputs and outputs, and backend side effects.

Current user priority (2026-09-27): focus parity work first on generative tools, student and teacher recommendations, ML experiments, and Word/PDF document formats. Within these areas, resolve authorization and data-integrity gaps before output/UI differences. The existing server boundary and rollout rules still apply.

Keep deployments to immutable EAS preview builds. Do not promote Expo to production, alter the live Streamlit service, run Supabase migrations, or execute broad data repair automatically. Surface those as concrete reviewable steps with evidence. Each run ends with a concise record of what changed, tests run, open risks, and the next source-to-target slice.
