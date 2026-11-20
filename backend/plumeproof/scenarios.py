"""
Evaluation simulator: 25 seeded scenarios, three policies, an ablation and a sensitivity analysis.

EVERYTHING HERE IS SIMULATED. Each scenario has a hidden "true" emission source. The *world*
answers investigations by sampling from the likelihood tables P(y | true source, action) in
config.py. Each policy only sees those answers, never the hidden truth. Metrics compare what the
policy concluded or did with the hidden truth.

Policies (PDF slide 13):
  A        alert-only: one automated alert; closes the case when the operator claims a repair.
  B        fixed checklist: records → OGI → ground survey for every case; closes on the operator's
           claim after a checklist sign-off.
  C        PlumeProof: EIG-ranked planning (planner.rank_actions), human approvals, evidence-gated
           verification (verification.evaluate_verification) and the lifecycle state machine.
  C_noplan ablation: C with the Evidence Planner disabled (cheapest available action first).

Fairness: for each scenario, the world's answer to each action and the measurement noise are
sampled ONCE, up front. Every policy therefore faces exactly the same world.

Run:  ``python -m plumeproof.scenarios``  → writes docs/EVALUATION.md and docs/evaluation_results.csv
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import bayes, config, planner, verification
from .schemas import (
    ActionSpec,
    ActorType,
    CaseStatus,
    Constraints,
    DataLabel,
    EvaluationReport,
    Measurement,
    PolicyMetrics,
    ScenarioPolicyOutcome,
    ScenarioResult,
    SensitivityResult,
    TransitionContext,
    Verdict,
)
from .state_machine import validate_transition

S = CaseStatus

TAGS = [
    "ambiguous",
    "missing_records",
    "inspector_unavailable",
    "conflicting_measurements",
    "unsupported_claim",
    "recurrence",
]

# ---------------------------------------------------------------------------
# Simulation parameters (all illustrative; documented in docs/ASSUMPTIONS.md §7)
# ---------------------------------------------------------------------------
APPROVAL_DELAY_DAYS = 1  # a human approval takes one day
ALERT_FORWARD_DELAY_DAYS = 30  # A: national focal point forwards the alert to the operator
CHECKLIST_STAKEHOLDER_DAYS = 7  # B: manual lookup of the responsible operator
OVERLAY_STAKEHOLDER_DAYS = 1  # C: overlay_facility_zones + 1-day approval
RECORDS_DEADLINE_DAYS = 7  # missing records: the deadline passes with no response
CHECKLIST_RETRY_WAIT_DAYS = 14  # B: waits this long for an unavailable resource, then skips
REPAIR_DAYS = 14  # operator repair work after notification
REDUCED_FRACTION = 0.25  # effective repair leaves 25% of E0
NOT_REDUCED_FRACTION = 1.0  # ineffective repair leaves the emission unchanged
TRUTH_REDUCED_IF_BELOW = 0.5  # "truth actually reduced" ⇔ true post < 0.5·E0
PRE_UNCERTAINTY_FRACTION = 0.25  # satellite pre-intervention uncertainty ±25%
MEAS_REL_U, MEAS_ABS_U = 0.15, 50.0  # independent measurement u = 0.15·truth + 50 kg/h
MEAS_NOISE_BOUND = 0.8  # bounded noise: reported value within ±0.8·u of the truth
CONFLICT_BIAS = 0.6  # conflicting campaign: second instrument reads ≥ +60% high
RECURRENCE_AFTER_DAYS = 300  # recurrence: emission returns this long after closure
MAX_REPAIR_LOOPS = 3
MAX_MEASUREMENT_CAMPAIGNS = 3
HORIZON_DAYS = 365
AMBIGUOUS_PRIOR = {config.WASTE: 0.36, config.GAS: 0.34, config.FLARE: 0.30}
NO_RESPONSE = "NO_RESPONSE"

POLICY_LABELS = {
    "A": "A: Alert-only",
    "B": "B: Fixed checklist",
    "C": "C: PlumeProof",
    "C_noplan": "C-ablation: planner disabled",
}
POLICY_DESCRIPTIONS = {
    "A": "Sends one automated alert to the national focal point; no investigation; marks the case "
         "resolved as soon as the operator claims a repair.",
    "B": "Runs the same sequence for every case (records → OGI → ground survey), attributes to the most "
         "probable source, notifies, and closes on the operator's repair claim after a checklist sign-off.",
    "C": "Ranks investigations by EIG/(cost+λ·time), stops when one source reaches 60%, gets human approvals, "
         "rejects claim-only closure, requires an independent measurement, re-plans after failed repairs, "
         "and reopens on recurrence.",
    "C_noplan": "Identical to C but the Evidence Planner is replaced by 'cheapest available action first'.",
}


# ---------------------------------------------------------------------------
# Scenario model
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    scenario_id: str
    tags: list[str]
    true_source: str
    agent_prior: dict[str, float]
    e0_kg_h: float
    world_outcomes: dict[str, str]  # action_id -> outcome the world returns (pre-sampled)
    noise: list[float]  # pre-sampled uniform(−1, 1) draws for measurement campaigns
    description: str = ""

    def has(self, tag: str) -> bool:
        return tag in self.tags


def _sample_outcome(action: ActionSpec, true_source: str, rng: random.Random) -> str:
    """Draw y ~ P(y | true_source, action)."""
    r = rng.random()
    acc = 0.0
    for o in action.outcomes:
        acc += o.likelihood[true_source]
        if r < acc:
            return o.id
    return action.outcomes[-1].id


def _sample_from(dist: dict[str, float], rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for k, p in dist.items():
        acc += p
        if r < acc:
            return k
    return list(dist)[-1]


def _assign_tags(n: int, rng: random.Random) -> list[list[str]]:
    """Every tag appears in several scenarios; a few scenarios are 'plain' (no tag)."""
    idx = list(range(n))
    rng.shuffle(idx)
    n_plain = max(1, round(n * 0.16))  # 4 of 25
    plain, tagged = idx[:n_plain], idx[n_plain:]
    per_tag = max(1, round(n * 0.2))  # 5 of 25
    tags: list[list[str]] = [[] for _ in range(n)]
    for t in TAGS:
        for i in rng.sample(tagged, min(per_tag, len(tagged))):
            tags[i].append(t)
    for i in tagged:
        if not tags[i]:
            tags[i].append(rng.choice(TAGS))
    _ = plain
    return [sorted(t, key=TAGS.index) for t in tags]


def generate_scenarios(seed: int = 2026, n: int = 25,
                       world_actions: Optional[Sequence[ActionSpec]] = None) -> list[Scenario]:
    """
    Build ``n`` seeded scenarios. ``world_actions`` lets the sensitivity analysis sample world
    outcomes from *perturbed* likelihoods while agents keep the nominal ones.
    """
    master = random.Random(seed)
    tag_lists = _assign_tags(n, master)
    acts = list(world_actions) if world_actions is not None else config.ACTIONS
    scenarios: list[Scenario] = []
    for i in range(n):
        rng = random.Random(seed * 1000 + i)
        tags = tag_lists[i]
        if "ambiguous" in tags:
            prior = dict(AMBIGUOUS_PRIOR)
            true_source = rng.choice(config.HYPOTHESIS_IDS)
        else:
            prior = dict(config.DEFAULT_PRIOR)
            true_source = _sample_from(config.DEFAULT_PRIOR, rng)
        e0 = float(round(rng.uniform(600, 3500), -1))
        outcomes = {a.id: _sample_outcome(a, true_source, rng) for a in acts}
        noise = [rng.uniform(-1.0, 1.0) for _ in range(16)]
        desc = (f"True source {config.HYPOTHESIS_LABELS[true_source]}, E0 ≈ {e0:,.0f} kg/h"
                + (f"; {', '.join(t.replace('_', ' ') for t in tags)}" if tags else "; plain case"))
        scenarios.append(Scenario(f"S{i + 1:02d}", tags, true_source, prior, e0, outcomes, noise, desc))
    return scenarios


# ---------------------------------------------------------------------------
# Policy run bookkeeping
# ---------------------------------------------------------------------------
@dataclass
class Decision:
    id: str
    kind: str  # investigation | attribution | notification | closure
    evidence_ids: list[str]
    approved_by: Optional[str]
    day: float


@dataclass
class PolicyRun:
    policy_id: str
    scenario: Scenario
    day: float = 0.0
    cost: float = 0.0
    inspections: int = 0
    attribution_inspections: int = 0  # field inspections used to identify the source (excl. verification)
    actions: list[str] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    transitions: list[tuple[CaseStatus, CaseStatus, TransitionContext]] = field(default_factory=list)
    status: CaseStatus = S.OPEN
    days_to_stakeholder: Optional[float] = None
    attributed_source: Optional[str] = None
    true_emission: float = 0.0
    closed_ever: bool = False
    closure_day: Optional[float] = None
    closure_evidence_ok: bool = False
    truth_reduced_at_closure: bool = False
    resolved: bool = False
    reopened: bool = False
    _noise_i: int = 0

    def next_noise(self) -> float:
        v = self.scenario.noise[self._noise_i % len(self.scenario.noise)]
        self._noise_i += 1
        return v

    def decide(self, kind: str, evidence: list[str], approved_by: Optional[str]) -> Decision:
        d = Decision(f"{kind.upper()[:5]}-{len(self.decisions) + 1}", kind, list(evidence), approved_by, self.day)
        self.decisions.append(d)
        return d

    def transition(self, to: CaseStatus, actor: ActorType, **ctx_kwargs) -> None:
        """Every status change of C goes through the real state machine. A refusal is a bug → raise."""
        ctx = TransitionContext(actor=actor, **ctx_kwargs)
        decision = validate_transition(self.status, to, ctx)
        if not decision.allowed:
            raise RuntimeError(f"[{self.policy_id}/{self.scenario.scenario_id}] forbidden transition "
                               f"{self.status.value} → {to.value}: {decision.reason}")
        self.transitions.append((self.status, to, ctx))
        self.status = to


OBS_ID = "OBS-0"
REQUIRED_EVIDENCE_PREFIX = {
    "investigation": "OBS-",
    "attribution": "FIND-",
    "notification": "ATTRI-",
    "closure": "VERDICT-VR",
}


def is_traceable(d: Decision) -> bool:
    """A critical decision is traceable iff it links the evidence its kind requires AND has a human approval."""
    prefix = REQUIRED_EVIDENCE_PREFIX[d.kind]
    return d.approved_by is not None and any(e.startswith(prefix) for e in d.evidence_ids)


def _repair(run: PolicyRun, target: str, claim_number: int) -> None:
    """The operator repairs ``target`` and files a repair claim. Effective only if it is the true source.

    ``unsupported_claim`` scenarios: the operator's FIRST claim is unsupported (nothing effective done).
    """
    sc = run.scenario
    run.day += REPAIR_DAYS
    effective = target == sc.true_source and not (sc.has("unsupported_claim") and claim_number == 1)
    run.true_emission = sc.e0_kg_h * (REDUCED_FRACTION if effective else NOT_REDUCED_FRACTION)
    run.actions.append(f"operator_repair:{target}:{'effective' if effective else 'ineffective'}")
    if effective:
        run.resolved = True


def _truth_reduced(run: PolicyRun) -> bool:
    return run.true_emission < TRUTH_REDUCED_IF_BELOW * run.scenario.e0_kg_h


def _execute_investigation(run: PolicyRun, action: ActionSpec, belief: dict[str, float],
                           human_approval: bool) -> tuple[dict[str, float], Optional[str]]:
    """Request approval (if needed), pay cost and time, read the world's answer and update beliefs."""
    if action.requires_approval:
        run.decide("investigation", [OBS_ID], "Human reviewer" if human_approval else None)
        run.day += APPROVAL_DELAY_DAYS
    run.cost += action.cost_inr
    if action.is_field_inspection:
        run.inspections += 1
        run.attribution_inspections += 1
    if action.id == "records_request" and run.scenario.has("missing_records"):
        run.day += RECORDS_DEADLINE_DAYS  # track_deadline: deadline missed, no belief update
        run.actions.append(f"{action.id}:{NO_RESPONSE}")
        return belief, None
    run.day += action.time_days
    outcome = run.scenario.world_outcomes[action.id]
    upd = bayes.update_with_outcome(belief, action, outcome)
    run.actions.append(f"{action.id}:{outcome}")
    return upd.posterior, f"FIND-{action.id}"


