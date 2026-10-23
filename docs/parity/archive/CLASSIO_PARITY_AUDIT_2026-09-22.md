# Classio Streamlit → Expo parity audit and completion plan

**Archivo histórico (corte de septiembre de 2026).** Conservar los hallazgos, fixtures y verificaciones de su fecha. El estado actual y la única cola de equivalencia están en el [checklist de paridad](../CLASSIO_EXPO_PARITY_CHECKLIST.md); los controles de seguridad y operación pasan a la [auditoría tecnológica](../../CLASSIO_TECHNOLOGY_AUDIT.md). No reabrir como pendientes actuales las fases y estados de este informe sin comprobar el código vigente.

Audit date: 2026-09-22  
Blueprint: the current Streamlit implementation  
Target: `https://classio--staging.expo.app`  
Verified Expo release: `gypmkvglva` (2026-09-26)

## 2026-09-26 parity implementation pass

This pass turned the eight shared findings into an explicit work queue and added document-output styling as a ninth track. Completed and deployed in this release:

- **Route authorization:** teacher and student URL families now have an active-workspace capability guard. Wrong-face URLs were verified in staging in both directions; the first declarative implementation exposed a React redirect loop during live acceptance and was replaced with a one-shot web redirect.
- **Internationalization foundation:** the new student notification flow and teacher-discovery language filter ship in EN/ES/TR; document variant labels and footers are localized. A full literal-string sweep remains open.
- **Recommendation/review equivalence:** completed independent practice can now select an eligible, subject-scoped connected teacher and create the same review request used by assigned work. The student recommendation scorer still needs replacement with the Streamlit model.
- **Notifications:** Student Home now derives Streamlit-aligned new, due-soon, overdue, graded, and completed-review signals in a collapsed notification panel. Persisted read/unread state and preferences remain open.
- **Protected workflows:** package-date repair is now available for one learner or the full roster through ownership-scoped Supabase operations. Moving browser-built reports behind protected server routes remains open.
- **Observability/error detail:** structured Supabase message/details/hint extraction is centralized and used by Calendar and Smart Tools. Production event capture and correlation IDs remain open.
- **Acceptance coverage:** type checking, targeted lint, a clean 24-route production export, and authenticated staging checks now cover route guards, student notifications, instructional-language filtering, package-repair controls, analytics optimizer controls, and a real PDF generation action. Automated role-by-role browser fixtures remain open.
- **Accessibility/responsive:** the new notification and filter controls use the shared accessible Disclosure/Select/Button components and retain responsive wrapping. The full device, keyboard, screen-reader, and reduced-motion matrix remains open.
- **Document styling:** generic JSON-like exports were replaced with Streamlit-aligned branded PDF/Word hierarchy: brand header, title and metadata band, section bands, readable list content, localized copy variants, consistent typography/margins, and branded page footers. Saved `branding_settings` now influence brand name, department, header style, font, and density. Staging successfully generated a lesson-plan PDF.

## How this audit was performed

This audit compares workflows and data paths, not only page names. It includes:

- Source comparison across every teacher and student route in `streamlit/app_pages` and `expo/src/app/(app)`.
- Comparison of the Supabase calls and recommendation/practice services used by both faces.
- Authenticated staging checks for practice history and recurring-calendar editing.
- A rollback-only SQL reproduction of the calendar RPC before and after its repair.
- TypeScript validation and a clean 24-page Expo web export.

Statuses below mean:

- **Match** — the main Streamlit workflow and persisted data path are present.
- **Partial** — the route exists, but a material workflow, grouping, model, or control differs.
- **Missing** — the Streamlit capability has no Expo equivalent yet.
- **Fixed in this audit** — repaired, deployed, and verified on staging.

## Defects fixed and verified in this audit

### Student word search — fixed in this audit

The 2026-09-22 history row showed `0%`, `0/6`, while review displayed six answered words. Its reconstructed vocabulary contained serialized fragments such as `["HOLA"` and `"HASTALUEGO"]`. The Expo session reader was accepting a nested array as final instead of recursively decoding it.

The repair now:

