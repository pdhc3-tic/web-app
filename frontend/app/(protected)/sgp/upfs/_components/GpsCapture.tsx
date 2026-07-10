"use client";

import { useState } from "react";
import { MapPin, RotateCw } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";

type GpsCaptureProps = {
  latitude: string;
  longitude: string;
  onCapture: (lat: string, lng: string) => void;
};

/** Botão de captura de GPS via navigator.geolocation, com tratamento de permissão. */
export function GpsCapture({ latitude, longitude, onCapture }: GpsCaptureProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasCoords = latitude !== "" && longitude !== "";

  function capture() {
    setError(null);

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setError("Geolocalização não é suportada neste navegador.");
      return;
    }

    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onCapture(
          pos.coords.latitude.toFixed(6),
          pos.coords.longitude.toFixed(6),
        );
        setLoading(false);
      },
      (err) => {
        setLoading(false);
        if (err.code === err.PERMISSION_DENIED) {
          setError(
            "Permissão de localização negada. Habilite o acesso à localização nas configurações do navegador.",
          );
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setError("Não foi possível determinar a localização.");
        } else {
          setError("Tempo esgotado ao obter a localização. Tente novamente.");
        }
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-label font-medium text-text leading-[1.2]">
        GPS
      </legend>

      {hasCoords ? (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm tabular-nums text-text">
            {latitude}, {longitude}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={capture}
            loading={loading}
            leftIcon={<RotateCw className="h-4 w-4" />}
          >
            Refazer
          </Button>
        </div>
      ) : (
        <div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={capture}
            loading={loading}
            leftIcon={<MapPin className="h-4 w-4" />}
          >
            Capturar GPS atual
          </Button>
        </div>
      )}

      {error && (
        <span className="text-xs text-error-text" role="alert">
          {error}
        </span>
      )}
    </fieldset>
  );
}
