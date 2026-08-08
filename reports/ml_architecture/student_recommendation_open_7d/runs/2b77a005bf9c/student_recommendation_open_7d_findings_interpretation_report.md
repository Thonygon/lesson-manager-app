# Student Recommendation Open Within 7 Days Academic Report

## General Academic Purpose
This document records a supervised-learning evaluation inside Classio for internal academic and product-learning purposes.

## Research Question
Can a classifier predict whether a student will open an optional recommendation within seven days, using only information available when the recommendation is shown?

## Unit of Analysis
One optional student recommendation exposure.

## Outcome Definition
The target is `opened_within_7d`, derived from recommendation `shown_at` timestamps and subsequent `opened` telemetry events inside a seven-day window.

## Dataset
- extraction timestamp: 2026-08-01T13:56:40.353608+00:00
- included mature labels: 403
- positives: 43
- negatives: 360
- excluded rows: 563
- students represented: 6
- resources represented: 53

## Evaluation Design
- chronological holdout cutoff: 2026-07-23T08:59:45.226331+00:00
- development rows: 322
- holdout rows: 81
- comparisons remain exploratory until the evidence base broadens across usage contexts and repeated runs.

## Result
- best evaluated candidate: no credible winner
- maturity verdict: EXPLORATORY_ONLY

## Validity Threats
- At least one supervised candidate collapsed to single-class predictions on the holdout set.
