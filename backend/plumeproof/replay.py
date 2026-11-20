"""
Historical replay: Kanjur landfill 2025–2026 (the hero demo, PDF slide 15/18).

REAL DATA      : Carbon Mapper observations of 9 Feb 2025 and 3 Apr 2026.
SIMULATED EVENT: everything operational (inspector availability, records content, repair claim,
                 follow-up measurement). Each frame carries its label so the UI can show it.

The replay drives the real CaseAgent (same code path as the live API). Each call to ``step()``
applies one scripted beat and returns a complete ReplayFrame (self-contained, also used for the
offline snapshot). The current position is stored in the kv table, so it works across requests.

Human approvals: when a frame has ``pending_approval``, the next step needs a human decision.
Either the presenter clicks Approve in the UI (POST /api/approvals/{id}/decide) or presses
Next/Play with auto_approve=True. That click is logged as a HUMAN DECISION by "Demo presenter".
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import Any, Callable, Optional

from . import db, planner
from .agent import CaseAgent
from .kanjur import (
    CASE_ID,
    FACILITY,
    OBS_2025_A,
    OBS_2025_B,
    OBS_2026,
    OUTSTANDING_QUESTIONS,
    PRE_MEASUREMENT,
    REAL_OBSERVATIONS,
    STAKEHOLDERS,
)
from .schemas import (
    ActorType,
    ApprovalDecision,
    ApprovalStatus,
    Banner,
    Belief,
    CaseDetail,
    DataLabel,
    Measurement,
    PlanResult,
    ReplayFrame,
    ReplayStepInfo,
    VerificationResult,
)

KV_KEY = "replay"
PRESENTER = "Demo presenter"
CASE_TITLE = "Kanjur Landfill, Mumbai"

FOLLOW_UP = Measurement(
    id="MEAS-2025-05-20", rate_kg_h=610.0, uncertainty_kg_h=150.0, date="2025-05-20",
    method="Independent aerial methane survey (simulated)", independent=True, comparable_conditions=True,
    actor=ActorType.SIMULATED, label=DataLabel.SIMULATED_EVENT,
    notes="Simulated follow-up measurement under comparable wind conditions.",
)


@dataclass
class StepResult:
    narration: str
    banner: Optional[Banner] = None
    belief_before: Optional[Belief] = None
    belief_after: Optional[Belief] = None
    plan: Optional[PlanResult] = None
    plan_before: Optional[PlanResult] = None
    verification: Optional[VerificationResult] = None
    highlight: Optional[list[str]] = None


@dataclass
class Step:
    id: str
    title: str
    label: DataLabel
    sim_date: Optional[str]
    run: Callable[[], StepResult]


# ---------------------------------------------------------------------------
# Scripted beats
# ---------------------------------------------------------------------------
def _agent() -> CaseAgent:
    return CaseAgent.load(CASE_ID)


def _s1_observation() -> StepResult:
    CaseAgent.open_case(CASE_ID, CASE_TITLE, FACILITY, [OBS_2025_A, OBS_2025_B], STAKEHOLDERS,
                        pre_measurement=PRE_MEASUREMENT, sim_date="2025-02-09", priority="Critical")
    return StepResult(
        narration=("REAL DATA: Carbon Mapper detected two methane plumes at Kanjur landfill on 9 Feb 2025: "
                   "~1,600 kg/h and ~136 kg/h. The agent opens case KJ-2025-02, overlays the plumes on the facility "
                   "zones and resolves who is accountable (BMC SWM Dept, the landfill operator and MPCB; simulated mapping)."),
        highlight=[OBS_2025_A.id, OBS_2025_B.id],
    )


def _s2_hypotheses() -> StepResult:
    a = _agent()
    a.initialise_hypotheses(questions=OUTSTANDING_QUESTIONS)
    return StepResult(
        narration=("The agent keeps three competing source hypotheses instead of guessing: exposed waste surface 50%, "
                   "gas-collection system 35%, flare system 15%. Its uncertainty is H = 1.44 bits."),
        belief_after=dict(a.case.belief),
    )


def _s3_plan() -> StepResult:
    a = _agent()
    plan = a.plan()
    a.propose_action(plan.recommended_action_id or "records_request")
    top = plan.ranked[0]
    ground = next((r for r in plan.ranked if r.action_id == "ground_survey"), None)
    return StepResult(
        narration=(f"The Evidence Planner scores every investigation by expected information gain per rupee and day. "
                   f"The ground survey is most informative ({ground.eig_bits:.2f} bits) but costs ₹60,000; "
                   f"'{top.label}' gives {top.eig_bits:.2f} bits for ₹{top.cost_inr:,.0f}, so it ranks first. "
                   "A human must approve before the agent acts." if ground else plan.explanation),
        plan=plan,
    )


def _s4_approved() -> StepResult:
    a = _agent()
    return StepResult(
        narration=("HUMAN DECISION: the reviewer approved the records request. The agent sends it to the operator "
                   "(simulated), moves the case to INVESTIGATION REQUESTED and tracks a 1-day deadline."),
        plan=a.plan(record=False),
    )


def _s5_ogi_unavailable() -> StepResult:
    a = _agent()
    c = a.case.constraints.model_copy(deep=True)
    if "ogi_inspector" not in c.unavailable_resources:
        c.unavailable_resources.append("ogi_inspector")
    before, after = a.set_constraints(c, actor=ActorType.SIMULATED, actor_name="Inspection scheduler (simulated)",
                                      note="SIMULATED: the optical gas-imaging inspector is unavailable this week.")
    text = planner.explain_replan(before, after)
    return StepResult(
        narration=("SIMULATED: the gas-imaging (OGI) inspector is unavailable. The agent excludes that action before "
                   "ranking and re-plans the follow-up: " + text),
        banner=Banner(kind="warning", title="Resource unavailable: re-planning",
                      text="OGI inspector unavailable. Action excluded before ranking; remaining options re-ranked."),
        plan=after, plan_before=before,
    )


def _s6_records_fault() -> StepResult:
    a = _agent()
    before = dict(a.case.belief)
    upd = a.update_beliefs("records_request", "fault_found", sim_date="2025-02-10")
    a = _agent()
    return StepResult(
        narration=(f"SIMULATED: the records show a gas-system fault (P = {upd.outcome_probability:.2f} before seeing it). "
                   f"Bayes' rule moves the gas-collection system to {upd.posterior['gas_collection']:.0%} and the waste "
                   f"surface down to {upd.posterior['waste_surface']:.0%}. The agent proposes an attribution; a human must approve it."),
        belief_before=before, belief_after=dict(upd.posterior), plan=a.plan(record=False),
    )


def _s7_attribution_approved() -> StepResult:
    return StepResult(
        narration=("HUMAN DECISION: attribution to the gas-collection system approved (other hypotheses stay open). "
                   "The agent drafts an official notice instructing the operator to repair it; sending it needs approval too."),
    )


def _s8_repair_claim() -> StepResult:
    a = _agent()
    a.report_repair(sim_date="2025-03-20", source="gas_collection")
    return StepResult(
        narration=("SIMULATED: on 20 Mar 2025 the operator reports the gas-collection repair complete and asks to close "
                   "the case. The agent REFUSES: there is no independent post-intervention measurement, and a claim is "
                   "not evidence. The case moves to VERIFICATION PENDING until independent evidence arrives."),
        banner=Banner(kind="rejected", title="CASE CLOSURE REJECTED",
                      text="No independent post-intervention measurement. A repair claim is not evidence."),
    )


def _s9_measurement() -> StepResult:
    a = _agent()
    result = a.add_measurement(FOLLOW_UP)
    return StepResult(
        narration=(f"SIMULATED: an independent aerial survey on 20 May 2025 measures {FOLLOW_UP.rate_kg_h:,.0f} ± "
                   f"{FOLLOW_UP.uncertainty_kg_h:,.0f} kg/h under comparable conditions. Its upper bound "
                   f"({result.post_high:,.0f}) is below the pre-repair lower bound ({result.pre_low:,.0f}), "
                   "so the verdict is VERIFIED REDUCTION. Final closure still needs a human."),
        banner=Banner(kind="verified", title="VERIFIED REDUCTION",
                      text=f"post + u ({result.post_high:,.0f}) < pre − u ({result.pre_low:,.0f}) kg/h, independent and comparable."),
        verification=result,
    )


def _s10_closed() -> StepResult:
    a = _agent()
    thr = a.case.recurrence_threshold_kg_h or 0
    return StepResult(
        narration=(f"HUMAN DECISION: final closure approved. The case is closed as VERIFIED REDUCTION, but the agent keeps "
                   f"watching: any later observation above {thr:,.0f} kg/h will reopen it automatically."),
        verification=a.case.verification,
    )


def _s11_recurrence() -> StepResult:
    a = _agent()
    a.observe(OBS_2026)
    a = _agent()
    return StepResult(
        narration=("REAL DATA: on 3 Apr 2026 Carbon Mapper observed ~3,300 kg/h at Kanjur, far above the verified level. "
                   "The agent automatically REOPENS the case as RECURRING, resets its hypotheses and re-plans. "
                   "Persistence over months is why this needs an agent."),
        banner=Banner(kind="reopened", title="CASE REOPENED: RECURRING EMISSIONS",
                      text="Real observation of 3 Apr 2026 (~3,300 kg/h) exceeds the verified post-repair level."),
        plan=a.plan(record=False), highlight=[OBS_2026.id],
    )


STEPS: list[Step] = [
    Step("obs-2025", "Real observation: 9 Feb 2025", DataLabel.REAL_DATA, "2025-02-09", _s1_observation),
    Step("hypotheses", "Competing source hypotheses", DataLabel.AGENT_ACTION, "2025-02-09", _s2_hypotheses),
    Step("plan", "Evidence Planner ranks investigations", DataLabel.AGENT_ACTION, "2025-02-09", _s3_plan),
    Step("approve-records", "Human approves the records request", DataLabel.HUMAN_DECISION, "2025-02-09", _s4_approved),
    Step("ogi-unavailable", "SIMULATED: OGI inspector unavailable", DataLabel.SIMULATED_EVENT, "2025-02-09", _s5_ogi_unavailable),
    Step("records-fault", "SIMULATED: records show a gas-system fault", DataLabel.SIMULATED_EVENT, "2025-02-10", _s6_records_fault),
    Step("attribution", "Human approves source attribution", DataLabel.HUMAN_DECISION, "2025-02-11", _s7_attribution_approved),
    Step("repair-claim", "SIMULATED: operator claims repair: closure REJECTED", DataLabel.SIMULATED_EVENT, "2025-03-20", _s8_repair_claim),
    Step("follow-up", "SIMULATED: independent follow-up measurement", DataLabel.SIMULATED_EVENT, "2025-05-20", _s9_measurement),
    Step("closure", "Human approves final closure", DataLabel.HUMAN_DECISION, "2025-05-21", _s10_closed),
    Step("obs-2026", "Real observation: 3 Apr 2026: case REOPENED", DataLabel.REAL_DATA, "2026-04-03", _s11_recurrence),
]
TOTAL_STEPS = len(STEPS)  # frames are 0 (intro) .. TOTAL_STEPS


def script() -> list[ReplayStepInfo]:
    return [ReplayStepInfo(index=i + 1, id=s.id, title=s.title, label=s.label) for i, s in enumerate(STEPS)]


# ---------------------------------------------------------------------------
# Frame building
# ---------------------------------------------------------------------------
def case_detail(case_id: str = CASE_ID) -> Optional[CaseDetail]:
    case = db.get_case(case_id)
    if case is None:
        return None
    agent = CaseAgent(case)
    return CaseDetail(
        case=case, facility=agent.facility, observations=db.list_observations(case_id),
        pending_approvals=db.list_approvals(case_id, ApprovalStatus.PENDING), plan=agent.plan(record=False),
    )


def _pending() -> Optional[object]:
    items = db.list_approvals(CASE_ID, ApprovalStatus.PENDING)
    return items[-1] if items else None


def _intro_frame() -> ReplayFrame:
    return ReplayFrame(
        step_index=0, total_steps=TOTAL_STEPS, step_id="intro", title="Replay: Kanjur landfill 2025–2026",
        narration=("A replay of REAL Carbon Mapper methane observations at Kanjur landfill, Mumbai, with SIMULATED "
                   "operational events (clearly labelled). Press Play or Next to watch the agent work the case."),
        label=DataLabel.REAL_DATA, sim_date=None, case=None,
    )


def _build_frame(index: int, step: Step, res: StepResult, n_events: int, n_calls: int) -> ReplayFrame:
    timeline = db.list_events(CASE_ID)
    calls = db.list_tool_calls(CASE_ID)
    return ReplayFrame(
        step_index=index, total_steps=TOTAL_STEPS, step_id=step.id, title=step.title, narration=res.narration,
        label=step.label, sim_date=step.sim_date, case=case_detail(),
        belief_before=res.belief_before, belief_after=res.belief_after, plan=res.plan, plan_before=res.plan_before,
        tool_calls=calls[n_calls:], new_events=timeline[n_events:], timeline=timeline,
        pending_approval=_pending(), banner=res.banner, verification=res.verification,
        highlight_observation_ids=res.highlight or [], done=index == TOTAL_STEPS,
    )


def _save_state(index: int, frame: ReplayFrame) -> None:
    db.kv_set(KV_KEY, {"step": index, "frame": frame.model_dump(mode="json")})


def current_frame() -> ReplayFrame:
    state = db.kv_get(KV_KEY)
    if not state:
        return _intro_frame()
    return ReplayFrame.model_validate(state["frame"])


def reset() -> ReplayFrame:
    """Delete case KJ-2025-02 (and its events/approvals) and return the intro frame."""
    db.init_db()
    db.delete_case(CASE_ID)
    ensure_observations()
    frame = _intro_frame()
    _save_state(0, frame)
    return frame


def ensure_observations() -> None:
    """Make sure the real Kanjur observations exist in the database (unlinked)."""
    for o in REAL_OBSERVATIONS:
        if db.get_observation(o.id) is None:
            db.save_observation(o)


def step(auto_approve: bool = True) -> ReplayFrame:
    """Apply the next scripted beat. Resolves a pending approval first (if auto_approve)."""
    state = db.kv_get(KV_KEY)
    if not state:
        reset()
        state = db.kv_get(KV_KEY)
    index = int(state["step"])
    if index >= TOTAL_STEPS:
        return current_frame()

    n_events = len(db.list_events(CASE_ID))
    n_calls = len(db.list_tool_calls(CASE_ID))

    # A human REJECTED the approval shown in this frame: the script must not pretend it was approved.
    shown = current_frame().pending_approval
    decided = db.get_approval(shown.id) if shown is not None else None
    if decided is not None and decided.status == ApprovalStatus.REJECTED:
        return _rejection_frame(index, decided, n_events, n_calls)

    pending = db.list_approvals(CASE_ID, ApprovalStatus.PENDING)
    if pending and not auto_approve:
        # Wait only while the approval SHOWN in the current frame is still undecided. If a human already
        # decided it (via /api/approvals/{id}/decide), the agent may have queued a follow-up approval,
        # e.g. attribution approved → notification drafted. That one belongs to the next step, so advance.
        shown = current_frame().pending_approval
        if shown is not None and any(item.id == shown.id for item in pending):
            return current_frame()
    elif pending:
        agent = _agent()
        for item in pending:
            agent = _agent()
            agent.decide(item.id, ApprovalDecision(decision="approve", decided_by=PRESENTER,
                                                   note="Approved during the historical replay."))

    nxt = STEPS[index]
    if db.get_case(CASE_ID) is not None:
        agent = _agent()
        agent.set_sim_date(nxt.sim_date)
        agent.save()
    res = nxt.run()
    frame = _build_frame(index + 1, nxt, res, n_events, n_calls)
    _save_state(index + 1, frame)
    return frame


def _rejection_frame(index: int, rejected: Any, n_events: int, n_calls: int) -> ReplayFrame:
    """
    The presenter clicked Reject. The agent has already logged the decision and re-planned
    (CaseAgent.on_approval_decided). It does NOT act. For the replay to continue, the agent
    re-proposes the same step as a new approval item, so the human stays in control.
    """
    agent = _agent()
    agent.request_approval(
        rejected.kind, rejected.title,
        f"Re-proposed after the reviewer rejected it. {rejected.summary}",
        proposed_text=rejected.proposed_text, payload=dict(rejected.payload),
        evidence_ids=list(rejected.evidence_ids) + [rejected.id],
    )
    prev = current_frame()
    timeline = db.list_events(CASE_ID)
    frame = prev.model_copy(update={
        "title": f"Human rejected: {rejected.title}",
        "narration": ("HUMAN DECISION: the reviewer REJECTED this step, so the agent did not act. The rejection is "
                      "logged in the audit trail, the case status is unchanged, and the agent re-planned. To continue "
                      "the replay, approve the re-proposed item (or edit it first)."),
        "label": DataLabel.HUMAN_DECISION,
        "case": case_detail(),
        "tool_calls": db.list_tool_calls(CASE_ID)[n_calls:],
        "new_events": timeline[n_events:],
        "timeline": timeline,
        "pending_approval": _pending(),
        "banner": Banner(kind="warning", title="HUMAN REJECTED: THE AGENT DID NOT ACT",
                         text="Every critical step waits for a human. Rejections are logged and the agent re-plans."),
    })
    _save_state(index, frame)
    return frame


def run_full_replay() -> list[ReplayFrame]:
    """Run every step from the start in the CURRENT database (auto-approving). Returns all frames."""
    frames = [reset()]
    for _ in range(TOTAL_STEPS):
        frames.append(step(auto_approve=True))
    return frames


def frames_in_scratch_db() -> list[ReplayFrame]:
    """Run the whole replay in a temporary database: live state is untouched."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="plumeproof-replay-")
    os.close(fd)
    try:
        with db.use_db(path):
            db.reset_db()
            return run_full_replay()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
