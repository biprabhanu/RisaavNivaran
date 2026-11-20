// Routes + app bootstrap (health check, metadata). HashRouter means the server only ever
// needs to serve index.html; every page lives behind "#/...".
import { useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { api } from './lib/api';
import { registerMeta } from './lib/format';
import { setState, useAppState } from './lib/store';
import Landing from './pages/Landing';
import Replay from './pages/Replay';
import MapPage from './pages/MapPage';
import CaseDetailPage from './pages/CaseDetail';
import Planner from './pages/Planner';
import Approvals from './pages/Approvals';
import Verification from './pages/Verification';
import Audit from './pages/Audit';
import Evaluation from './pages/Evaluation';
import WhatIf from './pages/WhatIf';
import DataSources from './pages/DataSources';

function useBootstrap() {
  const { offline } = useAppState();
  useEffect(() => {
    api.health().then((h) => setState({ health: h })).catch(() => undefined);
    api
      .meta()
      .then((m) => {
        registerMeta(m);
        setState({ meta: m });
      })
      .catch(() => undefined);
  }, [offline]);
}

export default function App() {
  useBootstrap();
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/replay" element={<Replay />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/cases/:id" element={<CaseDetailPage />} />
          <Route path="/cases" element={<Navigate to="/cases/KJ-2025-02" replace />} />
          <Route path="/planner" element={<Planner />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/verification" element={<Verification />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/evaluation" element={<Evaluation />} />
          <Route path="/whatif" element={<WhatIf />} />
          <Route path="/data" element={<DataSources />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </HashRouter>
  );
}
