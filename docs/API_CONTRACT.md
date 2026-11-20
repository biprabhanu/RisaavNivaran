# API contract

Models are defined in `backend/plumeproof/schemas.py` (mirrored in `frontend/src/types/api.ts`).
All routes are prefixed with `/api`. The frontend calls relative URLs (`/api/...`); in dev, Vite proxies them to :8000.

| Method | Path | Body | Returns | Notes |
|---|---|---|---|---|
| GET | /api/health | | HealthResponse | `llm_mode` drives the "LLM: on/off" badge |
| GET | /api/meta | | MetaResponse | hypotheses, action catalogue, λ default, landing stats |
| POST | /api/demo/reset | | `{"status":"ok"}` | wipe DB, reseed (full replay pre-run so every page has content) |
| GET | /api/map | | MapState | facility polygon + zones, plumes, cases, illustrative wind |
| GET | /api/cases | | CaseSummary[] | |
| GET | /api/cases/{id} | | CaseDetail | includes the current plan (case λ and constraints) |
| GET | /api/cases/{id}/plan?lam=1000 | | PlanResult | recomputes the plan at the given λ (doesn't persist λ) |
| PUT | /api/cases/{id}/constraints | Constraints | PlanResult | persists, logs an AUDIT event, re-ranks |
| GET | /api/cases/{id}/timeline | | AuditEvent[] | chronological |
| GET | /api/cases/{id}/tool-calls | | ToolCall[] | |
| POST | /api/cases/{id}/request-transition | TransitionRequest | TransitionDecision | validated by the state machine; rejections are logged (TRANSITION_REJECTED) |
| POST | /api/cases/{id}/measurements | Measurement | CaseDetail | agent runs `evaluate_measurement`; may create a FINAL_CLOSURE approval |
| POST | /api/cases/{id}/draft | DraftRequest | DraftResult | LLM or template; "notice" also creates a NOTIFICATION approval |
| GET | /api/audit | | AuditEvent[] | all cases |
| GET | /api/approvals?status=PENDING | | ApprovalItem[] | status optional |
| POST | /api/approvals/{id}/decide | ApprovalDecision | ApprovalItem | agent continues its loop after the decision |
| POST | /api/verification/evaluate | VerificationRequest | VerificationResult | stateless calculator (Verification page) |
| POST | /api/whatif | WhatIfRequest | WhatIfResult | stateless |
| GET | /api/replay/script | | ReplayStepInfo[] | |
| POST | /api/replay/reset | | ReplayFrame | step 0 (intro); resets case KJ-2025-02 |
| POST | /api/replay/step | ReplayStepRequest | ReplayFrame | applies the next scripted event |
| GET | /api/replay/frames | | ReplayFrame[] | runs the whole replay in a scratch DB (for the snapshot); doesn't touch live state |
| POST | /api/evaluate | EvaluateRequest | EvaluationReport | runs the simulation (takes a few seconds) |
| GET | /api/evaluate/latest | | EvaluationReport | cached last run (computed at startup if missing) |
| POST | /api/observations/upload | ObservationUpload (Mandar's) | CaseDetail | creates a case through the agent |
