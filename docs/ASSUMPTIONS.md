# Assumptions

Every number below is an **illustrative demonstration value**, as the proposal says: *"Costs and probabilities are illustrative demonstration values. They will be calibrated with an environmental engineering expert."* Each one lives in `backend/plumeproof/config.py`. Change it there and the whole app follows.

## 1. Hypotheses and prior
| Hypothesis | id | Prior |
|---|---|---|
| Exposed waste surface | `waste_surface` | 0.50 |
| Gas-collection system | `gas_collection` | 0.35 |
| Flare system | `flare` | 0.15 |

Entropy H = −Σ p log₂ p = **1.4406 bits** (PDF: 1.44).
The PDF says the prior is "derived from geospatial evidence (plume origin, wind, upwind facility zones)". In this prototype, the `overlay_facility_zones` tool reports which illustrative zones the plumes fall in, but the prior itself is fixed at the PDF values. A data-driven geospatial prior is future work.

## 2. Likelihood tables P(y | h, a)
These were chosen with a grid search (see the git history / CLAUDE.md) so that the computed results match the PDF worked example. They are *not* hard-coded outputs: the app computes every EIG and posterior from them.

| Action | Outcome | waste | gas | flare |
|---|---|---|---|---|
| Records request (flare + gas-collection logs) | fault_found | 0.05 | 0.805 | 0.84 |
| | no_fault | 0.95 | 0.195 | 0.16 |
| OGI survey of gas-collection system | leak_detected | 0.12 | 0.90 | 0.45 |
| | no_leak | 0.88 | 0.10 | 0.55 |
| Comprehensive ground survey | hotspot_waste | 0.90 | 0.05 | 0.05 |
| | hotspot_gas | 0.05 | 0.90 | 0.05 |
| | hotspot_flare | 0.05 | 0.05 | 0.90 |
| Await next satellite pass | plume_persists | 0.70 | 0.70 | 0.70 |
| | no_plume | 0.30 | 0.30 | 0.30 |

Physical reasoning: operational records reveal faults in *engineered* systems (gas collection, flare) but say little about the open waste surface. An OGI camera pointed at the gas-collection field sees leaks there well, sees an unlit or poorly combusting flare about half the time, and occasionally picks up surface emissions. A ground survey localises the hotspot with 90% accuracy. A satellite revisit confirms *that* emissions continue but cannot tell which component is responsible, so its likelihoods are identical across hypotheses and its EIG is exactly 0.

### Worked-example reproduction (computed by `tests/test_worked_example.py`)
| Quantity | PDF | Computed | Gap |
|---|---|---|---|
| EIG records | 0.50 | 0.499 | −0.001 |
| EIG OGI | 0.41 | 0.413 | +0.003 |
| EIG ground survey | 0.91 | 0.914 | +0.004 |
| EIG satellite wait | ≈0 | 0.000 | 0 |
| P(fault found) | 0.43 | 0.433 | +0.003 |
| Posterior after fault (gas/flare/waste) | 65/29/6 | 65.1/29.1/5.8 | <0.3 pp |
| Waste posterior after no fault | 84% | 83.7% | −0.3 pp |

**Documented gap:** the PDF's numbers cannot all be matched exactly at the same time. The fault posterior's waste share (6%) and the no-fault waste share (84%) pull P(fault | waste) in opposite directions. Our choice keeps every value within 0.5 percentage points (0.005 bits).

## 3. Costs, times and λ
| Action | Cost (₹) | Time (days) | Resources | Authorisation | Unsafe when |
|---|---|---|---|---|---|
| Records request | 2,000 | 1 | none | none | none |
| OGI survey | 25,000 | 2 | `ogi_inspector` | none | `landfill_fire` |
| Ground survey | 60,000 | 5 | `field_team` | `site_access_permit` | `landfill_fire` |
| Satellite wait | 0 | 30 | none | none | none |
| Independent post-repair measurement (verification only) | 40,000 | 3 | `measurement_team` | `site_access_permit` | none |

