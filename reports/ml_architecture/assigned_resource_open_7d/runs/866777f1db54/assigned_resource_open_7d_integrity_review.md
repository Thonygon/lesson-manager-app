# Phase 3.5 Integrity Review

Run id: `866777f1db54`
Data fingerprint: `2e2973e26148420c255bec1a2f49e6d66a73ed1a33fc40acd5734843458b10cf`

Final verdict:
- `VALIDATED_NO_ROBUST_WINNER`

Key findings:
- The earlier 61/53/13 audit split cannot be exactly reconstructed from the saved Phase 3 artifacts.
- `viewed_at` is not the cause of the discrepancy because there are zero view-only positives in the frozen dataset.
- All intended models executed successfully in the saved Phase 3 run, including `DummyClassifier` and `HistGradientBoostingClassifier`.
- The previous narrative overstated `LogisticRegressionReduced`; the evidence supports `NO_ROBUST_WINNER` rather than an unqualified best model.
- Fully missing training-slice features are now excluded automatically by the evaluator before fitting.

Interpretation:
- Primary ROC AUC leader: `RandomForestClassifier`.
- Best thresholded classifier: `RandomForestClassifier`.
- Best precision-recall ranking: `RandomForestClassifier`.
- Calibration leader: `RandomForestClassifier`.
