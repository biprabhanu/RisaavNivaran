// Small presentational building blocks (Mandar's visual language: white rounded-2xl cards,
// slate borders, emerald accents).
import type { ReactNode } from 'react';
import { AlertTriangle, Eye, Loader2 } from 'lucide-react';
import type { CaseStatus, DataLabel } from '../types/api';
import { LABEL_CLS, STATUS_META } from '../lib/format';

export function Card({ children, className = '', ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    // A caller-supplied background (e.g. bg-slate-900 for a dark panel) replaces the default white.
    <div className={`${/(^|\s)bg-/.test(className) ? '' : 'bg-white '}rounded-2xl border border-slate-200 shadow-sm ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, right, icon }: { title: ReactNode; subtitle?: ReactNode; right?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3 bg-slate-50/50 rounded-t-2xl">
      <div className="flex items-center gap-2 min-w-0">
        {icon}
        <div className="min-w-0">
          <h2 className="font-bold text-slate-900 text-base leading-tight">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/** The one-line "What you're seeing" explanation shown at the top of every page for judges. */
export function Caption({ children }: { children: ReactNode }) {
  return (
    <div className="mb-6 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50/70 px-4 py-3 text-[15px] text-emerald-950" data-testid="page-caption">
      <Eye className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
      <p>
        <strong className="font-semibold">What you're seeing: </strong>
        {children}
      </p>
    </div>
  );
}

export function PageTitle({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-col md:flex-row md:items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="text-slate-500 mt-1">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function LabelChip({ label, className = '' }: { label: DataLabel; className?: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-bold tracking-wide whitespace-nowrap ${LABEL_CLS[label] ?? 'bg-slate-100 text-slate-700 border-slate-200'} ${className}`}>
      {label}
    </span>
  );
}

export function StatusPill({ status, large = false }: { status: CaseStatus; large?: boolean }) {
  const m = STATUS_META[status];
  return (
    <span data-testid="status-pill" className={`inline-flex items-center rounded-full border font-semibold whitespace-nowrap ${m?.cls ?? 'bg-slate-100'} ${large ? 'px-4 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'}`}>
      {m?.label ?? status}
    </span>
  );
}

export function Chip({ children, className = 'bg-slate-100 text-slate-700 border-slate-200' }: { children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs font-medium ${className}`}>{children}</span>;
}

export function Spinner({ text = 'Loading…' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-slate-500">
      <Loader2 className="w-5 h-5 animate-spin" /> {text}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-start gap-2">
      <AlertTriangle className="w-5 h-5 shrink-0" />
      <div className="flex-1">{error}</div>
      {onRetry && (
        <button onClick={onRetry} className="text-red-700 font-semibold underline">
          Retry
        </button>
      )}
    </div>
  );
}

export const btn = {
  primary: 'inline-flex items-center justify-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-emerald-700 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed',
  dark: 'inline-flex items-center justify-center gap-2 bg-slate-900 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-slate-800 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed',
  ghost: 'inline-flex items-center justify-center gap-2 bg-white text-slate-700 border border-slate-300 px-4 py-2 rounded-xl text-sm font-semibold hover:bg-slate-50 transition disabled:opacity-50 disabled:cursor-not-allowed',
  danger: 'inline-flex items-center justify-center gap-2 bg-red-50 text-red-700 border border-red-200 px-4 py-2 rounded-xl text-sm font-semibold hover:bg-red-100 transition disabled:opacity-50 disabled:cursor-not-allowed',
};

export function Stat({ label, value, sub, tone = 'slate' }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'slate' | 'emerald' | 'red' | 'amber' | 'blue' }) {
  const tones: Record<string, string> = {
    slate: 'border-slate-200',
    emerald: 'border-emerald-300 bg-emerald-50/40',
    red: 'border-red-300 bg-red-50/40',
    amber: 'border-amber-300 bg-amber-50/40',
    blue: 'border-blue-300 bg-blue-50/40',
  };
  return (
    <div className={`p-4 rounded-2xl border bg-white shadow-sm ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="text-2xl font-extrabold text-slate-900 mt-1 num">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}
