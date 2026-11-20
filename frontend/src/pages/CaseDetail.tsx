import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Building2, CalendarClock, Clock, FileSignature, HelpCircle, Lock, Search, ScrollText } from 'lucide-react';
import type { DraftResult, TransitionDecision } from '../types/api';
import { api, errMsg } from '../lib/api';
import { useApi } from '../lib/hooks';
import { bumpData, showToast } from '../lib/store';
import { bits, fmtDate, hypColor, hypIds, hypLabel, kgh, VERDICT_META } from '../lib/format';
import { entropy } from '../lib/bayes';
import { BeliefChart } from '../components/BeliefChart';
import { IntervalChart } from '../components/IntervalChart';
import { LifecycleStepper } from '../components/LifecycleStepper';
import { Card, CardHeader, Chip, ErrorBox, LabelChip, Spinner, StatusPill, btn } from '../components/ui';

export default function CaseDetailPage() {
  const { id = 'KJ-2025-02' } = useParams();
  const { data, error, loading, reload } = useApi(() => api.caseDetail(id), [id]);
  const [draft, setDraft] = useState<{ kind: string; result: DraftResult } | null>(null);
  const [drafting, setDrafting] = useState<string | null>(null);
  const [decision, setDecision] = useState<TransitionDecision | null>(null);

  const doDraft = async (kind: 'notice' | 'case_summary') => {
    setDrafting(kind);
    try {
      const r = await api.draft(id, { kind });
      setDraft({ kind, result: r });
      if (kind === 'notice') {
        showToast('Notice drafted. It now waits in the Approval Queue; nothing is sent without a human.');
        bumpData();
      }
    } catch (e) {
      showToast(errMsg(e));
    } finally {
      setDrafting(null);
    }
  };

  const tryClose = async () => {
    try {
      const d = await api.requestTransition(id, { to_status: 'VERIFIED_REDUCTION', actor: 'human', actor_name: 'Human reviewer', reason: 'Close case from Case page' });
      setDecision(d);
      bumpData();
    } catch (e) {
      showToast(errMsg(e));
    }
  };

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return null;
  const c = data.case;
  const history = c.belief_history.map((s, i) => ({
    name: s.sim_date ? fmtDate(s.sim_date) : `#${i + 1}`,
    ...Object.fromEntries(hypIds().map((h) => [h, Math.round((s.belief[h] ?? 0) * 1000) / 10])),
    reason: s.reason,
  }));

  return (
    <div className="space-y-5">

      <Card className="p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl md:text-[28px] font-bold tracking-tight">
                {c.id}: {data.facility.name}
              </h1>
              <StatusPill status={c.status} large />
              <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${c.priority === 'Critical' ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-amber-50 text-amber-800 border border-amber-200'}`}>{c.priority} priority</span>
            </div>
            <p className="text-[15px] text-slate-600 mt-1.5" data-testid="page-caption">
              Everything the agent knows about this case: observations, hypotheses, stakeholders and deadlines.
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {data.facility.location} · {c.title} · in-world date {fmtDate(c.sim_date)}
              {c.reopen_count > 0 && <span className="ml-2 text-red-700 font-semibold">· reopened {c.reopen_count}×</span>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/planner" className={btn.primary}>
              <Search className="w-4 h-4" /> Evidence Planner
            </Link>
            <Link to="/audit" className={btn.dark}>
              <Clock className="w-4 h-4" /> Audit timeline
            </Link>
          </div>
        </div>
        <div className="mt-5">
          <LifecycleStepper status={c.status} />
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Satellite observations" right={<LabelChip label="REAL DATA" />} />
          <div className="p-5 grid sm:grid-cols-2 gap-3">
            {data.observations.map((o) => (
              <div key={o.id} className="p-4 rounded-xl border border-slate-100 bg-slate-50/30">
                <div className="flex items-center justify-between">
                  <span className="font-bold">{o.plume_label}</span>
                  <span className="text-xs text-slate-700 font-semibold">{fmtDate(o.date)}</span>
                </div>
                <div className="my-2">
                  <span className="text-2xl font-bold text-slate-900 num">{Math.round(o.rate_kg_h).toLocaleString('en-US')}</span>
                  <span className="text-sm text-slate-600 ml-1">kg CH₄/h{o.uncertainty_kg_h ? ` ± ${Math.round(o.uncertainty_kg_h)}` : ''}</span>
                </div>
                <div className="flex items-center gap-2">
                  <LabelChip label={o.label} />
                  <span className="text-xs text-slate-500">{o.source}</span>
                </div>
                {o.notes && <p className="text-xs text-slate-500 mt-1">{o.notes}</p>}
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Guardrail demo" icon={<Lock className="w-5 h-5 text-red-600" />} />
          <div className="p-5 space-y-3">
            <p className="text-sm text-slate-600">
              Ask to move this case to <strong>Verified Reduction</strong>. The state machine checks the workflow rules: only independent evidence plus a human approval can
              close a case.
            </p>
            <button data-testid="try-close" className={btn.danger} onClick={tryClose}>
              <Lock className="w-4 h-4" /> Try to close case
            </button>
            {decision && (
              <div data-testid="transition-decision" className={`rounded-xl border p-3 text-sm ${decision.allowed ? 'border-teal-300 bg-teal-50 text-teal-900' : 'border-red-300 bg-red-50 text-red-900'}`}>
                <strong>{decision.allowed ? 'ALLOWED' : decision.requires_approval ? 'NEEDS HUMAN APPROVAL' : 'REJECTED'}</strong>: {decision.reason}
              </div>
            )}
            {c.attributed_source && (
              <p className="text-sm">
                Attributed source (human-approved): <strong>{hypLabel(c.attributed_source)}</strong>
              </p>
            )}
            {c.repaired_source && (
              <p className="text-sm">
                Repair reported on: <strong>{hypLabel(c.repaired_source)}</strong>
              </p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <CardHeader title="Source hypotheses (current belief)" subtitle={`Entropy ${bits(entropy(c.belief))}`} right={<LabelChip label="AGENT ACTION" />} />
          <div className="p-4">
            <BeliefChart belief={c.belief} />
          </div>
        </Card>
        <Card>
          <CardHeader title="How the belief evolved" subtitle="Every point is a logged Bayesian update" />
          <div className="p-4">
            {history.length > 1 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={history} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: number) => `${v}%`} />
                  <Legend wrapperStyle={{ fontSize: 13 }} />
                  {hypIds().map((h) => (
                    <Line key={h} type="stepAfter" dataKey={h} name={hypLabel(h)} stroke={hypColor(h)} strokeWidth={3} dot={{ r: 4 }} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-slate-400 italic py-10 text-center">Only the prior so far.</p>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card>
          <CardHeader title="Outstanding questions" icon={<HelpCircle className="w-5 h-5 text-amber-600" />} />
          <ul className="p-5 space-y-2 text-sm">
            {c.outstanding_questions.length === 0 && <li className="text-slate-400 italic">None.</li>}
            {c.outstanding_questions.map((q, i) => (
              <li key={i} className="flex gap-2 bg-amber-50/60 border border-amber-200/60 rounded-lg p-2">
                <HelpCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" /> {q}
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Accountable stakeholders" icon={<Building2 className="w-5 h-5 text-slate-600" />} right={<LabelChip label="SIMULATED EVENT" />} />
          <div className="p-5 space-y-3">
            {c.stakeholders.length === 0 && <p className="text-sm text-slate-400 italic">Not resolved yet.</p>}
            {c.stakeholders.map((s, i) => (
              <div key={i} className="rounded-xl border border-slate-200 p-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{s.role}</div>
                <div className="font-bold">{s.name}</div>
                <div className="text-sm text-slate-600">{s.responsibility}</div>
                <div className="text-xs text-slate-400 mt-1">{s.contact}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader title="Deadlines" icon={<CalendarClock className="w-5 h-5 text-slate-600" />} />
          <div className="p-5 space-y-2">
            {c.deadlines.length === 0 && <p className="text-sm text-slate-400 italic">No deadlines.</p>}
            {c.deadlines.map((d) => (
              <div key={d.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 p-2 text-sm">
                <span>{d.title}</span>
                <span className="flex items-center gap-2 whitespace-nowrap">
                  <span className="text-slate-500">{fmtDate(d.due_date)}</span>
                  <Chip className={d.status === 'met' ? 'bg-teal-100 text-teal-800 border-teal-200' : d.status === 'overdue' ? 'bg-red-100 text-red-800 border-red-200' : 'bg-amber-100 text-amber-900 border-amber-200'}>{d.status}</Chip>
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {c.verification && (
        <Card>
          <CardHeader
            title="Verification"
            subtitle={c.verification.rule}
            right={<span className={`px-3 py-1 rounded-lg text-xs font-bold ${VERDICT_META[c.verification.verdict]?.cls}`}>{VERDICT_META[c.verification.verdict]?.label}</span>}
          />
          <div className="p-4">
            <IntervalChart result={c.verification} posts={c.measurements} />
            <p className="text-sm text-slate-600 mt-1">
              Pre-intervention: {kgh(c.verification.pre_rate)} ± {Math.round(c.verification.pre_uncertainty)}
              {c.recurrence_threshold_kg_h != null && <> · recurrence threshold {kgh(c.recurrence_threshold_kg_h)} (any later observation above it reopens the case)</>}
            </p>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Drafting (LLM at the edges)" subtitle="Claude drafts text if an API key is set; otherwise templates. Drafts never change case state." />
        <div className="p-5 space-y-3">
          <div className="flex flex-wrap gap-2">
            <button data-testid="draft-notice" className={btn.primary} disabled={!!drafting} onClick={() => doDraft('notice')}>
              <FileSignature className="w-4 h-4" /> {drafting === 'notice' ? 'Drafting…' : 'Draft notice to stakeholder'}
            </button>
            <button className={btn.ghost} disabled={!!drafting} onClick={() => doDraft('case_summary')}>
              <ScrollText className="w-4 h-4" /> {drafting === 'case_summary' ? 'Drafting…' : 'Case summary'}
            </button>
          </div>
          {draft && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-2 mb-2 text-xs">
                <Chip className={draft.result.mode === 'llm' ? 'bg-teal-100 text-teal-800 border-teal-200' : 'bg-slate-200 text-slate-700 border-slate-300'}>
                  {draft.result.mode === 'llm' ? `LLM draft (${draft.result.model ?? 'Claude'})` : 'Template draft'}
                </Chip>
                {draft.kind === 'notice' && <span className="text-slate-700 font-semibold">→ queued for human approval before it is "sent" (simulated)</span>}
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm text-slate-800">{draft.result.text}</pre>
            </div>
          )}
          {c.summary && !draft && <p className="text-sm text-slate-700">{c.summary}</p>}
        </div>
      </Card>
    </div>
  );
}
