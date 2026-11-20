import { useState } from 'react';
import type { ApprovalDecision, ApprovalItem } from '../types/api';
import { api, errMsg } from '../lib/api';
import { useApi } from '../lib/hooks';
import { bumpData, showToast, useAppState } from '../lib/store';
import { ApprovalCard } from '../components/ApprovalCard';
import { Caption, ErrorBox, PageTitle, Spinner, Stat } from '../components/ui';

export default function Approvals() {
  const { offline } = useAppState();
  const { data, error, loading, reload } = useApi(() => api.approvals());
  const [busy, setBusy] = useState<string | null>(null);

  const decide = async (item: ApprovalItem, d: ApprovalDecision) => {
    setBusy(item.id);
    try {
      await api.decide(item.id, d);
      showToast(`${d.decision === 'reject' ? 'Rejected' : 'Approved'}: ${item.title}. The decision is logged as HUMAN DECISION.`);
      bumpData();
    } catch (e) {
      showToast(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const items = data ?? [];
  const pending = items.filter((i) => i.status === 'PENDING');
  const history = items.filter((i) => i.status !== 'PENDING').sort((a, b) => (b.decided_at ?? '').localeCompare(a.decided_at ?? ''));

  return (
    <div className="space-y-5">
      <Caption>
        the Human Approval Queue. The agent never attributes a source, sends an official notice, dispatches a field team or closes a case on its own; it waits here for a
        human to Approve, Edit or Reject.
      </Caption>
      <PageTitle title="Approval Queue" subtitle="Source attribution · official notifications · field investigations · final closure" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Pending" value={pending.length} tone="amber" />
        <Stat label="Approved" value={items.filter((i) => i.status === 'APPROVED' || i.status === 'EDITED').length} tone="emerald" />
        <Stat label="Rejected" value={items.filter((i) => i.status === 'REJECTED').length} tone="red" />
        <Stat label="Total decisions" value={items.length} />
      </div>
      {loading && !data && <Spinner />}
      {error && <ErrorBox error={error} onRetry={reload} />}

      <section className="space-y-3">
        <h2 className="text-lg font-bold">Waiting for a human ({pending.length})</h2>
        {pending.length === 0 && <p className="text-slate-500 italic">Nothing pending. Run the replay or draft a notice from the Case page to create items.</p>}
        {pending.map((i) => (
          <ApprovalCard key={i.id} item={i} highlight busy={busy === i.id} onDecide={offline ? undefined : (d) => decide(i, d)} />
        ))}
      </section>

      {history.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">Decision history ({history.length})</h2>
          {history.map((i) => (
            <ApprovalCard key={i.id} item={i} />
          ))}
        </section>
      )}
    </div>
  );
}
