# Classio Machine Learning and Educational Intelligence Blueprint

Date: 2026-07-16

## Executive Summary

Classio currently mixes deterministic workflows, heuristic ranking, and small learned-weight layers, but only one business problem is a credible near-term supervised-learning candidate: predict whether an assigned resource will be opened within seven days from `teacher_assignments.assigned_at` and `teacher_assignments.opened_at` in `teacher_assignments` defined in [migrations/teacher_student_assignments.sql](/Users/agonzalez/Desktop/lesson-manager-app/migrations/teacher_student_assignments.sql:88) and updated in [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:947) and [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:1192).

The current optional recommendation pipelines are not yet reliable supervised targets. Student recommendation opens are logged in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:453), but impressions are only logged on `student_practice` in [app_pages/student_practice.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/student_practice.py:1471), while `student_home` logs opens without impressions in [app_pages/student_home.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/student_home.py:55) and [app_pages/student_home.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/student_home.py:527). That means Classio cannot yet reconstruct genuine shown-but-not-opened negatives for optional recommendations at useful scale.

Components that should remain deterministic:

- Practice mastery aggregation in [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2179) and [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2298).
- Review synchronization loop in [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:2004) and [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2452).
- Material reuse retrieval in [helpers/material_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/material_recommendations.py:231).

Components that should move toward statistical models only after instrumentation improves:

- Student recommendation acceptance / blend model in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:250) and [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:1194).
- Teacher recommendation objective selector in [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:289).
- Teacher recommendation resource ranker in [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:626).

Components that should be merged or retired:

- The report-only “ML recommendation” pipelines in [scripts/generate_student_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_student_recommendation_report.py:134) and [scripts/generate_teacher_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_teacher_recommendation_report.py:176) should not be presented as proof of real production ML performance because they evaluate handcrafted proxy targets from historical outcomes and event score maps rather than the exact product decision target.
- The student live ranker and student report model should eventually share one explicit target definition instead of mixing heuristic score, proxy labels, and dynamic blend weight across [helpers/student_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendations.py:653), [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:1194), and [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:194).

Single best model for the current university project:

- Binary classifier for `opened_within_7d` on assigned resources.
- Label source: `teacher_assignments.assigned_at`, `teacher_assignments.opened_at`, optionally `teacher_assignments.viewed_at`.
- Real live labels on 2026-07-16: 61 positives, 53 negatives, 13 right-censored from 127 assignments between 2026-04-10 and 2026-07-12.
- This is the only target in the repository today that is both product-relevant and reconstructable from real observed timestamps without synthetic negatives.

## Evidence Base

- Data audit: [classio_supervised_ml_data_audit.md](/Users/agonzalez/Desktop/lesson-manager-app/classio_supervised_ml_data_audit.md:1)
- Student report artifact summary: [reports/student_recommendation_project/classio_ml_student_recommendation_summary_single_student.txt](/Users/agonzalez/Desktop/lesson-manager-app/reports/student_recommendation_project/classio_ml_student_recommendation_summary_single_student.txt:1)
- Student report generator: [scripts/generate_student_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_student_recommendation_report.py:134)
- Teacher report generator: [scripts/generate_teacher_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_teacher_recommendation_report.py:176)
- Supabase access: [core/database.py](/Users/agonzalez/Desktop/lesson-manager-app/core/database.py:61)
- Assignment schema: [migrations/teacher_student_assignments.sql](/Users/agonzalez/Desktop/lesson-manager-app/migrations/teacher_student_assignments.sql:21)
- Recommendation feedback schema: [migrations/add_recommendation_feedback_loop.sql](/Users/agonzalez/Desktop/lesson-manager-app/migrations/add_recommendation_feedback_loop.sql:1)
- Learning program schema: [migrations/learning_programs.sql](/Users/agonzalez/Desktop/lesson-manager-app/migrations/learning_programs.sql:3)
- Practice schema: [migrations/practice_tables.sql](/Users/agonzalez/Desktop/lesson-manager-app/migrations/practice_tables.sql:7)

Live read-only counts used in this blueprint came from the same Supabase project on 2026-07-16:

| Table | Rows |
| --- | ---: |
| `profiles` | 24 |
| `students` | 19 |
| `teacher_student_links` | 15 |
| `teacher_student_subjects` | 18 |
| `teacher_assignments` | 127 |
| `teacher_assignment_attempts` | 69 |
| `learning_programs` | 5 |
| `learning_program_topics` | 220 |
| `learning_program_assignments` | 23 |
| `learning_program_progress` | 313 |
| `learning_program_recommendation_events` | 8 |
| `practice_sessions` | 88 |
| `worksheets` | 81 |
| `quick_exams` | 31 |
| `videos` | 44 |
| `user_activity_log` | 7021 |

