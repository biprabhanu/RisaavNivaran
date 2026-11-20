import pytest

from plumeproof import config
from plumeproof.planner import check_constraints, explain_plan, explain_replan, rank_actions, score
from plumeproof.schemas import ActionSpec, Constraints, OutcomeSpec

A = config.ACTIONS_BY_ID
P = config.DEFAULT_PRIOR


def ids(plan):
    return [r.action_id for r in plan.ranked]


def test_resource_unavailable_excluded_before_ranking():
    plan = rank_actions(P, config.ACTIONS, Constraints(unavailable_resources=["ogi_inspector"]))
    assert "ogi_survey" not in ids(plan)
    ex = {e.action_id: e for e in plan.excluded}
    assert ex["ogi_survey"].reason_codes == ["RESOURCE_UNAVAILABLE"]
    assert "OGI inspector" in ex["ogi_survey"].reasons[0]
    assert ex["ogi_survey"].eig_bits == pytest.approx(0.41, abs=0.02)  # still computed
    assert ids(plan) == ["records_request", "ground_survey", "satellite_wait"]


def test_authorisation_missing():
    codes, reasons = check_constraints(A["ground_survey"], Constraints(granted_authorisations=[]))
    assert codes == ["AUTHORISATION_MISSING"] and "site access permit" in reasons[0]


def test_safety():
    plan = rank_actions(P, config.ACTIONS, Constraints(safety_flags=["landfill_fire"]))
    assert set(ids(plan)) == {"records_request", "satellite_wait"}
    assert all("SAFETY" in e.reason_codes for e in plan.excluded)


def test_already_performed():
    plan = rank_actions(P, config.ACTIONS, Constraints(performed_actions=["records_request"]))
    assert "records_request" not in ids(plan)
    assert plan.excluded[0].reason_codes == ["ALREADY_PERFORMED"]


def test_allowed_has_no_reasons():
    assert check_constraints(A["records_request"], Constraints()) == ([], [])


def test_score_formula_and_lambda():
    assert score(0.5, 2000, 1, 1000) == pytest.approx(0.5 / 3000)
    assert score(0.0, 0, 30, 0) == 0.0  # zero denominator → 0
    p0 = rank_actions(P, config.ACTIONS, lam=0)
    p1 = rank_actions(P, config.ACTIONS, lam=5000)
    s0 = {r.action_id: r.score for r in p0.ranked}
    s1 = {r.action_id: r.score for r in p1.ranked}
    assert s0["ground_survey"] > s1["ground_survey"]
    sat = next(r for r in p0.ranked if r.action_id == "satellite_wait")
    assert sat.score == 0.0 and sat.effective_cost == 0.0


def test_default_ranking_order():
    assert ids(rank_actions(P, config.ACTIONS)) == ["records_request", "ogi_survey", "ground_survey", "satellite_wait"]


def test_tie_break_higher_eig_then_lower_cost():
    def act(id_, cost, p):
        return ActionSpec(id=id_, label=id_, description="", cost_inr=cost, time_days=0,
                          outcomes=[OutcomeSpec(id="y", label="y", likelihood={"a": p, "b": 1 - p}),
                                    OutcomeSpec(id="n", label="n", likelihood={"a": 1 - p, "b": p})])
    prior = {"a": 0.5, "b": 0.5}
    # Both zero-cost → score 0 for both; higher EIG should rank first.
    plan = rank_actions(prior, [act("weak", 0, 0.6), act("strong", 0, 0.9)], lam=0)
    assert ids(plan) == ["strong", "weak"]
    # Identical actions, different cost names with same score impossible; same EIG & cost 0 → lower cost wins
    plan2 = rank_actions(prior, [act("x", 0, 0.5), act("y", 0, 0.5)], lam=0)
    assert [r.rank for r in plan2.ranked] == [1, 2]


def test_no_informative_action_recommends_none():
    plan = rank_actions(P, config.ACTIONS, Constraints(performed_actions=["records_request", "ogi_survey", "ground_survey"]))
    assert plan.recommended_action_id is None
    assert "No informative action" in plan.explanation


def test_all_excluded():
    plan = rank_actions(P, [A["ogi_survey"]], Constraints(unavailable_resources=["ogi_inspector"]))
    assert plan.ranked == [] and plan.recommended_action_id is None
    assert "every action is excluded" in plan.explanation


def test_explanations_mention_key_facts():
    plan = rank_actions(P, config.ACTIONS)
    text = plan.explanation
    assert "Request flare and gas-collection records" in text and "₹2,000" in text
    assert "0.91" in text and "₹60,000" in text and "1.44 bits" in text
    after = rank_actions(P, config.ACTIONS, Constraints(unavailable_resources=["ogi_inspector"]))
    assert "Excluded before ranking" in after.explanation
    rp = explain_replan(plan, after)
    assert "OGI inspector" in rp and "Comprehensive ground-level survey" in rp
    assert "Still recommended first" in rp
    assert explain_plan(rank_actions(P, config.ACTIONS, lam=0)).count("λ = 0") == 1
