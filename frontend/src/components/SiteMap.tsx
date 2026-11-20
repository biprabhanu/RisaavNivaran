// Leaflet map of the facility: boundary, source zones (coloured by hypothesis), plume markers
// (marker size scales with √rate), and an illustrative wind arrow. No external marker images are used.
import { useEffect } from 'react';
import { CircleMarker, MapContainer, Marker, Polygon, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Link } from 'react-router-dom';
import type { CaseSummary, Facility, Observation, Wind } from '../types/api';
import { fmtDate, hypColor, hypIds, hypLabel, kgh, STATUS_META } from '../lib/format';

interface Props {
  facility: Facility;
  observations: Observation[];
  highlightIds?: string[];
  cases?: CaseSummary[];
  wind?: Wind | null;
  height?: number | string;
  zoom?: number;
  legend?: boolean;
}

// Light basemap. CARTO Positron now needs an API key, so by default we use OpenStreetMap tiles with a
// light-grey CSS filter (index.css: .pp-light-tiles), which gives the same calm look with no key.
// To use CARTO (or any other tile server), set VITE_MAP_TILE_URL in frontend/.env at build time, e.g.
//   VITE_MAP_TILE_URL=https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?api_key=YOUR_KEY
const CUSTOM_TILES = (import.meta.env.VITE_MAP_TILE_URL as string | undefined) || '';
const TILE_URL = CUSTOM_TILES || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const TILE_ATTRIBUTION = CUSTOM_TILES
  ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function windIcon(fromDeg: number): L.DivIcon {
  // Arrow points in the direction the wind blows TO (from + 180°).
  const to = (fromDeg + 180) % 360;
  return L.divIcon({
    className: '',
    iconSize: [64, 64],
    iconAnchor: [32, 32],
    html: `<div style="width:64px;height:64px;display:flex;align-items:center;justify-content:center;">
      <svg width="54" height="54" viewBox="0 0 54 54" style="transform:rotate(${to}deg)">
        <circle cx="27" cy="27" r="24" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>
        <path d="M27 8 L37 26 L30 24 L30 45 L24 45 L24 24 L17 26 Z" fill="#334155"/>
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

export function SiteMap({ facility, observations, highlightIds = [], cases = [], wind, height = 420, zoom = 15, legend = true }: Props) {
  const highlight = new Set(highlightIds);
  const caseStatus = cases[0]?.status;
  const statusHex = caseStatus ? STATUS_META[caseStatus]?.hex ?? '#0f172a' : '#0f172a';
  // Wind arrow sits at the north-west corner of the facility boundary.
  const lats = facility.boundary.map((p) => p[0]);
  const lngs = facility.boundary.map((p) => p[1]);
  const windPos: [number, number] = lats.length ? [Math.max(...lats) + 0.0015, Math.min(...lngs) - 0.0015] : [facility.lat, facility.lng];

  return (
    <div style={{ height }} className="w-full relative z-0" data-testid="site-map">
      <MapContainer center={[facility.lat, facility.lng]} zoom={zoom} style={{ height: '100%', width: '100%', background: '#f8fafc' }} scrollWheelZoom={false}>
        <Recenter lat={facility.lat} lng={facility.lng} />
        <TileLayer attribution={TILE_ATTRIBUTION} url={TILE_URL} maxZoom={19} className={CUSTOM_TILES ? '' : 'pp-light-tiles'} />
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
                color: hi ? '#0f766e' : '#115e59',
                weight: hi ? 4 : 2,
                fillColor: o.label === 'REAL DATA' ? '#0d9488' : '#94a3b8',
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
                    <Link to={`/cases/${o.case_id}`} className="inline-block mt-1 bg-teal-600 text-white px-2 py-1 rounded font-semibold">
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
      {legend && (
        // Simple legend (bottom-left). Zones and boundary are illustrative; plumes are real Carbon Mapper data.
        <div className="absolute bottom-3 left-3 z-[400] rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs text-slate-700 shadow-sm space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-teal-600/60 border-2 border-teal-800" /> Methane plume (larger = higher rate)
          </div>
          {hypIds().map((h) => (
            <div key={h} className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-sm" style={{ background: hypColor(h), opacity: 0.6 }} /> {hypLabel(h)} zone
            </div>
          ))}
          <div className="flex items-center gap-2">
            <span className="w-3 h-0 border-t-2 border-dashed" style={{ borderColor: statusHex }} /> Site boundary (case status)
          </div>
        </div>
      )}
    </div>
  );
}
