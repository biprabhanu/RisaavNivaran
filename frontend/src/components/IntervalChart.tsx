// Uncertainty-interval visualisation for verification: each measurement is a bar from
// (rate − u) to (rate + u). The red dashed line marks pre − u_pre: a verified reduction needs
// the post interval to end entirely to the LEFT of that line.
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Measurement, VerificationResult } from '../types/api';

interface Row { name: string; range: [number, number]; text: string; kind: 'pre' | 'post' | 'ignored' | 'combined' }

export function IntervalChart({ result, posts = [], height }: { result: VerificationResult; posts?: Measurement[]; height?: number }) {
  const rows: Row[] = [
    { name: 'Pre-intervention', range: [result.pre_low, result.pre_high], text: `${Math.round(result.pre_rate)} ± ${Math.round(result.pre_uncertainty)}`, kind: 'pre' },
  ];
  posts.forEach((m, i) => {
    rows.push({
      name: `${m.independent ? 'Post' : 'Claim'} ${posts.length > 1 ? i + 1 : ''}`.trim() + (m.independent ? '' : ' (ignored)'),
      range: [m.rate_kg_h - m.uncertainty_kg_h, m.rate_kg_h + m.uncertainty_kg_h],
      text: `${Math.round(m.rate_kg_h)} ± ${Math.round(m.uncertainty_kg_h)}${m.independent ? '' : ' · not independent'}`,
      kind: m.independent ? 'post' : 'ignored',
    });
  });
  if (result.post_low != null && result.post_high != null && result.post_rate != null && (posts.filter((p) => p.independent).length !== 1 || posts.length === 0)) {
    rows.push({
      name: posts.length ? 'Combined post' : 'Post-intervention',
      range: [result.post_low, result.post_high],
      text: `${Math.round(result.post_rate)} ± ${Math.round(result.post_uncertainty ?? 0)}`,
      kind: 'combined',
    });
  }
  const colour = (k: Row['kind']) => {
    if (k === 'pre') return '#64748b';
    if (k === 'ignored') return '#fbbf24';
    if (result.verdict === 'VERIFIED_REDUCTION') return '#10b981';
    if (result.verdict === 'STILL_LEAKING') return '#ef4444';
    return '#94a3b8';
  };
  const max = Math.max(...rows.map((r) => r.range[1])) * 1.15;
  return (
    <div data-testid="interval-chart">
      <ResponsiveContainer width="100%" height={height ?? 70 + rows.length * 52}>
        <BarChart data={rows} layout="vertical" margin={{ top: 22, right: 110, left: 10, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, Math.ceil(max / 100) * 100]} tick={{ fontSize: 13 }} unit=" kg/h" />
          <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 13, fill: '#0f172a' }} />
          <Tooltip formatter={(v: [number, number] | number) => (Array.isArray(v) ? `${Math.round(v[0])}–${Math.round(v[1])} kg/h` : v)} />
          <ReferenceLine x={result.pre_low} stroke="#dc2626" strokeDasharray="6 4" strokeWidth={2} label={{ value: `pre − u = ${Math.round(result.pre_low)}`, position: 'top', fill: '#dc2626', fontSize: 12, fontWeight: 700 }} />
          <Bar dataKey="range" barSize={22} radius={6} animationDuration={900}>
            {rows.map((r, i) => (
              <Cell key={i} fill={colour(r.kind)} />
            ))}
            <LabelList dataKey="text" position="right" style={{ fontSize: 12, fill: '#334155', fontWeight: 600 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
