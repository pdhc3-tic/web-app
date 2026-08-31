"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Download,
  FileText,
  Plus,
  Trash2,
} from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { useToast } from "@/app/components/ui/Toast/Toast";
import { absoluteDateTime, formatDate, relativeTime } from "@/app/lib/datetime";
import { FileTypeIcon } from "./FileTypeIcon";
import {
  downloadDocumento,
  listDocumentos,
  tipoDocumentoLabel,
  type Documento,
  type TipoDocumento,
} from "@/app/lib/upfDocumentos";
import { DocumentoSlideOver } from "./DocumentoSlideOver";
import { RemoverDocumentoDialog } from "./RemoverDocumentoDialog";

type Props = { upfId: string };
type SortKey = "tipo" | "descricao" | "data_documento" | "tamanho_bytes" | "criado_em" | "criado_por";
type SortDir = "asc" | "desc";

const SORTABLE_COLUMNS: { key: SortKey; label: string }[] = [
  { key: "tipo", label: "Tipo" },
  { key: "descricao", label: "Descrição" },
  { key: "data_documento", label: "Data do documento" },
  { key: "tamanho_bytes", label: "Tamanho" },
  { key: "criado_em", label: "Adicionado em" },
  { key: "criado_por", label: "Adicionado por" },
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function DocumentosTab({ upfId }: Props) {
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [slideOverOpen, setSlideOverOpen] = useState(false);
  const [remover, setRemover] = useState<Documento | null>(null);
  const { showToast } = useToast();
  const [sortKey, setSortKey] = useState<SortKey>("criado_em");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    listDocumentos(upfId, controller.signal)
      .then((data) => setDocumentos(data))
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : "Não foi possível carregar os documentos.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [upfId, reloadKey]);

  const ordenados = useMemo(() => {
    const arr = [...documentos];
    arr.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      let cmp = 0;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv), "pt-BR");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [documentos, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "criado_em" || key === "data_documento" ? "desc" : "asc");
    }
  }

  function handleSaved(saved: Documento) {
    setDocumentos((prev) => [saved, ...prev]);
    showToast("Documento adicionado.");
    setSlideOverOpen(false);
  }

  function handleDeleted(id: number) {
    setDocumentos((prev) => prev.filter((d) => d.id !== id));
    setRemover(null);
    showToast("Documento removido.");
  }

  async function handleDownload(doc: Documento) {
    try {
      await downloadDocumento(upfId, doc);
    } catch {
      showToast("Falha ao baixar o arquivo.", "error");
    }
  }

  return (
    <div className="space-y-4">
      {!loading && !error && documentos.length > 0 && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-text-muted">
            {documentos.length}{" "}
            {documentos.length === 1 ? "documento anexado" : "documentos anexados"}
          </p>
          <Button size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setSlideOverOpen(true)}>
            Adicionar documento
          </Button>
        </div>
      )}

      {loading && <TabelaSkeleton />}

      {!loading && error && <ErroSection message={error} onRetry={() => setReloadKey((k) => k + 1)} />}

      {!loading && !error && documentos.length === 0 && (
        <EmptyState
          icon={<FileText className="h-7 w-7" />}
          title="Nenhum documento anexado"
          description="Adicione DAPs, contratos, laudos e outros documentos da UPF."
          action={
            <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setSlideOverOpen(true)}>
              Adicionar primeiro documento
            </Button>
          }
        />
      )}

      {!loading && !error && documentos.length > 0 && (
        <Tabela
          documentos={ordenados}
          sortKey={sortKey}
          sortDir={sortDir}
          onSort={toggleSort}
          onDownload={handleDownload}
          onRemove={(d) => setRemover(d)}
        />
      )}

      <DocumentoSlideOver
        open={slideOverOpen}
        onClose={() => setSlideOverOpen(false)}
        upfId={upfId}
        onSaved={handleSaved}
      />

      <RemoverDocumentoDialog
        open={remover !== null}
        onClose={() => setRemover(null)}
        upfId={upfId}
        documentoId={remover?.id ?? null}
        nome={remover?.nome_original ?? ""}
        onDeleted={handleDeleted}
      />
    </div>
  );
}

