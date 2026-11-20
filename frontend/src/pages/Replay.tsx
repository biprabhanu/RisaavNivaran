// HERO FEATURE: step-by-step historical replay of the Kanjur landfill case (2025–2026).
// Each step is one backend call (POST /api/replay/step) that returns a complete ReplayFrame.
// Offline, the same frames are read from the bundled snapshot.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Calendar, ChevronRight, Loader2, Pause, Play, RotateCcw, SkipForward, Sparkles, Wrench,
} from 'lucide-react';
import type { ApprovalDecision, MapState, ReplayFrame, ReplayStepInfo, ToolCall } from '../types/api';
import { api, errMsg, loadSnapshot, OfflineError } from '../lib/api';
import { bumpData, getState, setState, useAppState } from '../lib/store';
import { fmtDate, LABEL_DOT } from '../lib/format';
import { ApprovalCard } from '../components/ApprovalCard';
import { Banner } from '../components/Banner';
import { BeliefChart } from '../components/BeliefChart';
import { IntervalChart } from '../components/IntervalChart';
import { PlanTable } from '../components/PlanTable';
import { SiteMap } from '../components/SiteMap';
import { Timeline } from '../components/Timeline';
import { Caption, Card, CardHeader, ErrorBox, LabelChip, btn } from '../components/ui';

const BASE_MS = 4000;

// Keep the replay position when the user navigates to another page and comes back.
let cachedFrame: ReplayFrame | null = null;
let cachedTools: ToolCall[] = [];

