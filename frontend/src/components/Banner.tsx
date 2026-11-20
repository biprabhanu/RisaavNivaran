// Full-width banners for the replay's key moments.
// "Closure rejected" and "Case reopened" are the two show-stopper moments: they are always big and solid red.
// Other banners (verified, warning, info) stay smaller so the step's main visual remains above the fold.
import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, RotateCcw, XCircle } from 'lucide-react';
import type { Banner as BannerT } from '../types/api';

const STYLES: Record<BannerT['kind'], { cls: string; icon: ReactNode; testid: string; big: boolean }> = {
  rejected: { cls: 'bg-red-600 text-white animate-reject', icon: <XCircle />, testid: 'banner-rejected', big: true },
  reopened: { cls: 'bg-red-600 text-white animate-shake', icon: <RotateCcw />, testid: 'banner-reopened', big: true },
  verified: { cls: 'bg-green-600 text-white', icon: <CheckCircle2 />, testid: 'banner-verified', big: false },
  warning: { cls: 'bg-amber-50 text-amber-900 border border-amber-300', icon: <AlertTriangle />, testid: 'banner-warning', big: false },
  info: { cls: 'bg-white text-slate-800 border border-slate-200', icon: <Info />, testid: 'banner-info', big: false },
};

export function Banner({ banner, compact = false }: { banner: BannerT; compact?: boolean }) {
  const s = STYLES[banner.kind] ?? STYLES.info;
  const big = s.big; // show-stoppers ignore `compact`
  return (
    <div
      key={banner.title}
      data-testid={s.testid}
      role="alert"
      className={`w-full rounded-xl flex items-center ${big ? 'px-8 py-6 gap-6 shadow-lg' : compact ? 'px-5 py-3 gap-4' : 'px-6 py-4 gap-4'} ${s.cls}`}
    >
      <span className={`shrink-0 ${big ? '[&>svg]:w-14 [&>svg]:h-14' : '[&>svg]:w-8 [&>svg]:h-8'}`}>{s.icon}</span>
      <div className="min-w-0">
        <p className={`${big ? 'text-3xl md:text-4xl font-extrabold uppercase tracking-tight' : 'text-lg md:text-xl font-bold'} leading-tight`}>{banner.title}</p>
        <p className={`${big ? 'text-lg md:text-xl mt-1.5 font-medium' : 'text-sm md:text-base mt-0.5'} opacity-95`}>{banner.text}</p>
      </div>
    </div>
  );
}
