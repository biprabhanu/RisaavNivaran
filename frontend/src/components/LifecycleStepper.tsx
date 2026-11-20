// Visual case lifecycle (PDF slide 12): main path plus the three possible outcomes.
import { ChevronRight } from 'lucide-react';
import type { CaseStatus } from '../types/api';
import { STATUS_META } from '../lib/format';

const MAIN: CaseStatus[] = ['OPEN', 'SOURCE_ATTRIBUTION_PENDING', 'INVESTIGATION_REQUESTED', 'REPAIR_REPORTED', 'VERIFICATION_PENDING'];
const OUTCOMES: CaseStatus[] = ['VERIFIED_REDUCTION', 'INCONCLUSIVE', 'STILL_LEAKING', 'RECURRING'];

export function LifecycleStepper({ status }: { status: CaseStatus }) {
  const mainIdx = MAIN.indexOf(status);
  const pill = (s: CaseStatus, i: number, isMain: boolean) => {
    const current = s === status;
    const passed = isMain && mainIdx >= 0 && i < mainIdx;
    return (
      <div
        key={s}
        data-current={current}
        className={`px-3 py-1.5 rounded-lg border text-xs font-semibold whitespace-nowrap transition ${
          current
            ? `${STATUS_META[s].cls} ring-2 ring-offset-1 ring-teal-600`
            : passed
              ? 'bg-slate-100 text-slate-500 border-slate-200'
              : 'bg-white text-slate-400 border-slate-200'
        }`}
      >
        {STATUS_META[s].label}
      </div>
    );
  };
  return (
    <div className="flex flex-col gap-2" data-testid="lifecycle">
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {MAIN.map((s, i) => (
          <div key={s} className="flex items-center gap-1">
            {pill(s, i, true)}
            {i < MAIN.length - 1 && <ChevronRight className="w-4 h-4 text-slate-300" />}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Outcome →</span>
        <div className="flex flex-wrap items-center gap-1 rounded-xl border border-dashed border-slate-300 p-1">
          {OUTCOMES.map((s, i) => pill(s, i, false))}
        </div>
      </div>
    </div>
  );
}
