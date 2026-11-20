// Audit timeline (Mandar's styling): coloured dot per provenance label, event card with chips.
import { Wrench } from 'lucide-react';
import type { AuditEvent } from '../types/api';
import { fmtDate, LABEL_DOT } from '../lib/format';
import { Chip, LabelChip } from './ui';

export function Timeline({ events, newIds, compact = false, newestFirst = false }: { events: AuditEvent[]; newIds?: Set<string>; compact?: boolean; newestFirst?: boolean }) {
  const list = newestFirst ? [...events].reverse() : events;
  if (!list.length) return <p className="text-sm text-slate-500 italic px-2 py-6">No events yet.</p>;
  return (
    <div className={`relative border-l-2 border-slate-200 ml-3 ${compact ? 'space-y-3' : 'space-y-5'}`} data-testid="timeline">
      {list.map((evt) => {
        const isNew = newIds?.has(evt.id);
        return (
          <div key={evt.id} className={`relative pl-5 ${isNew ? 'animate-slidein' : ''}`} data-testid="timeline-event">
            <div className={`absolute -left-[9px] top-2 w-4 h-4 rounded-full border-2 border-white shadow ${LABEL_DOT[evt.label] ?? 'bg-slate-400'}`} />
            <div className={`rounded-xl border shadow-sm ${isNew ? 'border-teal-300 bg-teal-50/50' : 'border-slate-200 bg-slate-50'} ${compact ? 'p-3' : 'p-4'}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <LabelChip label={evt.label} />
                  <h3 className={`font-bold text-slate-900 ${compact ? 'text-sm' : 'text-[15px]'}`}>{evt.title}</h3>
                </div>
                <span className="text-xs text-slate-500 font-medium whitespace-nowrap">{evt.sim_date ? fmtDate(evt.sim_date) : fmtDate(evt.timestamp)}</span>
              </div>
              {!compact && <p className="text-sm text-slate-700 leading-relaxed mt-2">{evt.description}</p>}
              {compact && evt.description && <p className="text-xs text-slate-600 mt-1 line-clamp-2">{evt.description}</p>}
              <div className="flex flex-wrap items-center gap-1.5 mt-2 text-[11px]">
                <Chip>Actor: {evt.actor_name} ({evt.actor})</Chip>
                <Chip className="bg-white text-slate-600 border-slate-200 font-mono">{evt.type}</Chip>
                {evt.tool && (
                  <Chip className="bg-slate-50 text-slate-600 border-slate-200 font-mono">
                    <Wrench className="w-3 h-3" /> {evt.tool}
                  </Chip>
                )}
                {evt.chain_stage && <Chip className="bg-slate-50 text-slate-800 border-slate-200">Chain: {evt.chain_stage}</Chip>}
                {!compact && evt.evidence_ids.length > 0 && (
                  <Chip className="bg-white text-slate-500 border-slate-200 font-mono">evidence: {evt.evidence_ids.join(', ')}</Chip>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
