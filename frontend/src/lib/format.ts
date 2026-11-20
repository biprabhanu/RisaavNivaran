// Formatting helpers and colour maps shared by every page.
import type { ApprovalKind, CaseStatus, DataLabel, MetaResponse } from '../types/api';

// One number style everywhere: international grouping (1,600 · ₹25,000), 2-dp bits, whole-number %.
const LOCALE = 'en-US';

export const inr = (n: number | null | undefined): string =>
  n == null ? '—' : `₹${Math.round(n).toLocaleString(LOCALE)}`;

export const pct = (p: number | null | undefined, digits = 0): string =>
  p == null ? '—' : `${(p * 100).toFixed(digits)}%`;

export const bits = (b: number | null | undefined, digits = 2): string =>
  b == null ? '—' : `${b.toFixed(digits)} bits`;

export const num = (n: number | null | undefined, digits = 0): string =>
  n == null ? '—' : n.toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const kgh = (n: number | null | undefined): string =>
  n == null ? '—' : `${Math.round(n).toLocaleString(LOCALE)} kg/h`;

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ---------- hypotheses (registry filled from /api/meta) ----------
const DEFAULT_HYP: Record<string, { label: string; color: string }> = {
  waste_surface: { label: 'Exposed waste surface', color: '#64748b' }, // slate-500
  gas_collection: { label: 'Gas-collection system', color: '#0d9488' }, // teal-600 (accent)
  flare: { label: 'Flare system', color: '#5eead4' }, // teal-300
};
let hypRegistry: Record<string, { label: string; color: string }> = { ...DEFAULT_HYP };
export const HYP_ORDER = ['waste_surface', 'gas_collection', 'flare'];

export function registerMeta(meta: MetaResponse | null): void {
  if (!meta) return;
  const reg: Record<string, { label: string; color: string }> = {};
  // Labels come from the API; colours stay on the UI palette so charts match the design system.
  meta.hypotheses.forEach((h) => (reg[h.id] = { label: h.label, color: DEFAULT_HYP[h.id]?.color ?? '#94a3b8' }));
  hypRegistry = { ...DEFAULT_HYP, ...reg };
}
export const hypLabel = (id: string | null | undefined): string =>
  id ? hypRegistry[id]?.label ?? id : '—';
export const hypColor = (id: string): string => hypRegistry[id]?.color ?? '#64748b';
export const hypIds = (): string[] => HYP_ORDER.filter((h) => h in hypRegistry);

// ---------- statuses ----------
// Status colours: amber = pending / in progress, green = verified, red = leaking / recurring, slate = neutral.
const PENDING = { cls: 'bg-amber-50 text-amber-800 border-amber-200', hex: '#d97706' };
export const STATUS_META: Record<CaseStatus, { label: string; cls: string; hex: string }> = {
  OPEN: { label: 'Open', cls: 'bg-slate-100 text-slate-700 border-slate-200', hex: '#64748b' },
  SOURCE_ATTRIBUTION_PENDING: { label: 'Source Attribution Pending', ...PENDING },
  INVESTIGATION_REQUESTED: { label: 'Investigation Requested', ...PENDING },
  REPAIR_REPORTED: { label: 'Repair Reported', ...PENDING },
  VERIFICATION_PENDING: { label: 'Verification Pending', ...PENDING },
  VERIFIED_REDUCTION: { label: 'Verified Reduction', cls: 'bg-green-50 text-green-800 border-green-200', hex: '#16a34a' },
  INCONCLUSIVE: { label: 'Inconclusive', cls: 'bg-slate-100 text-slate-700 border-slate-300', hex: '#64748b' },
  STILL_LEAKING: { label: 'Still Leaking', cls: 'bg-red-50 text-red-700 border-red-200', hex: '#dc2626' },
  RECURRING: { label: 'Recurring (reopened)', cls: 'bg-red-50 text-red-700 border-red-200', hex: '#dc2626' },
};
export const statusLabel = (s: string): string => STATUS_META[s as CaseStatus]?.label ?? s;

// ---------- provenance labels (always visible; distinguished by style, not by extra colours) ----------
export const LABEL_CLS: Record<DataLabel, string> = {
  'REAL DATA': 'bg-teal-600 text-white border-teal-600',
  'AGENT ACTION': 'bg-slate-100 text-slate-700 border-slate-300',
  'SIMULATED EVENT': 'bg-white text-slate-700 border-slate-400 border-dashed',
  'HUMAN DECISION': 'bg-slate-800 text-white border-slate-800',
};
export const LABEL_DOT: Record<DataLabel, string> = {
  'REAL DATA': 'bg-teal-600',
  'AGENT ACTION': 'bg-slate-400',
  'SIMULATED EVENT': 'bg-white border border-dashed border-slate-500',
  'HUMAN DECISION': 'bg-slate-800',
};

export const APPROVAL_KIND_LABEL: Record<ApprovalKind, string> = {
  SOURCE_ATTRIBUTION: 'Source attribution',
  NOTIFICATION: 'Official notification',
  FIELD_INVESTIGATION: 'Field investigation',
  FINAL_CLOSURE: 'Final closure',
};

export const VERDICT_META: Record<string, { label: string; cls: string }> = {
  VERIFIED_REDUCTION: { label: 'VERIFIED REDUCTION', cls: 'bg-green-600 text-white' },
  INCONCLUSIVE: { label: 'INCONCLUSIVE', cls: 'bg-slate-600 text-white' },
  STILL_LEAKING: { label: 'STILL LEAKING', cls: 'bg-red-600 text-white' },
  NO_INDEPENDENT_EVIDENCE: { label: 'NO INDEPENDENT EVIDENCE: STAYS VERIFICATION PENDING', cls: 'bg-amber-500 text-white' },
};

export const RESOURCE_LABEL: Record<string, string> = {
  ogi_inspector: 'OGI inspector',
  field_team: 'Field survey team',
  measurement_team: 'Measurement team',
};
