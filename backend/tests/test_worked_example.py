"""
Reproduce the worked example on slide 10 of RisaavNivaran.pdf.

Every number is COMPUTED from config.DEFAULT_PRIOR and the likelihood tables in config.ACTIONS.
Nothing is hard-coded except the PDF targets we compare against.
"""
import pytest

from plumeproof import config
from plumeproof.bayes import entropy, expected_information_gain, outcome_previews, update_with_outcome
from plumeproof.planner import rank_actions

A = config.ACTIONS_BY_ID
P = config.DEFAULT_PRIOR
W, G, F = config.WASTE, config.GAS, config.FLARE


def test_initial_entropy():
    assert entropy(P) == pytest.approx(1.44, abs=0.005)  # PDF: "Initial entropy: 1.44 bits"


@pytest.mark.parametrize("action_id,pdf_eig", [
    ("records_request", 0.50),  # PDF: 0.50 bits
    ("ogi_survey", 0.41),       # PDF: 0.41 bits
    ("ground_survey", 0.91),    # PDF: 0.91 bits
])
def test_eig_matches_pdf(action_id, pdf_eig):
    assert expected_information_gain(P, A[action_id]) == pytest.approx(pdf_eig, abs=0.02)


def test_satellite_wait_is_uninformative():
    assert expected_information_gain(P, A["satellite_wait"]) < 0.01  # PDF: "approx. 0 bits"


def test_gain_per_10k_and_ranking():
    plan = rank_actions(P, config.ACTIONS)
    by_id = {r.action_id: r for r in plan.ranked}
    assert by_id["records_request"].gain_per_10k == pytest.approx(2.50, abs=0.02)  # PDF: 2.50
    assert by_id["ogi_survey"].gain_per_10k == pytest.approx(0.17, abs=0.02)       # PDF: 0.17
    assert by_id["ground_survey"].gain_per_10k == pytest.approx(0.15, abs=0.02)    # PDF: 0.15
    assert by_id["satellite_wait"].gain_per_10k is None                            # PDF: "none"
    assert plan.ranked[0].action_id == "records_request"  # PDF: records request "ranked first"
    assert plan.recommended_action_id == "records_request"


def test_records_first_at_lambda_zero():
    plan = rank_actions(P, config.ACTIONS, lam=0)
    assert plan.ranked[0].action_id == "records_request"


def test_fault_found_probability_and_posterior():
    previews = {o.outcome_id: o for o in outcome_previews(P, A["records_request"])}
    fault = previews["fault_found"]
    assert fault.probability == pytest.approx(0.43, abs=0.01)  # PDF: "probability 43%"
    assert fault.posterior[G] == pytest.approx(0.65, abs=0.01)  # PDF: gas-collection 65%
    assert fault.posterior[F] == pytest.approx(0.29, abs=0.01)  # PDF: flare 29%
    assert fault.posterior[W] == pytest.approx(0.06, abs=0.01)  # PDF: waste surface 6%
    # Same numbers via the update path the agent uses.
    upd = update_with_outcome(P, A["records_request"], "fault_found")
    assert upd.posterior[G] == pytest.approx(fault.posterior[G])


def test_no_fault_posterior():
    no_fault = {o.outcome_id: o for o in outcome_previews(P, A["records_request"])}["no_fault"]
    assert no_fault.probability == pytest.approx(0.57, abs=0.01)  # PDF: "probability 57%"
    assert no_fault.posterior[W] == pytest.approx(0.84, abs=0.01)  # PDF: waste surface rises to 84%


def test_print_worked_example(capsys):
    """Not an assertion test: prints the computed table (run `pytest -s` to see it)."""
    plan = rank_actions(P, config.ACTIONS)
    print(f"\nH(prior) = {entropy(P):.4f} bits")
    for r in plan.ranked:
        print(f"#{r.rank} {r.action_id:16s} EIG={r.eig_bits:.4f} gain/10k={r.gain_per_10k} score/10k={r.score_per_10k:.4f}")
    for o in outcome_previews(P, A["records_request"]):
        print(o.outcome_id, round(o.probability, 4), {k: round(v, 4) for k, v in o.posterior.items()})
