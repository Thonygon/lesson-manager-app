# Best next move: product and model contract

## Decision

Classio should first choose a **teacher action** from evidence already available at decision time. The first release is deterministic and auditable. Python resource affinity may rank resources *within* an eligible action, but it must not decide that an action exists. A learned action ranker is a later experiment after exposure and outcome data become reliable.

## Candidate actions and priority

| Action | Eligibility | Destination | Suppression |
| --- | --- | --- | --- |
| Review a student submission | A review request remains open | Student review | Submission reviewed or archived |
| Respond to a practice request | Student asked for more practice on an assigned topic | Student recommendations for that topic | Request addressed or withdrawn |
| Resolve an overused or expiring package | Active student's balance is negative, zero, or near exhaustion | Student package/payments | New package covers the balance or student inactive |
| Prepare the next lesson | Scheduled lesson lacks a suitable plan or related material | Lesson plan generator, prefilled with student/topic | Lesson cancelled, completed, or suitable plan linked |
| Follow up on a scheduled lesson | A near-term lesson needs confirmation | Calendar/lesson record | Confirmed, cancelled, or elapsed |
| Plan future teaching | None of the above is eligible | Calendar | A higher-priority action appears |

Within a priority tier, use the closest actionable deadline, then the oldest unresolved request. Show **one primary action** and at most two alternatives. Never duplicate the same `(student, topic, action)` across cards. Completed, archived, inaccessible, or inactive records are ineligible. A model outage must keep the deterministic decision available.

## Explanation and action contract

Every displayed suggestion needs `action_id`, `action_type`, `student_id` when applicable, `topic_id` when applicable, `source_record_id`, `source_updated_at`, `reason_key`, `destination`, `priority_tier`, and `decision_version`. The explanation should cite the source event in plain language and give a direct action button. No unverified prediction, model score, or inferred student risk belongs in the teacher-facing copy.

Recompute from current records when opening the dashboard and after a relevant mutation. An action ID should be stable for the same source record so exposure and outcomes can be joined. The server must enforce the teacher's access to the student and source record; Expo only displays the result.

## Evidence needed before training

Log a unique decision instance for each displayed action, with candidate set, position, timestamp, teacher, source version, and model/rule version. Log `opened`, `dismissed`, and the actual downstream completion against that instance. A click is an intermediate behavior, not proof that the action helped. Training features must be frozen at display time; later completion or package updates cannot leak into them.

Evaluate rules first: eligible-action precision, stale/duplicate rate, time to resolution, teacher dismissal rate, and whether the destination completed the intended task. Only consider a learned ranker after sufficient multi-teacher exposure and outcome coverage, chronological holdout evaluation, calibration, and a reviewed rollback plan. The existing assigned-resource seven-day classifier is a separate experiment and should not be relabeled as a Best next move model.

## Rollout sequence

1. Authenticate Expo against the Python API and serve one human-approved affinity run from verified private artifacts.
2. Implement the deterministic action contract and event logging; review reasons and navigation with teachers.
3. Compare resource-affinity suggestions with the current fallback on eligible teacher actions.
4. Assess logged outcomes before proposing supervised training.
5. Expose approval, artifact publication, and runtime health in Expo through the same Python service used by Streamlit. Keep Streamlit controls operational until parity is verified.
