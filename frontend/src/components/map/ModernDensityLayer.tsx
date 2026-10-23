import React, { useMemo } from "react";
import { Polygon, CircleMarker, Marker, Tooltip, Popup } from "react-leaflet";
import L from "leaflet";
import type { Merchant, RawVisitReport } from "../../types";

interface HexBinData {
  key: string;
  centerLat: number;
  centerLng: number;
  polygonCoords: [number, number][];
  visits: number;
  uniqueStores: number;
  cmcbSigned: number;
  district: string;
  sampleStores: string[];
}

interface ModernDensityLayerProps {
  reports: RawVisitReport[];
  merchants: Merchant[];
  mode?: "hexbin" | "bubbles";
  redThreshold?: number; // threshold for crimson red hotspot (default 20)
  onSelectCluster?: (bin: HexBinData) => void;
}

// Hexagon radius: ~400m
const HEX_RADIUS_KM = 0.42;

function getHexPolygon(centerLat: number, centerLng: number, radiusKm: number): [number, number][] {
  const coords: [number, number][] = [];
  const latRadius = radiusKm / 111.32;
  const lngRadius = radiusKm / (111.32 * Math.cos((centerLat * Math.PI) / 180));

  for (let i = 0; i < 6; i++) {
    const angle = ((i * 60 - 30) * Math.PI) / 180;
    coords.push([
      centerLat + latRadius * Math.sin(angle),
      centerLng + lngRadius * Math.cos(angle),
    ]);
  }
  return coords;
}

