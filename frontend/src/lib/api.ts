// Typed API client. All URLs are relative (/api/...), so the same build works behind FastAPI,
// the Vite dev proxy, or any host. If the backend can't be reached, the app switches to
// "offline snapshot mode" and read-only calls are answered from the bundled snapshot.json.
import type {
  ApprovalDecision, ApprovalItem, AuditEvent, CaseDetail, CaseSummary, Constraints, DraftRequest, DraftResult,
  EvaluateRequest, EvaluationReport, HealthResponse, MapState, Measurement, MetaResponse, PlanResult,
  ReplayFrame, ReplayStepInfo, ReplayStepRequest, ToolCall, TransitionDecision, TransitionRequest,
  VerificationRequest, VerificationResult, WhatIfRequest, WhatIfResult,
} from '../types/api';
import { verify, whatIf } from './bayes';
import { getState, setState } from './store';

const BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
export class OfflineError extends Error {
  constructor(message = 'Backend unreachable: this action is unavailable in offline snapshot mode.') {
    super(message);
  }
}

// ---------- offline snapshot ----------
export interface OfflineSnapshot {
  generated_at: string;
  meta: MetaResponse | null;
  map: MapState | null;
  frames: ReplayFrame[];
  evaluation: EvaluationReport | null;
}
let snapshotPromise: Promise<OfflineSnapshot> | null = null;
export function loadSnapshot(): Promise<OfflineSnapshot> {
  // Dynamic import: the (large) snapshot is only downloaded when it is actually needed.
  if (!snapshotPromise) {
    snapshotPromise = import('./snapshot.json').then((m) => (m.default ?? m) as unknown as OfflineSnapshot);
  }
  return snapshotPromise;
}

async function offlineFrame(): Promise<ReplayFrame> {
  const snap = await loadSnapshot();
  if (!snap.frames.length) throw new OfflineError('Offline snapshot is empty.');
  const idx = getState().offlineFrameIndex;
  return snap.frames[idx == null ? snap.frames.length - 1 : Math.min(idx, snap.frames.length - 1)];
}
async function offlineCase(): Promise<CaseDetail> {
  const f = await offlineFrame();
  if (f.case) return f.case;
  // Intro frame has no case yet: use the last frame instead.
  const snap = await loadSnapshot();
  const last = [...snap.frames].reverse().find((fr) => fr.case);
  if (!last?.case) throw new OfflineError('No case in offline snapshot.');
  return last.case;
}
function summarise(d: CaseDetail): CaseSummary {
  const b = d.case.belief;
  const lead = Object.keys(b).sort((x, y) => b[y] - b[x])[0] ?? '';
  const last = [...d.observations].sort((x, y) => x.date.localeCompare(y.date)).pop();
  return {
    id: d.case.id, title: d.case.title, facility_name: d.facility.name, status: d.case.status,
    priority: d.case.priority, latest_rate_kg_h: last?.rate_kg_h ?? null, latest_obs_date: last?.date ?? null,
    leading_hypothesis: lead, leading_probability: b[lead] ?? 0, pending_approvals: d.pending_approvals.length,
    lat: d.facility.lat, lng: d.facility.lng,
  };
}

// ---------- core request ----------
interface ReqOpts {
  method?: string;
  body?: unknown;
  timeoutMs?: number;
  offline?: () => Promise<unknown> | unknown;
}

function isProxyDown(status: number, text: string): boolean {
  return status === 502 || status === 503 || status === 504 || (status === 500 && (text === '' || text.includes('ECONNREFUSED')));
}

async function request<T>(path: string, opts: ReqOpts = {}): Promise<T> {
  if (getState().offline && opts.offline) return (await opts.offline()) as T;
  if (getState().offline && !opts.offline) throw new OfflineError();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 6000);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: opts.method ?? 'GET',
      headers: opts.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal,
    });
  } catch {
    clearTimeout(timer);
    return goOffline<T>(opts);
  }
  clearTimeout(timer);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    if (isProxyDown(res.status, text)) return goOffline<T>(opts);
    let msg = text || res.statusText;
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch { /* not JSON */ }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get('content-type') ?? '';
  if (!ct.includes('application/json')) {
    // e.g. a static host returned index.html for /api/*: treat as "no backend".
    return goOffline<T>(opts);
  }
  return (await res.json()) as T;
}

async function goOffline<T>(opts: ReqOpts): Promise<T> {
  if (!getState().offline) setState({ offline: true });
  if (opts.offline) return (await opts.offline()) as T;
  throw new OfflineError();
}