# ---------------------------------------------------------------------------
# Policy A: alert-only
# ---------------------------------------------------------------------------
def run_policy_a(sc: Scenario) -> PolicyRun:
    run = PolicyRun("A", sc, true_emission=sc.e0_kg_h)
    run.decide("notification", [OBS_ID], None)  # automated alert, no attribution behind it
    run.actions.append("automated_alert:national_focal_point")
    run.day += ALERT_FORWARD_DELAY_DAYS
    run.days_to_stakeholder = run.day
    guess = max(sc.agent_prior, key=sc.agent_prior.get)  # the operator repairs its own best guess
    run.attributed_source = None
    _repair(run, guess, claim_number=1)
    run.decide("closure", ["CLAIM-1"], None)  # resolved on the claim alone
    run.actions.append("closed_on_operator_claim")
    run.status = S.VERIFIED_REDUCTION  # A has no state machine; it simply marks "resolved"
    run.closed_ever, run.closure_day = True, run.day
    run.closure_evidence_ok = False
    run.truth_reduced_at_closure = _truth_reduced(run)
    return run


# ---------------------------------------------------------------------------
# Policy B: fixed checklist
# ---------------------------------------------------------------------------
CHECKLIST = ["records_request", "ogi_survey", "ground_survey"]


def run_policy_b(sc: Scenario) -> PolicyRun:
    run = PolicyRun("B", sc, true_emission=sc.e0_kg_h)
    run.day += CHECKLIST_STAKEHOLDER_DAYS
    run.days_to_stakeholder = run.day
    unavailable = {"ogi_inspector"} if sc.has("inspector_unavailable") else set()
    belief = dict(sc.agent_prior)
    findings: list[str] = []
    for aid in CHECKLIST:
        action = config.ACTIONS_BY_ID[aid]
        if any(r in unavailable for r in action.resources):
            run.day += CHECKLIST_RETRY_WAIT_DAYS  # wait, retry, still unavailable → skip
            run.actions.append(f"{aid}:SKIPPED_RESOURCE_UNAVAILABLE")
            continue
        belief, fid = _execute_investigation(run, action, belief, human_approval=True)
        if fid:
            findings.append(fid)
    run.attributed_source = max(belief, key=belief.get)
    attr = run.decide("attribution", findings, "Checklist sign-off")
    run.day += APPROVAL_DELAY_DAYS
    run.decide("notification", [f"ATTRI-{attr.id}"], "Checklist sign-off")
    run.day += APPROVAL_DELAY_DAYS
    _repair(run, run.attributed_source, claim_number=1)
    run.decide("closure", ["CLAIM-1"], "Checklist sign-off")  # human sign-off, but no measurement
    run.actions.append("closed_on_operator_claim")
    run.status = S.VERIFIED_REDUCTION
    run.closed_ever, run.closure_day = True, run.day
    run.closure_evidence_ok = False
    run.truth_reduced_at_closure = _truth_reduced(run)
    return run


