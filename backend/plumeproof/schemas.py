"""
PlumeProof API contract: every data shape that crosses a module or network boundary.

These Pydantic models are the single source of truth for the API. The TypeScript
mirror lives in ``frontend/src/types/api.ts``. If you change a model here, change it there too.

Vocabulary
----------
* **Hypothesis**: a candidate emission source ("waste_surface", "gas_collection", "flare").
* **Belief**: a probability for each hypothesis, ``{"waste_surface": 0.5, ...}``, summing to 1.
* **Action**: an investigation the agent can request (records request, OGI survey, ...).
* **Outcome**: what an action can return ("fault_found" / "no_fault" ...).
* **Likelihood**: P(outcome | hypothesis, action), the probability of seeing that outcome
  if that hypothesis were the true source.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# A belief is just a mapping hypothesis-id -> probability.
Belief = dict[str, float]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class CaseStatus(str, Enum):
    """Case lifecycle (PDF slide 12). Transitions are enforced in state_machine.py."""

    OPEN = "OPEN"
    SOURCE_ATTRIBUTION_PENDING = "SOURCE_ATTRIBUTION_PENDING"
    INVESTIGATION_REQUESTED = "INVESTIGATION_REQUESTED"
    REPAIR_REPORTED = "REPAIR_REPORTED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED_REDUCTION = "VERIFIED_REDUCTION"  # the only "closed" state
    INCONCLUSIVE = "INCONCLUSIVE"
    STILL_LEAKING = "STILL_LEAKING"
    RECURRING = "RECURRING"  # was verified/closed, then a later observation re-opened it


class ApprovalKind(str, Enum):
    """The four decision types that always need a human (PDF objective 4)."""

    SOURCE_ATTRIBUTION = "SOURCE_ATTRIBUTION"
    NOTIFICATION = "NOTIFICATION"
    FIELD_INVESTIGATION = "FIELD_INVESTIGATION"
    FINAL_CLOSURE = "FINAL_CLOSURE"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EDITED = "EDITED"  # approved with human edits to the proposed text
    REJECTED = "REJECTED"


class ActorType(str, Enum):
    AGENT = "agent"
    HUMAN = "human"
    SATELLITE = "satellite"
    SIMULATED = "simulated"  # simulated operator / inspector / measurement team


class DataLabel(str, Enum):
    """Honest provenance label shown on every audit event."""

    REAL_DATA = "REAL DATA"
    AGENT_ACTION = "AGENT ACTION"
    SIMULATED_EVENT = "SIMULATED EVENT"
    HUMAN_DECISION = "HUMAN DECISION"


class ChainStage(str, Enum):
    """Evidence chain: Observation → Hypothesis → Investigation → Finding → Repair → Verification."""

    OBSERVATION = "Observation"
    HYPOTHESIS = "Hypothesis"
    INVESTIGATION = "Investigation"
    FINDING = "Finding"
    REPAIR = "Repair"
    VERIFICATION = "Verification"


class Verdict(str, Enum):
    VERIFIED_REDUCTION = "VERIFIED_REDUCTION"
    INCONCLUSIVE = "INCONCLUSIVE"
    STILL_LEAKING = "STILL_LEAKING"
    NO_INDEPENDENT_EVIDENCE = "NO_INDEPENDENT_EVIDENCE"  # case stays VERIFICATION_PENDING


class ToolName(str, Enum):
    """The tools the agent acts through (PDF slide 8)."""

    QUERY_OBSERVATIONS = "query_observations"
    OVERLAY_FACILITY_ZONES = "overlay_facility_zones"
    RANK_ACTIONS = "rank_actions"
    DRAFT_NOTICE = "draft_notice"
    TRACK_DEADLINE = "track_deadline"
    EVALUATE_MEASUREMENT = "evaluate_measurement"


# ---------------------------------------------------------------------------
# Engine models (planner / Bayes)
# ---------------------------------------------------------------------------
class OutcomeSpec(BaseModel):
    """One possible result of an action, with its likelihood under each hypothesis."""

    id: str
    label: str
    likelihood: dict[str, float]  # P(this outcome | hypothesis, action)


class ActionSpec(BaseModel):
    """An investigative action in the catalogue (see config.ACTIONS)."""

    id: str
    label: str
    description: str
    cost_inr: float
    time_days: float
    resources: list[str] = Field(default_factory=list)  # e.g. ["ogi_inspector"]
    authorisation: Optional[str] = None  # e.g. "site_access_permit"
    unsafe_when: list[str] = Field(default_factory=list)  # e.g. ["landfill_fire"]
    requires_approval: bool = True
    approval_kind: Optional[ApprovalKind] = ApprovalKind.FIELD_INVESTIGATION
    is_field_inspection: bool = False  # counts towards "inspections" in the evaluation
    outcomes: list[OutcomeSpec]


class Constraints(BaseModel):
    """Operational constraints on a case. Violating actions are excluded *before* ranking."""

    unavailable_resources: list[str] = Field(default_factory=list)
    granted_authorisations: list[str] = Field(default_factory=lambda: ["site_access_permit"])
    safety_flags: list[str] = Field(default_factory=list)
    performed_actions: list[str] = Field(default_factory=list)  # done for the current hypothesis set


class OutcomePreview(BaseModel):
    """"If we take this action and see outcome y, here is what we'd believe"."""

    outcome_id: str
    label: str
    probability: float  # P(y) = Σ_h P(y|h,a) P(h)
    posterior: Belief  # P(h | y)
    entropy_after: float


class RankedAction(BaseModel):
    action_id: str
    label: str
    eig_bits: float
    cost_inr: float
    time_days: float
    effective_cost: float  # cost + λ·time
    score: float  # EIG / (cost + λ·time)
    score_per_10k: float  # score × 10,000 (readable units: bits per ₹10k-equivalent)
    gain_per_10k: Optional[float]  # EIG / cost × 10,000; None when cost == 0
    rank: int  # 1 = best
    outcomes: list[OutcomePreview]


class ExcludedAction(BaseModel):
    action_id: str
    label: str
    reason_codes: list[str]  # RESOURCE_UNAVAILABLE | AUTHORISATION_MISSING | SAFETY | ALREADY_PERFORMED
    reasons: list[str]  # human-readable
    eig_bits: float  # still computed, so the UI can show what was given up


class PlanResult(BaseModel):
    belief: Belief
    entropy_bits: float
    lam: float  # λ in ₹ per day
    ranked: list[RankedAction]
    excluded: list[ExcludedAction]
    recommended_action_id: Optional[str]
    explanation: str  # deterministic template explanation of the ranking


class BayesUpdate(BaseModel):
    action_id: str
    outcome_id: str
    prior: Belief
    posterior: Belief
    entropy_before: float
    entropy_after: float
    outcome_probability: float


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
class Measurement(BaseModel):
    id: str
    rate_kg_h: float
    uncertainty_kg_h: float  # half-width of the interval: [rate − u, rate + u]
    date: str  # ISO date (in-world)
    method: str  # e.g. "Carbon Mapper satellite", "Aerial survey", "Operator claim"
    independent: bool  # False for operator self-reports
    comparable_conditions: bool = True
    actor: ActorType = ActorType.SIMULATED
    label: DataLabel = DataLabel.SIMULATED_EVENT
    notes: str = ""


class VerificationRequest(BaseModel):
    pre: Measurement
    posts: list[Measurement] = Field(default_factory=list)


class VerificationResult(BaseModel):
    verdict: Verdict
    pre_rate: float
    pre_uncertainty: float
    pre_low: float
    pre_high: float
    post_rate: Optional[float] = None  # combined independent post estimate
    post_uncertainty: Optional[float] = None
    post_low: Optional[float] = None
    post_high: Optional[float] = None
    conflicting: bool = False
    measurements_used: list[str] = Field(default_factory=list)
    measurements_ignored: list[str] = Field(default_factory=list)  # non-independent ones
    rule: str  # the rule text, e.g. "post + u_post < pre − u_pre"
    reasons: list[str]
    recurrence_threshold_kg_h: Optional[float] = None  # set when VERIFIED_REDUCTION


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
class TransitionContext(BaseModel):
    actor: ActorType
    verification_verdict: Optional[Verdict] = None
    approval_granted: bool = False
    observation_above_threshold: bool = False


class TransitionDecision(BaseModel):
    allowed: bool  # True = the transition may happen now
    from_status: CaseStatus
    to_status: CaseStatus
    requires_approval: Optional[ApprovalKind] = None  # set if a human must approve first
    reason: str


class TransitionRequest(BaseModel):
    """Body of POST /api/cases/{id}/request-transition (used by humans, simulated operators and the LLM)."""

    to_status: CaseStatus
    actor: ActorType = ActorType.HUMAN
    actor_name: str = "Human reviewer"
    reason: str = ""
    requested_by_llm: bool = False


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------
class Observation(BaseModel):
    id: str
    case_id: Optional[str] = None
    facility_id: str
    date: str  # ISO date
    lat: float
    lng: float
    rate_kg_h: float
    uncertainty_kg_h: Optional[float] = None
    plume_label: str  # e.g. "Plume A"
    source: str  # e.g. "Carbon Mapper"
    label: DataLabel = DataLabel.REAL_DATA
    notes: str = ""


class Stakeholder(BaseModel):
    role: str  # "Responsible operator", "Municipal authority", "Regulator", "UN focal point"
    name: str
    contact: str
    responsibility: str
    label: DataLabel = DataLabel.SIMULATED_EVENT


class Deadline(BaseModel):
    id: str
    title: str
    due_date: str  # ISO date (in-world)
    status: Literal["open", "met", "overdue"] = "open"
    related_action: Optional[str] = None


class FacilityZone(BaseModel):
    id: str
    name: str
    hypothesis_id: str
    polygon: list[tuple[float, float]]  # [(lat, lng), ...]


class Facility(BaseModel):
    id: str
    name: str
    location: str
    lat: float
    lng: float
    boundary: list[tuple[float, float]]
    zones: list[FacilityZone]


class AuditEvent(BaseModel):
    id: str
    case_id: Optional[str]
    timestamp: str  # ISO datetime (wall clock)
    sim_date: Optional[str] = None  # in-world date of the event
    actor: ActorType
    actor_name: str
    type: str  # e.g. OBSERVATION_RECORDED, TOOL_CALL, BELIEF_UPDATED, TRANSITION_REJECTED ...
    label: DataLabel
    title: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)
    chain_stage: Optional[ChainStage] = None
    tool: Optional[ToolName] = None
    data: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str
    case_id: Optional[str]
    tool: ToolName
    timestamp: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    output_summary: str


class ApprovalItem(BaseModel):
    id: str
    case_id: str
    kind: ApprovalKind
    status: ApprovalStatus = ApprovalStatus.PENDING
    title: str
    summary: str
    proposed_text: str = ""
    edited_text: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)  # e.g. {"action_id": ...} or {"target_status": ...}
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    note: str = ""


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edited_text: Optional[str] = None
    note: str = ""
    decided_by: str = "Human reviewer"


class BeliefSnapshot(BaseModel):
    timestamp: str
    sim_date: Optional[str] = None
    belief: Belief
    entropy_bits: float
    reason: str


class Case(BaseModel):
    id: str
    facility_id: str
    title: str
    status: CaseStatus
    priority: Literal["Low", "Medium", "High", "Critical"]
    created_at: str
    sim_date: Optional[str] = None  # current in-world date of the case
    belief: Belief
    belief_history: list[BeliefSnapshot] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    lam: float = 1000.0
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    outstanding_questions: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    pre_measurement: Optional[Measurement] = None
    measurements: list[Measurement] = Field(default_factory=list)  # post-intervention
    verification: Optional[VerificationResult] = None
    attributed_source: Optional[str] = None
    repaired_source: Optional[str] = None
    recurrence_threshold_kg_h: Optional[float] = None
    reopen_count: int = 0
    summary: str = ""


class CaseSummary(BaseModel):
    id: str
    title: str
    facility_name: str
    status: CaseStatus
    priority: str
    latest_rate_kg_h: Optional[float]
    latest_obs_date: Optional[str]
    leading_hypothesis: str
    leading_probability: float
    pending_approvals: int
    lat: float
    lng: float


class CaseDetail(BaseModel):
    case: Case
    facility: Facility
    observations: list[Observation]
    pending_approvals: list[ApprovalItem]
    plan: Optional[PlanResult]


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
class Banner(BaseModel):
    kind: Literal["rejected", "verified", "reopened", "warning", "info"]
    title: str
    text: str


class ReplayStepInfo(BaseModel):
    index: int
    id: str
    title: str
    label: DataLabel


class ReplayFrame(BaseModel):
    """A complete, self-contained snapshot after one replay step (also used for the offline snapshot)."""

    step_index: int  # 0 = intro (nothing happened yet)
    total_steps: int
    step_id: str
    title: str
    narration: str
    label: DataLabel
    sim_date: Optional[str]
    case: Optional[CaseDetail]
    belief_before: Optional[Belief] = None
    belief_after: Optional[Belief] = None
    plan: Optional[PlanResult] = None
    plan_before: Optional[PlanResult] = None  # for re-rank comparisons (step 4)
    tool_calls: list[ToolCall] = Field(default_factory=list)  # tools called in this step
    new_events: list[AuditEvent] = Field(default_factory=list)
    timeline: list[AuditEvent] = Field(default_factory=list)  # full case timeline so far
    pending_approval: Optional[ApprovalItem] = None  # if set, the next step needs a human decision
    banner: Optional[Banner] = None
    verification: Optional[VerificationResult] = None
    highlight_observation_ids: list[str] = Field(default_factory=list)
    done: bool = False


class ReplayStepRequest(BaseModel):
    # When True and the current frame has a pending approval, the presenter's click on
    # Next/Play counts as the human "Approve" (logged as HUMAN DECISION, actor "Demo presenter").
    auto_approve: bool = True


# ---------------------------------------------------------------------------
# Map, what-if, LLM, meta
# ---------------------------------------------------------------------------
class Wind(BaseModel):
    from_deg: float  # meteorological convention: direction the wind blows FROM
    speed_m_s: float
    label: str
    illustrative: bool = True


class MapState(BaseModel):
    facility: Facility
    observations: list[Observation]
    cases: list[CaseSummary]
    wind: Wind


class WhatIfRequest(BaseModel):
    action_id: str
    outcome_id: str
    prior: Optional[Belief] = None  # default: config.DEFAULT_PRIOR


class WhatIfResult(BaseModel):
    update: BayesUpdate
    eig_bits: float
    outcomes: list[OutcomePreview]


class DraftRequest(BaseModel):
    kind: Literal["notice", "ranking_explanation", "case_summary"]
    lam: Optional[float] = None


class DraftResult(BaseModel):
    text: str
    mode: Literal["llm", "template"]
    model: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    llm_mode: Literal["llm", "template"]
    llm_model: Optional[str] = None


class HypothesisInfo(BaseModel):
    id: str
    label: str
    prior: float
    color: str


class MetaResponse(BaseModel):
    hypotheses: list[HypothesisInfo]
    actions: list[ActionSpec]
    verification_action: ActionSpec
    default_lambda: float
    attribution_threshold: float
    stats: dict[str, Any]  # e.g. {"mars_alerts": "5,000+", "response_rate_pct": 13, ...}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
PolicyId = Literal["A", "B", "C", "C_noplan"]


class PolicyMetrics(BaseModel):
    policy_id: PolicyId
    label: str
    description: str
    n_cases: int
    closed_cases: int
    false_closures: int  # closed without an independent verified reduction (or truth not reduced)
    false_closure_rate: float  # false_closures / n_cases
    resolved_cases: int  # true source correctly repaired (truth emission actually reduced)
    correct_attribution_rate: float
    inspections_total: int
    inspections_per_resolved: Optional[float]
    # Field inspections used to IDENTIFY THE SOURCE (excludes verification campaigns), mean per case.
    # This is the PDF objective-2 metric ("inspections required to identify the emission source").
    attribution_inspections_per_case: float = 0.0
    verification_inspections_total: int = 0
    cost_total_inr: float
    cost_per_resolved_inr: Optional[float]
    mean_days_to_stakeholder: Optional[float]
    stakeholder_assigned_rate: float
    traceability_pct: float  # % critical decisions with required evidence link + human approval
    mean_days_to_closure: Optional[float]


class ScenarioPolicyOutcome(BaseModel):
    final_status: str
    closed: bool
    false_closure: bool
    resolved: bool
    attributed_source: Optional[str]
    inspections: int
    attribution_inspections: int = 0
    cost_inr: float
    days_to_stakeholder: Optional[float]
    days_elapsed: float
    actions: list[str]
    critical_decisions: int
    traceable_decisions: int


class ScenarioResult(BaseModel):
    scenario_id: str
    tags: list[str]  # ambiguous, missing_records, inspector_unavailable, conflicting, unsupported_claim, recurrence
    true_source: str
    description: str
    outcomes: dict[str, ScenarioPolicyOutcome]  # keyed by PolicyId


class SensitivityResult(BaseModel):
    n_draws: int
    perturbation: float  # 0.2 = ±20%
    top_action_stability_pct: float  # % of draws where the top-ranked action is unchanged
    mean_kendall_tau: float  # rank agreement with the nominal ranking (1 = identical)
    top_action_counts: dict[str, int]
    c_false_closures_perturbed: int  # C run on worlds with perturbed true likelihoods
    c_inspections_per_resolved_perturbed: Optional[float]


class EvaluationReport(BaseModel):
    generated_at: str
    seed: int
    n_scenarios: int
    policies: list[PolicyMetrics]
    scenarios: list[ScenarioResult]
    sensitivity: SensitivityResult
    definitions: dict[str, str]
    notes: list[str]


class EvaluateRequest(BaseModel):
    seed: int = 2026
    n_scenarios: int = 25
