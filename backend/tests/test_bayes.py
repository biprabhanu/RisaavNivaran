import math
import random

import pytest

from plumeproof import config
from plumeproof.bayes import (bayes_update, entropy, expected_information_gain, normalise,
                              outcome_probability, perturb_actions)


def test_normalise():
    assert normalise({"a": 2, "b": 2}) == {"a": 0.5, "b": 0.5}
    with pytest.raises(ValueError):
        normalise({"a": 0, "b": 0})
    with pytest.raises(ValueError):
        normalise({"a": -1, "b": 2})


def test_entropy_basics():
    assert entropy({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}) == pytest.approx(math.log2(3))
    assert entropy({"a": 1.0, "b": 0.0}) == 0.0
    assert entropy({"a": 0.5, "b": 0.5}) == pytest.approx(1.0)


def test_bayes_update_by_hand():
    prior = {"x": 0.5, "y": 0.5}
    lik = {"x": 0.9, "y": 0.1}
    assert outcome_probability(prior, lik) == pytest.approx(0.5)
    post = bayes_update(prior, lik)
    assert post["x"] == pytest.approx(0.9)
    assert sum(post.values()) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        bayes_update(prior, {"x": 0.0, "y": 0.0})


def test_eig_nonnegative_and_bounded():
    for a in config.ACTIONS:
        e = expected_information_gain(config.DEFAULT_PRIOR, a)
        assert 0.0 <= e <= entropy(config.DEFAULT_PRIOR) + 1e-9


def test_eig_zero_when_certain():
    certain = {config.WASTE: 1.0, config.GAS: 0.0, config.FLARE: 0.0}
    for a in config.ACTIONS:
        assert expected_information_gain(certain, a) == pytest.approx(0.0, abs=1e-12)


def test_perturb_actions_columns_sum_to_one_and_reproducible():
    p1 = perturb_actions(config.ACTIONS, 0.2, random.Random(7))
    p2 = perturb_actions(config.ACTIONS, 0.2, random.Random(7))
    for a1, a2, orig in zip(p1, p2, config.ACTIONS):
        assert a1.model_dump() == a2.model_dump()
        assert a1.cost_inr == orig.cost_inr and a1.time_days == orig.time_days
        for h in config.HYPOTHESIS_IDS:
            assert sum(o.likelihood[h] for o in a1.outcomes) == pytest.approx(1.0)
    # originals untouched
    assert config.ACTIONS_BY_ID["records_request"].outcomes[0].likelihood[config.WASTE] == 0.05