- recursively flattens nested and serialized word arrays;
- removes legacy brackets, quotes, and escape characters;
- grades from the actual stored placements before weaker fallback fields;
- regrades a legacy word-search session when it is reviewed and only writes when the score improves.

Authenticated staging verification reopened the affected row, displayed `6 of 6 words found`, calculated `100%`, `6/6`, and persisted the corrected history score after a full reload. Older malformed rows remain eligible for the same safe repair when opened; batching them is included below.

### Calendar recurring-schedule edit — fixed in this audit

The shared `classio_edit_schedule` RPC accepted `p_time` as text but assigned it directly to a PostgreSQL `time without time zone` column. PostgreSQL raised error `42804`, while Expo replaced the structured Supabase error with a generic message.

The repair now:

- casts `p_time::time` in both the in-place update and future-version insert;
- ships as a new immutable migration instead of changing migration history;
- surfaces Supabase's structured error message in the Expo calendar.

The repaired RPC passed a transaction-and-rollback database test. An authenticated staging edit then returned `Weekly schedule updated.` and retained all 15 schedules. Because Streamlit and Expo call the same RPC, this repairs the edit path in both products.

## Student-facing parity matrix

| Page / workflow | Status | Remaining difference from Streamlit |
|---|---|---|
| Student Home | **Partial** | Expo has the four learning cards, urgent assignment, images, notification panel, and recommendations. Completed and finalized-assignment resources are now excluded. Recommendations remain a flat six-card token-overlap list instead of `build_recommended_materials`, ML feedback weighting, subject-grouped tabs, and the same explanation hierarchy. |
| Smart Practice library | **Partial** | Resource types, filters, category-first worksheet flow, imagery, pagination, video playback, drafts, and all exercise families exist. The recommendation tray now excludes its assigned-work cards plus completed and finalized-assignment sources, but ranking is still the simplified Expo overlap scorer rather than the Streamlit recommendation pipeline. |
| Word search | **Fixed in this audit** | New and the newest malformed saved session score correctly. A one-time batch repair is still needed for older malformed `0%` rows so users do not need to open them individually. |
| Practice History / My Progress | **Partial** | Pagination and metrics exist. Streamlit groups both views into subject tabs; Expo presents flat paginated lists. |
| Teacher review from practice | **Near match** | Assigned worksheet/exam reviews work. Independent completed practice now offers eligible subject-scoped connected teachers and stores the shared review request. A fixture-based live transition pass remains. |
| Student Assignments | **Partial** | Worksheet/exam/video tabs, status/search, attempts, feedback, program progress, and pagination exist. Streamlit's subject-grouped nested tabs and some empty-state guidance are flattened in Expo. |
| Smart Study Plan | **Partial** | Personal tasks, streaks, points, assigned programs/topics, and practice requests exist. Public-resource recommendations use a local heuristic instead of the Streamlit recommender; the assigned-program presentation lacks the same subject-grouped drill-down. |
| Find My Teacher | **Partial** | Search, subject and instructional-language filters, relationships, requests, withdrawal/end actions, and pagination exist. The request form now uses only the selected teacher's subjects; authenticated staging acceptance of the request and archived-link renewal remains. |
| Student Profile | **Match** | Core editable identity and preferences are present. Cross-route authorization still needs correction (see shared findings). |
| Student notifications | **Partial** | Student Home now derives and renders new, due-soon, overdue, graded, and completed-review signals in a Streamlit-style collapsed panel. Persisted read/unread/preferences remain missing. |

## Teacher-facing parity matrix

