"""Tests for the evaluation simulator (plumeproof.scenarios)."""
from __future__ import annotations

import time

import pytest

from plumeproof import scenarios as sim
from plumeproof.schemas import ActorType, CaseStatus, EvaluationReport, TransitionContext
from plumeproof.state_machine import validate_transition


@pytest.fixture(scope="module")
def report() -> EvaluationReport:
    return sim.run_evaluation(seed=2026, n_scenarios=25)


def _strip(rep: EvaluationReport) -> dict:
    d = rep.model_dump()
    d.pop("generated_at")
    return d


def test_deterministic_same_seed():
    a = sim.run_evaluation(seed=2026, n_scenarios=25)
    b = sim.run_evaluation(seed=2026, n_scenarios=25)
    assert _strip(a) == _strip(b)


def test_different_seed_changes_scenarios():
    a = sim.generate_scenarios(seed=1, n=25)
    b = sim.generate_scenarios(seed=2, n=25)
    assert [s.true_source for s in a] != [s.true_source for s in b] or [s.e0_kg_h for s in a] != [s.e0_kg_h for s in b]


def test_25_scenarios_with_every_tag_and_some_plain():
    scs = sim.generate_scenarios(seed=2026, n=25)
    assert len(scs) == 25
    for tag in sim.TAGS:
        assert sum(tag in s.tags for s in scs) >= 3, tag
    assert sum(not s.tags for s in scs) >= 3


def test_report_validates(report):
    EvaluationReport.model_validate(report.model_dump())
    assert {m.policy_id for m in report.policies} == {"A", "B", "C", "C_noplan"}
    assert report.n_scenarios == 25 and len(report.scenarios) == 25


def test_plumeproof_has_zero_false_closures(report):
    by = {m.policy_id: m for m in report.policies}
    assert by["C"].false_closures == 0
    assert by["C_noplan"].false_closures == 0
    assert report.sensitivity.c_false_closures_perturbed == 0


def test_baselines_close_on_claims(report):
    by = {m.policy_id: m for m in report.policies}
    # A and B close on operator claims, which the state machine forbids:
    d = validate_transition(CaseStatus.REPAIR_REPORTED, CaseStatus.VERIFIED_REDUCTION,
                            TransitionContext(actor=ActorType.SIMULATED))
    assert not d.allowed
    assert by["A"].false_closures > 0 and by["B"].false_closures > 0


def test_c_policies_only_use_allowed_transitions():
    for sc in sim.generate_scenarios(seed=2026, n=25):
        for fn in (sim.run_policy_c, sim.run_policy_c_noplan):
            run = fn(sc)
            for frm, to, ctx in run.transitions:
                assert validate_transition(frm, to, ctx).allowed, (sc.scenario_id, frm, to)
            # No closure without an independent verified verdict
            if run.closed_ever:
                assert run.closure_evidence_ok
            closures = [t for t in run.transitions if t[1] == CaseStatus.VERIFIED_REDUCTION]
            assert all(t[0] != CaseStatus.REPAIR_REPORTED for t in closures)


def test_recurrence_reopens_in_c():
    for sc in sim.generate_scenarios(seed=2026, n=25):
        run = sim.run_policy_c(sc)
        if sc.has("recurrence") and run.closed_ever:
            assert run.status == CaseStatus.RECURRING and run.reopened


def test_kendall_tau():
    assert sim.kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert sim.kendall_tau(["a", "b", "c"], ["c", "b", "a"]) == -1.0


def test_traceability_rule():
    ok = sim.Decision("x", "closure", ["VERDICT-VR-1"], "Human reviewer", 0)
    no_approval = sim.Decision("x", "closure", ["VERDICT-VR-1"], None, 0)
    claim_only = sim.Decision("x", "closure", ["CLAIM-1"], "Checklist sign-off", 0)
    assert sim.is_traceable(ok) and not sim.is_traceable(no_approval) and not sim.is_traceable(claim_only)


def test_runtime_under_5_seconds():
    t0 = time.perf_counter()
    sim.run_evaluation(seed=7, n_scenarios=25)
    assert time.perf_counter() - t0 < 5.0
