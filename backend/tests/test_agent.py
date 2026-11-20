"""CaseAgent orchestration: approvals, evidence-gated closure, conflicts, reopening, LLM guardrails."""
import pytest

from plumeproof import db, kanjur
from plumeproof.agent import CaseAgent
from plumeproof.schemas import (
    ActorType,
    ApprovalDecision,
    ApprovalKind,
    ApprovalStatus,
    CaseStatus as S,
    DataLabel,
    Measurement,
    Verdict,
)
from plumeproof.state_machine import NO_CLAIM_CLOSURE_REASON

APPROVE = ApprovalDecision(decision="approve", decided_by="Test reviewer")


def m(id_, rate, u, independent=True, comparable=True):
    return Measurement(id=id_, rate_kg_h=rate, uncertainty_kg_h=u, date="2025-05-20", method="test survey",
                       independent=independent, comparable_conditions=comparable)


def pending(case_id, kind=None):
    return [a for a in db.list_approvals(case_id, ApprovalStatus.PENDING) if kind is None or a.kind == kind]


@pytest.fixture()
def agent(temp_db):
    for o in kanjur.REAL_OBSERVATIONS:
        db.save_observation(o)
    a = CaseAgent.open_case("T-1", "Test case", kanjur.FACILITY, [kanjur.OBS_2025_A, kanjur.OBS_2025_B],
                            kanjur.STAKEHOLDERS, pre_measurement=kanjur.PRE_MEASUREMENT, sim_date="2025-02-09")
    a.initialise_hypotheses()
    return a


def to_verification_pending(agent):
    """Drive the case: records request approved → fault found → attribution + notice approved → repair claim."""
    agent.propose_action("records_request")
    agent.decide(pending("T-1")[0].id, APPROVE)
    agent = CaseAgent.load("T-1")
    agent.update_beliefs("records_request", "fault_found")
    agent = CaseAgent.load("T-1")
    agent.decide(pending("T-1", ApprovalKind.SOURCE_ATTRIBUTION)[0].id, APPROVE)
    agent = CaseAgent.load("T-1")
    agent.decide(pending("T-1", ApprovalKind.NOTIFICATION)[0].id, APPROVE)
    agent = CaseAgent.load("T-1")
    decision = agent.report_repair(sim_date="2025-03-20")
    return CaseAgent.load("T-1"), decision


def test_open_case_records_tools_and_stakeholders(agent):
    assert agent.case.status == S.SOURCE_ATTRIBUTION_PENDING
    assert {c.tool.value for c in db.list_tool_calls("T-1")} >= {"query_observations", "overlay_facility_zones"}
    assert agent.case.stakeholders[0].name.startswith("Kanjur landfill operator")
    labels = {e.label for e in db.list_events("T-1") if e.type == "OBSERVATION_RECORDED"}
    assert labels == {DataLabel.REAL_DATA}


def test_investigation_needs_human_approval(agent):
    item = agent.propose_action("records_request")
    assert item is not None and item.status == ApprovalStatus.PENDING
    assert CaseAgent.load("T-1").case.status == S.SOURCE_ATTRIBUTION_PENDING  # nothing happens yet
    agent.decide(item.id, APPROVE)
    assert CaseAgent.load("T-1").case.status == S.INVESTIGATION_REQUESTED


def test_rejected_approval_does_not_advance(agent):
    item = agent.propose_action("ogi_survey")
    agent.decide(item.id, ApprovalDecision(decision="reject", note="too expensive"))
    a = CaseAgent.load("T-1")
    assert a.case.status == S.SOURCE_ATTRIBUTION_PENDING
    assert any(e.type == "PLAN_REVISED" for e in db.list_events("T-1"))


def test_repair_claim_never_closes(agent):
    agent, decision = to_verification_pending(agent)
    assert not decision.allowed and decision.reason == NO_CLAIM_CLOSURE_REASON
    assert agent.case.status == S.VERIFICATION_PENDING
    assert any(e.type == "TRANSITION_REJECTED" for e in db.list_events("T-1"))
    # Even a non-independent "measurement" from the operator cannot close it.
    agent.add_measurement(m("OP-1", 100, 10, independent=False))
    agent = CaseAgent.load("T-1")
    assert agent.case.verification.verdict == Verdict.NO_INDEPENDENT_EVIDENCE
    assert agent.case.status == S.VERIFICATION_PENDING
    assert not pending("T-1", ApprovalKind.FINAL_CLOSURE)


def test_conflicting_measurements_inconclusive(agent):
    agent, _ = to_verification_pending(agent)
    agent.add_measurement(m("M-1", 500, 100))
    agent = CaseAgent.load("T-1")
    agent.add_measurement(m("M-2", 1800, 100))
    agent = CaseAgent.load("T-1")
    assert agent.case.verification.conflicting
    assert agent.case.status == S.INCONCLUSIVE


def test_verified_reduction_needs_closure_approval_then_reopens(agent):
    agent, _ = to_verification_pending(agent)
    agent.add_measurement(m("M-1", 610, 150))
    agent = CaseAgent.load("T-1")
    assert agent.case.status == S.VERIFICATION_PENDING  # waits for the human
    closure = pending("T-1", ApprovalKind.FINAL_CLOSURE)
    assert len(closure) == 1
    agent.decide(closure[0].id, APPROVE)
    agent = CaseAgent.load("T-1")
    assert agent.case.status == S.VERIFIED_REDUCTION
    assert agent.case.recurrence_threshold_kg_h == pytest.approx(760)
    # A small later observation does not reopen; a large one does.
    small = kanjur.OBS_2026.model_copy(update={"id": "OBS-small", "rate_kg_h": 300.0})
    assert agent.observe(small) is False
    agent = CaseAgent.load("T-1")
    assert agent.observe(kanjur.OBS_2026) is True
    agent = CaseAgent.load("T-1")
    assert agent.case.status == S.RECURRING and agent.case.reopen_count == 1
    types = [e.type for e in db.list_events("T-1")]
    assert "CASE_REOPENED" in types
    assert any(e.type == "STATUS_CHANGED" and e.data.get("to") == "RECURRING" for e in db.list_events("T-1"))


def test_still_leaking_downweights_repaired_source(agent):
    agent, _ = to_verification_pending(agent)
    before = agent.case.belief["gas_collection"]
    agent.add_measurement(m("M-1", 1700, 150))
    agent = CaseAgent.load("T-1")
    assert agent.case.status == S.SOURCE_ATTRIBUTION_PENDING  # STILL_LEAKING → re-attribute
    assert agent.case.belief["gas_collection"] < before
    assert any(e.type == "STATUS_CHANGED" and e.data.get("to") == "STILL_LEAKING" for e in db.list_events("T-1"))


def test_llm_requested_transition_is_validated(agent):
    d = agent.request_transition(S.VERIFIED_REDUCTION, actor=ActorType.AGENT, requested_by_llm=True,
                                 reason="LLM thinks the leak is fixed")
    assert not d.allowed
    assert CaseAgent.load("T-1").case.status == S.SOURCE_ATTRIBUTION_PENDING
    ev = [e for e in db.list_events("T-1") if e.type == "TRANSITION_REJECTED"][-1]
    assert ev.data["requested_by_llm"] is True


def test_every_event_is_labelled(agent):
    to_verification_pending(agent)
    for e in db.list_events("T-1"):
        assert e.label in set(DataLabel) and e.actor_name and e.timestamp