| Page / workflow | Status | Remaining difference from Streamlit |
|---|---|---|
| Teacher Home | **Partial** | Onboarding, action cards, and resource previews exist. Streamlit's active learning-program resume tray and return-to-builder flow are missing. |
| Dashboard | **Partial** | Core counts, next/today lessons, package action center, WhatsApp, reports, goal, and derived notifications exist. Notification read/unread state and preferences are not persisted, and operational error capture does not match Streamlit. |
| Students | **Near match** | Roster, profiles, history, connections, progress, assignments, reviews, programs, recommendations, ML-ranked resource tray, actions, and pagination exist. The remaining work is live acceptance of every review/revision transition and translation cleanup; the student-side independent review gap also prevents complete end-to-end parity here. |
| Lessons | **Near match** | Add, autofill, validation, search/year pagination, edit/delete, and a multi-row current-page bulk editor exist. Live acceptance of mixed valid/invalid bulk rows remains. |
| Payments | **Partial** | Add, package autofill, currency-aware totals, filtering, edit, normalization fields, delete, and explicit one-student/all-students package-date repair now exist. Streamlit's multi-row bulk payment editor remains missing. |
| Calendar | **Partial / edit fixed** | Week/month/day views, recurrence, effective dates, future versioning, exceptions, pauses, filters, expanders, and pagination exist. Recurring edit is fixed. Google Calendar connect/disconnect, auto-sync, event creation/deletion, and stored token workflow are missing. Much of the Expo calendar copy is still hard-coded English. |
| Smart Tools | **Partial** | Lesson plan, worksheet, exam, and learning-program generators, structured editors, saves, and correct document exports exist. Streamlit's CV and cover-letter creation tools are missing (Expo only has the resulting professional-document library). |
| Resources | **Near match** | All five teaching resource types, images, filters, cards, details, assignment, visibility, archive, professional library, and type-correct exports exist. It still needs a fixture-based acceptance pass for every legacy payload shape so missing dictionary keys never collapse a preview/editor. |
| Analytics | **Partial** | Expo has period selection, summary/revenue/delivery/risk tabs, persisted on-page goal editing, four what-if projections, renewal priorities, revenue breakdowns, and delivery/risk signals. Streamlit still has richer forecast tables/charts, more granular strategic actions, and fully translated explanatory UI. |
| Community | **Match for core workflow** | Teacher/student directories, canonical subjects, filters, cards, pagination, and contact controls are present. |
| Profile | **Partial** | Identity, avatar, language/theme/timezone/currency/default duration, teaching attributes, visibility, and deletion exist. Streamlit teacher branding/logo/footer controls are missing. |
| Billing / Account | **Divergent** | Expo exposes Billing and Account to normal teacher/student navigation; Streamlit limits pricing/account management differently. Live checkout/school-contact actions are not connected. This should be reconciled to Streamlit permissions rather than treated as an Expo-only feature. |

## Shared and architectural gaps

1. **Route authorization (P0, completed 2026-09-26):** active teacher/student URL families are guarded and wrong-face URLs safely redirect to the active home.
   - **Resume/reload stability fixed 2026-09-26:** persisted-session hydration now blocks route decisions until Supabase restoration completes, preventing a temporary Sign In redirect from replacing the requested page with Home.
2. **Internationalization (P1):** many teacher screens still contain literal English labels, validation messages, and empty states. Streamlit routes those through `t(...)`. All user-facing Expo strings must move into the EN/ES/TR catalog before parity can be accepted.
3. **Recommendation equivalence (P1):** teacher recommendation ranking has a ported feedback model, but student Home, Practice, and Smart Plan still use local token-overlap ranking. They must share the Streamlit student recommendation feature construction, grouping, logging, and explanation rules.
4. **Notifications (P1):** teacher notifications are derived only at render time; student notifications are absent. Stored read/unread state and preferences are missing for both faces.
5. **Protected workflows (P1):** some document/report generation and package recalculation remain browser-side workflows. Streamlit-equivalent authorization should be enforced server-side for sensitive writes and reports.
6. **Observability (P1):** Streamlit wraps page failures with operational diagnostics and an event ID. Expo has local error messages but no equivalent error monitoring/reporting path.
7. **Acceptance coverage (P1):** there is no role-by-role automated browser suite for the shared Supabase state transitions. Several regressions came from payload-shape compatibility, which needs fixture tests in addition to visual checks.
8. **Accessibility/responsive verification (P2):** components are responsive by construction, but complete keyboard, screen-reader, reduced-motion, phone, tablet, desktop, light, and dark acceptance is still outstanding.

## Admin and developer workspace migration (2026-09-26)

