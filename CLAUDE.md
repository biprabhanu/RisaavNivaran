# PlumeProof: project memory

## The project in one paragraph
PlumeProof (Team RisaavNivaran, IIT Bombay, Agentic AI Hackathon 2026, Ulster University) is a persistent case agent. It turns a satellite-detected methane plume into a managed investigation and refuses to close the case until independent evidence shows emissions went down. It keeps competing source hypotheses (exposed waste surface, gas-collection system, flare system) and updates them with Bayes' rule. It ranks the next investigation by expected information gain per unit of cost and time, routes every critical decision through a human approval queue, and logs everything in an audit trail. If a later observation shows the emissions are back, it reopens the case. The demo case is the Kanjur landfill in Mumbai. The Carbon Mapper plumes are real (9 Feb 2025: ~1,600 and ~136 kg/h; 3 Apr 2026: ~3,300 kg/h combined). Every operational event is simulated and labelled as simulated. The source of truth is `RisaavNivaran.pdf`.

## Architecture
```
frontend/ (React + Vite + Tailwind + Leaflet + Recharts, HashRouter)
   │  fetch /api/*   (falls back to bundled snapshot if the backend is down)
backend/app.py (FastAPI: /api/*, /docs, serves frontend/dist at /)
   └── plumeproof/
        config.py        hypotheses, prior, action catalogue + likelihood tables P(y|h,a), costs, λ
        schemas.py       Pydantic models = the API contract (mirrored in frontend/src/types/api.ts)
        bayes.py         entropy, Bayes update, outcome distribution, EIG        (pure math)
        planner.py       constraint filtering + score = EIG/(cost+λ·time) ranking (pure)
        verification.py  evidence-gated verdict rule + recurrence check          (pure)
        state_machine.py lifecycle transition table + validator                  (pure)
        agent.py         case orchestrator: observe → update → plan → approve → act → verify
        tools.py         the agent's tools (query_observations, overlay_facility_zones, rank_actions,
                         draft_notice, track_deadline, evaluate_measurement)
        llm.py           optional Claude drafting; template fallback (never changes state)
        replay.py        scripted Kanjur 2025–2026 historical replay
        scenarios.py     25 seeded evaluation scenarios + policies A/B/C + ablation + sensitivity
        db.py            SQLite persistence (plain sqlite3, JSON columns)
   tests/                pytest (engine + API)
```
Deterministic core, LLM at the edges: all maths and state changes live in plain tested Python. The LLM only drafts text.

## How to run
- Backend (dev): `cd backend && uv venv --python 3.12 .venv && source .venv/bin/activate && uv pip install -r requirements.txt && uvicorn app:app --reload --port 8000`
- Frontend (dev): `cd frontend && npm install && npm run dev` (Vite proxies `/api` to :8000), then open http://localhost:5173
- Tests: `cd backend && pytest -q`; `cd frontend && npm run build`; e2e: `cd frontend && npx playwright test` (needs the app running on :8000)
- Docker: `docker build -t plumeproof . && docker run -p 8000:8000 plumeproof`, then open http://localhost:8000
- Deploy: Render, using the Blueprint in `render.yaml` (single Docker web service, free plan).
- Regenerate the offline snapshot: `cd backend && python -m plumeproof.export_snapshot`, which writes `frontend/src/lib/snapshot.json`
- Regenerate the evaluation: `cd backend && python -m plumeproof.scenarios`, which writes `docs/EVALUATION.md` and `docs/evaluation_results.csv`

## Coding conventions
- Python 3.12, type hints everywhere, Pydantic v2 models for every API payload. Docstrings explain the maths in plain English with the formula.
- Prefer clarity over cleverness. The team lead is a beginner and must be able to defend the code in Q&A.
- Engine modules (`bayes`, `planner`, `verification`, `state_machine`) are pure: no I/O, no randomness, no LLM.
- Frontend: TypeScript, functional components, Tailwind. Look: slate-900 header, emerald accent, white `rounded-2xl` cards (Mandar's style). Every page has a one-line "What you're seeing" caption.
- API types live in `backend/plumeproof/schemas.py` and are mirrored by hand in `frontend/src/types/api.ts`. Change both together.
- Secrets only in `.env` (see `.env.example`). Commits are authored by the user alone: no AI attribution trailers. Never push.

## Non-negotiable product rules
1. Deterministic core, LLM at the edges. The LLM drafts notices, rationales and summaries. It never changes state; it can only *request* a transition, which `state_machine.validate_transition` checks.
2. The LLM is optional. If `ANTHROPIC_API_KEY` is set, Claude does the drafting; otherwise template text is used. The demo works offline without a key, and an "LLM: on/off" badge shows which mode is active.
3. Hypotheses are waste surface / gas collection / flare, with prior 0.50 / 0.35 / 0.15, so H = 1.44 bits.
4. score(a) = EIG(a) / (cost + λ·time). Also show gain per ₹10k = EIG / cost × 10,000. Actions that violate a constraint are excluded *before* ranking.
5. The worked example reproduces (test: `tests/test_worked_example.py`). Records ≈ 0.50 bits and ranks first; P(fault) ≈ 0.43; fault posterior ≈ gas 65 / flare 29 / waste 6; no-fault waste ≈ 84%. All of these are computed, never hard-coded.
6. Evidence-gated closure: the verdict is VERIFIED_REDUCTION only if post + u_post < pre − u_pre under comparable conditions with an independent measurement. A repair claim alone means VERIFICATION_PENDING. Conflicting measurements mean INCONCLUSIVE. A later observation above the threshold reopens the case (RECURRING).
7. Lifecycle is enforced by the transition table in `state_machine.py`.
8. Human in the loop: source attribution, official notifications, field investigations and final closure each create an approval item.
9. Audit log: each event has a timestamp, actor, type, evidence links and a label (REAL DATA / AGENT ACTION / SIMULATED EVENT / HUMAN DECISION), plus an evidence-chain stage.
10. Honest labelling: only the Carbon Mapper plumes are real. Everything else is visibly simulated.

## Current status (2026-11-21)
- Phases A–F are implemented (see docs/ROADMAP.md).
- Backend: 102 pytest tests pass. The worked example reproduces: records 0.499 bits, OGI 0.413, ground 0.914, satellite 0; P(fault) 0.433; posterior 65/29/6; no-fault waste 83.7%.
- Evaluation (seed 2026, 25 scenarios): false closures A 25, B 25, C 0, ablation 0; source-ID inspections per case B 1.80 vs C 0.72; ±20% sensitivity keeps the top action in 100% of draws.
- Frontend: `npm run build` and typecheck pass; the Playwright e2e replay passes; the offline snapshot fallback works.
- Docker: the image builds; `docker run -p 8000:8000 plumeproof` serves the UI, `/api` and `/docs`; the DB seeds on startup.
- Replay: 11 steps (frame 0 = intro). Step 5 is OGI unavailable, step 8 is the repair claim rejected, step 11 is the 2026 reopen.
- Known limits: see the README "Honest limitations" section. The LLM path is untested against the live API (no key in the dev environment).
- Regenerate `frontend/src/lib/snapshot.json` (`python -m plumeproof.export_snapshot`) after any change to the replay or evaluation.
