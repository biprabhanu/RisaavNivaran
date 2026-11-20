"""
PlumeProof FastAPI application.

    uvicorn app:app --reload --port 8000        (from backend/)

Serves:
  /api/*   the JSON API (contract: docs/API_CONTRACT.md, models: plumeproof/schemas.py)
  /docs    interactive OpenAPI docs
  /        the built React app (frontend/dist), if present: one container for everything.

On startup the SQLite database is created and, if empty, seeded by running the full Kanjur
replay, so every page has content. POST /api/demo/reset restores that clean state.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

try:  # optional .env support (ANTHROPIC_API_KEY etc.)
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:  # pragma: no cover
    pass

from plumeproof import bayes, db, llm, replay, verification
from plumeproof.agent import CaseAgent, CaseNotFound, save_facility
from plumeproof.config import (
    ACTIONS,
    ACTIONS_BY_ID,
    ATTRIBUTION_THRESHOLD,
    DEFAULT_LAMBDA,
    DEFAULT_PRIOR,
    HYPOTHESES,
    STATS,
    VERIFICATION_ACTION,
)
from plumeproof.kanjur import FACILITY, STAKEHOLDERS, WIND
from plumeproof.schemas import (
    ActorType,
    ApprovalDecision,
    ApprovalItem,
    ApprovalStatus,
    AuditEvent,
    CaseDetail,
    CaseSummary,
    Constraints,
    DataLabel,
    DraftRequest,
    DraftResult,
    EvaluateRequest,
    EvaluationReport,
    Facility,
    HealthResponse,
    MapState,
    Measurement,
    MetaResponse,
    Observation,
    PlanResult,
    ReplayFrame,
    ReplayStepInfo,
    ReplayStepRequest,
    ToolCall,
    TransitionDecision,
    TransitionRequest,
    VerificationRequest,
    VerificationResult,
    WhatIfRequest,
    WhatIfResult,
)
from plumeproof.tools import point_in_polygon

VERSION = "2.0.0"
EVAL_KEY = "evaluation_latest"


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def seed_demo() -> None:
    """Fresh database + the full Kanjur replay pre-run (so every page has content)."""
    db.reset_db()
    replay.ensure_observations()
    replay.run_full_replay()


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    if db.is_empty():
        seed_demo()
    yield


app = FastAPI(
    title="PlumeProof API",
    description=("Agentic AI backend turning satellite methane alerts into evidence-driven investigations and "
                 "independently verified mitigation (Team RisaavNivaran, IIT Bombay). "
                 "Deterministic core (Bayes, EIG, verification, state machine); LLM only drafts text."),
    version=VERSION,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(CaseNotFound)
async def _case_not_found(_: Request, exc: CaseNotFound):
    return JSONResponse(status_code=404, content={"detail": f"Case not found: {exc.args[0]}"})


def _agent(case_id: str) -> CaseAgent:
    return CaseAgent.load(case_id)


def _detail(case_id: str) -> CaseDetail:
    d = replay.case_detail(case_id)
    if d is None:
        raise CaseNotFound(case_id)
    return d


def _summary(agent: CaseAgent) -> CaseSummary:
    c = agent.case
    obs = db.list_observations(c.id)
    latest = max(obs, key=lambda o: o.date) if obs else None
    latest_rate = sum(o.rate_kg_h for o in obs if latest and o.date == latest.date) if latest else None
    leader, p = max(c.belief.items(), key=lambda kv: kv[1])
    fac = agent.facility
    return CaseSummary(
        id=c.id, title=c.title, facility_name=fac.name, status=c.status, priority=c.priority,
        latest_rate_kg_h=latest_rate, latest_obs_date=latest.date if latest else None,
        leading_hypothesis=leader, leading_probability=p,
        pending_approvals=len(db.list_approvals(c.id, ApprovalStatus.PENDING)), lat=fac.lat, lng=fac.lng,
    )


# ---------------------------------------------------------------------------
# Meta / health / demo
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    mode = llm.llm_mode()
    return HealthResponse(status="ok", version=VERSION, llm_mode=mode, llm_model=llm.llm_model())  # type: ignore[arg-type]


@app.get("/api/meta", response_model=MetaResponse, tags=["meta"])
def meta() -> MetaResponse:
    return MetaResponse(hypotheses=HYPOTHESES, actions=ACTIONS, verification_action=VERIFICATION_ACTION,
                        default_lambda=DEFAULT_LAMBDA, attribution_threshold=ATTRIBUTION_THRESHOLD, stats=STATS)


@app.post("/api/demo/reset", tags=["meta"])
def demo_reset() -> dict[str, str]:
    """Wipe the database and reseed the clean demo state."""
    seed_demo()
    return {"status": "ok"}


@app.get("/api/map", response_model=MapState, tags=["cases"])
def map_state() -> MapState:
    cases = [_summary(CaseAgent(c)) for c in db.list_cases()]
    return MapState(facility=FACILITY, observations=db.list_observations(), cases=cases, wind=WIND)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
@app.get("/api/cases", response_model=list[CaseSummary], tags=["cases"])
def list_cases() -> list[CaseSummary]:
    return [_summary(CaseAgent(c)) for c in db.list_cases()]


@app.get("/api/cases/{case_id}", response_model=CaseDetail, tags=["cases"])
def get_case(case_id: str) -> CaseDetail:
    return _detail(case_id)


@app.get("/api/cases/{case_id}/plan", response_model=PlanResult, tags=["planner"])
def get_plan(case_id: str, lam: Optional[float] = Query(None, ge=0)) -> PlanResult:
    return _agent(case_id).plan(record=False, lam=lam)


@app.put("/api/cases/{case_id}/constraints", response_model=PlanResult, tags=["planner"])
def put_constraints(case_id: str, constraints: Constraints) -> PlanResult:
    _, after = _agent(case_id).set_constraints(constraints, actor=ActorType.HUMAN, actor_name="Human reviewer")
    return after


@app.get("/api/cases/{case_id}/timeline", response_model=list[AuditEvent], tags=["audit"])
def case_timeline(case_id: str) -> list[AuditEvent]:
    _agent(case_id)
    return db.list_events(case_id)


@app.get("/api/cases/{case_id}/tool-calls", response_model=list[ToolCall], tags=["audit"])
def case_tool_calls(case_id: str) -> list[ToolCall]:
    _agent(case_id)
    return db.list_tool_calls(case_id)


@app.post("/api/cases/{case_id}/request-transition", response_model=TransitionDecision, tags=["cases"])
def request_transition(case_id: str, req: TransitionRequest) -> TransitionDecision:
    """Ask for a status change. Validated by the state machine; rejections are logged (TRANSITION_REJECTED)."""
    agent = _agent(case_id)
    return agent.request_transition(req.to_status, actor=req.actor, reason=req.reason,
                                    requested_by_llm=req.requested_by_llm, actor_name=req.actor_name)


@app.post("/api/cases/{case_id}/measurements", response_model=CaseDetail, tags=["verification"])
def add_measurement(case_id: str, m: Measurement) -> CaseDetail:
    _agent(case_id).add_measurement(m)
    return _detail(case_id)


@app.post("/api/cases/{case_id}/draft", response_model=DraftResult, tags=["llm"])
def draft(case_id: str, req: DraftRequest) -> DraftResult:
    """Draft text with Claude (if configured) or templates. Drafting never changes case state."""
    agent = _agent(case_id)
    if req.kind == "notice":
        text, mode, model, _ = agent.draft_stakeholder_notice(allow_llm=True)
        return DraftResult(text=text, mode=mode, model=model)  # type: ignore[arg-type]
    plan = agent.plan(record=False, lam=req.lam)
    if req.kind == "ranking_explanation":
        ctx = {
            "case_id": agent.case.id, "explanation": plan.explanation, "lambda_inr_per_day": plan.lam,
            "entropy_bits": round(plan.entropy_bits, 2),
            "ranked_actions": "; ".join(
                f"#{r.rank} {r.label}: EIG {r.eig_bits:.2f} bits, ₹{r.cost_inr:,.0f}, {r.time_days:g} days, "
                f"score {r.score_per_10k:.3f} per ₹10k-equivalent" for r in plan.ranked),
            "excluded_actions": "; ".join(f"{e.label} ({', '.join(e.reasons)})" for e in plan.excluded) or "none",
        }
        return llm.draft("ranking_explanation", ctx)
    c = agent.case
    ctx = {
        "case_id": c.id, "facility_name": agent.facility.name, "status": c.status.value,
        "observations": [f"{o.date}: {o.plume_label} ~{o.rate_kg_h:,.0f} kg/h ({o.label.value})" for o in db.list_observations(c.id)],
        "belief": c.belief, "entropy": bayes.entropy(c.belief),
        "recommended": ACTIONS_BY_ID[plan.recommended_action_id].label if plan.recommended_action_id else None,
        "verdict": c.verification.verdict.value if c.verification else None,
        "pending_approvals": len(db.list_approvals(c.id, ApprovalStatus.PENDING)),
    }
    return llm.draft("case_summary", ctx)


# ---------------------------------------------------------------------------
# Audit & approvals
# ---------------------------------------------------------------------------
@app.get("/api/audit", response_model=list[AuditEvent], tags=["audit"])
def audit() -> list[AuditEvent]:
    return db.list_events()


@app.get("/api/approvals", response_model=list[ApprovalItem], tags=["approvals"])
def approvals(status: Optional[ApprovalStatus] = None) -> list[ApprovalItem]:
    return db.list_approvals(status=status)


@app.post("/api/approvals/{approval_id}/decide", response_model=ApprovalItem, tags=["approvals"])
def decide(approval_id: str, decision: ApprovalDecision) -> ApprovalItem:
    item = db.get_approval(approval_id)
    if item is None:
        raise HTTPException(404, f"Approval not found: {approval_id}")
    if item.status != ApprovalStatus.PENDING:
        raise HTTPException(409, f"Approval already decided ({item.status.value})")
    return _agent(item.case_id).decide(approval_id, decision)


# ---------------------------------------------------------------------------
# Stateless calculators
# ---------------------------------------------------------------------------
@app.post("/api/verification/evaluate", response_model=VerificationResult, tags=["verification"])
def verification_evaluate(req: VerificationRequest) -> VerificationResult:
    return verification.evaluate_verification(req.pre, req.posts)


@app.post("/api/whatif", response_model=WhatIfResult, tags=["planner"])
def whatif(req: WhatIfRequest) -> WhatIfResult:
    action = ACTIONS_BY_ID.get(req.action_id)
    if action is None:
        raise HTTPException(404, f"Unknown action: {req.action_id}")
    if req.outcome_id not in {o.id for o in action.outcomes}:
        raise HTTPException(422, f"Unknown outcome '{req.outcome_id}' for action '{req.action_id}'")
    prior = bayes.normalise(req.prior) if req.prior else dict(DEFAULT_PRIOR)
    return WhatIfResult(update=bayes.update_with_outcome(prior, action, req.outcome_id),
                        eig_bits=bayes.expected_information_gain(prior, action),
                        outcomes=bayes.outcome_previews(prior, action))


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
@app.get("/api/replay/script", response_model=list[ReplayStepInfo], tags=["replay"])
def replay_script() -> list[ReplayStepInfo]:
    return replay.script()


@app.post("/api/replay/reset", response_model=ReplayFrame, tags=["replay"])
def replay_reset() -> ReplayFrame:
    return replay.reset()


@app.post("/api/replay/step", response_model=ReplayFrame, tags=["replay"])
def replay_step(req: Optional[ReplayStepRequest] = None) -> ReplayFrame:
    return replay.step(auto_approve=(req or ReplayStepRequest()).auto_approve)


@app.get("/api/replay/frames", response_model=list[ReplayFrame], tags=["replay"])
def replay_frames() -> list[ReplayFrame]:
    """The whole replay, computed in a scratch database (live state untouched)."""
    return replay.frames_in_scratch_db()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def _run_eval(seed: int, n: int) -> EvaluationReport:
    from plumeproof import scenarios  # lazy import (heavier module)

    report = scenarios.run_evaluation(seed=seed, n_scenarios=n)
    db.kv_set(EVAL_KEY, report.model_dump(mode="json"))
    return report


@app.post("/api/evaluate", response_model=EvaluationReport, tags=["evaluation"])
def evaluate(req: Optional[EvaluateRequest] = None) -> EvaluationReport:
    req = req or EvaluateRequest()
    return _run_eval(req.seed, req.n_scenarios)


@app.get("/api/evaluate/latest", response_model=EvaluationReport, tags=["evaluation"])
def evaluate_latest() -> EvaluationReport:
    cached = db.kv_get(EVAL_KEY)
    if cached:
        return EvaluationReport.model_validate(cached)
    return _run_eval(2026, 25)


# ---------------------------------------------------------------------------
# Observation upload (ported from the original main.py by Mandar)
# ---------------------------------------------------------------------------
class ObservationUpload(BaseModel):
    observation_id: str
    facility_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observation_date: str
    emission_rate_kg_hour: float = Field(gt=0)
    source: str = "SAMPLE UPLOAD (simulated)"
    confidence: Optional[float] = 0.95


@app.post("/api/observations/upload", response_model=CaseDetail, tags=["cases"])
def upload_observation(obs: ObservationUpload) -> CaseDetail:
    """Validate an uploaded observation and open a case for it through the agent."""
    try:
        datetime.fromisoformat(obs.observation_date)
    except ValueError:
        raise HTTPException(422, "observation_date must be an ISO date (YYYY-MM-DD)")
    if db.get_observation(obs.observation_id) is not None:
        raise HTTPException(409, f"Duplicate observation id: {obs.observation_id}")
    if point_in_polygon(obs.latitude, obs.longitude, FACILITY.boundary):
        facility = FACILITY
    else:
        fid = "fac-" + "".join(ch for ch in obs.facility_name.lower() if ch.isalnum())[:24]
        d = 0.006
        facility = Facility(id=fid, name=obs.facility_name, location="Uploaded location", lat=obs.latitude,
                            lng=obs.longitude, zones=[],
                            boundary=[(obs.latitude + d, obs.longitude - d), (obs.latitude + d, obs.longitude + d),
                                      (obs.latitude - d, obs.longitude + d), (obs.latitude - d, obs.longitude - d)])
        save_facility(facility)
    observation = Observation(
        id=obs.observation_id, facility_id=facility.id, date=obs.observation_date[:10], lat=obs.latitude,
        lng=obs.longitude, rate_kg_h=obs.emission_rate_kg_hour, plume_label=obs.observation_id, source=obs.source,
        label=DataLabel.SIMULATED_EVENT, notes="Uploaded observation: not verified real data.",
    )
    case_id = f"IMP-{int(datetime.now(timezone.utc).timestamp())}"
    pre = Measurement(id=f"PRE-{obs.observation_id}", rate_kg_h=obs.emission_rate_kg_hour,
                      uncertainty_kg_h=round(obs.emission_rate_kg_hour * 0.25, 1), date=observation.date,
                      method=obs.source, independent=True, actor=ActorType.SIMULATED, label=DataLabel.SIMULATED_EVENT)
    agent = CaseAgent.open_case(case_id, f"{obs.facility_name} (uploaded)", facility, [observation], STAKEHOLDERS,
                                pre_measurement=pre, sim_date=observation.date)
    agent.initialise_hypotheses()
    agent.plan()
    return _detail(case_id)


# ---------------------------------------------------------------------------
# Frontend (single-container deploy): serve frontend/dist at /
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parent.parent / "frontend" / "dist"))


@app.get("/", include_in_schema=False)
def index():
    idx = FRONTEND_DIST / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return JSONResponse({"name": "PlumeProof API", "docs": "/docs",
                         "note": "Frontend not built. Run `npm run build` in frontend/ or use the Vite dev server."})


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "Not found")
    target = (FRONTEND_DIST / full_path).resolve()
    if FRONTEND_DIST.exists() and target.is_file() and FRONTEND_DIST.resolve() in target.parents:
        return FileResponse(target)
    idx = FRONTEND_DIST / "index.html"
    if idx.exists():
        return FileResponse(idx)
    raise HTTPException(404, "Not found")