## Current Report Integrity Check

The current student and teacher recommendation reports use real history, but they do not evaluate the stated business question directly.

- Student report samples are assembled from practice sessions, assignments, and recommendation activity in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:250).
- The student target is handcrafted:
  - `0.3 + 0.7 * score` for practice in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:268).
  - Status-and-score proxy for assignments in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:297).
  - `0.78` for opens and `0.16` for impressions in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:345).
- Teacher report samples are assembled from recommendation events and teacher material activity in [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:595).
- The teacher report target is a fixed event map in [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:499) and objective target map in [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:219).
- The report text claims “binary target construction from observed actions” and “probabilistic linear classifier” in [scripts/generate_student_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_student_recommendation_report.py:257) and [scripts/generate_teacher_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_teacher_recommendation_report.py:309), but the exact target is still a handcrafted proxy, not a true observed seven-day recommendation-open label.
- The checked-in student report summary is real output, not mock data, because the summary file records live mode and a real student id in [reports/student_recommendation_project/classio_ml_student_recommendation_summary_single_student.txt](/Users/agonzalez/Desktop/lesson-manager-app/reports/student_recommendation_project/classio_ml_student_recommendation_summary_single_student.txt:1). The issue is target validity, not fake execution.

Conclusion: the reports are not purely simulated, but their metrics should not be treated as measured production recommendation acceptance performance.

## Component Blueprint

### 1. Teacher Recommendation Objective Selector

| Field | Finding |
| --- | --- |
| Exact component name | Teacher Recommendation Objective Selector |
| Business question | Which pedagogical objective should the teacher tackle next: `next_topic`, `review`, or `pending_gap`? |
| User decision supported | Which student-topic card should appear highest in the teacher recommendation panel |
| Current operational behaviour | Builds topic candidates from learning program progress, scores each candidate, and uses that score to order live teacher recommendation cards |
| Unit of analysis | One `(learning_program_assignment_id, learning_program_topic_id, recommendation_bucket)` candidate |
| Classification | Hybrid retrieval/ranking system with a proxy-label statistical scorer |
| Exact algorithm | Hand-engineered feature extraction plus `_fit_linear_model` over proxy targets from recommendation event summaries in [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:429) |
| Files and functions | [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:154), [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:261), [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:289), [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:483), [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:493), [app_pages/app_page_students.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/app_page_students.py:987) |
| Current features | Progress gap, score gap, retry pressure, status pressure, teacher/student done flags, topic position flags, historical event density, assignment rate, improvement rate |
| Current target | `_teacher_objective_target()` maps event summary to fixed numeric scores `0.18` to `1.0` |
| Labels source | `learning_program_recommendation_events.event_type` and grouped counts |
| Observed outcome or proxy | Handcrafted proxy |
| Output consumed by product | Objective score used to rank teacher recommendation cards |
| UI impact | Teacher recommendations page in [app_pages/app_page_students.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/app_page_students.py:1685) |
| Real row counts and coverage | Based on 8 `learning_program_recommendation_events` rows from 2026-04-10 to 2026-07-12; current live event types are `prefill`, `assignment_created`, `teacher_marked_done` |
| Positive and negative labels | No exact observed positive/negative business label; proxy labels only |
| Teachers/students/resources/topics represented | 1 teacher, 2 students, 4 topics represented in current recommendation-event data |
| Leakage risks | Event counts and last event type are post-decision outcomes reused as training signal; if used online without time guarding, leakage is immediate |
| Cross-tenant risks | Multi-teacher report path aggregates across teachers in [scripts/generate_teacher_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_teacher_recommendation_report.py:215) with no tenant id beyond teacher id |
| Duplicate-event risks | One duplicate recommendation-event signature observed in live data |
| Missing instrumentation | No explicit “recommendation shown” timestamp for objective cards; no unique recommendation instance id |
| Supervised ML appropriate | Not yet |
| Recommended future business question | Which teacher recommendation objective is most likely to lead to a student opening the assigned follow-up resource within seven days? |
| Recommended target | Real downstream open-within-7d after objective-triggered assignment |
| Recommended evaluation metrics | PR-AUC, ROC-AUC, calibration, assignment-open lift, top-1 success rate |
| Recommended maturity | DATA-COLLECTION |
| Next engineering action | Add unique recommendation instance ids and log objective-card impressions before considering supervised training |

