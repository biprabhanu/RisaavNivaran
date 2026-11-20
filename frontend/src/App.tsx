// Routes + app bootstrap (health check, metadata). HashRouter means the server only ever
// needs to serve index.html; every page lives behind "#/...".
import { lazy, Suspense, useEffect } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import PageLoader from './components/PageLoader';
import { api } from './lib/api';
import { registerMeta } from './lib/format';
import { setState, useAppState } from './lib/store';
// Landing is loaded eagerly (it is the first screen). Every other page is code-split, so
// Leaflet and Recharts only download when a page that needs them is opened.
import Landing from './pages/Landing';
const Replay = lazy(() => import('./pages/Replay'));
const MapPage = lazy(() => import('./pages/MapPage'));
const CaseDetailPage = lazy(() => import('./pages/CaseDetail'));
const Planner = lazy(() => import('./pages/Planner'));
const Approvals = lazy(() => import('./pages/Approvals'));
const Verification = lazy(() => import('./pages/Verification'));
const Audit = lazy(() => import('./pages/Audit'));
const Evaluation = lazy(() => import('./pages/Evaluation'));
const WhatIf = lazy(() => import('./pages/WhatIf'));
const DataSources = lazy(() => import('./pages/DataSources'));

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
        <Suspense fallback={<PageLoader />}>
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
        </Suspense>
      </Layout>
    </HashRouter>
  );
}
