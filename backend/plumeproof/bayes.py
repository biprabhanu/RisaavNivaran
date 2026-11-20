"""
Bayesian belief maths for PlumeProof (pure functions, no I/O).

Plain-English summary
---------------------
The agent does not know which part of the landfill is leaking, so it keeps a probability for
each candidate source (a "belief"). When an investigation returns a result, Bayes' rule
re-weights each candidate by how well it explains that result. Entropy measures how uncertain
the belief still is, in bits. Expected information gain (EIG) is how many bits of uncertainty
an action is expected to remove *before* we pay for it.

Formulas (PDF slide 9):
    Entropy               H(P) = − Σ_h P(h) · log2 P(h)            (bits; 0·log 0 := 0)
    Outcome probability   P(y | a) = Σ_h P(y | h, a) · P(h)
    Bayes' rule           P(h | y, a) = P(y | h, a) · P(h) / P(y | a)
    Expected info gain    EIG(a) = H(P) − Σ_y P(y | a) · H(P(· | y, a))

Worked intuition: with prior 50/35/15 the entropy is 1.44 bits. A records request either finds
a gas-system fault (P ≈ 0.43, which leaves us fairly sure it is gas/flare) or finds nothing
(P ≈ 0.57, which leaves us fairly sure it is the waste surface). On average this removes ≈ 0.50 bits.
"""
from __future__ import annotations

import copy
import math
import random
from typing import Mapping, Sequence

from .schemas import ActionSpec, BayesUpdate, OutcomePreview


def normalise(belief: Mapping[str, float]) -> dict[str, float]:
    """
    Scale probabilities so they sum to 1:  P'(h) = P(h) / Σ_k P(k).

    Raises ValueError if any value is negative or the total is 0 (nothing to normalise).
    """
    for h, p in belief.items():
        if p < 0:
            raise ValueError(f"Negative probability for {h!r}: {p}")
    total = sum(belief.values())
    if total <= 0:
        raise ValueError("Cannot normalise a belief whose probabilities sum to 0.")
    return {h: p / total for h, p in belief.items()}


def entropy(belief: Mapping[str, float]) -> float:
    """
    Shannon entropy in bits:  H = − Σ_h P(h) · log2 P(h).

    0 bits means we are certain; log2(3) ≈ 1.585 bits is maximal confusion among 3 sources.
    Terms with P(h) = 0 contribute 0 (the limit of p·log p as p → 0).
    """
    return -sum(p * math.log2(p) for p in belief.values() if p > 0)


def outcome_probability(prior: Mapping[str, float], likelihood: Mapping[str, float]) -> float:
    """
    Total probability of seeing an outcome y:  P(y) = Σ_h P(y|h) · P(h).

    ``likelihood`` maps hypothesis -> P(y|h). It is a weighted average of how likely each
    hypothesis makes this outcome, weighted by how much we currently believe that hypothesis.
    """
    return sum(likelihood[h] * p for h, p in prior.items())


def bayes_update(prior: Mapping[str, float], likelihood: Mapping[str, float]) -> dict[str, float]:
    """
    Bayes' rule:  P(h|y) = P(y|h) · P(h) / P(y).

    Each hypothesis is re-weighted by how well it predicted what we actually saw, then the
    result is rescaled to sum to 1. Raises ValueError if P(y) == 0 (the outcome was "impossible").
    """
    p_y = outcome_probability(prior, likelihood)
    if p_y <= 0:
        raise ValueError("Outcome has zero probability under the current belief; cannot update.")
    return {h: likelihood[h] * p / p_y for h, p in prior.items()}


def _find_outcome(action: ActionSpec, outcome_id: str):
    for o in action.outcomes:
        if o.id == outcome_id:
            return o
    raise KeyError(f"Action {action.id!r} has no outcome {outcome_id!r}")


def update_with_outcome(prior: Mapping[str, float], action: ActionSpec, outcome_id: str) -> BayesUpdate:
    """Apply the observed outcome of ``action`` to ``prior``. KeyError if outcome_id is unknown."""
    outcome = _find_outcome(action, outcome_id)
    posterior = bayes_update(prior, outcome.likelihood)
    return BayesUpdate(
        action_id=action.id,
        outcome_id=outcome_id,
        prior=dict(prior),
        posterior=posterior,
        entropy_before=entropy(prior),
        entropy_after=entropy(posterior),
        outcome_probability=outcome_probability(prior, outcome.likelihood),
    )


def outcome_previews(prior: Mapping[str, float], action: ActionSpec) -> list[OutcomePreview]:
    """
    "What if" table for one action: for each outcome y, its probability P(y), the posterior
    P(h|y) we would hold, and that posterior's entropy. Outcomes with P(y) = 0 keep the prior.
    """
    previews: list[OutcomePreview] = []
    for o in action.outcomes:
        p_y = outcome_probability(prior, o.likelihood)
        posterior = bayes_update(prior, o.likelihood) if p_y > 0 else dict(prior)
        previews.append(OutcomePreview(
            outcome_id=o.id, label=o.label, probability=p_y,
            posterior=posterior, entropy_after=entropy(posterior),
        ))
    return previews


def expected_information_gain(prior: Mapping[str, float], action: ActionSpec) -> float:
    """
    EIG(a) = H(prior) − Σ_y P(y) · H(posterior_y).

    "Uncertainty now" minus "uncertainty we expect to have after seeing the result, averaged
    over all results the action could give". An action whose outcomes are equally likely under
    every hypothesis (e.g. waiting for a satellite pass) has EIG = 0: it cannot tell sources apart.
    Tiny negative values from floating-point rounding are clipped to 0.
    """
    h_now = entropy(prior)
    expected_after = sum(p.probability * p.entropy_after for p in outcome_previews(prior, action))
    return max(0.0, h_now - expected_after)


def perturb_actions(actions: Sequence[ActionSpec], rel: float = 0.2, rng: random.Random | None = None) -> list[ActionSpec]:
    """
    Sensitivity analysis helper: return deep copies of ``actions`` in which every likelihood
    P(y|h,a) is multiplied by an independent factor drawn uniformly from [1 − rel, 1 + rel],
    then each (a, h) column is renormalised so Σ_y P(y|h,a) = 1 again. Costs/times unchanged.

    Pass a seeded ``random.Random`` for reproducible results.
    """
    rng = rng or random.Random()
    out: list[ActionSpec] = []
    for action in actions:
        a = copy.deepcopy(action)
        if a.outcomes:
            hyps = list(a.outcomes[0].likelihood.keys())
            for o in a.outcomes:
                for h in hyps:
                    o.likelihood[h] = o.likelihood[h] * rng.uniform(1 - rel, 1 + rel)
            for h in hyps:  # renormalise each hypothesis column over outcomes
                col = sum(o.likelihood[h] for o in a.outcomes)
                for o in a.outcomes:
                    o.likelihood[h] = o.likelihood[h] / col if col > 0 else 1.0 / len(a.outcomes)
        out.append(a)
    return out
