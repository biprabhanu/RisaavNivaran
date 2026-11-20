"""
CaseAgent: the persistent case orchestrator.

One CaseAgent manages one case through an explicit loop (PDF slide 11):

    observe → update beliefs → plan → request approval → act → verify
       ▲                                                          │
       └──────────── reopen if emissions return ◄─────────────────┘

Design rules
------------
* The agent never changes ``case.status`` by assignment. Every change goes through
  ``request_transition``, which asks ``state_machine.validate_transition``. Then:
    - allowed            → status changes, STATUS_CHANGED event
    - needs approval     → an ApprovalItem is created, the agent waits for a human
    - forbidden          → TRANSITION_REJECTED event, status unchanged
* Every critical decision (attribution, notification, field investigation, closure) goes through
  the Human Approval Queue. The agent resumes in ``on_approval_decided``.
* All maths is in bayes.py / planner.py / verification.py; this file only orchestrates and logs.
* State lives in SQLite (db.py), so a case can stay open for months across server restarts.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from . import bayes, db, state_machine, tools
from .config import (
    ACTIONS_BY_ID,
    ATTRIBUTION_THRESHOLD,
    DEFAULT_PRIOR,
    HYPOTHESIS_IDS,
    HYPOTHESIS_LABELS,
    REPAIR_FAILED_IF_OTHER,
    REPAIR_FAILED_IF_TARGET,
)
from .schemas import (
    ActorType,
    ApprovalDecision,
    ApprovalItem,
    ApprovalKind,
    ApprovalStatus,
    AuditEvent,
    BayesUpdate,
    BeliefSnapshot,
    Case,
    CaseStatus,
    ChainStage,
    Constraints,
    DataLabel,
    Facility,
    Measurement,
    Observation,
    PlanResult,
    Stakeholder,
    TransitionContext,
    TransitionDecision,
    Verdict,
)
from .tools import AGENT_NAME, add_days, new_id, now_iso

S = CaseStatus

_LABEL_FOR_ACTOR = {
    ActorType.AGENT: DataLabel.AGENT_ACTION,
    ActorType.HUMAN: DataLabel.HUMAN_DECISION,
    ActorType.SIMULATED: DataLabel.SIMULATED_EVENT,
    ActorType.SATELLITE: DataLabel.REAL_DATA,
}


class CaseNotFound(KeyError):
    pass


class CaseAgent:
    """Orchestrates one case. Create with ``CaseAgent.load(case_id)`` or ``CaseAgent.open_case(...)``."""

    def __init__(self, case: Case):
        self.case = case

    # ------------------------------------------------------------------
    # Construction / persistence
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, case_id: str) -> "CaseAgent":
        case = db.get_case(case_id)
        if case is None:
            raise CaseNotFound(case_id)
        return cls(case)

    def save(self) -> None:
        db.save_case(self.case)

    @property
    def facility(self) -> Facility:
        return get_facility(self.case.facility_id)

    @classmethod
    def open_case(
        cls,
        case_id: str,
        title: str,
        facility: Facility,
        observations: Sequence[Observation],
        stakeholders: Sequence[Stakeholder],
        pre_measurement: Optional[Measurement] = None,
        sim_date: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> "CaseAgent":
        """
        OBSERVE: a satellite detection becomes a managed case (PDF objective 1).
        Calls the query_observations and overlay_facility_zones tools and resolves stakeholders.
        """
        total = sum(o.rate_kg_h for o in observations)
        if priority is None:
            priority = "Critical" if total >= 1000 else "High" if total >= 500 else "Medium" if total >= 100 else "Low"
        sim_date = sim_date or (observations[0].date if observations else None)
        case = Case(
            id=case_id, facility_id=facility.id, title=title, status=S.OPEN, priority=priority,  # type: ignore[arg-type]
            created_at=now_iso(), sim_date=sim_date, belief=dict(DEFAULT_PRIOR),
            pre_measurement=pre_measurement,
        )
        agent = cls(case)
        agent.save()
        for o in observations:
            linked = o.model_copy(update={"case_id": case_id})
            db.save_observation(linked)
            agent._event(
                "OBSERVATION_RECORDED", f"Satellite observation: {o.plume_label}, {o.rate_kg_h:,.0f} kg/h",
                f"{o.source} detected {o.plume_label} at {facility.name} on {o.date}: ~{o.rate_kg_h:,.0f} kg CH₄/h.",
                label=o.label, actor=ActorType.SATELLITE if o.label == DataLabel.REAL_DATA else ActorType.SIMULATED,
                actor_name=o.source, chain_stage=ChainStage.OBSERVATION, evidence_ids=[o.id],
                data={"rate_kg_h": o.rate_kg_h, "lat": o.lat, "lng": o.lng},
            )
        found = tools.query_observations(case, facility.id, on_date=sim_date)
        overlay = tools.overlay_facility_zones(case, facility, found or list(observations), stakeholders)
        case.stakeholders = list(overlay["stakeholders"])
        case.observation_ids = [o.id for o in observations]
        agent._event(
            "CASE_OPENED", f"Case {case_id} opened",
            f"Detection converted into a managed case (priority {priority}). Accountable stakeholder: "
            f"{case.stakeholders[0].name if case.stakeholders else 'unresolved'} (simulated mapping).",
            chain_stage=ChainStage.OBSERVATION, evidence_ids=[o.id for o in observations],
        )
        agent.save()
        return agent

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _event(
        self,
        type_: str,
        title: str,
        description: str,
        label: DataLabel = DataLabel.AGENT_ACTION,
        actor: ActorType = ActorType.AGENT,
        actor_name: str = AGENT_NAME,
        chain_stage: Optional[ChainStage] = None,
        evidence_ids: Optional[list[str]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> AuditEvent:
        ev = AuditEvent(
            id=new_id("EVT"), case_id=self.case.id, timestamp=now_iso(), sim_date=self.case.sim_date,
            actor=actor, actor_name=actor_name, type=type_, label=label, title=title, description=description,
            evidence_ids=evidence_ids or [], chain_stage=chain_stage, data=data or {},
        )
        db.add_event(ev)
        return ev

    def _last_event_id(self, *types: str) -> Optional[str]:
        for ev in reversed(db.list_events(self.case.id)):
            if ev.type in types:
                return ev.id
        return None

    def _snapshot_belief(self, reason: str) -> None:
        self.case.belief_history.append(BeliefSnapshot(
            timestamp=now_iso(), sim_date=self.case.sim_date, belief=dict(self.case.belief),
            entropy_bits=bayes.entropy(self.case.belief), reason=reason,
        ))

    def set_sim_date(self, sim_date: Optional[str]) -> None:
        if sim_date:
            self.case.sim_date = sim_date

    # ------------------------------------------------------------------
    # The single gate for status changes
    # ------------------------------------------------------------------
    def request_transition(
        self,
        to_status: CaseStatus,
        actor: ActorType = ActorType.AGENT,
        reason: str = "",
        approval_granted: bool = False,
        verdict: Optional[Verdict] = None,
        above_threshold: bool = False,
        requested_by_llm: bool = False,
        actor_name: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
    ) -> TransitionDecision:
        """
        Ask the state machine whether the case may move to ``to_status``. Nobody, whether agent,
        human, operator or LLM, can bypass this.
        """
        from_status = self.case.status
        if verdict is None and self.case.verification is not None:
            verdict = self.case.verification.verdict
        ctx = TransitionContext(actor=actor, verification_verdict=verdict, approval_granted=approval_granted,
                                observation_above_threshold=above_threshold)
        decision = state_machine.validate_transition(from_status, to_status, ctx)
        who = actor_name or (AGENT_NAME if actor == ActorType.AGENT else actor.value)
        data = {"from": from_status.value, "to": to_status.value, "requested_by_llm": requested_by_llm,
                "requested_by": who, "request_reason": reason}

        if decision.allowed:
            self.case.status = to_status
            self._event(
                "STATUS_CHANGED", f"Status: {from_status.value} → {to_status.value}",
                decision.reason + (f" ({reason})" if reason else ""),
                label=DataLabel.SIMULATED_EVENT if actor == ActorType.SIMULATED else DataLabel.AGENT_ACTION,
                actor=ActorType.SIMULATED if actor == ActorType.SIMULATED else ActorType.AGENT,
                actor_name=who if actor == ActorType.SIMULATED else AGENT_NAME,
                evidence_ids=evidence_ids, data=data,
            )
            self.save()
        elif decision.requires_approval is not None:
            existing = [a for a in db.list_approvals(self.case.id, ApprovalStatus.PENDING)
                        if a.payload.get("target_status") == to_status.value]
            if not existing:
                self._request_approval_for_transition(decision, reason, evidence_ids or [])
        else:
            self._event(
                "TRANSITION_REJECTED", f"Transition REJECTED: {from_status.value} → {to_status.value}",
                decision.reason, chain_stage=ChainStage.VERIFICATION if to_status == S.VERIFIED_REDUCTION else None,
                evidence_ids=evidence_ids, data=data,
            )
            self.save()
        return decision

    def _request_approval_for_transition(self, decision: TransitionDecision, reason: str,
                                         evidence_ids: list[str]) -> ApprovalItem:
        kind = decision.requires_approval or ApprovalKind.FINAL_CLOSURE
        if decision.to_status == S.VERIFIED_REDUCTION:
            v = self.case.verification
            title = "Approve final closure: verified emission reduction"
            summary = (f"Independent evidence meets the closure rule: post {v.post_rate:,.0f} ± {v.post_uncertainty:,.0f} "
                       f"kg/h (upper {v.post_high:,.0f}) < pre lower bound {v.pre_low:,.0f} kg/h."
                       if v and v.post_rate is not None else "Verification verdict supports closure.")
            purpose = "closure"
        else:
            title = f"Approve transition to {decision.to_status.value}"
            summary = decision.reason
            purpose = "transition"
        return self.request_approval(kind, title, summary, payload={"purpose": purpose, "target_status": decision.to_status.value,
                                                                     "reason": reason}, evidence_ids=evidence_ids)

    # ------------------------------------------------------------------
    # Beliefs
    # ------------------------------------------------------------------
    def initialise_hypotheses(self, prior: Optional[dict[str, float]] = None,
                              questions: Optional[list[str]] = None) -> None:
        """Set up competing source hypotheses with the geospatial prior, then move to attribution."""
        self.case.belief = dict(prior or DEFAULT_PRIOR)
        self._snapshot_belief("Initial hypotheses (geospatial prior, illustrative)")
        h = bayes.entropy(self.case.belief)
        if questions:
            self.case.outstanding_questions = list(questions)
        self._event(
            "HYPOTHESES_INITIALISED", "Competing source hypotheses established",
            "Hypotheses: " + ", ".join(f"{HYPOTHESIS_LABELS[k]} {v:.0%}" for k, v in self.case.belief.items())
            + f". Uncertainty H = {h:.2f} bits. No source is treated as confirmed.",
            chain_stage=ChainStage.HYPOTHESIS, evidence_ids=list(self.case.observation_ids),
            data={"belief": dict(self.case.belief), "entropy_bits": h},
        )
        self.save()
        if self.case.status == S.OPEN:
            self.request_transition(S.SOURCE_ATTRIBUTION_PENDING, reason="hypotheses initialised")

    def update_beliefs(self, action_id: str, outcome_id: str, sim_date: Optional[str] = None,
                       actor: ActorType = ActorType.SIMULATED, actor_name: str = "Landfill operator (simulated)",
                       label: DataLabel = DataLabel.SIMULATED_EVENT) -> BayesUpdate:
        """
        UPDATE BELIEFS: a finding arrives (e.g. records show a fault). Apply Bayes' rule
        P(h|y) ∝ P(y|h,a)·P(h), log the finding and the before/after beliefs.
        """
        self.set_sim_date(sim_date)
        action = ACTIONS_BY_ID[action_id]
        outcome = next(o for o in action.outcomes if o.id == outcome_id)
        upd = bayes.update_with_outcome(self.case.belief, action, outcome_id)
        approval_id = None
        for a in reversed(db.list_approvals(self.case.id)):
            if a.payload.get("action_id") == action_id:
                approval_id = a.id
                break
        finding = self._event(
            "FINDING_RECEIVED", f"Finding: {outcome.label}",
            f"Result of '{action.label}': {outcome.label}.", label=label, actor=actor, actor_name=actor_name,
            chain_stage=ChainStage.FINDING, evidence_ids=[x for x in [approval_id] if x],
            data={"action_id": action_id, "outcome_id": outcome_id},
        )
        self.case.belief = dict(upd.posterior)
        self._snapshot_belief(f"After {action.label}: {outcome.label}")
        self._event(
            "BELIEF_UPDATED", "Bayesian belief update",
            "Before: " + ", ".join(f"{HYPOTHESIS_LABELS[k]} {upd.prior[k]:.0%}" for k in HYPOTHESIS_IDS)
            + ". After: " + ", ".join(f"{HYPOTHESIS_LABELS[k]} {upd.posterior[k]:.0%}" for k in HYPOTHESIS_IDS)
            + f". P(outcome) = {upd.outcome_probability:.2f}; entropy {upd.entropy_before:.2f} → {upd.entropy_after:.2f} bits.",
            chain_stage=ChainStage.FINDING, evidence_ids=[finding.id], data=upd.model_dump(),
        )
        if action_id not in self.case.constraints.performed_actions:
            self.case.constraints.performed_actions.append(action_id)
        tools.track_deadline(self.case, "", "", mark_met=action_id)
        self.save()
        self.after_finding(finding.id)
        return upd

    def after_finding(self, finding_event_id: str) -> None:
        """Propose an attribution if one hypothesis is strong enough; otherwise go back to planning."""
        leader, p = max(self.case.belief.items(), key=lambda kv: kv[1])
        if p >= ATTRIBUTION_THRESHOLD:
            self.request_approval(
                ApprovalKind.SOURCE_ATTRIBUTION,
                f"Approve source attribution: {HYPOTHESIS_LABELS[leader]} ({p:.0%})",
                f"Leading hypothesis after Bayesian update: {HYPOTHESIS_LABELS[leader]} at {p:.0%} "
                f"(threshold {ATTRIBUTION_THRESHOLD:.0%}). Other hypotheses remain open until verification.",
                payload={"purpose": "attribution", "hypothesis_id": leader, "probability": p},
                evidence_ids=[finding_event_id],
            )
        else:
            if self.case.status == S.INVESTIGATION_REQUESTED:
                self.request_transition(S.SOURCE_ATTRIBUTION_PENDING, reason="finding not decisive; re-planning")
            self.plan()

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    def plan(self, record: bool = True, lam: Optional[float] = None) -> PlanResult:
        """PLAN: rank admissible actions by EIG / (cost + λ·time)."""
        plan = tools.rank_actions(self.case, lam=lam, record=record)
        if record:
            self._event(
                "PLAN_GENERATED", "Evidence plan generated", plan.explanation, chain_stage=ChainStage.INVESTIGATION,
                evidence_ids=[x for x in [self._last_event_id("BELIEF_UPDATED", "HYPOTHESES_INITIALISED")] if x],
                data={"recommended_action_id": plan.recommended_action_id,
                      "ranked": [r.action_id for r in plan.ranked], "excluded": [e.action_id for e in plan.excluded]},
            )
        return plan

    def set_constraints(self, constraints: Constraints, actor: ActorType = ActorType.HUMAN,
                        actor_name: str = "Human reviewer", note: str = "") -> tuple[PlanResult, PlanResult]:
        """Update operational constraints (e.g. inspector unavailable) and re-plan. Returns (before, after)."""
        before = self.plan(record=False)
        old = self.case.constraints
        self.case.constraints = constraints
        changes = []
        for r in sorted(set(constraints.unavailable_resources) - set(old.unavailable_resources)):
            changes.append(f"{r} unavailable")
        for r in sorted(set(old.unavailable_resources) - set(constraints.unavailable_resources)):
            changes.append(f"{r} available again")
        for a in sorted(set(constraints.granted_authorisations) ^ set(old.granted_authorisations)):
            changes.append(f"authorisation {a} {'granted' if a in constraints.granted_authorisations else 'withdrawn'}")
        for f in sorted(set(constraints.safety_flags) ^ set(old.safety_flags)):
            changes.append(f"safety flag {f} {'raised' if f in constraints.safety_flags else 'cleared'}")
        self._event(
            "CONSTRAINTS_UPDATED", "Operational constraints changed: " + (", ".join(changes) or "no change"),
            note or "Constraint update; actions violating constraints are excluded before ranking.",
            label=_LABEL_FOR_ACTOR.get(actor, DataLabel.AGENT_ACTION), actor=actor, actor_name=actor_name,
            chain_stage=ChainStage.INVESTIGATION, data={"constraints": constraints.model_dump()},
        )
        self.save()
        after = self.plan(record=True)
        return before, after

    # ------------------------------------------------------------------
    # Approvals (human in the loop)
    # ------------------------------------------------------------------
    def request_approval(self, kind: ApprovalKind, title: str, summary: str, proposed_text: str = "",
                         payload: Optional[dict[str, Any]] = None, evidence_ids: Optional[list[str]] = None) -> ApprovalItem:
        item = ApprovalItem(
            id=new_id("APR"), case_id=self.case.id, kind=kind, title=title, summary=summary,
            proposed_text=proposed_text, payload=payload or {}, evidence_ids=evidence_ids or [], created_at=now_iso(),
        )
        db.save_approval(item)
        self._event(
            "APPROVAL_REQUESTED", f"Human approval requested: {title}", summary,
            chain_stage=_stage_for_kind(kind), evidence_ids=(evidence_ids or []) + [item.id],
            data={"approval_id": item.id, "kind": kind.value},
        )
        return item

    def propose_action(self, action_id: str) -> Optional[ApprovalItem]:
        """REQUEST APPROVAL for an investigative action (records request, OGI, ground survey...)."""
        action = ACTIONS_BY_ID[action_id]
        plan_ev = self._last_event_id("PLAN_GENERATED")
        if not action.requires_approval:
            self._start_action(action_id, None)
            return None
        draft = tools.draft_notice(self.case, self._notice_context(action_id), allow_llm=False)
        return self.request_approval(
            action.approval_kind or ApprovalKind.FIELD_INVESTIGATION,
            f"Approve investigation plan: {action.label}",
            f"{action.label}: ₹{action.cost_inr:,.0f}, {action.time_days:g} day(s). {action.description}",
            proposed_text=draft.text,
            payload={"purpose": "investigation", "action_id": action_id},
            evidence_ids=[x for x in [plan_ev] if x],
        )

    def decide(self, approval_id: str, decision: ApprovalDecision, label: DataLabel = DataLabel.HUMAN_DECISION) -> ApprovalItem:
        """A human approves / edits / rejects an approval item; the agent then continues its loop."""
        item = db.get_approval(approval_id)
        if item is None:
            raise KeyError(approval_id)
        if item.status != ApprovalStatus.PENDING:
            return item
        item.status = {"approve": ApprovalStatus.APPROVED, "edit": ApprovalStatus.EDITED,
                       "reject": ApprovalStatus.REJECTED}[decision.decision]
        item.edited_text = decision.edited_text if decision.decision == "edit" else None
        item.decided_at = now_iso()
        item.decided_by = decision.decided_by
        item.note = decision.note
        db.save_approval(item)
        verb = {"APPROVED": "approved", "EDITED": "approved with edits", "REJECTED": "rejected"}[item.status.value]
        self._event(
            "APPROVAL_DECIDED", f"Human {verb}: {item.title}",
            f"{decision.decided_by} {verb} '{item.title}'." + (f" Note: {decision.note}" if decision.note else ""),
            label=label, actor=ActorType.HUMAN, actor_name=decision.decided_by,
            chain_stage=_stage_for_kind(item.kind), evidence_ids=[item.id] + item.evidence_ids,
            data={"approval_id": item.id, "decision": item.status.value},
        )
        self.on_approval_decided(item)
        return item

    def on_approval_decided(self, item: ApprovalItem) -> None:
        """Continue the loop after a human decision."""
        approved = item.status in (ApprovalStatus.APPROVED, ApprovalStatus.EDITED)
        purpose = item.payload.get("purpose")
        if not approved:
            self._event("PLAN_REVISED", "Agent re-plans after rejection",
                        f"'{item.title}' was rejected; the agent keeps the case open and re-plans.",
                        evidence_ids=[item.id])
            if purpose in ("investigation", "attribution"):
                self.plan()
            return

        if purpose == "investigation":
            if self.case.status in (S.SOURCE_ATTRIBUTION_PENDING, S.STILL_LEAKING, S.RECURRING):
                self.request_transition(S.INVESTIGATION_REQUESTED, approval_granted=True,
                                        reason=f"approved: {item.title}", evidence_ids=[item.id])
            self._start_action(item.payload["action_id"], item)
        elif purpose == "attribution":
            h = item.payload["hypothesis_id"]
            self.case.attributed_source = h
            ev = self._event(
                "ATTRIBUTION_APPROVED", f"Source attributed: {HYPOTHESIS_LABELS[h]}",
                f"Human-approved attribution to {HYPOTHESIS_LABELS[h]} ({item.payload.get('probability', 0):.0%}). "
                "Other hypotheses are retained for verification.", chain_stage=ChainStage.FINDING, evidence_ids=[item.id],
            )
            self.save()
            self.propose_corrective_notice(h, ev.id)
        elif purpose in ("corrective_action", "notice"):
            text = item.edited_text or item.proposed_text
            recipient = item.payload.get("recipient", "Kanjur landfill operator (contractor)")
            self._event(
                "NOTICE_SENT", f"Notice sent to {recipient} (simulated)",
                (text[:280] + "…") if len(text) > 280 else text, label=DataLabel.SIMULATED_EVENT,
                actor=ActorType.SIMULATED, actor_name="Notification gateway (simulated)",
                chain_stage=ChainStage.REPAIR if purpose == "corrective_action" else ChainStage.INVESTIGATION,
                evidence_ids=[item.id],
            )
            if purpose == "corrective_action":
                tools.track_deadline(self.case, "Operator corrective action (gas-system repair)",
                                     add_days(self.case.sim_date, 30), related_action="corrective_action")
            self.save()
        elif purpose == "closure":
            self.request_transition(S.VERIFIED_REDUCTION, approval_granted=True, reason="human approved final closure",
                                    evidence_ids=[item.id])
            if self.case.status == S.VERIFIED_REDUCTION and self.case.verification:
                from . import verification
                self.case.recurrence_threshold_kg_h = verification.recurrence_threshold(self.case.verification)
                self._event(
                    "CASE_CLOSED", "Case closed: VERIFIED REDUCTION",
                    f"Closed on independent evidence. Any later observation above "
                    f"{self.case.recurrence_threshold_kg_h:,.0f} kg/h will reopen the case automatically.",
                    chain_stage=ChainStage.VERIFICATION, evidence_ids=[item.id],
                )
                self.save()
        elif purpose == "transition":
            self.request_transition(CaseStatus(item.payload["target_status"]), approval_granted=True,
                                    actor=ActorType.HUMAN, reason=item.payload.get("reason", ""), evidence_ids=[item.id])

    def _start_action(self, action_id: str, item: Optional[ApprovalItem]) -> None:
        """ACT: send the request / dispatch the inspection, and track its deadline."""
        action = ACTIONS_BY_ID[action_id]
        if item is not None and action.approval_kind == ApprovalKind.NOTIFICATION:
            text = item.edited_text or item.proposed_text
            self._event("NOTICE_SENT", "Records request sent to operator (simulated)",
                        (text[:280] + "…") if len(text) > 280 else text, label=DataLabel.SIMULATED_EVENT,
                        actor=ActorType.SIMULATED, actor_name="Notification gateway (simulated)",
                        chain_stage=ChainStage.INVESTIGATION, evidence_ids=[item.id])
        self._event("ACTION_REQUESTED", f"Investigation started: {action.label}",
                    f"Expected cost ₹{action.cost_inr:,.0f}, duration {action.time_days:g} day(s).",
                    chain_stage=ChainStage.INVESTIGATION, evidence_ids=[item.id] if item else [],
                    data={"action_id": action_id})
        # Mark as performed so the planner doesn't propose it again while it's in progress.
        if action_id not in self.case.constraints.performed_actions:
            self.case.constraints.performed_actions.append(action_id)
        tools.track_deadline(self.case, f"Result due: {action.label}", add_days(self.case.sim_date, action.time_days),
                             related_action=action_id)
        self.save()

    def _notice_context(self, action_id: Optional[str] = None, request_text: Optional[str] = None,
                        recipient: Optional[str] = None, deadline: Optional[str] = None) -> dict[str, Any]:
        obs = db.list_observations(self.case.id)
        operator = next((s.name for s in self.case.stakeholders if s.role == "Responsible operator"),
                        "The Site Operator")
        ctx: dict[str, Any] = {
            "case_id": self.case.id, "facility_name": self.facility.name, "recipient": recipient or operator,
            "observations": [f"{o.date}: {o.plume_label}, ~{o.rate_kg_h:,.0f} kg CH₄/h ({o.source}, {o.label.value})" for o in obs],
            "belief": dict(self.case.belief),
        }
        if action_id:
            a = ACTIONS_BY_ID[action_id]
            ctx["action_label"] = a.label
            ctx["deadline"] = f"within {a.time_days:g} working day(s)"
        if request_text:
            ctx["request_text"] = request_text
        if deadline:
            ctx["deadline"] = deadline
        return ctx

    def propose_corrective_notice(self, hypothesis_id: str, evidence_id: Optional[str] = None) -> ApprovalItem:
        """Draft the official notification asking the operator to fix the attributed source."""
        ctx = self._notice_context(
            request_text=(f"corrective action on the {HYPOTHESIS_LABELS[hypothesis_id].lower()} identified as the "
                          f"probable source, and notification to this office once the repair is complete"),
            deadline="within 30 days")
        ctx["action_label"] = f"Corrective action: {HYPOTHESIS_LABELS[hypothesis_id]}"
        draft = tools.draft_notice(self.case, ctx, allow_llm=False)
        return self.request_approval(
            ApprovalKind.NOTIFICATION, "Approve official notification to operator",
            f"Instruct the operator to repair the {HYPOTHESIS_LABELS[hypothesis_id].lower()} and report back.",
            proposed_text=draft.text,
            payload={"purpose": "corrective_action", "hypothesis_id": hypothesis_id, "recipient": ctx["recipient"]},
            evidence_ids=[x for x in [evidence_id] if x],
        )

    def draft_stakeholder_notice(self, allow_llm: bool = True) -> tuple[str, str, Optional[str], ApprovalItem]:
        """'Generate notice' button: draft a formal letter and put it in the approval queue."""
        rec = self.plan(record=False).recommended_action_id
        ctx = self._notice_context(rec)
        draft = tools.draft_notice(self.case, ctx, allow_llm=allow_llm)
        item = self.request_approval(
            ApprovalKind.NOTIFICATION, f"Approve notice to {ctx['recipient']}",
            "Formal investigation request letter drafted by the agent.", proposed_text=draft.text,
            payload={"purpose": "notice", "recipient": ctx["recipient"]},
        )
        return draft.text, draft.mode, draft.model, item

    # ------------------------------------------------------------------
    # Repair claims and verification
    # ------------------------------------------------------------------
    def report_repair(self, sim_date: Optional[str] = None, source: Optional[str] = None,
                      text: str = "Operator reports repair of gas-collection wells complete and requests case closure.",
                      actor_name: str = "Landfill operator (simulated)") -> TransitionDecision:
        """
        A (simulated) operator says it's fixed and asks to close the case. The state machine
        REJECTS closure: a claim is not an independent measurement. The case goes to VERIFICATION_PENDING.
        Returns the (rejected) closure decision.
        """
        self.set_sim_date(sim_date)
        self.case.repaired_source = source or self.case.attributed_source
        notice = self._last_event_id("NOTICE_SENT")
        claim = self._event("REPAIR_REPORTED", "Operator reports repair complete", text, label=DataLabel.SIMULATED_EVENT,
                            actor=ActorType.SIMULATED, actor_name=actor_name, chain_stage=ChainStage.REPAIR,
                            evidence_ids=[x for x in [notice] if x],
                            data={"repaired_source": self.case.repaired_source})
        tools.track_deadline(self.case, "", "", mark_met="corrective_action")
        if self.case.status not in (S.REPAIR_REPORTED, S.VERIFICATION_PENDING):
            self.request_transition(S.REPAIR_REPORTED, actor=ActorType.SIMULATED, actor_name=actor_name,
                                    reason="operator repair claim", evidence_ids=[claim.id])
        # The operator asks to close the case on the strength of its own claim:
        closure = self.request_transition(S.VERIFIED_REDUCTION, actor=ActorType.SIMULATED, actor_name=actor_name,
                                          reason="operator requests closure on repair claim",
                                          verdict=Verdict.NO_INDEPENDENT_EVIDENCE, evidence_ids=[claim.id])
        if self.case.status == S.REPAIR_REPORTED:
            self.request_transition(S.VERIFICATION_PENDING, reason="independent post-intervention measurement required",
                                    evidence_ids=[claim.id])
        tools.track_deadline(self.case, "Independent post-intervention measurement", add_days(self.case.sim_date, 60),
                             related_action="independent_measurement")
        self.save()
        return closure

    def add_measurement(self, m: Measurement, sim_date: Optional[str] = None) -> Any:
        """VERIFY: a post-intervention measurement arrives; apply the evidence-gated rule."""
        self.set_sim_date(sim_date or m.date)
        self.case.measurements.append(m)
        self._event(
            "MEASUREMENT_RECEIVED", f"Measurement received: {m.rate_kg_h:,.0f} ± {m.uncertainty_kg_h:,.0f} kg/h",
            f"{m.method} on {m.date}. Independent: {'yes' if m.independent else 'NO'}; "
            f"comparable conditions: {'yes' if m.comparable_conditions else 'NO'}.",
            label=m.label, actor=m.actor, actor_name=m.method, chain_stage=ChainStage.VERIFICATION,
            evidence_ids=[m.id], data=m.model_dump(),
        )
        pre = self.case.pre_measurement
        if pre is None:
            self.save()
            return None
        result = tools.evaluate_measurement(self.case, pre, self.case.measurements)
        self.case.verification = result
        verdict_ev = self._event(
            "VERDICT", f"Verification verdict: {result.verdict.value.replace('_', ' ')}", " ".join(result.reasons),
            chain_stage=ChainStage.VERIFICATION, evidence_ids=[pre.id] + [x.id for x in self.case.measurements],
            data=result.model_dump(),
        )
        self.save()
        if self.case.status == S.REPAIR_REPORTED:
            self.request_transition(S.VERIFICATION_PENDING, reason="measurement received")
        v = result.verdict
        if v == Verdict.VERIFIED_REDUCTION:
            self.request_transition(S.VERIFIED_REDUCTION, verdict=v, reason="independent evidence of reduction",
                                    evidence_ids=[verdict_ev.id])  # → FINAL_CLOSURE approval
        elif v == Verdict.INCONCLUSIVE:
            if self.case.status != S.INCONCLUSIVE:
                self.request_transition(S.INCONCLUSIVE, verdict=v, evidence_ids=[verdict_ev.id])
            tools.track_deadline(self.case, "Further independent measurement", add_days(self.case.sim_date, 30),
                                 related_action="independent_measurement")
        elif v == Verdict.STILL_LEAKING:
            self.request_transition(S.STILL_LEAKING, verdict=v, evidence_ids=[verdict_ev.id])
            if self.case.status == S.STILL_LEAKING:
                self._repair_failed(verdict_ev.id)
        self.save()
        return result

    def _repair_failed(self, evidence_id: str) -> None:
        """Repair of source X didn't reduce emissions → evidence against X; re-open attribution."""
        target = self.case.repaired_source
        if target:
            like = {h: (REPAIR_FAILED_IF_TARGET if h == target else REPAIR_FAILED_IF_OTHER) for h in HYPOTHESIS_IDS}
            before = dict(self.case.belief)
            self.case.belief = bayes.bayes_update(self.case.belief, like)
            self._snapshot_belief(f"Repair of {HYPOTHESIS_LABELS[target]} did not reduce emissions")
            self._event("BELIEF_UPDATED", "Belief update: repair ineffective",
                        f"Repair of {HYPOTHESIS_LABELS[target]} failed verification, so that hypothesis is down-weighted.",
                        chain_stage=ChainStage.VERIFICATION, evidence_ids=[evidence_id],
                        data={"prior": before, "posterior": dict(self.case.belief)})
        self.case.attributed_source = None
        self.case.measurements = []
        self.case.verification = None
        self.case.constraints.performed_actions = []
        self.save()
        self.request_transition(S.SOURCE_ATTRIBUTION_PENDING, reason="emissions continue; re-attribute")
        self.plan()

    # ------------------------------------------------------------------
    # New observations (and automatic reopening)
    # ------------------------------------------------------------------
    def observe(self, obs: Observation) -> bool:
        """
        OBSERVE: a new observation for this case's facility. If the case is closed (VERIFIED_REDUCTION)
        and the rate exceeds the recurrence threshold, the case is REOPENED automatically.
        Returns True if the case was reopened.
        """
        from . import verification

        self.set_sim_date(obs.date)
        linked = obs.model_copy(update={"case_id": self.case.id})
        db.save_observation(linked)
        if obs.id not in self.case.observation_ids:
            self.case.observation_ids.append(obs.id)
        ev = self._event(
            "OBSERVATION_RECORDED", f"Satellite observation: {obs.plume_label}, {obs.rate_kg_h:,.0f} kg/h",
            f"{obs.source} observed ~{obs.rate_kg_h:,.0f} kg CH₄/h on {obs.date}.", label=obs.label,
            actor=ActorType.SATELLITE if obs.label == DataLabel.REAL_DATA else ActorType.SIMULATED,
            actor_name=obs.source, chain_stage=ChainStage.OBSERVATION, evidence_ids=[obs.id],
            data={"rate_kg_h": obs.rate_kg_h},
        )
        self.save()
        tools.query_observations(self.case, self.case.facility_id, on_date=obs.date)
        threshold = self.case.recurrence_threshold_kg_h
        if self.case.status == S.VERIFIED_REDUCTION and verification.is_recurrence(obs.rate_kg_h, threshold):
            verdict_ev = self._last_event_id("CASE_CLOSED", "VERDICT")
            d = self.request_transition(
                S.RECURRING, actor=ActorType.SATELLITE, above_threshold=True,
                reason=f"{obs.rate_kg_h:,.0f} kg/h > recurrence threshold {threshold:,.0f} kg/h",
                evidence_ids=[x for x in [ev.id, verdict_ev] if x])
            if d.allowed:
                self.case.reopen_count += 1
                self._event(
                    "CASE_REOPENED", "CASE REOPENED: recurring emissions",
                    f"New observation {obs.rate_kg_h:,.0f} kg/h exceeds the verified post-repair level "
                    f"({threshold:,.0f} kg/h). The agent reopened the case automatically; hypotheses reset.",
                    chain_stage=ChainStage.OBSERVATION, evidence_ids=[x for x in [ev.id, verdict_ev] if x],
                    data={"rate_kg_h": obs.rate_kg_h, "threshold_kg_h": threshold},
                )
                self.case.belief = dict(DEFAULT_PRIOR)
                self._snapshot_belief("Reopened: hypotheses reset to geospatial prior")
                self.case.constraints = Constraints()
                self.case.attributed_source = None
                self.case.repaired_source = None
                self.case.verification = None
                self.case.measurements = []
                self.case.pre_measurement = Measurement(
                    id=f"PRE-{obs.id}", rate_kg_h=obs.rate_kg_h, uncertainty_kg_h=round(obs.rate_kg_h * 0.25, 1),
                    date=obs.date, method=f"{obs.source} satellite", independent=True, actor=ActorType.SATELLITE,
                    label=obs.label, notes="New pre-intervention baseline after reopening (±25% assumption).",
                )
                self.save()
                self.request_transition(S.SOURCE_ATTRIBUTION_PENDING, reason="recurring case returned to attribution")
                self.plan()
                return True
        return False


def _stage_for_kind(kind: ApprovalKind) -> ChainStage:
    return {
        ApprovalKind.SOURCE_ATTRIBUTION: ChainStage.FINDING,
        ApprovalKind.NOTIFICATION: ChainStage.INVESTIGATION,
        ApprovalKind.FIELD_INVESTIGATION: ChainStage.INVESTIGATION,
        ApprovalKind.FINAL_CLOSURE: ChainStage.VERIFICATION,
    }[kind]


# ---------------------------------------------------------------------------
# Facility registry (Kanjur + uploaded facilities stored in kv)
# ---------------------------------------------------------------------------
def get_facility(facility_id: str) -> Facility:
    from .kanjur import FACILITY

    if facility_id == FACILITY.id:
        return FACILITY
    data = db.kv_get(f"facility:{facility_id}")
    if data is None:
        raise KeyError(facility_id)
    return Facility.model_validate(data)


def save_facility(facility: Facility) -> None:
    db.kv_set(f"facility:{facility.id}", facility.model_dump(mode="json"))
