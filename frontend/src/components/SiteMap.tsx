// Leaflet map of the facility: boundary, source zones (coloured by hypothesis), plume markers
// (size ∝ √rate), and an illustrative wind arrow. No external marker images are used.
import { useEffect } from 'react';
import { CircleMarker, MapContainer, Marker, Polygon, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Link } from 'react-router-dom';
import type { CaseSummary, Facility, Observation, Wind } from '../types/api';
import { fmtDate, hypColor, kgh, STATUS_META } from '../lib/format';

interface Props {
  facility: Facility;
  observations: Observation[];
  highlightIds?: string[];
  cases?: CaseSummary[];
  wind?: Wind | null;
  height?: number | string;
  zoom?: number;
}

function windIcon(fromDeg: number): L.DivIcon {
  // Arrow points in the direction the wind blows TO (from + 180°).
  const to = (fromDeg + 180) % 360;
  return L.divIcon({
    className: '',
    iconSize: [64, 64],
    iconAnchor: [32, 32],
    html: `<div style="width:64px;height:64px;display:flex;align-items:center;justify-content:center;">
      <svg width="54" height="54" viewBox="0 0 54 54" style="transform:rotate(${to}deg)">
        <circle cx="27" cy="27" r="25" fill="rgba(15,23,42,0.75)"/>
        <path d="M27 8 L37 26 L30 24 L30 45 L24 45 L24 24 L17 26 Z" fill="#38bdf8"/>
      </svg></div>`,
  });
}

function Recenter({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lng]);
  }, [lat, lng, map]);
  return null;
}

export function SiteMap({ facility, observations, highlightIds = [], cases = [], wind, height = 420, zoom = 15 }: Props) {
  const highlight = new Set(highlightIds);
  const caseStatus = cases[0]?.status;
  const statusHex = caseStatus ? STATUS_META[caseStatus]?.hex ?? '#0f172a' : '#0f172a';
  // Wind arrow sits at the north-west corner of the facility boundary.
  const lats = facility.boundary.map((p) => p[0]);
  const lngs = facility.boundary.map((p) => p[1]);
  const windPos: [number, number] = lats.length ? [Math.max(...lats) + 0.0015, Math.min(...lngs) - 0.0015] : [facility.lat, facility.lng];

  return (
    <div style={{ height }} className="w-full relative z-0" data-testid="site-map">
      <MapContainer center={[facility.lat, facility.lng]} zoom={zoom} style={{ height: '100%', width: '100%', background: '#e2e8f0' }} scrollWheelZoom={false}>
        <Recenter lat={facility.lat} lng={facility.lng} />
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {facility.boundary.length > 0 && (
          <Polygon positions={facility.boundary} pathOptions={{ color: statusHex, weight: 3, fillOpacity: 0.04, dashArray: '6 4' }}>
            <Tooltip sticky>
              {facility.name}
              {caseStatus ? ` · case status: ${STATUS_META[caseStatus]?.label}` : ''} (illustrative boundary)
            </Tooltip>
          </Polygon>
        )}
        {facility.zones.map((z) => (
          <Polygon key={z.id} positions={z.polygon} pathOptions={{ color: hypColor(z.hypothesis_id), weight: 2, fillOpacity: 0.22 }}>
            <Tooltip sticky>{z.name} (illustrative zone)</Tooltip>
          </Polygon>
        ))}
        {observations.map((o) => {
          const r = 6 + Math.sqrt(o.rate_kg_h) / 2.6;
          const hi = highlight.has(o.id);
          return (
            <CircleMarker
              key={`${o.id}-${hi}`}
              center={[o.lat, o.lng]}
              radius={hi ? r * 1.15 : r}
              pathOptions={{
                color: hi ? '#dc2626' : '#991b1b',
                weight: hi ? 4 : 2,
                fillColor: o.label === 'REAL DATA' ? '#ef4444' : '#f59e0b',
                fillOpacity: hi ? 0.6 : 0.4,
              }}
            >
              <Tooltip direction="top" permanent={hi}>
                <strong>{o.plume_label}</strong> · {kgh(o.rate_kg_h)} · {fmtDate(o.date)}
              </Tooltip>
              <Popup>
                <div className="space-y-1 text-xs">
                  <div className="font-bold text-sm">{o.plume_label}</div>
                  <div>{kgh(o.rate_kg_h)} CH₄ · {fmtDate(o.date)}</div>
                  <div>Source: {o.source}</div>
                  <div className="font-bold">{o.label}</div>
                  {o.notes && <div className="text-slate-500">{o.notes}</div>}
                  {o.case_id && (
                    <Link to={`/cases/${o.case_id}`} className="inline-block mt-1 bg-emerald-600 text-white px-2 py-1 rounded font-semibold">
                      Open case {o.case_id}
                    </Link>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
        {wind && (
          <Marker position={windPos} icon={windIcon(wind.from_deg)}>
            <Tooltip direction="right">
              Wind from {Math.round(wind.from_deg)}° at {wind.speed_m_s} m/s: {wind.label}
              {wind.illustrative ? ' (illustrative)' : ''}
            </Tooltip>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