# ---------------------------------------------------------------------------
# Policy C (and its ablation): PlumeProof
# ---------------------------------------------------------------------------
Chooser = Callable[[dict[str, float], Constraints], Optional[ActionSpec]]


def choose_by_planner(belief: dict[str, float], constraints: Constraints) -> Optional[ActionSpec]:
    """C: the Evidence Planner's top-ranked action, provided it is worth at least MIN_USEFUL_EIG bits."""
    plan = planner.rank_actions(belief, config.ACTIONS, constraints, config.DEFAULT_LAMBDA)
    useful = [r for r in plan.ranked if r.eig_bits >= config.MIN_USEFUL_EIG]
    return config.ACTIONS_BY_ID[useful[0].action_id] if useful else None


def choose_cheapest(belief: dict[str, float], constraints: Constraints) -> Optional[ActionSpec]:
    """Ablation: planner disabled, so pick the cheapest allowed action (ties broken by time).

    The agent loop keeps the same stopping rule as C (stop when no allowed action is worth
    MIN_USEFUL_EIG bits). Only the *choice* of action is changed.
    """
    plan = planner.rank_actions(belief, config.ACTIONS, constraints, config.DEFAULT_LAMBDA)
    if not any(r.eig_bits >= config.MIN_USEFUL_EIG for r in plan.ranked):
        return None
    allowed = [config.ACTIONS_BY_ID[r.action_id] for r in plan.ranked]
    allowed.sort(key=lambda a: (a.cost_inr, a.time_days))
    return allowed[0]