### 2. Teacher Recommendation Resource Ranker

This component scores the supporting resource chosen for a teacher recommendation item.

- Implementation: [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:626), [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:723), [app_pages/app_page_students.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/app_page_students.py:278).
- Current algorithm: linear score over subject, stage, level, title overlap, objective match, bucket, focus, explicit topic alignment, and historical priors.
- Current target: `_teacher_event_target()` event-score map in [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:611).
- Classification: hybrid ranking system, not real supervised ML.
- Product effect: `_recommended_resource_match_score()` adds heuristic points plus `5.0 * ml_score` before rendering teacher resource options in [app_pages/app_page_students.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/app_page_students.py:240).
- Real data coverage: same 8 recommendation-event rows; 1 teacher, 2 students, 2 resources, 4 topics.
- Leakage risk: training signal includes post-selection actions like `student_completed` and `student_improved`.
- Duplicate risk: duplicate event signatures can overweight one resource-topic pair.
- Recommended maturity: EXPERIMENTAL.
- Next action: keep as heuristic-plus-affinity ranker until more real recommendation exposures and downstream assignment outcomes exist.

### 3. Teacher Material Feed Ranker

This is the teacher home/explore feed ranker, not the student-progress recommendation engine.

- Implementation: [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:793), [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:956), [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:1000), [app_pages/home.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/home.py:202).
- Behaviour: derives demand and open-rate aggregates from learning programs, teacher assignments, review requests, and `teacher_material_impression` / `teacher_material_open` activity, then scores materials deterministically.
- Classification: heuristic score / ranking system.
- Labels: none in the supervised sense; open rates are descriptive aggregates.
- Real coverage: 6,839 teacher impressions and 134 opens in `user_activity_log`; 2 teachers, 67 resources, 62 topic signatures in live activity.
- Leakage risk: open rates are aggregate post-exposure behaviour, but this is acceptable for a feed heuristic if kept tenant-local.
- Cross-tenant risk: multi-teacher aggregation can blend behaviour from different teachers because no tenant id exists beyond `teacher_id`.
- Recommended maturity: RULE-BASED.
- Next action: keep deterministic, add offline monitoring, do not prioritize supervised ML here before assignment-open modeling.

### 4. Student Recommendation Ranker

- Implementation: [helpers/student_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendations.py:576), [helpers/student_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendations.py:653), [helpers/student_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendations.py:888), [app_pages/student_practice.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/student_practice.py:1439), [app_pages/student_home.py](/Users/agonzalez/Desktop/lesson-manager-app/app_pages/student_home.py:92).
- Business question: which worksheet, exam, or video should the student see next?
- Unit of analysis: one student-resource candidate.
- Classification: hybrid ranking system.
- Exact algorithm: heuristic weighted sum over subject need, topic need, exercise need, program overlap, assignment state, explicit topic alignment, behaviour profile, then additive `ml_blend_weight * ml_score` from `score_student_resource_candidate()` in [helpers/student_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendations.py:789).
- Current features: subject/topic/exercise need, target level/stage, program subject/type fit, assigned-active and assigned-unseen flags, review/next-topic overlap, explicit topic alignment, recent teacher overlap, behaviour completion fit.
- Current target: none directly in this layer; it imports score from the proxy-trained student blend model.
- Output consumed by product: rendered recommendations with reasons and score in `student_practice` and `student_home`.
- Real coverage: 88 practice sessions, 127 assignments, and only 7 student recommendation activity rows; practice spans 16 students, 62 resources, 46 topic signatures.
- Leakage risk: ranker uses assignment status and prior success aggregates that can include post-exposure outcomes.
- Missing instrumentation: `student_home` has opens but no impressions.
- Supervised ML appropriate: eventually yes, but only after full optional recommendation exposure logging.
- Recommended future business question: which shown optional student recommendation is most likely to be opened within seven days?
- Recommended target: real impression-to-open-within-7d label from `user_activity_log`.
- Recommended evaluation metrics: PR-AUC, ROC-AUC, NDCG@k, open-rate lift@k, calibration.
- Recommended maturity: DATA-COLLECTION.
- Next action: instrument every student recommendation surface with a shared recommendation instance id and consistent impression logging.

### 5. Student Recommendation Acceptance / Blend Model

