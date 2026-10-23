# Classio Expo design and UX inspection

**Historical design inspection.** For current Streamlit–Expo acceptance, use the [parity checklist](CLASSIO_EXPO_PARITY_CHECKLIST.md) and the [single audit register](docs/AUDITORIAS_ESTADO_2026-10-22.md). This inspection remains design evidence, not a separate audit queue.

Updated: 2026-09-30. Source of behavioral parity: `streamlit/app_pages` and `streamlit/helpers`; Expo routes: `expo/src/app/(app)`. This checklist is for the visual and interaction pass. The detailed data and workflow parity ledger remains in `CLASSIO_EXPO_PARITY_CHECKLIST.md`.

## Shared app

- [x] Profile is now opened by clicking the user's avatar/name rather than a separate navigation item. Desktop keeps that identity at the foot of the sidebar; compact layouts show it in the page header. The shared shell applies this to student, teacher, admin, and data scientist workspaces; the existing protected `/profile` screen remains the destination. TypeScript, targeted ESLint, whitespace check, and web export passed. EAS deployment `5iz704gdnc` was promoted; versioned and production `/profile` returned HTTP 200 with local bundle `entry-9440dbc033b8ea595e45ea0c99a412d8.js`. Authenticated visual and click review remains for the user's account.
- [x] Design rule for future tasks: every resource gallery uses the teacher Home filter pattern—search and result count above three visible subject, learner-stage, and level selects. Reuse `expo/src/components/resource-filters.tsx` so spacing, labels, and responsive wrapping remain consistent. Public Explore, teacher Home, Resources, and student Practice now use it. Keep resource-type tabs and any page-specific filters below this shared row. Browser checks on staging confirmed that Subject selection changes Public Explore from 9 to 6 results and Resources from 10 to 6 results.
- [x] Public Explore, teacher Home, student Home, and Resources now use one clickable `ResourceShowcaseCard` design, with consistent image, metadata, theme colors, hover response, and accessible labels. Resource filters remain the shared pattern above the gallery.
- [x] Rebuilt public Explore for teachers and students: two hero paths, switchable role preview, matching role cards, dark/light surfaces, and complete authored EN/ES/TR interface copy. Localized the income planner choices and resource metadata. The source-authored resource titles and descriptions retain their original language. Reviewed the deployed desktop page in the browser; TypeScript, targeted ESLint, whitespace check, and 26-route web export passed. Staging deployment: `https://classio--q9px1v2iy4.expo.app`.
- [x] Configured Google OAuth after explicit approval: added the Supabase callback URI to the existing Streamlit Google Cloud OAuth client, allowed production and staging `/home` returns in Supabase, and enabled the Supabase Google provider with that client's ID and secret. Browser testing from `https://classio.expo.app/sign-in` reached Google's account chooser with the expected client ID, Supabase callback, and production return URL.
- [ ] Complete an account-selected Google sign-in and verify the role-based `/home` redirect. The browser is left at Google's account chooser for the user to select their account; no account was selected during configuration.
- [x] Promoted the reviewed deployment `q9px1v2iy4` to the project's production hostname `https://classio.expo.app` after the user confirmed the spelling. Browser verification shows the bilingual teacher/student Explorer at the production URL. The staging alias remains available for subsequent reviews.
- [ ] Explorer parity pass (2026-10-01): Streamlit offers one anonymous AI try each for lesson plans, worksheets, and exams; a learning-program setup that continues after sign-up; complete read-only viewers for all five public resource types; three interactive student demos with in-session progress; and six teacher feature cards. Expo currently sends smart-tool cards to sign-in, shows only resource metadata, and lacks the public demo and feature cards. Implement and verify each workflow while keeping the existing shared resource filter/tab pattern.

- [x] Added a reusable header notification inbox with count, accessible toggle, and direct destinations. Teacher Home and Dashboard use review/package alerts; Student Home uses assignment/review alerts. Removed the duplicate inline sections. TypeScript and targeted ESLint pass.
- [ ] Persist read state and extend the inbox to every route and privileged role using verified sources; the current count means active alerts, not unread alerts.
- [ ] Review responsive navigation, focus states, keyboard access, loading and error states, and EN/ES/TR copy on each route.
- [ ] Make card interaction consistent: the whole card should have an accessible label, visible hover/focus feedback on web, and no redundant Open text.

## Teacher

