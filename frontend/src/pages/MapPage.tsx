import { Link } from 'react-router-dom';
import { ArrowRight, Globe } from 'lucide-react';
import { api } from '../lib/api';
import { useApi } from '../lib/hooks';
import { fmtDate, hypLabel, kgh, pct } from '../lib/format';
import { SiteMap } from '../components/SiteMap';
import { Card, CardHeader, ErrorBox, LabelChip, PageTitle, Spinner, Stat, StatusPill, btn } from '../components/ui';
import type { Observation } from '../types/api';

/** e.g. "two plumes combined (3 Apr 2026)" for the combined 2026 observation. */
function peakSub(o: Observation): string {
  const combined = /combined|\+/i.test(o.plume_label) || /combined/i.test(o.notes);
  return `${combined ? 'two plumes combined' : 'single plume'} (${fmtDate(o.date)})`;
}

export default function MapPage() {
  const { data, error, loading, reload } = useApi(() => api.map());
  const peak = data?.observations.reduce<Observation | null>((best, o) => (!best || o.rate_kg_h > best.rate_kg_h ? o : best), null) ?? null;

  return (
    <div className="space-y-5">
      <PageTitle description="Real satellite plumes over the Kanjur landfill, with illustrative source zones." title="Monitoring map" meta="Mumbai region · Kanjur landfill (≈19.13 N, 72.93 E)" />
      {loading && !data && <Spinner />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat label="Plume observations" value={data.observations.length} sub="Carbon Mapper (real)" tone="teal" />
            <Stat label="Peak emission rate" value={kgh(peak?.rate_kg_h ?? 0)} sub={peak ? peakSub(peak) : '—'} tone="red" />
            <Stat label="Active cases" value={data.cases.length} sub={data.cases.map((c) => c.id).join(', ') || '—'} />
            <Stat
              label="Awaiting human approval"
              value={data.cases.reduce((s, c) => s + c.pending_approvals, 0)}
              sub="items in the approval queue"
              tone="amber"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card className="lg:col-span-2 overflow-hidden">
              <CardHeader title="Geospatial view" icon={<Globe className="w-5 h-5 text-slate-600" />} right={<LabelChip label="REAL DATA" />} />
              <SiteMap facility={data.facility} observations={data.observations} cases={data.cases} wind={data.wind} height={520} />
            </Card>
            <div className="space-y-5">
              <Card className="p-5">
                <h3 className="font-semibold text-slate-900 mb-3">About this map</h3>
                <ul className="space-y-2 text-sm text-slate-600">
                  <li><span className="font-medium text-slate-900">Plumes</span> are real Carbon Mapper observations; positions are approximate.</li>
                  <li><span className="font-medium text-slate-900">Zones</span> are illustrative areas for each source hypothesis.</li>
                  <li><span className="font-medium text-slate-900">Boundary</span> colour shows the case status (amber pending · green verified · red recurring).</li>
                  <li><span className="font-medium text-slate-900">Wind</span>: {data.wind.label}.</li>
                </ul>
              </Card>
              <Card className="p-5">
                <h3 className="font-bold mb-3">Observations</h3>
                <ul className="space-y-2 text-sm">
                  {data.observations.map((o) => (
                    <li key={o.id} className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                      <div>
                        <div className="font-semibold">{o.plume_label}</div>
                        <div className="text-xs text-slate-500">
                          {fmtDate(o.date)} · {o.source}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold num">{kgh(o.rate_kg_h)}</div>
                        <LabelChip label={o.label} />
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          </div>

          <Card className="overflow-hidden">
            <CardHeader title="Investigation cases" subtitle="Each detection becomes a managed case" />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                    <th className="py-3 px-5">Case</th>
                    <th className="py-3 px-5">Facility</th>
                    <th className="py-3 px-5">Latest observation</th>
                    <th className="py-3 px-5">Leading hypothesis</th>
                    <th className="py-3 px-5">Priority</th>
                    <th className="py-3 px-5">Status</th>
                    <th className="py-3 px-5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.cases.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/80">
                      <td className="py-3 px-5 font-mono font-bold">{c.id}</td>
                      <td className="py-3 px-5">{c.facility_name}</td>
                      <td className="py-3 px-5 num">
                        {kgh(c.latest_rate_kg_h)} · {fmtDate(c.latest_obs_date)}
                      </td>
                      <td className="py-3 px-5">
                        {hypLabel(c.leading_hypothesis)} ({pct(c.leading_probability)})
                      </td>
                      <td className="py-3 px-5">
                        <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full ${c.priority === 'Critical' ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'}`}>{c.priority}</span>
                      </td>
                      <td className="py-3 px-5">
                        <StatusPill status={c.status} />
                      </td>
                      <td className="py-3 px-5 text-right">
                        <Link to={`/cases/${c.id}`} className={btn.primary}>
                          Open case <ArrowRight className="w-4 h-4" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
