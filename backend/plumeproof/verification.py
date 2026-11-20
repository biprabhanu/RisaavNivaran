"""
Evidence-gated verification (PDF slide 9, "Novelty 2").

Plain-English summary
---------------------
Every measurement is a rate with an uncertainty, i.e. an interval [rate − u, rate + u].
We only say emissions went down if the WHOLE post-repair interval sits below the WHOLE
pre-repair interval:

        post + u_post  <  pre − u_pre        →  VERIFIED_REDUCTION

and only if the post measurement is independent (not the operator's own claim) and was taken
under comparable conditions. Anything weaker is not proof.

Rule order (see docs/ASSUMPTIONS.md §4):
  1. Ignore non-independent posts (e.g. operator claims). None left → NO_INDEPENDENT_EVIDENCE.
  2. Any two independent posts whose intervals [x−u, x+u] do not overlap → INCONCLUSIVE (conflicting=True).
  3. Any independent post with comparable_conditions=False (or pre not comparable) → INCONCLUSIVE.
  4. Combine posts by inverse-variance weighting: x̄ = Σ(x/u²)/Σ(1/u²), ū = 1/√Σ(1/u²).
  5. post + u_post < pre − u_pre → VERIFIED_REDUCTION (recurrence_threshold = max(post+u_post, MIN_RECURRENCE_KG_H)).
  6. post ≥ pre − u_pre → STILL_LEAKING.
  7. Otherwise → INCONCLUSIVE (intervals overlap).

Kanjur example: pre 1,736 ± 434 → [1,302, 2,170]; post 610 ± 150 → [460, 760].
760 < 1,302, so it is a verified reduction, and any later observation above 760 kg/h reopens the case.
"""
from __future__ import annotations

import math
from itertools import combinations
from typing import Sequence

from .config import MIN_RECURRENCE_KG_H
from .schemas import Measurement, Verdict, VerificationResult

RULE_TEXT = "VERIFIED_REDUCTION iff (post + u_post) < (pre − u_pre) under comparable conditions with independent evidence"


def _kg(x: float) -> str:
    return f"{x:,.0f} kg/h"


def interval(m: Measurement) -> tuple[float, float]:
    """(rate − u, rate + u)."""
    return (m.rate_kg_h - m.uncertainty_kg_h, m.rate_kg_h + m.uncertainty_kg_h)


def intervals_overlap(a: Measurement, b: Measurement) -> bool:
    """Two intervals overlap if neither lies entirely above the other."""
    a_lo, a_hi = interval(a)
    b_lo, b_hi = interval(b)
    return a_lo <= b_hi and b_lo <= a_hi


def combine_measurements(ms: Sequence[Measurement]) -> tuple[float, float]:
    """
    Inverse-variance weighted mean and its uncertainty. A u of 0 is treated as 1e-6.

        weight_i = 1 / u_i²      x̄ = Σ w_i x_i / Σ w_i      ū = 1 / √(Σ w_i)

    More precise measurements (smaller u) count for more, and combining measurements
    makes the result more precise than any single one.
    """
    if not ms:
        raise ValueError("No measurements to combine.")
    weights = [1.0 / max(m.uncertainty_kg_h, 1e-6) ** 2 for m in ms]
    total = sum(weights)
    mean = sum(w * m.rate_kg_h for w, m in zip(weights, ms)) / total
    return mean, 1.0 / math.sqrt(total)


