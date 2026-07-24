"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { AlertTriangle, ZoomIn } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import {
  clampCenter,
  computeCropRect,
  cropToBlob,
  loadImageFromFile,
  type CropCenter,
  type ImageSize,
} from "./cropImage";

const VIEWPORT_SIZE = 280;

type CropModalProps = {
  open: boolean;
  file: File | null;
  aspectRatio: number;
  shape: "circle" | "square";
  onCancel: () => void;
  onConfirm: (blob: Blob) => void;
};

/** Modal de recorte com pan (arrastar) e zoom, desenhado em canvas via cropImage.ts. */
export function CropModal({
  open,
  file,
  aspectRatio,
  shape,
  onCancel,
  onConfirm,
}: CropModalProps) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [center, setCenter] = useState<CropCenter>({ x: 0.5, y: 0.5 });
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const objectUrlRef = useRef<string | null>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!file || !open) return;
    let cancelled = false;
    // Reinicia o estado local do crop a cada novo arquivo/abertura do modal.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadError(null);
    setZoom(1);
    setCenter({ x: 0.5, y: 0.5 });

    loadImageFromFile(file)
      .then(({ image: img, objectUrl }) => {
        if (cancelled) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        objectUrlRef.current = objectUrl;
        setImage(img);
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError("Não foi possível carregar a imagem selecionada.");
        }
      });

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
      setImage(null);
    };
  }, [file, open]);

  const viewportHeight = VIEWPORT_SIZE / aspectRatio;

  const transform = useMemo(() => {
    if (!image) return null;
    const size: ImageSize = { width: image.naturalWidth, height: image.naturalHeight };
    const rect = computeCropRect(size, zoom, aspectRatio, center);
    const scale = VIEWPORT_SIZE / rect.width;
    return {
      scale,
      translateX: -rect.sx * scale,
      translateY: -rect.sy * scale,
      displayWidth: size.width * scale,
      displayHeight: size.height * scale,
    };
  }, [image, zoom, center, aspectRatio]);

  function handlePointerDown(e: PointerEvent<HTMLDivElement>) {
    if (!image) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY };
  }

  function handlePointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!image || !dragRef.current || !transform) return;
    const dx = e.clientX - dragRef.current.x;
    const dy = e.clientY - dragRef.current.y;
    dragRef.current = { x: e.clientX, y: e.clientY };

    const size: ImageSize = { width: image.naturalWidth, height: image.naturalHeight };
    setCenter((prev) =>
      clampCenter(size, zoom, aspectRatio, {
        x: prev.x - dx / transform.scale / size.width,
        y: prev.y - dy / transform.scale / size.height,
      }),
    );
  }

  function handlePointerUp(e: PointerEvent<HTMLDivElement>) {
    dragRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  function handleZoomChange(next: number) {
    if (!image) return;
    const size: ImageSize = { width: image.naturalWidth, height: image.naturalHeight };
    setZoom(next);
    setCenter((prev) => clampCenter(size, next, aspectRatio, prev));
  }

  async function handleConfirm() {
    if (!image) return;
    setSaving(true);
    try {
      const size: ImageSize = { width: image.naturalWidth, height: image.naturalHeight };
      const rect = computeCropRect(size, zoom, aspectRatio, center);
      const blob = await cropToBlob(image, rect, aspectRatio);
      onConfirm(blob);
    } catch {
      setLoadError("Não foi possível recortar a imagem. Tente novamente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SlideOver
      open={open}
      onClose={onCancel}
      title="Recortar foto"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={saving}>
            Cancelar
          </Button>
          <Button onClick={handleConfirm} loading={saving} disabled={!image}>
            Aplicar recorte
          </Button>
        </div>
      }
    >
      <div className="flex flex-col items-center gap-4 p-4">
        {loadError && (
          <div
            role="alert"
            className="flex w-full items-start gap-2 rounded-md bg-error-bg px-3 py-2 text-sm text-error-text"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {loadError}
          </div>
        )}

        <div
          className={`relative touch-none select-none overflow-hidden border border-border bg-surface-muted ${
            shape === "circle" ? "rounded-full" : "rounded-md"
          }`}
          style={{
            width: VIEWPORT_SIZE,
            height: viewportHeight,
            cursor: image ? "grab" : "default",
          }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          {image && transform && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={image.src}
              alt=""
              draggable={false}
              className="pointer-events-none absolute top-0 left-0 max-w-none"
              style={{
                width: transform.displayWidth,
                height: transform.displayHeight,
                transform: `translate(${transform.translateX}px, ${transform.translateY}px)`,
              }}
            />
          )}
        </div>

        <div className="flex w-full max-w-70 items-center gap-3">
          <ZoomIn className="h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
          <input
            type="range"
            min={1}
            max={3}
            step={0.05}
            value={zoom}
            onChange={(e) => handleZoomChange(Number(e.target.value))}
            disabled={!image}
            aria-label="Zoom do recorte"
            className="w-full accent-primary"
          />
        </div>

        <p className="text-center text-xs text-text-muted">
          Arraste para posicionar e use o controle para aproximar.
        </p>
      </div>
    </SlideOver>
  );
}
