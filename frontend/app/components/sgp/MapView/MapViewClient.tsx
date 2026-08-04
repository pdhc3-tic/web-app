"use client";

import "./mapview.css";
import type { CSSProperties } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import { MarkersLayer } from "./MarkersLayer";
import { FitBounds } from "./FitBounds";
import { LocateControl } from "./LocateControl";
import type { MapViewProps } from "./types";

// Fallback quando não há markers nem initialCenter (Nordeste — Recife/PE).
const DEFAULT_CENTER: [number, number] = [-8.05, -34.9];
const DEFAULT_ZOOM = 5;

export default function MapViewClient({
  markers,
  height = "600px",
  initialCenter,
  initialZoom,
  clusteringThreshold = 200,
  onMarkerClick,
  ariaLabel = "Mapa de Unidades de Produção Familiar",
}: MapViewProps) {
  const clustering = markers.length > clusteringThreshold;
  const style = { "--map-height": height } as CSSProperties;

  return (
    <div
      className="mapview-root"
      style={style}
      role="region"
      aria-label={ariaLabel}
    >
      <MapContainer
        center={initialCenter ?? DEFAULT_CENTER}
        zoom={initialZoom ?? DEFAULT_ZOOM}
        scrollWheelZoom
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MarkersLayer
          markers={markers}
          clustering={clustering}
          onMarkerClick={onMarkerClick}
        />
        <FitBounds markers={markers} enabled={!initialCenter} />
        <LocateControl />
      </MapContainer>
    </div>
  );
}
