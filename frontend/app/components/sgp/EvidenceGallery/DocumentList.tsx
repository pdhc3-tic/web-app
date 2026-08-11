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
  Download,
  FilePlus,
  FileText,
  Loader2,
  Pencil,
  Trash2,
  X,
  CloudOff,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Select } from "@/app/components/ui/Select/Select";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { absoluteDateTime, formatDate, relativeTime } from "@/app/lib/datetime";
import { ApiError } from "@/app/lib/api";
import {
  confirmDocument,
  deleteDocument as apiDeleteDocument,
  getDocumentDownloadUrl,
  listDocuments,
  requestDocumentUploadUrl,
  updateDocument,
  uploadBlobToStorage,
} from "./evidenceApi";
import { validateDocument } from "./validation";
import {
  DOCUMENT_ACCEPTED_TYPES,
  MAX_DOCUMENTS_PER_ACTIVITY,
  TIPO_DOC_ATIVIDADE_OPTIONS,
  formatBytes,
  tipoDocumentoAtividadeLabel,
  type EvidenceDocument,
  type TipoDocumentoAtividade,
} from "./types";

type UploadPhase = "staged" | "uploading" | "confirming" | "error";

type StagedDoc = {
  localId: string;
  file: File;
  tipo: TipoDocumentoAtividade | "";
  descricao: string;
  data_documento: string;
  progress: number;
  phase: UploadPhase;
  error?: string;
};

type Props = {
  atividadeId: string;
  readOnly?: boolean;
};

const HOJE = () => new Date().toISOString().slice(0, 10);

