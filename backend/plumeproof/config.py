"""
Demonstration parameters for PlumeProof.

Every number here is an ILLUSTRATIVE value (see docs/ASSUMPTIONS.md). Change it here and the
whole system follows: the planner, the replay, the evaluation and the UI all read from this file.

The likelihood tables were chosen so that the *computed* expected information gains and
posteriors reproduce the worked example on slide 10 of RisaavNivaran.pdf:

    records request ≈ 0.50 bits, OGI ≈ 0.41, ground survey ≈ 0.91, satellite wait ≈ 0
    P(fault found) ≈ 0.43 → posterior gas 65% / flare 29% / waste 6%
    no fault             → waste ≈ 84%

The test ``tests/test_worked_example.py`` checks this.
"""
from __future__ import annotations

from .schemas import ActionSpec, ApprovalKind, HypothesisInfo, OutcomeSpec

# ---------------------------------------------------------------------------
# Hypotheses (PDF slide 9) and the prior P(h)
# ---------------------------------------------------------------------------
WASTE = "waste_surface"
GAS = "gas_collection"
FLARE = "flare"

HYPOTHESES: list[HypothesisInfo] = [
    HypothesisInfo(id=WASTE, label="Exposed waste surface", prior=0.50, color="#f59e0b"),
    HypothesisInfo(id=GAS, label="Gas-collection system", prior=0.35, color="#10b981"),
    HypothesisInfo(id=FLARE, label="Flare system", prior=0.15, color="#6366f1"),
]
HYPOTHESIS_IDS: list[str] = [h.id for h in HYPOTHESES]
HYPOTHESIS_LABELS: dict[str, str] = {h.id: h.label for h in HYPOTHESES}
DEFAULT_PRIOR: dict[str, float] = {h.id: h.prior for h in HYPOTHESES}  # H = 1.4406 bits

# ---------------------------------------------------------------------------
# Planner parameters
# ---------------------------------------------------------------------------
DEFAULT_LAMBDA: float = 1000.0  # λ: rupees per day of delay, in score = EIG / (cost + λ·time)
ATTRIBUTION_THRESHOLD: float = 0.60  # propose attribution once max posterior ≥ this
MIN_USEFUL_EIG: float = 0.05  # bits; below this an action is "not worth it"

# ---------------------------------------------------------------------------
# Verification parameters
# ---------------------------------------------------------------------------
MIN_RECURRENCE_KG_H: float = 100.0  # floor for the recurrence threshold
# After a repair of source X fails verification (STILL_LEAKING), apply this likelihood:
#   P(no reduction | h = X) = REPAIR_FAILED_IF_TARGET, P(no reduction | h ≠ X) = REPAIR_FAILED_IF_OTHER
REPAIR_FAILED_IF_TARGET: float = 0.15
REPAIR_FAILED_IF_OTHER: float = 0.95


def _binary(id_yes: str, label_yes: str, id_no: str, label_no: str, p_yes: dict[str, float]) -> list[OutcomeSpec]:
    """Build a two-outcome likelihood table from P(yes | h); P(no | h) = 1 − P(yes | h)."""
    return [
        OutcomeSpec(id=id_yes, label=label_yes, likelihood=dict(p_yes)),
        OutcomeSpec(id=id_no, label=label_no, likelihood={h: round(1.0 - p, 6) for h, p in p_yes.items()}),
    ]


# ---------------------------------------------------------------------------
# Action catalogue with likelihood tables P(y | h, a)
# ---------------------------------------------------------------------------
ACTIONS: list[ActionSpec] = [
    ActionSpec(
        id="records_request",
        label="Request flare and gas-collection records",
        description="Ask the operator for flare uptime logs and gas-collection well/pipe maintenance records.",
        cost_inr=2_000,
        time_days=1,
        requires_approval=True,
        approval_kind=ApprovalKind.NOTIFICATION,  # it is an official request to the stakeholder
        is_field_inspection=False,
        outcomes=_binary(
            "fault_found", "Records show a gas-system fault",
            "no_fault", "Records show no fault",
            # Records reveal faults in engineered systems, rarely anything about the open waste surface.
            {WASTE: 0.05, GAS: 0.805, FLARE: 0.84},
        ),
    ),
    ActionSpec(
        id="ogi_survey",
        label="Gas-imaging (OGI) survey of the gas-collection system",
        description="Optical gas imaging camera survey of wells, headers and the flare station.",
        cost_inr=25_000,
        time_days=2,
        resources=["ogi_inspector"],
        unsafe_when=["landfill_fire"],
        requires_approval=True,
        approval_kind=ApprovalKind.FIELD_INVESTIGATION,
        is_field_inspection=True,
        outcomes=_binary(
            "leak_detected", "OGI camera sees a leak",
            "no_leak", "No leak visible",
            {WASTE: 0.12, GAS: 0.90, FLARE: 0.45},
        ),
    ),
    ActionSpec(
        id="ground_survey",
        label="Comprehensive ground-level survey",
        description="Walk-over surface methane survey of the whole site to localise the hotspot.",
        cost_inr=60_000,
        time_days=5,
        resources=["field_team"],
        authorisation="site_access_permit",
        unsafe_when=["landfill_fire"],
        requires_approval=True,
        approval_kind=ApprovalKind.FIELD_INVESTIGATION,
        is_field_inspection=True,
        outcomes=[
            OutcomeSpec(id="hotspot_waste", label="Hotspot on the waste surface",
                        likelihood={WASTE: 0.90, GAS: 0.05, FLARE: 0.05}),
            OutcomeSpec(id="hotspot_gas", label="Hotspot at gas-collection infrastructure",
                        likelihood={WASTE: 0.05, GAS: 0.90, FLARE: 0.05}),
            OutcomeSpec(id="hotspot_flare", label="Hotspot at the flare station",
                        likelihood={WASTE: 0.05, GAS: 0.05, FLARE: 0.90}),
        ],
    ),
    ActionSpec(
        id="satellite_wait",
        label="Await the next satellite observation",
        description="Do nothing and wait for the next satellite pass (~30 days).",
        cost_inr=0,
        time_days=30,
        requires_approval=False,
        approval_kind=None,
        is_field_inspection=False,
        # A revisit shows *whether* it still leaks, not *which component*: identical likelihoods → EIG = 0.
        outcomes=_binary(
            "plume_persists", "Plume still visible",
            "no_plume", "No plume detected",
            {WASTE: 0.70, GAS: 0.70, FLARE: 0.70},
        ),
    ),
]
ACTIONS_BY_ID: dict[str, ActionSpec] = {a.id: a for a in ACTIONS}

# Used only in the verification phase (not a source-attribution action).
VERIFICATION_ACTION = ActionSpec(
    id="independent_measurement",
    label="Independent post-intervention measurement",
    description="Independent measurement campaign (aerial / ground) under comparable conditions.",
    cost_inr=40_000,
    time_days=3,
    resources=["measurement_team"],
    authorisation="site_access_permit",
    requires_approval=True,
    approval_kind=ApprovalKind.FIELD_INVESTIGATION,
    is_field_inspection=True,
    outcomes=[],
)

# ---------------------------------------------------------------------------
# Headline statistics shown on the landing page (PDF slides 2–3)
# ---------------------------------------------------------------------------
STATS: dict[str, object] = {
    "mars_alerts": "5,000+",
    "countries": 33,
    "response_rate_pct": 13,
    "target_response_rate_pct": 80,
    "verified_mitigations": "40+",
    "methane_share_of_warming_pct": 30,
    "gwp20": 80,
}
