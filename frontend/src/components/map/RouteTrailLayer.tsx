import React, { useMemo } from "react";
import { Polyline, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import type { RMVisit } from "../../types";

interface RouteTrailLayerProps {
  visits: RMVisit[];
  onSelectVisit?: (visit: RMVisit) => void;
}

export const RouteTrailLayer: React.FC<RouteTrailLayerProps> = ({
  visits,
  onSelectVisit,
}) => {
  // Filter visits with valid coordinates and fan out identical/overlapping stops (~16m)
  const validVisits = useMemo(() => {
    const raw = visits.filter((v) => {
      const lat = Number(v.latitude);
      const lng = Number(v.longitude);
      return !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0;
    });

    const coordCounts = new Map<string, number>();
    return raw.map((v) => {
      const lat = Number(v.latitude);
      const lng = Number(v.longitude);
      const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
      const count = coordCounts.get(key) || 0;
      coordCounts.set(key, count + 1);

      if (count === 0) {
        return { ...v, displayLat: lat, displayLng: lng };
      }

      // Fan out duplicate pins at same venue/mall
      const angle = (count - 1) * 1.57 + 0.78;
      const radius = 0.00015;
      const displayLat = lat + Math.sin(angle) * radius;
      const displayLng = lng + (Math.cos(angle) * radius) / Math.cos((lat * Math.PI) / 180);

      return { ...v, displayLat, displayLng };
    });
  }, [visits]);

  // Coordinate trail for Polyline
  const positions = useMemo<[number, number][]>(() => {
    return validVisits.map((v) => [v.displayLat, v.displayLng]);
  }, [validVisits]);

  const createNumberedIcon = (sequenceNumber: number, isLatest: boolean) => {
    return L.divIcon({
      className: "custom-route-marker",
      html: `
        <div style="
          background: ${isLatest ? "#006B3F" : "#0f172a"};
          color: #ffffff;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          font-weight: 700;
          border: 2px solid #ffffff;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        ">
          ${sequenceNumber}
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
      popupAnchor: [0, -16],
    });
  };

  if (validVisits.length === 0) return null;

  return (
    <>
      {/* Route dashed line */}
      <Polyline
        positions={positions}
        pathOptions={{
          color: "#006B3F",
          weight: 3,
          dashArray: "6, 8",
          opacity: 0.8,
          lineJoin: "round",
        }}
      />

      {/* Numbered Sequence Markers */}
      {validVisits.map((v, index) => {
        const seqNumber = index + 1;
        const isLatest = index === validVisits.length - 1;
        const icon = createNumberedIcon(seqNumber, isLatest);

        return (
          <Marker
            key={`route-visit-${v.visit_id || index}-${v.latitude}`}
            position={[v.displayLat, v.displayLng]}
            icon={icon}
            eventHandlers={{
              click: () => {
                if (onSelectVisit) onSelectVisit(v);
              },
            }}
          >
            <Popup>
              <div className="p-3">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-[11px] font-bold text-emerald-800">
                    Stop #{seqNumber}
                  </span>
                  <span className="text-[11px] text-slate-500 font-medium">
                    {v.report_time ? new Date(v.report_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                </div>
                <h4 className="mt-1 font-display text-sm font-bold text-slate-900">
                  {v.merchant_name || "Unnamed store"}
                </h4>
                <p className="text-xs text-slate-600">
                  {[v.business, v.district_khan ? `Khan ${v.district_khan}` : null]
                    .filter(Boolean)
                    .join(" · ") || "No location detail"}
                </p>
                {v.status && (
                  <div className="mt-2 text-xs">
                    <span className="font-semibold text-slate-700">Status: </span>
                    <span className="text-slate-600">{v.status}</span>
                  </div>
                )}
                {v.remark && (
                  <p className="mt-1 text-xs italic text-slate-500 border-t border-slate-100 pt-1">
                    "{v.remark}"
                  </p>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
};
