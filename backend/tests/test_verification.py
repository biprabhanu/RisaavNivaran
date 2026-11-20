import pytest

from plumeproof.schemas import Measurement, Verdict
from plumeproof.verification import (combine_measurements, evaluate_verification, interval, intervals_overlap,
                                     is_recurrence, recurrence_threshold)


def m(id_, rate, u, independent=True, comparable=True):
    return Measurement(id=id_, rate_kg_h=rate, uncertainty_kg_h=u, date="2025-05-20", method="test",
                       independent=independent, comparable_conditions=comparable)


PRE = m("pre", 1736, 434)


def test_kanjur_verified_and_recurrence():
    r = evaluate_verification(PRE, [m("post", 610, 150)])
    assert r.verdict == Verdict.VERIFIED_REDUCTION
    assert r.pre_low == pytest.approx(1302) and r.post_high == pytest.approx(760)
    assert r.recurrence_threshold_kg_h == pytest.approx(760)
    assert recurrence_threshold(r) == pytest.approx(760)
    assert is_recurrence(3300, recurrence_threshold(r))  # 3 Apr 2026: ~3,300 kg/h
    assert not is_recurrence(700, 760)
    assert not is_recurrence(5000, None)
    assert any("760" in s and "1,302" in s for s in r.reasons)


def test_still_leaking():
    r = evaluate_verification(PRE, [m("post", 1500, 100)])
    assert r.verdict == Verdict.STILL_LEAKING
    assert recurrence_threshold(r) is None


def test_overlap_inconclusive():
    r = evaluate_verification(PRE, [m("post", 1200, 300)])  # [900, 1500] overlaps [1302, 2170]
    assert r.verdict == Verdict.INCONCLUSIVE and not r.conflicting


def test_operator_claim_only():
    r = evaluate_verification(PRE, [m("claim", 0, 0, independent=False)])
    assert r.verdict == Verdict.NO_INDEPENDENT_EVIDENCE
    assert r.measurements_ignored == ["claim"] and r.measurements_used == []
    r2 = evaluate_verification(PRE, [])
    assert r2.verdict == Verdict.NO_INDEPENDENT_EVIDENCE


def test_claim_ignored_when_mixed():
    r = evaluate_verification(PRE, [m("claim", 0, 0, independent=False), m("post", 610, 150)])
    assert r.verdict == Verdict.VERIFIED_REDUCTION
    assert r.measurements_ignored == ["claim"] and r.measurements_used == ["post"]


def test_conflicting():
    r = evaluate_verification(PRE, [m("a", 400, 100), m("b", 1600, 100)])
    assert r.verdict == Verdict.INCONCLUSIVE and r.conflicting


def test_not_comparable():
    r = evaluate_verification(PRE, [m("post", 610, 150, comparable=False)])
    assert r.verdict == Verdict.INCONCLUSIVE
    pre_bad = m("pre", 1736, 434, comparable=False)
    assert evaluate_verification(pre_bad, [m("post", 610, 150)]).verdict == Verdict.INCONCLUSIVE


def test_inverse_variance_combination():
    mean, u = combine_measurements([m("a", 600, 100), m("b", 700, 200)])
    # weights 1/100² and 1/200² → 4:1
    assert mean == pytest.approx((4 * 600 + 700) / 5)
    assert u == pytest.approx(1 / (1 / 100**2 + 1 / 200**2) ** 0.5)
    r = evaluate_verification(PRE, [m("a", 600, 100), m("b", 700, 200)])
    assert r.post_rate == pytest.approx(620) and r.verdict == Verdict.VERIFIED_REDUCTION


def test_interval_helpers():
    assert interval(m("x", 100, 10)) == (90, 110)
    assert intervals_overlap(m("a", 100, 10), m("b", 115, 5))
    assert not intervals_overlap(m("a", 100, 10), m("b", 130, 5))


def test_min_recurrence_floor():
    r = evaluate_verification(PRE, [m("post", 20, 10)])
    assert r.verdict == Verdict.VERIFIED_REDUCTION and r.recurrence_threshold_kg_h == 100
