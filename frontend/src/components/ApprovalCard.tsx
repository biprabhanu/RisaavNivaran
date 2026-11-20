// One item in the Human Approval Queue. Approve / Edit (then approve) / Reject.
import { useState } from 'react';
import { Check, Pencil, UserCheck, X } from 'lucide-react';
import type { ApprovalDecision, ApprovalItem } from '../types/api';
import { APPROVAL_KIND_LABEL, fmtDate } from '../lib/format';
import { Chip, btn } from './ui';

interface Props {
  item: ApprovalItem;
  onDecide?: (d: ApprovalDecision) => Promise<void> | void;
  highlight?: boolean;
  busy?: boolean;
  compact?: boolean; // replay: hide the drafted text behind a toggle so the buttons stay above the fold
  caseDate?: string | null; // in-world date of the case (the replay runs in 2025–2026)
}

const PURPOSE_LABEL: Record<string, string> = {
  investigation: 'Investigation request',
  attribution: 'Source attribution',
  corrective_action: 'Corrective-action notice',
  notice: 'Stakeholder notice',
  closure: 'Final closure',
  transition: 'Status change',
};

const STATUS_CLS: Record<string, string> = {
  PENDING: 'bg-amber-100 text-amber-900 border-amber-300',
  APPROVED: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  EDITED: 'bg-sky-100 text-sky-800 border-sky-300',
  REJECTED: 'bg-red-100 text-red-800 border-red-300',
};

export function ApprovalCard({ item, onDecide, highlight = false, busy = false, compact = false, caseDate }: Props) {
  const [editing, setEditing] = useState(false);
  const [showDraft, setShowDraft] = useState(!compact);
  const purpose = typeof item.payload.purpose === 'string' ? item.payload.purpose : null;
  const sendsText = !!item.proposed_text && purpose !== 'attribution' && purpose !== 'closure';
  const [text, setText] = useState(item.edited_text ?? item.proposed_text);
  const [note, setNote] = useState('');
  const pending = item.status === 'PENDING';

  return (
    <div
      data-testid="approval-card"
      className={`rounded-2xl border-2 bg-white ${compact ? 'p-4' : 'p-5'} shadow-sm ${highlight && pending ? 'border-violet-400 animate-glow' : 'border-slate-200'}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <UserCheck className="w-5 h-5 text-violet-600" />
          <span className="text-xs font-bold uppercase tracking-wider text-violet-700">
            {pending ? 'Human approval required' : 'Decision recorded'}
          </span>
          <Chip className="bg-violet-50 text-violet-800 border-violet-200">{APPROVAL_KIND_LABEL[item.kind] ?? item.kind}</Chip>
          {purpose && PURPOSE_LABEL[purpose] && PURPOSE_LABEL[purpose] !== APPROVAL_KIND_LABEL[item.kind] && (
            <Chip className="bg-white text-violet-800 border-violet-200">{PURPOSE_LABEL[purpose]}</Chip>
          )}
          {sendsText && (
            <Chip className="bg-amber-50 text-amber-900 border-amber-300 font-bold">SIMULATED: sending is simulated</Chip>
          )}
          <Chip className="font-mono">{item.case_id}</Chip>
        </div>
        <Chip className={STATUS_CLS[item.status]}>{item.status}</Chip>
      </div>
      <h3 title={item.title} className={`${compact ? 'text-base mt-2 truncate' : 'text-lg mt-3'} font-bold text-slate-900`}>{item.title}</h3>
      <p title={compact ? item.summary : undefined} className={`text-sm text-slate-700 mt-1 ${compact ? 'line-clamp-2' : ''}`}>{item.summary}</p>

      {compact && item.proposed_text && !editing && (
        <button className="mt-2 text-xs font-semibold text-violet-700 underline" onClick={() => setShowDraft((v) => !v)}>
          {showDraft ? 'Hide drafted text' : 'Show drafted text'}
        </button>
      )}
      {((item.proposed_text && showDraft) || editing) && (
        <div className="mt-3">
          {editing ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              className="w-full font-mono text-xs p-3 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-violet-500 bg-slate-50"
            />
          ) : (
            <pre className="whitespace-pre-wrap text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-xl p-3 max-h-48 overflow-auto font-sans">
              {item.edited_text ?? item.proposed_text}
            </pre>
          )}
        </div>
      )}

      <div className={`flex flex-wrap items-center gap-2 ${compact ? 'mt-2' : 'mt-3'} text-xs text-slate-500`}>
        {item.evidence_ids.length > 0 && (
          <span className={`font-mono ${compact ? 'truncate max-w-[260px]' : ''}`} title={item.evidence_ids.join(', ')}>
            evidence: {item.evidence_ids.join(', ')}
          </span>
        )}
        {caseDate && <span>· case date <strong>{fmtDate(caseDate)}</strong></span>}
        <span>· logged {fmtDate(item.created_at)}</span>
        {item.decided_by && (
          <span>
            · decided by <strong>{item.decided_by}</strong> {item.decided_at ? `(${fmtDate(item.decided_at)})` : ''}
          </span>
        )}
        {item.note && <span>· note: {item.note}</span>}
      </div>

      {pending && onDecide && (
        <div className={`${compact ? 'mt-3' : 'mt-4'} flex flex-wrap items-center gap-2`}>
          {!editing ? (
            <>
              <button data-testid="approve-button" disabled={busy} className={btn.primary} onClick={() => onDecide({ decision: 'approve', note })}>
                <Check className="w-4 h-4" /> Approve
              </button>
              <button data-testid="edit-button" disabled={busy} className={btn.ghost} onClick={() => setEditing(true)}>
                <Pencil className="w-4 h-4" /> Edit
              </button>
              <button data-testid="reject-button" disabled={busy} className={btn.danger} onClick={() => onDecide({ decision: 'reject', note })}>
                <X className="w-4 h-4" /> Reject
              </button>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Optional note for the audit log"
                className="flex-1 min-w-[180px] text-sm px-3 py-2 rounded-xl border border-slate-200"
              />
            </>
          ) : (
            <>
              <button disabled={busy} className={btn.primary} onClick={() => onDecide({ decision: 'edit', edited_text: text, note })}>
                <Check className="w-4 h-4" /> Save edits &amp; approve
              </button>
              <button className={btn.ghost} onClick={() => setEditing(false)}>
                Cancel
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