- Implementation: [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:1118), [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:1194), [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:194), [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:250), [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:391).
- Business question: how much should the live student ranker trust the learned score over the heuristic score?
- Classification: statistical estimator trained on proxy labels, not a clean acceptance model.
- Exact algorithm: linear model fitted on practice, assignment, and recommendation activity rows; blend weight is derived from offline test metrics in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:220).
- Current target: handcrafted proxy values from practice score, assignment status/score, and recommendation opens/impressions.
- Labels source: `practice_sessions`, `teacher_assignments`, and `user_activity_log`.
- Observed outcome or proxy: proxy.
- Output consumed by product: `ml_score` and `ml_blend_weight` inserted into live ranker output and logged in recommendation metadata.
- UI impact: recommendation reasons mention ML fit in [helpers/student_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendations.py:850).
- Real row counts and coverage: checked-in live student report summary shows 49 total samples, 34 train, 15 test for one student in [reports/student_recommendation_project/classio_ml_student_recommendation_summary_single_student.txt](/Users/agonzalez/Desktop/lesson-manager-app/reports/student_recommendation_project/classio_ml_student_recommendation_summary_single_student.txt:1).
- Positive and negative labels: report metrics exist, but labels are thresholded proxies from `_target_to_label()` in [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:128), not the product business target.
- Leakage risks: assignment outcomes and score are downstream of resource exposure; `ml_blend_weight` from past evaluation is also reused as a feature in activity rows.
- Recommended maturity: EXPERIMENTAL.
- Next action: retire the “acceptance” framing until the model is retrained on real impression/open labels.

### 6. Explicit Topic-Resource Matching Model

- Implementation: [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:425) and [helpers/recommendation_models.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_models.py:498).
- Business question: how historically aligned is a resource with a learning-program topic?
- Classification: statistical prior / affinity model.
- Exact algorithm: average target scores by `(kind, resource_id, topic_id)` and `(kind, topic_id)` using assignments, recommendation events, and direct video links.
- Current target: `_topic_reference_target()` from assignment score/status and `_teacher_event_target()` from recommendation events.
- Observed outcome or proxy: proxy.
- Output consumed by product: `explicit_topic_match`, `explicit_topic_support`, `direct_topic_link`, `topic_kind_prior`, `topic_match_ambiguity`.
- UI impact: used in teacher resource matching and student recommendation ranking.
- Real coverage: 127 assignments, 8 recommendation events, and direct `learning_program_topics` / video links; only 3 live assignment topic ids are populated in current assignments, so present-day support is sparse.
- Supervised ML appropriate: not as a standalone model; better treated as an engineered feature source.
- Recommended maturity: RULE-BASED.
- Next action: keep it as feature engineering, not as a separate “ML model” claim.

### 7. Practice Mastery Aggregator

- Implementation: [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2179), [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2298), [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2601).
- Business question: what has the student practiced, and how accurate are they by subject/topic/exercise type/level?
- Classification: deterministic workflow.
- Algorithm: exact aggregation of `practice_answers` into `practice_progress`.
- Real coverage: 88 practice sessions, 16 students, 62 source resources, 46 topics.
- Positive/negative labels: not applicable.
- Leakage risk: none if used as historical feature store with time cutoffs.
- Recommended maturity: PRODUCTION.
- Next action: keep deterministic and treat as a supervised-feature source only.

### 8. Review Synchronization Loop

- Implementation: [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:1727), [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:2004), [helpers/practice_engine.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/practice_engine.py:2432).
- Business question: how should teacher review corrections propagate back into practice accuracy and assignment records?
- Classification: deterministic workflow.
- Behaviour: updates `practice_answers.is_correct`, `practice_sessions.score_pct`, `teacher_review_requests`, `teacher_assignments`, `teacher_assignment_attempts`, then rebuilds `practice_progress`.
- Supervised ML appropriate: no.
- Recommended maturity: PRODUCTION.
- Next action: keep deterministic; only add event timestamps if future causal analysis needs them.

### 9. Material Reuse Similarity Retriever

- Implementation: [helpers/material_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/material_recommendations.py:123), [helpers/material_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/material_recommendations.py:181), [helpers/material_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/material_recommendations.py:231), [helpers/material_recommendations.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/material_recommendations.py:296).
- Business question: is there already a sufficiently similar resource so Classio can reuse instead of generating a new one?
- Classification: deterministic retrieval/ranking system.
- Algorithm: weighted similarity over subject, stage, level, topic text, token overlap, and type-specific matches.
- Real coverage: resource pool built from lesson plans, worksheets, exams, and videos; live total resources are at least 81 worksheets, 31 exams, and 44 videos, plus lesson plans loaded from planner storage.
- Supervised ML appropriate: no.
- Recommended maturity: PRODUCTION.
- Next action: keep deterministic and optionally add offline acceptance monitoring.

