"""
The agent's tools (PDF slide 8: "acting through tools").

Each tool is a plain, deterministic Python function. Every call is recorded twice:
  * a ToolCall row (inputs + one-line output summary), and
  * an AuditEvent of type TOOL_CALL (label AGENT ACTION), so judges can see the agent act through tools.

Tools:
  query_observations      - fetch satellite observations for a facility
  overlay_facility_zones  - which facility zones do the plumes fall in? who is accountable?
  rank_actions            - Evidence Planner (EIG / (cost + λ·time))
  draft_notice            - draft a notice/letter (LLM or template; never sent without approval)
  track_deadline          - create/update deadlines, flag overdue ones
  evaluate_measurement    - evidence-gated verification rule
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from . import db, llm, planner, verification
from .config import ACTIONS, DEFAULT_PRIOR
from .schemas import (
    ActorType,
    AuditEvent,
    Case,
    ChainStage,
    DataLabel,
    Deadline,
    DraftResult,
    Facility,
    Measurement,
    Observation,
    PlanResult,
    Stakeholder,
    ToolCall,
    ToolName,
    VerificationResult,
)

AGENT_NAME = "PlumeProof agent"


def new_id(prefix: str) -> str:
    """Short unique id, e.g. EVT-3f2a9c1b07."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def add_days(iso_day: Optional[str], days: float) -> str:
    base = date.fromisoformat(iso_day) if iso_day else date.today()
    return (base + timedelta(days=round(days))).isoformat()


def _record(
    case: Case,
    tool: ToolName,
    inputs: dict[str, Any],
    summary: str,
    evidence_ids: Optional[list[str]] = None,
    chain_stage: Optional[ChainStage] = None,
    data: Optional[dict[str, Any]] = None,
) -> ToolCall:
    call = ToolCall(id=new_id("TC"), case_id=case.id, tool=tool, timestamp=now_iso(), inputs=inputs,
                    output_summary=summary)
    db.add_tool_call(call)
    db.add_event(AuditEvent(
        id=new_id("EVT"), case_id=case.id, timestamp=call.timestamp, sim_date=case.sim_date,
        actor=ActorType.AGENT, actor_name=AGENT_NAME, type="TOOL_CALL", label=DataLabel.AGENT_ACTION,
        title=f"Tool call: {tool.value}", description=summary, evidence_ids=evidence_ids or [],
        chain_stage=chain_stage, tool=tool, data={"tool_call_id": call.id, "inputs": inputs, **(data or {})},
    ))
    return call


