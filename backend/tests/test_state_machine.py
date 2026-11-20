"""The case lifecycle transition table (state_machine.py)."""
import pytest

from plumeproof.schemas import ActorType, ApprovalKind, CaseStatus as S, TransitionContext, Verdict
from plumeproof.state_machine import (
    NO_CLAIM_CLOSURE_REASON,
    TRANSITIONS,
    allowed_targets,
    is_closed,
    validate_transition,
)


def ctx(**kw):
    kw.setdefault("actor", ActorType.AGENT)
    return TransitionContext(**kw)


# (from, to, context that should make it allowed)
HAPPY = [
    (S.OPEN, S.SOURCE_ATTRIBUTION_PENDING, ctx()),
    (S.SOURCE_ATTRIBUTION_PENDING, S.INVESTIGATION_REQUESTED, ctx(approval_granted=True)),
    (S.SOURCE_ATTRIBUTION_PENDING, S.REPAIR_REPORTED, ctx(actor=ActorType.SIMULATED)),
    (S.INVESTIGATION_REQUESTED, S.SOURCE_ATTRIBUTION_PENDING, ctx()),
    (S.INVESTIGATION_REQUESTED, S.REPAIR_REPORTED, ctx(actor=ActorType.SIMULATED)),
    (S.REPAIR_REPORTED, S.VERIFICATION_PENDING, ctx()),
    (S.VERIFICATION_PENDING, S.VERIFIED_REDUCTION, ctx(verification_verdict=Verdict.VERIFIED_REDUCTION, approval_granted=True)),
    (S.VERIFICATION_PENDING, S.INCONCLUSIVE, ctx(verification_verdict=Verdict.INCONCLUSIVE)),
    (S.VERIFICATION_PENDING, S.STILL_LEAKING, ctx(verification_verdict=Verdict.STILL_LEAKING)),
    (S.INCONCLUSIVE, S.VERIFICATION_PENDING, ctx()),
    (S.INCONCLUSIVE, S.VERIFIED_REDUCTION, ctx(verification_verdict=Verdict.VERIFIED_REDUCTION, approval_granted=True)),
    (S.INCONCLUSIVE, S.STILL_LEAKING, ctx(verification_verdict=Verdict.STILL_LEAKING)),
    (S.STILL_LEAKING, S.SOURCE_ATTRIBUTION_PENDING, ctx()),
    (S.STILL_LEAKING, S.INVESTIGATION_REQUESTED, ctx(approval_granted=True)),
    (S.VERIFIED_REDUCTION, S.RECURRING, ctx(actor=ActorType.SATELLITE, observation_above_threshold=True)),
    (S.RECURRING, S.SOURCE_ATTRIBUTION_PENDING, ctx()),
    (S.RECURRING, S.INVESTIGATION_REQUESTED, ctx(approval_granted=True)),
]


def test_happy_list_covers_whole_table():
    assert {(a, b) for a, b, _ in HAPPY} == set(TRANSITIONS)


@pytest.mark.parametrize("frm,to,c", HAPPY)
def test_every_edge_allowed_with_right_context(frm, to, c):
    d = validate_transition(frm, to, c)
    assert d.allowed, d.reason


@pytest.mark.parametrize("frm,to,kind", [
    (S.SOURCE_ATTRIBUTION_PENDING, S.INVESTIGATION_REQUESTED, ApprovalKind.FIELD_INVESTIGATION),
    (S.VERIFICATION_PENDING, S.VERIFIED_REDUCTION, ApprovalKind.FINAL_CLOSURE),
    (S.INCONCLUSIVE, S.VERIFIED_REDUCTION, ApprovalKind.FINAL_CLOSURE),
    (S.STILL_LEAKING, S.INVESTIGATION_REQUESTED, ApprovalKind.FIELD_INVESTIGATION),
    (S.RECURRING, S.INVESTIGATION_REQUESTED, ApprovalKind.FIELD_INVESTIGATION),
])
def test_approval_edges_wait_for_human(frm, to, kind):
    c = ctx(verification_verdict=Verdict.VERIFIED_REDUCTION)
    d = validate_transition(frm, to, c)
    assert not d.allowed and d.requires_approval == kind


def test_repair_claim_can_never_close():
    for v in (None, Verdict.NO_INDEPENDENT_EVIDENCE, Verdict.VERIFIED_REDUCTION):
        d = validate_transition(S.REPAIR_REPORTED, S.VERIFIED_REDUCTION,
                                ctx(actor=ActorType.SIMULATED, verification_verdict=v, approval_granted=True))
        assert not d.allowed and d.requires_approval is None
        assert d.reason == NO_CLAIM_CLOSURE_REASON


def test_closure_from_verification_pending_needs_verified_verdict():
    for v in (None, Verdict.NO_INDEPENDENT_EVIDENCE):
        d = validate_transition(S.VERIFICATION_PENDING, S.VERIFIED_REDUCTION, ctx(verification_verdict=v, approval_granted=True))
        assert not d.allowed and d.reason == NO_CLAIM_CLOSURE_REASON
    d = validate_transition(S.VERIFICATION_PENDING, S.VERIFIED_REDUCTION,
                            ctx(verification_verdict=Verdict.INCONCLUSIVE, approval_granted=True))
    assert not d.allowed and "VERIFIED_REDUCTION" in d.reason


def test_inconclusive_and_still_leaking_guards():
    assert not validate_transition(S.VERIFICATION_PENDING, S.INCONCLUSIVE, ctx(verification_verdict=Verdict.STILL_LEAKING)).allowed
    assert not validate_transition(S.VERIFICATION_PENDING, S.STILL_LEAKING, ctx(verification_verdict=Verdict.INCONCLUSIVE)).allowed


def test_recurrence_requires_observation_above_threshold():
    assert not validate_transition(S.VERIFIED_REDUCTION, S.RECURRING, ctx(actor=ActorType.SATELLITE)).allowed
    assert validate_transition(S.VERIFIED_REDUCTION, S.RECURRING,
                               ctx(actor=ActorType.SATELLITE, observation_above_threshold=True)).allowed


def test_repair_report_must_come_from_operator_side():
    assert not validate_transition(S.INVESTIGATION_REQUESTED, S.REPAIR_REPORTED, ctx(actor=ActorType.AGENT)).allowed


def test_unknown_edges_forbidden_and_closed_status():
    assert not validate_transition(S.OPEN, S.REPAIR_REPORTED, ctx(actor=ActorType.SIMULATED)).allowed
    assert not validate_transition(S.VERIFIED_REDUCTION, S.OPEN, ctx()).allowed
    assert is_closed(S.VERIFIED_REDUCTION) and not is_closed(S.VERIFICATION_PENDING)
    assert S.VERIFIED_REDUCTION not in allowed_targets(S.REPAIR_REPORTED)
