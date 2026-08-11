"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type DragEvent,
} from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  CloudOff,
  GripVertical,
  ImagePlus,
  Loader2,
  Pencil,
  Star,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { ApiError } from "@/app/lib/api";
import {
  confirmPhoto,
  deletePhoto as apiDeletePhoto,
  listPhotos,
  reorderPhotos,
  requestPhotoUploadUrl,
  updatePhoto,
  uploadBlobToStorage,
} from "./evidenceApi";
import { validatePhoto } from "./validation";
import {
  MAX_PHOTOS_PER_ACTIVITY,
  PHOTO_ACCEPTED_TYPES,
  formatBytes,
  type EvidencePhoto,
} from "./types";

const EXT_BY_TYPE: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
};

type UploadPhase = "staged" | "uploading" | "confirming" | "error";

type StagedUpload = {
  localId: string;
  file: File;
  previewUrl: string;
  legenda: string;
  progress: number;
  phase: UploadPhase;
  error?: string;
};

type Props = {
  atividadeId: string;
  /** Desabilita todas as ações de edição (para leitores da atividade). */
  readOnly?: boolean;
};

export function PhotoGallery({ atividadeId, readOnly = false }: Props) {
  const { showToast } = useToast();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadsRef = useRef<StagedUpload[]>([]);
  const abortsRef = useRef<Map<string, AbortController>>(new Map());

  const [photos, setPhotos] = useState<EvidencePhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [uploads, setUploads] = useState<StagedUpload[]>([]);
  const [limitMessage, setLimitMessage] = useState<string | null>(null);
  const [dragOverTray, setDragOverTray] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingLegenda, setEditingLegenda] = useState("");
  const [savingEditId, setSavingEditId] = useState<number | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<EvidencePhoto | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [dragPhotoId, setDragPhotoId] = useState<number | null>(null);
  const [dropTargetIndex, setDropTargetIndex] = useState<number | null>(null);

  useEffect(() => {
    uploadsRef.current = uploads;
  }, [uploads]);

  // ── Carga inicial ─────────────────────────────────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setLoadError(null);
    listPhotos(atividadeId, controller.signal)
      .then((data) => setPhotos(data))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as fotos.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [atividadeId, reloadKey]);

  // ── Limpeza: revoga previews e aborta uploads pendentes ao desmontar ──────
  useEffect(() => {
    const aborts = abortsRef.current;
    return () => {
      for (const u of uploadsRef.current) URL.revokeObjectURL(u.previewUrl);
      for (const c of aborts.values()) c.abort();
      aborts.clear();
    };
  }, []);

  const totalOcupado = photos.length + uploads.length;
  const podeAdicionarMais = totalOcupado < MAX_PHOTOS_PER_ACTIVITY;
  const vagasRestantes = Math.max(0, MAX_PHOTOS_PER_ACTIVITY - totalOcupado);

  // ── Adição de arquivos ────────────────────────────────────────────────────
  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const list = Array.from(files);
      if (list.length === 0) return;

      setLimitMessage(null);
      const staged: StagedUpload[] = [];
      const rejeitados: string[] = [];
      let restantes = MAX_PHOTOS_PER_ACTIVITY - (photos.length + uploads.length);

      for (const file of list) {
        if (restantes <= 0) {
          setLimitMessage(
            `Máximo de ${MAX_PHOTOS_PER_ACTIVITY} fotos por atividade.`,
          );
          break;
        }
        const result = validatePhoto(file);
        if (!result.valid) {
          rejeitados.push(result.message);
          continue;
        }
        staged.push({
          localId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          file,
          previewUrl: URL.createObjectURL(file),
          legenda: "",
          progress: 0,
          phase: "staged",
        });
        restantes--;
      }

      if (rejeitados.length > 0) {
        showToast(rejeitados.join("\n"), "error");
      }
      if (staged.length > 0) {
        setUploads((prev) => [...prev, ...staged]);
      }
    },
    [photos.length, uploads.length, showToast],
  );

  function openPicker() {
    if (readOnly || !podeAdicionarMais) return;
    inputRef.current?.click();
  }

  function handleTrayDragOver(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    if (dragPhotoId !== null) return; // reordenação em curso, não trate como upload
    setDragOverTray(true);
  }

  function handleTrayDrop(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    setDragOverTray(false);
    if (dragPhotoId !== null) return;
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  }

  // ── Upload de uma foto encenada ───────────────────────────────────────────
  const patchUpload = useCallback(
    (localId: string, patch: Partial<StagedUpload>) => {
      setUploads((prev) =>
        prev.map((u) => (u.localId === localId ? { ...u, ...patch } : u)),
      );
    },
    [],
  );

  const removeUpload = useCallback((localId: string) => {
    setUploads((prev) => {
      const found = prev.find((u) => u.localId === localId);
      if (found) URL.revokeObjectURL(found.previewUrl);
      return prev.filter((u) => u.localId !== localId);
    });
    abortsRef.current.get(localId)?.abort();
    abortsRef.current.delete(localId);
  }, []);

  async function startUpload(upload: StagedUpload) {
    const controller = new AbortController();
    abortsRef.current.set(upload.localId, controller);

    patchUpload(upload.localId, { phase: "uploading", progress: 0, error: undefined });

    try {
      const contentType = upload.file.type;
      const ext = EXT_BY_TYPE[contentType] ?? "jpg";
      const uploadInfo = await requestPhotoUploadUrl(atividadeId, {
        filename: `foto.${ext}`,
        content_type: contentType,
        size: upload.file.size,
        legenda: upload.legenda,
      });

      await uploadBlobToStorage(
        uploadInfo.url,
        upload.file,
        contentType,
        (percent) => patchUpload(upload.localId, { progress: percent }),
        controller.signal,
      );

      patchUpload(upload.localId, { phase: "confirming" });
      const saved = await confirmPhoto(atividadeId, {
        key: uploadInfo.key,
        legenda: upload.legenda,
      });

      // Sucesso: promove para a lista final e libera o object URL.
      URL.revokeObjectURL(upload.previewUrl);
      abortsRef.current.delete(upload.localId);
      setUploads((prev) => prev.filter((u) => u.localId !== upload.localId));
      setPhotos((prev) => [...prev, saved]);
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return;
      abortsRef.current.delete(upload.localId);
      patchUpload(upload.localId, {
        phase: "error",
        error:
          e instanceof ApiError
            ? e.message
            : "Falha no envio. Tente novamente.",
      });
    }
  }

  async function enviarPendentes() {
    const pendentes = uploads.filter(
      (u) => u.phase === "staged" || u.phase === "error",
    );
    if (pendentes.length === 0) return;
    // Envia em paralelo — a progress bar é individual por arquivo.
    await Promise.all(pendentes.map(startUpload));
  }

  // ── Reordenação (drag & drop) ─────────────────────────────────────────────
  function handleTileDragStart(fotoId: number) {
    if (readOnly) return;
    setDragPhotoId(fotoId);
  }

  function handleTileDragOverIndex(e: DragEvent<HTMLLIElement>, idx: number) {
    if (dragPhotoId === null || readOnly) return;
    e.preventDefault();
    setDropTargetIndex(idx);
  }

  function handleTileDragEnd() {
    setDragPhotoId(null);
    setDropTargetIndex(null);
  }

  async function handleTileDrop(e: DragEvent<HTMLLIElement>, dropIdx: number) {
    if (dragPhotoId === null || readOnly) return;
    e.preventDefault();
    const fromIdx = photos.findIndex((p) => p.id === dragPhotoId);
    setDragPhotoId(null);
    setDropTargetIndex(null);
    if (fromIdx === -1 || fromIdx === dropIdx) return;

    // Reordena localmente (otimista) e envia ao backend.
    const anterior = photos;
    const proximo = [...photos];
    const [moved] = proximo.splice(fromIdx, 1);
    proximo.splice(dropIdx, 0, moved);
    setPhotos(proximo);

    try {
      const atualizadas = await reorderPhotos(
        atividadeId,
        proximo.map((p) => p.id),
      );
      setPhotos(atualizadas);
    } catch (e) {
      setPhotos(anterior);
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível reordenar as fotos.",
        "error",
      );
    }
  }

  // ── Edição inline de legenda ──────────────────────────────────────────────
  function beginEdit(foto: EvidencePhoto) {
    setEditingId(foto.id);
    setEditingLegenda(foto.legenda ?? "");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingLegenda("");
  }

  async function commitEdit(fotoId: number) {
    const trimmed = editingLegenda.trim();
    const alvo = photos.find((p) => p.id === fotoId);
    if (!alvo) return;
    if (alvo.legenda === trimmed) {
      cancelEdit();
      return;
    }
    setSavingEditId(fotoId);
    try {
      const atualizada = await updatePhoto(atividadeId, fotoId, {
        legenda: trimmed,
      });
      setPhotos((prev) => prev.map((p) => (p.id === fotoId ? atualizada : p)));
      cancelEdit();
    } catch (e) {
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível salvar a legenda.",
        "error",
      );
    } finally {
      setSavingEditId(null);
    }
  }

  // ── Remoção ───────────────────────────────────────────────────────────────
  async function confirmarRemocao() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiDeletePhoto(atividadeId, deleteTarget.id);
      setPhotos((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      showToast("Foto removida.", "success");
      setDeleteTarget(null);
    } catch (e) {
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível remover a foto.",
        "error",
      );
    } finally {
      setDeleting(false);
    }
  }

  const temPendentesParaEnviar = useMemo(
    () => uploads.some((u) => u.phase === "staged" || u.phase === "error"),
    [uploads],
  );
  const enviandoAlgum = useMemo(
    () => uploads.some((u) => u.phase === "uploading" || u.phase === "confirming"),
    [uploads],
  );

  return (
    <section aria-label="Fotos da atividade" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text">Fotos</h3>
          <p className="text-xs text-text-muted">
            {photos.length}/{MAX_PHOTOS_PER_ACTIVITY} · JPEG, PNG ou WEBP · até{" "}
            {formatBytes(819_200)} por foto
          </p>
        </div>
        {!readOnly && (
          <Button
            size="sm"
            variant="secondary"
            leftIcon={<ImagePlus className="h-4 w-4" />}
            onClick={openPicker}
            disabled={!podeAdicionarMais}
          >
            Adicionar fotos
          </Button>
        )}
      </header>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={PHOTO_ACCEPTED_TYPES.join(",")}
        className="sr-only"
        multiple
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {limitMessage && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-warning-text bg-warning-bg px-3 py-2 text-sm text-warning-text"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{limitMessage}</span>
        </p>
      )}

      {loading && <GridSkeleton />}

      {!loading && loadError && (
        <ErroSection
          message={loadError}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      )}

      {!loading && !loadError && photos.length === 0 && uploads.length === 0 && (
        <EmptyState
          icon={<Camera className="h-7 w-7" />}
          title="Nenhuma foto anexada"
          description="Adicione fotos da execução da atividade."
          action={
            !readOnly && (
              <Button
                leftIcon={<ImagePlus className="h-4 w-4" />}
                onClick={openPicker}
              >
                Adicionar primeira foto
              </Button>
            )
          }
        />
      )}

      {!loading && !loadError && (photos.length > 0 || uploads.length > 0) && (
        <div
          onDragOver={handleTrayDragOver}
          onDragLeave={() => setDragOverTray(false)}
          onDrop={handleTrayDrop}
          className={`rounded-lg border-2 border-dashed p-3 transition-colors ${
            dragOverTray
              ? "border-primary bg-surface-warm"
              : "border-border bg-surface"
          }`}
        >
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {photos.map((foto, idx) => (
              <li
                key={`p-${foto.id}`}
                draggable={!readOnly}
                onDragStart={() => handleTileDragStart(foto.id)}
                onDragOver={(e) => handleTileDragOverIndex(e, idx)}
                onDragEnd={handleTileDragEnd}
                onDrop={(e) => handleTileDrop(e, idx)}
                className={`group relative flex flex-col overflow-hidden rounded-md border bg-surface transition ${
                  dropTargetIndex === idx
                    ? "border-primary ring-2 ring-primary/40"
                    : "border-border"
                } ${dragPhotoId === foto.id ? "opacity-40" : ""}`}
              >
                <PhotoTile
                  foto={foto}
                  isCover={idx === 0}
                  editing={editingId === foto.id}
                  editingLegenda={editingLegenda}
                  saving={savingEditId === foto.id}
                  readOnly={readOnly}
                  onLegendaChange={setEditingLegenda}
                  onBeginEdit={() => beginEdit(foto)}
                  onCancelEdit={cancelEdit}
                  onCommitEdit={() => commitEdit(foto.id)}
                  onRemove={() => setDeleteTarget(foto)}
                />
              </li>
            ))}
            {uploads.map((u) => (
              <li
                key={`u-${u.localId}`}
                className="flex flex-col overflow-hidden rounded-md border border-dashed border-primary/50 bg-surface"
              >
                <UploadTile
                  upload={u}
                  onLegendaChange={(v) => patchUpload(u.localId, { legenda: v })}
                  onRemove={() => removeUpload(u.localId)}
                  onRetry={() => startUpload(u)}
                />
              </li>
            ))}
          </ul>

          <p className="mt-3 text-xs text-text-muted">
            {vagasRestantes > 0
              ? `Você pode adicionar mais ${vagasRestantes} foto${vagasRestantes === 1 ? "" : "s"}.`
              : "Limite atingido. Remova uma foto para adicionar outra."}
          </p>
        </div>
      )}

      {uploads.length > 0 && !readOnly && (
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => uploads.forEach((u) => removeUpload(u.localId))}
            disabled={enviandoAlgum}
          >
            Cancelar tudo
          </Button>
          <Button
            size="sm"
            onClick={enviarPendentes}
            disabled={!temPendentesParaEnviar || enviandoAlgum}
            loading={enviandoAlgum}
          >
            Enviar {uploads.filter((u) => u.phase !== "uploading" && u.phase !== "confirming").length} foto
            {uploads.filter((u) => u.phase !== "uploading" && u.phase !== "confirming").length === 1 ? "" : "s"}
          </Button>
        </div>
      )}

      <SlideOver
        open={deleteTarget !== null}
        onClose={deleting ? () => {} : () => setDeleteTarget(null)}
        title="Remover foto"
        footer={
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={confirmarRemocao}
              loading={deleting}
            >
              Confirmar
            </Button>
          </div>
        }
      >
        <div className="flex items-start gap-3 px-4 py-6">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-error-bg text-error-text">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <p className="text-sm text-text">
            Tem certeza que deseja remover esta foto? Esta ação não pode ser
            desfeita.
          </p>
        </div>
      </SlideOver>
    </section>
  );
}

