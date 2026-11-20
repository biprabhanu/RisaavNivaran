// App shell: Mandar's dark header + tab navigation, LLM badge, Reset demo, offline banner, footer.
import { useState, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity, BarChart3, CheckCircle2, Clock, Database, FileText, FlaskConical, Globe, Home, Inbox, Loader2,
  PlayCircle, RotateCcw, Search, ShieldAlert, WifiOff,
} from 'lucide-react';
import { api, errMsg, retryOnline } from '../lib/api';
import { useApi } from '../lib/hooks';
import { bumpData, setState, showToast, useAppState } from '../lib/store';

const NAV = [
  { to: '/', label: 'Overview', icon: Home, end: true },
  { to: '/replay', label: 'Replay', icon: PlayCircle },
  { to: '/map', label: 'Map', icon: Globe },
  { to: '/cases/KJ-2025-02', label: 'Case', icon: FileText },
  { to: '/planner', label: 'Planner', icon: Search },
  { to: '/approvals', label: 'Approvals', icon: Inbox, badge: true },
  { to: '/verification', label: 'Verification', icon: CheckCircle2 },
  { to: '/audit', label: 'Audit', icon: Clock },
  { to: '/evaluation', label: 'Evaluation', icon: BarChart3 },
  { to: '/whatif', label: 'What-if', icon: FlaskConical },
  { to: '/data', label: 'Data', icon: Database },
];

export function Layout({ children }: { children: ReactNode }) {
  const { health, offline, toast } = useAppState();
  const [resetting, setResetting] = useState(false);
  const pending = useApi(() => api.approvals('PENDING'), []);
  const pendingCount = pending.data?.filter((a) => a.status === 'PENDING').length ?? 0;

  const badgeText = offline ? 'LLM: off (offline snapshot)' : health?.llm_mode === 'llm' ? 'LLM: on (Claude)' : 'LLM: off (template mode)';
  const badgeCls = !offline && health?.llm_mode === 'llm'
    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
    : 'bg-slate-700/60 text-slate-200 border-slate-600';

  const reset = async () => {
    setResetting(true);
    try {
      await api.resetDemo();
      setState({ offlineFrameIndex: null });
      bumpData();
      showToast('Demo reset: database re-seeded with the clean Kanjur case.');
    } catch (e) {
      showToast(`Reset failed: ${errMsg(e)}`);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col text-[15px]">
      {toast && (
        <div className="fixed top-5 right-5 z-[1000] bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 border border-slate-700 animate-slidein max-w-md" data-testid="toast">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <span className="text-sm font-medium">{toast}</span>
        </div>
      )}

      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-[500] shadow-md">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 h-[72px] flex items-center justify-between gap-4">
          <NavLink to="/" className="flex items-center gap-3 min-w-0">
            <div className="bg-emerald-500 p-2.5 rounded-xl shadow-lg shadow-emerald-500/20">
              <ShieldAlert className="w-7 h-7 text-slate-950" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight">PlumeProof</span>
                <span className="hidden sm:inline bg-emerald-500/20 text-emerald-400 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-emerald-500/30">MVP</span>
              </div>
              <p className="hidden md:block text-xs text-slate-400 truncate">From satellite methane alerts to verified mitigation · Team RisaavNivaran, IIT Bombay</p>
            </div>
          </NavLink>
          <div className="flex items-center gap-2 text-xs">
            <span data-testid="llm-badge" className={`px-3 py-1.5 rounded-lg border font-semibold whitespace-nowrap ${badgeCls}`} title={health?.llm_model ?? 'Deterministic template drafting'}>
              {badgeText}
            </span>
            <button
              data-testid="reset-demo"
              onClick={reset}
              disabled={resetting || offline}
              className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 px-3 py-1.5 rounded-lg font-semibold disabled:opacity-50"
              title="Wipe the database and re-seed the clean demo state"
            >
              {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />} Reset demo
            </button>
          </div>
        </div>
        <nav className="bg-slate-950/60 border-t border-slate-800/60 px-4 sm:px-6 lg:px-8">
          <div className="max-w-[1400px] mx-auto flex space-x-1 overflow-x-auto">
            {NAV.map((n) => {
              const Icon = n.icon;
              return (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    `flex items-center gap-2 py-3 px-3 border-b-2 text-sm font-medium transition-colors whitespace-nowrap ${
                      isActive ? 'border-emerald-400 text-emerald-400' : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  {n.label}
                  {n.badge && pendingCount > 0 && (
                    <span data-testid="pending-count" className="bg-violet-500 text-white text-[11px] font-bold rounded-full px-1.5 min-w-[20px] text-center">
                      {pendingCount}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </div>
        </nav>
      </header>

      {offline && (
        <div className="bg-amber-400 text-slate-950 border-b border-amber-600" data-testid="offline-banner">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center gap-3 text-sm font-semibold">
            <WifiOff className="w-5 h-5" />
            <span>Offline snapshot mode: backend unreachable. Showing a bundled, pre-computed snapshot (read-only).</span>
            <button
              className="ml-auto underline"
              onClick={async () => showToast((await retryOnline()) ? 'Backend reconnected.' : 'Still offline.')}
            >
              Retry connection
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">{children}</main>

      <footer className="bg-slate-900 text-slate-400 border-t border-slate-800 py-6 text-center text-sm">
        <p className="flex items-center justify-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" /> PlumeProof · Agentic AI Hackathon 2026 | Team RisaavNivaran, IIT Bombay
        </p>
        <p className="mt-1 text-slate-500 text-xs">
          Every methane plume deserves a timely investigation. Every claimed mitigation outcome must be supported by verifiable evidence.
        </p>
        <p className="mt-1 text-slate-500 text-xs">
          Carbon Mapper plume observations (Kanjur, 9 Feb 2025 &amp; 3 Apr 2026) are real · all operational events, stakeholder responses and measurements are simulated and labelled.
        </p>
      </footer>
    </div>
  );
}