| Workspace | Status | Expo parity delivered / remaining |
|---|---|---|
| Admin access and navigation | **Implemented** | Admin links are hidden from ordinary accounts, `/admin` is directly guarded, and every data load independently verifies the authenticated profile role. |
| Admin Overview | **Implemented** | User, paid-user, recent-signup, suspended-account, product-volume, recent-account, and plan-mix views use live Supabase data. |
| Admin Operations | **Partial** | Accounts, searchable/paginated users, and staff-access records mirror the Streamlit information architecture. Account creation, role assignment, suspension, and other privileged mutations still require protected server endpoints. |
| Pricing and subscriptions | **Partial** | Plan catalog, subscriptions, provider metadata, status totals, payment events, and overrides are visible. Plan and subscription mutations remain intentionally unavailable from the public browser client. |
| AI intelligence and Explorer | **Partial** | Content/readiness counts and the full Explorer queue, states, metadata, and destinations are visible. Publish/assignment actions remain protected-server work. |
| Business and audit | **Implemented for visibility** | Signup trend, plan/status mix, subscription/payment KPIs, overrides, and payment audit history are present. |
| Developer workspace | **Implemented for evidence and diagnostics** | All Streamlit top-level sections exist: Overview, ML Lab, Experiment Evidence, Telemetry, Jobs, and Audit. Experiments, runs, model evidence, artifacts, diagnostics, recommendation telemetry, jobs, and privileged audit rows are live, expandable, searchable, and paginated. |
| Developer mutations | **Not exposed by design** | Experiment launch and integrity reruns stay behind the Streamlit server worker/capability/idempotency/audit boundary until equivalent protected Expo server routes exist. |
| Localization and theming | **Implemented for this workspace batch** | New Admin/Developer UI is catalogued in English, Spanish, and Turkish and uses shared dark/light theme tokens and responsive layouts. |

## Ordered completion plan

### Student recommendation port map (2026-09-26 source trace)

The three Expo surfaces currently rank independently: token overlap in `expo/src/app/(app)/student-home.tsx`, a local recommendation calculation in `expo/src/app/(app)/student-practice.tsx`, and task-title overlap in `expo/src/app/(app)/student-study-plan.tsx`. Home and Practice should share the port of `build_recommended_materials` from `streamlit/helpers/student_recommendations.py`. Smart Plan follows its own Streamlit path, `_recommend_smart_plan_resources` in `streamlit/app_pages/student_study_plan.py`, which calls `find_similar_materials` in `streamlit/helpers/material_recommendations.py`. Share input loading and telemetry where their contracts match, while preserving these distinct ranking algorithms. `streamlit/helpers/student_recommendation_ml.py` provides feedback weighting and impression/open logging.

Port in this order, comparing fixed local fixtures at each step:

1. Build the same bounded input snapshot: profile subjects/stage, practice progress, assignment history and exclusions, unfinished program topics, completed source IDs, and public worksheet/exam/video candidates. Reuse one snapshot across Home, Practice, and Smart Plan instead of adding three Supabase fetch paths. Keep user filters and row limits on every query.
2. Port Python need-profile construction (`_build_student_need_profile`), assignment/program signals, and eligibility policy (`_recommendation_policy`), including cold-start beginner safety, level/stage distance, completed/assigned exclusions, and subject-scoped program rules. The archived-program exclusion plus cold-start and stage-distance gates are live in Expo with local fixtures. The full policy decision and need-profile weight fitting are ported and fixture-checked as pure functions, including a frozen-clock Python weight comparison. Assignment/program signals still need exact porting before wiring the full decision to candidate selection. Confirm with fixtures before ranking.
3. Port feature scoring (`_resource_feature_score`), feedback blend, normalized reasons, program-scoped deduplication, subject-balanced selection, and subject-tab grouping for Home and Practice. Preserve deterministic score/topic/title tie-breaking and the six-item default. Port Smart Plan's task requests, match buckets, score adjustments, and topic coverage separately from `_recommend_smart_plan_resources` and `find_similar_materials`.
4. Match exposure/impression/open identity and idempotency in `expo/src/services/student-practice.ts` with the Python telemetry path. The invalid Expo exposure type was corrected to the schema-permitted `optional_student_recommendation`, and idempotent `opened` exposure events are wired to Home and Practice clicks. `user_activity_log` impressions/opens, full cycle identity, and live RLS acceptance still need parity. Log only displayed items and actual opens; do not create duplicate events on React rerenders. Verify the same candidate set produces equivalent ordering, groups, reasons, and events before replacing each surface.

