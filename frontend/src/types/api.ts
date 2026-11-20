// PlumeProof API contract: TypeScript mirror of backend/plumeproof/schemas.py.
// If you change one, change the other. Route list: docs/API_CONTRACT.md

export type Belief = Record<string, number>;

export type CaseStatus =
  | 'OPEN'
  | 'SOURCE_ATTRIBUTION_PENDING'
  | 'INVESTIGATION_REQUESTED'
  | 'REPAIR_REPORTED'
  | 'VERIFICATION_PENDING'
  | 'VERIFIED_REDUCTION'
  | 'INCONCLUSIVE'
  | 'STILL_LEAKING'
  | 'RECURRING';

export type ApprovalKind = 'SOURCE_ATTRIBUTION' | 'NOTIFICATION' | 'FIELD_INVESTIGATION' | 'FINAL_CLOSURE';
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'EDITED' | 'REJECTED';
export type ActorType = 'agent' | 'human' | 'satellite' | 'simulated';
export type DataLabel = 'REAL DATA' | 'AGENT ACTION' | 'SIMULATED EVENT' | 'HUMAN DECISION';
export type ChainStage = 'Observation' | 'Hypothesis' | 'Investigation' | 'Finding' | 'Repair' | 'Verification';
export type Verdict = 'VERIFIED_REDUCTION' | 'INCONCLUSIVE' | 'STILL_LEAKING' | 'NO_INDEPENDENT_EVIDENCE';
export type ToolName =
  | 'query_observations'
  | 'overlay_facility_zones'
  | 'rank_actions'
  | 'draft_notice'
  | 'track_deadline'
  | 'evaluate_measurement';

// ---------- engine ----------
export interface OutcomeSpec { id: string; label: string; likelihood: Record<string, number> }
export interface ActionSpec {
  id: string; label: string; description: string;
  cost_inr: number; time_days: number;
  resources: string[]; authorisation: string | null; unsafe_when: string[];
  requires_approval: boolean; approval_kind: ApprovalKind | null; is_field_inspection: boolean;
  outcomes: OutcomeSpec[];
}
export interface Constraints {
  unavailable_resources: string[]; granted_authorisations: string[];
  safety_flags: string[]; performed_actions: string[];
}
export interface OutcomePreview { outcome_id: string; label: string; probability: number; posterior: Belief; entropy_after: number }
export interface RankedAction {
  action_id: string; label: string; eig_bits: number; cost_inr: number; time_days: number;
  effective_cost: number; score: number; score_per_10k: number; gain_per_10k: number | null;
  rank: number; outcomes: OutcomePreview[];
}
export interface ExcludedAction { action_id: string; label: string; reason_codes: string[]; reasons: string[]; eig_bits: number }
export interface PlanResult {
  belief: Belief; entropy_bits: number; lam: number;
  ranked: RankedAction[]; excluded: ExcludedAction[];
  recommended_action_id: string | null; explanation: string;
}
export interface BayesUpdate {
  action_id: string; outcome_id: string; prior: Belief; posterior: Belief;
  entropy_before: number; entropy_after: number; outcome_probability: number;
}

// ---------- verification ----------
export interface Measurement {
  id: string; rate_kg_h: number; uncertainty_kg_h: number; date: string; method: string;
  independent: boolean; comparable_conditions: boolean; actor: ActorType; label: DataLabel; notes: string;
}
export interface VerificationRequest { pre: Measurement; posts: Measurement[] }
export interface VerificationResult {
  verdict: Verdict;
  pre_rate: number; pre_uncertainty: number; pre_low: number; pre_high: number;
  post_rate: number | null; post_uncertainty: number | null; post_low: number | null; post_high: number | null;
  conflicting: boolean; measurements_used: string[]; measurements_ignored: string[];
  rule: string; reasons: string[]; recurrence_threshold_kg_h: number | null;
}

// ---------- state machine ----------
export interface TransitionDecision {
  allowed: boolean; from_status: CaseStatus; to_status: CaseStatus;
  requires_approval: ApprovalKind | null; reason: string;
}
export interface TransitionRequest {
  to_status: CaseStatus; actor?: ActorType; actor_name?: string; reason?: string; requested_by_llm?: boolean;
}

