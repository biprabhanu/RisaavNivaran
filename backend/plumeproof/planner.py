"""
Evidence Planner: choose the next investigation (PDF slide 9, "Novelty 1").

CONTRACT STUB, to be implemented by the engine agent. Signatures are fixed.

    1. Exclude actions that violate a constraint (BEFORE ranking):
         RESOURCE_UNAVAILABLE  - an action resource is in constraints.unavailable_resources
         AUTHORISATION_MISSING - action.authorisation not in constraints.granted_authorisations
         SAFETY                - any of action.unsafe_when is in constraints.safety_flags
         ALREADY_PERFORMED     - action.id in constraints.performed_actions
    2. For the rest compute EIG(a) (bayes.expected_information_gain) and
         score(a) = EIG(a) / (cost_a + λ · time_a)
       If cost + λ·time == 0, score = 0.
    3. Sort by score descending (ties: higher EIG first, then lower cost). rank 1 = best.
    4. Also report gain_per_10k = EIG / cost × 10,000 (None if cost == 0).
"""
from __future__ import annotations

from typing import Mapping, Sequence

from .config import DEFAULT_LAMBDA
from .schemas import ActionSpec, Constraints, PlanResult


def check_constraints(action: ActionSpec, constraints: Constraints) -> tuple[list[str], list[str]]:
    """Return (reason_codes, human_readable_reasons). Both empty = the action is allowed."""
    raise NotImplementedError


def score(eig_bits: float, cost_inr: float, time_days: float, lam: float) -> float:
    """score = EIG / (cost + λ·time), or 0 when the denominator is 0."""
    raise NotImplementedError


def rank_actions(
    belief: Mapping[str, float],
    actions: Sequence[ActionSpec],
    constraints: Constraints | None = None,
    lam: float = DEFAULT_LAMBDA,
) -> PlanResult:
    """Filter, score and rank. Fills PlanResult.explanation with explain_plan(...)."""
    raise NotImplementedError


def explain_plan(plan: PlanResult) -> str:
    """
    Deterministic plain-English explanation of the ranking (no LLM). Must mention: the top action,
    its EIG/cost/time and gain per ₹10k; the action with the highest raw EIG if different and why it
    ranks lower; any excluded actions and why; and the current entropy.
    """
    raise NotImplementedError


def explain_replan(before: PlanResult, after: PlanResult) -> str:
    """
    Deterministic trade-off explanation after a re-rank (e.g. an inspector became unavailable):
    which actions were newly excluded, what replaced them, and the cost/time/information trade-off.
    """
    raise NotImplementedError