Do not mark recommendation parity complete from a visual card match. It requires fixture equality for cold start, weak subject, active program, assigned/completed exclusion, legacy resource shapes, and feedback history, followed by bounded authenticated staging acceptance.

### Phase 0 — close data-integrity defects

- [x] Repair nested/serialized word-search grading.
- [x] Repair the affected 2026-09-22 history row and verify persistence.
- [x] Repair the shared calendar edit RPC and deploy the migration.
- [x] Verify recurring-schedule editing in authenticated staging.
- [ ] Add an idempotent batch repair for older malformed word-search sessions, preserving XP monotonicity.
- [ ] Add regression fixtures for current, legacy, nested, and serialized word-search payloads.

Acceptance: all valid completed word searches report the number of actual placed words; no repaired score decreases; whole-schedule and future-version calendar edits both pass in Streamlit and Expo.

### Phase 1 — enforce shared contracts

- [x] Add capability guards to every implemented teacher and student route. Admin/developer route families remain future work because they do not exist in Expo yet.
- [ ] Port remaining literal UI strings to the EN/ES/TR catalog.
- [ ] Centralize structured Supabase error extraction instead of page-specific generic fallbacks. **Partial:** shared extraction is live in Calendar and Smart Tools; remaining pages still need adoption.
- [ ] Add browser tests for route roles, locale switching, and light/dark behavior.

Acceptance: a user cannot render another face by typing its URL; every audited route works in all three languages and both themes.

### Phase 2 — finish the student face

- [ ] Port the Streamlit student recommender into one shared Expo service used by Home, Practice, and Smart Plan.
- [ ] Restore subject-grouped recommendation, History, Progress, Assignment, and Program tabs.
- [x] Implement independent-practice teacher selection and review request against active subject-scoped connections.
- [ ] Add the student notification panel and persisted notification state/preferences. **Partial:** the derived panel is live; persisted state/preferences remain.
- [x] Add instructional-language filtering and controlled subject selection to Find My Teacher. Local TypeScript and targeted lint pass; authenticated staging acceptance remains.
- [ ] Batch-repair legacy practice history and validate every exercise type with saved/resumed sessions.

Acceptance: the same learner and data produce the same recommendation groups, review choices, exercise scores, assignment states, program progress, and notification actions in Streamlit and Expo.

### Phase 3 — finish the teacher face

- [x] Restore Lessons bulk editing with the same validation and recalculation behavior.
- [ ] Restore Payments bulk editing and package-date repair actions. **Partial:** repair actions are live; the multi-row payment editor remains.
- [ ] Port the full Analytics goal optimizer, forecast, strategic recommendations, priority learners, and goal editing. **Partial:** goal editing and scenario projections are live; richer forecast/action parity remains.
- [ ] Add Google Calendar connect/disconnect and auto-sync through protected server routes.
- [ ] Add CV and cover-letter builders, reusing the current professional-resource storage and export renderers.
- [ ] Add teacher branding/logo/footer controls to Profile.
- [ ] Restore Teacher Home's active-program resume/builder handoff.
- [ ] Reconcile Billing/Account visibility and actions with Streamlit permissions.

Acceptance: every Streamlit teacher mutation, filter, expander/tab hierarchy, generated artifact, and external handoff has a matching Expo workflow and shared persisted outcome.

### Phase 4 — exhaustive release acceptance

- [ ] Build golden fixtures for all five resource types and every exercise family, including legacy records.
- [ ] Run teacher→student and student→teacher end-to-end flows for assignments, reviews, revision requests, program progress, and recommendations.
- [ ] Run phone/tablet/desktop, keyboard/screen-reader, EN/ES/TR, light/dark, and reduced-motion matrices.
- [ ] Add production-safe error monitoring and privacy review.
- [ ] Re-run the page-by-page ledger; only mark a capability complete after local validation and authenticated staging evidence.

Acceptance: no open P0/P1 parity item, no failed role transition, and no unmatched Streamlit workflow in the teacher or student face.