// ---------- domain ----------
export interface Observation {
  id: string; case_id: string | null; facility_id: string; date: string; lat: number; lng: number;
  rate_kg_h: number; uncertainty_kg_h: number | null; plume_label: string; source: string; label: DataLabel; notes: string;
}
export interface Stakeholder { role: string; name: string; contact: string; responsibility: string; label: DataLabel }
export interface Deadline { id: string; title: string; due_date: string; status: 'open' | 'met' | 'overdue'; related_action: string | null }
export type LatLng = [number, number];
export interface FacilityZone { id: string; name: string; hypothesis_id: string; polygon: LatLng[] }
export interface Facility { id: string; name: string; location: string; lat: number; lng: number; boundary: LatLng[]; zones: FacilityZone[] }
export interface AuditEvent {
  id: string; case_id: string | null; timestamp: string; sim_date: string | null;
  actor: ActorType; actor_name: string; type: string; label: DataLabel; title: string; description: string;
  evidence_ids: string[]; chain_stage: ChainStage | null; tool: ToolName | null; data: Record<string, unknown>;
}
export interface ToolCall { id: string; case_id: string | null; tool: ToolName; timestamp: string; inputs: Record<string, unknown>; output_summary: string }
export interface ApprovalItem {
  id: string; case_id: string; kind: ApprovalKind; status: ApprovalStatus; title: string; summary: string;
  proposed_text: string; edited_text: string | null; payload: Record<string, unknown>; evidence_ids: string[];
  created_at: string; decided_at: string | null; decided_by: string | null; note: string;
}
export interface ApprovalDecision { decision: 'approve' | 'edit' | 'reject'; edited_text?: string | null; note?: string; decided_by?: string }
export interface BeliefSnapshot { timestamp: string; sim_date: string | null; belief: Belief; entropy_bits: number; reason: string }
export interface Case {
  id: string; facility_id: string; title: string; status: CaseStatus;
  priority: 'Low' | 'Medium' | 'High' | 'Critical'; created_at: string; sim_date: string | null;
  belief: Belief; belief_history: BeliefSnapshot[]; constraints: Constraints; lam: number;
  stakeholders: Stakeholder[]; deadlines: Deadline[]; outstanding_questions: string[]; observation_ids: string[];
  pre_measurement: Measurement | null; measurements: Measurement[]; verification: VerificationResult | null;
  attributed_source: string | null; repaired_source: string | null; recurrence_threshold_kg_h: number | null;
  reopen_count: number; summary: string;
}
export interface CaseSummary {
  id: string; title: string; facility_name: string; status: CaseStatus; priority: string;
  latest_rate_kg_h: number | null; latest_obs_date: string | null;
  leading_hypothesis: string; leading_probability: number; pending_approvals: number; lat: number; lng: number;
}
export interface CaseDetail {
  case: Case; facility: Facility; observations: Observation[]; pending_approvals: ApprovalItem[]; plan: PlanResult | null;
}

// ---------- replay ----------
export interface Banner { kind: 'rejected' | 'verified' | 'reopened' | 'warning' | 'info'; title: string; text: string }
export interface ReplayStepInfo { index: number; id: string; title: string; label: DataLabel }
export interface ReplayFrame {
  step_index: number; total_steps: number; step_id: string; title: string; narration: string;
  label: DataLabel; sim_date: string | null; case: CaseDetail | null;
  belief_before: Belief | null; belief_after: Belief | null;
  plan: PlanResult | null; plan_before: PlanResult | null;
  tool_calls: ToolCall[]; new_events: AuditEvent[]; timeline: AuditEvent[];
  pending_approval: ApprovalItem | null; banner: Banner | null; verification: VerificationResult | null;
  highlight_observation_ids: string[]; done: boolean;
}
export interface ReplayStepRequest { auto_approve?: boolean }

// ---------- map / what-if / llm / meta ----------
export interface Wind { from_deg: number; speed_m_s: number; label: string; illustrative: boolean }
export interface MapState { facility: Facility; observations: Observation[]; cases: CaseSummary[]; wind: Wind }
export interface WhatIfRequest { action_id: string; outcome_id: string; prior?: Belief | null }
export interface WhatIfResult { update: BayesUpdate; eig_bits: number; outcomes: OutcomePreview[] }
export interface DraftRequest { kind: 'notice' | 'ranking_explanation' | 'case_summary'; lam?: number | null }
export interface DraftResult { text: string; mode: 'llm' | 'template'; model: string | null }
export interface HealthResponse { status: 'ok'; version: string; llm_mode: 'llm' | 'template'; llm_model: string | null }
export interface HypothesisInfo { id: string; label: string; prior: number; color: string }
export interface MetaResponse {
  hypotheses: HypothesisInfo[]; actions: ActionSpec[]; verification_action: ActionSpec;
  default_lambda: number; attribution_threshold: number; stats: Record<string, string | number>;
}

// ---------- evaluation ----------
export type PolicyId = 'A' | 'B' | 'C' | 'C_noplan';
export interface PolicyMetrics {
  policy_id: PolicyId; label: string; description: string; n_cases: number; closed_cases: number;
  false_closures: number; false_closure_rate: number; resolved_cases: number; correct_attribution_rate: number;
  inspections_total: number; inspections_per_resolved: number | null; cost_total_inr: number;
  cost_per_resolved_inr: number | null; mean_days_to_stakeholder: number | null; stakeholder_assigned_rate: number;
  traceability_pct: number; mean_days_to_closure: number | null;
}
export interface ScenarioPolicyOutcome {
  final_status: string; closed: boolean; false_closure: boolean; resolved: boolean; attributed_source: string | null;
  inspections: number; cost_inr: number; days_to_stakeholder: number | null; days_elapsed: number;
  actions: string[]; critical_decisions: number; traceable_decisions: number;
}
export interface ScenarioResult { scenario_id: string; tags: string[]; true_source: string; description: string; outcomes: Record<string, ScenarioPolicyOutcome> }
export interface SensitivityResult {
  n_draws: number; perturbation: number; top_action_stability_pct: number; mean_kendall_tau: number;
  top_action_counts: Record<string, number>; c_false_closures_perturbed: number; c_inspections_per_resolved_perturbed: number | null;
}
export interface EvaluationReport {
  generated_at: string; seed: number; n_scenarios: number; policies: PolicyMetrics[];
  scenarios: ScenarioResult[]; sensitivity: SensitivityResult; definitions: Record<string, string>; notes: string[];
}
export interface EvaluateRequest { seed?: number; n_scenarios?: number }

// ---------- offline snapshot (frontend/src/lib/snapshot.json, written by `python -m plumeproof.export_snapshot`) ----------
export interface Snapshot {
  generated_at: string;
  meta: MetaResponse;
  map: MapState;
  frames: ReplayFrame[];          // full replay, frame 0 = intro
  evaluation: EvaluationReport | null;
}
