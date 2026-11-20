"""
Bayesian belief maths for PlumeProof (pure functions, no I/O).

CONTRACT STUB, to be implemented by the engine agent. Signatures are fixed.

Formulas (PDF slide 9):
    Entropy               H(P) = − Σ_h P(h) · log2 P(h)            (bits; 0·log 0 := 0)
    Outcome probability   P(y | a) = Σ_h P(y | h, a) · P(h)
    Bayes' rule           P(h | y, a) = P(y | h, a) · P(h) / P(y | a)
    Expected info gain    EIG(a) = H(P) − Σ_y P(y | a) · H(P(· | y, a))
"""
from __future__ import annotations

import random
from typing import Mapping, Sequence

from .schemas import ActionSpec, BayesUpdate, OutcomePreview


def normalise(belief: Mapping[str, float]) -> dict[str, float]:
    """Scale probabilities so they sum to 1. Raises ValueError if the total is 0 or a value is negative."""
    raise NotImplementedError


def entropy(belief: Mapping[str, float]) -> float:
    """Shannon entropy in bits."""
    raise NotImplementedError


def outcome_probability(prior: Mapping[str, float], likelihood: Mapping[str, float]) -> float:
    """P(y) = Σ_h P(y|h) P(h). ``likelihood`` maps hypothesis -> P(y|h)."""
    raise NotImplementedError


def bayes_update(prior: Mapping[str, float], likelihood: Mapping[str, float]) -> dict[str, float]:
    """Posterior P(h|y) ∝ P(y|h) P(h). Raises ValueError if P(y) == 0."""
    raise NotImplementedError


def update_with_outcome(prior: Mapping[str, float], action: ActionSpec, outcome_id: str) -> BayesUpdate:
    """Apply the observed outcome of ``action`` to ``prior``. KeyError if outcome_id unknown."""
    raise NotImplementedError


def outcome_previews(prior: Mapping[str, float], action: ActionSpec) -> list[OutcomePreview]:
    """For every outcome y of ``action``: P(y), the posterior, and the posterior entropy."""
    raise NotImplementedError


def expected_information_gain(prior: Mapping[str, float], action: ActionSpec) -> float:
    """EIG(a) = H(prior) − Σ_y P(y) H(posterior_y). Always ≥ 0 (clip tiny negatives to 0)."""
    raise NotImplementedError


def perturb_actions(actions: Sequence[ActionSpec], rel: float = 0.2, rng: random.Random | None = None) -> list[ActionSpec]:
    """
    Sensitivity analysis helper: return deep copies of ``actions`` in which every likelihood
    P(y|h,a) is multiplied by an independent factor drawn uniformly from [1 − rel, 1 + rel],
    then each (a, h) column is renormalised so Σ_y P(y|h,a) = 1 again. Costs/times unchanged.
    """
    raise NotImplementedError
