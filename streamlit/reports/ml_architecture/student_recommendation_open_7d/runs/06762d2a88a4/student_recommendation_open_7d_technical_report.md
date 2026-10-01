# Student Recommendation Open Within 7 Days Technical Report

Integrity review:
- This experiment uses current first-party recommendation exposure telemetry.
- No historical audit reconciliation is required for validation.
- The run remains offline evidence only and does not justify direct production replacement by itself.

Comparative interpretation:
- Primary ROC AUC leader: RandomForestClassifier.
- Best thresholded classifier: LogisticRegression.
- Best precision-recall ranking: RandomForestClassifier.
- Calibration leader: RandomForestClassifier.
- Overall model conclusion: RandomForestClassifier.

Conclusion:
- Final review verdict: VALIDATED_EXPLORATORY_RUN.
