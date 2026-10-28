"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import type { Demanda } from "@/app/lib/demandas";
import { formatCurrencyBRL } from "@/app/lib/format";
import { qk } from "@/app/lib/queryKeys";
import { listPedidos } from "@/app/lib/remanejamentos";

/** Os status em que a demanda ainda pode ser submetida — `STATUS_EDITAVEIS` do backend. */
const EDITAVEIS = ["rascunho", "devolvida"];

/**
 * O desfecho do pedido de recurso extra na demanda bloqueada (#321), para o
 * solicitante: aprovado, a demanda pode ser submetida de novo; recusado, segue
 * bloqueada; em análise, aguarda.
 *
 * Mostra o pedido mais recente que `GET /sgd/remanejamentos/?demanda={id}`
 * devolve. A conferência do `demanda_id` fica como salvaguarda: o aviso nunca
 * mostra o pedido de outra demanda.
 */
export function AvisoRecursoExtra({ demanda }: { demanda: Demanda }) {
  const { data } = useQuery({
    queryKey: qk.remanejamentos.daDemanda(demanda.id),
    queryFn: ({ signal }) => listPedidos({ status: ["todos"], demanda: demanda.id }, signal),
    enabled: EDITAVEIS.includes(demanda.status),
  });

  const pedido = data?.pedidos[0];
  if (!EDITAVEIS.includes(demanda.status) || !pedido) return null;
  if (pedido.demanda_id !== String(demanda.id)) return null;

  const link = (
    <Link href={`/sgd/remanejamentos/${pedido.id}`} className="font-medium underline">
      Ver pedido #{pedido.id}
    </Link>
  );

  if (pedido.status === "aprovada" || pedido.status === "aprovada_parcialmente") {
    return (
      <div
        role="status"
        data-testid="aviso-recurso-extra-aprovado"
        className="flex items-start gap-2 rounded-md border border-success-text bg-success-bg px-3 py-2.5 text-sm text-success-text"
      >
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <p>
          Recurso extra {pedido.status === "aprovada" ? "aprovado" : "aprovado parcialmente"}:{" "}
          {formatCurrencyBRL(pedido.valor_aprovado)} a mais no seu limite em {pedido.rubrica_nome}.
          A demanda já pode ser submetida de novo.
          {pedido.status === "aprovada_parcialmente" &&
            " Se o valor não cobrir o que ela precisa, a submissão volta a ser bloqueada."}{" "}
          {link}
        </p>
      </div>
    );
  }

  if (pedido.status === "recusada") {
    return (
      <div
        role="status"
        data-testid="aviso-recurso-extra-recusado"
        className="flex items-start gap-2 rounded-md border border-error-text bg-error-bg px-3 py-2.5 text-sm text-error-text"
      >
        <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <p>
          Recurso extra recusado: {pedido.justificativa_decisao} A demanda continua bloqueada pelo
          limite individual. {link}
        </p>
      </div>
    );
  }

  return (
    <div
      role="status"
      data-testid="aviso-recurso-extra-em-analise"
      className="flex items-start gap-2 rounded-md border border-info-text bg-info-bg px-3 py-2.5 text-sm text-info-text"
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <p>
        Pedido de recurso extra de {formatCurrencyBRL(pedido.valor_solicitado)} em{" "}
        {pedido.rubrica_nome}: {pedido.status_display.toLowerCase()}. {link}
      </p>
    </div>
  );
}
