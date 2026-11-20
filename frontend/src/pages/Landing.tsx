import { Link } from 'react-router-dom';
import {
  ArrowRight, BrainCircuit, Building2, FileCheck2, Globe2, Landmark, PlayCircle, Satellite, ShieldCheck, Users,
} from 'lucide-react';
import { Caption, Card, LabelChip } from '../components/ui';
import { useAppState } from '../lib/store';

const FLOW = [
  {
    icon: Satellite,
    title: 'Problem',
    tone: 'border-red-200 bg-red-50/50',
    iconCls: 'text-red-600',
    body: 'Satellites detect huge methane plumes, but most alerts never lead to an investigation, a repair, or proof that emissions fell.',
  },
  {
    icon: Globe2,
    title: 'Input',
    tone: 'border-blue-200 bg-blue-50/50',
    iconCls: 'text-blue-600',
    body: 'Satellite plume observations (Carbon Mapper), facility zones, stakeholder registry, operator records and field measurements.',
  },
  {
    icon: BrainCircuit,
    title: 'Agent',
    tone: 'border-emerald-200 bg-emerald-50/50',
    iconCls: 'text-emerald-600',
    body: 'Keeps competing source hypotheses, updates them with Bayes, picks the investigation with the best information per ₹ and day, and asks a human before acting.',
  },
  {
    icon: FileCheck2,
    title: 'Output',
    tone: 'border-violet-200 bg-violet-50/50',
    iconCls: 'text-violet-600',
    body: 'Ranked investigation plan, drafted notices, an evidence-linked audit trail, and a verdict: Verified Reduction, Inconclusive, or Still Leaking.',
  },
  {
    icon: Users,
    title: 'End users',
    tone: 'border-slate-300 bg-white',
    iconCls: 'text-slate-700',
    body: 'Landfill operators & municipal corporations · pollution control boards · UN IMEO / MARS national focal points.',
  },
];

export default function Landing() {
  const { meta } = useAppState();
  const s = meta?.stats ?? {};
  const rate = s.response_rate_pct ?? 13;
  const alerts = s.mars_alerts ?? '5,000+';
  const target = s.target_response_rate_pct ?? 80;

  return (
    <div className="space-y-6">
      <Caption>a one-screen overview of PlumeProof: what problem it solves, what goes in, what the agent does, what comes out, and who uses it.</Caption>

      <div className="grid lg:grid-cols-5 gap-6 items-stretch">
        <Card className="lg:col-span-3 p-8 bg-gradient-to-br from-slate-900 to-slate-800 text-white border-slate-800">
          <p className="text-emerald-400 font-semibold uppercase tracking-widest text-sm">The response gap</p>
          <p className="mt-3 text-5xl md:text-6xl font-black tracking-tight">
            Only <span className="text-emerald-400">{rate}%</span>
          </p>
          <p className="mt-2 text-xl md:text-2xl font-semibold text-slate-200">of {alerts} UN methane alerts get a response.</p>
          <p className="mt-4 text-slate-400 text-base max-w-2xl">
            Methane drives ~{s.methane_share_of_warming_pct ?? 30}% of current warming and is ~{s.gwp20 ?? 80}× more potent than CO₂ over 20 years. The UN targets an {target}% response
            rate by 2030. Detection is solved; <strong className="text-white">follow-through</strong> isn't.
          </p>
          <Link
            to="/replay?autostart=1"
            data-testid="start-demo"
            className="mt-8 inline-flex items-center gap-3 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xl font-extrabold px-8 py-4 rounded-2xl shadow-lg shadow-emerald-500/30 transition animate-glow"
          >
            <PlayCircle className="w-8 h-8" /> Start live demo
          </Link>
          <p className="mt-3 text-sm text-slate-400">Replays the real Kanjur landfill (Mumbai) observations, 2025–2026 · about 3 minutes</p>
        </Card>

        <Card className="lg:col-span-2 p-6 flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-600" /> What's real vs. simulated
            </h2>
            <ul className="mt-4 space-y-3 text-[15px]">
              <li className="flex gap-2">
                <LabelChip label="REAL DATA" className="shrink-0 self-start mt-0.5" />
                <span>Carbon Mapper plumes at Kanjur: 9 Feb 2025 (~1,600 &amp; ~136 kg/h) and 3 Apr 2026 (~3,300 kg/h combined).</span>
              </li>
              <li className="flex gap-2">
                <LabelChip label="SIMULATED EVENT" className="shrink-0 self-start mt-0.5" />
                <span>Stakeholder replies, inspector availability, operator records, repair claims, follow-up measurements.</span>
              </li>
              <li className="flex gap-2">
                <LabelChip label="AGENT ACTION" className="shrink-0 self-start mt-0.5" />
                <span>Every belief update, ranking and verdict is computed live by deterministic, tested code.</span>
              </li>
              <li className="flex gap-2">
                <LabelChip label="HUMAN DECISION" className="shrink-0 self-start mt-0.5" />
                <span>Attribution, notifications, field investigations and closure always wait for a human click.</span>
              </li>
            </ul>
          </div>
          <p className="mt-4 text-xs text-slate-500">Likelihoods, costs and times are illustrative demonstration values (see docs/ASSUMPTIONS.md).</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-stretch">
        {FLOW.map((f, i) => {
          const Icon = f.icon;
          return (
            <div key={f.title} className="relative flex">
              <div className={`flex-1 rounded-2xl border p-5 shadow-sm ${f.tone}`}>
                <div className="flex items-center gap-2">
                  <Icon className={`w-7 h-7 ${f.iconCls}`} />
                  <h3 className="text-lg font-extrabold">{f.title}</h3>
                </div>
                <p className="mt-2 text-[15px] text-slate-700 leading-relaxed">{f.body}</p>
              </div>
              {i < FLOW.length - 1 && (
                <ArrowRight className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 text-slate-400 z-10 bg-slate-50 rounded-full" />
              )}
            </div>
          );
        })}
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {[
          { icon: Building2, t: 'Landfill operators & municipal corporations', d: 'Get a precise, ranked request (e.g. "send flare + gas-collection records") instead of a vague alert.' },
          { icon: Landmark, t: 'Pollution control boards', d: 'Receive evidence-linked findings and a closure verdict that cannot be faked by a repair claim alone.' },
          { icon: Globe2, t: 'UN IMEO / MARS focal points', d: 'Supervise thousands of alerts through an approval queue, deadlines, and an auditable trail per case.' },
        ].map((u) => (
          <Card key={u.t} className="p-5">
            <u.icon className="w-6 h-6 text-emerald-600" />
            <h3 className="font-bold mt-2">{u.t}</h3>
            <p className="text-sm text-slate-600 mt-1">{u.d}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
