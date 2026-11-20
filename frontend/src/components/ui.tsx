// Small presentational building blocks: the whole app's design system lives here and in lib/format.ts.
// White cards with subtle slate borders on a light-grey page; one teal accent; red/amber/green for status only.
import type { ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import type { CaseStatus, DataLabel } from '../types/api';
import { LABEL_CLS, STATUS_META } from '../lib/format';

export function Card({ children, className = '', ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    // A caller-supplied background replaces the default white.
    <div className={`${/(^|\s)bg-/.test(className) ? '' : 'bg-white '}rounded-xl border border-slate-200 ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, right, icon }: { title: ReactNode; subtitle?: ReactNode; right?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2.5 min-w-0">
        {icon && <span className="text-slate-400 shrink-0 [&>svg]:text-current">{icon}</span>}
        <div className="min-w-0">
          <h2 className="font-semibold text-slate-900 text-base leading-tight">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/**
 * Page header: a clear title plus ONE short line explaining what the page shows (for judges).
 * The description carries data-testid="page-caption".
 */
export function PageTitle({ title, description, meta, right }: { title: string; description: ReactNode; meta?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col md:flex-row md:items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl md:text-[28px] font-bold tracking-tight text-slate-900 leading-tight">{title}</h1>
        <p className="mt-1.5 text-[15px] text-slate-600 max-w-3xl" data-testid="page-caption">
          {description}
        </p>
        {meta && <p className="mt-1 text-xs text-slate-400">{meta}</p>}
      </div>
      {right && <div className="shrink-0 flex items-center gap-2">{right}</div>}
    </div>
  );
}

export function LabelChip({ label, className = '' }: { label: DataLabel; className?: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-semibold tracking-wide whitespace-nowrap ${LABEL_CLS[label] ?? 'bg-slate-100 text-slate-700 border-slate-200'} ${className}`}>
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

const BTN = 'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed';
export const btn = {
  primary: `${BTN} bg-teal-600 text-white hover:bg-teal-700`,
  dark: `${BTN} bg-slate-900 text-white hover:bg-slate-800`,
  ghost: `${BTN} bg-white text-slate-700 border border-slate-300 hover:bg-slate-50`,
  danger: `${BTN} bg-white text-red-700 border border-red-300 hover:bg-red-50`,
};

type Tone = 'slate' | 'teal' | 'red' | 'amber' | 'green';
export function Stat({ label, value, sub, tone = 'slate' }: { label: string; value: ReactNode; sub?: ReactNode; tone?: Tone }) {
  // Tone is a thin left accent only, so tiles stay calm: teal = headline, red/amber/green = status.
  const accent: Record<Tone, string> = {
    slate: 'border-l-slate-200',
    teal: 'border-l-teal-600',
    red: 'border-l-red-500',
    amber: 'border-l-amber-500',
    green: 'border-l-green-600',
  };
  return (
    <div className={`p-5 rounded-xl border border-slate-200 border-l-4 bg-white ${accent[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="text-[26px] font-bold text-slate-900 mt-1.5 leading-none num">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-2">{sub}</p>}
    </div>
  );
}
