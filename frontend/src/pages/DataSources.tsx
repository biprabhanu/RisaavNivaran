// Mandar's ingestion page, kept and wired to the agent: an uploaded observation becomes a new case.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle, Upload } from 'lucide-react';
import type { CaseDetail } from '../types/api';
import { api, errMsg } from '../lib/api';
import { bumpData, showToast, useAppState } from '../lib/store';
import { Caption, Card, CardHeader, LabelChip, PageTitle, btn } from '../components/ui';

const SAMPLE = {
  observation_id: 'OBS-SAMPLE-01',
  facility_name: 'Kanjur Landfill (sample upload)',
  latitude: 19.132,
  longitude: 72.933,
  observation_date: '2026-06-01',
  emission_rate_kg_hour: 1400.0,
  source: 'SIMULATED SAMPLE UPLOAD',
  confidence: 0.95,
};

export default function DataSources() {
  const { offline } = useAppState();
  const [text, setText] = useState('');
  const [created, setCreated] = useState<CaseDetail | null>(null);
  const [busy, setBusy] = useState(false);

  const upload = async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      showToast('Invalid JSON.');
      return;
    }
    setBusy(true);
    try {
      const d = await api.uploadObservation(parsed);
      setCreated(d);
      showToast(`Observation validated: case ${d.case.id} created by the agent.`);
      setText('');
      bumpData();
    } catch (e) {
      showToast(`Validation failed: ${errMsg(e)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <Caption>
        where data comes from. Real plume observations come from the Carbon Mapper open data portal; you can also upload an observation as JSON, and the agent validates it and
        opens a new case. Sample uploads are <strong>simulated</strong>.
      </Caption>
      <PageTitle title="Data sources & ingestion" subtitle="Validate coordinates, timestamps and units; tag provenance on every record" />

      <div className="grid md:grid-cols-3 gap-4">
        {[
          { t: 'Carbon Mapper Open Data Portal', d: 'Satellite plume observations with emission rates (Kanjur 9 Feb 2025, 3 Apr 2026).', l: 'REAL DATA' as const },
          { t: 'UN MARS alerts', d: 'Public alert & response information. Adapter is future work.', l: null },
          { t: 'Operator records & field measurements', d: 'Simulated in this prototype; clearly labelled everywhere.', l: 'SIMULATED EVENT' as const },
        ].map((s) => (
          <Card key={s.t} className="p-5">
            {s.l ? (
              <LabelChip label={s.l} />
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-bold tracking-wide bg-slate-100 text-slate-600 border-slate-300">
                NOT INTEGRATED (future work)
              </span>
            )}
            <h3 className="font-bold mt-2">{s.t}</h3>
            <p className="text-sm text-slate-600 mt-1">{s.d}</p>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader title="Upload observation JSON" subtitle="POST /api/observations/upload → the agent opens a case" />
        <div className="grid md:grid-cols-2 gap-6 p-6">
          <div className="space-y-3">
            <textarea
              rows={11}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={JSON.stringify(SAMPLE, null, 2)}
              className="w-full font-mono text-xs p-4 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-slate-50"
            />
            <div className="flex gap-2">
              <button className={btn.ghost} onClick={() => setText(JSON.stringify(SAMPLE, null, 2))}>
                Load simulated sample
              </button>
              <button onClick={upload} disabled={busy || !text.trim() || offline} className={`${btn.primary} flex-1`}>
                <Upload className="w-4 h-4" /> Validate &amp; ingest observation
              </button>
            </div>
            {created && (
              <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm">
                Case <strong>{created.case.id}</strong> created.{' '}
                <Link className="underline font-semibold" to={`/cases/${created.case.id}`}>
                  Open it →
                </Link>
              </div>
            )}
          </div>
          <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200 flex flex-col justify-between">
            <div className="space-y-3">
              <h3 className="font-bold text-sm">Pipeline validation standards</h3>
              <ul className="space-y-2 text-sm text-slate-600">
                {[
                  'Coordinate boundary verification (latitude / longitude bounds)',
                  'Timestamp and date format parsing',
                  'Unit standardisation to kg CH₄/hour',
                  'Duplicate observation ID detection',
                  'Provenance tagging on every record (REAL DATA vs SIMULATED)',
                ].map((x) => (
                  <li key={x} className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" /> {x}
                  </li>
                ))}
              </ul>
            </div>
            <p className="mt-6 pt-4 border-t border-slate-200 text-xs text-slate-500 flex gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              The files in backend/data/sample_observations.* are sample uploads, not real satellite observations.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
