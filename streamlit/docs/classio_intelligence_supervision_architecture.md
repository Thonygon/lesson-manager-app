# Classio Intelligence Supervision Architecture

## Why the split changed

Classio now has two different intelligence-management needs:

1. `AI Intelligence`
   This is the operational supervision surface for admins. It should explain what intelligence exists in Classio, how it behaves in production, where signals come from, and which business-facing risks or opportunities need attention.

2. `Experiment Evidence`
   This is the validated experiment governance surface for developers and data scientists. It should hold run registries, integrity state, model comparisons, protected artifacts, and exportable evidence reports tied to approved experiments.

The previous `EIC` implementation mixed those two concerns together. In practice, most of that page was about one validated supervised experiment, not the whole intelligence portfolio. That made the name misleading and made the admin IA heavier than necessary.

## Final placement

### Admin

Keep `AI Intelligence` in Admin.

Admin owners:
- Platform admin
- Product leadership
- Operations leadership

Admin goals:
- Supervise built-in intelligence without touching code
- Understand live portfolio behavior
- Review product-facing risks and decisions
- Track evidence maturity at a high level
- Know when technical teams need to intervene

Admin should not be the primary surface for:
- Experiment reruns
- Technical artifact downloads
- Model-by-model validation work
- Integrity rerun control

### Developer Workspace

Add `Experiment Evidence` to Developer Workspace.

Primary owners:
- Developers
- Data scientists

Developer Workspace goals:
- Run and review approved experiments
- Inspect integrity and maturity verdicts
- Compare validated runs
- Access protected artifacts
- Generate formal reports from validated evidence

## Concrete page architecture

### Admin > AI Intelligence

Sections:
- Portfolio overview
- Intelligence systems
- Data and signal maps
- Operational model readiness
- Product decision guidance

This page should answer:
- What intelligence is active in Classio today?
- What signals feed it?
- What parts are healthy, limited, or still heuristic?
- What should leadership do next?

### Developer Workspace > Experiment Evidence

Sections:
- Latest validated evidence summary
- Experiment registry
- Selected run detail
- Model comparison
- Protected artifacts
- Word reports

This page should answer:
- Which approved experiments exist?
- Which run is the current validated reference?
- Did integrity pass?
- Which model led the selected metrics?
- What evidence can be exported or audited?

## Product language

Recommended naming:
- `AI Intelligence` for the admin supervision page
- `Experiment Evidence` for the developer/data-science evidence page

Reason:
- `AI Intelligence` describes the live intelligence portfolio
- `Experiment Evidence` accurately describes validated experiment outputs
- It avoids implying that one experiment registry represents all educational intelligence in Classio

## Next evolution

Later, `Experiment Evidence` can expand into a broader multi-experiment registry where each AI component has its own evidence lane. At that point, Classio can support:

- Per-component experiment catalogs
- Controlled model selection without Python edits
- Safer configuration management for approved models
- Stronger separation between production supervision and offline validation
