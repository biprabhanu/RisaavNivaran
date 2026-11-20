import { useEffect, useState } from 'react';
import { Lightbulb, MessageSquareText, ShieldAlert, Sparkles } from 'lucide-react';
import type { ActionSpec, Constraints, DraftResult } from '../types/api';
import { api, errMsg } from '../lib/api';
import { useApi } from '../lib/hooks';
import { bumpData, showToast, useAppState } from '../lib/store';
import { bits, hypLabel, inr, RESOURCE_LABEL } from '../lib/format';
import { PlanTable } from '../components/PlanTable';
import { Caption, Card, CardHeader, Chip, ErrorBox, PageTitle, Spinner, btn } from '../components/ui';

export default function Planner() {
  const { meta, offline } = useAppState();
  const cases = useApi(() => api.cases());
  const [caseId, setCaseId] = useState('KJ-2025-02');
  const [lamInput, setLamInput] = useState<number | null>(null);
  const [lam, setLam] = useState<number | null>(null);
  const detail = useApi(() => api.caseDetail(caseId), [caseId]);
  const plan = useApi(() => api.plan(caseId, lam ?? undefined), [caseId, lam]);
  const [explain, setExplain] = useState<DraftResult | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [saving, setSaving] = useState(false);

  // Initialise the slider from the case's λ.
  useEffect(() => {
    if (detail.data && lamInput == null) setLamInput(detail.data.case.lam);
  }, [detail.data, lamInput]);
  // Debounce the slider so we don't call the API on every pixel.
  useEffect(() => {
    if (lamInput == null) return;
    const t = setTimeout(() => setLam(lamInput), 250);
    return () => clearTimeout(t);
  }, [lamInput]);

  const constraints = detail.data?.case.constraints;

  const save = async (next: Constraints, msg: string) => {
    setSaving(true);
    try {
      const p = await api.setConstraints(caseId, next);
      plan.setData(p);
      showToast(msg);
      bumpData();
    } catch (e) {
      showToast(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const toggle = (a: ActionSpec, makeUnavailable: boolean) => {
    if (!constraints) return;
    const set = new Set(constraints.unavailable_resources);
    a.resources.forEach((r) => (makeUnavailable ? set.add(r) : set.delete(r)));
    save(
      { ...constraints, unavailable_resources: [...set] },
      makeUnavailable ? `${a.label}: resource marked unavailable. The agent excluded it and re-ranked.` : `${a.label}: resource available again. Re-ranked.`,
    );
  };

  const toggleFlag = (kind: 'permit' | 'fire', on: boolean) => {
    if (!constraints) return;
    if (kind === 'permit') {
      const g = new Set(constraints.granted_authorisations);
      if (on) g.add('site_access_permit');
      else g.delete('site_access_permit');
      save({ ...constraints, granted_authorisations: [...g] }, on ? 'Site access permit granted.' : 'Site access permit withdrawn: actions needing it are excluded.');
    } else {
      const f = new Set(constraints.safety_flags);
      if (on) f.add('landfill_fire');
      else f.delete('landfill_fire');
      save({ ...constraints, safety_flags: [...f] }, on ? 'Safety flag raised (landfill fire): field actions excluded.' : 'Safety flag cleared.');
    }
  };

  const askExplain = async () => {
    setExplaining(true);
    try {
      setExplain(await api.draft(caseId, { kind: 'ranking_explanation', lam: lam ?? undefined }));
    } catch (e) {
      showToast(errMsg(e));
    } finally {
      setExplaining(false);
    }
  };

  const p = plan.data;
  const top = p?.ranked[0];
  const maxEig = p ? [...p.ranked].sort((a, b) => b.eig_bits - a.eig_bits)[0] : undefined;
  const unavailable = constraints?.unavailable_resources ?? [];

  return (
    <div className="space-y-5">
      <Caption>
        the agent's ranking of the next investigation. It is not "most information first" but <strong>information per rupee and per day</strong>: score = EIG / (cost + λ·time).
        Scores change with λ; the ranking is robust across 0–20,000 ₹/day. Use <strong>Mark unavailable</strong> to see the agent re-rank.
      </Caption>
      <PageTitle
        title="Evidence Planner"
        subtitle="Expected information gain (EIG) from Bayesian likelihood tables P(outcome | source, action)"
        right={
          (cases.data?.length ?? 0) > 1 ? (
            <select value={caseId} onChange={(e) => setCaseId(e.target.value)} className="border border-slate-300 rounded-xl px-3 py-2 font-semibold bg-white">
              {cases.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id}: {c.facility_name}
                </option>
              ))}
            </select>
          ) : undefined
        }
      />

      {top && (
        <div className="rounded-2xl bg-emerald-600 text-white p-5 shadow flex flex-col md:flex-row md:items-center justify-between gap-3" data-testid="top-pick">
          <div>
            <p className="text-xs uppercase tracking-widest font-bold text-emerald-100">Top recommended action</p>
            <p className="text-2xl font-extrabold">{top.label}</p>
          </div>
          <div className="text-right text-sm">
            <div className="font-bold text-lg">
              {bits(top.eig_bits)} for {inr(top.cost_inr)} + {top.time_days} day{top.time_days === 1 ? '' : 's'}
            </div>
            <div className="text-emerald-100">{top.gain_per_10k != null ? `${top.gain_per_10k.toFixed(2)} bits per ₹10,000` : 'free, but slow'}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <Card className="xl:col-span-3">
          <CardHeader title="Ranked investigation actions" subtitle="Click a row to see its possible outcomes and resulting beliefs" icon={<Sparkles className="w-5 h-5 text-emerald-600" />} />
          <div className="p-4">
            {plan.loading && !p && <Spinner />}
            {plan.error && <ErrorBox error={plan.error} onRetry={plan.reload} />}
            {p && <PlanTable plan={p} actions={meta?.actions} onToggle={offline ? undefined : toggle} />}
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="p-5">
            <h3 className="font-bold">λ: value of one day of delay</h3>
            <p className="text-sm text-slate-500">Converts days into rupees. High λ favours fast actions; λ = 0 ranks on money only.</p>
            <input
              data-testid="lambda-slider"
              type="range"
              min={0}
              max={20000}
              step={250}
              value={lamInput ?? 1000}
              onChange={(e) => setLamInput(Number(e.target.value))}
              className="w-full mt-3 accent-emerald-600"
            />
            <div className="flex justify-between text-sm">
              <span className="text-slate-400">₹0</span>
              <span className="font-extrabold text-emerald-700 num">{inr(lamInput ?? 1000)} / day</span>
              <span className="text-slate-400">₹20,000</span>
            </div>
            {p && (
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm" data-testid="lambda-scores">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Live scores at this λ (bits per ₹10k-equivalent)</p>
                {p.ranked.map((r) => (
                  <div key={r.action_id} className="flex justify-between gap-2">
                    <span className="truncate">#{r.rank} {r.label}</span>
                    <span className="font-bold text-emerald-700 num whitespace-nowrap">{r.score_per_10k.toFixed(3)}</span>
                  </div>
                ))}
                <p className="text-xs text-slate-500 mt-1">The order holds across the whole range: the ranking is robust to λ.</p>
              </div>
            )}
            <button className="mt-2 text-xs text-slate-500 underline" onClick={() => setLamInput(meta?.default_lambda ?? 1000)}>
              reset to default ({inr(meta?.default_lambda ?? 1000)})
            </button>
          </Card>

          <Card className="p-5">
            <h3 className="font-bold flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-red-600" /> Constraints
            </h3>
            <p className="text-sm text-slate-500">Violating actions are excluded <em>before</em> ranking.</p>
            <div className="mt-3 space-y-2 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  disabled={!constraints || saving || offline}
                  checked={constraints?.granted_authorisations.includes('site_access_permit') ?? false}
                  onChange={(e) => toggleFlag('permit', e.target.checked)}
                  className="w-4 h-4 accent-emerald-600"
                />
                Site access permit granted (human authorisation)
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  disabled={!constraints || saving || offline}
                  checked={constraints?.safety_flags.includes('landfill_fire') ?? false}
                  onChange={(e) => toggleFlag('fire', e.target.checked)}
                  className="w-4 h-4 accent-red-600"
                />
                Active landfill fire (safety)
              </label>
              <div className="pt-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Unavailable resources</p>
                {unavailable.length === 0 ? (
                  <span className="text-slate-400 text-xs">none</span>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {unavailable.map((r) => (
                      <Chip key={r} className="bg-red-100 text-red-800 border-red-200">
                        {RESOURCE_LABEL[r] ?? r}
                      </Chip>
                    ))}
                  </div>
                )}
              </div>
              {(constraints?.performed_actions.length ?? 0) > 0 && (
                <div className="pt-1">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Already performed</p>
                  <div className="flex flex-wrap gap-1">
                    {constraints?.performed_actions.map((a) => (
                      <Chip key={a}>{meta?.actions.find((x) => x.id === a)?.label ?? a}</Chip>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader title="Explain this ranking" icon={<Lightbulb className="w-5 h-5 text-amber-500" />} subtitle="Deterministic explanation, computed from the same numbers as the table" />
        <div className="p-5 space-y-4">
          {p && <p className="text-[15px] text-slate-800 whitespace-pre-line leading-relaxed" data-testid="plan-explanation">{p.explanation}</p>}
          {p && maxEig && top && maxEig.action_id !== top.action_id && (
            <div className="rounded-xl bg-blue-50/60 border border-blue-100 p-4 text-sm text-blue-950">
              <strong>Why the most informative action isn't first:</strong> "{maxEig.label}" has the highest EIG ({bits(maxEig.eig_bits)}) but costs {inr(maxEig.cost_inr)} and takes {maxEig.time_days} days,
              so its score is {maxEig.score_per_10k.toFixed(2)} vs {top.score_per_10k.toFixed(2)} for "{top.label}". Current leading hypothesis:{' '}
              {hypLabel(Object.entries(p.belief).sort((a, b) => b[1] - a[1])[0]?.[0])}.
            </div>
          )}
          <div>
            <button data-testid="explain-llm" className={btn.dark} onClick={askExplain} disabled={explaining || offline}>
              <MessageSquareText className="w-4 h-4" /> {explaining ? 'Drafting…' : 'Explain this ranking (LLM)'}
            </button>
            {explain && (
              <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <Chip className={explain.mode === 'llm' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-slate-200 text-slate-700 border-slate-300'}>
                  {explain.mode === 'llm' ? `Drafted by ${explain.model ?? 'Claude'}` : 'Template mode (no API key)'}
                </Chip>
                <p className="mt-2 text-sm text-slate-800 whitespace-pre-line">{explain.text}</p>
                <p className="mt-2 text-xs text-slate-500">The LLM only rephrases; the ranking itself comes from deterministic, tested code.</p>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
