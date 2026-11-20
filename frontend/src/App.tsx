import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { 
  ShieldAlert, Activity, FileText, CheckCircle2, AlertTriangle, 
  Upload, RefreshCw, Layers, ArrowRight, CheckCircle, XCircle, Clock, Database, Globe, Search, Play, HelpCircle
} from 'lucide-react';
import L from 'leaflet';

// Fix leaflet marker icon issue in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const customIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'investigation' | 'pipeline' | 'planner' | 'timeline' | 'verification'>('dashboard');
  const [cases, setCases] = useState<any[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('KJ-2025-02');
  const [selectedCase, setSelectedCase] = useState<any>(null);
  const [investigations, setInvestigations] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [toast, setToast] = useState<string | null>(null);

  // Verification state
  const [preRate, setPreRate] = useState<number>(1736);
  const [preUncertainty, setPreUncertainty] = useState<number>(150);
  const [postRate, setPostRate] = useState<number>(120);
  const [postUncertainty, setPostUncertainty] = useState<number>(30);
  const [comparable, setComparable] = useState<boolean>(true);
  const [independent, setIndependent] = useState<boolean>(true);
  const [verificationResult, setVerificationResult] = useState<any>(null);

  // Upload state
  const [uploadText, setUploadText] = useState<string>('');

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (cases.length > 0) {
      const c = cases.find(item => item.case_id === selectedCaseId) || cases[0];
      setSelectedCase(c);
    }
  }, [selectedCaseId, cases]);

  const fetchData = async () => {
    try {
      const resCases = await fetch('http://localhost:8000/api/cases');
      const dataCases = await resCases.json();
      setCases(dataCases.cases);
      if (dataCases.cases.length > 0) {
        setSelectedCase(dataCases.cases[0]);
      }

      const resInvs = await fetch('http://localhost:8000/api/investigations');
      const dataInvs = await resInvs.json();
      setInvestigations(dataInvs.investigations);

      const resTime = await fetch('http://localhost:8000/api/cases/KJ-2025-02/timeline');
      const dataTime = await resTime.json();
      setTimeline(dataTime.timeline);
    } catch (e) {
      console.error("API fetch error, using fallback seed", e);
    }
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  const handleMarkUnavailable = async (id: string) => {
    try {
      const res = await fetch('http://localhost:8000/api/investigations/resource-unavailable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ investigation_id: id })
      });
      const data = await res.json();
      setInvestigations(data.investigations);
      showToast("Resource marked unavailable. Evidence planner re-ranked successfully!");
      fetchData(); // refresh timeline
    } catch (e) {
      showToast("Error updating resource status");
    }
  };

  const handleEvaluateVerification = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/verification/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pre_rate: preRate,
          pre_uncertainty: preUncertainty,
          post_rate: postRate,
          post_uncertainty: postUncertainty,
          comparable_conditions: comparable,
          independent_measurement: independent
        })
      });
      const data = await res.json();
      setVerificationResult(data);
      showToast(`Verification Outcome: ${data.outcome}`);
      fetchData();
    } catch (e) {
      showToast("Error evaluating verification");
    }
  };

  const handleSimulateRepairClosure = async () => {
    try {
      await fetch('http://localhost:8000/api/cases/KJ-2025-02/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: "Operator reports repair completion",
          description: "Municipal operator reported repair of gas collection wells. Agent automatically rejected closure due to lack of independent post-measurement.",
          evidence: "SIMULATED DEMONSTRATION DATA",
          responsible_actor: "Facility Operator",
          approval_status: "Rejected by Agent"
        })
      });
      showToast("Operator repair reported. Agent successfully REJECTED closure without independent verification!");
      fetchData();
    } catch (e) {
      showToast("Error simulating repair");
    }
  };

  const handleUploadJSON = async () => {
    try {
      const parsed = JSON.parse(uploadText);
      const res = await fetch('http://localhost:8000/api/observations/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsed)
      });
      const data = await res.json();
      if (data.status === 'success') {
        showToast("Observation uploaded and validated successfully!");
        setUploadText('');
        fetchData();
      }
    } catch (e) {
      showToast("Invalid JSON format or validation failed.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col">
      {/* Top Notification Toast */}
      {toast && (
        <div className="fixed top-5 right-5 z-50 bg-slate-900 text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 border border-slate-700 animate-bounce">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <span className="text-sm font-medium">{toast}</span>
        </div>
      )}

      {/* Top Header */}
      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40 shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="bg-emerald-500 p-2.5 rounded-xl shadow-lg shadow-emerald-500/20">
              <ShieldAlert className="w-7 h-7 text-slate-950 font-bold" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight">PlumeProof</h1>
                <span className="bg-emerald-500/20 text-emerald-400 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-emerald-500/30">MVP v1.0</span>
              </div>
              <p className="text-xs text-slate-400">Agentic AI for Methane Detection, Investigation & Verified Mitigation (IIT Bombay)</p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="bg-blue-500/10 text-blue-400 px-3 py-1 rounded-lg border border-blue-500/20 font-medium">
              HISTORICAL SATELLITE DATA: Kanjur Landfill (Mumbai)
            </span>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="bg-slate-950/60 border-t border-slate-800/60 px-4 sm:px-6 lg:px-8">
          <div className="max-w-7xl mx-auto flex space-x-1 sm:space-x-8 overflow-x-auto">
            {[
              { id: 'dashboard', label: 'Monitoring Dashboard', icon: Activity },
              { id: 'investigation', label: 'Investigation Cases', icon: FileText },
              { id: 'planner', label: 'Evidence Planner', icon: Search },
              { id: 'timeline', label: 'Audit Timeline', icon: Clock },
              { id: 'verification', label: 'Mitigation Verification', icon: CheckCircle2 },
              { id: 'pipeline', label: 'Data Sources & Ingestion', icon: Database },
            ].map(tab => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 py-3 px-3 border-b-2 text-sm font-medium transition-colors whitespace-nowrap ${
                    active 
                      ? 'border-emerald-400 text-emerald-400' 
                      : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* PAGE 1: MONITORING DASHBOARD */}
        {activeTab === 'dashboard' && (
          <div className="space-y-8">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {[
                { title: 'Total Methane Alerts', value: '12', sub: '2 Active Sites', color: 'border-blue-500/30 bg-blue-50/50 text-blue-700' },
                { title: 'High-Priority Alerts', value: '5', sub: '>1,000 kg CH4/hr', color: 'border-red-500/30 bg-red-50/50 text-red-700' },
                { title: 'Investigations Pending', value: '3', sub: 'Action Required', color: 'border-orange-500/30 bg-orange-50/50 text-orange-700' },
                { title: 'Awaiting Verification', value: '2', sub: 'Post-Intervention', color: 'border-amber-500/30 bg-amber-50/50 text-amber-700' },
                { title: 'Verified Outcomes', value: '8', sub: 'Independently Confirmed', color: 'border-emerald-500/30 bg-emerald-50/50 text-emerald-700' },
              ].map((card, idx) => (
                <div key={idx} className={`p-5 rounded-2xl border bg-white shadow-sm flex flex-col justify-between ${card.color}`}>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-600">{card.title}</p>
                  <div className="my-3 flex items-baseline justify-between">
                    <span className="text-3xl font-extrabold text-slate-900">{card.value}</span>
                  </div>
                  <span className="text-xs font-medium text-slate-500">{card.sub}</span>
                </div>
              ))}
            </div>

            {/* Map and Quick Info Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Interactive Map */}
              <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col">
                <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <div className="flex items-center gap-2">
                    <Globe className="w-5 h-5 text-blue-600" />
                    <h2 className="font-bold text-slate-900 text-sm">Geospatial Intelligence Map — Mumbai Region</h2>
                  </div>
                  <span className="text-xs bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full font-medium">HISTORICAL SATELLITE DATA</span>
                </div>
                <div className="h-[450px] w-full relative z-10">
                  <MapContainer center={[19.1312, 72.9345]} zoom={13} style={{ height: '100%', width: '100%' }}>
                    <TileLayer
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    <Marker position={[19.1312, 72.9345]} icon={customIcon}>
                      <Popup>
                        <div className="p-2 space-y-2">
                          <h3 className="font-bold text-sm text-slate-900">Kanjur Landfill, Mumbai</h3>
                          <p className="text-xs text-slate-600">Case ID: KJ-2025-02</p>
                          <p className="text-xs text-slate-600">Emission: ~1,736 kg CH4/hr</p>
                          <button 
                            onClick={() => { setSelectedCaseId('KJ-2025-02'); setActiveTab('investigation'); }}
                            className="mt-2 w-full bg-emerald-600 text-white py-1.5 px-3 rounded text-xs font-semibold hover:bg-emerald-700 transition"
                          >
                            Open Investigation
                          </button>
                        </div>
                      </Popup>
                    </Marker>
                  </MapContainer>
                </div>
              </div>

              {/* Sidebar Quick Highlight */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 text-emerald-600 mb-3">
                    <ShieldAlert className="w-5 h-5" />
                    <h3 className="font-bold text-slate-900">Featured Case: Kanjur</h3>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed mb-4">
                    Identified via Carbon Mapper satellite observation on 9 February 2025. Two distinct plumes (~1,600 kg/hr and ~136 kg/hr) detected over the municipal waste site in Mumbai.
                  </p>
                  <div className="space-y-3 bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Status:</span>
                      <span className="font-semibold text-orange-600">Source Attribution Pending</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Priority:</span>
                      <span className="font-semibold text-red-600">High (Top 3 Global Emitter)</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Primary Hypothesis:</span>
                      <span className="font-semibold text-slate-800">Exposed Waste (50%)</span>
                    </div>
                  </div>
                </div>

                <button 
                  onClick={() => { setSelectedCaseId('KJ-2025-02'); setActiveTab('investigation'); }}
                  className="mt-6 w-full bg-slate-900 text-white py-2.5 px-4 rounded-xl text-sm font-semibold hover:bg-slate-800 flex items-center justify-center gap-2 transition"
                >
                  View Case Investigation <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Case Table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-slate-900">Active Investigation Cases</h3>
                  <p className="text-xs text-slate-500">Manage satellite alerts through evidence attribution and verification</p>
                </div>
                <span className="text-xs bg-slate-100 text-slate-700 px-3 py-1 rounded-full font-medium">Showing {cases.length} Cases</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                      <th className="py-3 px-6 font-semibold">Case ID</th>
                      <th className="py-3 px-6 font-semibold">Facility</th>
                      <th className="py-3 px-6 font-semibold">Location</th>
                      <th className="py-3 px-6 font-semibold">Observation Date</th>
                      <th className="py-3 px-6 font-semibold">Emission Rate</th>
                      <th className="py-3 px-6 font-semibold">Priority</th>
                      <th className="py-3 px-6 font-semibold">Status</th>
                      <th className="py-3 px-6 font-semibold text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {cases.map((c) => (
                      <tr key={c.case_id} className="hover:bg-slate-50/80 transition">
                        <td className="py-4 px-6 font-mono font-bold text-slate-900">{c.case_id}</td>
                        <td className="py-4 px-6 font-medium text-slate-800">{c.facility}</td>
                        <td className="py-4 px-6 text-slate-600">{c.location}</td>
                        <td className="py-4 px-6 text-slate-600">{c.observation_date}</td>
                        <td className="py-4 px-6 font-semibold text-slate-900">{c.emission_rate_kg_hour} kg CH4/hr</td>
                        <td className="py-4 px-6">
                          <span className={`inline-flex px-2.5 py-1 text-xs font-semibold rounded-full ${
                            c.priority === 'Critical' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'
                          }`}>
                            {c.priority}
                          </span>
                        </td>
                        <td className="py-4 px-6">
                          <span className="inline-flex px-2.5 py-1 text-xs font-medium rounded-full bg-slate-100 text-slate-700">
                            {c.investigation_status}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-right">
                          <button
                            onClick={() => { setSelectedCaseId(c.case_id); setActiveTab('investigation'); }}
                            className="bg-emerald-600 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold hover:bg-emerald-700 transition shadow-sm"
                          >
                            Open Case
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* PAGE 2: INVESTIGATION CASE DETAILS */}
        {activeTab === 'investigation' && selectedCase && (
          <div className="space-y-8">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-100">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-2xl font-extrabold text-slate-900">{selectedCase.case_id} — {selectedCase.facility}</h2>
                    <span className="bg-orange-100 text-orange-800 px-3 py-1 rounded-full text-xs font-semibold">
                      {selectedCase.investigation_status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500 mt-1">Location: {selectedCase.location} | Observed: {selectedCase.observation_date}</p>
                </div>
                <div className="flex items-center gap-3">
                  <button 
                    onClick={() => setActiveTab('planner')}
                    className="bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-emerald-700 transition shadow-sm flex items-center gap-2"
                  >
                    <Search className="w-4 h-4" /> Open Evidence Planner
                  </button>
                  <button 
                    onClick={() => setActiveTab('timeline')}
                    className="bg-slate-900 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-slate-800 transition shadow-sm flex items-center gap-2"
                  >
                    <Clock className="w-4 h-4" /> View Audit Timeline
                  </button>
                </div>
              </div>

              {/* Satellite Observations Section */}
              <div className="mt-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-slate-900 text-base">Satellite Observations</h3>
                  <span className="text-xs bg-blue-100 text-blue-800 px-2.5 py-1 rounded-full font-semibold">HISTORICAL SATELLITE DATA</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {selectedCase.satellite_observations.map((obs: any, idx: number) => (
                    <div key={idx} className="p-4 rounded-xl border border-blue-100 bg-blue-50/30 flex flex-col justify-between">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900 text-sm">{obs.plume_id}</span>
                        <span className="text-xs text-blue-700 font-semibold">{obs.date}</span>
                      </div>
                      <div className="my-3">
                        <span className="text-2xl font-extrabold text-blue-900">{obs.emission_rate}</span>
                        <span className="text-sm text-slate-600 ml-1">{obs.unit}</span>
                      </div>
                      <span className="text-xs text-slate-500 italic">Source attribution pending further ground investigation.</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Source Attribution Hypotheses */}
              <div className="mt-8 pt-6 border-t border-slate-100">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-bold text-slate-900 text-base">Source Attribution Hypotheses (Bayesian Prior Probabilities)</h3>
                  <span className="text-xs bg-amber-100 text-amber-800 px-2.5 py-1 rounded-full font-semibold">AGENT-GENERATED OUTPUT</span>
                </div>
                <p className="text-xs text-slate-500 mb-6 italic">
                  "The system maintains competing hypotheses instead of assuming that satellite observations alone establish the precise emission source."
                </p>

                <div className="space-y-4">
                  {selectedCase.source_attribution.map((hyp: any, idx: number) => (
                    <div key={idx} className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-semibold text-slate-800">{hyp.source}</span>
                        <span className="text-sm font-bold text-slate-900">{(hyp.probability * 100).toFixed(0)}%</span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                        <div 
                          className="bg-emerald-600 h-2.5 rounded-full transition-all duration-500" 
                          style={{ width: `${hyp.probability * 100}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Outstanding Information Requirements */}
              <div className="mt-8 pt-6 border-t border-slate-100">
                <h3 className="font-bold text-slate-900 text-base mb-3">Outstanding Information Requirements</h3>
                <ul className="space-y-2 bg-amber-50/50 p-4 rounded-xl border border-amber-200/60 text-xs text-slate-700">
                  {selectedCase.outstanding_requirements.map((req: string, idx: number) => (
                    <li key={idx} className="flex items-start gap-2">
                      <HelpCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <span>{req}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Action Buttons */}
              <div className="mt-8 flex flex-wrap items-center gap-4 pt-6 border-t border-slate-100">
                <button 
                  onClick={() => setActiveTab('planner')}
                  className="bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-emerald-700 transition shadow-sm flex items-center gap-2"
                >
                  <Search className="w-4 h-4" /> Generate Investigation Plan
                </button>
                <button 
                  onClick={handleSimulateRepairClosure}
                  className="bg-slate-900 text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-slate-800 transition shadow-sm flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" /> Simulate Operator Repair Notification
                </button>
              </div>
            </div>
          </div>
        )}

        {/* PAGE 3: SATELLITE DATA AND GEOSPATIAL PIPELINE */}
        {activeTab === 'pipeline' && (
          <div className="space-y-8">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
              <div className="flex items-center justify-between pb-6 border-b border-slate-100">
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900">Satellite Data Ingestion & Geospatial Pipeline</h2>
                  <p className="text-xs text-slate-500">Accept methane observations from CSV/JSON, validate coordinates, timestamps and units.</p>
                </div>
                <span className="text-xs bg-blue-100 text-blue-800 px-3 py-1 rounded-full font-semibold">Clean Adapter Architecture</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-6">
                {/* Upload Section */}
                <div className="space-y-4">
                  <h3 className="font-bold text-slate-900 text-sm">Upload Observation JSON</h3>
                  <p className="text-xs text-slate-500">Paste JSON payload matching observation schema or upload file.</p>
                  <textarea
                    rows={8}
                    value={uploadText}
                    onChange={(e) => setUploadText(e.target.value)}
                    placeholder={`{\n  "observation_id": "OBS-NEW-01",\n  "facility_name": "Kanjur West Landfill",\n  "latitude": 19.1320,\n  "longitude": 72.9330,\n  "observation_date": "2026-06-01",\n  "emission_rate_kg_hour": 1400.0,\n  "source": "HISTORICAL SATELLITE DATA",\n  "confidence": 0.95\n}`}
                    className="w-full font-mono text-xs p-4 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 bg-slate-50"
                  ></textarea>
                  <button
                    onClick={handleUploadJSON}
                    className="w-full bg-emerald-600 text-white py-3 rounded-xl text-sm font-semibold hover:bg-emerald-700 transition shadow-sm flex items-center justify-center gap-2"
                  >
                    <Upload className="w-4 h-4" /> Validate & Ingest Observation
                  </button>
                </div>

                {/* Pipeline Features */}
                <div className="bg-slate-50 p-6 rounded-2xl border border-slate-200 flex flex-col justify-between">
                  <div className="space-y-4">
                    <h3 className="font-bold text-slate-900 text-sm">Pipeline Validation Standards</h3>
                    <ul className="space-y-3 text-xs text-slate-600">
                      <li className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Coordinate boundary verification (Latitude/Longitude bounds)</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Timestamp and date format parsing</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Unit standardisation to kg CH4/hour</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Duplicate observation ID detection</span>
                      </li>
                      <li className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Data provenance tagging: <strong className="text-slate-900">HISTORICAL SATELLITE DATA</strong></span>
                      </li>
                    </ul>
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-200 text-xs text-slate-500 italic">
                    Ready for Carbon Mapper Open Data Portal & UN MARS API adapters.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PAGE 4: EVIDENCE PLANNER */}
        {activeTab === 'planner' && (
          <div className="space-y-8">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-100">
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900">Interactive Evidence Planner & Decision Engine</h2>
                  <p className="text-xs text-slate-500">Ranking investigation actions by Expected Information Gain (EIG) per ₹10,000.</p>
                </div>
                <div className="bg-emerald-50 text-emerald-800 px-4 py-2 rounded-xl text-xs font-bold border border-emerald-200">
                  Top Recommended Action: REQUEST OPERATIONAL RECORDS
                </div>
              </div>

              {/* Worked Example Banner */}
              <div className="my-6 p-4 rounded-xl bg-blue-50/50 border border-blue-100 text-xs text-blue-900 leading-relaxed">
                <strong>Why absolute information gain isn't enough:</strong> Comprehensive ground-level surveys offer high information gain (0.91 bits) but incur high costs (₹60,000) and take 5 days. The optimization engine ranks actions by information gain per unit cost and time, ensuring maximum resource efficiency.
              </div>

              {/* Table of Investigations */}
              <div className="overflow-x-auto mt-6">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider border-b border-slate-200">
                      <th className="py-3 px-4 font-semibold">Investigation Action</th>
                      <th className="py-3 px-4 font-semibold">Information Gain</th>
                      <th className="py-3 px-4 font-semibold">Estimated Cost</th>
                      <th className="py-3 px-4 font-semibold">Time</th>
                      <th className="py-3 px-4 font-semibold">Gain per ₹10k</th>
                      <th className="py-3 px-4 font-semibold">Availability</th>
                      <th className="py-3 px-4 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {investigations.map((inv, idx) => (
                      <tr key={inv.id} className={`hover:bg-slate-50/80 transition ${idx === 0 ? 'bg-emerald-50/30' : ''}`}>
                        <td className="py-4 px-4 font-bold text-slate-900 flex items-center gap-2">
                          {idx === 0 && <span className="bg-emerald-600 text-white text-[10px] px-2 py-0.5 rounded font-bold">TOP PICK</span>}
                          {inv.name}
                        </td>
                        <td className="py-4 px-4 font-semibold text-slate-800">{inv.information_gain} bits</td>
                        <td className="py-4 px-4 text-slate-700">₹{inv.cost.toLocaleString()}</td>
                        <td className="py-4 px-4 text-slate-700">{inv.time_days} day(s)</td>
                        <td className="py-4 px-4 font-extrabold text-emerald-700">{inv.gain_per_10k}</td>
                        <td className="py-4 px-4">
                          <span className={`inline-flex px-2.5 py-1 text-xs font-semibold rounded-full ${
                            inv.available ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {inv.available ? 'Available' : 'Unavailable'}
                          </span>
                        </td>
                        <td className="py-4 px-4 text-right">
                          {inv.available ? (
                            <button
                              onClick={() => handleMarkUnavailable(inv.id)}
                              className="bg-red-50 text-red-700 border border-red-200 px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-red-100 transition"
                            >
                              Mark Unavailable
                            </button>
                          ) : (
                            <span className="text-xs text-slate-400 italic">Excluded & Re-ranked</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* PAGE 5: INVESTIGATION TIMELINE AND AUDIT LOG */}
        {activeTab === 'timeline' && (
          <div className="space-y-8">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
              <div className="flex items-center justify-between pb-6 border-b border-slate-100">
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900">Investigation Timeline & Persistent Audit Log</h2>
                  <p className="text-xs text-slate-500">Chronological audit trail distinguishing real observations, agent decisions, and simulated events.</p>
                </div>
                <span className="text-xs bg-slate-100 text-slate-800 px-3 py-1 rounded-full font-semibold">SQLite / Structured Local Storage</span>
              </div>

              <div className="mt-8 relative border-l-2 border-slate-200 ml-4 space-y-8">
                {timeline.map((evt, idx) => (
                  <div key={evt.event_id || idx} className="relative pl-6">
                    <div className="absolute -left-[9px] top-1.5 w-4 h-4 rounded-full bg-emerald-600 border-2 border-white shadow"></div>
                    <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200 shadow-sm">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-slate-500">{evt.event_id}</span>
                          <h3 className="font-bold text-slate-900 text-sm">{evt.event_type}</h3>
                        </div>
                        <span className="text-xs text-slate-400 font-medium">{evt.timestamp}</span>
                      </div>
                      <p className="text-xs text-slate-700 leading-relaxed mb-3">{evt.description}</p>
                      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-200/60 text-[11px]">
                        <span className="bg-blue-50 text-blue-800 px-2 py-0.5 rounded font-semibold border border-blue-200">
                          {evt.evidence}
                        </span>
                        <span className="bg-slate-200/70 text-slate-700 px-2 py-0.5 rounded font-medium">
                          Actor: {evt.responsible_actor}
                        </span>
                        <span className="bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded font-semibold">
                          Status: {evt.approval_status}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* PAGE 6: MITIGATION VERIFICATION */}
        {activeTab === 'verification' && (
          <div className="space-y-8">
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
              <div className="flex items-center justify-between pb-6 border-b border-slate-100">
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900">Mitigation Verification Engine</h2>
                  <p className="text-xs text-slate-500">Evidence-gated case closure rule: Post-rate + uncertainty &lt; Pre-rate - uncertainty.</p>
                </div>
                <span className="text-xs bg-red-100 text-red-800 px-3 py-1 rounded-full font-semibold">SIMULATED DEMONSTRATION DATA</span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-6">
                {/* Inputs */}
                <div className="space-y-4 bg-slate-50 p-6 rounded-2xl border border-slate-200">
                  <h3 className="font-bold text-slate-900 text-sm mb-4">Measurement Parameters</h3>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">Pre-intervention Rate (kg/hr)</label>
                      <input 
                        type="number" 
                        value={preRate} 
                        onChange={(e) => setPreRate(Number(e.target.value))}
                        className="w-full p-2.5 rounded-xl border border-slate-200 text-sm font-semibold bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">Pre Uncertainty (± kg/hr)</label>
                      <input 
                        type="number" 
                        value={preUncertainty} 
                        onChange={(e) => setPreUncertainty(Number(e.target.value))}
                        className="w-full p-2.5 rounded-xl border border-slate-200 text-sm font-semibold bg-white"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">Post-intervention Rate (kg/hr)</label>
                      <input 
                        type="number" 
                        value={postRate} 
                        onChange={(e) => setPostRate(Number(e.target.value))}
                        className="w-full p-2.5 rounded-xl border border-slate-200 text-sm font-semibold bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 mb-1">Post Uncertainty (± kg/hr)</label>
                      <input 
                        type="number" 
                        value={postUncertainty} 
                        onChange={(e) => setPostUncertainty(Number(e.target.value))}
                        className="w-full p-2.5 rounded-xl border border-slate-200 text-sm font-semibold bg-white"
                      />
                    </div>
                  </div>

                  <div className="space-y-2 pt-2">
                    <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={comparable} 
                        onChange={(e) => setComparable(e.target.checked)}
                        className="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4"
                      />
                      <span>Measurement conditions are comparable (wind, pressure, methodology)</span>
                    </label>
                    <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={independent} 
                        onChange={(e) => setIndependent(e.target.checked)}
                        className="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4"
                      />
                      <span>Post-intervention measurement is independently verified (not operator-reported alone)</span>
                    </label>
                  </div>

                  <button
                    onClick={handleEvaluateVerification}
                    className="w-full bg-emerald-600 text-white py-3 rounded-xl text-sm font-semibold hover:bg-emerald-700 transition shadow-sm mt-4 flex items-center justify-center gap-2"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Run Verification Engine
                  </button>
                </div>

                {/* Results Card */}
                <div className="bg-slate-900 text-white p-6 rounded-2xl border border-slate-800 flex flex-col justify-between">
                  <div>
                    <h3 className="font-bold text-slate-300 text-sm mb-4">Verification Assessment Outcome</h3>
                    {verificationResult ? (
                      <div className="space-y-4">
                        <div className={`p-4 rounded-xl border font-extrabold text-center text-lg ${
                          verificationResult.outcome === 'VERIFIED EMISSION REDUCTION' 
                            ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' 
                            : 'bg-red-500/20 text-red-400 border-red-500/40'
                        }`}>
                          {verificationResult.outcome}
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed bg-slate-800/80 p-4 rounded-xl border border-slate-700">
                          {verificationResult.description}
                        </p>
                        <div className="space-y-2 text-xs text-slate-400">
                          <div className="flex justify-between">
                            <span>Pre-intervention Lower Bound:</span>
                            <span className="font-mono text-white">{verificationResult.pre_lower_bound} kg/hr</span>
                          </div>
                          <div className="flex justify-between">
                            <span>Post-intervention Upper Bound:</span>
                            <span className="font-mono text-white">{verificationResult.post_upper_bound} kg/hr</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="h-48 flex items-center justify-center text-center text-xs text-slate-400 italic">
                        Click 'Run Verification Engine' to evaluate mitigation success against rigorous threshold rules.
                      </div>
                    )}
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-800 text-[11px] text-slate-400 italic">
                    Rule enforced: A repair-completion notification alone never closes a case. Independent post-intervention measurements are strictly required.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 border-t border-slate-800 py-6 text-center text-xs">
        <p>PlumeProof — Agentic AI Hackathon 2026 | Team RisaavNivaran, IIT Bombay</p>
        <p className="mt-1 text-slate-500">Every methane plume deserves a timely investigation. Every claimed mitigation outcome must be supported by verifiable evidence.</p>
      </footer>
    </div>
  );
}
