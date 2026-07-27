"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import type { MapMarker } from "./types";

type Props = {
  markers: MapMarker[];
  /** Só ajusta bounds quando não há initialCenter definido. */
  enabled: boolean;
};

/** Ao montar/atualizar com markers > 0 e sem initialCenter, enquadra todos. */
export function FitBounds({ markers, enabled }: Props) {
  const map = useMap();

  useEffect(() => {
    if (!enabled || markers.length === 0) return;
    const bounds = L.latLngBounds(markers.map((m) => m.position));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [map, markers, enabled]);

  return null;
}
