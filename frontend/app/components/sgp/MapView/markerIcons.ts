import L from "leaflet";
import type { MapMarkerStatus } from "./types";

/**
 * Ícone de marker por status. Usa divIcon (HTML/CSS) — evita o clássico bug de
 * imagem de ícone quebrada do Leaflet com bundler. As cores vêm das CSS vars do
 * design system (theme-aware), aplicadas em mapview.css.
 */
export function statusIcon(status: MapMarkerStatus): L.DivIcon {
  return L.divIcon({
    className: "", // sem classe no wrapper; estilizamos o filho .mapview-marker
    html: `<span class="mapview-marker mapview-marker--${status}"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  });
}

/** iconCreateFunction do markerCluster: círculo maior com a contagem no centro. */
export function clusterIcon(cluster: {
  getChildCount: () => number;
}): L.DivIcon {
  const count = cluster.getChildCount();
  return L.divIcon({
    className: "",
    html: `<span class="mapview-cluster">${count}</span>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  });
}
