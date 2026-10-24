"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Info } from "lucide-react";
import Spinner from "@/app/components/icons/Spinner";
import { PageHeader } from "@/app/components/layout/PageHeader";
import { TabErroSection } from "@/app/components/sgp/CrudTab/CrudTab";
import { Badge } from "@/app/components/ui/Badge/Badge";
import { Breadcrumb } from "@/app/components/ui/Breadcrumb/Breadcrumb";
import { DefinitionList } from "@/app/components/ui/DefinitionList/DefinitionList";
import { ApiError } from "@/app/lib/api";
import { absoluteDateTime } from "@/app/lib/datetime";
import { formatCurrencyBRL } from "@/app/lib/format";
import { badgeStatusDoPedido, getPedido } from "@/app/lib/remanejamentos";
import { qk } from "@/app/lib/queryKeys";
import { AcoesPedido, type Desfecho } from "../_components/AcoesPedido";

/**
 * Detalhe de um pedido de recurso extra (#321) — o link das notificações do
 * backend (`/sgd/remanejamentos/{id}`). Mostra o pedido, o parecer do
 * Articulador, a decisão da UGP e as ações do perfil logado.
 *
 * Quem enxerga o pedido é o backend (`pedidos_visiveis`): fora do escopo, 404.
 */
export default function PedidoRemanejamentoPage() {
  const { id } = useParams<{ id: string }>();
  const [desfecho, setDesfecho] = useState<Desfecho | null>(null);

  const { data: pedido, isPending, error, refetch } = useQuery({
    queryKey: qk.remanejamentos.detalhe(id),
    queryFn: ({ signal }) => getPedido(id, signal),
  });

  return (
    <>
      <PageHeader>
        <span className="truncate text-base font-semibold text-text">SGD</span>
      </PageHeader>

      <div className="mx-auto flex max-w-3xl flex-col gap-5" data-testid="pedido-page">
        <Breadcrumb
          items={[
            { label: "Início", href: "/dashboard" },
            { label: "SGD", href: "/sgd" },
            { label: "Remanejamentos", href: "/sgd/remanejamentos" },
            { label: `Pedido #${id}` },
          ]}
        />

        {isPending ? (
          <p role="status" className="flex items-center gap-2 text-sm text-text-muted">
            <Spinner className="h-4 w-4 animate-spin" /> Carregando…
          </p>
        ) : error ? (
          <TabErroSection
            message={
              error instanceof ApiError && error.status === 404
                ? "Pedido não encontrado ou fora do seu escopo."
                : error instanceof ApiError
                  ? error.message
                  : "Não foi possível carregar o pedido."
            }
            onRetry={() => void refetch()}
          />
        ) : pedido ? (
          <>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-text">
                Recurso extra — pedido #{pedido.id}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge status={badgeStatusDoPedido(pedido.status)} label={pedido.status_display} />
                <span className="text-sm text-text-muted">
                  {formatCurrencyBRL(pedido.valor_solicitado)} em {pedido.rubrica_nome}
                </span>
              </div>
            </div>

            {desfecho && (
              <p
                role="status"
                data-testid={`pedido-mensagem-${desfecho.tipo}`}
                className={`flex items-start gap-2 rounded-md border px-3 py-2.5 text-sm ${
                  desfecho.tipo === "sucesso"
                    ? "border-success-text bg-success-bg text-success-text"
                    : "border-info-text bg-info-bg text-info-text"
                }`}
              >
                {desfecho.tipo === "sucesso" ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                ) : (
                  <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                )}
                {desfecho.texto}
              </p>
            )}

            <section className="rounded-lg border border-border bg-surface p-5">
              <DefinitionList
                items={[
                  { label: "Solicitante", value: pedido.solicitante_nome },
                  {
                    label: "Demanda",
                    value: pedido.demanda_id ? (
                      <Link
                        href={`/sgd/demandas?visao=todas&demanda=${pedido.demanda_id}`}
                        className="text-primary hover:underline"
                        data-testid="pedido-link-demanda"
                      >
                        Demanda #{pedido.demanda_id}
                      </Link>
                    ) : undefined,
                  },
                  { label: "Rubrica", value: pedido.rubrica_nome },
                  { label: "Valor solicitado", value: formatCurrencyBRL(pedido.valor_solicitado) },
                  {
                    label: "Valor aprovado",
                    value:
                      pedido.valor_aprovado !== null ? formatCurrencyBRL(pedido.valor_aprovado) : undefined,
                  },
                  { label: "Pedido em", value: absoluteDateTime(pedido.criado_em) },
                  { label: "Justificativa", value: pedido.justificativa },
                ]}
              />
            </section>

            {pedido.parecer_articulador && (
              <section
                className="rounded-lg border border-border bg-surface p-5"
                data-testid="pedido-parecer"
              >
                <h2 className="text-sm font-semibold text-text">
                  {pedido.status === "devolvida" ? "Motivo da devolução" : "Parecer do Articulador"}
                </h2>
                <p className="mt-1 text-xs text-text-muted">{pedido.parecer_por_nome}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-text">{pedido.parecer_articulador}</p>
              </section>
            )}

            {pedido.justificativa_decisao && (
              <section
                className="rounded-lg border border-border bg-surface p-5"
                data-testid="pedido-decisao"
              >
                <h2 className="text-sm font-semibold text-text">Decisão da UGP: {pedido.status_display}</h2>
                <p className="mt-1 text-xs text-text-muted">
                  {pedido.decidido_por_nome}
                  {pedido.decidido_em && ` · ${absoluteDateTime(pedido.decidido_em)}`}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm text-text">{pedido.justificativa_decisao}</p>
              </section>
            )}

            <AcoesPedido pedido={pedido} onDecidido={setDesfecho} onIniciar={() => setDesfecho(null)} />
          </>
        ) : null}
      </div>
    </>
  );
}
