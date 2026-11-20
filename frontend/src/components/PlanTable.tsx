// The Evidence Planner table: ranked actions + excluded (struck-through) actions with reasons.
import { Fragment, useState } from 'react';
import { ChevronDown, ChevronRight, Ban, Trophy } from 'lucide-react';
import type { ActionSpec, PlanResult } from '../types/api';
import { bits, hypIds, hypLabel, inr, num, pct } from '../lib/format';

interface Props {
  plan: PlanResult;
  before?: PlanResult | null; // shows "was #n" when the plan was re-ranked
  actions?: ActionSpec[]; // needed for the availability toggles
  onToggle?: (action: ActionSpec, makeUnavailable: boolean) => void;
  compact?: boolean;
}

export function PlanTable({ plan, before, actions, onToggle, compact = false }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const beforeRank = new Map(before?.ranked.map((r) => [r.action_id, r.rank]) ?? []);
  const newlyExcluded = new Set(
    plan.excluded.filter((e) => !before || !before.excluded.some((b) => b.action_id === e.action_id)).map((e) => e.action_id),
  );
  const spec = (id: string) => actions?.find((a) => a.id === id);
  const cell = compact ? 'py-2 px-3' : 'py-3 px-4';

  return (
    <div className="overflow-x-auto" data-testid="plan-table">
      <table className="w-full text-left border-collapse text-sm">
        <thead>
          <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
            <th className={`${cell} font-semibold`}>#</th>
            <th className={`${cell} font-semibold`}>Investigation action</th>
            <th className={`${cell} font-semibold text-right`}>EIG</th>
            <th className={`${cell} font-semibold text-right`}>Cost</th>
            <th className={`${cell} font-semibold text-right`}>Time</th>
            {!compact && <th className={`${cell} font-semibold text-right`}>Cost + λ·time</th>}
            <th className={`${cell} font-semibold text-right`} title="score = EIG / (cost + λ·time), shown ×10,000">Score</th>
            <th className={`${cell} font-semibold text-right`}>Gain / ₹10k</th>
            {onToggle && <th className={`${cell} font-semibold text-right`}>Availability</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {plan.ranked.map((r) => {
            const was = beforeRank.get(r.action_id);
            const s = spec(r.action_id);
            const isOpen = open === r.action_id;
            return (
              <Fragment key={r.action_id}>
                <tr className={`transition ${r.rank === 1 ? 'bg-emerald-50/60' : 'hover:bg-slate-50/80'}`} data-testid={`ranked-${r.action_id}`}>
                  <td className={cell}>
                    <span className={`inline-flex w-7 h-7 items-center justify-center rounded-full text-xs font-bold ${r.rank === 1 ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-700'}`}>{r.rank}</span>
                  </td>
                  <td className={`${cell} font-semibold text-slate-900`}>
                    <button className="flex items-center gap-1.5 text-left" onClick={() => setOpen(isOpen ? null : r.action_id)}>
                      {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                      {r.rank === 1 && <Trophy className="w-4 h-4 text-emerald-600" />}
                      {r.label}
                    </button>
                    {was != null && was !== r.rank && (
                      <span className="ml-7 text-xs font-semibold text-amber-700">re-ranked: was #{was}</span>
                    )}
                  </td>
                  <td className={`${cell} text-right font-semibold num`}>{bits(r.eig_bits)}</td>
                  <td className={`${cell} text-right num`}>{inr(r.cost_inr)}</td>
                  <td className={`${cell} text-right num`}>{num(r.time_days)} d</td>
                  {!compact && <td className={`${cell} text-right num text-slate-600`}>{inr(r.effective_cost)}</td>}
                  <td className={`${cell} text-right font-extrabold text-emerald-700 num`}>{r.score_per_10k.toFixed(2)}</td>
                  <td className={`${cell} text-right num`}>{r.gain_per_10k == null ? '—' : r.gain_per_10k.toFixed(2)}</td>
                  {onToggle && (
                    <td className={`${cell} text-right`}>
                      {s && s.resources.length > 0 ? (
                        <button
                          data-testid={`toggle-${r.action_id}`}
                          onClick={() => onToggle(s, true)}
                          className="bg-red-50 text-red-700 border border-red-200 px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-red-100 transition"
                        >
                          Mark unavailable
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400" title="No limited resource needed for this action">always available</span>
                      )}
                    </td>
                  )}
                </tr>
                {isOpen && (
                  <tr className="bg-slate-50/70">
                    <td />
                    <td colSpan={onToggle ? 8 : compact ? 6 : 7} className="px-4 pb-3 pt-1">
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Possible outcomes (computed with Bayes' rule)</p>
                      <div className="grid md:grid-cols-3 gap-2">
                        {r.outcomes.map((o) => (
                          <div key={o.outcome_id} className="rounded-lg border border-slate-200 bg-white p-2 text-xs">
                            <div className="font-semibold text-slate-800">
                              {o.label} <span className="text-slate-500 font-normal">P = {pct(o.probability)}</span>
                            </div>
                            <div className="text-slate-600 mt-1">
                              → {hypIds().map((h) => `${hypLabel(h).split(' ')[0]} ${pct(o.posterior[h] ?? 0)}`).join(' · ')}
                            </div>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
          {plan.excluded.map((e) => {
            const s = spec(e.action_id);
            return (
              <tr key={e.action_id} className={`bg-red-50/40 ${newlyExcluded.has(e.action_id) && before ? 'animate-slidein' : ''}`} data-testid={`excluded-${e.action_id}`}>
                <td className={cell}>
                  <Ban className="w-5 h-5 text-red-500" />
                </td>
                <td className={`${cell}`}>
                  <span className="line-through text-slate-500 font-semibold">{e.label}</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {e.reasons.map((reason, i) => (
                      <span key={i} className="text-[11px] font-semibold bg-red-100 text-red-800 border border-red-200 rounded px-1.5 py-0.5">
                        EXCLUDED: {reason}
                      </span>
                    ))}
                  </div>
                </td>
                <td className={`${cell} text-right text-slate-400 line-through num`}>{bits(e.eig_bits)}</td>
                <td className={`${cell} text-right text-slate-400`} colSpan={compact ? 4 : 5}>
                  excluded before ranking
                </td>
                {onToggle && (
                  <td className={`${cell} text-right`}>
                    {s && s.resources.length > 0 && e.reason_codes.includes('RESOURCE_UNAVAILABLE') ? (
                      <button
                        data-testid={`toggle-${e.action_id}`}
                        onClick={() => onToggle(s, false)}
                        className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-emerald-100 transition"
                      >
                        Mark available
                      </button>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-slate-500 mt-2 px-1">
        score = EIG / (cost + λ·time) × 10,000 (bits per ₹10k-equivalent) · λ = {inr(plan.lam)}/day · current uncertainty {bits(plan.entropy_bits)}
      </p>
    </div>
  );
}