// ── Sub-componentes ─────────────────────────────────────────────────────────

function PhotoTile({
  foto,
  isCover,
  editing,
  editingLegenda,
  saving,
  readOnly,
  onLegendaChange,
  onBeginEdit,
  onCancelEdit,
  onCommitEdit,
  onRemove,
}: {
  foto: EvidencePhoto;
  isCover: boolean;
  editing: boolean;
  editingLegenda: string;
  saving: boolean;
  readOnly: boolean;
  onLegendaChange: (v: string) => void;
  onBeginEdit: () => void;
  onCancelEdit: () => void;
  onCommitEdit: () => void;
  onRemove: () => void;
}) {
  return (
    <>
      <div className="relative aspect-square w-full bg-surface-muted">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={foto.arquivo_url}
          alt={foto.legenda || "Foto da atividade"}
          className="h-full w-full object-cover"
          draggable={false}
        />

        {isCover && (
          <span
            className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-primary/90 px-2 py-0.5 text-2xs font-semibold text-surface shadow-sm"
            title="Foto de capa"
          >
            <Star className="h-3 w-3" aria-hidden="true" />
            Capa
          </span>
        )}

        {foto.pendente_sincronizacao && <PendenteBadge />}

        {!readOnly && (
          <div className="absolute inset-x-0 top-0 flex items-center justify-between p-1.5 opacity-0 transition-opacity group-hover:opacity-100">
            <span
              className="inline-flex h-6 items-center gap-1 rounded bg-black/60 px-1.5 text-2xs text-white"
              aria-hidden="true"
            >
              <GripVertical className="h-3 w-3" />
              Arraste para reordenar
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1 p-2">
        {editing ? (
          <div className="flex flex-col gap-1">
            <label className="sr-only" htmlFor={`legenda-${foto.id}`}>
              Legenda
            </label>
            <input
              id={`legenda-${foto.id}`}
              type="text"
              autoFocus
              maxLength={255}
              value={editingLegenda}
              onChange={(e) => onLegendaChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  onCommitEdit();
                }
                if (e.key === "Escape") {
                  e.preventDefault();
                  onCancelEdit();
                }
              }}
              className="h-7 rounded border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary"
              placeholder="Descreva a foto..."
            />
            <div className="flex items-center justify-end gap-1">
              <button
                type="button"
                onClick={onCancelEdit}
                disabled={saving}
                className="rounded p-1 text-text-muted hover:bg-surface-muted"
                aria-label="Cancelar edição"
              >
                <X className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={onCommitEdit}
                disabled={saving}
                className="rounded p-1 text-success-text hover:bg-success-bg"
                aria-label="Salvar legenda"
              >
                {saving ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={readOnly ? undefined : onBeginEdit}
            disabled={readOnly}
            className="group/legenda flex items-start gap-1 rounded text-left text-xs text-text-muted enabled:hover:text-text"
            title={readOnly ? undefined : "Clique para editar a legenda"}
          >
            <span className="line-clamp-2 flex-1 break-words">
              {foto.legenda || (
                <span className="italic text-text-muted">Sem legenda</span>
              )}
            </span>
            {!readOnly && (
              <Pencil className="mt-0.5 h-3 w-3 shrink-0 opacity-0 group-hover/legenda:opacity-100" />
            )}
          </button>
        )}

        {!readOnly && !editing && (
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={onRemove}
              className="inline-flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-error-bg hover:text-error-text"
              title="Remover foto"
              aria-label="Remover foto"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function UploadTile({
  upload,
  onLegendaChange,
  onRemove,
  onRetry,
}: {
  upload: StagedUpload;
  onLegendaChange: (v: string) => void;
  onRemove: () => void;
  onRetry: () => void;
}) {
  const busy = upload.phase === "uploading" || upload.phase === "confirming";
  return (
    <>
      <div className="relative aspect-square w-full bg-surface-muted">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={upload.previewUrl}
          alt=""
          className="h-full w-full object-cover"
        />
        <span className="absolute left-2 top-2 rounded-full bg-primary/90 px-2 py-0.5 text-2xs font-semibold text-surface">
          Nova
        </span>
        {busy && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/60 text-white">
            {upload.phase === "uploading" ? (
              <>
                <span
                  role="progressbar"
                  aria-valuenow={upload.progress}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Progresso do envio de ${upload.file.name}`}
                  className="h-1.5 w-24 overflow-hidden rounded-full bg-white/30"
                >
                  <span
                    className="block h-full rounded-full bg-white transition-[width]"
                    style={{ width: `${upload.progress}%` }}
                  />
                </span>
                <span className="text-2xs tabular-nums">{upload.progress}%</span>
              </>
            ) : (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="text-2xs">Confirmando…</span>
              </>
            )}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-1 p-2">
        <label className="sr-only" htmlFor={`nova-${upload.localId}`}>
          Legenda
        </label>
        <input
          id={`nova-${upload.localId}`}
          type="text"
          maxLength={255}
          value={upload.legenda}
          onChange={(e) => onLegendaChange(e.target.value)}
          disabled={busy}
          className="h-7 rounded border border-border bg-surface px-2 text-xs text-text outline-none focus:border-primary disabled:opacity-60"
          placeholder="Legenda (opcional)"
        />
        <p className="truncate text-2xs text-text-muted" title={upload.file.name}>
          {upload.file.name} · {formatBytes(upload.file.size)}
        </p>
        {upload.phase === "error" && upload.error && (
          <p role="alert" className="text-2xs text-error-text">
            {upload.error}
          </p>
        )}
        <div className="flex items-center justify-end gap-1">
          {upload.phase === "error" && (
            <button
              type="button"
              onClick={onRetry}
              className="text-2xs font-medium text-primary hover:underline"
            >
              Tentar novamente
            </button>
          )}
          <button
            type="button"
            onClick={onRemove}
            disabled={busy}
            className="inline-flex h-6 w-6 items-center justify-center rounded text-text-muted hover:bg-surface-muted disabled:opacity-40"
            aria-label="Descartar"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </>
  );
}

function PendenteBadge() {
  return (
    <span
      title="Registro ainda não confirmado pelo backend (aguardando sincronização SCA)."
      className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-warning-bg px-2 py-0.5 text-2xs font-semibold text-warning-text"
    >
      <CloudOff className="h-3 w-3" aria-hidden="true" />
      Pendente
    </span>
  );
}

function GridSkeleton() {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <li
          key={i}
          className="aspect-square rounded-md border border-border bg-surface-muted"
        />
      ))}
    </ul>
  );
}

function ErroSection({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-surface px-6 py-8 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        Tentar novamente
      </Button>
    </div>
  );
}
