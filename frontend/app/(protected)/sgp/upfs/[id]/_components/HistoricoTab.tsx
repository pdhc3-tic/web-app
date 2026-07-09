"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, History } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { fetchUpfHistorico, type HistoricoEntry } from "@/app/lib/upfs";
import { relativeTime, absoluteDateTime } from "@/app/lib/datetime";

const PAGE_SIZE = 25;

// Rótulos legíveis para os campos cobertos pelo histórico do backend.
const FIELD_LABELS: Record<string, string> = {
  nome_titular: "o nome do titular",
  cpf: "o CPF",
  projeto_id: "o projeto",
  municipio_id: "o município",
  territorio_id: "o território",
  comunidade_id: "a comunidade",
};

// FKs vêm como *_id (valor numérico), sem nome legível — narramos sem "de/para".
const ID_FIELDS = new Set([
  "projeto_id",
  "municipio_id",
  "territorio_id",
  "comunidade_id",
]);

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

/** Monta a frase amigável de uma alteração (sem o autor nem o tempo). */
function narrate(entry: HistoricoEntry): string {
  const { campo, valor_anterior, valor_novo } = entry;

  if (campo === null) {
    return valor_anterior == null ? "criou a UPF" : "atualizou a UPF";
  }
  if (campo === "ativa") {
    return valor_novo ? "reativou a UPF" : "inativou a UPF";
  }

  const label = FIELD_LABELS[campo] ?? `o campo ${campo}`;
  if (ID_FIELDS.has(campo)) return `alterou ${label}`;

  const from = formatValue(valor_anterior);
  const to = formatValue(valor_novo);
  if (from && to) return `alterou ${label} de "${from}" para "${to}"`;
  if (to) return `definiu ${label} como "${to}"`;
  return `alterou ${label}`;
}

type HistoricoTabProps = {
  upfId: string;
};

export function HistoricoTab({ upfId }: HistoricoTabProps) {
  const [page, setPage] = useState(1);
  const [entries, setEntries] = useState<HistoricoEntry[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    fetchUpfHistorico(upfId, { page, pageSize: PAGE_SIZE }, controller.signal)
      .then((data) => {
        setEntries(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar o histórico.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [upfId, page, reloadKey]);

  if (loading) {
    return (
      <div className="flex min-h-[30vh] items-center justify-center">
        <Spinner className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-lg border border-border bg-surface px-6 py-16 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error-bg text-error-text">
          <AlertTriangle className="h-6 w-6" />
        </span>
        <p className="max-w-sm text-sm text-text-muted">{error}</p>
        <Button variant="secondary" onClick={() => setReloadKey((k) => k + 1)}>
          Tentar novamente
        </Button>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <EmptyState
        icon={<History className="h-7 w-7" />}
        title="Nenhuma alteração registrada"
        description="As alterações feitas nesta UPF aparecerão aqui."
      />
    );
  }

  return (
    <div className="space-y-4">
      <ul className="space-y-3">
        {entries.map((entry) => (
          <li
            key={entry.id}
            className="flex gap-3 rounded-lg border border-border bg-surface px-4 py-3"
          >
            <span
              aria-hidden="true"
              className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary/60"
            />
            <p className="text-sm leading-relaxed text-text">
              <span className="font-medium">
                {entry.usuario?.nome ?? "Alguém"}
              </span>{" "}
              {narrate(entry)}{" "}
              <span
                className="text-text-muted"
                title={absoluteDateTime(entry.timestamp)}
              >
                · {relativeTime(entry.timestamp) || "data desconhecida"}
              </span>
            </p>
          </li>
        ))}
      </ul>

      <Pagination
        count={count}
        offset={(page - 1) * PAGE_SIZE}
        limit={PAGE_SIZE}
        onOffsetChange={(offset) => setPage(Math.floor(offset / PAGE_SIZE) + 1)}
        onLimitChange={() => {}}
        pageSizes={[PAGE_SIZE]}
        itemNoun={{ one: "alteração", other: "alterações" }}
      />
    </div>
  );
}
