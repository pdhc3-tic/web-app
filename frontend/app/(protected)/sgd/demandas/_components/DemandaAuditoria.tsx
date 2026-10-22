"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDollarSign } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime } from "@/app/lib/datetime";
import {
  AUDITORIA_PAGINA,
  listAuditoriaDemanda,
  type EventoAuditoria,
  type StatusDemanda,
} from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";

/** Rótulos dos status para a trilha; o backend devolve o valor cru em `valores_*`. */
const STATUS_LABEL: Record<StatusDemanda, string> = {
  rascunho: "Rascunho",
  submetida: "Submetida",
  devolvida: "Devolvida",
  pre_autorizada: "Pré-autorizada",
  autorizada: "Autorizada",
  em_atendimento: "Em atendimento",
  concluida: "Concluída",
  recusada: "Recusada",
  cancelada: "Cancelada",
};

function rotuloStatus(valor: unknown): string {
  if (typeof valor !== "string") return "";
  return STATUS_LABEL[valor as StatusDemanda] ?? valor;
}

/**
 * Texto da ação na trilha. Para status, mostra a transição ("Submetida →
 * Pré-autorizada"); para saldo, o tipo da movimentação ("Reserva") e, quando
 * houver, o valor (liberação) ou a mudança do comprometido.
 */
function textoDaAcao(evento: EventoAuditoria): string {
  if (evento.tipo === "status") {
    if (evento.acao === "demanda.criada") {
      return `Demanda criada (${rotuloStatus(evento.valores_novos.status)})`;
    }
    const de = rotuloStatus(evento.valores_anteriores.status);
    const para = rotuloStatus(evento.valores_novos.status);
    return de ? `${de} → ${para}` : para;
  }

  const operacao = evento.acao.replace(/^saldo\./, "");
  const operacoes: Record<string, string> = {
    reserva: "Reserva de saldo",
    ajuste: "Ajuste do saldo reservado",
    execucao: "Execução do pagamento",
    liberacao: "Liberação de saldo",
    remanejamento: "Remanejamento de saldo",
  };
  const base = operacoes[operacao] ?? `Movimentação de saldo (${operacao})`;

  const valor = evento.valores_novos.valor;
  if (typeof valor === "string" || typeof valor === "number") {
    return `${base} — ${formatCurrencyBRL(valor)}`;
  }
  return base;
}

/** Rótulo humano de quem agiu — "Sistema" cobre a transição automática. */
function nomeDoAutor(evento: EventoAuditoria): string {
  return evento.usuario?.nome ?? "Sistema";
}

function LinhaEvento({ evento }: { evento: EventoAuditoria }) {
  const Icone = evento.tipo === "status" ? CheckCircle2 : CircleDollarSign;
  // Fundos distintos para a leitura rápida pedida pela #322 (ícone + cor).
  const classeIcone =
    evento.tipo === "status"
      ? "bg-primary/15 text-primary"
      : "bg-warning-bg text-warning-text";
  const quando = absoluteDateTime(evento.timestamp) ?? evento.timestamp;

  return (
    <li
      className="relative flex gap-3 pb-4 last:pb-0"
      data-testid={`auditoria-evento-${evento.id}`}
      data-tipo={evento.tipo}
    >
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${classeIcone}`}
        aria-hidden
      >
        <Icone className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm text-text">
          <span className="font-medium">{textoDaAcao(evento)}</span>
          <span className="text-text-muted"> · {nomeDoAutor(evento)}</span>
        </p>
        <p className="text-xs text-text-muted">
          <span className="sr-only">
            {evento.tipo === "status" ? "Evento de status. " : "Evento de saldo. "}
          </span>
          {quando}
          {evento.ip && <span> · IP {evento.ip}</span>}
        </p>
      </div>
    </li>
  );
}

/**
 * Painel de auditoria da demanda (#322): mudanças de status e movimentações de
 * saldo em ordem cronológica, com "carregar mais" sobre a paginação do backend
 * (`DemandViewSet.auditoria`, BE-7).
 */
export function DemandaAuditoria({ demandaId }: { demandaId: number }) {
  const { data, isPending, isFetchingNextPage, hasNextPage, fetchNextPage, error, refetch } =
    useInfiniteQuery({
      queryKey: qk.demandas.auditoria(demandaId),
      queryFn: ({ pageParam, signal }) =>
        listAuditoriaDemanda(demandaId, { offset: pageParam, limit: AUDITORIA_PAGINA }, signal),
      initialPageParam: 0,
      getNextPageParam: (pagina) => pagina.proxima_offset,
    });

  if (isPending) {
    return (
      <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
        <Spinner className="h-4 w-4 animate-spin" /> Carregando auditoria…
      </p>
    );
  }

  if (error) {
    return (
      <TabErroSection
        message={
          error instanceof ApiError
            ? error.message
            : "Não foi possível carregar a auditoria desta demanda."
        }
        onRetry={() => void refetch()}
      />
    );
  }

  const eventos = data.pages.flatMap((p) => p.resultados);
  const total = data.pages[data.pages.length - 1]?.total ?? eventos.length;

  if (eventos.length === 0) {
    return (
      <p className="text-sm text-text-muted">Esta demanda ainda não tem eventos de auditoria.</p>
    );
  }

  return (
    <div className="flex flex-col gap-3" data-testid="painel-auditoria">
      <ol className="flex list-none flex-col">
        {eventos.map((e) => (
          <LinhaEvento key={e.id} evento={e} />
        ))}
      </ol>
      {hasNextPage && (
        <button
          type="button"
          onClick={() => void fetchNextPage()}
          disabled={isFetchingNextPage}
          data-testid="auditoria-carregar-mais"
          className="self-start rounded border border-border px-3 py-1.5 text-sm text-text hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:opacity-60"
        >
          {isFetchingNextPage
            ? "Carregando…"
            : `Carregar mais (${eventos.length} de ${total})`}
        </button>
      )}
    </div>
  );
}
