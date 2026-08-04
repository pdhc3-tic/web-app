"use client";

import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { AlertTriangle, Camera, ImagePlus, Loader2, Trash2 } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { ApiError } from "@/app/lib/api";
import { confirmUpload, deletePhoto, requestUploadUrl, uploadToStorage } from "./photoUpload";
import { DEFAULT_ACCEPTED_TYPES, validateFile } from "./validation";
import { CropModal } from "./CropModal";

type Phase = "idle" | "preview" | "uploading" | "confirming" | "error";

export type PhotoUploaderProps = {
  currentUrl: string | null;
  onChange: (newUrl: string | null) => void;
  /** Ex.: "/api/v1/upfs/{id}/foto/upload-url/" já resolvido com o id concreto. */
  uploadUrlEndpoint: string;
  /** Ex.: "/api/v1/upfs/{id}/foto/confirm/" já resolvido com o id concreto. */
  confirmEndpoint: string;
  /** Ex.: "/api/v1/upfs/{id}/foto/" já resolvido com o id concreto. */
  deleteEndpoint: string;
  maxSizeMB?: number;
  acceptedTypes?: string[];
  aspectRatio?: number;
  shape?: "circle" | "square";
};

const EXT_BY_TYPE: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

function extFromType(type: string): string {
  return EXT_BY_TYPE[type] ?? "jpg";
}

