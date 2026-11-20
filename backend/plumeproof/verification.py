"""
Evidence-gated verification (PDF slide 9, "Novelty 2").

CONTRACT STUB, to be implemented by the engine agent. Signatures are fixed.

Rule order (see docs/ASSUMPTIONS.md §4):
  1. Ignore non-independent posts (e.g. operator claims). None left → NO_INDEPENDENT_EVIDENCE.
  2. Any two independent posts whose intervals [x−u, x+u] do not overlap → INCONCLUSIVE (conflicting=True).
  3. Any independent post with comparable_conditions=False (or pre not comparable) → INCONCLUSIVE.
  4. Combine posts by inverse-variance weighting: x̄ = Σ(x/u²)/Σ(1/u²), ū = 1/√Σ(1/u²).
  5. post + u_post < pre − u_pre → VERIFIED_REDUCTION (recurrence_threshold = max(post+u_post, MIN_RECURRENCE_KG_H)).
  6. post ≥ pre − u_pre → STILL_LEAKING.
  7. Otherwise → INCONCLUSIVE (intervals overlap).
"""
from __future__ import annotations

from typing import Sequence

from .schemas import Measurement, VerificationResult


def interval(m: Measurement) -> tuple[float, float]:
    """(rate − u, rate + u)."""
    raise NotImplementedError


def intervals_overlap(a: Measurement, b: Measurement) -> bool:
    raise NotImplementedError


def combine_measurements(ms: Sequence[Measurement]) -> tuple[float, float]:
    """Inverse-variance weighted mean and its uncertainty. A u of 0 is treated as 1e-6."""
    raise NotImplementedError


def evaluate_verification(pre: Measurement, posts: Sequence[Measurement]) -> VerificationResult:
    raise NotImplementedError


def recurrence_threshold(result: VerificationResult) -> float | None:
    """max(post_high, MIN_RECURRENCE_KG_H) for VERIFIED_REDUCTION results, else None."""
    raise NotImplementedError


def is_recurrence(rate_kg_h: float, threshold_kg_h: float | None) -> bool:
    """True if a new observation's rate is strictly above the threshold (False if threshold is None)."""
    raise NotImplementedError
