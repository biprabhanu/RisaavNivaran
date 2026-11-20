// HERO FEATURE: step-by-step historical replay of the Kanjur landfill case (2025–2026).
// Each step is one backend call (POST /api/replay/step) that returns a complete ReplayFrame.
// Offline, the same frames are read from the bundled snapshot.
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Calendar, ChevronRight, Loader2, Pause, Play, RotateCcw, SkipForward, Sparkles, Wrench,
} from 'lucide-react';
import type { ApprovalDecision, MapState, ReplayFrame, ReplayStepInfo, ToolCall } from '../types/api';
import { api, errMsg, loadSnapshot, OfflineError } from '../lib/api';
import { bumpData, getState, setState, showToast, useAppState } from '../lib/store';
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
let cachedResetVersion = -1; // demoResetVersion the cached frame belongs to

export default function Replay() {
  const { offline, meta, demoResetVersion } = useAppState();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [frame, setFrame] = useState<ReplayFrame | null>(cachedFrame);
  const [script, setScript] = useState<ReplayStepInfo[]>([]);
  const [mapState, setMapState] = useState<MapState | null>(null);
  const [tools, setTools] = useState<ToolCall[]>(cachedTools);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initDone = useRef(false);
  const seenResetVersion = useRef(demoResetVersion);
  const busyRef = useRef(false);
  const controlsRef = useRef<HTMLDivElement | null>(null);
  const railRef = useRef<HTMLDivElement | null>(null);

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

  const reset = useCallback(() => {
    cachedResetVersion = getState().demoResetVersion;
    return run(() => api.replayReset(), () => 0, true);
  }, [run]);
  /** Restore the live replay position (page reload, navigation back, after a header "Reset demo"). */
  const loadCurrent = useCallback(() => {
    cachedResetVersion = getState().demoResetVersion;
    return run(() => api.replayCurrent(), () => getState().offlineFrameIndex ?? 0, true);
  }, [run]);
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
      if (d.decision === 'reject') {
        showToast('Offline snapshot mode replays the recorded approvals. Reject needs the live backend.');
        return;
      }
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
    // Approve/Edit → the backend advances to the next beat. Reject → the backend returns a frame at the
    // SAME step index ("Human rejected…") with the agent's re-proposed item; we simply render it.
    await run(() => api.replayStep({ auto_approve: false }), () => (cachedFrame?.step_index ?? -1) + 1);
  };

  // First load. "Start live demo" (/replay?autostart=1) → reset to the intro and WAIT for the presenter.
  // The URL is then replaced with /replay so Back/refresh never resets the replay again.
  // A plain /replay load restores the live position from the backend.
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    if (params.get('autostart') === '1') {
      navigate('/replay', { replace: true });
      setPlaying(false);
      reset();
    } else if (!cachedFrame || cachedResetVersion !== getState().demoResetVersion) {
      loadCurrent();
    }
  }, [params, navigate, reset, loadCurrent]);

  // Header "Reset demo" while on this page → restart the replay at the intro so Next starts at step 1.
  useEffect(() => {
    if (demoResetVersion === seenResetVersion.current) return;
    seenResetVersion.current = demoResetVersion;
    setPlaying(false);
    reset();
  }, [demoResetVersion, reset]);

  // Every new frame: bring the controls, banner and approval card into view (the key moments must be
  // visible on a projector without scrolling), and slide the progress rail to the active step.
  const frameKey = frame ? `${frame.step_index}|${frame.title}` : '';
  useEffect(() => {
    if (!frameKey) return;
    const el = controlsRef.current;
    if (el) {
      const header = document.querySelector('header')?.getBoundingClientRect().height ?? 0;
      const top = el.getBoundingClientRect().top + window.scrollY - header - 12;
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    }
    const rail = railRef.current;
    const active = rail?.querySelector<HTMLElement>('[data-active="true"]');
    if (rail && active) {
      rail.scrollTo({ left: Math.max(0, active.offsetLeft - rail.clientWidth / 2 + active.clientWidth / 2), behavior: 'smooth' });
    }
  }, [frameKey]);

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
    <div className="space-y-4">
      <Caption>
        a step-by-step replay of the Kanjur landfill case. <strong>Blue = real Carbon Mapper data</strong>, <strong>amber = simulated operational events</strong>. Watch the agent
        update its beliefs, re-plan, refuse an unsupported closure, and reopen the case when emissions return.
      </Caption>

      {/* 1. Controls + current step (always the first thing on screen after each step) */}
      <div ref={controlsRef} className="scroll-mt-40">
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="mr-auto min-w-0">
              <p className="text-sm font-semibold text-slate-500">
                Replay · Kanjur landfill, Mumbai, 2025–2026 · Case KJ-2025-02
              </p>
              {frame ? (
                <div className="flex flex-wrap items-center gap-2 text-sm mt-0.5">
                  <span className="font-bold text-slate-600" data-testid="step-counter">
                    Step {frame.step_index} / {total}
                  </span>
                  <LabelChip label={frame.label} />
                  {frame.sim_date && (
                    <span className="inline-flex items-center gap-1 text-slate-600 font-semibold">
                      <Calendar className="w-4 h-4" /> {fmtDate(frame.sim_date)}
                    </span>
                  )}
                  {frame.done && <span className="text-emerald-700 font-bold" data-testid="replay-done">Replay complete ✓</span>}
                </div>
              ) : (
                <span className="text-sm text-slate-400" data-testid="step-counter">Loading replay…</span>
              )}
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
          {frame && (
            <h1 key={frameKey} className="text-2xl md:text-[28px] font-extrabold tracking-tight text-slate-900 mt-2 animate-slidein" data-testid="step-title">
              {frame.title}
            </h1>
          )}

          {/* Progress rail (auto-scrolls to the active step) */}
          {script.length > 0 && (
            <div ref={railRef} className="relative mt-3 flex items-stretch gap-1 overflow-x-auto pb-1 pr-2 scroll-smooth" data-testid="replay-rail">
              {script.filter((s) => s.index > 0).map((s) => {
                const cur = frame?.step_index ?? -1;
                const done = s.index < cur;
                const active = s.index === cur;
                return (
                  <div
                    key={`${s.index}-${s.id}`}
                    data-active={active ? 'true' : 'false'}
                    className={`min-w-[132px] flex-1 shrink-0 rounded-lg border px-2 py-1 text-xs transition ${
                      active ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-400' : done ? 'border-slate-200 bg-slate-100 text-slate-500' : 'border-slate-200 bg-white text-slate-400'
                    }`}
                  >
                    <div className="flex items-center gap-1 font-bold">
                      <span className={`w-2 h-2 rounded-full ${LABEL_DOT[s.label] ?? 'bg-slate-400'}`} />
                      {s.index}
                    </div>
                    <div className={`leading-tight mt-0.5 line-clamp-2 ${active ? 'text-slate-900 font-semibold' : ''}`}>{s.title}</div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      {error && <ErrorBox error={error} />}

      {/* 2. Dramatic banner */}
      {frame?.banner && <Banner key={`${frameKey}-${frame.banner.kind}`} banner={frame.banner} />}

      {/* 3. Human approval: compact so Approve / Edit / Reject stay above the fold */}
      {frame?.pending_approval && (
        <ApprovalCard
          key={frame.pending_approval.id}
          item={frame.pending_approval}
          onDecide={decide}
          highlight
          busy={busy}
          compact
          caseDate={frame.sim_date ?? frame.case?.case.sim_date ?? null}
        />
      )}

      {/* 4. Narration */}
      <Card className="p-5" data-testid="narration">
        {frame ? (
          <p key={frameKey} className="text-lg text-slate-700 leading-relaxed animate-slidein">{frame.narration}</p>
        ) : (
          <p className="text-lg text-slate-600 text-center py-2">
            Press <strong>Next</strong> (or <strong>Play</strong>) to start. This replays case KJ-2025-02 from the first satellite observation.
          </p>
        )}
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
        {/* Left: map + tools */}
        <div className="xl:col-span-2 space-y-5">
          <Card className="overflow-hidden">
            <CardHeader title="Monitoring map" subtitle="Marker size scales with √(emission rate) · zones are illustrative" right={<LabelChip label="REAL DATA" />} />
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
