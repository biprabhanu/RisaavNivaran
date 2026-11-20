import { useEffect, useState } from 'react';
import { FlaskConical } from 'lucide-react';
import type { Belief, WhatIfResult } from '../types/api';
import { api, errMsg } from '../lib/api';
import { useAppState } from '../lib/store';
import { bits, hypColor, hypIds, hypLabel, inr, pct } from '../lib/format';
import { normalise } from '../lib/bayes';
import { BeliefChart } from '../components/BeliefChart';
import { Card, CardHeader, ErrorBox, PageTitle, Spinner, Stat, btn } from '../components/ui';

export default function WhatIf() {
  const { meta } = useAppState();
  const [actionId, setActionId] = useState('records_request');
  const [outcomeId, setOutcomeId] = useState('fault_found');
  const [prior, setPrior] = useState<Belief | null>(null);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const defaultPrior = (): Belief => Object.fromEntries((meta?.hypotheses ?? []).map((h) => [h.id, h.prior]));
  useEffect(() => {
    if (meta && !prior) setPrior(defaultPrior());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta]);

  const action = meta?.actions.find((a) => a.id === actionId);
  useEffect(() => {
    if (action && !action.outcomes.some((o) => o.id === outcomeId)) setOutcomeId(action.outcomes[0]?.id ?? '');
  }, [action, outcomeId]);

  useEffect(() => {
    if (!prior || !action || !action.outcomes.some((o) => o.id === outcomeId)) return;
    let alive = true;
    api
      .whatif({ action_id: actionId, outcome_id: outcomeId, prior })
      .then((r) => alive && (setResult(r), setError(null)))
      .catch((e) => alive && setError(errMsg(e)));
    return () => {
      alive = false;
    };
  }, [actionId, outcomeId, prior, action]);

  const setOne = (h: string, v: number) => {
    if (!prior) return;
    // Keep the edited hypothesis at v and rescale the others so everything sums to 1.
    const others = hypIds().filter((x) => x !== h);
    const rest = others.reduce((s, x) => s + (prior[x] ?? 0), 0);
    const next: Belief = { [h]: v };
    others.forEach((x) => (next[x] = rest > 0 ? ((prior[x] ?? 0) / rest) * (1 - v) : (1 - v) / others.length));
    setPrior(normalise(next));
  };

  if (!meta) return <Spinner />;
  const u = result?.update;

  return (
    <div className="space-y-5">
      <PageTitle description="Pick an investigation and an outcome, and watch Bayes' rule update the beliefs." title="What-if: play the evidence yourself" meta="Same likelihood tables the agent uses" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="p-5 space-y-5">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">1. Investigation action</label>
            <div className="mt-2 space-y-2">
              {meta.actions.map((a) => (
                <button
                  key={a.id}
                  data-testid={`whatif-action-${a.id}`}
                  onClick={() => setActionId(a.id)}
                  className={`w-full text-left rounded-xl border px-3 py-2 text-sm transition ${a.id === actionId ? 'border-teal-500 bg-teal-50 ring-1 ring-teal-400' : 'border-slate-200 hover:bg-slate-50'}`}
                >
                  <div className="font-semibold">{a.label}</div>
                  <div className="text-xs text-slate-500">
                    {inr(a.cost_inr)} · {a.time_days} d
                  </div>
                </button>
              ))}
            </div>
          </div>
          {action && (
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">2. Outcome you observe</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {action.outcomes.map((o) => {
                  const p = result?.outcomes.find((x) => x.outcome_id === o.id)?.probability;
                  return (
                    <button
                      key={o.id}
                      data-testid={`whatif-outcome-${o.id}`}
                      onClick={() => setOutcomeId(o.id)}
                      className={o.id === outcomeId ? btn.primary : btn.ghost}
                    >
                      {o.label} {p != null && <span className="opacity-75">({pct(p)})</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">3. Starting belief (prior)</label>
              <button className="text-xs underline text-slate-500" onClick={() => setPrior(defaultPrior())}>
                reset to 50/35/15
              </button>
            </div>
            <div className="mt-2 space-y-2">
              {prior &&
                hypIds().map((h) => (
                  <div key={h}>
                    <div className="flex justify-between text-sm">
                      <span style={{ color: hypColor(h) }} className="font-semibold">
                        {hypLabel(h)}
                      </span>
                      <span className="num font-bold">{pct(prior[h] ?? 0)}</span>
                    </div>
                    <input type="range" min={0.01} max={0.98} step={0.01} value={prior[h] ?? 0} onChange={(e) => setOne(h, Number(e.target.value))} className="w-full" style={{ accentColor: hypColor(h) }} />
                  </div>
                ))}
            </div>
          </div>
        </Card>

        <div className="lg:col-span-2 space-y-5">
          {error && <ErrorBox error={error} />}
          {u && result && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Stat label="P(this outcome)" value={pct(u.outcome_probability, 1)} sub="Σ_h P(y|h)·P(h)" tone="teal" />
                <Stat label="Entropy before" value={bits(u.entropy_before)} />
                <Stat label="Entropy after" value={bits(u.entropy_after)} tone={u.entropy_after < u.entropy_before ? 'green' : 'amber'} />
                <Stat label="EIG of this action" value={bits(result.eig_bits)} sub="expected, before seeing the outcome" tone="teal" />
              </div>
              <Card>
                <CardHeader title="Belief before → after" subtitle="Grey = prior, colour = posterior" icon={<FlaskConical className="w-5 h-5 text-slate-600" />} />
                <div className="p-4" data-testid="whatif-result">
                  <BeliefChart key={`${actionId}-${outcomeId}`} belief={u.posterior} before={u.prior} height={240} />
                </div>
              </Card>
              <Card>
                <CardHeader title="All possible outcomes of this action" />
                <div className="p-4 grid md:grid-cols-3 gap-3">
                  {result.outcomes.map((o) => (
                    <div key={o.outcome_id} className={`rounded-xl border p-3 text-sm ${o.outcome_id === outcomeId ? 'border-teal-400 bg-teal-50' : 'border-slate-200'}`}>
                      <div className="font-semibold">{o.label}</div>
                      <div className="text-slate-500 text-xs">P = {pct(o.probability, 1)} · H after = {bits(o.entropy_after)}</div>
                      <ul className="mt-2 space-y-0.5">
                        {hypIds().map((h) => (
                          <li key={h} className="flex justify-between">
                            <span>{hypLabel(h)}</span>
                            <span className="num font-semibold">{pct(o.posterior[h] ?? 0)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