function Tabela({
  documentos,
  sortKey,
  sortDir,
  onSort,
  onDownload,
  onRemove,
}: {
  documentos: Documento[];
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (k: SortKey) => void;
  onDownload: (d: Documento) => void;
  onRemove: (d: Documento) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-200 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              {SORTABLE_COLUMNS.map((col) => (
                <th key={col.key} className="px-4 py-2.5">
                  <SortButton
                    label={col.label}
                    active={sortKey === col.key}
                    dir={sortDir}
                    onClick={() => onSort(col.key)}
                  />
                </th>
              ))}
              <th className="px-4 py-2.5 text-right">Ações</th>
            </tr>
          </thead>
          <tbody>
            {documentos.map((d) => (
              <tr key={d.id} className="border-t border-border align-middle transition hover:bg-surface-muted/40">
                <td className="px-4 py-3">
                  <TipoBadge tipo={d.tipo} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <FileTypeIcon contentType={d.content_type} />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-text">
                        {d.descricao || d.nome_original}
                      </p>
                      {d.descricao && (
                        <p className="truncate text-xs text-text-muted">{d.nome_original}</p>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-text-muted">{formatDate(d.data_documento) || "—"}</td>
                <td className="px-4 py-3 font-mono tabular-nums text-text-muted">{formatBytes(d.tamanho_bytes)}</td>
                <td className="px-4 py-3 text-text-muted" title={absoluteDateTime(d.criado_em)}>
                  {relativeTime(d.criado_em)}
                </td>
                <td className="px-4 py-3 text-text-muted">{d.criado_por}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <AcaoIcone title="Baixar" onClick={() => onDownload(d)} icon={<Download className="h-4 w-4" />} />
                    <AcaoIcone title="Remover" onClick={() => onRemove(d)} icon={<Trash2 className="h-4 w-4" />} danger />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SortButton({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 uppercase tracking-wide text-text-muted transition hover:text-text"
    >
      {label}
      {active ? (
        dir === "asc" ? (
          <ArrowUp className="h-3 w-3" />
        ) : (
          <ArrowDown className="h-3 w-3" />
        )
      ) : (
        <ArrowUpDown className="h-3 w-3 opacity-40" />
      )}
    </button>
  );
}

function TipoBadge({ tipo }: { tipo: TipoDocumento }) {
  const map: Record<TipoDocumento, string> = {
    dap_caf: "border-success-text bg-success-bg text-success-text",
    contrato: "border-primary bg-primary/10 text-primary",
    laudo: "border-warning-text bg-warning-bg text-warning-text",
    identidade: "border-border bg-surface-muted text-text",
    outro: "border-border bg-surface-muted text-text-muted",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-semibold ${map[tipo]}`}>
      {tipoDocumentoLabel(tipo)}
    </span>
  );
}

function AcaoIcone({
  title,
  onClick,
  icon,
  danger,
}: {
  title: string;
  onClick: () => void;
  icon: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition hover:bg-surface-muted ${
        danger ? "hover:text-error-text" : "hover:text-text"
      }`}
    >
      {icon}
    </button>
  );
}

function TabelaSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="border-b border-border bg-surface-muted px-4 py-2.5">
        <div className="h-3 w-24 rounded bg-border" />
      </div>
      <ul className="divide-y divide-border">
        {Array.from({ length: 3 }).map((_, i) => (
          <li key={i} className="flex items-center gap-4 px-4 py-4">
            <div className="h-4 w-20 rounded bg-border/70" />
            <div className="h-4 w-56 rounded bg-border/50" />
            <div className="h-4 w-20 rounded bg-border/50" />
            <div className="ml-auto h-4 w-24 rounded bg-border/50" />
          </li>
        ))}
      </ul>
    </div>
  );
}

function ErroSection({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
        <AlertTriangle className="h-6 w-6" />
      </span>
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
      <Button variant="secondary" onClick={onRetry}>Tentar novamente</Button>
    </div>
  );
}

