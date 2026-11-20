import { useMemo, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import type { ChainStage, DataLabel } from '../types/api';
import { api } from '../lib/api';
import { useApi } from '../lib/hooks';
import { LABEL_CLS } from '../lib/format';
import { Timeline } from '../components/Timeline';
import { Card, ErrorBox, PageTitle, Spinner } from '../components/ui';

const LABELS: DataLabel[] = ['REAL DATA', 'AGENT ACTION', 'SIMULATED EVENT', 'HUMAN DECISION'];
const CHAIN: ChainStage[] = ['Observation', 'Hypothesis', 'Investigation', 'Finding', 'Repair', 'Verification'];

export default function Audit() {
  const { data, error, loading, reload } = useApi(() => api.audit());
  const [labels, setLabels] = useState<Set<DataLabel>>(new Set(LABELS));
  const [stage, setStage] = useState<ChainStage | null>(null);
  const [toolsOnly, setToolsOnly] = useState(false);

  const events = data ?? [];
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    events.forEach((e) => {
      if (e.chain_stage) c[e.chain_stage] = (c[e.chain_stage] ?? 0) + 1;
      c[e.label] = (c[e.label] ?? 0) + 1;
    });
    return c;
  }, [events]);
  const filtered = events.filter((e) => labels.has(e.label) && (!stage || e.chain_stage === stage) && (!toolsOnly || e.tool));

  const toggle = (l: DataLabel) =>
    setLabels((prev) => {
      const n = new Set(prev);
      if (n.has(l)) n.delete(l);
      else n.add(l);
      return n;
    });

  return (
    <div className="space-y-5">
      <PageTitle description="Every event with its time, actor, evidence links and provenance label." title="Audit timeline" meta={`${events.length} events · SQLite persistence`} />

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-1" data-testid="evidence-chain">
          {CHAIN.map((s, i) => (
            <div key={s} className="flex items-center gap-1">
              <button
                onClick={() => setStage(stage === s ? null : s)}
                className={`px-3 py-2 rounded-xl border text-sm font-semibold transition ${stage === s ? 'bg-teal-600 text-white border-teal-700' : 'bg-white border-slate-200 hover:bg-slate-50'}`}
              >
                {s} <span className={`ml-1 text-xs ${stage === s ? 'text-teal-100' : 'text-slate-400'}`}>{counts[s] ?? 0}</span>
              </button>
              {i < CHAIN.length - 1 && <ChevronRight className="w-4 h-4 text-slate-300" />}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Filter labels:</span>
          {LABELS.map((l) => (
            <button
              key={l}
              onClick={() => toggle(l)}
              className={`px-2 py-1 rounded-md border text-xs font-bold ${labels.has(l) ? LABEL_CLS[l] : 'bg-white text-slate-300 border-slate-200 line-through'}`}
            >
              {l} ({counts[l] ?? 0})
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={toolsOnly} onChange={(e) => setToolsOnly(e.target.checked)} className="w-4 h-4 accent-teal-600" /> Only tool calls
          </label>
        </div>
      </Card>

      {loading && !data && <Spinner />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      <Card className="p-6">
        <Timeline events={filtered} />
      </Card>
    </div>
  );
}
