import { Link } from 'react-router-dom';
import { ArrowRight, Globe } from 'lucide-react';
import { api } from '../lib/api';
import { useApi } from '../lib/hooks';
import { fmtDate, hypColor, hypIds, hypLabel, kgh, pct, STATUS_META } from '../lib/format';
import { SiteMap } from '../components/SiteMap';
import { Caption, Card, CardHeader, ErrorBox, LabelChip, PageTitle, Spinner, Stat, StatusPill, btn } from '../components/ui';
import type { CaseStatus } from '../types/api';

export default function MapPage() {
  const { data, error, loading, reload } = useApi(() => api.map());

  return (
    <div className="space-y-5">
      <Caption>
        the Kanjur landfill with its illustrative source zones (coloured by hypothesis). Red circles are real Carbon Mapper plumes, sized by emission rate; the
        dashed boundary is coloured by the case status; the arrow shows an illustrative wind direction.
      </Caption>
      <PageTitle title="Monitoring map" subtitle="Mumbai region · Kanjur landfill (≈19.13 N, 72.93 E)" />
      {loading && !data && <Spinner />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Stat label="Plume observations" value={data.observations.length} sub="Carbon Mapper (real)" tone="blue" />
            <Stat label="Peak emission rate" value={kgh(Math.max(0, ...data.observations.map((o) => o.rate_kg_h)))} sub="single observation" tone="red" />
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
              <CardHeader title="Geospatial view" icon={<Globe className="w-5 h-5 text-blue-600" />} right={<LabelChip label="REAL DATA" />} />
              <SiteMap facility={data.facility} observations={data.observations} cases={data.cases} wind={data.wind} height={520} />
            </Card>
            <div className="space-y-5">
              <Card className="p-5">
                <h3 className="font-bold mb-3">Legend</h3>
                <div className="space-y-2 text-sm">
                  {hypIds().map((h) => (
                    <div key={h} className="flex items-center gap-2">
                      <span className="w-4 h-4 rounded" style={{ background: hypColor(h), opacity: 0.6 }} /> {hypLabel(h)} zone
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-full bg-red-500/50 border-2 border-red-800" /> Satellite plume (size ∝ √rate)
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 rounded-full bg-slate-900 text-sky-400 text-[10px] flex items-center justify-center">↑</span> Wind: {data.wind.label}
                    {data.wind.illustrative && <span className="text-xs text-amber-700 font-semibold">(illustrative)</span>}
                  </div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 pt-2">Boundary colour = case status</p>
                  <div className="flex flex-wrap gap-1">
                    {(Object.keys(STATUS_META) as CaseStatus[]).map((s) => (
                      <span key={s} className="text-[11px] px-1.5 py-0.5 rounded border font-semibold" style={{ borderColor: STATUS_META[s].hex, color: STATUS_META[s].hex }}>
                        {STATUS_META[s].label}
                      </span>
                    ))}
                  </div>
                </div>
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
                        <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full ${c.priority === 'Critical' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'}`}>{c.priority}</span>
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