export function DocumentList({ atividadeId, readOnly = false }: Props) {
  const { showToast } = useToast();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const abortsRef = useRef<Map<string, AbortController>>(new Map());

  const [docs, setDocs] = useState<EvidenceDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [uploads, setUploads] = useState<StagedDoc[]>([]);
  const [limitMessage, setLimitMessage] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingTipo, setEditingTipo] =
    useState<TipoDocumentoAtividade | "">("");
  const [editingDescricao, setEditingDescricao] = useState("");
  const [savingEditId, setSavingEditId] = useState<number | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<EvidenceDocument | null>(
    null,
  );
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setLoadError(null);
    listDocuments(atividadeId, controller.signal)
      .then((data) => setDocs(data))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar os documentos.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [atividadeId, reloadKey]);

  useEffect(() => {
    const aborts = abortsRef.current;
    return () => {
      for (const c of aborts.values()) c.abort();
      aborts.clear();
    };
  }, []);

  const totalOcupado = docs.length + uploads.length;
  const podeAdicionarMais = totalOcupado < MAX_DOCUMENTS_PER_ACTIVITY;
  const vagasRestantes = Math.max(
    0,
    MAX_DOCUMENTS_PER_ACTIVITY - totalOcupado,
  );

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const list = Array.from(files);
      if (list.length === 0) return;

      setLimitMessage(null);
      const staged: StagedDoc[] = [];
      const rejeitados: string[] = [];
      let restantes = MAX_DOCUMENTS_PER_ACTIVITY - (docs.length + uploads.length);

      for (const file of list) {
        if (restantes <= 0) {
          setLimitMessage(
            `Máximo de ${MAX_DOCUMENTS_PER_ACTIVITY} documentos por atividade.`,
          );
          break;
        }
        const result = validateDocument(file);
        if (!result.valid) {
          rejeitados.push(result.message);
          continue;
        }
        staged.push({
          localId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          file,
          tipo: "",
          descricao: "",
          data_documento: HOJE(),
          progress: 0,
          phase: "staged",
        });
        restantes--;
      }

      if (rejeitados.length > 0) showToast(rejeitados.join("\n"), "error");
      if (staged.length > 0) setUploads((prev) => [...prev, ...staged]);
    },
    [docs.length, uploads.length, showToast],
  );

  function openPicker() {
    if (readOnly || !podeAdicionarMais) return;
    inputRef.current?.click();
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    setDragOver(true);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    if (readOnly) return;
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  }

  const patchUpload = useCallback(
    (localId: string, patch: Partial<StagedDoc>) => {
      setUploads((prev) =>
        prev.map((u) => (u.localId === localId ? { ...u, ...patch } : u)),
      );
    },
    [],
  );

  const removeUpload = useCallback((localId: string) => {
    abortsRef.current.get(localId)?.abort();
    abortsRef.current.delete(localId);
    setUploads((prev) => prev.filter((u) => u.localId !== localId));
  }, []);

  async function startUpload(upload: StagedDoc) {
    // Requerimos tipo e data antes do envio — ambos são não-nulos no backend.
    if (!upload.tipo || !upload.data_documento) {
      patchUpload(upload.localId, {
        phase: "error",
        error: "Preencha tipo e data antes de enviar.",
      });
      return;
    }

    const controller = new AbortController();
    abortsRef.current.set(upload.localId, controller);

    patchUpload(upload.localId, {
      phase: "uploading",
      progress: 0,
      error: undefined,
    });

    try {
      const uploadInfo = await requestDocumentUploadUrl(atividadeId, {
        filename: upload.file.name,
        content_type: upload.file.type,
        size: upload.file.size,
      });

      await uploadBlobToStorage(
        uploadInfo.url,
        upload.file,
        upload.file.type,
        (percent) => patchUpload(upload.localId, { progress: percent }),
        controller.signal,
      );

      patchUpload(upload.localId, { phase: "confirming" });
      const saved = await confirmDocument(atividadeId, {
        key: uploadInfo.key,
        tipo: upload.tipo,
        descricao: upload.descricao.trim(),
        nome_original: upload.file.name,
        data_documento: upload.data_documento,
      });

      abortsRef.current.delete(upload.localId);
      setUploads((prev) => prev.filter((u) => u.localId !== upload.localId));
      setDocs((prev) => [saved, ...prev]);
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
      (u) =>
        (u.phase === "staged" || u.phase === "error") &&
        u.tipo &&
        u.data_documento,
    );
    if (pendentes.length === 0) return;
    await Promise.all(pendentes.map(startUpload));
  }

  function beginEdit(doc: EvidenceDocument) {
    setEditingId(doc.id);
    setEditingTipo(doc.tipo);
    setEditingDescricao(doc.descricao ?? "");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingTipo("");
    setEditingDescricao("");
  }

  async function commitEdit(docId: number) {
    if (!editingTipo) {
      showToast("Selecione um tipo.", "error");
      return;
    }
    const alvo = docs.find((d) => d.id === docId);
    if (!alvo) return;
    const proximaDescricao = editingDescricao.trim();
    if (alvo.tipo === editingTipo && alvo.descricao === proximaDescricao) {
      cancelEdit();
      return;
    }
    setSavingEditId(docId);
    try {
      const atualizado = await updateDocument(atividadeId, docId, {
        tipo: editingTipo,
        descricao: proximaDescricao,
      });
      setDocs((prev) => prev.map((d) => (d.id === docId ? atualizado : d)));
      cancelEdit();
    } catch (e) {
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível salvar o documento.",
        "error",
      );
    } finally {
      setSavingEditId(null);
    }
  }

  async function handleDownload(doc: EvidenceDocument) {
    try {
      const url = await getDocumentDownloadUrl(atividadeId, doc.id);
      // Nova aba com noopener — evita passar contexto para o R2.
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível gerar o link de download.",
        "error",
      );
    }
  }

  async function confirmarRemocao() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiDeleteDocument(atividadeId, deleteTarget.id);
      setDocs((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      showToast("Documento removido.", "success");
      setDeleteTarget(null);
    } catch (e) {
      showToast(
        e instanceof ApiError
          ? e.message
          : "Não foi possível remover o documento.",
        "error",
      );
    } finally {
      setDeleting(false);
    }
  }

  const temPendentesValidos = useMemo(
    () =>
      uploads.some(
        (u) =>
          (u.phase === "staged" || u.phase === "error") &&
          u.tipo &&
          u.data_documento,
      ),
    [uploads],
  );
  const enviandoAlgum = useMemo(
    () =>
      uploads.some((u) => u.phase === "uploading" || u.phase === "confirming"),
    [uploads],
  );

  return (
    <section aria-label="Documentos da atividade" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text">Documentos</h3>
          <p className="text-xs text-text-muted">
            {docs.length}/{MAX_DOCUMENTS_PER_ACTIVITY} · PDF · até{" "}
            {formatBytes(10 * 1024 * 1024)} por arquivo
          </p>
        </div>
        {!readOnly && (
          <Button
            size="sm"
            variant="secondary"
            leftIcon={<FilePlus className="h-4 w-4" />}
            onClick={openPicker}
            disabled={!podeAdicionarMais}
          >
            Adicionar documentos
          </Button>
        )}
      </header>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={DOCUMENT_ACCEPTED_TYPES.join(",")}
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

      {loading && <ListaSkeleton />}

      {!loading && loadError && (
        <ErroSection
          message={loadError}
          onRetry={() => setReloadKey((k) => k + 1)}
        />
      )}

      {!loading && !loadError && docs.length === 0 && uploads.length === 0 && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`rounded-lg border-2 border-dashed transition-colors ${
            dragOver ? "border-primary bg-surface-warm" : "border-border"
          }`}
        >
          <EmptyState
            icon={<FileText className="h-7 w-7" />}
            title="Nenhum documento anexado"
            description="Anexe listas de presença, atas, contratos e outros PDFs da atividade."
            action={
              !readOnly && (
                <Button
                  leftIcon={<FilePlus className="h-4 w-4" />}
                  onClick={openPicker}
                >
                  Adicionar primeiro documento
                </Button>
              )
            }
          />
        </div>
      )}

      {!loading && !loadError && (docs.length > 0 || uploads.length > 0) && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`rounded-lg border-2 border-dashed p-2 transition-colors ${
            dragOver ? "border-primary bg-surface-warm" : "border-border"
          }`}
        >
          <ul className="flex flex-col divide-y divide-border">
            {docs.map((doc) => (
              <li key={`d-${doc.id}`} className="py-2">
                <DocumentRow
                  doc={doc}
                  editing={editingId === doc.id}
                  editingTipo={editingTipo}
                  editingDescricao={editingDescricao}
                  saving={savingEditId === doc.id}
                  readOnly={readOnly}
                  onTipoChange={(v) =>
                    setEditingTipo(v as TipoDocumentoAtividade | "")
                  }
                  onDescricaoChange={setEditingDescricao}
                  onBeginEdit={() => beginEdit(doc)}
                  onCancelEdit={cancelEdit}
                  onCommitEdit={() => commitEdit(doc.id)}
                  onDownload={() => handleDownload(doc)}
                  onRemove={() => setDeleteTarget(doc)}
                />
              </li>
            ))}
            {uploads.map((u) => (
              <li key={`u-${u.localId}`} className="py-2">
                <UploadRow
                  upload={u}
                  onTipoChange={(v) =>
                    patchUpload(u.localId, {
                      tipo: v as TipoDocumentoAtividade | "",
                    })
                  }
                  onDescricaoChange={(v) =>
                    patchUpload(u.localId, { descricao: v })
                  }
                  onDataChange={(v) =>
                    patchUpload(u.localId, { data_documento: v })
                  }
                  onRemove={() => removeUpload(u.localId)}
                  onRetry={() => startUpload(u)}
                />
              </li>
            ))}
          </ul>

          <p className="px-2 pt-2 text-xs text-text-muted">
            {vagasRestantes > 0
              ? `Você pode adicionar mais ${vagasRestantes} documento${vagasRestantes === 1 ? "" : "s"}.`
              : "Limite atingido. Remova um documento para adicionar outro."}
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
            disabled={!temPendentesValidos || enviandoAlgum}
            loading={enviandoAlgum}
          >
            Enviar pendentes
          </Button>
        </div>
      )}

      <SlideOver
        open={deleteTarget !== null}
        onClose={deleting ? () => {} : () => setDeleteTarget(null)}
        title="Remover documento"
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
            Tem certeza que deseja remover{" "}
            <span className="font-semibold">
              {deleteTarget?.nome_original}
            </span>
            ? Esta ação não pode ser desfeita.
          </p>
        </div>
      </SlideOver>
    </section>
  );
}

