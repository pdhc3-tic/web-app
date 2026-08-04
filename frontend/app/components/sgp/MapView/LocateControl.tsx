"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

const LOCATE_SVG = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/><line x1="1" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="23" y2="12"/></svg>`;

/** Controle custom de "minha localização" (topo-esquerdo), via map.locate(). */
export function LocateControl() {
  const map = useMap();

  useEffect(() => {
    const control = new L.Control({ position: "topleft" });

    control.onAdd = () => {
      const container = L.DomUtil.create("div", "leaflet-bar leaflet-control");
      const link = L.DomUtil.create(
        "a",
        "mapview-locate-btn",
        container,
      ) as HTMLAnchorElement;
      link.href = "#";
      link.title = "Minha localização";
      link.setAttribute("role", "button");
      link.setAttribute("aria-label", "Centralizar na minha localização");
      link.innerHTML = LOCATE_SVG;

      L.DomEvent.on(link, "click", (e) => {
        L.DomEvent.stop(e);
        link.setAttribute("aria-busy", "true");
        map.locate({ setView: true, maxZoom: 14 });
      });
      return container;
    };

    control.addTo(map);

    const clearBusy = () => {
      map
        .getContainer()
        .querySelector(".mapview-locate-btn")
        ?.removeAttribute("aria-busy");
    };
    map.on("locationfound", clearBusy);
    map.on("locationerror", clearBusy);

    return () => {
      map.off("locationfound", clearBusy);
      map.off("locationerror", clearBusy);
      control.remove();
    };
  }, [map]);

  return null;
}
