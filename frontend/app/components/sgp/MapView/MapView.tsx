"use client";

import dynamic from "next/dynamic";
import type { MapViewProps } from "./types";

// Leaflet acessa `window` no import → carregamento dinâmico sem SSR.
// dynamic({ ssr: false }) só é permitido dentro de um Client Component (Next 16).
const MapViewClient = dynamic(() => import("./MapViewClient"), {
  ssr: false,
  loading: () => (
    <div
      style={{
        height: "600px",
        width: "100%",
        borderRadius: "0.5rem",
        border: "1px solid var(--color-border)",
        background: "var(--color-surface-muted)",
      }}
      aria-hidden="true"
    />
  ),
});

/** Mapa reusável (Leaflet + OSM). Ver types.ts para as props. */
export function MapView(props: MapViewProps) {
  return <MapViewClient {...props} />;
}

export type { MapMarker, MapMarkerStatus, MapViewProps } from "./types";