// ── Sub-componentes ─────────────────────────────────────────────────────────

function DocumentRow({
  doc,
  editing,
  editingTipo,
  editingDescricao,
  saving,
  readOnly,
  onTipoChange,
  onDescricaoChange,
  onBeginEdit,
  onCancelEdit,
  onCommitEdit,
  onDownload,
  onRemove,
}: {
  doc: EvidenceDocument;
  editing: boolean;
  editingTipo: TipoDocumentoAtividade | "";
  editingDescricao: string;
  saving: boolean;
  readOnly: boolean;
  onTipoChange: (v: string) => void;
  onDescricaoChange: (v: string) => void;
  onBeginEdit: () => void;
  onCancelEdit: () => void;
  onCommitEdit: () => void;
  onDownload: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-start gap-3 rounded-md px-2 py-2 hover:bg-surface-muted/40">
      <FileText className="mt-0.5 h-5 w-5 shrink-0 text-error-text" aria-label="PDF" />

      <div className="min-w-0 flex-1">
        {editing ? (
          <div className="flex flex-col gap-2">
            <Select
              label="Tipo"
              value={editingTipo}
              onChange={onTipoChange}
              options={TIPO_DOC_ATIVIDADE_OPTIONS.map((o) => ({
                value: o.value,
                label: o.label,
              }))}
              placeholder="Selecione..."
            />
            <label className="flex flex-col gap-1 text-xs">
              <span className="font-medium text-text">Descrição</span>
              <input
                type="text"
                value={editingDescricao}
                onChange={(e) => onDescricaoChange(e.target.value)}
                maxLength={255}
                className="h-8 rounded border border-border bg-surface px-2 text-sm text-text outline-none focus:border-primary"
                placeholder="Descreva o documento..."
              />
            </label>
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
                aria-label="Salvar alterações"
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
          <>
            <div className="flex flex-wrap items-center gap-2">
              <TipoBadge tipo={doc.tipo} label={doc.tipo_display} />
              {doc.pendente_sincronizacao && <PendenteChip />}
            </div>
            <p className="mt-1 truncate text-sm font-medium text-text" title={doc.nome_original}>
              {doc.descricao || doc.nome_original}
            </p>
            {doc.descricao && (
              <p className="truncate text-xs text-text-muted" title={doc.nome_original}>
                {doc.nome_original}
              </p>
            )}
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
              <span>{formatDate(doc.data_documento) || "—"}</span>
              <span aria-hidden="true">·</span>
              <span className="font-mono tabular-nums">
                {formatBytes(doc.tamanho_bytes)}
              </span>
              <span aria-hidden="true">·</span>
              <span title={absoluteDateTime(doc.criado_em)}>
                anexado {relativeTime(doc.criado_em)}
              </span>
            </p>
          </>
        )}
      </div>

      {!editing && (
        <div className="flex shrink-0 items-center gap-1">
          <IconAction
            title="Baixar"
            onClick={onDownload}
            icon={<Download className="h-4 w-4" />}
          />
          {!readOnly && (
            <>
              <IconAction
                title="Editar"
                onClick={onBeginEdit}
                icon={<Pencil className="h-4 w-4" />}
              />
              <IconAction
                title="Remover"
                onClick={onRemove}
                icon={<Trash2 className="h-4 w-4" />}
                danger
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function UploadRow({
  upload,
  onTipoChange,
  onDescricaoChange,
  onDataChange,
  onRemove,
  onRetry,
}: {
  upload: StagedDoc;
  onTipoChange: (v: string) => void;
  onDescricaoChange: (v: string) => void;
  onDataChange: (v: string) => void;
  onRemove: () => void;
  onRetry: () => void;
}) {
  const busy = upload.phase === "uploading" || upload.phase === "confirming";
  return (
    <div className="flex items-start gap-3 rounded-md border border-dashed border-primary/40 bg-surface p-2">
      <FileText className="mt-0.5 h-5 w-5 shrink-0 text-error-text" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-2xs font-semibold text-primary">
            Novo
          </span>
          <p className="truncate text-sm font-medium text-text" title={upload.file.name}>
            {upload.file.name}
          </p>
          <span className="text-xs text-text-muted">
            {formatBytes(upload.file.size)}
          </span>
        </div>

        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Select
            label="Tipo"
            required
            value={upload.tipo}
            onChange={onTipoChange}
            options={TIPO_DOC_ATIVIDADE_OPTIONS.map((o) => ({
              value: o.value,
              label: o.label,
            }))}
            placeholder="Selecione..."
            disabled={busy}
          />
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-text">
              Data <span className="text-error-text">*</span>
            </span>
            <input
              type="date"
              value={upload.data_documento}
              onChange={(e) => onDataChange(e.target.value)}
              disabled={busy}
              className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none focus:border-primary disabled:opacity-60"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs sm:col-span-1">
            <span className="font-medium text-text">Descrição</span>
            <input
              type="text"
              value={upload.descricao}
              onChange={(e) => onDescricaoChange(e.target.value)}
              disabled={busy}
              maxLength={255}
              className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-text outline-none focus:border-primary disabled:opacity-60"
              placeholder="Opcional"
            />
          </label>
        </div>

        {busy && (
          <div className="mt-2 flex items-center gap-2">
            {upload.phase === "uploading" ? (
              <>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    role="progressbar"
                    aria-valuenow={upload.progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`Progresso do envio de ${upload.file.name}`}
                    className="h-full rounded-full bg-primary transition-[width]"
                    style={{ width: `${upload.progress}%` }}
                  />
                </div>
                <span className="w-9 text-right text-xs tabular-nums text-text-muted">
                  {upload.progress}%
                </span>
              </>
            ) : (
              <span className="flex items-center gap-2 text-xs text-text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Confirmando…
              </span>
            )}
          </div>
        )}

        {upload.phase === "error" && upload.error && (
          <p role="alert" className="mt-2 text-xs text-error-text">
            {upload.error}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {upload.phase === "error" && (
          <button
            type="button"
            onClick={onRetry}
            className="text-xs font-medium text-primary hover:underline"
          >
            Tentar novamente
          </button>
        )}
        <IconAction
          title="Descartar"
          onClick={onRemove}
          icon={<X className="h-4 w-4" />}
          disabled={busy}
        />
      </div>
    </div>
  );
}

function TipoBadge({
  tipo,
  label,
}: {
  tipo: TipoDocumentoAtividade | string;
  label?: string;
}) {
  const CLASS_BY_TIPO: Record<string, string> = {
    lista_presenca: "border-primary bg-primary/10 text-primary",
    ata: "border-success-text bg-success-bg text-success-text",
    relatorio_parcial: "border-warning-text bg-warning-bg text-warning-text",
    declaracao: "border-border bg-surface-muted text-text",
    contrato: "border-border bg-surface-muted text-text",
    outro: "border-border bg-surface-muted text-text-muted",
  };
  const cls = CLASS_BY_TIPO[tipo] ?? CLASS_BY_TIPO.outro;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-semibold ${cls}`}
    >
      {label ?? tipoDocumentoAtividadeLabel(tipo)}
    </span>
  );
}

function PendenteChip() {
  return (
    <span
      title="Registro ainda não confirmado pelo backend (aguardando sincronização SCA)."
      className="inline-flex items-center gap-1 rounded-full bg-warning-bg px-2 py-0.5 text-2xs font-semibold text-warning-text"
    >
      <CloudOff className="h-3 w-3" aria-hidden="true" />
      Pendente
    </span>
  );
}

function IconAction({
  title,
  onClick,
  icon,
  danger,
  disabled,
}: {
  title: string;
  onClick: () => void;
  icon: React.ReactNode;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-40 ${
        danger ? "hover:text-error-text" : "hover:text-text"
      }`}
    >
      {icon}
    </button>
  );
}

function ListaSkeleton() {
  return (
    <ul className="divide-y divide-border rounded-md border border-border bg-surface">
      {Array.from({ length: 3 }).map((_, i) => (
        <li key={i} className="flex items-center gap-3 px-4 py-3">
          <div className="h-5 w-5 rounded bg-border" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-40 rounded bg-border/70" />
            <div className="h-3 w-24 rounded bg-border/40" />
          </div>
          <div className="h-8 w-16 rounded bg-border/40" />
        </li>
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
