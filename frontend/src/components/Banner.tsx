// Full-width dramatic banners for the replay's key moments.
import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, RotateCcw, XCircle } from 'lucide-react';
import type { Banner as BannerT } from '../types/api';

const STYLES: Record<BannerT['kind'], { cls: string; icon: ReactNode; testid: string }> = {
  rejected: {
    cls: 'bg-red-600 text-white border-red-800 animate-reject',
    icon: <XCircle className="w-14 h-14 shrink-0" />,
    testid: 'banner-rejected',
  },
  verified: {
    cls: 'bg-emerald-600 text-white border-emerald-800',
    icon: <CheckCircle2 className="w-14 h-14 shrink-0" />,
    testid: 'banner-verified',
  },
  reopened: {
    cls: 'bg-gradient-to-r from-red-600 to-orange-500 text-white border-red-800 animate-shake',
    icon: <RotateCcw className="w-14 h-14 shrink-0" />,
    testid: 'banner-reopened',
  },
  warning: {
    cls: 'bg-amber-400 text-slate-950 border-amber-600',
    icon: <AlertTriangle className="w-12 h-12 shrink-0" />,
    testid: 'banner-warning',
  },
  info: {
    cls: 'bg-slate-800 text-white border-slate-900',
    icon: <Info className="w-10 h-10 shrink-0" />,
    testid: 'banner-info',
  },
};

export function Banner({ banner }: { banner: BannerT }) {
  const s = STYLES[banner.kind] ?? STYLES.info;
  return (
    <div key={banner.title} data-testid={s.testid} className={`rounded-2xl border-2 px-6 py-5 flex items-center gap-5 shadow-xl ${s.cls}`} role="alert">
      {s.icon}
      <div>
        <p className="text-2xl md:text-3xl font-black tracking-tight uppercase">{banner.title}</p>
        <p className="text-base md:text-lg mt-1 opacity-95 font-medium">{banner.text}</p>
      </div>
    </div>
  );
}