def evaluate_verification(pre: Measurement, posts: Sequence[Measurement]) -> VerificationResult:
    """Apply the 7-step evidence-gated rule (module docstring) and explain the verdict."""
    pre_lo, pre_hi = interval(pre)
    base = dict(
        pre_rate=pre.rate_kg_h, pre_uncertainty=pre.uncertainty_kg_h,
        pre_low=pre_lo, pre_high=pre_hi, rule=RULE_TEXT,
    )
    independent = [m for m in posts if m.independent]
    ignored = [m.id for m in posts if not m.independent]
    reasons: list[str] = []
    if ignored:
        reasons.append(f"Ignored {len(ignored)} non-independent report(s) ({', '.join(ignored)}): "
                       "a claim is not a measurement.")

    # 1. No independent evidence at all.
    if not independent:
        reasons.append("No independent post-intervention measurement: the case stays VERIFICATION_PENDING.")
        return VerificationResult(verdict=Verdict.NO_INDEPENDENT_EVIDENCE, measurements_ignored=ignored,
                                  reasons=reasons, **base)

    used = [m.id for m in independent]

    # 2. Conflicting independent measurements.
    for a, b in combinations(independent, 2):
        if not intervals_overlap(a, b):
            a_lo, a_hi = interval(a)
            b_lo, b_hi = interval(b)
            reasons.append(
                f"Conflicting measurements: {a.id} [{_kg(a_lo)}, {_kg(a_hi)}] and {b.id} "
                f"[{_kg(b_lo)}, {_kg(b_hi)}] do not overlap. Both are retained; more evidence is needed."
            )
            return VerificationResult(verdict=Verdict.INCONCLUSIVE, conflicting=True, measurements_used=used,
                                      measurements_ignored=ignored, reasons=reasons, **base)

    # 3. Non-comparable conditions.
    bad = [m.id for m in independent if not m.comparable_conditions]
    if bad or not pre.comparable_conditions:
        who = ", ".join(bad) if bad else f"pre-intervention {pre.id}"
        reasons.append(f"Measurement conditions not comparable ({who}): the reduction cannot be attributed to the repair.")
        return VerificationResult(verdict=Verdict.INCONCLUSIVE, measurements_used=used,
                                  measurements_ignored=ignored, reasons=reasons, **base)

    # 4. Combine.
    post, u_post = combine_measurements(independent)
    post_lo, post_hi = post - u_post, post + u_post
    post_fields = dict(post_rate=post, post_uncertainty=u_post, post_low=post_lo, post_high=post_hi)
    if len(independent) > 1:
        reasons.append(f"Combined {len(independent)} independent measurements (inverse-variance): "
                       f"{_kg(post)} ± {u_post:,.0f}.")

    # 5. Verified reduction.
    if post_hi < pre_lo:
        threshold = max(post_hi, MIN_RECURRENCE_KG_H)
        reasons.append(f"Post upper bound {_kg(post_hi)} < pre lower bound {_kg(pre_lo)}: "
                       "the reduction is larger than the measurement uncertainty.")
        reasons.append(f"Recurrence threshold set to {_kg(threshold)}: any later observation above it reopens the case.")
        return VerificationResult(verdict=Verdict.VERIFIED_REDUCTION, measurements_used=used,
                                  measurements_ignored=ignored, reasons=reasons,
                                  recurrence_threshold_kg_h=threshold, **post_fields, **base)

    # 6. Still leaking.
    if post >= pre_lo:
        reasons.append(f"Post estimate {_kg(post)} ≥ pre lower bound {_kg(pre_lo)}: no demonstrable reduction.")
        return VerificationResult(verdict=Verdict.STILL_LEAKING, measurements_used=used,
                                  measurements_ignored=ignored, reasons=reasons, **post_fields, **base)

    # 7. Overlap.
    reasons.append(f"Post estimate {_kg(post)} is below the pre interval, but its upper bound {_kg(post_hi)} "
                   f"≥ pre lower bound {_kg(pre_lo)}: the intervals overlap, so the reduction is not proven.")
    return VerificationResult(verdict=Verdict.INCONCLUSIVE, measurements_used=used,
                              measurements_ignored=ignored, reasons=reasons, **post_fields, **base)


def recurrence_threshold(result: VerificationResult) -> float | None:
    """max(post_high, MIN_RECURRENCE_KG_H) for VERIFIED_REDUCTION results, else None."""
    if result.verdict != Verdict.VERIFIED_REDUCTION or result.post_high is None:
        return None
    return max(result.post_high, MIN_RECURRENCE_KG_H)


def is_recurrence(rate_kg_h: float, threshold_kg_h: float | None) -> bool:
    """True if a new observation's rate is strictly above the threshold (False if threshold is None)."""
    if threshold_kg_h is None:
        return False
    return rate_kg_h > threshold_kg_h
