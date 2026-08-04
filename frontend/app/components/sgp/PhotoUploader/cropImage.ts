/**
 * Lógica pura de recorte em canvas (sem dependências de UI). Isolada aqui para
 * ser reaproveitada por qualquer componente de crop no projeto.
 */

export type ImageSize = { width: number; height: number };

/** Centro do recorte, normalizado em [0,1] relativo às dimensões da imagem. */
export type CropCenter = { x: number; y: number };

export type CropDimensions = { width: number; height: number };

export type CropRect = { sx: number; sy: number; width: number; height: number };

const MIN_ZOOM = 1;
const MAX_ZOOM = 3;
const DEFAULT_OUTPUT_SIZE = 512;

export function clampZoom(zoom: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** Carrega um File como HTMLImageElement. O chamador deve `URL.revokeObjectURL(objectUrl)` ao descartar. */
export function loadImageFromFile(
  file: File,
): Promise<{ image: HTMLImageElement; objectUrl: string }> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => resolve({ image, objectUrl });
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("Não foi possível ler a imagem."));
    };
    image.src = objectUrl;
  });
}

/**
 * Dimensões (em px da imagem original) do retângulo visível no viewport, dado o
 * zoom e a proporção desejada. zoom=1 mostra o maior retângulo dessa proporção
 * que cabe na imagem; zoom>1 aproxima.
 */
export function visibleCropSize(
  image: ImageSize,
  zoom: number,
  aspectRatio: number,
): CropDimensions {
  const maxWidth = Math.min(image.width, image.height * aspectRatio);
  const maxHeight = maxWidth / aspectRatio;
  const z = clampZoom(zoom);
  return { width: maxWidth / z, height: maxHeight / z };
}

/** Garante que o retângulo de recorte (centrado em `center`) não saia da imagem. */
export function clampCenter(
  image: ImageSize,
  zoom: number,
  aspectRatio: number,
  center: CropCenter,
): CropCenter {
  const { width, height } = visibleCropSize(image, zoom, aspectRatio);
  const halfW = width / 2 / image.width;
  const halfH = height / 2 / image.height;
  return {
    x: Math.min(1 - halfW, Math.max(halfW, center.x)),
    y: Math.min(1 - halfH, Math.max(halfH, center.y)),
  };
}

/** Retângulo de origem (em px da imagem) a recortar. */
export function computeCropRect(
  image: ImageSize,
  zoom: number,
  aspectRatio: number,
  center: CropCenter,
): CropRect {
  const { width, height } = visibleCropSize(image, zoom, aspectRatio);
  const clamped = clampCenter(image, zoom, aspectRatio, center);
  return {
    sx: clamped.x * image.width - width / 2,
    sy: clamped.y * image.height - height / 2,
    width,
    height,
  };
}

/** Desenha o recorte num canvas e retorna um Blob. */
export function cropToBlob(
  image: HTMLImageElement,
  rect: CropRect,
  aspectRatio: number,
  outputSize: number = DEFAULT_OUTPUT_SIZE,
  mimeType: string = "image/jpeg",
  quality = 0.92,
): Promise<Blob> {
  const outputWidth = aspectRatio >= 1 ? outputSize : Math.round(outputSize * aspectRatio);
  const outputHeight = aspectRatio >= 1 ? Math.round(outputSize / aspectRatio) : outputSize;

  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return Promise.reject(new Error("Canvas indisponível."));

  ctx.drawImage(
    image,
    rect.sx,
    rect.sy,
    rect.width,
    rect.height,
    0,
    0,
    outputWidth,
    outputHeight,
  );

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob ? resolve(blob) : reject(new Error("Falha ao gerar imagem recortada.")),
      mimeType,
      quality,
    );
  });
}
