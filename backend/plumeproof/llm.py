"""
LLM at the edges: optional text drafting.

Rule 1 of PlumeProof: the language model NEVER changes case state. It only drafts text
(notices, ranking explanations, case summaries). Every outgoing notice is approved by a human.
``suggest_transition`` may *propose* a status change, but the proposal must go through
``CaseAgent.request_transition(..., requested_by_llm=True)``, which validates it against the
state machine like any other request.

Mode selection:
  * ANTHROPIC_API_KEY set and the ``anthropic`` package importable → "llm" (Claude drafts)
  * otherwise → "template" (well-written deterministic templates)
Any API error, timeout or refusal silently falls back to the template text.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .config import HYPOTHESIS_LABELS
from .schemas import DraftResult, TransitionDecision, TransitionRequest

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5-5"  # the current Sonnet ("claude-sonnet-4-5 or newer"); override with ANTHROPIC_MODEL
TIMEOUT_S = 15.0  # one attempt, no retries: a slow API must never stall the demo; we fall back to the template
MAX_TOKENS = 2000  # drafts are short (a letter is < 250 words)

# Current-generation models that accept the server-side refusal fallback ("default" routing) and
# output_config.effort. For any other model (e.g. an older one set through ANTHROPIC_MODEL) we send a
# plain request so an unsupported parameter can never turn into a 400.
CURRENT_GEN_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-fable-5-2"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = (
    "You are the drafting assistant inside PlumeProof, a methane-leak case management system used by "
    "regulators and municipal authorities. Write clear, formal, concise English. Use ONLY the facts given "
    "in the user message. Never invent numbers, dates, names, measurements or legal provisions. Keep every "
    "number exactly as given. Clearly distinguish REAL satellite data from SIMULATED operational events. "
    "You cannot change the status of a case; a human reviews everything you write. "
    "Reply with the requested text only, with no preamble."
)


def _api_key() -> str:
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def llm_model() -> Optional[str]:
    """Model id used for drafting, or None in template mode."""
    if llm_mode() != "llm":
        return None
    return (os.environ.get("ANTHROPIC_MODEL") or "").strip() or DEFAULT_MODEL


def llm_mode() -> str:
    """"llm" if a (non-blank) Claude API key is configured and the SDK imports, else "template"."""
    if not _api_key():
        return "template"
    try:
        import anthropic  # noqa: F401
    except Exception:
        return "template"
    return "llm"


def _make_client() -> Any:
    """Create the Anthropic client. Kept as a separate function so tests can swap in a fake client."""
    import anthropic

    return anthropic.Anthropic(api_key=_api_key(), timeout=TIMEOUT_S, max_retries=0)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
def _pct(p: float) -> str:
    return f"{p * 100:.0f}%"


def _belief_text(belief: dict[str, float]) -> str:
    items = sorted(belief.items(), key=lambda kv: -kv[1])
    return ", ".join(f"{HYPOTHESIS_LABELS.get(h, h)} {_pct(p)}" for h, p in items)


def template_notice(ctx: dict[str, Any]) -> str:
    case_id = ctx.get("case_id", "UNKNOWN")
    facility = ctx.get("facility_name", "the facility")
    recipient = ctx.get("recipient", "The Site Operator")
    action = ctx.get("action_label", "Request flare and gas-collection records")
    request_text = ctx.get("request_text") or (
        "flare uptime and combustion logs, and gas-collection well and header maintenance records, "
        "covering the period of the observation"
    )
    deadline = ctx.get("deadline", "within 1 working day")
    obs_lines = ctx.get("observations", [])
    obs_block = "\n".join(f"  • {o}" for o in obs_lines) or "  • (see case file)"
    belief = ctx.get("belief")
    belief_line = f"\nCurrent source assessment (illustrative probabilities): {_belief_text(belief)}.\n" if belief else ""
    return (
        f"To: {recipient}\n"
        f"Subject: Methane emission investigation, case {case_id} ({facility}): {action}\n\n"
        f"Dear Sir/Madam,\n\n"
        f"Satellite observations have recorded methane emissions at {facility}:\n"
        f"{obs_block}\n"
        f"{belief_line}\n"
        f"To establish the source of these emissions, we request that you provide the following: "
        f"{request_text}.\n\n"
        f"Please respond {deadline}. Your response will be recorded in the case file and assessed against "
        f"independent evidence. Please note that a report of completed repairs will not, on its own, close "
        f"this case: independent post-intervention measurement is required.\n\n"
        f"Yours faithfully,\nCase Officer, PlumeProof methane response desk\n\n"
        f"Drafted by PlumeProof. Requires human approval before sending (simulated)."
    )


def _inr(x: float) -> str:
    return f"₹{x:,.0f}"


def _days(x: float) -> str:
    return f"{x:g} day" + ("" if x == 1 else "s")


def _next_best_after(plan: Any, top: Any, posterior: dict[str, float]) -> Optional[tuple[str, float]]:
    """
    Re-rank the plan's OTHER allowed actions under ``posterior`` (the belief after the top action's outcome),
    with the same λ. Uses the deterministic engine; returns (label, score per ₹10k-equivalent) or None.
    """
    from . import bayes, planner
    from .config import ACTIONS_BY_ID

    best: Optional[tuple[str, float]] = None
    for r in plan.ranked:
        if r.action_id == top.action_id or r.action_id not in ACTIONS_BY_ID:
            continue
        spec = ACTIONS_BY_ID[r.action_id]
        eig = bayes.expected_information_gain(posterior, spec)
        sc = planner.score(eig, spec.cost_inr, spec.time_days, plan.lam) * 10_000
        if eig >= 1e-9 and (best is None or sc > best[1]):
            best = (spec.label, sc)
    return best


def explain_plan_arithmetic(plan: Any) -> str:
    """
    A step-by-step breakdown of a PlanResult, showing the arithmetic behind each score:
        score = EIG ÷ (cost + λ × time)
    then the excluded actions and their reasons, then what each outcome of the top action would change.
    Every number comes from the plan (or is recomputed from it with the same engine).
    """
    if plan is None or not plan.ranked:
        lines = ["No action can be ranked right now."]
        for e in getattr(plan, "excluded", []) or []:
            lines.append(f"Excluded: {e.label}: {'; '.join(e.reasons)}.")
        return "\n".join(lines)

    lam = plan.lam
    lines = [
        f"How the ranking is computed (λ = {_inr(lam)} per day of delay; current uncertainty {plan.entropy_bits:.2f} bits):",
        "",
    ]
    for r in plan.ranked:
        denom = f"{_inr(r.cost_inr)} + {_inr(lam)}/day × {_days(r.time_days)}"
        if r.effective_cost <= 0:
            arithmetic = f"score = {r.eig_bits:.2f} bits ÷ ({denom}) = 0 (nothing to buy: zero cost and zero delay)"
        else:
            arithmetic = (f"score = {r.eig_bits:.2f} bits ÷ ({denom} = {_inr(r.effective_cost)}) "
                          f"= {r.score_per_10k:.2f} bits per ₹10k-equivalent")
        gain = (f"; gain per ₹10k of cash = {r.gain_per_10k:.2f}" if r.gain_per_10k is not None else "; costs no cash")
        lines.append(f"#{r.rank} {r.label}: {arithmetic}{gain}.")

    if plan.excluded:
        lines += ["", "Excluded before ranking (they never compete):"]
        for e in plan.excluded:
            lines.append(f"• {e.label} ({e.eig_bits:.2f} bits forgone): {'; '.join(e.reasons)}.")

    top = plan.ranked[0]
    most_informative = max(plan.ranked, key=lambda r: r.eig_bits)
    if most_informative.action_id != top.action_id and top.score_per_10k > 0:
        ratio = top.score_per_10k / most_informative.score_per_10k if most_informative.score_per_10k > 0 else None
        lines += ["", (f"{most_informative.label} would reveal more ({most_informative.eig_bits:.2f} vs {top.eig_bits:.2f} bits), "
                       f"but per rupee and per day {top.label} is worth "
                       + (f"{ratio:.1f}× more." if ratio else "more."))]

    if top.outcomes:
        lines += ["", "What would change the decision:"]
        for o in top.outcomes:
            lead_h, lead_p = max(o.posterior.items(), key=lambda kv: kv[1])
            nxt = _next_best_after(plan, top, o.posterior)
            tail = (f"; {nxt[0]} becomes the next best ({nxt[1]:.2f} bits per ₹10k-equivalent)" if nxt
                    else "; no remaining action would add useful information")
            lines.append(f"• If '{o.label}' (P = {_pct(o.probability)}): {HYPOTHESIS_LABELS.get(lead_h, lead_h)} "
                         f"rises to {_pct(lead_p)}, uncertainty {o.entropy_after:.2f} bits{tail}.")
    return "\n".join(lines)


def template_ranking_explanation(ctx: dict[str, Any]) -> str:
    """Prefer the full arithmetic breakdown (needs ctx["plan"]); otherwise use the summary strings given."""
    plan = ctx.get("plan")
    if plan is not None:
        return explain_plan_arithmetic(plan)
    parts = []
    if ctx.get("ranked_actions"):
        parts.append("Ranked actions (score = EIG ÷ (cost + λ × time)): " + str(ctx["ranked_actions"]) + ".")
    if ctx.get("excluded_actions") and ctx["excluded_actions"] != "none":
        parts.append("Excluded before ranking: " + str(ctx["excluded_actions"]) + ".")
    return "\n".join(parts) or ctx.get("explanation") or "No ranking available."


def template_case_summary(ctx: dict[str, Any]) -> str:
    parts = [
        f"Case {ctx.get('case_id')} ({ctx.get('facility_name')}) is currently {ctx.get('status')}.",
    ]
    if ctx.get("observations"):
        parts.append("Observations: " + "; ".join(ctx["observations"]) + ".")
    if ctx.get("belief"):
        parts.append("Source assessment: " + _belief_text(ctx["belief"]) + f" (entropy {ctx.get('entropy', 0):.2f} bits).")
    if ctx.get("recommended"):
        parts.append(f"Recommended next action: {ctx['recommended']}.")
    if ctx.get("verdict"):
        parts.append(f"Latest verification verdict: {ctx['verdict']}.")
    if ctx.get("pending_approvals"):
        parts.append(f"{ctx['pending_approvals']} decision(s) await human approval.")
    return " ".join(parts)


TEMPLATES = {
    "notice": template_notice,
    "ranking_explanation": template_ranking_explanation,
    "case_summary": template_case_summary,
}

INSTRUCTIONS = {
    "notice": "Draft a formal investigation request letter (under 250 words) from the case officer to the recipient. "
              "End with the line: 'Drafted by PlumeProof. Requires human approval before sending (simulated).'",
    "ranking_explanation": "Explain to a non-expert judge, in 4-6 sentences, why the planner ranked the actions "
                           "in this order. Use the numbers given (bits, rupees, days). Do not change the ranking.",
    "case_summary": "Write a 3-5 sentence status summary of this case for a regulator.",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_user_message(kind: str, context: dict[str, Any], template_text: str) -> str:
    """The user message sent to Claude: the instruction, the facts (and nothing else), and the template."""
    # Structured objects (e.g. the PlanResult) are summarised by the template text below, not dumped raw.
    facts = "\n".join(f"{k}: {v}" for k, v in context.items() if k != "plan")
    return (f"{INSTRUCTIONS[kind]}\n\nFacts:\n{facts}\n\n"
            f"Reference template (facts are correct):\n{template_text}")


def _extract_text(response: Any) -> str:
    """Join the text blocks of a Messages API response (thinking and other block types are skipped)."""
    return "".join(getattr(b, "text", "") for b in (response.content or []) if getattr(b, "type", "") == "text").strip()


def draft(kind: str, context: dict[str, Any], allow_llm: bool = True) -> DraftResult:
    """
    Draft text of ``kind`` from ``context``. Falls back to the template on ANY problem:
    no key, SDK missing, network error, timeout, refusal, truncated (max_tokens) or empty output.
    """
    template_text = TEMPLATES[kind](context)
    if not allow_llm or llm_mode() != "llm":
        return DraftResult(text=template_text, mode="template", model=None)
    model = llm_model() or DEFAULT_MODEL
    try:
        client = _make_client()
        params: dict[str, Any] = dict(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(kind, context, template_text)}],
        )
        if model in CURRENT_GEN_MODELS:
            # Short drafting task: low effort keeps latency down. On a safety decline the API re-runs
            # the request on a fallback model chosen by refusal category ("default" routing).
            params["output_config"] = {"effort": "low"}
            response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
        else:
            response = client.messages.create(**params)

        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            raise RuntimeError("model declined (refusal)")
        if stop == "max_tokens":
            raise RuntimeError("draft truncated (max_tokens)")
        text = _extract_text(response)
        if not text:
            raise RuntimeError("empty response")
        return DraftResult(text=text, mode="llm", model=getattr(response, "model", None) or model)
    except Exception as exc:  # deliberate: the demo must never break because of the LLM
        log.warning("LLM drafting failed (%s); using template text", exc)
        return DraftResult(text=template_text, mode="template", model=None)


def suggest_transition(case: Any) -> Optional[TransitionRequest]:
    """
    Optional LLM suggestion of a status change. In template mode it returns None.
    The suggestion is never applied directly: callers must pass it to
    CaseAgent.request_transition(..., requested_by_llm=True), which validates it.
    (Kept deliberately simple: we do not let the LLM drive the workflow in this prototype.)
    """
    return None


def apply_suggestion(agent: Any, suggestion: Optional[TransitionRequest]) -> Optional[TransitionDecision]:
    """
    The ONLY path by which an LLM suggestion can affect a case: it is handed to
    ``agent.request_transition(..., requested_by_llm=True)``, which runs the state-machine validator.
    An illegal suggestion (e.g. closing a case on a repair claim) is rejected and logged as
    TRANSITION_REJECTED; it never changes the status.
    """
    if suggestion is None:
        return None
    from .schemas import ActorType

    return agent.request_transition(
        suggestion.to_status,
        actor=ActorType.AGENT,
        reason=suggestion.reason or "Suggested by the language model",
        requested_by_llm=True,
        actor_name="PlumeProof agent (LLM suggestion)",
    )