# ---------------------------------------------------------------------------
# Geometry helper
# ---------------------------------------------------------------------------
def point_in_polygon(lat: float, lng: float, polygon: Sequence[tuple[float, float]]) -> bool:
    """
    Ray casting: draw a ray from the point and count how many polygon edges it crosses.
    An odd number of crossings means the point is inside.
    """
    inside = False
    n = len(polygon)
    for i in range(n):
        y1, x1 = polygon[i]
        y2, x2 = polygon[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lng < x_cross:
                inside = not inside
    return inside


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def query_observations(case: Case, facility_id: str, on_date: Optional[str] = None) -> list[Observation]:
    """Return satellite observations for a facility (optionally only those on ``on_date``)."""
    obs = [o for o in db.list_observations() if o.facility_id == facility_id and (on_date is None or o.date == on_date)]
    summary = (f"Found {len(obs)} observation(s) for {facility_id}"
               + (f" on {on_date}" if on_date else "") + ": "
               + "; ".join(f"{o.plume_label} {o.rate_kg_h:,.0f} kg/h ({o.label.value})" for o in obs))
    _record(case, ToolName.QUERY_OBSERVATIONS, {"facility_id": facility_id, "date": on_date}, summary,
            evidence_ids=[o.id for o in obs], chain_stage=ChainStage.OBSERVATION)
    return obs


def overlay_facility_zones(case: Case, facility: Facility, observations: Sequence[Observation],
                           stakeholders: Sequence[Stakeholder]) -> dict[str, Any]:
    """
    Overlay plume positions on the facility zones (point-in-polygon) and resolve stakeholders.
    The prior returned is config.DEFAULT_PRIOR (illustrative values from the proposal); a data-driven
    geospatial prior is future work. See docs/ASSUMPTIONS.md §1.
    """
    hits: dict[str, list[str]] = {}
    for o in observations:
        hits[o.id] = [z.name for z in facility.zones if point_in_polygon(o.lat, o.lng, z.polygon)]
    inside = [o.id for o in observations if point_in_polygon(o.lat, o.lng, facility.boundary)]
    parts = []
    for o in observations:
        zs = hits[o.id]
        parts.append(f"{o.plume_label} → {', '.join(zs) if zs else 'no specific zone'}")
    summary = (f"{len(inside)}/{len(observations)} plume(s) inside {facility.name}. " + "; ".join(parts)
               + f". Accountable stakeholders resolved: {', '.join(s.name for s in stakeholders)} (simulated mapping).")
    _record(case, ToolName.OVERLAY_FACILITY_ZONES, {"facility_id": facility.id, "observation_ids": [o.id for o in observations]},
            summary, evidence_ids=[o.id for o in observations], chain_stage=ChainStage.HYPOTHESIS,
            data={"zone_hits": hits})
    return {"zone_hits": hits, "inside": inside, "stakeholders": list(stakeholders), "prior": dict(DEFAULT_PRIOR)}


def rank_actions(case: Case, lam: Optional[float] = None, record: bool = True) -> PlanResult:
    """Run the Evidence Planner on the case's current belief and constraints."""
    plan = planner.rank_actions(case.belief, ACTIONS, case.constraints, case.lam if lam is None else lam)
    if record:
        top = plan.ranked[0] if plan.ranked else None
        summary = (f"Ranked {len(plan.ranked)} action(s), excluded {len(plan.excluded)}. "
                   + (f"Top: {top.label} (EIG {top.eig_bits:.2f} bits, ₹{top.cost_inr:,.0f}, {top.time_days:g} d). "
                      if top else "No admissible action. ")
                   + f"Entropy {plan.entropy_bits:.2f} bits.")
        _record(case, ToolName.RANK_ACTIONS, {"belief": {k: round(v, 4) for k, v in case.belief.items()},
                                              "lam": plan.lam, "constraints": case.constraints.model_dump()},
                summary, chain_stage=ChainStage.INVESTIGATION)
    return plan


def draft_notice(case: Case, context: dict[str, Any], allow_llm: bool = True) -> DraftResult:
    """Draft a formal notice. It is only a draft: a human must approve it before it is 'sent'."""
    result = llm.draft("notice", context, allow_llm=allow_llm)
    _record(case, ToolName.DRAFT_NOTICE, {"recipient": context.get("recipient"), "action": context.get("action_label")},
            f"Drafted notice to {context.get('recipient', 'stakeholder')} ({result.mode} mode, {len(result.text)} chars).",
            chain_stage=ChainStage.INVESTIGATION, data={"mode": result.mode})
    return result


def track_deadline(case: Case, title: str, due_date: str, related_action: Optional[str] = None,
                   mark_met: Optional[str] = None) -> Optional[Deadline]:
    """
    Create a deadline (if ``title`` is given) and/or mark an existing one as met.
    Any open deadline whose due date is before the case's in-world date is flagged overdue.
    """
    created: Optional[Deadline] = None
    if mark_met:
        for d in case.deadlines:
            if d.related_action == mark_met and d.status != "met":
                d.status = "met"
    if title:
        created = Deadline(id=new_id("DL"), title=title, due_date=due_date, related_action=related_action)
        case.deadlines.append(created)
    overdue = []
    if case.sim_date:
        for d in case.deadlines:
            if d.status == "open" and d.due_date < case.sim_date:
                d.status = "overdue"
                overdue.append(d.title)
    summary = (f"Deadline set: '{title}' due {due_date}." if title else "Deadlines updated.")
    if mark_met:
        summary += f" Marked '{mark_met}' as met."
    if overdue:
        summary += f" OVERDUE: {', '.join(overdue)}."
    _record(case, ToolName.TRACK_DEADLINE, {"title": title, "due_date": due_date, "mark_met": mark_met}, summary,
            chain_stage=ChainStage.INVESTIGATION)
    return created


def evaluate_measurement(case: Case, pre: Measurement, posts: Sequence[Measurement]) -> VerificationResult:
    """Apply the evidence-gated verification rule to the pre measurement and all post measurements."""
    result = verification.evaluate_verification(pre, posts)
    summary = f"Verdict {result.verdict.value}. " + " ".join(result.reasons)
    _record(case, ToolName.EVALUATE_MEASUREMENT, {"pre": pre.id, "posts": [m.id for m in posts]}, summary,
            evidence_ids=[pre.id] + [m.id for m in posts], chain_stage=ChainStage.VERIFICATION)
    return result
