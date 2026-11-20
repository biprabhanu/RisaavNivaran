import { useState } from 'react';
import { CheckCircle2, Plus, Trash2 } from 'lucide-react';
import type { Measurement, VerificationResult } from '../types/api';
import { api, errMsg } from '../lib/api';
import { VERDICT_META } from '../lib/format';
import { IntervalChart } from '../components/IntervalChart';
import { Caption, Card, ErrorBox, LabelChip, PageTitle, btn } from '../components/ui';

interface PostForm { rate: number; u: number; independent: boolean; comparable: boolean }
interface Form { preRate: number; preU: number; preComparable: boolean; posts: PostForm[] }

const PRESETS: { name: string; form: Form }[] = [
  { name: 'Kanjur verified', form: { preRate: 1736, preU: 434, preComparable: true, posts: [{ rate: 610, u: 150, independent: true, comparable: true }] } },
  { name: 'Operator claim only', form: { preRate: 1736, preU: 434, preComparable: true, posts: [{ rate: 0, u: 0, independent: false, comparable: true }] } },
  {
    name: 'Conflicting',
    form: { preRate: 1736, preU: 434, preComparable: true, posts: [{ rate: 500, u: 120, independent: true, comparable: true }, { rate: 1500, u: 200, independent: true, comparable: true }] },
  },
  { name: 'Still leaking', form: { preRate: 1736, preU: 434, preComparable: true, posts: [{ rate: 1650, u: 300, independent: true, comparable: true }] } },
  { name: 'Overlap', form: { preRate: 1736, preU: 434, preComparable: true, posts: [{ rate: 1150, u: 250, independent: true, comparable: true }] } },
];

function toMeasurements(f: Form): { pre: Measurement; posts: Measurement[] } {
  const pre: Measurement = {
    id: 'PRE', rate_kg_h: f.preRate, uncertainty_kg_h: f.preU, date: '2025-02-09', method: 'Carbon Mapper satellite (pre-intervention)',
    independent: true, comparable_conditions: f.preComparable, actor: 'satellite', label: 'REAL DATA', notes: '',
  };
  const posts: Measurement[] = f.posts.map((p, i) => ({
    id: `POST-${i + 1}`, rate_kg_h: p.rate, uncertainty_kg_h: p.u, date: '2025-05-20',
    method: p.independent ? 'Independent measurement (simulated)' : 'Operator repair claim (simulated)',
    independent: p.independent, comparable_conditions: p.comparable, actor: 'simulated', label: 'SIMULATED EVENT', notes: '',
  }));
  return { pre, posts };
}

const inputCls = 'w-full p-2.5 rounded-xl border border-slate-200 text-sm font-semibold bg-white num';