### 10. Recommendation Event Feedback Loop

- Implementation: [helpers/recommendation_memory.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_memory.py:57), [helpers/recommendation_memory.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_memory.py:89), [helpers/recommendation_memory.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/recommendation_memory.py:140), [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:983), [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:1215), [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:1360), [helpers/teacher_student_integration.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_student_integration.py:1473).
- Business question: how should teacher recommendation actions and assignment outcomes be stored for future learning?
- Classification: deterministic telemetry layer.
- Real coverage: 8 rows live; event types currently observed are `prefill`, `assignment_created`, `teacher_marked_done`.
- Missing instrumentation: current live snapshot shows no `student_started`, `student_completed`, or `student_improved` rows despite code paths existing.
- Recommended maturity: DATA-COLLECTION.
- Next action: verify end-to-end event emission in production and add alerting for missing downstream event types.

### 11. Student Recommendation Report Pipeline

- Implementation: [scripts/generate_student_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_student_recommendation_report.py:134), [helpers/student_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/student_recommendation_ml.py:194), [helpers/ml_reporting.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/ml_reporting.py:641).
- Classification: offline proxy-target evaluation pipeline.
- Current behaviour: generates charts and a docx report from real student history.
- Real or invented metrics: real calculations on real rows, but the target is proxy-based.
- Synthetic data or fallback data: none found in the checked-in single-student artifact path; it runs in `mode=live`.
- Recommended maturity: SHADOW.
- Next action: relabel the report as “proxy recommendation diagnostics” until a real recommendation-open target is available.

### 12. Teacher Recommendation Report Pipeline

- Implementation: [scripts/generate_teacher_recommendation_report.py](/Users/agonzalez/Desktop/lesson-manager-app/scripts/generate_teacher_recommendation_report.py:176), [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:595), [helpers/ml_reporting.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/ml_reporting.py:641).
- Classification: offline proxy-target evaluation pipeline.
- Current behaviour: builds teacher recommendation and objective diagnostics from real recommendation-event and teacher-material activity history.
- Real or invented metrics: calculated from real rows, but targets come from handcrafted event score maps and thresholding.
- Synthetic data or fallback data: no explicit simulated data path found in the checked-in code reviewed here.
- Recommended maturity: SHADOW.
- Next action: stop presenting report maturity strings such as “Production Ready” from [helpers/teacher_recommendation_ml.py](/Users/agonzalez/Desktop/lesson-manager-app/helpers/teacher_recommendation_ml.py:745) as evidence of production model readiness.

## Best Current Supervised Candidate

The single best supervised-learning project for Classio right now is:

- Predict `teacher_assignments.opened_at <= teacher_assignments.assigned_at + 7 days`
- Population: assigned worksheets, exams, and videos in `teacher_assignments`
- Primary key candidates: `teacher_assignments.id`
- Useful features already available:
  - `teacher_id`, `student_id`, `assignment_type`, `source_record_id`, `subject_key`, `topic`, `assigned_at`, `learning_program_topic_id`, `recommendation_bucket`, `recommendation_focus_kind` from `teacher_assignments`
  - Resource metadata from `worksheets`, `quick_exams`, and `videos`
  - Prior student engagement from `practice_sessions`, `practice_progress`, and prior `teacher_assignment_attempts`
  - Student stage/language proxies from `profiles`, `students`, resources, and programs
- Real label counts as of 2026-07-16:
  - Positive: 61
  - Negative: 53
  - Right-censored: 13
- Immediate risks:
  - Only 1 teacher in current live assignment data, so generalisation across teachers is unproven
  - No tenant id beyond teacher id
  - `learning_program_topic_id` is missing on 124 of 127 assignments
  - `opened_at` is missing on 49 rows by design for negatives
- Recommended maturity: EXPERIMENTAL
- Recommended next engineering action: build a frozen offline dataset and baseline rule model first; do not deploy to product yet

## Final Architecture Verdict

- Deterministic core systems should remain deterministic: practice mastery, review sync, and reuse retrieval.
- Current “ML” teacher and student recommendation layers are mostly heuristic or hybrid ranking with small proxy-trained weight updates.
- Optional recommendation acceptance is not yet a credible supervised problem because negative exposure labels are missing.
- Assigned-resource open-within-seven-days is the strongest real supervised candidate today.
- University-project recommendation: use the assigned-resource seven-day open classifier as the primary model, and treat the optional recommendation pipelines as instrumentation work rather than model training work.