def _measurement_campaign(run: PolicyRun, campaign: int) -> list[Measurement]:
    """Independent post-intervention measurement(s). Bounded noise: |reported − truth| ≤ 0.8·u."""
    sc = run.scenario
    va = config.VERIFICATION_ACTION
    run.decide("investigation", [OBS_ID], "Human reviewer")
    run.day += APPROVAL_DELAY_DAYS + va.time_days
    run.cost += va.cost_inr
    run.inspections += 1
    truth = run.true_emission
    u = MEAS_REL_U * truth + MEAS_ABS_U
    m1 = Measurement(id=f"M{campaign}a", rate_kg_h=max(0.0, truth + MEAS_NOISE_BOUND * u * run.next_noise()),
                     uncertainty_kg_h=u, date=f"day {run.day:.0f}", method="Independent survey (simulated)",
                     independent=True, comparable_conditions=True, actor=ActorType.SIMULATED,
                     label=DataLabel.SIMULATED_EVENT)
    posts = [m1]
    if sc.has("conflicting_measurements") and campaign == 1:
        # A second instrument reads high (e.g. downwind of another source). Push until the intervals are disjoint.
        v2 = truth * (1 + CONFLICT_BIAS)
        while True:
            u2 = MEAS_REL_U * v2 + MEAS_ABS_U
            if v2 - u2 > m1.rate_kg_h + m1.uncertainty_kg_h:
                break
            v2 *= 1.2
        posts.append(Measurement(id=f"M{campaign}b", rate_kg_h=v2, uncertainty_kg_h=u2, date=m1.date,
                                 method="Second independent instrument (simulated)", independent=True,
                                 comparable_conditions=True, actor=ActorType.SIMULATED,
                                 label=DataLabel.SIMULATED_EVENT))
    run.actions.append(f"independent_measurement#{campaign}:" + ",".join(f"{m.rate_kg_h:.0f}±{m.uncertainty_kg_h:.0f}" for m in posts))
    return posts


