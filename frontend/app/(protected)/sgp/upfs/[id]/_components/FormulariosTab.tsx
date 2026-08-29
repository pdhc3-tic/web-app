"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, ClipboardList, Plus } from "lucide-react";
import { Button } from "@/app/components/ui/Button/Button";
import { EmptyState } from "@/app/components/ui/EmptyState/EmptyState";
import { Pagination } from "@/app/components/ui/Pagination/Pagination";
import Spinner from "@/app/components/icons/Spinner";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime, formatDate } from "@/app/lib/datetime";
import {
  listFormResponses,
  type FormResponseListItem,
} from "@/app/lib/formularios";
import {
  RespostaFormularioSlideOver,
  StatusChip,
} from "./RespostaFormularioSlideOver";

const PAGE_SIZE = 25;

type Props = { upfId: string };

export function FormulariosTab({ upfId }: Props) {
  const [page, setPage] = useState(1);
  const [respostas, setRespostas] = useState<FormResponseListItem[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [selecionada, setSelecionada] = useState<FormResponseListItem | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    listFormResponses(
      upfId,
      { page, page_size: PAGE_SIZE },
      controller.signal,
    )
      .then((data) => {
        setRespostas(data.results);
        setCount(data.count);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Não foi possível carregar as respostas.",
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

  if (respostas.length === 0) {
    return (
      <>
        <EmptyState
          icon={<ClipboardList className="h-7 w-7" />}
          title="Nenhuma resposta registrada"
          description="Os formulários preenchidos para esta UPF aparecerão aqui."
          action={
            <Button
              leftIcon={<Plus className="h-4 w-4" />}
              // #181 vai wire este onClick para o seletor de formulários disponíveis.
              onClick={() => {}}
              data-testid="formularios-preencher-novo"
            >
              Preencher novo formulário
            </Button>
          }
        />
        <RespostaFormularioSlideOver
          open={selecionada !== null}
          onClose={() => setSelecionada(null)}
          upfId={upfId}
          resposta={selecionada}
        />
      </>
    );
  }

  return (
    <div className="space-y-4" data-testid="formularios-tab">
      <Tabela
        respostas={respostas}
        onSelect={(r) => setSelecionada(r)}
      />

      <Pagination
        count={count}
        offset={(page - 1) * PAGE_SIZE}
        limit={PAGE_SIZE}
        onOffsetChange={(offset) => setPage(Math.floor(offset / PAGE_SIZE) + 1)}
        onLimitChange={() => {}}
        pageSizes={[PAGE_SIZE]}
        itemNoun={{ one: "resposta", other: "respostas" }}
      />

      <RespostaFormularioSlideOver
        open={selecionada !== null}
        onClose={() => setSelecionada(null)}
        upfId={upfId}
        resposta={selecionada}
      />
    </div>
  );
}

function Tabela({
  respostas,
  onSelect,
}: {
  respostas: FormResponseListItem[];
  onSelect: (r: FormResponseListItem) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full min-w-180 border-collapse text-sm">
          <thead className="bg-surface-muted text-left text-2xs font-semibold uppercase tracking-wide text-text-muted">
            <tr>
              <th className="px-4 py-2.5">Formulário</th>
              <th className="px-4 py-2.5">Versão</th>
              <th className="px-4 py-2.5">Data</th>
              <th className="px-4 py-2.5">Respondente</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {respostas.map((r) => (
              <tr
                key={r.id}
                data-testid={`formulario-row-${r.id}`}
                className="cursor-pointer border-t border-border align-middle transition hover:bg-surface-muted/40"
                onClick={() => onSelect(r)}
              >
                <td className="px-4 py-3 font-medium text-text">
                  {r.formulario_nome}
                </td>
                <td className="px-4 py-3 text-text-muted">
                  {r.formulario_versao}
                </td>
                <td
                  className="px-4 py-3 text-text-muted"
                  title={absoluteDateTime(r.data_preenchimento)}
                >
                  {formatDate(r.data_preenchimento)}
                </td>
                <td className="px-4 py-3 text-text">
                  {r.respondente?.trim() || "Anônimo"}
                </td>
                <td className="px-4 py-3">
                  <StatusChip status={r.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