/** Try the backend again (used by the offline banner's "Retry" button). */
export async function retryOnline(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/health`);
    if (res.ok && (res.headers.get('content-type') ?? '').includes('application/json')) {
      setState({ offline: false, health: (await res.json()) as HealthResponse, dataVersion: getState().dataVersion + 1 });
      return true;
    }
  } catch { /* still offline */ }
  return false;
}

// ---------- endpoints ----------
export const api = {
  health: () =>
    request<HealthResponse>('/api/health', {
      timeoutMs: 5000,
      offline: (): HealthResponse => ({ status: 'ok', version: 'snapshot', llm_mode: 'template', llm_model: null }),
    }),
  meta: () =>
    request<MetaResponse>('/api/meta', {
      offline: async () => {
        const s = await loadSnapshot();
        if (!s.meta) throw new OfflineError('Offline snapshot has no metadata.');
        return s.meta;
      },
    }),
  resetDemo: () => request<{ status: string }>('/api/demo/reset', { method: 'POST', timeoutMs: 30000 }),
  map: () =>
    request<MapState>('/api/map', {
      offline: async () => {
        const s = await loadSnapshot();
        if (!s.map) throw new OfflineError('Offline snapshot has no map.');
        const d = await offlineCase().catch(() => null);
        return d ? { ...s.map, cases: [summarise(d)], observations: d.observations.length ? d.observations : s.map.observations } : s.map;
      },
    }),
  cases: () =>
    request<CaseSummary[]>('/api/cases', {
      offline: async () => [summarise(await offlineCase())],
    }),
  caseDetail: (id: string) => request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`, { offline: () => offlineCase() }),
  plan: (id: string, lam?: number) =>
    request<PlanResult>(`/api/cases/${encodeURIComponent(id)}/plan${lam != null ? `?lam=${lam}` : ''}`, {
      offline: async () => {
        const d = await offlineCase();
        if (!d.plan) throw new OfflineError('No plan in snapshot.');
        return d.plan;
      },
    }),
  setConstraints: (id: string, c: Constraints) =>
    request<PlanResult>(`/api/cases/${encodeURIComponent(id)}/constraints`, { method: 'PUT', body: c }),
  timeline: (id: string) =>
    request<AuditEvent[]>(`/api/cases/${encodeURIComponent(id)}/timeline`, {
      offline: async () => (await offlineFrame()).timeline,
    }),
  toolCalls: (id: string) =>
    request<ToolCall[]>(`/api/cases/${encodeURIComponent(id)}/tool-calls`, {
      offline: async () => {
        const s = await loadSnapshot();
        const idx = getState().offlineFrameIndex ?? s.frames.length - 1;
        return s.frames.slice(0, idx + 1).flatMap((f) => f.tool_calls);
      },
    }),
  requestTransition: (id: string, body: TransitionRequest) =>
    request<TransitionDecision>(`/api/cases/${encodeURIComponent(id)}/request-transition`, { method: 'POST', body }),
  addMeasurement: (id: string, m: Measurement) =>
    request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}/measurements`, { method: 'POST', body: m }),
  draft: (id: string, body: DraftRequest) =>
    request<DraftResult>(`/api/cases/${encodeURIComponent(id)}/draft`, { method: 'POST', body, timeoutMs: 30000 }),
  audit: () => request<AuditEvent[]>('/api/audit', { offline: async () => (await offlineFrame()).timeline }),
  approvals: (status?: string) =>
    request<ApprovalItem[]>(`/api/approvals${status ? `?status=${status}` : ''}`, {
      offline: async () => {
        const d = await offlineCase().catch(() => null);
        return d ? d.pending_approvals : [];
      },
    }),
  decide: (id: string, body: ApprovalDecision) =>
    request<ApprovalItem>(`/api/approvals/${encodeURIComponent(id)}/decide`, { method: 'POST', body }),
  verify: (body: VerificationRequest) =>
    request<VerificationResult>('/api/verification/evaluate', { method: 'POST', body, offline: () => verify(body.pre, body.posts) }),
  whatif: (body: WhatIfRequest) =>
    request<WhatIfResult>('/api/whatif', {
      method: 'POST',
      body,
      offline: async () => {
        const s = await loadSnapshot();
        const meta = getState().meta ?? s.meta;
        const action = meta?.actions.find((a) => a.id === body.action_id);
        if (!meta || !action) throw new OfflineError('Action catalogue missing from snapshot.');
        const prior = body.prior ?? Object.fromEntries(meta.hypotheses.map((h) => [h.id, h.prior]));
        return whatIf(prior, action, body.outcome_id);
      },
    }),
  replayScript: () =>
    request<ReplayStepInfo[]>('/api/replay/script', {
      offline: async () =>
        (await loadSnapshot()).frames.map((f) => ({ index: f.step_index, id: f.step_id, title: f.title, label: f.label })),
    }),
  replayReset: () => request<ReplayFrame>('/api/replay/reset', { method: 'POST', timeoutMs: 15000 }),
  replayCurrent: () => request<ReplayFrame>('/api/replay/current', { timeoutMs: 10000 }),
  replayStep: (body: ReplayStepRequest) => request<ReplayFrame>('/api/replay/step', { method: 'POST', body, timeoutMs: 15000 }),
  evaluationLatest: () =>
    request<EvaluationReport>('/api/evaluate/latest', {
      timeoutMs: 90000,
      offline: async () => {
        const s = await loadSnapshot();
        if (!s.evaluation) throw new OfflineError('Offline snapshot has no evaluation results.');
        return s.evaluation;
      },
    }),
  evaluate: (body: EvaluateRequest) =>
    request<EvaluationReport>('/api/evaluate', { method: 'POST', body, timeoutMs: 120000 }),
  uploadObservation: (body: unknown) =>
    request<CaseDetail>('/api/observations/upload', { method: 'POST', body }),
};

export function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