- [x] Home resource preview has Streamlit's search, subject, learner-stage, and level filters, plus type tabs and six-item paging. Removed the redundant See all resources button and Open labels from navigation cards. TypeScript, targeted ESLint, and whitespace checks passed.
- [x] Home resource cards now deep link by resource ID and open the selected Resources detail after loading. TypeScript and targeted ESLint pass.
- [x] Replaced internal Streamlit wording in the teacher Home onboarding prompt with clear EN/ES/TR guidance.
- [x] Reordered the teacher Dashboard around next lesson, today's lessons, package follow-ups, WhatsApp, academic status, and reports; removed duplicate quick actions. The annual goal editor now closes after saving.
- [x] Added an in-page student report preview with package balance and recent lesson/payment rows before the existing PDF and share actions. The WhatsApp assistant now uses visible filter fields and the Streamlit EN/ES/TR confirm, cancel, and package renewal wording, including active pricing from `pricing_items`.
- [x] Package action cards can mark students inactive for the panel, with a restore control. This state is stored per teacher as numeric per-student flags in `app_settings`; panel metrics, lessons, and renewal actions omit those students while their records and reports remain available.
- [x] Reviewed the authenticated teacher Dashboard on staging in Spanish. Confirmed the goal editor is collapsed, quick actions are absent, action cards include the inactive control, WhatsApp has three visible filters and live prices, and a loaded student report shows balance, lesson, and payment previews. TypeScript, targeted ESLint, and the 26-route web export pass. Deployed to `https://classio--scnebn3klr.expo.app` and the `staging` alias.
- [x] Made the Dashboard goal, next lesson, and four summary metrics clickable. Package risk opens Analytics on its risk tab, and review requests open Students on the reviews tab. Redesigned follow-up cards with the Home resource card layout and icon actions; verified the risk link in an authenticated browser. Deployed to `https://classio--lfwcbto18j.expo.app`.
- [x] Teacher Students now has three top tabs: list, Connections, and Progress. The list uses clickable cards with active status filtering; a selected student has profile/history controls, an activity toggle, and a preselected delete option. Dashboard and Students share numeric per-student activity flags in `app_settings` and reload them on focus; rename and delete paths update the saved status. Inactive students remain in records and reports while Dashboard metrics, lessons, and follow-ups omit them. Fixed the earlier JSON-in-numeric setting error found during browser review. TypeScript and targeted ESLint pass.
- [ ] Decide whether inactivity should also deactivate recurring schedules. The current status is deliberately scoped to Dashboard planning and the teacher roster because the `students` table has no verified active-status column.
- [ ] Audit Dashboard, Students, Lessons, Calendar, Resources, Smart Tools, Payments, Analytics, Community, Profile, Billing, and Account for hierarchy, mobile layout, and Streamlit workflow parity.

## Student

- [x] 2026-10-09 load-pressure pass: replaced the all-page student workspace query with Home, Assignments, Study Plan, and Practice scopes. Large assignment/practice payloads open on demand and public practice resources reuse a brief user-scoped cache. Streamlit's actions and score/progress data remain available. TypeScript and targeted ESLint pass.
- [ ] Confirm student load times, Supabase health, and open/detail/resume behavior with an authenticated staging learner before production deployment.

- [x] Removed redundant Open labels from clickable Home navigation cards.
- [x] Moved Home assignment and review notifications into the header inbox, preserving the Assignments destination.
- [x] Home cards are compact, left aligned, and accessible as buttons; recommendations now have a useful empty state and workspace errors have a retry action.
- [ ] Validate student Home recommendation ranking and urgent work with an authenticated learner in the browser.
- [ ] Audit Practice, Study Plan, Assignments, Find Teacher, Profile, and Account for mobile layout and Streamlit workflow parity.

## Admin

- [x] Overview now gives direct cards into Operations, Subscriptions, AI, and Audit; actionable pending Explorer moves and partial-data warnings appear in the header inbox and deep link to their tabs.
- [ ] Audit the remaining admin tabs for filters, actions, mobile layout, and Streamlit parity.
- [x] Connected header alerts to the existing privileged Explorer and warning data. Persistent read state remains open.

## Developer

- [x] Overview now gives direct cards into Lab, Evidence, Telemetry, and Jobs; unresolved diagnostics and failed jobs appear in the header inbox and deep link to their tabs.
- [ ] Audit the remaining developer tabs for mobile layout and Streamlit parity.
- [x] Connected header alerts to the existing privileged diagnostics and jobs data. Persistent read state remains open.

## Verification

- [ ] Run an authenticated browser review at desktop and phone widths for each role. Latest Students deployment: `https://classio--kv7sv75fyo.expo.app` (staging alias `https://classio--staging.expo.app`). A 26-route web export passed. Authenticated browser checks confirmed the Students list/detail/history load without the prior numeric-setting error, with three top tabs and no private notes on roster cards. Student Practice still needs a student account for live validation.
- [x] Compared teacher Home filters and navigation with Streamlit; verified source behavior and direct resource detail routing.
- [ ] Compare student, admin, and developer Home interactions with authenticated accounts.