- **λ = ₹1,000 per day** by default: the "value of one day of delay". It is adjustable with the Planner slider (0–20,000). With the default, the ranking is records > OGI > ground > satellite, the same order as the PDF's gain-per-₹10k column.
- **score(a) = EIG / (cost + λ·time)**. The UI shows it as "bits per ₹10k-equivalent" (score × 10,000) to keep the numbers readable.
- If cost + λ·time = 0 (satellite wait with λ = 0), the score is defined as 0, because there is no information to buy.
- An action that has already been performed for the current hypothesis set is excluded with the reason ALREADY_PERFORMED. Repeating a records request returns the same records.

## 4. Verification rule
- pre = pre-intervention rate ± u_pre; post = post-intervention rate ± u_post. u is treated as an interval half-width.
- **No independent measurement** (for example, only an operator claim) gives NO_INDEPENDENT_EVIDENCE, and the case stays VERIFICATION_PENDING.
- **Conflicting measurements** (two independent post measurements whose intervals do not overlap) give INCONCLUSIVE. Both measurements are kept.
- **Non-comparable conditions** give INCONCLUSIVE.
- Several consistent independent posts are combined with an inverse-variance weighted mean: x̄ = Σ(xᵢ/uᵢ²)/Σ(1/uᵢ²), u = 1/√Σ(1/uᵢ²).
- **VERIFIED_REDUCTION** if post + u_post < pre − u_pre.
- **STILL_LEAKING** if the central post estimate ≥ pre − u_pre: there is no demonstrable reduction.
- Otherwise the intervals overlap, which gives **INCONCLUSIVE**.
- **Recurrence threshold** after a verified reduction = max(post + u_post, 100 kg/h). Any later observation above it automatically reopens the case as RECURRING.

## 5. Kanjur replay data
- **Real** (Carbon Mapper, PDF ref [2]): 9 Feb 2025, plume A ~1,600 kg/h and plume B ~136 kg/h; 3 Apr 2026, two plumes, ~3,300 kg/h combined. The individual 2026 plume split is not public, so it is shown as one combined marker.
- Plume marker *positions* inside the landfill are approximate and illustrative. Landfill centre ≈ 19.13 N, 72.93 E.
- **Pre-intervention uncertainty**: ±25% of the combined 1,736 kg/h, so ±434 kg/h. This is an assumption; Carbon Mapper publishes per-plume uncertainties, but we did not ingest them.
- **Simulated**: stakeholder mapping (BMC Solid Waste Management Dept, landfill operator, MPCB), OGI inspector unavailable, records content ("fault found"), the operator's repair claim, the follow-up independent measurement (610 ± 150 kg/h under comparable conditions), and every human approval in the replay (the presenter clicks approve).
- Facility zone polygons (active waste face, gas-collection field, flare station) are illustrative, not surveyed boundaries.
- The wind arrow is illustrative, not taken from meteorological data.
- Mandar's `sample_observations.{csv,json}` are sample upload files. They are **not** real observations and are labelled SIMULATED in the ingestion page.

## 6. Agent behaviour
- Attribution threshold: the agent proposes a source attribution once the leading hypothesis has posterior ≥ 0.60 (or no remaining action has EIG ≥ 0.05 bits).
- If verification returns STILL_LEAKING after a repair of source X, the agent applies a "repair-failed" likelihood: P(no reduction | h = X) = 0.15 and P(no reduction | h ≠ X) = 0.95. It then re-plans.
- In the replay, LLM drafting is not used, so steps stay instant and deterministic. Claude (if a key is set) is used for the on-demand buttons: Explain ranking, Draft notice and Case summary.

## 7. Evaluation
See docs/EVALUATION.md for the scenario generator parameters, the policy definitions and the metric definitions (the evaluation agent appends them here as well).

## 8. Infrastructure
- SQLite instead of PostgreSQL/PostGIS. The schema is simple JSON-in-SQLite. PostGIS and GeoPandas are future work.
- A hand-written orchestrator instead of LangGraph: same explicit state-machine semantics, fewer dependencies, easier to test.
- Map tiles come from OpenStreetMap and need internet. Everything else works offline.
- The MQ-4 sensor from the proposal is not calibrated and is **not** used for verification.
