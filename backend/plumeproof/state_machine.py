"""
Case lifecycle state machine (PDF slide 12).

    OPEN → SOURCE_ATTRIBUTION_PENDING → INVESTIGATION_REQUESTED → REPAIR_REPORTED
         → VERIFICATION_PENDING → { VERIFIED_REDUCTION | INCONCLUSIVE | STILL_LEAKING }
    VERIFIED_REDUCTION → RECURRING (a later observation above threshold) → re-investigate

Every status change in the system, whether the agent, a human, a simulated operator or the LLM
asks for it, goes through ``validate_transition``. If a (from, to) pair is not in
``TRANSITIONS`` it is forbidden. In particular there is NO edge
REPAIR_REPORTED → VERIFIED_REDUCTION: a repair claim can never close a case.

This module is pure: no database, no clock, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .schemas import ActorType, ApprovalKind, CaseStatus, TransitionContext, TransitionDecision, Verdict

S = CaseStatus

# A guard looks at the context and returns None if OK, or a human-readable refusal reason.
Guard = Callable[[TransitionContext], Optional[str]]


def _verdict_is(v: Verdict) -> Guard:
    def guard(ctx: TransitionContext) -> Optional[str]:
        if ctx.verification_verdict != v:
            got = ctx.verification_verdict.value if ctx.verification_verdict else "no verdict"
            return f"Requires verification verdict {v.value}, but the current evidence gives {got}."
        return None

    return guard


def _above_threshold(ctx: TransitionContext) -> Optional[str]:
    if not ctx.observation_above_threshold:
        return "Requires a new observation above the recurrence threshold."
    return None


def _not_human_only(ctx: TransitionContext) -> Optional[str]:
    # Repair reports come from the operator side (simulated in the demo) or a human entering them.
    if ctx.actor not in (ActorType.SIMULATED, ActorType.HUMAN):
        return "Only the operator (or a human entering the operator's report) can report a repair."
    return None


@dataclass(frozen=True)
class TransitionRule:
    description: str
    requires_approval: Optional[ApprovalKind] = None
    guard: Optional[Guard] = None


# The complete transition table. Anything not listed here is forbidden.
TRANSITIONS: dict[tuple[CaseStatus, CaseStatus], TransitionRule] = {
    (S.OPEN, S.SOURCE_ATTRIBUTION_PENDING): TransitionRule("Agent initialised competing source hypotheses."),
    (S.SOURCE_ATTRIBUTION_PENDING, S.INVESTIGATION_REQUESTED): TransitionRule(
        "Investigation requested (human approval required).", ApprovalKind.FIELD_INVESTIGATION),
    (S.SOURCE_ATTRIBUTION_PENDING, S.REPAIR_REPORTED): TransitionRule(
        "Operator reported a repair before investigation completed.", guard=_not_human_only),
    (S.INVESTIGATION_REQUESTED, S.SOURCE_ATTRIBUTION_PENDING): TransitionRule(
        "Findings received; attribution re-opened for further planning."),
    (S.INVESTIGATION_REQUESTED, S.REPAIR_REPORTED): TransitionRule(
        "Operator reported repair completion.", guard=_not_human_only),
    (S.REPAIR_REPORTED, S.VERIFICATION_PENDING): TransitionRule(
        "Repair claim recorded; independent post-intervention evidence required."),
    (S.VERIFICATION_PENDING, S.VERIFIED_REDUCTION): TransitionRule(
        "Independent evidence shows a reduction; final closure needs human approval.",
        ApprovalKind.FINAL_CLOSURE, _verdict_is(Verdict.VERIFIED_REDUCTION)),
    (S.VERIFICATION_PENDING, S.INCONCLUSIVE): TransitionRule(
        "Evidence insufficient or conflicting.", guard=_verdict_is(Verdict.INCONCLUSIVE)),
    (S.VERIFICATION_PENDING, S.STILL_LEAKING): TransitionRule(
        "Independent evidence shows no reduction.", guard=_verdict_is(Verdict.STILL_LEAKING)),
    (S.INCONCLUSIVE, S.VERIFICATION_PENDING): TransitionRule("Further independent measurement requested."),
    (S.INCONCLUSIVE, S.VERIFIED_REDUCTION): TransitionRule(
        "New evidence shows a reduction; final closure needs human approval.",
        ApprovalKind.FINAL_CLOSURE, _verdict_is(Verdict.VERIFIED_REDUCTION)),
    (S.INCONCLUSIVE, S.STILL_LEAKING): TransitionRule(
        "New evidence shows emissions continue.", guard=_verdict_is(Verdict.STILL_LEAKING)),
    (S.STILL_LEAKING, S.SOURCE_ATTRIBUTION_PENDING): TransitionRule("Case reopened for re-attribution."),
    (S.STILL_LEAKING, S.INVESTIGATION_REQUESTED): TransitionRule(
        "New investigation requested.", ApprovalKind.FIELD_INVESTIGATION),
    (S.VERIFIED_REDUCTION, S.RECURRING): TransitionRule(
        "A later observation exceeds the recurrence threshold: automatic reopen.", guard=_above_threshold),
    (S.RECURRING, S.SOURCE_ATTRIBUTION_PENDING): TransitionRule("Recurring case returned to source attribution."),
    (S.RECURRING, S.INVESTIGATION_REQUESTED): TransitionRule(
        "New investigation requested.", ApprovalKind.FIELD_INVESTIGATION),
}

CLOSED_STATUSES: frozenset[CaseStatus] = frozenset({S.VERIFIED_REDUCTION})

# Special explanation for the most important forbidden move (the demo's show-stopper).
NO_CLAIM_CLOSURE_REASON = (
    "Closure REJECTED: no independent post-intervention measurement. "
    "A repair-completion claim is not evidence of reduced emissions; the case stays VERIFICATION_PENDING."
)


def is_closed(status: CaseStatus) -> bool:
    """A case counts as closed only in VERIFIED_REDUCTION."""
    return status in CLOSED_STATUSES


def allowed_targets(status: CaseStatus) -> list[CaseStatus]:
    """All statuses reachable in one step from ``status`` (ignoring guards)."""
    return [to for (frm, to) in TRANSITIONS if frm == status]


def validate_transition(from_status: CaseStatus, to_status: CaseStatus, ctx: TransitionContext) -> TransitionDecision:
    """
    Decide whether a case may move from ``from_status`` to ``to_status``.

    Order of checks:
    1. The edge must exist in TRANSITIONS (otherwise forbidden).
    2. Its guard (if any) must pass, e.g. "verdict must be VERIFIED_REDUCTION".
    3. If the edge needs human approval and ``ctx.approval_granted`` is False, the result is
       ``allowed=False`` with ``requires_approval`` set. The caller should create an approval item.
    """
    rule = TRANSITIONS.get((from_status, to_status))
    if rule is None:
        if to_status == S.VERIFIED_REDUCTION:
            reason = NO_CLAIM_CLOSURE_REASON if from_status in (
                S.REPAIR_REPORTED, S.INVESTIGATION_REQUESTED, S.SOURCE_ATTRIBUTION_PENDING, S.OPEN,
                S.STILL_LEAKING, S.RECURRING,
            ) else f"Transition {from_status.value} → {to_status.value} is not allowed."
        else:
            reason = f"Transition {from_status.value} → {to_status.value} is not in the workflow."
        return TransitionDecision(allowed=False, from_status=from_status, to_status=to_status, reason=reason)

    if rule.guard is not None:
        refusal = rule.guard(ctx)
        if refusal:
            if to_status == S.VERIFIED_REDUCTION:
                refusal = NO_CLAIM_CLOSURE_REASON if ctx.verification_verdict in (
                    None, Verdict.NO_INDEPENDENT_EVIDENCE) else refusal
            return TransitionDecision(allowed=False, from_status=from_status, to_status=to_status, reason=refusal)

    if rule.requires_approval is not None and not ctx.approval_granted:
        return TransitionDecision(
            allowed=False, from_status=from_status, to_status=to_status,
            requires_approval=rule.requires_approval,
            reason=f"Allowed after human approval ({rule.requires_approval.value}). {rule.description}",
        )

    return TransitionDecision(
        allowed=True, from_status=from_status, to_status=to_status,
        requires_approval=rule.requires_approval, reason=rule.description,
    )
