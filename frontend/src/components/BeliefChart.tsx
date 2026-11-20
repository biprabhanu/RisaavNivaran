// Horizontal bar chart of P(source). If `before` is given, grey "ghost" bars show the belief
// before the latest Bayesian update, so the audience sees the shift.
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Belief } from '../types/api';
import { entropy } from '../lib/bayes';
import { bits, hypColor, hypIds, hypLabel } from '../lib/format';

export function BeliefChart({ belief, before, height = 220, showEntropy = true }: { belief: Belief; before?: Belief | null; height?: number; showEntropy?: boolean }) {
  const ids = hypIds().filter((h) => h in belief);
  const data = ids.map((id) => ({
    id,
    name: hypLabel(id),
    now: Math.round((belief[id] ?? 0) * 1000) / 10,
    before: before ? Math.round((before[id] ?? 0) * 1000) / 10 : undefined,
  }));
  const hNow = entropy(belief);
  const hBefore = before ? entropy(before) : null;
  return (
    <div data-testid="belief-chart">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, left: 8, bottom: 4 }} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} tick={{ fontSize: 13 }} />
          <YAxis type="category" dataKey="name" width={170} tick={{ fontSize: 14, fill: '#0f172a' }} />
          <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
          {before && <Legend wrapperStyle={{ fontSize: 13 }} />}
          {before && (
            <Bar dataKey="before" name="Before update" fill="#cbd5e1" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList dataKey="before" position="right" formatter={(v: number) => `${v.toFixed(0)}%`} style={{ fontSize: 12, fill: '#94a3b8' }} />
            </Bar>
          )}
          <Bar dataKey="now" name={before ? 'After update' : 'P(source)'} radius={[0, 6, 6, 0]} animationDuration={1200}>
            {data.map((d) => (
              <Cell key={d.id} fill={hypColor(d.id)} />
            ))}
            <LabelList dataKey="now" position="right" formatter={(v: number) => `${v.toFixed(0)}%`} style={{ fontSize: 14, fontWeight: 700, fill: '#0f172a' }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {showEntropy && (
        <div className="flex items-center justify-between text-sm px-2 pt-1">
          <span className="text-slate-500">Uncertainty (Shannon entropy H = −Σ p·log₂p)</span>
          <span className="font-bold text-slate-900 num" data-testid="entropy">
            {hBefore != null && <span className="text-slate-400 font-medium">{bits(hBefore)} → </span>}
            {bits(hNow)}
          </span>
        </div>
      )}
    </div>
  );
}
