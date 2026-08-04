import type { ReactNode } from "react";

export type MapMarkerStatus = "active" | "inactive";

export type MapMarker = {
  id: string | number;
  /** [lat, lng] */
  position: [number, number];
  status: MapMarkerStatus;
  /** Conteúdo do popup ao clicar no marker. */
  popup: ReactNode;
};

export type MapViewProps = {
  markers: MapMarker[];
  /** Altura em desktop (default '600px'). Em mobile cai para 400px via CSS. */
  height?: string;
  /** Centro inicial [lat, lng]. Se ausente, faz fit bounds dos markers. */
  initialCenter?: [number, number];
  initialZoom?: number;
  /** Acima deste total de markers, ativa clustering (default 200). */
  clusteringThreshold?: number;
  onMarkerClick?: (id: MapMarker["id"]) => void;
  /**
   * aria-label do container. Default aponta para UPFs (uso desta sprint), mas é
   * sobrescrevível para os usos futuros (atividades, OSCs) — o componente é genérico.
   */
  ariaLabel?: string;
};
