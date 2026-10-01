# Assigned Resource Open Within 7 Days Technical Report

Business question: Can Classio predict whether a student will open an assigned resource within seven days of assignment?

Integrity review:
- This experiment is exploratory.
- Only one teacher is represented.
- The chronological holdout contains 25 rows.
- The selected model does not dominate all metrics.
- No production decision should be based on this run alone.

Label reconciliation:
- Earlier audit counts: 61 positive, 53 negative, 13 unknown.
- Phase 3 run counts: 72 positive, 53 negative, 2 excluded.
- `viewed_at` does not explain the difference because the frozen dataset has 0 view-only positives.
- Current saved artifacts cannot exactly reproduce the earlier audit split, so the audit-to-run transition is not fully validated from repository evidence alone.

Model completeness:
- MajorityClassRule: status=success
- DummyClassifier: status=success
- LogisticRegression: status=success
- LogisticRegressionReduced: status=success
- DecisionTreeClassifier: status=success
- RandomForestClassifier: status=success
- HistGradientBoostingClassifier: status=success
- SVC: status=success
- KNeighborsClassifier: status=success

Interpretation:
- Primary ROC AUC leader: RandomForestClassifier (0.8269230769230769).
- Best thresholded classifier by balanced accuracy/F1: RandomForestClassifier (balanced_accuracy=0.7628205128205128, F1=0.7692307692307692).
- Best precision-recall ranking: RandomForestClassifier (average_precision=0.8764753764753763).
- Calibration leader: RandomForestClassifier (brier_score=0.2077426380857454, log_loss=0.604947669170616).
- Overall evidence strength: NO_ROBUST_WINNER

Conclusion:
- Final review verdict: VALIDATED_NO_ROBUST_WINNER.
- Overall model conclusion: NO_ROBUST_WINNER.