def run_policy_c(sc: Scenario, chooser: Chooser = choose_by_planner, policy_id: str = "C") -> PolicyRun:
    run = PolicyRun(policy_id, sc, true_emission=sc.e0_kg_h)
    run.transition(S.SOURCE_ATTRIBUTION_PENDING, ActorType.AGENT)
    # Stakeholder resolver: overlay_facility_zones + human approval → accountable operator assigned on day 1.
    run.day += OVERLAY_STAKEHOLDER_DAYS
    run.days_to_stakeholder = run.day
    constraints = Constraints(unavailable_resources=["ogi_inspector"] if sc.has("inspector_unavailable") else [])
    belief = dict(sc.agent_prior)
    findings: list[str] = []
    pre = Measurement(id="PRE", rate_kg_h=sc.e0_kg_h, uncertainty_kg_h=PRE_UNCERTAINTY_FRACTION * sc.e0_kg_h,
                      date="day 0", method="Satellite (simulated)", independent=True,
                      actor=ActorType.SATELLITE, label=DataLabel.SIMULATED_EVENT)

    for loop in range(1, MAX_REPAIR_LOOPS + 1):
        # --- plan → approve → act → update, until one source is likely enough ---
        while max(belief.values()) < config.ATTRIBUTION_THRESHOLD:
            action = chooser(belief, constraints)
            if action is None:
                break
            if action.requires_approval and run.status == S.SOURCE_ATTRIBUTION_PENDING:
                run.transition(S.INVESTIGATION_REQUESTED, ActorType.AGENT, approval_granted=True)
            belief, fid = _execute_investigation(run, action, belief, human_approval=True)
            constraints.performed_actions.append(action.id)
            if fid:
                findings.append(fid)
            if run.status == S.INVESTIGATION_REQUESTED and max(belief.values()) < config.ATTRIBUTION_THRESHOLD:
                run.transition(S.SOURCE_ATTRIBUTION_PENDING, ActorType.AGENT)

        # --- attribution + notification (both human-approved) ---
        run.attributed_source = max(belief, key=belief.get)
        attr = run.decide("attribution", list(findings), "Human reviewer")
        run.day += APPROVAL_DELAY_DAYS
        run.decide("notification", [f"ATTRI-{attr.id}"], "Human reviewer")
        run.day += APPROVAL_DELAY_DAYS
        if run.status == S.SOURCE_ATTRIBUTION_PENDING:
            run.transition(S.INVESTIGATION_REQUESTED, ActorType.AGENT, approval_granted=True)

        # --- operator repairs and claims; the claim alone can never close the case ---
        _repair(run, run.attributed_source, claim_number=loop)
        run.transition(S.REPAIR_REPORTED, ActorType.SIMULATED)
        refusal = validate_transition(S.REPAIR_REPORTED, S.VERIFIED_REDUCTION, TransitionContext(actor=ActorType.SIMULATED))
        assert not refusal.allowed
        run.actions.append("closure_on_claim_REJECTED")
        run.transition(S.VERIFICATION_PENDING, ActorType.AGENT)

        # --- independent verification ---
        verdict: Optional[Verdict] = None
        result = None
        for campaign in range(1, MAX_MEASUREMENT_CAMPAIGNS + 1):
            posts = _measurement_campaign(run, campaign)
            result = verification.evaluate_verification(pre, posts)
            verdict = result.verdict
            run.actions.append(f"verdict:{verdict.value}")
            if verdict == Verdict.INCONCLUSIVE:
                run.transition(S.INCONCLUSIVE, ActorType.AGENT, verification_verdict=verdict)
                run.transition(S.VERIFICATION_PENDING, ActorType.AGENT)  # request a fresh campaign
                continue
            break

        if verdict == Verdict.VERIFIED_REDUCTION:
            assert result is not None
            run.decide("closure", [f"VERDICT-VR-{loop}"], "Human reviewer")
            run.day += APPROVAL_DELAY_DAYS
            run.transition(S.VERIFIED_REDUCTION, ActorType.HUMAN, verification_verdict=verdict, approval_granted=True)
            run.closed_ever, run.closure_day = True, run.day
            run.closure_evidence_ok = True
            run.truth_reduced_at_closure = _truth_reduced(run)
            threshold = verification.recurrence_threshold(result)
            if sc.has("recurrence"):
                run.day += RECURRENCE_AFTER_DAYS
                run.true_emission = sc.e0_kg_h  # emissions return
                if verification.is_recurrence(sc.e0_kg_h, threshold):
                    run.transition(S.RECURRING, ActorType.SATELLITE, observation_above_threshold=True)
                    run.reopened = True
                    run.actions.append("REOPENED_RECURRING")
            break

        if verdict == Verdict.STILL_LEAKING:
            run.transition(S.STILL_LEAKING, ActorType.AGENT, verification_verdict=verdict)
            target = run.attributed_source
            lik = {h: (config.REPAIR_FAILED_IF_TARGET if h == target else config.REPAIR_FAILED_IF_OTHER)
                   for h in config.HYPOTHESIS_IDS}
            belief = bayes.bayes_update(belief, lik)
            findings.append(f"FIND-repair_failed_{target}_{loop}")
            run.transition(S.SOURCE_ATTRIBUTION_PENDING, ActorType.AGENT)
            continue
        break  # still INCONCLUSIVE after all campaigns: stay open, honestly
    return run


def run_policy_c_noplan(sc: Scenario) -> PolicyRun:
    return run_policy_c(sc, chooser=choose_cheapest, policy_id="C_noplan")


