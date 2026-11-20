// Formatting helpers and colour maps shared by every page.
import type { ApprovalKind, CaseStatus, DataLabel, MetaResponse } from '../types/api';

export const inr = (n: number | null | undefined): string =>
  n == null ? '—' : `₹${Math.round(n).toLocaleString('en-IN')}`;

export const pct = (p: number | null | undefined, digits = 0): string =>
  p == null ? '—' : `${(p * 100).toFixed(digits)}%`;

export const bits = (b: number | null | undefined, digits = 2): string =>
  b == null ? '—' : `${b.toFixed(digits)} bits`;

export const num = (n: number | null | undefined, digits = 0): string =>
  n == null ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const kgh = (n: number | null | undefined): string =>
  n == null ? '—' : `${Math.round(n).toLocaleString('en-IN')} kg/h`;

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ---------- hypotheses (registry filled from /api/meta) ----------
const DEFAULT_HYP: Record<string, { label: string; color: string }> = {
  waste_surface: { label: 'Exposed waste surface', color: '#f59e0b' },
  gas_collection: { label: 'Gas-collection system', color: '#10b981' },
  flare: { label: 'Flare system', color: '#6366f1' },
};
let hypRegistry: Record<string, { label: string; color: string }> = { ...DEFAULT_HYP };
export const HYP_ORDER = ['waste_surface', 'gas_collection', 'flare'];

export function registerMeta(meta: MetaResponse | null): void {
  if (!meta) return;
  const reg: Record<string, { label: string; color: string }> = {};
  meta.hypotheses.forEach((h) => (reg[h.id] = { label: h.label, color: h.color }));
  hypRegistry = { ...DEFAULT_HYP, ...reg };
}
export const hypLabel = (id: string | null | undefined): string =>
  id ? hypRegistry[id]?.label ?? id : '—';
export const hypColor = (id: string): string => hypRegistry[id]?.color ?? '#64748b';
export const hypIds = (): string[] => HYP_ORDER.filter((h) => h in hypRegistry);

// ---------- statuses ----------
export const STATUS_META: Record<CaseStatus, { label: string; cls: string; hex: string }> = {
  OPEN: { label: 'Open', cls: 'bg-sky-100 text-sky-800 border-sky-200', hex: '#0284c7' },
  SOURCE_ATTRIBUTION_PENDING: { label: 'Source Attribution Pending', cls: 'bg-orange-100 text-orange-800 border-orange-200', hex: '#ea580c' },
  INVESTIGATION_REQUESTED: { label: 'Investigation Requested', cls: 'bg-amber-100 text-amber-800 border-amber-200', hex: '#d97706' },
  REPAIR_REPORTED: { label: 'Repair Reported', cls: 'bg-violet-100 text-violet-800 border-violet-200', hex: '#7c3aed' },
  VERIFICATION_PENDING: { label: 'Verification Pending', cls: 'bg-yellow-100 text-yellow-800 border-yellow-300', hex: '#ca8a04' },
  VERIFIED_REDUCTION: { label: 'Verified Reduction', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200', hex: '#059669' },
  INCONCLUSIVE: { label: 'Inconclusive', cls: 'bg-slate-200 text-slate-800 border-slate-300', hex: '#475569' },
  STILL_LEAKING: { label: 'Still Leaking', cls: 'bg-red-100 text-red-800 border-red-200', hex: '#dc2626' },
  RECURRING: { label: 'Recurring (reopened)', cls: 'bg-red-100 text-red-800 border-red-300', hex: '#b91c1c' },
};
export const statusLabel = (s: string): string => STATUS_META[s as CaseStatus]?.label ?? s;

// ---------- provenance labels ----------
export const LABEL_CLS: Record<DataLabel, string> = {
  'REAL DATA': 'bg-blue-100 text-blue-800 border-blue-300',
  'AGENT ACTION': 'bg-emerald-50 text-emerald-800 border-emerald-300',
  'SIMULATED EVENT': 'bg-amber-100 text-amber-900 border-amber-300',
  'HUMAN DECISION': 'bg-violet-100 text-violet-800 border-violet-300',
};
export const LABEL_DOT: Record<DataLabel, string> = {
  'REAL DATA': 'bg-blue-600',
  'AGENT ACTION': 'bg-emerald-600',
  'SIMULATED EVENT': 'bg-amber-500',
  'HUMAN DECISION': 'bg-violet-600',
};

export const APPROVAL_KIND_LABEL: Record<ApprovalKind, string> = {
  SOURCE_ATTRIBUTION: 'Source attribution',
  NOTIFICATION: 'Official notification',
  FIELD_INVESTIGATION: 'Field investigation',
  FINAL_CLOSURE: 'Final closure',
};

export const VERDICT_META: Record<string, { label: string; cls: string }> = {
  VERIFIED_REDUCTION: { label: 'VERIFIED REDUCTION', cls: 'bg-emerald-600 text-white' },
  INCONCLUSIVE: { label: 'INCONCLUSIVE', cls: 'bg-slate-600 text-white' },
  STILL_LEAKING: { label: 'STILL LEAKING', cls: 'bg-red-600 text-white' },
  NO_INDEPENDENT_EVIDENCE: { label: 'NO INDEPENDENT EVIDENCE: STAYS VERIFICATION PENDING', cls: 'bg-amber-500 text-slate-950' },
};

export const RESOURCE_LABEL: Record<string, string> = {
  ogi_inspector: 'OGI inspector',
  field_team: 'Field survey team',
  measurement_team: 'Measurement team',
};