export const ModernDensityLayer: React.FC<ModernDensityLayerProps> = ({
  reports,
  merchants,
  mode = "hexbin",
  redThreshold = 20,
  onSelectCluster,
}) => {
  // Aggregate into hexagonal spatial bins
  const hexBins = useMemo<HexBinData[]>(() => {
    const HEX_RADIUS_DEG = HEX_RADIUS_KM / 111.32;
    const binsMap = new Map<
      string,
      {
        key: string;
        lat: number;
        lng: number;
        visits: number;
        storeIds: Set<number | string>;
        cmcbCount: number;
        district: string;
        stores: string[];
      }
    >();

    // Use reports or merchants
    const items = reports && reports.length > 0 ? reports : merchants;

    for (const item of items) {
      const lat = item.latitude;
      const lng = item.longitude;
      if (!lat || !lng || isNaN(lat) || isNaN(lng) || lat === 0) continue;

      // Regular hex coordinates mapping
      const cosLat = Math.cos((lat * Math.PI) / 180);
      const q = Math.round((lng * cosLat) / (HEX_RADIUS_DEG * Math.sqrt(3)));
      const r = Math.round(lat / (HEX_RADIUS_DEG * 1.5));
      const centerLat = r * (HEX_RADIUS_DEG * 1.5);
      const centerLng = (q * (HEX_RADIUS_DEG * Math.sqrt(3))) / cosLat;
      const key = `${q},${r}`;

      const district =
        ("district_khan" in item && typeof item.district_khan === "string" && item.district_khan) ||
        ("khan_name" in item && typeof item.khan_name === "string" && item.khan_name) ||
        "Phnom Penh";

      const bin = binsMap.get(key) || {
        key,
        lat: centerLat,
        lng: centerLng,
        visits: 0,
        storeIds: new Set<number | string>(),
        cmcbCount: 0,
        district,
        stores: [] as string[],
      };

      const visitIncrement = "total_visits" in item ? (item.total_visits || 1) : 1;
      bin.visits += visitIncrement;

      const mId = "merchant_id" in item ? (item.merchant_id || item.id) : item.id;
      if (mId) bin.storeIds.add(mId);

      const isCMCB =
        ("has_cmcb" in item && item.has_cmcb === 1) ||
        ("khqr_stage" in item && item.khqr_stage === "CONVERTED") ||
        ("current_khqr_stage" in item && item.current_khqr_stage === "CONVERTED");
      if (isCMCB) bin.cmcbCount += 1;

      const sName =
        ("merchant_name" in item && typeof item.merchant_name === "string" && item.merchant_name) ||
        ("canonical_name" in item && typeof item.canonical_name === "string" && item.canonical_name) ||
        "";
      if (sName && bin.stores.length < 5) bin.stores.push(sName);

      binsMap.set(key, bin);
    }

    return Array.from(binsMap.values()).map((b) => ({
      key: b.key,
      centerLat: b.lat,
      centerLng: b.lng,
      polygonCoords: getHexPolygon(b.lat, b.lng, HEX_RADIUS_KM),
      visits: b.visits,
      uniqueStores: Math.max(b.storeIds.size, 1),
      cmcbSigned: b.cmcbCount,
      district: b.district,
      sampleStores: b.stores,
    }));
  }, [reports, merchants]);

  // Color & Opacity styling based on state-of-the-art tiering
  const getStyleForVisits = (visits: number) => {
    if (visits >= redThreshold) {
      // Mega Hotspot
      return {
        fillColor: "#dc2626", // Luminous Crimson
        fillOpacity: 0.62,
        strokeColor: "#991b1b",
        strokeWidth: 2.0,
      };
    }
    if (visits >= 14) {
      // High Density Corridor
      return {
        fillColor: "#ea580c", // Vibrant Orange
        fillOpacity: 0.52,
        strokeColor: "#c2410c",
        strokeWidth: 1.6,
      };
    }
    if (visits >= 8) {
      // Moderate Density
      return {
        fillColor: "#eab308", // Amber Gold
        fillOpacity: 0.42,
        strokeColor: "#ca8a04",
        strokeWidth: 1.3,
      };
    }
    if (visits >= 4) {
      // Emerging Cluster
      return {
        fillColor: "#10b981", // Emerald Green
        fillOpacity: 0.32,
        strokeColor: "#059669",
        strokeWidth: 1.0,
      };
    }
    // Low Density / Scatter
    return {
      fillColor: "#0284c7", // Electric Sky Blue
      fillOpacity: 0.22,
      strokeColor: "#0369a1",
      strokeWidth: 0.8,
    };
  };

  const createBadgeIcon = (count: number, isHotspot: boolean) => {
    const bg = isHotspot ? "#dc2626" : "#0f172a";
    return L.divIcon({
      className: "hex-count-badge",
      html: `
        <div style="
          background: ${bg};
          color: #ffffff;
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px;
          font-weight: 700;
          padding: 1px 5px;
          border-radius: 9999px;
          border: 1.5px solid #ffffff;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          white-space: nowrap;
        ">
          ${count}
        </div>
      `,
      iconSize: [26, 18],
      iconAnchor: [13, 9],
    });
  };

  return (
    <>
      {mode === "hexbin" &&
        hexBins.map((bin) => {
          const style = getStyleForVisits(bin.visits);
          const isHotspot = bin.visits >= redThreshold;

          return (
            <React.Fragment key={`hex-${bin.key}`}>
              <Polygon
                positions={bin.polygonCoords}
                pathOptions={{
                  fillColor: style.fillColor,
                  fillOpacity: style.fillOpacity,
                  color: style.strokeColor,
                  weight: style.strokeWidth,
                  lineJoin: "round",
                }}
                eventHandlers={{
                  click: () => onSelectCluster && onSelectCluster(bin),
                  mouseover: (e) => {
                    const l = e.target;
                    l.setStyle({ fillOpacity: style.fillOpacity + 0.2, weight: style.strokeWidth + 1 });
                  },
                  mouseout: (e) => {
                    const l = e.target;
                    l.setStyle({ fillOpacity: style.fillOpacity, weight: style.strokeWidth });
                  },
                }}
              >
                <Tooltip direction="top" offset={[0, -10]}>
                  <div className="p-1 font-sans text-xs">
                    <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-1">
                      <strong className="text-slate-900">Khan {bin.district}</strong>
                      <span className="rounded bg-slate-900 px-1.5 py-0.2 font-mono text-[10px] font-bold text-white">
                        {bin.visits} visits
                      </span>
                    </div>
                    <div className="mt-1 text-slate-600">
                      <span>Stores: <strong>{bin.uniqueStores}</strong></span>
                      <span className="mx-1.5">·</span>
                      <span className="text-emerald-700 font-semibold">CMCB Signed: <strong>{bin.cmcbSigned}</strong></span>
                    </div>
                    {bin.sampleStores.length > 0 && (
                      <p className="mt-1 text-[10px] italic text-slate-400 truncate max-w-[200px]">
                        e.g. {bin.sampleStores.join(", ")}
                      </p>
                    )}
                  </div>
                </Tooltip>
              </Polygon>

              {/* Number Badge for significant clusters (>= 8 visits) */}
              {bin.visits >= 8 && (
                <Marker
                  position={[bin.centerLat, bin.centerLng]}
                  icon={createBadgeIcon(bin.visits, isHotspot)}
                  interactive={false}
                />
              )}
            </React.Fragment>
          );
        })}

      {mode === "bubbles" &&
        hexBins.map((bin) => {
          const style = getStyleForVisits(bin.visits);
          const isHotspot = bin.visits >= redThreshold;
          const radius = Math.min(10 + Math.sqrt(bin.visits) * 4, 38);

          return (
            <React.Fragment key={`bubble-${bin.key}`}>
              {/* Outer Glow Ring */}
              <CircleMarker
                center={[bin.centerLat, bin.centerLng]}
                radius={radius + 8}
                pathOptions={{
                  fillColor: style.fillColor,
                  fillOpacity: 0.15,
                  stroke: false,
                }}
              />

              {/* Core Node */}
              <CircleMarker
                center={[bin.centerLat, bin.centerLng]}
                radius={radius}
                pathOptions={{
                  fillColor: style.fillColor,
                  fillOpacity: style.fillOpacity + 0.1,
                  color: "#ffffff",
                  weight: 2,
                }}
                eventHandlers={{
                  click: () => onSelectCluster && onSelectCluster(bin),
                }}
              >
                <Tooltip direction="top" offset={[0, -radius]}>
                  <div className="p-1 font-sans text-xs">
                    <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-1">
                      <strong className="text-slate-900">Khan {bin.district}</strong>
                      <span className="rounded bg-slate-900 px-1.5 py-0.2 font-mono text-[10px] font-bold text-white">
                        {bin.visits} visits
                      </span>
                    </div>
                    <div className="mt-1 text-slate-600">
                      <span>Stores: <strong>{bin.uniqueStores}</strong></span>
                      <span className="mx-1.5">·</span>
                      <span className="text-emerald-700 font-semibold">CMCB Signed: <strong>{bin.cmcbSigned}</strong></span>
                    </div>
                  </div>
                </Tooltip>
              </CircleMarker>

              {/* Number Badge for significant clusters (>= 8 visits) */}
              {bin.visits >= 8 && (
                <Marker
                  position={[bin.centerLat, bin.centerLng]}
                  icon={createBadgeIcon(bin.visits, isHotspot)}
                  interactive={false}
                />
              )}
            </React.Fragment>
          );
        })}
    </>
  );
};
