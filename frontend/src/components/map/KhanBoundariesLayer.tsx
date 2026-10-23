import React, { useMemo } from "react";
import { GeoJSON } from "react-leaflet";
import type { PathOptions, Layer, StyleFunction, LeafletMouseEvent } from "leaflet";
import type { Feature, Geometry, GeoJsonObject } from "geojson";
import ppKhansGeoJson from "../../data/boundaries/phnom_penh_khans.json";
import type { KhanStat } from "../../types";

interface KhanBoundariesLayerProps {
  khanStats: KhanStat[];
  selectedKhan?: string;
  onSelectKhan?: (khanName: string) => void;
}

export const KhanBoundariesLayer: React.FC<KhanBoundariesLayerProps> = ({
  khanStats,
  selectedKhan,
  onSelectKhan,
}) => {
  const statsMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const stat of khanStats) {
      map.set((stat.khan_name || "").toLowerCase(), stat.visit_count);
    }
    return map;
  }, [khanStats]);
  // Compute a data signature so React-Leaflet GeoJSON re-mounts whenever live visit data updates
  const dataSignature = useMemo(() => {
    const totalVisits = khanStats.reduce((sum, s) => sum + (s.visit_count || 0), 0);
    const coldZones = khanStats.filter((s) => s.is_cold_zone || s.visit_count === 0).length;
    return `${totalVisits}-${coldZones}`;
  }, [khanStats]);

  const getStyle: StyleFunction = (feature) => {
    const khanName = (feature?.properties?.hrname || "").toLowerCase();
    const visits = statsMap.get(khanName) ?? 0;
    const isSelected = selectedKhan && selectedKhan.toLowerCase() === khanName;

    if (isSelected) {
      return {
        color: "#006B3F",
        weight: 3,
        opacity: 0.95,
        fillColor: "#10b981",
        fillOpacity: 0.18,
      };
    }

    if (visits === 0) {
      return {
        color: "#dc2626",
        weight: 1.5,
        opacity: 0.6,
        fillColor: "#fee2e2",
        fillOpacity: 0.08,
        dashArray: "4, 4",
      };
    }

    return {
      color: "#006B3F",
      weight: 1.2,
      opacity: 0.45,
      fillColor: "#059669",
      fillOpacity: 0.03,
    };
  };

  const onEachFeature = (feature: Feature<Geometry, { hrname?: string }>, layer: Layer) => {
    const khanName = feature.properties?.hrname || "Unknown";
    const visits = statsMap.get(khanName.toLowerCase()) ?? 0;

    const badge =
      visits === 0
        ? '<span style="color:#dc2626;font-weight:600;">0 visits (Cold Zone)</span>'
        : `<span style="color:#006B3F;font-weight:600;">${visits} visits logged</span>`;

    layer.bindTooltip(
      `
      <div style="font-family:'Inter',sans-serif;font-size:12px;padding:4px 8px;">
        <strong style="color:#0f172a;font-size:13px;">Khan ${khanName}</strong><br/>
        ${badge}
      </div>
      `,
      { sticky: true, className: "khan-tooltip" }
    );

    layer.on({
      click: (e: LeafletMouseEvent) => {
        if (e.originalEvent) {
          e.originalEvent.preventDefault?.();
          e.originalEvent.stopPropagation?.();
        }
        if (onSelectKhan) {
          if (selectedKhan && selectedKhan.toLowerCase() === khanName.toLowerCase()) {
            onSelectKhan("all");
          } else {
            onSelectKhan(khanName);
          }
        }
      },
      mouseover: (e) => {
        const l = e.target;
        l.setStyle({ fillOpacity: 0.15, weight: 2 });
      },
      mouseout: (e) => {
        const l = e.target;
        l.setStyle(getStyle(feature));
      },
    });
  };

  return (
    <GeoJSON
      key={`khans-${selectedKhan || "all"}-${dataSignature}`}
      data={ppKhansGeoJson as unknown as GeoJsonObject}
      style={getStyle}
      onEachFeature={onEachFeature as unknown as (feature: Feature<Geometry, unknown>, layer: Layer) => void}
    />
  );
};
