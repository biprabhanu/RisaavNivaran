import { Fragment, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChevronDown, ChevronRight, FlaskConical, Info, Loader2, RefreshCw } from 'lucide-react';
import type { EvaluationReport, PolicyMetrics } from '../types/api';
import { api, errMsg } from '../lib/api';
import { useApi } from '../lib/hooks';
import { showToast, useAppState } from '../lib/store';
import { fmtDate, hypLabel, inr, num } from '../lib/format';
import { Caption, Card, CardHeader, Chip, ErrorBox, PageTitle, Spinner, Stat, btn } from '../components/ui';

const POLICY_COLOR: Record<string, string> = { A: '#94a3b8', B: '#f59e0b', C: '#10b981', C_noplan: '#6366f1' };
const SHORT: Record<string, string> = { A: 'A: Alert-only', B: 'B: Checklist', C: 'C: PlumeProof', C_noplan: 'C-ablation (planner off)' };

/** Accept either 0–1 fractions or 0–100 percentages from the backend. */
const asPct = (v: number) => (v <= 1.0001 ? v * 100 : v);

function MetricChart({ title, subtitle, data, unit = '', digits = 1, testid, help, note, format }: {
  title: string; subtitle?: string; data: { id: string; value: number | null }[]; unit?: string; digits?: number; testid?: string; help?: string;
  note?: string; format?: (v: number) => string;
}) {
  const fmt = format ?? ((v: number) => `${v.toFixed(digits)}${unit}`);
  const rows = data.map((d) => ({ name: SHORT[d.id] ?? d.id, id: d.id, value: d.value ?? 0, missing: d.value == null }));
  return (
    <Card data-testid={testid}>
      <CardHeader
        title={title}
        subtitle={subtitle}
        right={help ? <span title={help} className="text-slate-400 cursor-help"><Info className="w-5 h-5" /></span> : undefined}
      />
      <div className="p-3">
        <ResponsiveContainer width="100%" height={230}>
          <BarChart data={rows} margin={{ top: 24, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#0f172a' }} interval={0} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={format ? (v: number) => fmt(v) : undefined} width={format ? 78 : 40} />
            <Tooltip formatter={(v: number) => fmt(v)} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} animationDuration={900}>
              {rows.map((r) => (
                <Cell key={r.id} fill={POLICY_COLOR[r.id] ?? '#64748b'} />
              ))}
              <LabelList
                dataKey="value"
                position="top"
                formatter={(v: number) => fmt(v)}
                style={{ fontSize: 13, fontWeight: 700, fill: '#0f172a' }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {note && <p className="text-sm text-slate-700 px-2 font-medium">{note}</p>}
        {help && <p className="text-xs text-slate-500 px-2">{help}</p>}
      </div>
    </Card>
  );
}

export default function Evaluation() {
  const { offline } = useAppState();
  const latest = useApi(() => api.evaluationLatest());
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [seed, setSeed] = useState(2026);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [openScenarios, setOpenScenarios] = useState(false);
  const [openRow, setOpenRow] = useState<string | null>(null);

  const r = report ?? latest.data;

  const rerun = async () => {
    setRunning(true);
    setErr(null);
    try {
      const rep = await api.evaluate({ seed, n_scenarios: 25 });
      setReport(rep);
      showToast(`Evaluation re-run with seed ${seed}: ${rep.n_scenarios} scenarios simulated.`);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setRunning(false);
    }
  };

  const pol = (id: string): PolicyMetrics | undefined => r?.policies.find((p) => p.policy_id === id);
  const series = (f: (p: PolicyMetrics) => number | null) => (r?.policies ?? []).map((p) => ({ id: p.policy_id, value: f(p) }));
  const C = pol('C');
  const B = pol('B');

  return (
    <div className="space-y-5">
      <Caption>
        the proof slide. 25 seeded scenarios, each with a hidden true source, run through three policies (alert-only, fixed checklist, PlumeProof) plus an ablation and a
        ±20% likelihood sensitivity test. <strong>All results are computed by running the simulator; nothing is typed in.</strong> Scenarios are simulated.
      </Caption>
      <PageTitle
        title="Evaluation: 25 simulated scenarios"
        subtitle={r ? `Generated ${fmtDate(r.generated_at)} · seed ${r.seed} · ${r.n_scenarios} scenarios` : 'Running the simulator…'}
        right={
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-600 flex items-center gap-1">
              seed
              <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} className="w-24 border border-slate-300 rounded-lg px-2 py-1.5 text-sm font-semibold" />
            </label>
            <button data-testid="rerun-evaluation" className={btn.primary} onClick={rerun} disabled={running || offline}>
              {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Re-run evaluation
            </button>
          </div>
        }
      />
      {err && <ErrorBox error={err} />}
      {latest.loading && !r && <Spinner text="Running 25 scenarios × 4 policies…" />}
      {latest.error && !r && <ErrorBox error={latest.error} onRetry={latest.reload} />}

      {r && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat label="PlumeProof false closures" value={`${C?.false_closures ?? '—'} / ${r.n_scenarios}`} sub="target: zero" tone="emerald" />
            <Stat label="Checklist false closures" value={`${B?.false_closures ?? '—'} / ${r.n_scenarios}`} sub="closes on repair claims" tone="red" />
            <Stat
              label="Source-ID inspections / case"
              value={`${num(C?.attribution_inspections_per_case, 2)} vs ${num(B?.attribution_inspections_per_case, 2)}`}
              sub="PlumeProof vs checklist"
              tone="blue"
            />
            <Stat label="PlumeProof traceability" value={`${num(C ? asPct(C.traceability_pct) : null, 0)}%`} sub="critical decisions with evidence + approval" tone="amber" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <MetricChart
              testid="chart-false-closures"
              title="False closures (lower is better)"
              subtitle="Cases closed without independent evidence of a reduction"
              data={series((p) => p.false_closures)}
              digits={0}
              note="A and B close on the operator's repair claim; a claim is never independent evidence, so every such closure counts as false."
            />
            <MetricChart
              testid="chart-attribution-inspections"
              title="Field inspections to identify the source, per case"
              subtitle="Headline efficiency metric (PDF objective 2): excludes verification"
              data={series((p) => p.attribution_inspections_per_case)}
              digits={2}
            />
            <MetricChart
              title="Inspections per resolved case (incl. verification)"
              subtitle="Secondary metric"
              data={series((p) => p.inspections_per_resolved)}
              digits={2}
              help="PlumeProof also pays for an independent post-repair measurement that the checklist and alert-only policies never do. That is exactly why it never closes falsely."
            />
            <MetricChart title="Cost per resolved case (₹)" data={series((p) => p.cost_per_resolved_inr)} digits={0} format={(v) => inr(v)} />
            <MetricChart title="Days to accountable stakeholder" subtitle="Detection → responsible operator assigned" data={series((p) => p.mean_days_to_stakeholder)} digits={1} unit=" d" />
            <MetricChart title="Decision traceability (%)" subtitle="Critical decisions linked to required evidence + human approval" data={series((p) => asPct(p.traceability_pct))} digits={0} unit="%" />
          </div>

          <Card className="overflow-hidden">
            <CardHeader title="Metrics table" subtitle="Every number below comes from the simulation run" />
            <div className="overflow-x-auto">
              <table className="w-full text-[13px] table-fixed" data-testid="metrics-table">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-[11px] uppercase tracking-wide border-b border-slate-200 text-right align-bottom leading-tight">
                    <th className="py-2 px-2 text-left w-[26%]">Policy</th>
                    <th className="py-2 px-2 whitespace-normal">Closed</th>
                    <th className="py-2 px-2 whitespace-normal">False closures</th>
                    <th className="py-2 px-2 whitespace-normal">Resolved</th>
                    <th className="py-2 px-2 whitespace-normal">Correct attribution</th>
                    <th className="py-2 px-2 whitespace-normal">Source-ID insp./case</th>
                    <th className="py-2 px-2 whitespace-normal">Insp./resolved</th>
                    <th className="py-2 px-2 whitespace-normal">Cost/resolved</th>
                    <th className="py-2 px-2 whitespace-normal">Days → stakeholder</th>
                    <th className="py-2 px-2 whitespace-normal">Traceability</th>
                    <th className="py-2 px-2 whitespace-normal">Days → closure</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-right num">
                  {r.policies.map((p) => (
                    <tr key={p.policy_id} className={p.policy_id === 'C' ? 'bg-emerald-50/60 font-semibold' : ''}>
                      <td className="py-2 px-2 text-left">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full" style={{ background: POLICY_COLOR[p.policy_id] }} />
                          <span className="font-bold">{p.policy_id === 'C_noplan' ? 'C-ablation (planner off)' : p.label}</span>
                        </div>
                        <div className="text-xs text-slate-500 font-normal ">{p.description}</div>
                      </td>
                      <td className="py-2 px-2 whitespace-nowrap">{p.closed_cases}</td>
                      <td className={`py-2 px-2 whitespace-nowrap font-bold ${p.false_closures === 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                        {p.false_closures} ({num(asPct(p.false_closure_rate), 0)}%)
                      </td>
                      <td className="py-2 px-2 whitespace-nowrap">{p.resolved_cases}</td>
                      <td className="py-2 px-2 whitespace-nowrap">{num(asPct(p.correct_attribution_rate), 0)}%</td>
                      <td className="py-2 px-2 whitespace-nowrap">{num(p.attribution_inspections_per_case, 2)}</td>
                      <td className="py-2 px-2 whitespace-nowrap">{num(p.inspections_per_resolved, 2)}</td>
                      <td className="py-2 px-2 whitespace-nowrap">{inr(p.cost_per_resolved_inr)}</td>
                      <td className="py-2 px-2 whitespace-nowrap">{num(p.mean_days_to_stakeholder, 1)}</td>
                      <td className="py-2 px-2 whitespace-nowrap">{num(asPct(p.traceability_pct), 0)}%</td>
                      <td className="py-2 px-2 whitespace-nowrap">{num(p.mean_days_to_closure, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="p-5" data-testid="sensitivity">
            <h3 className="font-bold flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-violet-600" /> Sensitivity: every likelihood perturbed by ±{num(asPct(r.sensitivity.perturbation), 0)}% ({r.sensitivity.n_draws} draws)
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <Stat label="Top action unchanged" value={`${num(asPct(r.sensitivity.top_action_stability_pct), 0)}%`} sub="of perturbed draws" tone="emerald" />
              <Stat label="Mean Kendall τ" value={num(r.sensitivity.mean_kendall_tau, 2)} sub="1 = identical ranking" />
              <Stat label="C false closures (perturbed worlds)" value={r.sensitivity.c_false_closures_perturbed} sub="evidence gate still holds" tone={r.sensitivity.c_false_closures_perturbed === 0 ? 'emerald' : 'red'} />
              <Stat label="C insp./resolved (perturbed)" value={num(r.sensitivity.c_inspections_per_resolved_perturbed, 2)} />
            </div>
            <div className="flex flex-wrap gap-2 mt-3 text-sm">
              <span className="text-slate-500">Top-ranked action across draws:</span>
              {Object.entries(r.sensitivity.top_action_counts).map(([a, n]) => (
                <Chip key={a}>
                  {a}: {n}
                </Chip>
              ))}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <button className="w-full" onClick={() => setOpenScenarios((o) => !o)}>
              <CardHeader title={`Scenario details (${r.scenarios.length})`} subtitle="Hidden true source, tags, and the outcome per policy" right={openScenarios ? <ChevronDown /> : <ChevronRight />} />
            </button>
            {openScenarios && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                      <th className="py-2 px-4 text-left">Scenario</th>
                      <th className="py-2 px-4 text-left">True source</th>
                      <th className="py-2 px-4 text-left">Tags</th>
                      {r.policies.map((p) => (
                        <th key={p.policy_id} className="py-2 px-4 text-left">
                          {SHORT[p.policy_id] ?? p.policy_id}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {r.scenarios.map((s) => (
                      <Fragment key={s.scenario_id}>
                        <tr className="hover:bg-slate-50 cursor-pointer" onClick={() => setOpenRow(openRow === s.scenario_id ? null : s.scenario_id)}>
                          <td className="py-2 px-4 font-mono font-bold">{s.scenario_id}</td>
                          <td className="py-2 px-4">{hypLabel(s.true_source)}</td>
                          <td className="py-2 px-4">
                            <div className="flex flex-wrap gap-1">
                              {s.tags.map((t) => (
                                <Chip key={t} className="bg-amber-50 text-amber-900 border-amber-200">
                                  {t}
                                </Chip>
                              ))}
                            </div>
                          </td>
                          {r.policies.map((p) => {
                            const o = s.outcomes[p.policy_id];
                            if (!o) return <td key={p.policy_id} />;
                            return (
                              <td key={p.policy_id} className="py-2 px-4">
                                <span className={`text-xs font-semibold ${o.false_closure ? 'text-red-700' : o.resolved ? 'text-emerald-700' : 'text-slate-600'}`}>
                                  {o.false_closure ? '✗ false closure' : o.final_status.replace(/_/g, ' ').toLowerCase()}
                                </span>
                                <div className="text-[11px] text-slate-500">
                                  {o.attribution_inspections} src-insp · {inr(o.cost_inr)}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                        {openRow === s.scenario_id && (
                          <tr className="bg-slate-50">
                            <td colSpan={3 + r.policies.length} className="px-4 py-3 text-xs text-slate-700">
                              <p className="mb-2">{s.description}</p>
                              {r.policies.map((p) => (
                                <p key={p.policy_id}>
                                  <strong>{SHORT[p.policy_id]}:</strong> {s.outcomes[p.policy_id]?.actions.join(' → ')}
                                </p>
                              ))}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="grid lg:grid-cols-2 gap-5">
            <Card className="p-5">
              <h3 className="font-bold mb-2">Metric definitions</h3>
              <dl className="space-y-2 text-sm">
                {Object.entries(r.definitions).map(([k, v]) => (
                  <div key={k}>
                    <dt className="font-semibold">{k}</dt>
                    <dd className="text-slate-600">{v}</dd>
                  </div>
                ))}
              </dl>
            </Card>
            <Card className="p-5">
              <h3 className="font-bold mb-2">Notes & honest caveats</h3>
              <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
                {r.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