export default function Verification() {
  const [form, setForm] = useState<Form>(PRESETS[0].form);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [usedPosts, setUsedPosts] = useState<Measurement[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async (f: Form = form) => {
    setBusy(true);
    setError(null);
    try {
      const body = toMeasurements(f);
      setResult(await api.verify(body));
      setUsedPosts(body.posts);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const setPost = (i: number, patch: Partial<PostForm>) => setForm((f) => ({ ...f, posts: f.posts.map((p, j) => (j === i ? { ...p, ...patch } : p)) }));

  return (
    <div className="space-y-5">
      <Caption>
        the evidence-gated closure rule. A case is a <strong>Verified Reduction</strong> only if the post-intervention interval lies entirely below the pre-intervention interval
        (post + u &lt; pre − u), with independent measurements under comparable conditions. A repair claim alone is never enough.
      </Caption>
      <PageTitle title="Mitigation verification" subtitle="Rule: post + u_post < pre − u_pre · conflicting measurements → Inconclusive" right={<LabelChip label="SIMULATED EVENT" />} />

      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.name}
            data-testid={`preset-${p.name.toLowerCase().replace(/\s+/g, '-')}`}
            className={btn.ghost}
            onClick={() => {
              setForm(p.form);
              run(p.form);
            }}
          >
            {p.name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-6 space-y-5 bg-slate-50">
          <h3 className="font-bold">Measurement parameters</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Pre-intervention rate (kg/h)</label>
              <input type="number" value={form.preRate} onChange={(e) => setForm({ ...form, preRate: Number(e.target.value) })} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Pre uncertainty (± kg/h)</label>
              <input type="number" value={form.preU} onChange={(e) => setForm({ ...form, preU: Number(e.target.value) })} className={inputCls} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={form.preComparable} onChange={(e) => setForm({ ...form, preComparable: e.target.checked })} className="w-4 h-4 accent-emerald-600" />
            Pre measurement taken under comparable conditions (wind, method)
          </label>

          {form.posts.map((p, i) => (
            <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-sm">Post-intervention measurement {form.posts.length > 1 ? i + 1 : ''}</h4>
                {form.posts.length > 1 && (
                  <button className="text-red-600 text-xs flex items-center gap-1" onClick={() => setForm({ ...form, posts: form.posts.filter((_, j) => j !== i) })}>
                    <Trash2 className="w-3.5 h-3.5" /> remove
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Rate (kg/h)</label>
                  <input type="number" value={p.rate} onChange={(e) => setPost(i, { rate: Number(e.target.value) })} className={inputCls} />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1">Uncertainty (± kg/h)</label>
                  <input type="number" value={p.u} onChange={(e) => setPost(i, { u: Number(e.target.value) })} className={inputCls} />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={p.independent} onChange={(e) => setPost(i, { independent: e.target.checked })} className="w-4 h-4 accent-emerald-600" />
                Independently measured (not an operator self-report)
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={p.comparable} onChange={(e) => setPost(i, { comparable: e.target.checked })} className="w-4 h-4 accent-emerald-600" />
                Comparable conditions
              </label>
            </div>
          ))}
          {form.posts.length < 2 && (
            <button className={btn.ghost} onClick={() => setForm({ ...form, posts: [...form.posts, { rate: 1400, u: 200, independent: true, comparable: true }] })}>
              <Plus className="w-4 h-4" /> Add a second post measurement (to test conflicts)
            </button>
          )}
          <button data-testid="run-verification" onClick={() => run()} disabled={busy} className={`${btn.primary} w-full py-3`}>
            <CheckCircle2 className="w-4 h-4" /> Run verification engine
          </button>
        </Card>

        <Card className="bg-slate-900 text-white border-slate-800 p-6 flex flex-col">
          <h3 className="font-bold text-slate-300 mb-4">Verification outcome</h3>
          {error && <ErrorBox error={error} />}
          {result ? (
            <div className="space-y-4" data-testid="verdict">
              <div className={`p-4 rounded-xl font-black text-center text-xl tracking-tight ${VERDICT_META[result.verdict]?.cls}`} data-testid="verdict-label">
                {VERDICT_META[result.verdict]?.label ?? result.verdict}
              </div>
              <ul className="text-sm text-slate-200 space-y-1 bg-slate-800/80 p-4 rounded-xl border border-slate-700 list-disc pl-8">
                {result.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
              <div className="grid grid-cols-2 gap-2 text-sm text-slate-300">
                <span>Pre lower bound (pre − u)</span>
                <span className="font-mono text-white text-right">{Math.round(result.pre_low)} kg/h</span>
                <span>Post upper bound (post + u)</span>
                <span className="font-mono text-white text-right">{result.post_high != null ? `${Math.round(result.post_high)} kg/h` : '—'}</span>
                {result.recurrence_threshold_kg_h != null && (
                  <>
                    <span>Recurrence threshold</span>
                    <span className="font-mono text-white text-right">{Math.round(result.recurrence_threshold_kg_h)} kg/h</span>
                  </>
                )}
              </div>
              <div className="bg-white rounded-xl p-2">
                <IntervalChart result={result} posts={usedPosts} />
              </div>
              <p className="text-xs text-slate-400">{result.rule}</p>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-center text-sm text-slate-400 italic">Pick a preset or click "Run verification engine".</div>
          )}
          <p className="mt-6 pt-4 border-t border-slate-800 text-xs text-slate-400 italic">
            Rule enforced: a repair-completion notification alone never closes a case. Independent post-intervention measurements are required.
          </p>
        </Card>
      </div>
    </div>
  );
}
