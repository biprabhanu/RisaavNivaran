"""
Evidence Planner: choose the next investigation (PDF slide 9, "Novelty 1").

Plain-English summary
---------------------
Every possible investigation buys some information (EIG, in bits) at some price (rupees)
and some delay (days). The planner:

    1. Excludes actions that violate a constraint, BEFORE ranking:
         RESOURCE_UNAVAILABLE  - one of the action's resources is in constraints.unavailable_resources
         AUTHORISATION_MISSING - action.authorisation is not in constraints.granted_authorisations
         SAFETY                - one of action.unsafe_when is in constraints.safety_flags
         ALREADY_PERFORMED     - action.id is in constraints.performed_actions
    2. For each remaining action computes EIG(a) (bayes.expected_information_gain) and

           score(a) = EIG(a) / (cost_a + λ · time_a)

       λ ("lambda", ₹ per day) converts delay into money, so that one score trades off
       information, cost and time. If cost + λ·time == 0, score = 0 (free and instant only
       happens for no-op actions, and an action with no price is ranked by nothing).
    3. Sorts by score, highest first (ties: higher EIG first, then lower cost). Rank 1 = best.
    4. Also reports gain_per_10k = EIG / cost × 10,000 (None when cost == 0), the PDF's column.

Why not just pick the highest EIG? The ground survey is the most informative action
(0.91 bits), but the records request gives 0.50 bits for 1/30th of the price and 1/5th of the
time, so per rupee and per day it is far better value. That is what the score captures.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from .bayes import entropy, expected_information_gain, outcome_previews
from .config import DEFAULT_LAMBDA, MIN_USEFUL_EIG
from .schemas import ActionSpec, Constraints, ExcludedAction, PlanResult, RankedAction

# Friendly names for constraint identifiers (fallback: replace underscores with spaces).
_FRIENDLY: dict[str, str] = {
    "ogi_inspector": "OGI inspector",
    "field_team": "field survey team",
    "measurement_team": "independent measurement team",
    "site_access_permit": "site access permit",
    "landfill_fire": "active landfill fire",
}


def _friendly(key: str) -> str:
    return _FRIENDLY.get(key, key.replace("_", " "))


def _inr(x: float) -> str:
    """Format rupees with thousands separators: 60000 -> '₹60,000'."""
    return f"₹{x:,.0f}"


def _days(d: float) -> str:
    n = f"{d:g}"
    return f"{n} day" if d == 1 else f"{n} days"


def check_constraints(action: ActionSpec, constraints: Constraints) -> tuple[list[str], list[str]]:
    """Return (reason_codes, human_readable_reasons). Both empty = the action is allowed."""
    codes: list[str] = []
    reasons: list[str] = []
    for r in action.resources:
        if r in constraints.unavailable_resources:
            codes.append("RESOURCE_UNAVAILABLE")
            reasons.append(f"Resource unavailable: {_friendly(r)}")
    if action.authorisation and action.authorisation not in constraints.granted_authorisations:
        codes.append("AUTHORISATION_MISSING")
        reasons.append(f"Human authorisation missing: {_friendly(action.authorisation)}")
    for flag in action.unsafe_when:
        if flag in constraints.safety_flags:
            codes.append("SAFETY")
            reasons.append(f"Unsafe under current conditions: {_friendly(flag)}")
    if action.id in constraints.performed_actions:
        codes.append("ALREADY_PERFORMED")
        reasons.append("Already performed for the current hypotheses (repeating it gives the same answer)")
    return codes, reasons


def score(eig_bits: float, cost_inr: float, time_days: float, lam: float) -> float:
    """
    score = EIG / (cost + λ·time): bits of information bought per rupee-equivalent.
    Returns 0 when the denominator is 0.
    """
    denom = cost_inr + lam * time_days
    if denom <= 0:
        return 0.0
    return eig_bits / denom


def rank_actions(
    belief: Mapping[str, float],
    actions: Sequence[ActionSpec],
    constraints: Constraints | None = None,
    lam: float = DEFAULT_LAMBDA,
) -> PlanResult:
    """Filter, score and rank. Fills PlanResult.explanation with explain_plan(...)."""
    constraints = constraints or Constraints()
    ranked: list[RankedAction] = []
    excluded: list[ExcludedAction] = []

    # Step 1: constraint filtering happens before any scoring/ranking.
    allowed: list[ActionSpec] = []
    for a in actions:
        codes, reasons = check_constraints(a, constraints)
        if codes:
            excluded.append(ExcludedAction(
                action_id=a.id, label=a.label, reason_codes=codes, reasons=reasons,
                eig_bits=expected_information_gain(belief, a),
            ))
        else:
            allowed.append(a)

    # Step 2: score the allowed actions.
    for a in allowed:
        eig = expected_information_gain(belief, a)
        s = score(eig, a.cost_inr, a.time_days, lam)
        ranked.append(RankedAction(
            action_id=a.id, label=a.label, eig_bits=eig, cost_inr=a.cost_inr, time_days=a.time_days,
            effective_cost=a.cost_inr + lam * a.time_days, score=s, score_per_10k=s * 10_000,
            gain_per_10k=(eig / a.cost_inr * 10_000) if a.cost_inr > 0 else None,
            rank=0, outcomes=outcome_previews(belief, a),
        ))

    # Step 3: sort (score desc, then EIG desc, then cost asc) and number the ranks.
    ranked.sort(key=lambda r: (-r.score, -r.eig_bits, r.cost_inr))
    for i, r in enumerate(ranked, start=1):
        r.rank = i

    # Recommend the top action only if it is actually informative.
    recommended = ranked[0].action_id if ranked and ranked[0].eig_bits >= MIN_USEFUL_EIG else None

    plan = PlanResult(
        belief=dict(belief), entropy_bits=entropy(belief), lam=lam,
        ranked=ranked, excluded=excluded, recommended_action_id=recommended, explanation="",
    )
    plan.explanation = explain_plan(plan)
    return plan


def _gain_phrase(r: RankedAction) -> str:
    g = f"{r.gain_per_10k:.2f} bits per ₹10k" if r.gain_per_10k is not None else "free"
    return f"{r.eig_bits:.2f} bits for {_inr(r.cost_inr)} and {_days(r.time_days)} ({g})"


def explain_plan(plan: PlanResult) -> str:
    """
    Deterministic plain-English explanation of the ranking (no LLM). Mentions: the top action,
    its EIG/cost/time and gain per ₹10k; the action with the highest raw EIG if different and why
    it ranks lower; any excluded actions and why; and the current entropy.
    """
    parts: list[str] = []
    if not plan.ranked:
        parts.append("No investigation is currently possible: every action is excluded by a constraint.")
    elif plan.recommended_action_id is None:
        parts.append("No informative action remains: every available option would barely reduce uncertainty "
                     f"(best is {plan.ranked[0].eig_bits:.2f} bits). Propose attribution or wait for new evidence.")
    else:
        top = plan.ranked[0]
        parts.append(f"Recommended: {top.label}: {_gain_phrase(top)}.")
        best_eig = max(plan.ranked, key=lambda r: r.eig_bits)
        if best_eig.action_id != top.action_id and best_eig.eig_bits > top.eig_bits:
            ratio = top.score / best_eig.score if best_eig.score > 0 else float("inf")
            ratio_txt = f"~{ratio:.0f}× less" if ratio != float("inf") else "far less"
            parts.append(
                f"{best_eig.label} would reveal more ({best_eig.eig_bits:.2f} bits) but costs "
                f"{_inr(best_eig.cost_inr)} and {_days(best_eig.time_days)}, so per rupee and per day "
                f"it is worth {ratio_txt}."
            )
        zero = [r.label for r in plan.ranked if r.eig_bits < 0.01]
        if zero:
            parts.append(f"{', '.join(zero)}: ~0 bits (cannot tell the sources apart).")
    if plan.excluded:
        ex = "; ".join(f"{e.label} ({', '.join(e.reasons)})" for e in plan.excluded)
        parts.append(f"Excluded before ranking: {ex}.")
    lam_txt = "λ = 0, so time is ignored" if plan.lam == 0 else f"λ = {_inr(plan.lam)}/day"
    parts.append(f"Current uncertainty: {plan.entropy_bits:.2f} bits ({lam_txt}).")
    return " ".join(parts)


def explain_replan(before: PlanResult, after: PlanResult) -> str:
    """
    Deterministic trade-off explanation after a re-rank (e.g. an inspector became unavailable):
    which actions were newly excluded, what replaced them, and the cost/time/information trade-off.
    """
    before_ex = {e.action_id for e in before.excluded}
    newly = [e for e in after.excluded if e.action_id not in before_ex]
    parts: list[str] = []
    if newly:
        parts.append("Newly excluded: " + "; ".join(f"{e.label} ({', '.join(e.reasons)})" for e in newly) + ".")
    else:
        parts.append("No new exclusions.")
    if not after.ranked:
        parts.append("No actions remain; the case needs a human decision or new evidence.")
        return " ".join(parts)

    order = " > ".join(r.label for r in after.ranked)
    parts.append(f"New ranking: {order}.")

    # Trade-off: best field option now available vs what was lost and vs the free option.
    for e in newly:
        lost = next((r for r in before.ranked if r.action_id == e.action_id), None)
        if lost is None:
            continue
        replacement = next(
            (r for r in after.ranked if r.action_id != after.recommended_action_id and r.cost_inr > 0),
            None,
        ) or next((r for r in after.ranked if r.cost_inr > 0), None)
        if replacement is not None:
            d_bits = replacement.eig_bits - lost.eig_bits
            d_cost = replacement.cost_inr - lost.cost_inr
            d_days = replacement.time_days - lost.time_days
            parts.append(
                f"Best substitute for {lost.label}: {replacement.label} "
                f"({d_bits:+.2f} bits, {'+' if d_cost >= 0 else '−'}{_inr(abs(d_cost))}, "
                f"{d_days:+g} days)."
            )
        free = next((r for r in after.ranked if r.cost_inr == 0), None)
        if free is not None:
            parts.append(f"{free.label} is free but gives {free.eig_bits:.2f} bits and takes {_days(free.time_days)}.")
        break

    if after.recommended_action_id:
        top = after.ranked[0]
        parts.append(f"Still recommended first: {top.label}." if before.recommended_action_id == top.action_id
                     else f"Now recommended: {top.label}.")
    else:
        parts.append("No informative action remains.")
    return " ".join(parts)
