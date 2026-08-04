"use client";

import { useEffect, useRef, useState } from "react";
import { Upload, X } from "lucide-react";
import { SlideOver } from "@/app/components/ui/SlideOver/SlideOver";
import { Button } from "@/app/components/ui/Button/Button";
import { Input } from "@/app/components/ui/Input/Input";
import { Select } from "@/app/components/ui/Select/Select";
import { Textarea } from "@/app/components/ui/Textarea/Textarea";
import { FileTypeIcon } from "./FileTypeIcon";
import {
  uploadDocumentoMock,
  type UploadHandle,
} from "./documentoMock";
import {
  ACCEPTED_CONTENT_TYPES,
  MAX_DOC_SIZE_BYTES,
  TIPO_DOC_OPTIONS,
  type Documento,
  type TipoDocumento,
} from "./documentoTypes";

type Props = {
  open: boolean;
  onClose: () => void;
  upfId: string;
  onSaved: (d: Documento) => void;
};

type FormState = {
  tipo: TipoDocumento | "";
  descricao: string;
  data_documento: string;
  file: File | null;
};

const EMPTY: FormState = { tipo: "", descricao: "", data_documento: "", file: null };

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function validateFile(file: File): string | null {
  if (!ACCEPTED_CONTENT_TYPES.includes(file.type as (typeof ACCEPTED_CONTENT_TYPES)[number])) {
    return "Tipo de arquivo inválido. Envie PDF, JPG ou PNG.";
  }
  if (file.size > MAX_DOC_SIZE_BYTES) {
    return `Arquivo excede o tamanho máximo de ${formatBytes(MAX_DOC_SIZE_BYTES)}.`;
  }
  return null;
}

export function DocumentoSlideOver({ open, onClose, upfId, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const uploadRef = useRef<UploadHandle | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm(EMPTY);
    setErrors({});
    setGlobalError(null);
    setProgress(0);
    setUploading(false);
    return () => {
      uploadRef.current?.abort();
      uploadRef.current = null;
    };
  }, [open]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => {
      if (!(key in e)) return e;
      const next = { ...e };
      delete next[key as string];
      return next;
    });
  }

  function pickFile(file: File | null) {
    if (!file) {
      update("file", null);
      return;
    }
    const err = validateFile(file);
    if (err) {
      setErrors((e) => ({ ...e, file: err }));
      update("file", null);
      return;
    }
    update("file", file);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (uploading) return;
    const file = e.dataTransfer.files?.[0];
    if (file) pickFile(file);
  }

  async function handleSave() {
    if (uploading) return;
    const errs: Record<string, string> = {};
    if (!form.tipo) errs.tipo = "Selecione o tipo.";
    if (!form.data_documento) errs.data_documento = "Informe a data do documento.";
    if (!form.file) errs.file = "Anexe um arquivo.";
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setGlobalError(null);
    setUploading(true);
    setProgress(0);

    const handle = uploadDocumentoMock(
      upfId,
      form.file!,
      {
        tipo: form.tipo as TipoDocumento,
        descricao: form.descricao.trim(),
        data_documento: form.data_documento,
      },
      (p) => setProgress(p),
    );
    uploadRef.current = handle;

    try {
      const saved = await handle.promise;
      onSaved(saved);
    } catch (e) {
      if ((e as DOMException).name !== "AbortError") {
        setGlobalError("Falha no upload. Tente novamente.");
      }
    } finally {
      uploadRef.current = null;
      setUploading(false);
    }
  }

  function handleClose() {
    if (uploading) {
      uploadRef.current?.abort();
      uploadRef.current = null;
      setUploading(false);
    }
    onClose();
  }

  return (
    <SlideOver
      open={open}
      onClose={handleClose}
      title="Adicionar documento"
      width="wide"
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={handleClose} disabled={uploading}>
            {uploading ? "Cancelar upload" : "Cancelar"}
          </Button>
          <Button onClick={handleSave} loading={uploading}>Salvar</Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5 px-4 py-4">
        {globalError && (
          <div role="alert" className="rounded-md border border-error-text bg-error-bg px-3 py-2 text-sm text-error-text">
            {globalError}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label="Tipo"
            required
            value={form.tipo}
            onChange={(v) => update("tipo", v as TipoDocumento | "")}
            options={TIPO_DOC_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            placeholder="Selecione..."
            error={errors.tipo}
          />
          <Input
            label="Data do documento"
            required
            type="date"
            value={form.data_documento}
            onChange={(e) => update("data_documento", e.target.value)}
            error={errors.data_documento}
          />
        </div>

        <Textarea
          label="Descrição"
          rows={3}
          value={form.descricao}
          onChange={(e) => update("descricao", e.target.value)}
          error={errors.descricao}
        />

        <div className="flex flex-col gap-2">
          <span className="text-label font-medium text-text">
            Arquivo <span className="ml-0.5 font-semibold text-error-text">*</span>
          </span>

          {form.file ? (
            <SelectedFile
              file={form.file}
              onRemove={() => update("file", null)}
              disabled={uploading}
            />
          ) : (
            <DropZone
              dragging={dragging}
              hasError={!!errors.file}
              onDragEnter={() => setDragging(true)}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onPick={() => fileInputRef.current?.click()}
            />
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_CONTENT_TYPES.join(",")}
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
          />

          {errors.file && <span className="text-xs text-error-text">{errors.file}</span>}
          <span className="text-xs text-text-muted">
            PDF, JPG ou PNG · até {formatBytes(MAX_DOC_SIZE_BYTES)}
          </span>
        </div>

        {uploading && <ProgressBar percent={progress} />}
      </div>
    </SlideOver>
  );
}

function DropZone({
  dragging,
  hasError,
  onDragEnter,
  onDragOver,
  onDragLeave,
  onDrop,
  onPick,
}: {
  dragging: boolean;
  hasError: boolean;
  onDragEnter: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  onPick: () => void;
}) {
  const border = hasError
    ? "border-error-text"
    : dragging
    ? "border-primary"
    : "border-border";
  const bg = dragging ? "bg-primary/5" : "bg-surface";
  return (
    <button
      type="button"
      onClick={onPick}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-4 py-8 text-center text-sm transition ${border} ${bg}`}
    >
      <Upload className="h-6 w-6 text-text-muted" />
      <span className="text-text">
        Arraste um arquivo aqui ou <span className="text-primary underline">selecione</span>
      </span>
    </button>
  );
}

function SelectedFile({
  file,
  onRemove,
  disabled,
}: {
  file: File;
  onRemove: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2">
      <FileTypeIcon contentType={file.type} className="h-5 w-5" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-text">{file.name}</p>
        <p className="text-xs text-text-muted">{formatBytes(file.size)}</p>
      </div>
      <button
        type="button"
        aria-label="Remover arquivo"
        onClick={onRemove}
        disabled={disabled}
        className="inline-flex h-7 w-7 items-center justify-center rounded text-text-muted hover:bg-surface-muted hover:text-text disabled:cursor-not-allowed disabled:opacity-40"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-150"
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-right text-xs tabular-nums text-text-muted">{percent}%</span>
    </div>
  );
}
