import React from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
const CAMBODIA_BOUNDS: [[number, number], [number, number]] = [
  [9.0, 101.5], // Southwest (Gulf of Thailand / Southern Border)
  [15.5, 108.5], // Northeast (Northern Border with Laos & Vietnam)
];

interface MapCanvasProps {
  children?: React.ReactNode;
  center?: [number, number];
  zoom?: number;
  basemap?: "flatwhite" | "google";
  restrictToCambodia?: boolean;
  showZoomControls?: boolean;
}

export const MapCanvas: React.FC<MapCanvasProps> = ({
  children,
  center = [11.5564, 104.9282], // Phnom Penh Center
  zoom = 12,
  basemap = "google",
  restrictToCambodia = true,
  showZoomControls = false,
}) => {
  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm">
      <MapContainer
        center={center}
        zoom={zoom}
        minZoom={restrictToCambodia ? 7 : 2}
        maxZoom={20}
        maxBounds={restrictToCambodia ? CAMBODIA_BOUNDS : undefined}
        maxBoundsViscosity={1.0}
        scrollWheelZoom={true}
        className="h-full w-full"
        zoomControl={showZoomControls}
      >
        <TileLayer
          attribution='&copy; Google Maps'
          url="https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
          subdomains={["0", "1", "2", "3"]}
          maxZoom={20}
        />
        {children}
      </MapContainer>
    </div>
  );
};
