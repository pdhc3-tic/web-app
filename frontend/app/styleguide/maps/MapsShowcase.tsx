"use client";

import { useMemo } from "react";
import { MapView, type MapMarker } from "@/app/components/sgp/MapView/MapView";

/** Gera markers mock espalhados pelo Nordeste (lat -3..-16, lng -34..-46). */
function makeMarkers(n: number): MapMarker[] {
  const out: MapMarker[] = [];
  for (let i = 0; i < n; i++) {
    const lat = -3 - Math.random() * 13;
    const lng = -34 - Math.random() * 12;
    const status: MapMarker["status"] =
      Math.random() > 0.35 ? "active" : "inactive";
    out.push({
      id: i + 1,
      position: [lat, lng],
      status,
      popup: (
        <div>
          <p className="font-semibold text-text">UPF #{i + 1}</p>
          <p className="mt-0.5 text-text-muted">
            {status === "active" ? "Ativa" : "Inativa"} · {lat.toFixed(3)},{" "}
            {lng.toFixed(3)}
          </p>
        </div>
      ),
    });
  }
  return out;
}

function Example({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-lg font-semibold text-text border-b border-border pb-2 mb-2">
        {title}
      </h2>
      <p className="mb-4 text-sm text-text-muted">{description}</p>
      {children}
    </section>
  );
}

export function MapsShowcase() {
  const five = useMemo(() => makeMarkers(5), []);
  const fifty = useMemo(() => makeMarkers(50), []);
  const fiveHundred = useMemo(() => makeMarkers(500), []);

  return (
    <div className="space-y-12">
      <Example
        title="5 markers"
        description="Markers individuais coloridos por status (ativo = primary, inativo = terracota). Fit bounds automático."
      >
        <MapView markers={five} height="460px" />
      </Example>

      <Example
        title="50 markers"
        description="Ainda individuais (abaixo do threshold de 200). Clique num marker para ver o popup."
      >
        <MapView markers={fifty} height="460px" />
      </Example>

      <Example
        title="500 markers"
        description="Acima do threshold (200) → clustering automático. Aproxime o zoom para os clusters se dividirem."
      >
        <MapView markers={fiveHundred} height="460px" />
      </Example>
    </div>
  );
}