export function PhotoUploader({
  currentUrl,
  onChange,
  uploadUrlEndpoint,
  confirmEndpoint,
  deleteEndpoint,
  maxSizeMB = 5,
  acceptedTypes = DEFAULT_ACCEPTED_TYPES,
  aspectRatio = 1,
  shape = "circle",
}: PhotoUploaderProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [dragActive, setDragActive] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [cropOpen, setCropOpen] = useState(false);
  const [removeOpen, setRemoveOpen] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const pendingBlobRef = useRef<Blob | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Espelha o object URL de preview corrente para poder revogá-lo no unmount
  // (o cleanup roda uma vez e não enxerga o valor mais recente do state).
  const previewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      abortRef.current?.abort();
    };
  }, []);

  /** Troca o object URL de preview, revogando o anterior. Centraliza a limpeza. */
  function setPreview(url: string | null) {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = url;
    setPreviewUrl(url);
  }

  function resetToIdle() {
    setPreview(null);
    setRawFile(null);
    pendingBlobRef.current = null;
    setProgress(0);
    setErrorMessage(null);
    setPhase("idle");
  }

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;

    const result = validateFile(file, maxSizeMB, acceptedTypes);
    if (!result.valid) {
      setValidationError(result.message);
      return;
    }

    setValidationError(null);
    setPreview(URL.createObjectURL(file));
    setRawFile(file);
    pendingBlobRef.current = file;
    setPhase("preview");
  }

  function openPicker() {
    if (phase !== "idle") return;
    inputRef.current?.click();
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (phase === "idle") setDragActive(true);
  }

  function handleDragLeave() {
    setDragActive(false);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    if (phase !== "idle") return;
    handleFiles(e.dataTransfer.files);
  }

  function cancelPreview() {
    resetToIdle();
    setValidationError(null);
  }

  function handleCropConfirm(blob: Blob) {
    setPreview(URL.createObjectURL(blob));
    pendingBlobRef.current = blob;
    setCropOpen(false);
  }

  async function startUpload(blob: Blob) {
    setPhase("uploading");
    setProgress(0);
    setErrorMessage(null);
    setStatusMessage("Enviando foto...");
    abortRef.current = new AbortController();

    try {
      const contentType = blob.type || "image/jpeg";
      const uploadInfo = await requestUploadUrl(uploadUrlEndpoint, {
        name: `foto.${extFromType(contentType)}`,
        type: contentType,
        size: blob.size,
      });

      await uploadToStorage(
        uploadInfo.url,
        blob,
        contentType,
        setProgress,
        abortRef.current.signal,
      );

      setPhase("confirming");
      setStatusMessage("Confirmando envio...");
      const { foto_url } = await confirmUpload(confirmEndpoint, uploadInfo.key);

      setStatusMessage("Foto atualizada.");
      resetToIdle();
      onChange(foto_url);
    } catch (e) {
      setErrorMessage(
        e instanceof ApiError
          ? e.message
          : "Não foi possível enviar a foto. Tente novamente.",
      );
      setStatusMessage("Erro ao enviar a foto.");
      setPhase("error");
    }
  }

  function handleConfirmUpload() {
    if (pendingBlobRef.current) startUpload(pendingBlobRef.current);
  }

  function handleRetry() {
    if (pendingBlobRef.current) startUpload(pendingBlobRef.current);
  }

  async function handleRemoveConfirm() {
    setRemoving(true);
    setRemoveError(null);
    try {
      await deletePhoto(deleteEndpoint);
      setStatusMessage("Foto removida.");
      setRemoveOpen(false);
      onChange(null);
    } catch (e) {
      setRemoveError(
        e instanceof ApiError
          ? e.message
          : "Não foi possível remover a foto. Tente novamente.",
      );
    } finally {
      setRemoving(false);
    }
  }

  const shapeClass = shape === "circle" ? "rounded-full" : "rounded-lg";
  const busy = phase === "uploading" || phase === "confirming";
  const displayUrl =
    phase === "idle" ? currentUrl : previewUrl ?? currentUrl;

  return (
    <div className="flex flex-col items-center gap-3">
      <div aria-live="polite" className="sr-only">
        {statusMessage}
      </div>

      <div
        role="button"
        tabIndex={busy ? -1 : 0}
        aria-label={
          currentUrl || previewUrl ? "Trocar foto" : "Selecionar foto"
        }
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openPicker();
          }
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`group relative flex h-32 w-32 shrink-0 items-center justify-center overflow-hidden border-2 border-dashed bg-surface-muted transition-colors ${shapeClass} ${
          dragActive
            ? "border-primary bg-surface-warm"
            : "border-border"
        } ${phase === "idle" ? "cursor-pointer hover:border-primary" : "cursor-default"}`}
      >
        {displayUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={displayUrl}
            alt=""
            className="h-full w-full object-cover"
          />
        ) : (
          <ImagePlus
            className="h-8 w-8 text-text-muted"
            aria-hidden="true"
          />
        )}

        {phase === "idle" && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center gap-1 bg-black/50 text-xs font-medium text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
            <Camera className="h-4 w-4" aria-hidden="true" />
            Trocar foto
          </div>
        )}

        {busy && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/60 text-white">
            {phase === "uploading" ? (
              <>
                <span
                  role="progressbar"
                  aria-valuenow={progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Progresso do envio"
                  className="h-1.5 w-20 overflow-hidden rounded-full bg-white/30"
                >
                  <span
                    className="block h-full rounded-full bg-white transition-[width]"
                    style={{ width: `${progress}%` }}
                  />
                </span>
                <span className="text-2xs">{progress}%</span>
              </>
            ) : (
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            )}
          </div>
        )}
      </div>

      <label htmlFor={inputId} className="sr-only">
        Selecionar foto
      </label>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={acceptedTypes.join(",")}
        className="sr-only"
        disabled={phase !== "idle"}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {validationError && (
        <p role="alert" className="max-w-56 text-center text-xs text-error-text">
          {validationError}
        </p>
      )}

      {phase === "preview" && (
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button variant="ghost" size="sm" onClick={cancelPreview}>
            Cancelar
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setCropOpen(true)}
          >
            Recortar
          </Button>
          <Button size="sm" onClick={handleConfirmUpload}>
            Confirmar
          </Button>
        </div>
      )}

      {phase === "error" && (
        <div className="flex max-w-64 flex-col items-center gap-2">
          <p role="alert" className="flex items-start gap-1.5 text-center text-xs text-error-text">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {errorMessage}
          </p>
          <Button variant="secondary" size="sm" onClick={handleRetry}>
            Tentar novamente
          </Button>
        </div>
      )}

      {phase === "idle" && currentUrl && (
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<Trash2 className="h-3.5 w-3.5" />}
          onClick={() => setRemoveOpen(true)}
        >
          Remover foto
        </Button>
      )}

      <CropModal
        open={cropOpen}
        file={rawFile}
        aspectRatio={aspectRatio}
        shape={shape}
        onCancel={() => setCropOpen(false)}
        onConfirm={handleCropConfirm}
      />

      <SlideOver
        open={removeOpen}
        onClose={removing ? () => {} : () => setRemoveOpen(false)}
        title="Remover foto"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => setRemoveOpen(false)}
              disabled={removing}
            >
              Cancelar
            </Button>
            <Button variant="danger" onClick={handleRemoveConfirm} loading={removing}>
              Confirmar
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-4 px-4 py-6">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
              <AlertTriangle className="h-5 w-5" />
            </span>
            <p className="text-sm text-text">
              Tem certeza que deseja remover a foto?
            </p>
          </div>

          {removeError && (
            <div
              role="alert"
              className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text"
            >
              {removeError}
            </div>
          )}
        </div>
      </SlideOver>
    </div>
  );
}