export default function Replay() {
  const { offline, meta } = useAppState();
  const [params] = useSearchParams();
  const [frame, setFrame] = useState<ReplayFrame | null>(cachedFrame);
  const [script, setScript] = useState<ReplayStepInfo[]>([]);
  const [mapState, setMapState] = useState<MapState | null>(null);
  const [tools, setTools] = useState<ToolCall[]>(cachedTools);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autostarted = useRef(false);
  const busyRef = useRef(false);

  useEffect(() => {
    api.replayScript().then(setScript).catch(() => undefined);
    api.map().then(setMapState).catch(() => undefined);
  }, [offline]);

  const show = useCallback((f: ReplayFrame, resetTools = false) => {
    cachedFrame = f;
    setFrame(f);
    setTools((prev) => {
      const base = resetTools ? [] : prev;
      const seen = new Set(base.map((t) => t.id));
      const next = [...base, ...f.tool_calls.filter((t) => !seen.has(t.id))];
      cachedTools = next;
      return next;
    });
    if (f.done) setPlaying(false);
  }, []);

  // ---- offline helpers (snapshot frames) ----
  const offlineGo = useCallback(
    async (index: number, resetTools = false) => {
      const snap = await loadSnapshot();
      if (!snap.frames.length) throw new OfflineError('The offline snapshot has no replay frames.');
      const i = Math.max(0, Math.min(index, snap.frames.length - 1));
      setState({ offlineFrameIndex: i });
      show(snap.frames[i], resetTools);
      bumpData();
    },
    [show],
  );

  const run = useCallback(async (online: () => Promise<ReplayFrame>, offlineIndex: () => number, resetTools = false) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      if (getState().offline) {
        await offlineGo(offlineIndex(), resetTools);
      } else {
        try {
          const f = await online();
          show(f, resetTools);
          bumpData();
        } catch (e) {
          if (e instanceof OfflineError || getState().offline) await offlineGo(offlineIndex(), resetTools);
          else throw e;
        }
      }
    } catch (e) {
      setError(errMsg(e));
      setPlaying(false);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, [offlineGo, show]);

  const reset = useCallback(
    () => run(() => api.replayReset(), () => 0, true),
    [run],
  );
  const step = useCallback(
    (autoApprove: boolean) => {
      if (cachedFrame?.done) return Promise.resolve();
      return run(() => api.replayStep({ auto_approve: autoApprove }), () => (cachedFrame?.step_index ?? -1) + 1);
    },
    [run],
  );

  const decide = async (d: ApprovalDecision) => {
    const pa = frame?.pending_approval;
    if (!pa) return;
    if (getState().offline) {
      await step(true);
      return;
    }
    busyRef.current = true;
    setBusy(true);
    let ok = true;
    try {
      await api.decide(pa.id, { ...d, decided_by: 'Demo presenter' });
    } catch (e) {
      ok = false;
      setError(errMsg(e));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
    if (!ok) return;
    const prev = cachedFrame?.step_index;
    await run(
      async () => {
        let f = await api.replayStep({ auto_approve: false });
        if (f.step_index === prev) {
          // The decision may have created a follow-up approval (e.g. attribution → notification).
          // Show whatever is genuinely pending now instead of the stale item.
          const pend = (await api.approvals('PENDING')).filter((a) => a.status === 'PENDING' && (!f.case || a.case_id === f.case.case.id));
          f = { ...f, pending_approval: pend[0] ?? null };
        }
        return f;
      },
      () => (cachedFrame?.step_index ?? -1) + 1,
    );
  };

  // ?autostart=1 (from the landing page's "Start live demo") → reset then play.
  useEffect(() => {
    if (params.get('autostart') === '1' && !autostarted.current) {
      autostarted.current = true;
      reset().then(() => setPlaying(true));
    }
  }, [params, reset]);

  // Play loop: one step per interval; dramatic frames and approvals linger a little longer.
  useEffect(() => {
    if (!playing || busy) return;
    if (!frame) {
      reset();
      return;
    }
    if (frame.done) {
      setPlaying(false);
      return;
    }
    const dramatic = frame.banner?.kind === 'rejected' || frame.banner?.kind === 'reopened' || frame.pending_approval;
    const ms = (BASE_MS / speed) * (dramatic ? 1.6 : 1);
    const t = setTimeout(() => step(true), ms);
    return () => clearTimeout(t);
  }, [playing, busy, frame, speed, step, reset]);

  const c = frame?.case ?? null;
  const facility = c?.facility ?? mapState?.facility ?? null;
  const observations = c?.observations ?? [];
  const belief = frame?.belief_after ?? c?.case.belief ?? null;
  const plan = frame?.plan ?? c?.plan ?? null;
  const thisStepTools = new Set(frame?.tool_calls.map((t) => t.id) ?? []);
  const newIds = new Set(frame?.new_events.map((e) => e.id) ?? []);
  const total = frame?.total_steps ?? script.length;
  const actions = meta?.actions;

  return (
    <div className="space-y-5">
      <Caption>
        a step-by-step replay of the Kanjur landfill case. <strong>Blue = real Carbon Mapper data</strong>, <strong>amber = simulated operational events</strong>. Watch the agent
        update its beliefs, re-plan, refuse an unsupported closure, and reopen the case when emissions return.
      </Caption>

      {/* Controls */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="mr-auto">
            <h1 className="text-2xl font-extrabold tracking-tight">Replay: Kanjur landfill, Mumbai, 2025–2026</h1>
            <p className="text-sm text-slate-500">Case KJ-2025-02 · historical satellite observations + labelled simulated events</p>
          </div>
          <button data-testid="replay-reset" className={btn.ghost} onClick={() => { setPlaying(false); reset(); }} disabled={busy}>
            <RotateCcw className="w-4 h-4" /> Reset
          </button>
          <button
            data-testid="replay-play"
            className={playing ? btn.dark : btn.primary}
            onClick={() => setPlaying((p) => !p)}
            disabled={!!frame?.done}
          >
            {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />} {playing ? 'Pause' : 'Play'}
          </button>
          <button
            data-testid="replay-next"
            data-busy={busy ? 'true' : 'false'}
            className={btn.dark}
            onClick={() => (frame ? step(true) : reset())}
            disabled={busy || !!frame?.done}
            title={frame?.pending_approval ? 'Next = the presenter approves the pending item' : 'Next step'}
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <SkipForward className="w-4 h-4" />} Next
          </button>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Speed
            <select data-testid="replay-speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="border border-slate-300 rounded-lg px-2 py-1.5 text-sm font-semibold bg-white">
              <option value={0.5}>0.5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
            </select>
          </label>
        </div>

        {/* Progress rail */}
        {script.length > 0 && (
          <div className="mt-4 flex items-stretch gap-1 overflow-x-auto pb-1" data-testid="replay-rail">
            {script.filter((s) => s.index > 0).map((s) => {
              const cur = frame?.step_index ?? -1;
              const done = s.index < cur;
              const active = s.index === cur;
              return (
                <div
                  key={`${s.index}-${s.id}`}
                  className={`min-w-[120px] flex-1 rounded-lg border px-2 py-1.5 text-xs transition ${
                    active ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-400' : done ? 'border-slate-200 bg-slate-100 text-slate-500' : 'border-slate-200 bg-white text-slate-400'
                  }`}
                >
                  <div className="flex items-center gap-1 font-bold">
                    <span className={`w-2 h-2 rounded-full ${LABEL_DOT[s.label] ?? 'bg-slate-400'}`} />
                    {s.index}
                  </div>
                  <div className={`leading-tight mt-0.5 ${active ? 'text-slate-900 font-semibold' : ''}`}>{s.title}</div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {error && <ErrorBox error={error} />}

      {/* Dramatic banner */}
      {frame?.banner && <Banner key={`${frame.step_index}-${frame.banner.kind}`} banner={frame.banner} />}

      {/* Narration */}
      <Card className="p-5" data-testid="narration">
        {frame ? (
          <div key={frame.step_index} className="animate-slidein">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-bold text-slate-500" data-testid="step-counter">
                Step {frame.step_index} / {total}
              </span>
              <LabelChip label={frame.label} />
              {frame.sim_date && (
                <span className="inline-flex items-center gap-1 text-slate-600 font-semibold">
                  <Calendar className="w-4 h-4" /> {fmtDate(frame.sim_date)}
                </span>
              )}
              {frame.done && <span className="ml-auto text-emerald-700 font-bold" data-testid="replay-done">Replay complete ✓</span>}
            </div>
            <h2 className="text-2xl font-extrabold mt-2 text-slate-900" data-testid="step-title">{frame.title}</h2>
            <p className="text-lg text-slate-700 mt-2 leading-relaxed">{frame.narration}</p>
          </div>
        ) : (
          <div className="text-center py-6">
            <p className="text-lg text-slate-600">Press <strong>Play</strong> (or <strong>Next</strong>) to start. This resets case KJ-2025-02 and replays it from the first satellite observation.</p>
          </div>
        )}
      </Card>

      {/* Human approval */}
      {frame?.pending_approval && (
        <ApprovalCard key={frame.pending_approval.id} item={frame.pending_approval} onDecide={decide} highlight busy={busy} />
      )}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
        {/* Left: map + tools */}
        <div className="xl:col-span-2 space-y-5">
          <Card className="overflow-hidden">
            <CardHeader title="Monitoring map" subtitle="Plume size ∝ √(emission rate) · zones are illustrative" right={<LabelChip label="REAL DATA" />} />
            {facility ? (
              <SiteMap facility={facility} observations={observations} highlightIds={frame?.highlight_observation_ids} wind={mapState?.wind} height={340} />
            ) : (
              <div className="h-[340px] flex items-center justify-center text-slate-400 text-sm">Map loads with the first observation</div>
            )}
          </Card>
          <Card>
            <CardHeader title="Agent tool calls" subtitle="The agent acts by calling deterministic tools" icon={<Wrench className="w-5 h-5 text-slate-600" />} />
            <div className="p-4 space-y-2 max-h-[320px] overflow-auto" data-testid="tool-ticker">
              {tools.length === 0 && <p className="text-sm text-slate-400 italic">No tool calls yet.</p>}
              {[...tools].reverse().map((t) => (
                <div key={t.id} className={`rounded-lg border px-3 py-2 text-sm ${thisStepTools.has(t.id) ? 'border-emerald-300 bg-emerald-50 animate-slidein' : 'border-slate-200 bg-slate-50'}`}>
                  <div className="font-mono text-[13px]">
                    <span className="text-slate-500">agent called </span>
                    <span className="font-bold text-emerald-700">{t.tool}</span>
                    <ChevronRight className="inline w-3 h-3 text-slate-400 mx-1" />
                  </div>
                  <div className="text-slate-700 text-[13px]">{t.output_summary}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right: beliefs + planner */}
        <div className="xl:col-span-3 space-y-5">
          <Card>
            <CardHeader
              title="Source hypotheses: P(source | evidence)"
              subtitle={frame?.belief_before ? 'Grey = before this step’s Bayesian update, colour = after' : 'Competing hypotheses; none is assumed true'}
              right={<LabelChip label="AGENT ACTION" />}
            />
            <div className="p-4">
              {belief ? <BeliefChart key={frame?.step_index} belief={belief} before={frame?.belief_before} /> : <p className="text-sm text-slate-400 italic py-8 text-center">Hypotheses appear once the case is opened.</p>}
            </div>
          </Card>
          <Card>
            <CardHeader
              title="Evidence Planner"
              subtitle="score = EIG / (cost + λ·time); constraint-violating actions excluded before ranking"
              right={frame?.plan_before ? <span className="text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 rounded-md px-2 py-1" data-testid="replanned-badge">RE-RANKED</span> : undefined}
              icon={<Sparkles className="w-5 h-5 text-emerald-600" />}
            />
            <div className="p-4">
              {plan ? (
                <>
                  <PlanTable plan={plan} before={frame?.plan_before} actions={actions} compact />
                  <div className="mt-3 rounded-xl bg-blue-50/60 border border-blue-100 p-3 text-sm text-blue-950 whitespace-pre-line" data-testid="plan-explanation">
                    {plan.explanation}
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-400 italic py-8 text-center">The planner runs once hypotheses exist.</p>
              )}
            </div>
          </Card>
        </div>
      </div>

      {frame?.verification && (
        <Card>
          <CardHeader title="Verification: uncertainty intervals" subtitle={frame.verification.rule} right={<span className="text-sm font-bold">{frame.verification.verdict.replace(/_/g, ' ')}</span>} />
          <div className="p-4">
            <IntervalChart result={frame.verification} posts={c?.case.measurements ?? []} />
            <ul className="mt-2 text-sm text-slate-700 list-disc pl-5">
              {frame.verification.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Audit timeline (newest first)" subtitle="Every event: timestamp, actor, type, evidence links, provenance label" />
        <div className="p-5 max-h-[560px] overflow-auto">
          <Timeline events={frame?.timeline ?? []} newIds={newIds} compact newestFirst />
        </div>
      </Card>
    </div>
  );
}
