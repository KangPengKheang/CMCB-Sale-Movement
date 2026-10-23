import React, { useState, useMemo, useRef } from "react";
import {
  Search,
  MapPin,
  List,
  Map as MapIcon,
  X,
  Navigation,
  ZoomIn,
  ZoomOut,
  Layers,
  ArrowLeft,
  Store,
  Check,
  Phone,
  Clock,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { useSales } from "../../context/SalesContext";
import type { SalesStoreItem } from "../../types";

const CAMBODIA_BOUNDS: [[number, number], [number, number]] = [
  [9.0, 101.5], // Southwest (Gulf of Thailand / Southern Border)
  [15.5, 108.5], // Northeast (Northern Border with Laos & Vietnam)
];

// Stable module-scope identity — inline arrays here would re-fire flyTo on every render
const PHNOM_PENH_CENTER: [number, number] = [11.5564, 104.9282];
const FOCUS_ZOOM = 16;

// ============================================================================
// 1. PREMIUM TEARDROP STORE PIN (Matching Google Maps / CMCB Admin)
// ============================================================================
const createTeardropPin = ({
  store,
  isSelected,
  showLabel,
  isSearchMatch,
}: {
  store: SalesStoreItem;
  isSelected: boolean;
  showLabel: boolean;
  isSearchMatch: boolean;
}) => {
  const isSigned = Boolean(
    store.is_signed ?? (store.is_onboarded || store.stage === "CONVERTED" || store.stage === "EXISTING" || store.has_cmcb)
  );
  const daysSinceVisit = store.days_since_last_visit ?? 999;
  const isDormant = !isSigned && (store.status_category === "UNSIGNED_DORMANT" || daysSinceVisit > 14);

  // Colors:
  // 1. Signed: CMCB Signature Forest Green
  // 2. Unsigned Dormant (> 14d): Slate/Cool Gray with pulsing Aura
  // 3. Unsigned Recent (<= 14d): Light Red
  const pinBg = isSigned
    ? "linear-gradient(135deg, #008751 0%, #006B3F 100%)" // CMCB Signature Forest Green
    : isDormant
    ? "linear-gradient(135deg, #64748b 0%, #475569 100%)" // Cool Slate Gray
    : "linear-gradient(135deg, #f87171 0%, #ef4444 100%)"; // Light Red

  const ringColor = isSelected ? "#f59e0b" : "#ffffff";
  const ringWidth = isSelected ? "3px" : "2px";
  const pinScale = isSelected ? 1.25 : 1.0;

  // Center Icon Glyph
  const centerGlyph = isSigned
    ? `<svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"></path></svg>`
    : isDormant
    ? `<svg class="w-3.5 h-3.5 text-slate-100" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`
    : `<svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path></svg>`;
  // Pulsing cold aura for unsigned stores ignored for > 14 days
  const auraHtml = isDormant
    ? `<span class="absolute inline-flex rounded-full opacity-60 animate-ping" style="width: 34px; height: 34px; top: -3px; left: -3px; background-color: #94a3b8; animation-duration: 2.8s; z-index: 0; pointer-events: none;"></span>`
    : "";

  // Multiple visits count badge (matches Admin StoreMarkersLayer)
  const visits = store.total_visits || 1;
  const visitBadgeHtml =
    visits >= 2
      ? `<span style="
          position: absolute;
          top: -5px;
          right: -5px;
          background: #0f172a;
          color: #ffffff;
          border: 1.5px solid #ffffff;
          font-family: 'JetBrains Mono', monospace;
          font-size: 9px;
          font-weight: 800;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 4px rgba(0,0,0,0.25);
          z-index: 10;
        ">${visits}</span>`
      : "";

  // Floating store name label above pin
  const displayName = store.name.length > 20 ? store.name.slice(0, 18) + "…" : store.name;
  const labelHtml = showLabel
    ? `<div style="
        position: absolute;
        bottom: 34px;
        left: 50%;
        transform: translateX(-50%);
        white-space: nowrap;
        background: #ffffff;
        border: 1px solid ${isSelected ? "#006B3F" : "#cbd5e1"};
        color: ${isSelected ? "#004226" : "#0f172a"};
        font-family: system-ui, sans-serif;
        font-size: 10px;
        font-weight: 800;
        padding: 2px 7px;
        border-radius: 6px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.12);
        pointer-events: none;
        ${isSearchMatch ? "border-color: #006B3F; background: #f0fdf4;" : ""}
      ">${displayName}</div>`
    : "";

  return L.divIcon({
    className: "premium-teardrop-pin",
    html: `
      <div style="position: relative; width: 30px; height: 36px; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; transform: scale(${pinScale}); transition: transform 0.2s ease;">
        ${labelHtml}
        ${auraHtml}
        
        <!-- Teardrop Pin -->
        <div style="position: relative; width: 28px; height: 28px; z-index: 1;">
          <!-- 45-degree rotated square forming teardrop point -->
          <div style="
            position: absolute;
            top: 0;
            left: 0;
            width: 28px;
            height: 28px;
            background: ${pinBg};
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            border: ${ringWidth} solid ${ringColor};
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
          "></div>
          
          <!-- Un-rotated Icon Content in Center of Head -->
          <div style="
            position: absolute;
            top: 2px;
            left: 2px;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2;
          ">
            ${centerGlyph}
          </div>

          ${visitBadgeHtml}
        </div>

        <!-- Soft Ground Shadow Ellipse -->
        <div style="
          width: 12px;
          height: 4px;
          background: rgba(15, 23, 42, 0.35);
          border-radius: 50%;
          filter: blur(1px);
          margin-top: 1px;
        "></div>
      </div>
    `,
    iconSize: [30, 36],
    iconAnchor: [15, 36],
    popupAnchor: [0, -36],
  });
};

// ============================================================================
// 2. SLEEK CLUSTER BUBBLE PIN (Matching Apple Maps / Airbnb)
// ============================================================================
const createClusterBubble = (count: number, signedCount: number) => {
  // If cluster has any CMCB signed stores, highlight with emerald glow
  const hasSigned = signedCount > 0;
  const bubbleBg = hasSigned
    ? "linear-gradient(135deg, #008751 0%, #006B3F 100%)"
    : "linear-gradient(135deg, #f87171 0%, #ef4444 100%)";

  const size = count >= 50 ? 44 : count >= 20 ? 38 : 34;

  return L.divIcon({
    className: "cluster-bubble-pin",
    html: `
      <div style="
        width: ${size}px;
        height: ${size}px;
        display: flex;
        align-items: center;
        justify-content: center;
        position: relative;
        cursor: pointer;
        transform: translate(-50%, -50%);
      ">
        <!-- Subtle Pulse Ring -->
        <span class="absolute inline-flex h-full w-full rounded-full opacity-40 animate-ping" style="background-color: ${hasSigned ? "#10b981" : "#64748b"}; animation-duration: 2.5s;"></span>
        
        <!-- Bubble Body -->
        <div style="
          position: relative;
          width: ${size}px;
          height: ${size}px;
          background: ${bubbleBg};
          border: 2.5px solid #ffffff;
          border-radius: 50%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          box-shadow: 0 6px 14px rgba(0, 0, 0, 0.28), 0 2px 4px rgba(0, 0, 0, 0.15);
          color: #ffffff;
          font-family: 'Space Grotesk', system-ui, sans-serif;
          font-weight: 800;
          font-size: ${count >= 50 ? "13px" : "11px"};
          line-height: 1;
        ">
          <span>${count}</span>
          ${hasSigned ? `<span style="font-size: 8px; font-weight: 700; color: #a7f3d0; margin-top: 1px;">CMCB</span>` : ""}
        </div>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

// ============================================================================
// 3. MAP CONTROLLER HELPER
// ============================================================================
const MapController: React.FC<{
  focusId: number | null;
  focusLat?: number;
  focusLng?: number;
  triggerCenter: number;
  zoomTarget: { zoom: number; count: number } | null;
  onViewportChange: (bounds: L.LatLngBounds, zoom: number) => void;
}> = ({ focusId, focusLat, focusLng, triggerCenter, zoomTarget, onViewportChange }) => {
  const map = useMap();
  const lastFocusIdRef = useRef<number | null>(null);

  useMapEvents({
    moveend: () => onViewportChange(map.getBounds().pad(0.15), map.getZoom()),
    zoomend: () => onViewportChange(map.getBounds().pad(0.15), map.getZoom()),
  });

  React.useEffect(() => {
    onViewportChange(map.getBounds().pad(0.15), map.getZoom());
  }, [map, onViewportChange]);

  // Fly to a store only when the selected store actually changes.
  // Guarding on focusId (a primitive) stops this from re-firing on every
  // re-render, which previously hijacked zoom/pan and caused shaking.
  React.useEffect(() => {
    if (focusId == null) {
      lastFocusIdRef.current = null;
      return;
    }
    if (lastFocusIdRef.current === focusId) return;
    if (focusLat == null || focusLng == null) return;

    lastFocusIdRef.current = focusId;
    // Never zoom out on focus — keep the user's closer zoom if they are already in
    map.flyTo([focusLat, focusLng], Math.max(map.getZoom(), FOCUS_ZOOM), {
      duration: 0.7,
    });
  }, [focusId, focusLat, focusLng, map]);

  // Recenter button — triggerCenter only changes on explicit tap
  React.useEffect(() => {
    if (triggerCenter > 0) {
      map.flyTo(PHNOM_PENH_CENTER, 13, { duration: 0.8 });
    }
  }, [triggerCenter, map]);

  React.useEffect(() => {
    if (zoomTarget && zoomTarget.count > 0) {
      map.flyTo(map.getCenter(), zoomTarget.zoom, { duration: 0.6 });
    }
  }, [zoomTarget, map]);

  return null;
};

// ============================================================================
// 4. MAIN STORE MAP VIEW
// ============================================================================
export const SalesStoreMapView: React.FC = () => {
  const {
    storeMapData,
    mapSearch,
    setMapSearch,
    mapKhan,
    setMapKhan,
    mapStage,
    setMapStage,
    mapOwner,
    setMapOwner,
    selectedStore,
    setSelectedStore,
    openMerchantDetail,
  } = useSales();

  const [mobileViewMode, setMobileViewMode] = useState<"map" | "list">("map");
  const [recenterCount, setRecenterCount] = useState(0);
  const [currentZoom, setCurrentZoom] = useState<number>(13);
  const [viewportBounds, setViewportBounds] = useState<L.LatLngBounds | null>(null);
  const [zoomTarget, setZoomTarget] = useState<{ zoom: number; count: number } | null>(null);

  // Earlier visits only — the most recent visit is already surfaced in the sheet header
  const previousVisits = useMemo(() => {
    const history = selectedStore?.visit_history ?? [];
    return history.slice(1);
  }, [selectedStore]);

  // =========================================================================
  // BOTTOM SHEET GESTURE (Google Maps style drag up/down between detents)
  // =========================================================================
  const [viewportH, setViewportH] = useState<number>(() =>
    typeof window === "undefined" ? 800 : window.innerHeight
  );
  const [isMobileSheet, setIsMobileSheet] = useState<boolean>(() =>
    typeof window === "undefined" ? true : window.innerWidth < 1024
  );
  const [detentIndex, setDetentIndex] = useState(1);
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const [isDraggingSheet, setIsDraggingSheet] = useState(false);
  const gestureRef = useRef<{
    startY: number;
    startHeight: number;
    lastY: number;
    lastT: number;
    vy: number;
    moved: number;
    startedAt: number;
  } | null>(null);

  React.useEffect(() => {
    const onResize = () => {
      setViewportH(window.innerHeight);
      setIsMobileSheet(window.innerWidth < 1024);
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
  }, []);

  // Three detents, Google Maps style: minimized → default → maximized
  const sheetDetents = useMemo(
    () => [
      Math.round(viewportH * 0.24),
      Math.round(viewportH * 0.36),
      Math.round(viewportH * 0.88),
    ],
    [viewportH]
  );
  const minDetentH = sheetDetents[0];
  const maxDetentH = sheetDetents[sheetDetents.length - 1];
  const sheetHeightPx = dragHeight ?? sheetDetents[detentIndex];

  // Every freshly opened store starts at the default detent
  React.useEffect(() => {
    setDetentIndex(1);
    setDragHeight(null);
    setIsDraggingSheet(false);
    gestureRef.current = null;
  }, [selectedStore?.id]);

  const onSheetPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isMobileSheet) return;
    // Never hijack taps meant for buttons/links/inputs
    if ((e.target as HTMLElement).closest("button, a, input, select, textarea")) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    gestureRef.current = {
      startY: e.clientY,
      startHeight: sheetHeightPx,
      lastY: e.clientY,
      lastT: performance.now(),
      vy: 0,
      moved: 0,
      startedAt: performance.now(),
    };
    setIsDraggingSheet(true);
  };

  const onSheetPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const g = gestureRef.current;
    if (!g) return;
    const now = performance.now();
    const dt = Math.max(1, now - g.lastT);
    g.vy = (e.clientY - g.lastY) / dt; // px/ms, positive = downward
    g.lastY = e.clientY;
    g.lastT = now;
    g.moved = Math.max(g.moved, Math.abs(e.clientY - g.startY));

    // Dragging up grows the sheet, down shrinks it — clamped to the detent range
    const next = Math.max(minDetentH, Math.min(maxDetentH, g.startHeight + (g.startY - e.clientY)));
    setDragHeight(next);
  };

  const onSheetPointerUp = () => {
    const g = gestureRef.current;
    if (!g) return;
    gestureRef.current = null;
    setIsDraggingSheet(false);

    const elapsed = performance.now() - g.startedAt;

    // A tap (no meaningful movement) steps up to the next detent, wrapping around
    if (g.moved < 6 && elapsed < 300) {
      setDragHeight(null);
      setDetentIndex((prev) => (prev + 1) % sheetDetents.length);
      return;
    }

    // Sliding snaps to the nearest detent and NEVER closes the sheet.
    // Closing is always an explicit action via the X button.
    let nearest = 0;
    for (let i = 1; i < sheetDetents.length; i++) {
      if (
        Math.abs(sheetDetents[i] - sheetHeightPx) <
        Math.abs(sheetDetents[nearest] - sheetHeightPx)
      ) {
        nearest = i;
      }
    }
    setDragHeight(null);
    setDetentIndex(nearest);
  };

  const handleViewportChange = React.useCallback((bounds: L.LatLngBounds, zoom: number) => {
    setViewportBounds(bounds);
    setCurrentZoom(zoom);
  }, []);
  const stores = storeMapData?.stores || [];
  const totalInView = storeMapData?.total_stores_in_view || 0;

  // Search evaluation
  const hasSearch = Boolean(mapSearch.trim());
  const searchLower = mapSearch.toLowerCase().trim();

  // =========================================================================
  // 1. VIEWPORT CULLING: Only retain stores inside current phone screen (+15%)
  // Eliminates 90% of DOM nodes, maintaining 60 FPS drag performance
  // =========================================================================
  const inViewStores = useMemo(() => {
    if (!viewportBounds) return stores.slice(0, 80);

    return stores.filter((s) => {
      if (selectedStore?.id === s.id) return true;
      if (hasSearch && (
        s.name.toLowerCase().includes(searchLower) ||
        s.phone.toLowerCase().includes(searchLower) ||
        s.address.toLowerCase().includes(searchLower)
      )) {
        return true;
      }
      return viewportBounds.contains([s.latitude, s.longitude]);
    });
  }, [stores, viewportBounds, selectedStore, hasSearch, searchLower]);

  // =========================================================================
  // 2. SPATIAL CLUSTERING: Up to Zoom 15, group nearby stores into count bubbles
  // At Zoom >= 16 (block level) or during active search, unpack to pins!
  // =========================================================================
  const { clusters, individualPins } = useMemo(() => {
    if (currentZoom >= 16 || hasSearch) {
      return { clusters: [], individualPins: inViewStores };
    }

    // Dynamic grid size per zoom level
    const gridSize =
      currentZoom <= 10
        ? 0.05
        : currentZoom <= 12
        ? 0.02
        : currentZoom <= 13
        ? 0.01
        : currentZoom <= 14
        ? 0.005
        : 0.0025;
    const gridMap = new Map<
      string,
      {
        centerLat: number;
        centerLng: number;
        stores: SalesStoreItem[];
        signedCount: number;
      }
    >();

    const unclustered: SalesStoreItem[] = [];

    inViewStores.forEach((s) => {
      const gridX = Math.floor(s.longitude / gridSize);
      const gridY = Math.floor(s.latitude / gridSize);
      const key = `${gridX}_${gridY}`;

      const isSigned = s.stage === "CONVERTED" || s.stage === "EXISTING";

      const bucket = gridMap.get(key);
      if (bucket) {
        bucket.stores.push(s);
        if (isSigned) bucket.signedCount += 1;
      } else {
        gridMap.set(key, {
          centerLat: s.latitude,
          centerLng: s.longitude,
          stores: [s],
          signedCount: isSigned ? 1 : 0,
        });
      }
    });

    const clusterList: Array<{
      key: string;
      lat: number;
      lng: number;
      count: number;
      signedCount: number;
    }> = [];

    gridMap.forEach((bucket, key) => {
      // If only 1 store in this bucket, show as an individual teardrop pin
      if (bucket.stores.length === 1) {
        unclustered.push(bucket.stores[0]);
      } else {
        // Average coordinates for the cluster center
        const avgLat = bucket.stores.reduce((acc, s) => acc + s.latitude, 0) / bucket.stores.length;
        const avgLng = bucket.stores.reduce((acc, s) => acc + s.longitude, 0) / bucket.stores.length;
        clusterList.push({
          key,
          lat: avgLat,
          lng: avgLng,
          count: bucket.stores.length,
          signedCount: bucket.signedCount,
        });
      }
    });

    return { clusters: clusterList, individualPins: unclustered };
  }, [inViewStores, currentZoom, hasSearch]);

  // Quick zoom toggle button (Street View vs City Overview)
  const handleToggleZoomTier = () => {
    if (currentZoom < 15) {
      setZoomTarget((prev) => ({ zoom: 16, count: (prev?.count || 0) + 1 }));
    } else {
      setZoomTarget((prev) => ({ zoom: 12, count: (prev?.count || 0) + 1 }));
    }
  };

  return (
    <div className="relative flex-1 w-full h-full overflow-hidden bg-slate-100 select-none">
      {/* =================================================================== */}
      {/* 1. FULLSCREEN LEAFLET MAP                                           */}
      {/* =================================================================== */}
      <div className="absolute inset-0 z-0">
        <MapContainer
          center={PHNOM_PENH_CENTER}
          zoom={13}
          minZoom={7}
          maxZoom={20}
          maxBounds={CAMBODIA_BOUNDS}
          maxBoundsViscosity={1.0}
          style={{ height: "100%", width: "100%" }}
          zoomControl={false}
        >
          {/* Google Maps Tiles */}
          <TileLayer
            attribution="&copy; Google Maps"
            url="https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}"
            subdomains={["0", "1", "2", "3"]}
            maxZoom={20}
          />

          <MapController
            focusId={selectedStore?.id ?? null}
            focusLat={selectedStore?.latitude}
            focusLng={selectedStore?.longitude}
            triggerCenter={recenterCount}
            zoomTarget={zoomTarget}
            onViewportChange={handleViewportChange}
          />

          {/* A. CLUSTER BUBBLES (Rendered on Overview zoom < 14) */}
          {clusters.map((c) => (
            <Marker
              key={`cluster-${c.key}`}
              position={[c.lat, c.lng]}
              icon={createClusterBubble(c.count, c.signedCount)}
              eventHandlers={{
                click: () => {
                  // Zoom in smoothly to unpack the cluster!
                  setZoomTarget((prev) => ({
                    zoom: Math.min(17, currentZoom + 3),
                    count: (prev?.count || 0) + 1,
                  }));
                },
              }}
            />
          ))}

          {/* B. TEARDROP PLACE PINS (Rendered at Street zoom or single stores) */}
          {individualPins.map((s) => {
            const isSelected = selectedStore?.id === s.id;
            const isSearchMatch =
              hasSearch &&
              (s.name.toLowerCase().includes(searchLower) ||
                s.phone.toLowerCase().includes(searchLower) ||
                s.address.toLowerCase().includes(searchLower) ||
                s.category.toLowerCase().includes(searchLower));

            // Show floating name label only when selected, matching active search, or at building-level zoom
            const showLabel = isSelected || isSearchMatch || currentZoom >= 18;

            return (
              <Marker
                key={`store-${s.id}`}
                position={[s.latitude, s.longitude]}
                zIndexOffset={isSelected ? 1000 : isSearchMatch ? 500 : 0}
                icon={createTeardropPin({
                  store: s,
                  isSelected,
                  showLabel,
                  isSearchMatch,
                })}
                eventHandlers={{
                  click: () => setSelectedStore(s),
                }}
              >
                {!showLabel && (
                  <Tooltip direction="top" offset={[0, -38]} opacity={0.95}>
                    <div className="font-bold text-slate-900 text-xs">{s.name}</div>
                    <div className="text-[10px] text-slate-500">{s.category} · {s.address}</div>
                  </Tooltip>
                )}
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      {/* =================================================================== */}
      {/* 2. TOP FLOATING GOOGLE MAPS SEARCH & FILTER PILLS                   */}
      {/* =================================================================== */}
      <div className="absolute top-3 left-3 right-3 lg:left-6 lg:max-w-xl z-[1000] pointer-events-auto space-y-2">
        {/* Floating Search Pill */}
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200/80 bg-white px-3 py-2 shadow-lg">
          <Search className="h-4 w-4 text-slate-400 shrink-0" />
          <input
            type="text"
            value={mapSearch}
            onChange={(e) => setMapSearch(e.target.value)}
            placeholder="Search stores, phone, district..."
            className="flex-1 bg-transparent text-xs font-semibold text-slate-900 placeholder-slate-400 focus:outline-none"
          />

          {mapSearch && (
            <button
              onClick={() => setMapSearch("")}
              className="p-1 rounded-full text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}

          <div className="h-4 w-px bg-slate-200 shrink-0" />

          {/* Map / List toggle icon */}
          <button
            onClick={() => setMobileViewMode(mobileViewMode === "map" ? "list" : "map")}
            title={mobileViewMode === "map" ? "Switch to list view" : "Switch to map view"}
            className="flex items-center gap-1.5 rounded-xl bg-slate-100 hover:bg-slate-200/80 px-2.5 py-1 text-xs font-bold text-slate-700 transition-all shrink-0"
          >
            {mobileViewMode === "map" ? (
              <>
                <List className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">List</span>
              </>
            ) : (
              <>
                <MapIcon className="h-3.5 w-3.5 text-cmcb-700" />
                <span className="hidden sm:inline text-cmcb-800">Map</span>
              </>
            )}
          </button>
        </div>

        {/* Horizontal Scrolling Filter Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 pr-2">
          {/* Status Chip */}
          <div className="relative shrink-0">
            <select
              value={mapStage}
              onChange={(e) => setMapStage(e.target.value)}
              className={`rounded-full px-3 py-1 text-[11px] font-bold border shadow-sm transition-all cursor-pointer focus:outline-none ${
                mapStage !== "ALL"
                  ? "bg-cmcb-700 text-white border-cmcb-700"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
              }`}
            >
              <option value="ALL">All Statuses</option>
              <option value="SIGNED">🟢 Signed</option>
              <option value="UNSIGNED_RECENT">🔴 Unsigned (≤ 14d)</option>
              <option value="UNSIGNED_DORMANT">⚪ Ignored (&gt; 14d Aura)</option>
            </select>
          </div>

          {/* Owner Chip */}
          <div className="relative shrink-0">
            <select
              value={mapOwner}
              onChange={(e) => setMapOwner(e.target.value)}
              className={`rounded-full px-3 py-1 text-[11px] font-bold border shadow-sm transition-all cursor-pointer focus:outline-none ${
                mapOwner !== "all"
                  ? "bg-cmcb-700 text-white border-cmcb-700"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
              }`}
            >
              <option value="all">All Owners</option>
              <option value="me">Assigned to Me</option>
              <option value="teammates">Teammates Only</option>
              <option value="unassigned">Unassigned Only</option>
            </select>
          </div>

          {/* District / Khan Chip */}
          <div className="relative shrink-0">
            <select
              value={mapKhan}
              onChange={(e) => setMapKhan(e.target.value)}
              className={`rounded-full px-3 py-1 text-[11px] font-bold border shadow-sm transition-all cursor-pointer focus:outline-none ${
                mapKhan !== "all"
                  ? "bg-cmcb-700 text-white border-cmcb-700"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
              }`}
            >
              <option value="all">All Districts</option>
              <option value="Boeng Keng Kang">Khan Boeng Keng Kang</option>
              <option value="Chamkar Mon">Khan Chamkar Mon</option>
              <option value="Doun Penh">Khan Doun Penh</option>
              <option value="Tuol Kouk">Khan Tuol Kouk</option>
              <option value="Prampir Meakkakra">Khan Prampir Meakkakra</option>
              <option value="Mean Chey">Khan Mean Chey</option>
              <option value="Sen Sok">Khan Sen Sok</option>
              <option value="Chroy Changvar">Khan Chroy Changvar</option>
              <option value="Russey Keo">Khan Russey Keo</option>
              <option value="Pur Senchey">Khan Pur Senchey</option>
            </select>
          </div>

          {/* Stores in View Counter Chip */}
          <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-extrabold text-slate-700 border border-slate-200 shadow-sm shrink-0">
            {totalInView} stores
          </span>
        </div>
      </div>

      {/* =================================================================== */}
      {/* 3. FLOATING ACTION CONTROLS (Right Edge)                            */}
      {/* =================================================================== */}
      <div className="absolute right-3 top-28 z-[900] flex flex-col gap-2 pointer-events-auto">
        {/* Recenter Button */}
        <button
          onClick={() => {
            setSelectedStore(null);
            setRecenterCount((c) => c + 1);
          }}
          title="Recenter to Phnom Penh Overview"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-700 shadow-lg border border-slate-200 hover:bg-slate-50 transition-all"
        >
          <Navigation className="h-4 w-4 text-cmcb-700" />
        </button>

        {/* Quick Zoom Tier Toggle (Street vs Overview) */}
        <button
          onClick={handleToggleZoomTier}
          title={currentZoom < 14 ? "Zoom into Street Level Pins" : "Zoom out to City Clusters"}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-700 shadow-lg border border-slate-200 hover:bg-slate-50 transition-all"
        >
          {currentZoom < 14 ? (
            <ZoomIn className="h-4 w-4 text-cmcb-700" />
          ) : (
            <ZoomOut className="h-4 w-4 text-slate-700" />
          )}
        </button>
      </div>

      {/* =================================================================== */}
      {/* 4. GOOGLE MAPS MOBILE BOTTOM SHEET                                  */}
      {/* =================================================================== */}
      {selectedStore && (
        <div
          className="fixed bottom-0 left-0 right-0 lg:left-6 lg:bottom-6 lg:right-auto lg:w-[420px] z-[1100] flex flex-col overflow-hidden rounded-t-3xl lg:rounded-2xl border-t lg:border border-slate-200/90 bg-white shadow-2xl animate-in slide-in-from-bottom duration-200 pointer-events-auto"
          style={
            isMobileSheet
              ? {
                  height: `${sheetHeightPx}px`,
                  transition: isDraggingSheet
                    ? "none"
                    : "height 260ms cubic-bezier(0.32, 0.72, 0, 1)",
                }
              : undefined
          }
        >
          {/* Drag zone — grab the handle/title and swipe up or down */}
          <div
            className={`shrink-0 px-5 pt-2.5 lg:pt-5 select-none lg:cursor-default ${
              isDraggingSheet ? "cursor-grabbing" : "cursor-grab"
            }`}
            style={isMobileSheet ? { touchAction: "none" } : undefined}
            onPointerDown={onSheetPointerDown}
            onPointerMove={onSheetPointerMove}
            onPointerUp={onSheetPointerUp}
            onPointerCancel={onSheetPointerUp}
          >
          {/* Google Maps Drag / Swipe Handle Pill */}
          <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-slate-300 lg:hidden" />

          {/* Store Title & Close Button */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h3 className="text-base lg:text-lg font-extrabold text-slate-900 truncate leading-snug">
                {selectedStore.name}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 truncate font-medium">
                {selectedStore.category} · Khan {selectedStore.district_khan}
              </p>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              <span
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                  selectedStore.is_signed || selectedStore.stage === "CONVERTED" || selectedStore.stage === "EXISTING"
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : selectedStore.status_category === "UNSIGNED_DORMANT" || (selectedStore.days_since_last_visit ?? 0) > 14
                    ? "bg-slate-100 text-slate-700 border border-slate-300 ring-1 ring-slate-400/40"
                    : "bg-rose-50 text-rose-800 border border-rose-200"
                }`}
              >
                {selectedStore.is_signed || selectedStore.stage === "CONVERTED" || selectedStore.stage === "EXISTING"
                  ? "🟢 Signed"
                  : selectedStore.status_category === "UNSIGNED_DORMANT" || (selectedStore.days_since_last_visit ?? 0) > 14
                  ? "⚪ Ignored > 14d"
                  : "🔴 Unsigned"}
              </span>

              <button
                onClick={() => setSelectedStore(null)}
                className="p-1.5 rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                title="Close sheet"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          </div>
          {/* end drag zone */}

          {/* Action Buttons Bar — pinned so it stays visible at every detent */}
          <div className="mt-3.5 shrink-0 px-5 flex items-center gap-2">
            <button
              onClick={() => {
                openMerchantDetail(selectedStore.id);
                setSelectedStore(null);
              }}
              className="flex-1 rounded-xl bg-cmcb-700 py-2.5 px-4 text-xs font-bold text-white shadow-sm hover:bg-cmcb-800 transition-colors text-center"
            >
              View store
            </button>

            <a
              href={`https://www.google.com/maps?q=${selectedStore.latitude},${selectedStore.longitude}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white py-2.5 px-4 text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors shrink-0"
            >
              <MapPin className="h-3.5 w-3.5 text-cmcb-700" />
              Directions
            </a>

            {selectedStore.phone && selectedStore.phone !== "N/A" && (
              <a
                href={`tel:${selectedStore.phone}`}
                title={`Call ${selectedStore.phone}`}
                className="flex items-center justify-center rounded-xl border border-slate-200 bg-white p-2.5 text-slate-700 shadow-sm hover:bg-slate-50 transition-colors shrink-0"
              >
                <Phone className="h-3.5 w-3.5 text-emerald-600" />
              </a>
            )}
          </div>

          {/* Scrollable details — reveals more as the sheet is pulled up */}
          <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-5 pb-6 lg:pb-5 mt-3.5">
          {/* Assigned Sales Rep & Phone info */}
          <div className="mt-3 flex items-center justify-between rounded-xl bg-slate-50 p-2.5 border border-slate-100 text-xs">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cmcb-700 text-xs font-bold text-white shadow-sm">
                {selectedStore.assigned_initials}
              </div>
              <div className="min-w-0">
                <p className="font-semibold text-slate-900 truncate">
                  {selectedStore.is_assigned_to_me
                    ? "Assigned to you"
                    : selectedStore.is_unassigned
                    ? "Available to approach"
                    : `Visited by ${selectedStore.assigned_name}`}
                </p>
                <p className="text-[11px] text-slate-500 truncate">
                  Last visit: {selectedStore.latest_visit_date?.slice(0, 10) || "None"}
                </p>
              </div>
            </div>

            {selectedStore.phone && selectedStore.phone !== "N/A" && (
              <span className="font-mono text-[11px] font-semibold text-slate-600 shrink-0 pl-2">
                {selectedStore.phone}
              </span>
            )}
          </div>

          {/* Field Remark Snippet */}
          {selectedStore.latest_remark && (
            <p className="mt-2.5 text-xs text-slate-600 line-clamp-2 italic px-0.5">
              "{selectedStore.latest_remark}"
            </p>
          )}

          {/* Previous Visits Log (earlier visits only; latest is shown above) */}
          {previousVisits.length > 0 && (
            <div className="mt-3 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-cmcb-700" />
                  Previous visits ({previousVisits.length})
                </span>
                <span className="text-[10px] font-semibold text-slate-400">
                  Earlier logs
                </span>
              </div>

              <div className="divide-y divide-slate-200/60 space-y-1.5">
                {previousVisits.map((v) => (
                  <div key={v.id} className="pt-1.5 first:pt-0 text-xs">
                    <div className="flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                        <span className="font-mono text-slate-500">{v.date}</span>
                        <span>·</span>
                        <span className="truncate max-w-[140px]">{v.sales_rep}</span>
                      </div>
                      <span className="rounded bg-white px-1.5 py-0.5 font-mono text-[9px] font-bold text-slate-600 border border-slate-200">
                        {v.status}
                      </span>
                    </div>

                    {v.remark && (
                      <p className="mt-0.5 text-[11px] text-slate-600 italic leading-snug">
                        "{v.remark}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* 5. FULLSCREEN LIST VIEW OVERLAY                                     */}
      {/* =================================================================== */}
      {mobileViewMode === "list" && (
        <div className="absolute inset-0 z-[1050] flex flex-col bg-white animate-in fade-in duration-200">
          {/* List Top Bar */}
          <div className="flex items-center justify-between border-b border-slate-100 p-3.5 bg-slate-50/80">
            <button
              onClick={() => setMobileViewMode("map")}
              className="flex items-center gap-1.5 text-xs font-bold text-cmcb-700 hover:text-cmcb-800"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Map
            </button>
            <span className="text-xs font-bold text-slate-800">
              {stores.length} Stores in View
            </span>
          </div>

          {/* List Content */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {stores.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No stores match your current filters.
              </div>
            ) : (
              stores.map((s) => {
                const isConverted = s.stage === "CONVERTED" || s.stage === "EXISTING";
                const isPipeline = s.stage === "PIPELINE";

                return (
                  <div
                    key={s.id}
                    onClick={() => {
                      setSelectedStore(s);
                      setMobileViewMode("map");
                    }}
                    className="p-4 transition-all hover:bg-slate-50 cursor-pointer"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h4 className="text-xs font-bold text-slate-900 truncate">
                          {s.name}
                        </h4>
                        <p className="text-[11px] text-slate-500 truncate mt-0.5">
                          {s.address} · {s.category}
                        </p>
                      </div>

                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold shrink-0 ${
                          s.is_signed || s.stage === "CONVERTED" || s.stage === "EXISTING"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : s.status_category === "UNSIGNED_DORMANT" || (s.days_since_last_visit ?? 0) > 14
                            ? "bg-slate-100 text-slate-700 border border-slate-300"
                            : "bg-rose-50 text-rose-700 border border-rose-200"
                        }`}
                      >
                        {s.is_signed || s.stage === "CONVERTED" || s.stage === "EXISTING"
                          ? "Signed"
                          : s.status_category === "UNSIGNED_DORMANT" || (s.days_since_last_visit ?? 0) > 14
                          ? "Ignored > 14d"
                          : "Unsigned"}
                      </span>
                    </div>

                    <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-500">
                      <div className="flex items-center gap-1.5 truncate pr-2">
                        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-cmcb-700 text-[9px] font-bold text-white">
                          {s.assigned_initials}
                        </div>
                        <span className="truncate">
                          {s.is_assigned_to_me
                            ? "Assigned to you"
                            : s.is_unassigned
                            ? "Available to approach"
                            : s.assigned_name}
                        </span>
                      </div>
                      <span className="shrink-0 text-[10px] text-slate-400">
                        {s.latest_visit_date ? s.latest_visit_date.slice(0, 10) : ""}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
