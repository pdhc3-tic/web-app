"use client";

import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import { createRoot, type Root } from "react-dom/client";
import L from "leaflet";
import "leaflet.markercluster";
import { clusterIcon, statusIcon } from "./markerIcons";
import type { MapMarker } from "./types";

type Props = {
  markers: MapMarker[];
  /** Acima do threshold → markerClusterGroup; abaixo → markers individuais. */
  clustering: boolean;
  onMarkerClick?: (id: MapMarker["id"]) => void;
};

/**
 * Camada de markers imperativa: constrói os L.marker à mão para poder (a) usar o
 * plugin markercluster e (b) renderizar o popup ReactNode via createRoot em um
 * container DOM ligado ao marker. onMarkerClick fica num ref para não reconstruir
 * a camada a cada render do pai.
 */
export function MarkersLayer({ markers, clustering, onMarkerClick }: Props) {
  const map = useMap();
  const onClickRef = useRef(onMarkerClick);

  useEffect(() => {
    onClickRef.current = onMarkerClick;
  }, [onMarkerClick]);

  useEffect(() => {
    const roots: Root[] = [];
    const group: L.FeatureGroup = clustering
      ? L.markerClusterGroup({
          iconCreateFunction: clusterIcon,
          showCoverageOnHover: false,
          chunkedLoading: true,
        })
      : L.featureGroup();

    for (const m of markers) {
      const marker = L.marker(m.position, {
        icon: statusIcon(m.status),
        keyboard: true,
        title: String(m.id),
      });

      const container = document.createElement("div");
      const root = createRoot(container);
      root.render(m.popup);
      roots.push(root);
      marker.bindPopup(container, { minWidth: 200, maxWidth: 320 });

      marker.on("click", () => onClickRef.current?.(m.id));
      group.addLayer(marker);
    }

    map.addLayer(group);

    return () => {
      map.removeLayer(group);
      // Desmonta fora do ciclo atual para evitar warning de unmount síncrono.
      queueMicrotask(() => roots.forEach((r) => r.unmount()));
    };
  }, [map, markers, clustering]);

  return null;
}
