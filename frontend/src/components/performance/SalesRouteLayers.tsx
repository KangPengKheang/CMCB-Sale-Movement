import React, { useMemo } from "react";
import { CircleMarker, Marker, Polyline, Tooltip } from "react-leaflet";
import L from "leaflet";
import type { SalesMovementTrack } from "../../types";
import { DropPointPopup } from "./DropPointPopup";

const clock = (value: string) => new Date(value).toLocaleTimeString("en-GB", {
  timeZone: "Asia/Phnom_Penh", hour: "2-digit", minute: "2-digit",
});
const gap = (seconds: number) => seconds < 60 ? `${seconds}s` : seconds < 3600
  ? `${(seconds / 60).toFixed(1)} min` : `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
const distance = (meters: number) => meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(2)} km`;

export function routeColors(color: string) {
  const safe = /^#[0-9a-f]{6}$/i.test(color) ? color : "#0d9488";
  const rgb = [1, 3, 5].map((index) => parseInt(safe.slice(index, index + 2), 16));
  const hex = (channels: number[]) => "#" + channels.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("");
  return {
    point: hex(rgb.map((channel, index) => channel * .74 + [15, 23, 42][index] * .26)),
    line: hex(rgb.map((channel) => channel * .65 + 255 * .35)),
    original: safe,
  };
}

function stopIcon(number: number, color: string, halo: string, last: boolean) {
  return L.divIcon({
    className: "sales-movement-number",
    html: `<div class="sales-stop ${last ? "sales-stop-latest" : ""}" style="--stop-color:${color};--stop-halo:${halo}44"><span>${number}</span></div>`,
    iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -18],
  });
}

function arrowIcon(angle: number, color: string) {
  return L.divIcon({
    className: "sales-movement-direction",
    html: `<svg width="20" height="20" viewBox="0 0 20 20" style="transform:rotate(${angle}deg);filter:drop-shadow(0 1px 2px #fff)"><path d="M10 2L17 16L10 12L3 16Z" fill="${color}" stroke="white" stroke-width="1.5"/></svg>`,
    iconSize: [20, 20], iconAnchor: [10, 10],
  });
}

export function SalesRouteLayers({ track, selected, onSelect, onSelectPoint, popupPointId, replaying = false }: {
  track: SalesMovementTrack; selected: boolean; onSelect: (id: number) => void; replaying?: boolean;
  onSelectPoint: (pointId: number) => void; popupPointId: number | null;
}) {
  const pointIndex = useMemo(() => new Map(track.points.map((point) => [point.id, point])), [track.points]);
  const incoming = useMemo(() => new Map(track.segments.map((segment) => [segment.to_id, segment])), [track.segments]);
  const colors = routeColors(track.color);
  return <>
    {track.segments.map((segment) => {
      const first = pointIndex.get(segment.from_id)!;
      const second = pointIndex.get(segment.to_id)!;
      const positions: [number, number][] = [[first.latitude, first.longitude], [second.latitude, second.longitude]];
      const angle = Math.atan2(
        (second.longitude - first.longitude) * Math.cos((first.latitude + second.latitude) / 2 * Math.PI / 180),
        second.latitude - first.latitude,
      ) * 180 / Math.PI;
      const dashArray = segment.missing_gps_between ? "2 11" : "10 8";
      return <React.Fragment key={`${segment.from_id}-${segment.to_id}`}>
        {selected && <Polyline pane="sales-route-casing" className="sales-trail-selected" positions={positions} interactive={false}
          pathOptions={{ color: "white", weight: 7, opacity: .9, dashArray, lineCap: "round", className: "sales-trail-selected" }} />}
        <Polyline pane="sales-route-lines" className={selected ? "sales-trail sales-trail-selected" : "sales-trail"} positions={positions}
          pathOptions={{ color: colors.line, weight: selected ? 3.5 : 2.2, opacity: selected ? .9 : .65,
            dashArray, lineCap: "round", className: selected ? "sales-trail sales-trail-selected" : "sales-trail" }}
          eventHandlers={{ click: () => onSelect(track.sender_id) }}>
          <Tooltip sticky><div className="text-xs">
            <strong style={{ color: colors.point }}>{track.sender_name}</strong><br />
            Visit {segment.from_drop_number} → {segment.to_drop_number} · {clock(segment.from_time)} → {clock(segment.to_time)}<br />
            {gap(segment.gap_seconds)} between GPS drops · {distance(segment.distance_meters)} straight line
            {segment.missing_gps_between > 0 && <><br />{segment.missing_gps_between} intervening report(s) without GPS</>}
          </div></Tooltip>
        </Polyline>
        {selected && segment.distance_meters > 1 && <Marker pane="sales-route-directions"
          position={[(first.latitude + second.latitude) / 2, (first.longitude + second.longitude) / 2]}
          icon={arrowIcon(angle, colors.point)} interactive={false} />}
      </React.Fragment>;
    })}
    {track.points.map((point, index) => {
      const last = index === track.points.length - 1;
      const start = index === 0;
      const segment = incoming.get(point.id);
      const label = replaying && last ? "Replay position" : last ? "Latest GPS drop" : start ? "First GPS drop" : "Reported GPS location";
      const content = <DropPointPopup point={point} senderName={track.sender_name} color={colors.original}
        label={label} gpsGap={segment?.gap_seconds ?? null} autoOpen={popupPointId === point.id} />;
      return selected
        ? <Marker key={point.id} pane="sales-selected-points" position={[point.latitude, point.longitude]}
            icon={stopIcon(point.drop_number, colors.point, colors.original, last)} zIndexOffset={last ? 200 : start ? 100 : 0}
            eventHandlers={{ click: () => onSelectPoint(point.id) }}>
            {(start || last) && <Tooltip permanent direction="top" offset={[0, -20]} className="sales-stop-label">
              {last ? replaying ? "REPLAY" : "LATEST" : "START"} · {clock(point.submitted_at)}
            </Tooltip>}
            {content}
          </Marker>
        : <CircleMarker key={point.id} pane="sales-route-points" className="sales-route-dot" center={[point.latitude, point.longitude]} radius={6}
            pathOptions={{ color: "white", weight: 2, fillColor: colors.point, fillOpacity: 1, className: "sales-route-dot" }}
            eventHandlers={{ click: () => onSelectPoint(point.id) }}>
            <Tooltip>{track.sender_name} · Visit {point.drop_number} · {clock(point.submitted_at)}</Tooltip>
            {content}
          </CircleMarker>;
    })}
  </>;
}