POLICIES: dict[str, Callable[[Scenario], PolicyRun]] = {
    "A": run_policy_a,
    "B": run_policy_b,
    "C": run_policy_c,
    "C_noplan": run_policy_c_noplan,
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def to_outcome(run: PolicyRun) -> ScenarioPolicyOutcome:
    false_closure = run.closed_ever and not (run.closure_evidence_ok and run.truth_reduced_at_closure)
    return ScenarioPolicyOutcome(
        final_status=run.status.value,
        closed=run.closed_ever,
        false_closure=false_closure,
        resolved=run.resolved,
        attributed_source=run.attributed_source,
        inspections=run.inspections,
        attribution_inspections=run.attribution_inspections,
        cost_inr=run.cost,
        days_to_stakeholder=run.days_to_stakeholder if (run.days_to_stakeholder or 0) <= HORIZON_DAYS else None,
        days_elapsed=run.day,
        actions=run.actions,
        critical_decisions=len(run.decisions),
        traceable_decisions=sum(is_traceable(d) for d in run.decisions),
    )


def _mean(xs: list[float]) -> Optional[float]:
    return round(sum(xs) / len(xs), 2) if xs else None


def aggregate(policy_id: str, runs: list[PolicyRun]) -> PolicyMetrics:
    outs = [to_outcome(r) for r in runs]
    n = len(outs)
    resolved = sum(o.resolved for o in outs)
    inspections = sum(o.inspections for o in outs)
    cost = sum(o.cost_inr for o in outs)
    crit = sum(o.critical_decisions for o in outs)
    trace = sum(o.traceable_decisions for o in outs)
    attributing = [r for r in runs if r.attributed_source is not None]
    stake = [o.days_to_stakeholder for o in outs if o.days_to_stakeholder is not None]
    closures = [r.closure_day for r in runs if r.closure_day is not None]
    return PolicyMetrics(
        policy_id=policy_id,  # type: ignore[arg-type]
        label=POLICY_LABELS[policy_id],
        description=POLICY_DESCRIPTIONS[policy_id],
        n_cases=n,
        closed_cases=sum(o.closed for o in outs),
        false_closures=sum(o.false_closure for o in outs),
        false_closure_rate=round(sum(o.false_closure for o in outs) / n, 4) if n else 0.0,
        resolved_cases=resolved,
        correct_attribution_rate=round(sum(r.attributed_source == r.scenario.true_source for r in attributing) / n, 4) if n else 0.0,
        inspections_total=inspections,
        inspections_per_resolved=round(inspections / resolved, 2) if resolved else None,
        attribution_inspections_per_case=round(sum(o.attribution_inspections for o in outs) / n, 2) if n else 0.0,
        verification_inspections_total=inspections - sum(o.attribution_inspections for o in outs),
        cost_total_inr=cost,
        cost_per_resolved_inr=round(cost / resolved, 0) if resolved else None,
        mean_days_to_stakeholder=_mean(stake),
        stakeholder_assigned_rate=round(len(stake) / n, 4) if n else 0.0,
        traceability_pct=round(100.0 * trace / crit, 1) if crit else 0.0,
        mean_days_to_closure=_mean(closures),
    )


# ---------------------------------------------------------------------------
# Sensitivity analysis
# ---------------------------------------------------------------------------
def kendall_tau(order_a: Sequence[str], order_b: Sequence[str]) -> float:
    """Kendall's τ between two rankings of the same items: (concordant − discordant) / pairs."""
    pos_b = {x: i for i, x in enumerate(order_b)}
    items = [x for x in order_a if x in pos_b]
    conc = disc = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if pos_b[items[i]] < pos_b[items[j]]:
                conc += 1
            else:
                disc += 1
    pairs = conc + disc
    return (conc - disc) / pairs if pairs else 1.0


def run_sensitivity(seed: int, n_scenarios: int, n_draws: int = 200, rel: float = 0.2) -> SensitivityResult:
    nominal = planner.rank_actions(config.DEFAULT_PRIOR, config.ACTIONS, Constraints(), config.DEFAULT_LAMBDA)
    nominal_order = [r.action_id for r in nominal.ranked]
    rng = random.Random(seed + 7)
    taus: list[float] = []
    top_counts: dict[str, int] = {}
    same_top = 0
    for _ in range(n_draws):
        perturbed = bayes.perturb_actions(config.ACTIONS, rel, rng)
        plan = planner.rank_actions(config.DEFAULT_PRIOR, perturbed, Constraints(), config.DEFAULT_LAMBDA)
        order = [r.action_id for r in plan.ranked]
        top_counts[order[0]] = top_counts.get(order[0], 0) + 1
        same_top += order[0] == nominal_order[0]
        taus.append(kendall_tau(nominal_order, order))

    # Robustness: the WORLD uses perturbed likelihoods, the agent keeps the nominal ones.
    world_rng = random.Random(seed + 11)
    world_actions = bayes.perturb_actions(config.ACTIONS, rel, world_rng)
    scenarios = generate_scenarios(seed + 1, n_scenarios, world_actions=world_actions)
    runs = [run_policy_c(sc) for sc in scenarios]
    m = aggregate("C", runs)
    return SensitivityResult(
        n_draws=n_draws,
        perturbation=rel,
        top_action_stability_pct=round(100.0 * same_top / n_draws, 1),
        mean_kendall_tau=round(sum(taus) / len(taus), 3),
        top_action_counts=top_counts,
        c_false_closures_perturbed=m.false_closures,
        c_inspections_per_resolved_perturbed=m.inspections_per_resolved,
    )


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------
DEFINITIONS = {
    "false_closure": "Case closed AND (no independent VERIFIED_REDUCTION verdict behind the closure OR the hidden "
                     "true emission was not actually reduced, i.e. true post ≥ 0.5·E0). Target: 0.",
    "closed": "The case reached a closed/resolved state at some point (a later automatic reopen does not undo the "
              "count; see final_status = RECURRING).",
    "resolved": "The operator's repair actually hit the hidden true source and was effective (true emission reduced), "
                "regardless of the paperwork.",
    "inspections": "Field inspections: OGI surveys, ground surveys and independent measurement campaigns "
                   "(actions with is_field_inspection). Records requests and satellite waits are not inspections.",
    "inspections_per_resolved": "Total inspections / resolved cases.",
    "attribution_inspections_per_case": "Field inspections used to IDENTIFY THE SOURCE (OGI + ground surveys; excludes "
                                        "verification campaigns), mean per case. PDF objective 2.",
    "cost_per_resolved_inr": "Total investigation + verification cost (₹) / resolved cases.",
    "days_to_stakeholder": "Simulated days from detection until the accountable operator is formally identified and "
                           "assigned (A: alert forwarded by the national focal point; B: manual lookup; C: overlay + approval).",
    "traceability_pct": "% of critical decisions (investigation, attribution, notification, closure) that link the "
                        "evidence their kind requires (investigation→observation, attribution→finding, "
                        "notification→attribution decision, closure→independent VERIFIED_REDUCTION verdict) AND have a "
                        "recorded human approval.",
    "correct_attribution_rate": "Share of all cases where the policy's final attributed source equals the hidden "
                                "true source (A never attributes → 0).",
    "mean_days_to_closure": "Mean simulated day of closure, over cases that were closed.",
}


def run_evaluation(seed: int = 2026, n_scenarios: int = 25) -> EvaluationReport:
    scenarios = generate_scenarios(seed, n_scenarios)
    runs: dict[str, list[PolicyRun]] = {pid: [fn(sc) for sc in scenarios] for pid, fn in POLICIES.items()}
    results = [
        ScenarioResult(
            scenario_id=sc.scenario_id, tags=sc.tags, true_source=sc.true_source, description=sc.description,
            outcomes={pid: to_outcome(runs[pid][i]) for pid in POLICIES},
        )
        for i, sc in enumerate(scenarios)
    ]
    metrics = [aggregate(pid, runs[pid]) for pid in POLICIES]
    sens = run_sensitivity(seed, n_scenarios)
    recur = [sc for sc in scenarios if sc.has("recurrence")]
    reopened = {pid: sum(r.reopened for r in runs[pid]) for pid in POLICIES}
    notes = [
        "All 25 scenarios, operator behaviour, inspector availability, records content and measurements are SIMULATED. "
        "Likelihoods, costs and delays are illustrative demonstration values (docs/ASSUMPTIONS.md).",
        "Fairness: each scenario's world answers and measurement noise are pre-sampled once, so every policy faces the same world.",
        f"Recurrence scenarios: {len(recur)}. Automatically reopened after closure: "
        + ", ".join(f"{POLICY_LABELS[p]} {reopened[p]}" for p in POLICIES) + ". A and B do no post-closure monitoring.",
        "Field inspections used for SOURCE ATTRIBUTION only (excluding verification campaigns), mean per case: "
        + ", ".join(f"{POLICY_LABELS[p]} {sum(r.attribution_inspections for r in runs[p]) / len(runs[p]):.2f}" for p in POLICIES)
        + ". PlumeProof's totals above also include its independent verification campaigns, which A and B never pay for.",
        "A and B close on the operator's repair claim, so every closure they make is a false closure by definition "
        "(no independent evidence). This follows from their design; it is not a tuned result.",
        "Measurement noise is bounded (|error| ≤ 0.8·u). With unbounded (e.g. Gaussian) noise, rare false verified "
        "reductions become possible for any policy that relies on measurements.",
    ]
    return EvaluationReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        seed=seed,
        n_scenarios=n_scenarios,
        policies=metrics,
        scenarios=results,
        sensitivity=sens,
        definitions=DEFINITIONS,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def _fmt(v, nd=2, money=False) -> str:
    if v is None:
        return "n/a"
    if money:
        return f"₹{v:,.0f}"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def summary_table(report: EvaluationReport) -> str:
    head = ("| Policy | False closures | Closed | Resolved | Correct attribution | Source-ID inspections / case | "
            "Inspections / resolved (incl. verification) | Cost / resolved | Days to stakeholder | Traceability | Days to closure |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n")
    rows = []
    for m in report.policies:
        rows.append(
            f"| {m.label} | {m.false_closures}/{m.n_cases} ({100 * m.false_closure_rate:.0f}%) | {m.closed_cases} | "
            f"{m.resolved_cases} | {100 * m.correct_attribution_rate:.0f}% | {m.attribution_inspections_per_case:.2f} | {_fmt(m.inspections_per_resolved)} | "
            f"{_fmt(m.cost_per_resolved_inr, money=True)} | {_fmt(m.mean_days_to_stakeholder, 1)} | "
            f"{m.traceability_pct:.1f}% | {_fmt(m.mean_days_to_closure, 1)} |"
        )
    return head + "\n".join(rows)


def write_reports(report: EvaluationReport, docs_dir: str | Path) -> None:
    docs = Path(docs_dir)
    docs.mkdir(parents=True, exist_ok=True)
    s = report.sensitivity
    by = {m.policy_id: m for m in report.policies}
    lines = [
        "# PlumeProof evaluation",
        "",
        f"> Generated by `python -m plumeproof.scenarios` at {report.generated_at}, seed {report.seed}, "
        f"{report.n_scenarios} scenarios. **All scenarios are simulated.** Re-run it from the Evaluation page "
        "(\"Re-run evaluation\") or with `POST /api/evaluate`. These numbers come from running the code; none were typed in by hand.",
        "",
        "## Method",
        "",
        f"- {report.n_scenarios} seeded scenarios, each with a hidden true emission source (waste surface / gas collection / flare) "
        "and a true pre-intervention emission E0 ∈ [600, 3500] kg/h.",
        "- Scenario tags: ambiguous (flat prior 0.36/0.34/0.30, uniformly drawn true source), missing records (records request "
        "gets no response before the 7-day deadline), inspector unavailable (OGI inspector), conflicting measurements (first "
        "verification campaign returns two non-overlapping readings), unsupported claim (the operator's first repair claim is "
        "false), recurrence (emission returns 300 days after closure). Untagged scenarios are plain.",
        "- The world answers each investigation by sampling y ~ P(y | true source, action) from the likelihood tables in "
        "`config.py`. Answers and measurement noise are pre-sampled per scenario, so all policies face the same world.",
        "- The operator repairs whatever source it is told (A: its own guess) and always files a repair claim. The repair is effective "
        "(E → 0.25·E0) only if it targets the true source and the claim is not an unsupported one.",
        "- Independent measurements report truth ± bounded noise (|error| ≤ 0.8·u, u = 0.15·truth + 50 kg/h). The pre-intervention "
        "satellite estimate is E0 ± 25%.",
        "",
        "## Policies",
        "",
    ]
    lines += [f"- **{m.label}**: {m.description}" for m in report.policies]
    lines += ["", "## Metric definitions", ""]
    lines += [f"- **{k}**: {v}" for k, v in report.definitions.items()]
    lines += ["", "## Results", "", summary_table(report), ""]
    c, b, nop = by.get("C"), by.get("B"), by.get("C_noplan")
    lines += ["## Ablation: planner disabled", ""]
    if c and nop:
        lines.append(
            f"With the Evidence Planner replaced by \"cheapest action first\", PlumeProof keeps its verification gate "
            f"({nop.false_closures} false closures), but it spends {_fmt(nop.mean_days_to_closure, 1)} days to closure on average vs "
            f"{_fmt(c.mean_days_to_closure, 1)} for C. Its correct-attribution rate is {100 * nop.correct_attribution_rate:.0f}% vs "
            f"{100 * c.correct_attribution_rate:.0f}%, and it needs {_fmt(nop.inspections_per_resolved)} vs "
            f"{_fmt(c.inspections_per_resolved)} inspections and {_fmt(nop.cost_per_resolved_inr, money=True)} vs "
            f"{_fmt(c.cost_per_resolved_inr, money=True)} per resolved case. Cheapest-first starts with the free satellite "
            "wait (30 days, 0 bits about the source)."
        )
    if c and b:
        lines += ["", "## PlumeProof vs fixed checklist", "",
                  f"C needs {_fmt(c.inspections_per_resolved)} inspections per resolved case vs {_fmt(b.inspections_per_resolved)} "
                  f"for B, and {_fmt(c.cost_per_resolved_inr, money=True)} vs {_fmt(b.cost_per_resolved_inr, money=True)}. "
                  "C's count *includes* its independent verification campaigns, which B never pays for. "
                  f"Counting only the inspections used to identify the source, C needs {c.attribution_inspections_per_case:.2f} "
                  f"per case vs {b.attribution_inspections_per_case:.2f} for B. "
                  f"False closures: C {c.false_closures}, B {b.false_closures}."]
    lines += [
        "", "## Sensitivity (±20% likelihoods)", "",
        f"- Ranking stability: in {s.n_draws} draws, every P(y|h,a) is multiplied by U[0.8, 1.2] and renormalised. The top-ranked "
        f"action is unchanged in **{s.top_action_stability_pct:.1f}%** of draws. Mean Kendall τ vs the nominal ranking: "
        f"**{s.mean_kendall_tau:.3f}**. Top-action counts: "
        + ", ".join(f"{k} {v}" for k, v in sorted(s.top_action_counts.items(), key=lambda kv: -kv[1])) + ".",
        f"- Robustness: C is run on worlds whose *true* likelihoods are perturbed ±20% while the agent keeps the nominal "
        f"tables. False closures: **{s.c_false_closures_perturbed}**. Inspections per resolved case: "
        f"{_fmt(s.c_inspections_per_resolved_perturbed)}.",
        "", "## Per-scenario results", "",
        "| Scenario | Tags | True source | A | B | C | C-ablation |", "|---|---|---|---|---|---|---|",
    ]

    def cell(o: ScenarioPolicyOutcome) -> str:
        flag = "FALSE CLOSURE" if o.false_closure else ("resolved" if o.resolved else "unresolved")
        return f"{o.final_status} · {flag} · {o.inspections} insp · ₹{o.cost_inr:,.0f}"

    for r in report.scenarios:
        lines.append(f"| {r.scenario_id} | {', '.join(r.tags) or 'plain'} | {config.HYPOTHESIS_LABELS[r.true_source]} | "
                     + " | ".join(cell(r.outcomes[p]) for p in ["A", "B", "C", "C_noplan"]) + " |")
    lines += ["", "## Notes and honest limitations", ""]
    lines += [f"- {n}" for n in report.notes]
    lines += [
        "- Policy behaviours for A and B are our models of an alert-only system and a fixed checklist. They are not measurements "
        "of any real system.",
        "- Delays (approval 1 day, alert forwarding 30 days, manual stakeholder lookup 7 days, repair 14 days) are assumptions.",
        "- The expert-assessment metric from the proposal (environmental-engineer review of priorities) is not yet done.",
        "",
    ]
    (docs / "EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")

    with open(docs / "evaluation_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario_id", "tags", "true_source", "policy", "final_status", "closed", "false_closure", "resolved",
                    "attributed_source", "inspections", "cost_inr", "days_to_stakeholder", "days_elapsed",
                    "critical_decisions", "traceable_decisions", "actions"])
        for r in report.scenarios:
            for pid, o in r.outcomes.items():
                w.writerow([r.scenario_id, ";".join(r.tags), r.true_source, pid, o.final_status, o.closed, o.false_closure,
                            o.resolved, o.attributed_source or "", o.inspections, f"{o.cost_inr:.0f}",
                            "" if o.days_to_stakeholder is None else f"{o.days_to_stakeholder:.0f}", f"{o.days_elapsed:.0f}",
                            o.critical_decisions, o.traceable_decisions, " | ".join(o.actions)])


if __name__ == "__main__":
    rep = run_evaluation(2026, 25)
    out = Path(__file__).resolve().parents[2] / "docs"
    write_reports(rep, out)
    print(summary_table(rep))
    s = rep.sensitivity
    print(f"\nSensitivity: top action stable {s.top_action_stability_pct}% · Kendall τ {s.mean_kendall_tau} · "
          f"C false closures (perturbed world) {s.c_false_closures_perturbed}")
    print(f"Wrote {out / 'EVALUATION.md'} and {out / 'evaluation_results.csv'}")
