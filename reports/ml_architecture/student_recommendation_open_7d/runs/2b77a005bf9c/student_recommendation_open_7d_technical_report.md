# Student Recommendation Open Within 7 Days Technical Report

Business question: Can Classio predict whether a student will open an optional recommendation within seven days of seeing it?

Target construction:
- `opened_within_7d = 1` when a recommendation exposure records an `opened` event within seven days of `shown_at`.
- `opened_within_7d = 0` when the seven-day window closes without a qualifying `opened` event.
- Rows with still-open observation windows are excluded from training and evaluation.

Evidence sources:
- `resource_exposures` for optional student recommendation impressions.
- `resource_exposure_events` for downstream recommendation opens.
- `practice_sessions` for student-history context.
- resource metadata from `worksheets`, `quick_exams`, and `videos`.

Dataset summary:
- extraction timestamp: 2026-08-01T13:56:40.353608+00:00
- source rows inspected: 966
- mature included rows: 403
- positives: 43
- negatives: 360
- excluded rows: 563
- students represented: 6
- surfaces represented: 2

Evaluation summary:
- chronological cutoff: 2026-07-23T08:59:45.226331+00:00
- development rows: 322
- holdout rows: 81
- winning candidate: no credible winner
- maturity verdict: EXPLORATORY_ONLY

Limitations:
- At least one supervised candidate collapsed to single-class predictions on the holdout set.
