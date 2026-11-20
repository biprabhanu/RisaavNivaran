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

import os
from typing import Any, Optional

from .config import HYPOTHESIS_LABELS
from .schemas import DraftResult, TransitionRequest

DEFAULT_MODEL = "claude-sonnet-5-5"  # "claude-sonnet-4-5 or newer"; override with ANTHROPIC_MODEL
TIMEOUT_S = 15.0

SYSTEM_PROMPT = (
    "You are the drafting assistant inside PlumeProof, a methane-leak case management system used by "
    "regulators and municipal authorities. Write clear, formal, concise English. Use ONLY the facts given "
    "in the user message. Never invent numbers, dates, names, measurements or legal provisions. Keep every "
    "number exactly as given. Clearly distinguish REAL satellite data from SIMULATED operational events. "
    "You cannot change the status of a case; a human reviews everything you write."
)


def llm_model() -> Optional[str]:
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL) if llm_mode() == "llm" else None


def llm_mode() -> str:
    """"llm" if a Claude API key is configured and the SDK imports, else "template"."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "template"
    try:
        import anthropic  # noqa: F401
    except Exception:
        return "template"
    return "llm"


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


def template_ranking_explanation(ctx: dict[str, Any]) -> str:
    return ctx.get("explanation") or "No ranking available."


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
def draft(kind: str, context: dict[str, Any], allow_llm: bool = True) -> DraftResult:
    """Draft text of ``kind`` from ``context``. Falls back to the template on any problem."""
    template_text = TEMPLATES[kind](context)
    if not allow_llm or llm_mode() != "llm":
        return DraftResult(text=template_text, mode="template", model=None)
    try:
        import anthropic

        model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
        client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1)
        facts = "\n".join(f"{k}: {v}" for k, v in context.items())
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"{INSTRUCTIONS[kind]}\n\nFacts:\n{facts}\n\nReference template (facts are correct):\n{template_text}",
            }],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("refusal")
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
        if not text:
            raise RuntimeError("empty response")
        return DraftResult(text=text, mode="llm", model=model)
    except Exception:
        return DraftResult(text=template_text, mode="template", model=None)


def suggest_transition(case: Any) -> Optional[TransitionRequest]:
    """
    Optional LLM suggestion of a status change. In template mode it returns None.
    The suggestion is never applied directly: callers must pass it to
    CaseAgent.request_transition(..., requested_by_llm=True), which validates it.
    (Kept deliberately simple: we do not let the LLM drive the workflow in this prototype.)
    """
    return None
